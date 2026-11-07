"""Entrenamiento y evaluación de las GNN con el objetivo composicional bajo CV por corral (#142).

Adapta la cabeza y la pérdida al objetivo del contrato v2 (sección 1; #146): la salida `[B, 3]`
del modelo se interpreta como `(z_1, z_2, ln T)` (`MODEL_OUTPUT_NAMES` de
`nutrigraphdt.models.composition`), derivada de `y_graph` con `compositional_graph_target`. No
hace falta cambiar la arquitectura: la cabeza lineal de tres salidas ya es la de
`components.ScfaRegressionHead`; lo que cambia es el significado de las salidas, la pérdida
(MSE estandarizado sobre los animales con objetivo válido, sin pseudoconteo) y la métrica de
detención temprana (esa misma pérdida sobre un `val` **interno al train de cada fold**, para que
ningún dato de evaluación del fold intervenga; criterio de aceptación de #142).

Piezas:

- `CompositionalTargetTransform`: `TargetTransform` (protocolo de `training.loop`) que convierte
  concentraciones → `(z_1, z_2, ln T)` estandarizados, ajustado solo con el train del fold.
- `split_inner_validation`: reparto interno del train del fold agrupado por corral y
  estratificado por dieta (`StratifiedGroupKFold`), determinista por semilla.
- `drop_inferred_edges`: ablación V-01 (respuesta 3): quita las aristas con
  `evidence_status == "inferred"` de un grafo.
- `train_compositional_model`: bucle con detención temprana sobre el `val` interno; puede
  guardar el estado al final de cada época y reanudarse desde él sin diferencias
  (`CompositionalTrainingState`, #181), y registrar por época la tasa y la magnitud de las
  violaciones de cada restricción, aparte de la pérdida (`ViolationLogRow`, #179).
- `run_compositional_fold` puede guardar la corrida de cada fold con su checkpoint
  (`compositional_tracking`, #180).
- `run_compositional_fold`: entrena una variante en un fold (escalado ajustado con el train del
  fold, val interno por corral) y evalúa el test del fold con `evaluate_composition` (métricas
  de D-03, globales y por día).

Uso de principio a fin: `scripts/evaluate_gnn_d1_composition.py`.
"""

from __future__ import annotations

import copy
import json
import math
import statistics
import time
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from numbers import Real
from pathlib import Path
from typing import Any, Final, cast

import torch
from torch import Tensor
from torch.nn.parameter import is_lazy
from torch_geometric.data import HeteroData
from torch_geometric.loader import DataLoader

from nutrigraphdt.constraints import (
    Constraint,
    compositional_constraint_inputs,
    constraint_catalog,
    constraint_penalty,
    evaluate_constraints,
)
from nutrigraphdt.models.composition import (
    MODEL_OUTPUT_NAMES,
    evaluate_composition,
)
from nutrigraphdt.models.gnn.base import GraphMetadata, SCFAGraphModel
from nutrigraphdt.models.gnn.batching import for_training
from nutrigraphdt.models.gnn.factory import GNNModelConfig, build_model
from nutrigraphdt.models.gnn.initialization import initialize_lazy_parameters
from nutrigraphdt.models.gnn.target import compositional_graph_target, masked_mse_loss
from nutrigraphdt.models.metrics import EvaluationReport
from nutrigraphdt.models.training.compositional_tracking import (
    CompositionalRunRecord,
    save_compositional_run,
)
from nutrigraphdt.models.training.config import TrainingConfig, set_seed
from nutrigraphdt.models.training.loop import NonFiniteError
from nutrigraphdt.models.training.scaling import FeatureScaler, TargetScaler
from nutrigraphdt.models.training.taxon_identity import TaxonIdentityConfig, TaxonLineageEncoder

INFERRED_STATUS: Final[str] = "inferred"
"""`evidence_status` de las aristas que quita la ablación (V-01, respuesta 3)."""

DEFAULT_INNER_FOLDS: Final[int] = 5
"""Número de folds del reparto interno del train de cada fold; un quinto de los corrales de
entrenamiento queda como `val` interno para la detención temprana."""

EDGE_ATTRIBUTE_KEYS: Final[tuple[str, ...]] = (
    "edge_index",
    "evidence_id",
    "evidence_status",
    "evidence_method",
)
"""Atributos de arista indexados por arista que `drop_inferred_edges` filtra a la vez."""

SELECTION_DESCRIPTION: Final[str] = (
    "Pérdida total composicional en el val interno "
    "(MSE estandarizado más la penalización de restricciones)"
)


class CompositionalTrainingError(ValueError):
    """El train o el val interno de un fold no tiene animales con objetivo composicional válido."""


# ---------------------------------------------------------------------------
# Objetivo y escalado
# ---------------------------------------------------------------------------


