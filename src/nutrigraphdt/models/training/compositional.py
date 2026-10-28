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
- `train_compositional_model`: bucle con detención temprana sobre el `val` interno.
- `run_compositional_fold`: entrena una variante en un fold (escalado ajustado con el train del
  fold, val interno por corral) y evalúa el test del fold con `evaluate_composition` (métricas
  de D-03, globales y por día).

Uso de principio a fin: `scripts/evaluate_gnn_d1_composition.py`.
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from numbers import Real
from typing import Any, Final, cast

import torch
from torch import Tensor
from torch.nn.parameter import is_lazy
from torch_geometric.data import HeteroData
from torch_geometric.loader import DataLoader

from nutrigraphdt.constraints import (
    Constraint,
    compositional_constraint_inputs,
    constraint_penalty,
    evaluate_constraints,
    structural_constraints,
)
from nutrigraphdt.models.composition import (
    MODEL_OUTPUT_NAMES,
    evaluate_composition,
)
from nutrigraphdt.models.gnn.base import GraphMetadata, SCFAGraphModel
from nutrigraphdt.models.gnn.factory import GNNModelConfig, build_model
from nutrigraphdt.models.gnn.initialization import initialize_lazy_parameters
from nutrigraphdt.models.gnn.target import compositional_graph_target, masked_mse_loss
from nutrigraphdt.models.metrics import EvaluationReport
from nutrigraphdt.models.training.config import TrainingConfig, set_seed
from nutrigraphdt.models.training.loop import NonFiniteError
from nutrigraphdt.models.training.scaling import FeatureScaler, TargetScaler

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


@dataclass(frozen=True)
class CompositionalTrainingResult:
    """Resultado de `train_compositional_model`. `model` queda con los pesos de `best_epoch`."""

    model: SCFAGraphModel
    history: tuple[CompositionalEpochRecord, ...]
    best_epoch: int
    best_val_loss: float
    stopped_early: bool
    duration_seconds: float

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
        for constraint in structural_constraints()
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


def train_compositional_model(
    model: SCFAGraphModel,
    train_graphs: Sequence[HeteroData],
    val_graphs: Sequence[HeteroData],
    config: TrainingConfig,
    transform: CompositionalTargetTransform,
) -> CompositionalTrainingResult:
    """Entrena `model` con el objetivo composicional y detiene con el val interno.

    El objetivo suma el MSE estandarizado y, si `constraint_lambda > 0`, la penalización
    seleccionada. La detención temprana usa la pérdida total de `val_graphs` (val **interno**).
    Con lambda cero no se des-escala ni reconstruye la salida, ni se evalúan restricciones.
    Tras `config.patience` épocas sin mejora se restauran los pesos de la mejor época. No fija la
    semilla: llame a `set_seed` antes de construir el modelo y los `DataLoader`.

    Raises:
        CompositionalTrainingError: si train o val no tienen animales con objetivo válido.
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
        list(train_graphs), batch_size=config.batch_size, shuffle=True, generator=generator
    )
    val_loader = DataLoader(list(val_graphs), batch_size=config.batch_size, shuffle=False)
    model.to(device)
    if any(is_lazy(parameter) for parameter in model.parameters()):
        initialize_lazy_parameters(model)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)
    constraints = _selected_constraints(config) if config.constraint_lambda > 0 else ()

    start = time.perf_counter()
    history: list[CompositionalEpochRecord] = []
    best_state = {name: value.detach().clone() for name, value in model.state_dict().items()}
    best_loss = math.inf
    best_epoch = 0
    epochs_without_improvement = 0
    stopped_early = False
    for epoch in range(1, config.max_epochs + 1):
        model.train()
        train_total = 0.0
        train_bio_total = 0.0
        train_cells = 0
        train_valid_animals = 0
        for batch in train_loader:
            batch = batch.to(device)
            target, mask = _batch_target(batch, transform)
            optimizer.zero_grad()
            output = model(batch)
            _check_finite(output, f"las predicciones de train (época {epoch})")
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
        with torch.no_grad():
            for batch in val_loader:
                batch = batch.to(device)
                target, mask = _batch_target(batch, transform)
                output = model(batch)
                _check_finite(output, f"las predicciones del val interno (época {epoch})")
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
        if epochs_without_improvement >= config.patience:
            stopped_early = True
            break

    model.load_state_dict(best_state)
    return CompositionalTrainingResult(
        model=model,
        history=tuple(history),
        best_epoch=best_epoch,
        best_val_loss=best_loss,
        stopped_early=stopped_early,
        duration_seconds=time.perf_counter() - start,
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


def _scaled(graphs: Sequence[HeteroData], scaler: FeatureScaler) -> list[HeteroData]:
    return scaler.transform(list(graphs))


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
) -> FoldEvaluation:
    """Entrena una variante en un fold y devuelve las métricas D-03 de su test.

    `graphs` (indexados por `sample_id`) ya deben tener `y_graph`, las aristas inversas y los
    tipos alineados con `metadata`. El escalado de features y del objetivo se ajusta solo con el
    train del fold; la detención temprana usa un val interno por corral (`split_inner_validation`
    con `seed` derivada de la del fold); el test del fold solo se evalúa al final.
    `edges_arm` es la etiqueta de la ablación (`"with_inferred"` o `"without_inferred"`); la
    selección de aristas la hace el llamador pasando `graphs` ya filtrados.

    Raises:
        CompositionalTrainingError: si falta algún animal en `graphs` o el train/val interno no
            tiene objetivo válido.
    """
    missing = [s for s in (*train_ids, *test_ids) if s not in graphs]
    if missing:
        raise CompositionalTrainingError(f"Animales del fold sin grafo: {missing}.")
    set_seed(config.seed)
    inner_train_ids, inner_val_ids = split_inner_validation(
        train_ids, pens, diets, seed=config.seed, inner_folds=inner_folds
    )
    train_graphs = [graphs[s] for s in inner_train_ids]
    val_graphs = [graphs[s] for s in inner_val_ids]
    test_graphs = [graphs[s] for s in test_ids]

    feature_scaler = FeatureScaler.fit(train_graphs)
    transform = CompositionalTargetTransform.fit(train_graphs)
    model = build_model(model_config, metadata)
    result = train_compositional_model(
        model,
        _scaled(train_graphs, feature_scaler),
        _scaled(val_graphs, feature_scaler),
        config,
        transform,
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
    )


__all__ = [
    "DEFAULT_INNER_FOLDS",
    "INFERRED_STATUS",
    "SELECTION_DESCRIPTION",
    "CompositionalEpochRecord",
    "CompositionalTargetTransform",
    "CompositionalTrainingError",
    "CompositionalTrainingResult",
    "FoldEvaluation",
    "drop_inferred_edges",
    "run_compositional_fold",
    "split_inner_validation",
    "train_compositional_model",
]