class CompositionalTargetTransform:
    """Conversión concentraciones → `(z_1, z_2, ln T)` estandarizados (protocolo TargetTransform).

    `fit` deriva el objetivo de los grafos de train con `compositional_graph_target` y ajusta un
    `TargetScaler` (media y desviación de cada salida) **solo con los animales de objetivo
    válido** (los tres AGCC medidos, finitos y positivos; sin pseudoconteo). `transform` toma
    `y_graph` e `y_graph_mask` (`[B, 3]`, mmol/kg) y devuelve el objetivo estandarizado con las
    filas inválidas en `0.0`; `validity` da la máscara `[B, 1]` que usa la pérdida.
    """

    def __init__(self, scaler: TargetScaler) -> None:
        self._scaler = scaler

    @classmethod
    def fit(cls, train_graphs: Sequence[HeteroData]) -> CompositionalTargetTransform:
        """Ajusta el escalado del objetivo con los grafos de entrenamiento del fold.

        Raises:
            CompositionalTrainingError: si ningún grafo de train tiene objetivo válido.
        """
        if not train_graphs:
            raise CompositionalTrainingError(
                "No hay grafos de train para ajustar el escalado del objetivo composicional."
            )
        target, valid = compositional_graph_target(
            torch.cat([g.y_graph for g in train_graphs]),
            torch.cat([g.y_graph_mask for g in train_graphs]),
        )
        valid_rows = valid[:, 0]
        if not bool(valid_rows.any()):
            raise CompositionalTrainingError(
                "Ningún animal de train tiene objetivo composicional válido "
                "(los tres AGCC medidos, finitos y positivos)."
            )
        scaler = TargetScaler.fit(
            target[valid_rows],
            targets=MODEL_OUTPUT_NAMES,
        )
        return cls(scaler)

    @property
    def scaler(self) -> TargetScaler:
        """El `TargetScaler` ajustado sobre las tres salidas."""
        return self._scaler

    def validity(self, y_graph: Tensor, y_graph_mask: Tensor) -> Tensor:
        """Máscara `[B, 1]` de animales con objetivo composicional válido."""
        _, valid = compositional_graph_target(y_graph, y_graph_mask)
        return valid

    def transform(self, y: Tensor, mask: Tensor | None = None) -> Tensor:
        """`y_graph` (`[B, 3]`, mmol/kg) → objetivo estandarizado; filas inválidas en `0.0`."""
        if mask is None:
            mask = torch.ones_like(y, dtype=torch.bool)
        target, valid = compositional_graph_target(y, mask)
        scaled = self._scaler.transform(target)
        return torch.where(valid, scaled, torch.zeros_like(scaled))

    def inverse_transform(self, y: Tensor, mask: Tensor | None = None) -> Tensor:
        """Salida estandarizada → `(z_1, z_2, ln T)` en las unidades del objetivo."""
        return self._scaler.inverse_transform(y)


# ---------------------------------------------------------------------------
# Reparto interno del fold y ablación de aristas
# ---------------------------------------------------------------------------


def split_inner_validation(
    sample_ids: Sequence[str],
    pens: Mapping[str, str],
    diets: Mapping[str, str],
    *,
    seed: int,
    inner_folds: int = DEFAULT_INNER_FOLDS,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Divide el train de un fold en train interno y val interno, agrupado por corral.

    Usa `StratifiedGroupKFold` (grupo `pen_code`, estrato dieta) sobre los animales ordenados y
    toma el primer fold como val interno (~ 1/`inner_folds` de los corrales). Es determinista
    para una misma `seed`; el test del fold nunca participa (criterio de aceptación de #142).

    Raises:
        CompositionalTrainingError: si falta el corral o la dieta de algún animal, si hay menos
            de `inner_folds` corrales o si el val interno queda vacío.
    """
    ids = sorted(str(s) for s in sample_ids)
    missing = [s for s in ids if s not in pens or s not in diets]
    if missing:
        raise CompositionalTrainingError(
            f"Animales sin corral o dieta para el val interno: {missing}."
        )
    if len({pens[s] for s in ids}) < inner_folds:
        raise CompositionalTrainingError(
            f"El train del fold tiene menos de {inner_folds} corrales; "
            "no se puede hacer el reparto interno."
        )
    try:
        from sklearn.model_selection import StratifiedGroupKFold
    except ImportError as error:  # pragma: no cover - depende del entorno
        raise ImportError(
            'El val interno por corral requiere scikit-learn: pip install -e ".[baselines]".'
        ) from error
    splitter = StratifiedGroupKFold(n_splits=inner_folds, shuffle=True, random_state=seed)
    _, val_index = next(splitter.split(ids, [diets[s] for s in ids], groups=[pens[s] for s in ids]))
    val = tuple(sorted(ids[int(i)] for i in val_index))
    if not val:
        raise CompositionalTrainingError("El val interno quedó vacío.")
    train = tuple(s for s in ids if s not in set(val))
    return train, val


def drop_inferred_edges(graph: HeteroData) -> HeteroData:
    """Copia de `graph` sin las aristas con `evidence_status == "inferred"` (ablación V-01).

    Filtra `edge_index` y los atributos de evidencia por arista. Las relaciones que se quedan
    sin aristas conservan su almacén vacío para no cambiar el esquema del lote.
    """
    result = graph.clone()
    for edge_type in graph.edge_types:
        store = graph[edge_type]
        status = getattr(store, "evidence_status", None)
        if status is None or "edge_index" not in store:
            continue
        keep = torch.tensor([str(value) != INFERRED_STATUS for value in status], dtype=torch.bool)
        out = result[edge_type]
        for key in EDGE_ATTRIBUTE_KEYS:
            if key in store:
                value = getattr(store, key)
                if isinstance(value, Tensor):
                    setattr(out, key, value[..., keep] if key == "edge_index" else value[keep])
                else:
                    setattr(out, key, [v for v, k in zip(value, keep.tolist(), strict=True) if k])
    return result


# ---------------------------------------------------------------------------
# Bucle de entrenamiento con objetivo composicional
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompositionalEpochRecord:
    """Pérdidas de datos, bioquímicas y totales en train y val interno."""

    epoch: int
    train_data_loss: float
    train_bio_loss: float
    train_total_loss: float
    val_data_loss: float
    val_bio_loss: float
    val_total_loss: float
    improved: bool
    constraint_lambda: float
    constraint_terms: tuple[str, ...]

    @property
    def train_loss(self) -> float:
        """Pérdida de train usada por el objetivo (alias compatible con el registro previo)."""
        return self.train_total_loss

    @property
    def val_loss(self) -> float:
        """Pérdida de val usada para detener (alias compatible con el registro previo)."""
        return self.val_total_loss

    def to_dict(self) -> dict[str, float | int | bool | str]:
        """Fila serializable de historial con la configuración del objetivo."""
        return {
            "epoch": self.epoch,
            "train_loss": self.train_loss,
            "train_data_loss": self.train_data_loss,
            "train_bio_loss": self.train_bio_loss,
            "train_total_loss": self.train_total_loss,
            "val_loss": self.val_loss,
            "val_data_loss": self.val_data_loss,
            "val_bio_loss": self.val_bio_loss,
            "val_total_loss": self.val_total_loss,
            "constraint_lambda": self.constraint_lambda,
            "constraint_terms": json.dumps(self.constraint_terms),
            "improved": self.improved,
        }


TRAIN_SUBSET: Final[str] = "train"
VAL_SUBSET: Final[str] = "val"
TEST_SUBSET: Final[str] = "test"


@dataclass(frozen=True)
class ViolationLogRow:
    """Tasa y magnitud de las violaciones de una restricción en un subconjunto y época (#179).

    Se calcula sobre las predicciones des-escaladas y reconstruidas de los animales con objetivo
    composicional válido del subconjunto (`sample_count`, el denominador); los demás se cuentan
    en `excluded_sample_count` y no entran en las métricas. Cada fila es de una sola restricción,
    con su espacio y su unidad: las magnitudes de restricciones distintas nunca se suman.

    - `subset`: `train` (predicciones de los pasos de entrenamiento de la época, como la pérdida
      de train), `val` (val interno, en modo evaluación al final de la época) o `test` (test del
      fold, con los pesos de la mejor época; `epoch` es esa época).
    - `violation_rate_percent` (VR) = 100 · `violation_count` / `sample_count`.
    - `mean_magnitude` (VMM) promedia la magnitud de todos los animales; la condicional, solo la
      de los violados (`None` si no hay); `worst_case_magnitude` (VWM) es la máxima.
    - `joint_feasibility_percent` (FR) es del subconjunto: porcentaje de animales que no violan
      ninguna de las restricciones monitoreadas.
    """

    epoch: int
    subset: str
    constraint: str
    kind: str
    space: str
    unit: str
    tolerance: float
    sample_count: int
    excluded_sample_count: int
    violation_count: int
    violation_rate_percent: float
    mean_magnitude: float
    conditional_mean_magnitude: float | None
    worst_case_magnitude: float
    joint_feasibility_percent: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


VIOLATION_LOG_COLUMNS: Final[tuple[str, ...]] = tuple(
    name for name in ViolationLogRow.__dataclass_fields__
)
"""Columnas del registro de violaciones por época, en orden."""


def violation_log_rows(
    output: Tensor,
    valid: Tensor,
    sample_ids: Sequence[str],
    constraints: Sequence[Constraint],
    *,
    epoch: int,
    subset: str,
) -> tuple[ViolationLogRow, ...]:
    """Filas de `ViolationLogRow` para salidas `(z_1, z_2, ln T)` ya des-escaladas.

    `valid` es la máscara `[B]` de animales con objetivo válido. Devuelve una fila por
    restricción, en el orden de `constraints`; sin restricciones, una tupla vacía.

    Raises:
        CompositionalReconstructionError: si alguna salida no se puede reconstruir.
    """
    if not constraints:
        return ()
    evaluation = evaluate_constraints(
        compositional_constraint_inputs(output),
        [str(sample_id) for sample_id in sample_ids],
        constraints=constraints,
        valid_mask=valid,
    )
    summary = evaluation.summary
    return tuple(
        ViolationLogRow(
            epoch=epoch,
            subset=subset,
            constraint=item.metadata.name,
            kind=item.metadata.kind.value,
            space=item.metadata.space.value,
            unit=item.metadata.unit,
            tolerance=item.metadata.tolerance,
            sample_count=item.sample_count,
            excluded_sample_count=summary.excluded_sample_count,
            violation_count=item.violation_count,
            violation_rate_percent=item.violation_rate_percent,
            mean_magnitude=item.mean_magnitude,
            conditional_mean_magnitude=item.conditional_mean_magnitude,
            worst_case_magnitude=item.worst_case_magnitude,
            joint_feasibility_percent=summary.joint_feasibility_rate_percent,
        )
        for item in summary.constraints
    )


AGGREGATED_VIOLATION_METRICS: Final[tuple[str, ...]] = (
    "violation_rate_percent",
    "mean_magnitude",
    "worst_case_magnitude",
    "joint_feasibility_percent",
)
"""Campos de `ViolationLogRow` que se agregan entre folds y semillas (#183)."""


@dataclass(frozen=True)
class ViolationAggregate:
    """Una métrica de violación de una restricción, agregada entre folds y semillas (#183).

    `mean` y `std` son la media y la desviación estándar muestral entre todos los
    `(semilla, fold)`; `seed_std`, la desviación entre las medias por semilla; `n`, el número
    de folds; `max`, el mayor valor por fold (para VWM, el peor caso de toda la evaluación). Las
    convenciones son las de `aggregate_fold_reports`.
    """

    subset: str
    constraint: str
    space: str
    unit: str
    metric: str
    mean: float
    std: float
    seed_std: float
    n: int
    max: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def aggregate_violation_log(
    rows: Sequence[tuple[int, ViolationLogRow]], *, subset: str = TEST_SUBSET
) -> tuple[ViolationAggregate, ...]:
    """Agrega por restricción las filas `(semilla, fila)` de un subconjunto (por omisión, test).

    Cada fold debe aportar una sola fila por restricción y subconjunto: las de `test`. Para
    agregar `train` o `val` hay que elegir antes una época (por ejemplo, la mejor).

    Raises:
        CompositionalTrainingError: si una restricción tiene filas de varias unidades o varias
            épocas en un mismo fold.
    """
    cells: dict[str, list[tuple[int, ViolationLogRow]]] = defaultdict(list)
    for seed, row in rows:
        if row.subset == subset:
            cells[row.constraint].append((seed, row))
    aggregates: list[ViolationAggregate] = []
    for constraint, pairs in cells.items():
        units = {(row.space, row.unit) for _, row in pairs}
        if len(units) != 1:
            raise CompositionalTrainingError(
                f"'{constraint}' tiene filas con espacios o unidades distintos: {sorted(units)}."
            )
        space, unit = next(iter(units))
        for metric in AGGREGATED_VIOLATION_METRICS:
            values = [float(getattr(row, metric)) for _, row in pairs]
            by_seed: dict[int, list[float]] = defaultdict(list)
            for (seed, _), value in zip(pairs, values, strict=True):
                by_seed[seed].append(value)
            seed_means = [statistics.fmean(v) for v in by_seed.values()]
            aggregates.append(
                ViolationAggregate(
                    subset=subset,
                    constraint=constraint,
                    space=space,
                    unit=unit,
                    metric=metric,
                    mean=statistics.fmean(values),
                    std=statistics.stdev(values) if len(values) > 1 else math.nan,
                    seed_std=statistics.stdev(seed_means) if len(seed_means) > 1 else math.nan,
                    n=len(values),
                    max=max(values),
                )
            )
    return tuple(aggregates)


class _SubsetOutputs:
    """Salidas estandarizadas, objetivos y `sample_id` de un subconjunto durante una época."""

    def __init__(self) -> None:
        self.outputs: list[Tensor] = []
        self.targets: list[Tensor] = []
        self.masks: list[Tensor] = []
        self.sample_ids: list[str] = []

    def add(self, output: Tensor, batch: HeteroData) -> None:
        self.outputs.append(output.detach().cpu())
        self.targets.append(batch.y_graph.detach().cpu())
        self.masks.append(batch.y_graph_mask.detach().cpu())
        self.sample_ids.extend(str(sample_id) for sample_id in batch.sample_id)

    def rows(
        self,
        transform: CompositionalTargetTransform,
        constraints: Sequence[Constraint],
        *,
        epoch: int,
        subset: str,
    ) -> tuple[ViolationLogRow, ...]:
        valid = transform.validity(torch.cat(self.targets), torch.cat(self.masks))[:, 0]
        output = transform.inverse_transform(torch.cat(self.outputs))
        return violation_log_rows(
            output, valid, self.sample_ids, constraints, epoch=epoch, subset=subset
        )


def _row_from_dict(data: Mapping[str, Any]) -> ViolationLogRow:
    return ViolationLogRow(**dict(data))


RESUME_FIELDS: Final[tuple[str, ...]] = (
    "lr",
    "weight_decay",
    "batch_size",
    "seed",
    "constraint_lambda",
    "constraint_terms",
)
"""Campos de `TrainingConfig` que deben coincidir para reanudar una corrida (#181).

`max_epochs`, `patience` y `device` pueden cambiar al reanudar: no alteran las épocas ya
corridas."""

TRAINING_STATE_VERSION: Final[str] = "1.1.0"
"""`1.1.0` agrega `violations` (#179); un estado `1.0.0` se lee sin violaciones."""


def _resume_fingerprint(config: TrainingConfig) -> dict[str, Any]:
    dumped = config.model_dump(mode="json")
    return {name: dumped[name] for name in RESUME_FIELDS}


def _record_from_dict(data: Mapping[str, Any]) -> CompositionalEpochRecord:
    values = dict(data)
    values["constraint_terms"] = tuple(values["constraint_terms"])
    return CompositionalEpochRecord(**values)


@dataclass(frozen=True)
class CompositionalTrainingState:
    """Estado al terminar una época: todo lo necesario para reanudar sin cambiar el resultado.

    Guarda los pesos y el optimizador de esa época, el mejor estado hasta ella, el contador de
    paciencia, el historial y el estado de los generadores aleatorios (el del `DataLoader` de
    train y el global de PyTorch, que usa el dropout). Reanudar desde el estado de la época `e`
    con la misma configuración (`RESUME_FIELDS`) da el mismo historial y los mismos pesos que el
    entrenamiento sin interrupción (`test_training_composite_loss.py`).
    """

    epoch: int
    model_state: Mapping[str, Tensor]
    optimizer_state: Mapping[str, Any]
    best_state: Mapping[str, Tensor]
    best_val_loss: float
    best_epoch: int
    epochs_without_improvement: int
    history: tuple[CompositionalEpochRecord, ...]
    loader_generator_state: Tensor
    rng_state: Tensor
    config: Mapping[str, Any]
    duration_seconds: float
    cuda_rng_state: Tensor | None = None
    violations: tuple[ViolationLogRow, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Diccionario de tensores y tipos simples, apto para `torch.load(weights_only=True)`."""
        return {
            "format_version": TRAINING_STATE_VERSION,
            "epoch": self.epoch,
            "model_state": dict(self.model_state),
            "optimizer_state": dict(self.optimizer_state),
            "best_state": dict(self.best_state),
            "best_val_loss": self.best_val_loss,
            "best_epoch": self.best_epoch,
            "epochs_without_improvement": self.epochs_without_improvement,
            "history": [
                {**asdict(record), "constraint_terms": list(record.constraint_terms)}
                for record in self.history
            ],
            "loader_generator_state": self.loader_generator_state,
            "rng_state": self.rng_state,
            "cuda_rng_state": self.cuda_rng_state,
            "config": dict(self.config),
            "duration_seconds": self.duration_seconds,
            "violations": [row.to_dict() for row in self.violations],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CompositionalTrainingState:
        version = str(data.get("format_version", ""))
        if version.split(".")[0] != TRAINING_STATE_VERSION.split(".")[0]:
            raise CompositionalTrainingError(
                f"Estado de entrenamiento con formato {version!r}; se esperaba "
                f"{TRAINING_STATE_VERSION}."
            )
        return cls(
            epoch=int(data["epoch"]),
            model_state=data["model_state"],
            optimizer_state=data["optimizer_state"],
            best_state=data["best_state"],
            best_val_loss=float(data["best_val_loss"]),
            best_epoch=int(data["best_epoch"]),
            epochs_without_improvement=int(data["epochs_without_improvement"]),
            history=tuple(_record_from_dict(row) for row in data["history"]),
            loader_generator_state=data["loader_generator_state"],
            rng_state=data["rng_state"],
            cuda_rng_state=data.get("cuda_rng_state"),
            config=dict(data["config"]),
            duration_seconds=float(data["duration_seconds"]),
            violations=tuple(_row_from_dict(row) for row in data.get("violations", [])),
        )


def save_training_state(state: CompositionalTrainingState, path: str | Path) -> Path:
    """Escribe el estado con `torch.save` (sin objetos de Python arbitrarios)."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(state.to_dict(), out)
    return out


def load_training_state(path: str | Path) -> CompositionalTrainingState:
    """Lee un estado guardado con `save_training_state` usando `weights_only=True`."""
    return CompositionalTrainingState.from_dict(torch.load(Path(path), weights_only=True))


@dataclass(frozen=True)
class CompositionalTrainingResult:
    """Resultado de `train_compositional_model`. `model` queda con los pesos de `best_epoch`."""

    model: SCFAGraphModel
    history: tuple[CompositionalEpochRecord, ...]
    best_epoch: int
    best_val_loss: float
    stopped_early: bool
    duration_seconds: float
    violations: tuple[ViolationLogRow, ...] = ()
    """Registro por época de `train` y `val` si se pidió monitorear restricciones (#179)."""

    @property
    def epochs_run(self) -> int:
        return len(self.history)


def _check_finite(values: Tensor, what: str) -> None:
    if not bool(torch.isfinite(values).all()):
        raise NonFiniteError(f"Hay NaN o infinitos en {what}; se detiene el entrenamiento.")


def _batch_target(
    batch: HeteroData, transform: CompositionalTargetTransform
) -> tuple[Tensor, Tensor]:
    """Objetivo estandarizado `[B, 3]` y máscara `[B, 3]` (validez `[B, 1]` replicada)."""
    target = transform.transform(batch.y_graph, batch.y_graph_mask)
    valid = transform.validity(batch.y_graph, batch.y_graph_mask)
    return target, valid.expand_as(target)


def _selected_constraints(config: TrainingConfig) -> tuple[Constraint, ...]:
    """Resuelve los nombres configurados contra el registro activo de restricciones."""
    selected_names = set(config.constraint_terms)
    return tuple(
        constraint
        for constraint in constraint_catalog().values()
        if constraint.metadata.name in selected_names
    )


def _bio_loss(
    output: Tensor,
    batch: HeteroData,
    transform: CompositionalTargetTransform,
    constraints: tuple[Constraint, ...],
) -> Tensor:
    """Penalización de restricciones sobre animales válidos del lote."""
    valid = transform.validity(batch.y_graph, batch.y_graph_mask)[:, 0]
    if not bool(valid.any()):
        return output.sum() * 0.0
    output_descaled = transform.inverse_transform(output)
    inputs = compositional_constraint_inputs(output_descaled)
    evaluation = evaluate_constraints(
        inputs,
        [str(sample_id) for sample_id in batch.sample_id],
        constraints=constraints,
        valid_mask=valid,
    )
    return constraint_penalty(
        evaluation.results,
        {constraint.metadata.name: cast(Real, 1.0) for constraint in constraints},
    )


def _clone_state(model: SCFAGraphModel) -> dict[str, Tensor]:
    return {name: value.detach().clone() for name, value in model.state_dict().items()}


def train_compositional_model(
    model: SCFAGraphModel,
    train_graphs: Sequence[HeteroData],
    val_graphs: Sequence[HeteroData],
    config: TrainingConfig,
    transform: CompositionalTargetTransform,
    *,
    resume_from: CompositionalTrainingState | None = None,
    on_epoch_end: Callable[[CompositionalTrainingState], None] | None = None,
    monitor_constraints: Sequence[Constraint] = (),
) -> CompositionalTrainingResult:
    """Entrena `model` con el objetivo composicional y detiene con el val interno.

    El objetivo suma el MSE estandarizado y, si `constraint_lambda > 0`, la penalización
    seleccionada. La detención temprana usa la pérdida total de `val_graphs` (val **interno**).
    Con lambda cero no se des-escala ni reconstruye la salida, ni se evalúan restricciones.
    Tras `config.patience` épocas sin mejora se restauran los pesos de la mejor época. No fija la
    semilla: llame a `set_seed` antes de construir el modelo y los `DataLoader`.

    Reanudación (#181): `on_epoch_end` recibe el `CompositionalTrainingState` de cada época (por
    ejemplo, para `save_training_state`). Con `resume_from`, el entrenamiento sigue desde la
    época siguiente a la del estado, con sus pesos, optimizador, paciencia, historial y
    generadores aleatorios; el resultado es el mismo que sin interrupción. `model` debe ser de
    la misma variante y dimensiones que el que produjo el estado.

    Registro de violaciones (#179): con `monitor_constraints`, cada época agrega a
    `violations` una `ViolationLogRow` por restricción para `train` y para `val`, sin que el
    monitoreo intervenga en la pérdida ni en la detención temprana: con lambda cero, los pesos y
    el historial son los mismos que sin monitoreo. Sin restricciones monitoreadas no se
    des-escala ni se reconstruye nada.

    Raises:
        CompositionalTrainingError: si train o val no tienen animales con objetivo válido, o si
            `resume_from` viene de una configuración distinta en `RESUME_FIELDS`.
        NonFiniteError: si la pérdida o las predicciones tienen NaN o infinitos.
    """
    device = torch.device(config.device)
    for subset, graphs in (("train", train_graphs), ("val interno", val_graphs)):
        if not any(bool(transform.validity(g.y_graph, g.y_graph_mask).any()) for g in graphs):
            raise CompositionalTrainingError(
                f"{subset} no tiene animales con objetivo composicional válido."
            )
    generator = torch.Generator().manual_seed(config.seed)
    train_loader = DataLoader(
        [for_training(graph) for graph in train_graphs],
        batch_size=config.batch_size,
        shuffle=True,
        generator=generator,
    )
    val_loader = DataLoader(
        [for_training(graph) for graph in val_graphs],
        batch_size=config.batch_size,
        shuffle=False,
    )
    model.to(device)
    if any(is_lazy(parameter) for parameter in model.parameters()):
        initialize_lazy_parameters(model)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)
    constraints = _selected_constraints(config) if config.constraint_lambda > 0 else ()
    fingerprint = _resume_fingerprint(config)

    start = time.perf_counter()
    history: list[CompositionalEpochRecord] = []
    best_state = _clone_state(model)
    best_loss = math.inf
    best_epoch = 0
    epochs_without_improvement = 0
    stopped_early = False
    first_epoch = 1
    previous_duration = 0.0
    monitored = tuple(monitor_constraints)
    violations: list[ViolationLogRow] = []
    if resume_from is not None:
        if dict(resume_from.config) != fingerprint:
            raise CompositionalTrainingError(
                "El estado a reanudar viene de otra configuración: "
                f"{dict(resume_from.config)} frente a {fingerprint}."
            )
        model.load_state_dict(resume_from.model_state)
        optimizer.load_state_dict(dict(resume_from.optimizer_state))
        best_state = {name: value.clone() for name, value in resume_from.best_state.items()}
        best_loss = resume_from.best_val_loss
        best_epoch = resume_from.best_epoch
        epochs_without_improvement = resume_from.epochs_without_improvement
        history = list(resume_from.history)
        violations = list(resume_from.violations)
        generator.set_state(resume_from.loader_generator_state)
        torch.set_rng_state(resume_from.rng_state)
        if resume_from.cuda_rng_state is not None and device.type == "cuda":
            torch.cuda.set_rng_state(resume_from.cuda_rng_state, device)
        first_epoch = resume_from.epoch + 1
        previous_duration = resume_from.duration_seconds
        stopped_early = epochs_without_improvement >= config.patience
    for epoch in range(first_epoch, config.max_epochs + 1):
        if stopped_early:
            break
        model.train()
        train_total = 0.0
        train_bio_total = 0.0
        train_cells = 0
        train_valid_animals = 0
        train_outputs = _SubsetOutputs()
        for batch in train_loader:
            batch = batch.to(device)
            target, mask = _batch_target(batch, transform)
            optimizer.zero_grad()
            output = model(batch)
            _check_finite(output, f"las predicciones de train (época {epoch})")
            if monitored:
                train_outputs.add(output, batch)
            data_loss = masked_mse_loss(output, target, mask)
            bio_loss = (
                _bio_loss(output, batch, transform, constraints)
                if config.constraint_lambda > 0
                else None
            )
            loss = (
                data_loss if bio_loss is None else data_loss + config.constraint_lambda * bio_loss
            )
            _check_finite(loss, f"la pérdida de train (época {epoch})")
            loss.backward()  # type: ignore[no-untyped-call]
            optimizer.step()
            observed = int(mask.sum())
            train_total += float(data_loss.detach()) * observed
            train_cells += observed
            if bio_loss is not None:
                valid_animals = int(transform.validity(batch.y_graph, batch.y_graph_mask).sum())
                train_bio_total += float(bio_loss.detach()) * valid_animals
                train_valid_animals += valid_animals

        model.eval()
        total = 0.0
        bio_total = 0.0
        cells = 0
        valid_animals_total = 0
        val_outputs = _SubsetOutputs()
        with torch.no_grad():
            for batch in val_loader:
                batch = batch.to(device)
                target, mask = _batch_target(batch, transform)
                output = model(batch)
                _check_finite(output, f"las predicciones del val interno (época {epoch})")
                if monitored:
                    val_outputs.add(output, batch)
                data_loss = masked_mse_loss(output, target, mask)
                bio_loss = (
                    _bio_loss(output, batch, transform, constraints)
                    if config.constraint_lambda > 0
                    else None
                )
                loss = (
                    data_loss
                    if bio_loss is None
                    else data_loss + config.constraint_lambda * bio_loss
                )
                observed = int(mask.sum())
                total += float(data_loss) * observed
                cells += observed
                if bio_loss is not None:
                    valid_animals = int(transform.validity(batch.y_graph, batch.y_graph_mask).sum())
                    bio_total += float(bio_loss) * valid_animals
                    valid_animals_total += valid_animals
        train_data_loss = train_total / train_cells
        train_bio_loss = train_bio_total / train_valid_animals if train_valid_animals else 0.0
        train_total_loss = (
            train_data_loss
            if config.constraint_lambda == 0
            else train_data_loss + config.constraint_lambda * train_bio_loss
        )
        val_data_loss = total / cells
        val_bio_loss = bio_total / valid_animals_total if valid_animals_total else 0.0
        val_total_loss = (
            val_data_loss
            if config.constraint_lambda == 0
            else val_data_loss + config.constraint_lambda * val_bio_loss
        )
        improved = val_total_loss < best_loss
        if improved:
            best_loss, best_epoch = val_total_loss, epoch
            best_state = {
                name: value.detach().clone() for name, value in model.state_dict().items()
            }
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
        history.append(
            CompositionalEpochRecord(
                epoch=epoch,
                train_data_loss=train_data_loss,
                train_bio_loss=train_bio_loss,
                train_total_loss=train_total_loss,
                val_data_loss=val_data_loss,
                val_bio_loss=val_bio_loss,
                val_total_loss=val_total_loss,
                improved=improved,
                constraint_lambda=config.constraint_lambda,
                constraint_terms=config.constraint_terms,
            )
        )
        if monitored:
            for subset, outputs in ((TRAIN_SUBSET, train_outputs), (VAL_SUBSET, val_outputs)):
                violations.extend(outputs.rows(transform, monitored, epoch=epoch, subset=subset))
        if epochs_without_improvement >= config.patience:
            stopped_early = True
        if on_epoch_end is not None:
            on_epoch_end(
                CompositionalTrainingState(
                    epoch=epoch,
                    model_state=_clone_state(model),
                    optimizer_state=copy.deepcopy(optimizer.state_dict()),
                    best_state={name: value.clone() for name, value in best_state.items()},
                    best_val_loss=best_loss,
                    best_epoch=best_epoch,
                    epochs_without_improvement=epochs_without_improvement,
                    history=tuple(history),
                    loader_generator_state=generator.get_state(),
                    rng_state=torch.get_rng_state(),
                    cuda_rng_state=(
                        torch.cuda.get_rng_state(device) if device.type == "cuda" else None
                    ),
                    config=fingerprint,
                    duration_seconds=previous_duration + time.perf_counter() - start,
                    violations=tuple(violations),
                )
            )
        if stopped_early:
            break

    model.load_state_dict(best_state)
    return CompositionalTrainingResult(
        model=model,
        history=tuple(history),
        best_epoch=best_epoch,
        best_val_loss=best_loss,
        stopped_early=stopped_early,
        duration_seconds=previous_duration + time.perf_counter() - start,
        violations=tuple(violations),
    )


# ---------------------------------------------------------------------------
# Evaluación de un fold
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FoldEvaluation:
    """Resultado de entrenar y evaluar una variante en un fold de una semilla."""

    seed: int
    fold: int
    model_name: str
    edges_arm: str
    report: EvaluationReport
    predictions: tuple[dict[str, Any], ...]
    best_epoch: int
    epochs_run: int
    stopped_early: bool
    duration_seconds: float
    n_train: int
    n_inner_val: int
    n_test: int
    history: tuple[CompositionalEpochRecord, ...] = field(default_factory=tuple)
    violations: tuple[ViolationLogRow, ...] = field(default_factory=tuple)
    """`train` y `val` por época y `test` con los pesos de la mejor época (#179)."""
    run_dir: Path | None = None
    """Directorio de la corrida guardada con `runs_dir` (#180); `None` si no se guardó."""
    taxon_vocabulary: tuple[str, ...] = ()
    """Grupos de linaje ajustados con el train del fold, si se usó `taxon_identity` (#266)."""

    @property
    def run_id(self) -> str | None:
        return self.run_dir.name if self.run_dir is not None else None


def _scaled(graphs: Sequence[HeteroData], scaler: FeatureScaler) -> list[HeteroData]:
    return scaler.transform([for_training(graph) for graph in graphs])


def _check_pen_isolation(
    first: Sequence[str], second: Sequence[str], pens: Mapping[str, str], what: str
) -> None:
    """Ningún animal ni corral puede estar en los dos conjuntos (#183)."""
    shared_animals = sorted(set(first) & set(second))
    missing = sorted(s for s in (*first, *second) if s not in pens)
    if missing:
        raise CompositionalTrainingError(f"Animales sin corral: {missing}.")
    shared_pens = sorted({pens[s] for s in first} & {pens[s] for s in second})
    if shared_animals or shared_pens:
        raise CompositionalTrainingError(
            f"Fuga entre {what}: animales {shared_animals}, corrales {shared_pens}."
        )


def run_compositional_fold(
    *,
    seed: int,
    fold: int,
    model_name: str,
    edges_arm: str,
    train_ids: Sequence[str],
    test_ids: Sequence[str],
    graphs: Mapping[str, HeteroData],
    pens: Mapping[str, str],
    diets: Mapping[str, str],
    days: Mapping[str, str],
    model_config: GNNModelConfig,
    metadata: GraphMetadata,
    config: TrainingConfig,
    inner_folds: int = DEFAULT_INNER_FOLDS,
    monitor_constraints: Sequence[Constraint] = (),
    runs_dir: str | Path | None = None,
    run_context: Mapping[str, Any] | None = None,
    taxon_identity: TaxonIdentityConfig | None = None,
) -> FoldEvaluation:
    """Entrena una variante en un fold y devuelve las métricas D-03 de su test.

    `graphs` (indexados por `sample_id`) ya deben tener `y_graph`, las aristas inversas y los
    tipos alineados con `metadata`. El escalado de features y del objetivo se ajusta solo con el
    train del fold; la detención temprana usa un val interno por corral (`split_inner_validation`
    con `seed` derivada de la del fold); el test del fold solo se evalúa al final.
    `edges_arm` es la etiqueta de la ablación (`"with_inferred"` o `"without_inferred"`); la
    selección de aristas la hace el llamador pasando `graphs` ya filtrados. Con
    `monitor_constraints`, `violations` registra las violaciones por época de `train` y `val` y
    las del test del fold (#179). Con `runs_dir`, guarda la corrida del fold
    (`save_compositional_run`, #180); `run_context` aporta `dataset_id`, `plan`
    (`PLAN_FIELDS`), `cohort`, `source` y `repo_root`.

    Con `taxon_identity`, los taxones se codifican con su linaje multiplicado por la abundancia
    (decisión de #239). El vocabulario se ajusta solo con el train interno del fold, antes de
    escalar, y `metadata` se adapta a sus columnas.

    Antes de entrenar comprueba que ningún corral esté a la vez en el train y el test del fold,
    ni en el train y el val interno (#183).

    Raises:
        CompositionalTrainingError: si falta algún animal en `graphs`, si un corral cruza train y
            test o train y val interno, o si el train/val interno no tiene objetivo válido.
    """
    missing = [s for s in (*train_ids, *test_ids) if s not in graphs]
    if missing:
        raise CompositionalTrainingError(f"Animales del fold sin grafo: {missing}.")
    _check_pen_isolation(train_ids, test_ids, pens, "train y test del fold")
    set_seed(config.seed)
    inner_train_ids, inner_val_ids = split_inner_validation(
        train_ids, pens, diets, seed=config.seed, inner_folds=inner_folds
    )
    _check_pen_isolation(inner_train_ids, inner_val_ids, pens, "train y val interno")
    train_graphs = [graphs[s] for s in inner_train_ids]
    val_graphs = [graphs[s] for s in inner_val_ids]
    test_graphs = [graphs[s] for s in test_ids]

    taxon_encoder: TaxonLineageEncoder | None = None
    if taxon_identity is not None:
        taxon_encoder = TaxonLineageEncoder.fit(train_graphs, taxon_identity)
        train_graphs = taxon_encoder.transform(train_graphs)
        val_graphs = taxon_encoder.transform(val_graphs)
        test_graphs = taxon_encoder.transform(test_graphs)
        metadata = taxon_encoder.adapt_metadata(metadata)

    feature_scaler = FeatureScaler.fit(train_graphs)
    transform = CompositionalTargetTransform.fit(train_graphs)
    model = build_model(model_config, metadata, target_names=MODEL_OUTPUT_NAMES)
    result = train_compositional_model(
        model,
        _scaled(train_graphs, feature_scaler),
        _scaled(val_graphs, feature_scaler),
        config,
        transform,
        monitor_constraints=monitor_constraints,
    )

    loader = DataLoader(_scaled(test_graphs, feature_scaler), batch_size=config.batch_size)
    device = next(model.parameters()).device
    model.eval()
    outputs: list[Tensor] = []
    measured: list[Tensor] = []
    masks: list[Tensor] = []
    sample_ids: list[str] = []
    with torch.no_grad():
        for batch in loader:
            batch = batch.to(device)
            output = model(batch)
            _check_finite(output, "las predicciones del test del fold")
            outputs.append(transform.inverse_transform(output.cpu()))
            measured.append(batch.y_graph.cpu())
            masks.append(batch.y_graph_mask.cpu())
            sample_ids.extend(str(s) for s in batch.sample_id)
    output_all = torch.cat(outputs)
    measured_all = torch.cat(measured)
    mask_all = torch.cat(masks)
    test_violations = violation_log_rows(
        output_all,
        transform.validity(measured_all, mask_all)[:, 0],
        sample_ids,
        tuple(monitor_constraints),
        epoch=result.best_epoch,
        subset=TEST_SUBSET,
    )

    true_concentrations: list[list[float | None]] = []
    for row in range(measured_all.shape[0]):
        true_concentrations.append(
            [
                float(measured_all[row, column]) if bool(mask_all[row, column]) else None
                for column in range(measured_all.shape[1])
            ]
        )
    report = evaluate_composition(
        true_concentrations,
        output_all.tolist(),
        model_name,
        split="test",
        sampling_days=[days.get(s, "?") for s in sample_ids],
    )
    predictions = tuple(
        {
            "sample_id": sample_id,
            "seed": seed,
            "fold": fold,
            "model": model_name,
            "edges_arm": edges_arm,
            "sampling_day": days.get(sample_id, "?"),
            "z1": float(output_all[row, 0]),
            "z2": float(output_all[row, 1]),
            "log_total": float(output_all[row, 2]),
        }
        for row, sample_id in enumerate(sample_ids)
    )
    violations = (*result.violations, *test_violations)
    run_dir: Path | None = None
    if runs_dir is not None:
        context = dict(run_context or {})
        run_dir = save_compositional_run(
            CompositionalRunRecord(
                model=result.model,
                model_config=model_config,
                training_config=config,
                feature_scaler=feature_scaler,
                target_scaler=transform.scaler,
                variant=model_name,
                edges_arm=edges_arm,
                dataset_id=str(context.get("dataset_id", config.dataset_id)),
                seed=seed,
                fold=fold,
                plan=context.get("plan", {}),
                cohort=context.get("cohort", {}),
                sample_ids={
                    "train": inner_train_ids,
                    "inner_val": inner_val_ids,
                    "test": tuple(sample_ids),
                },
                monitored_constraints=[c.metadata.name for c in monitor_constraints],
                history=[record.to_dict() for record in result.history],
                violations=[row.to_dict() for row in violations],
                metrics=report,
                predictions=predictions,
                best_epoch=result.best_epoch,
                stopped_early=result.stopped_early,
                duration_seconds=result.duration_seconds,
                source=context.get("source", {}),
                taxon_identity=taxon_encoder.to_dict() if taxon_encoder is not None else None,
            ),
            runs_dir,
            repo_root=context.get("repo_root"),
        )
    return FoldEvaluation(
        seed=seed,
        fold=fold,
        model_name=model_name,
        edges_arm=edges_arm,
        report=report,
        predictions=predictions,
        best_epoch=result.best_epoch,
        epochs_run=result.epochs_run,
        stopped_early=result.stopped_early,
        duration_seconds=result.duration_seconds,
        n_train=len(inner_train_ids),
        n_inner_val=len(inner_val_ids),
        n_test=len(sample_ids),
        history=result.history,
        violations=violations,
        run_dir=run_dir,
        taxon_vocabulary=taxon_encoder.vocabulary if taxon_encoder is not None else (),
    )


__all__ = [
    "AGGREGATED_VIOLATION_METRICS",
    "DEFAULT_INNER_FOLDS",
    "INFERRED_STATUS",
    "RESUME_FIELDS",
    "SELECTION_DESCRIPTION",
    "TEST_SUBSET",
    "TRAINING_STATE_VERSION",
    "TRAIN_SUBSET",
    "VAL_SUBSET",
    "VIOLATION_LOG_COLUMNS",
    "CompositionalEpochRecord",
    "CompositionalTargetTransform",
    "CompositionalTrainingError",
    "CompositionalTrainingResult",
    "CompositionalTrainingState",
    "FoldEvaluation",
    "ViolationAggregate",
    "ViolationLogRow",
    "aggregate_violation_log",
    "drop_inferred_edges",
    "load_training_state",
    "run_compositional_fold",
    "save_training_state",
    "split_inner_validation",
    "train_compositional_model",
    "violation_log_rows",
]
