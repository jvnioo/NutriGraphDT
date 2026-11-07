"""Trazabilidad de las corridas composicionales por fold: registro, checkpoint y recarga (#180).

Extiende la trazabilidad de A44-5 (`tracking.py`) al entrenamiento composicional con
restricciones (A66 y A68). Cada fold entrenado puede dejar un directorio
`runs/<run_id>/` (ignorado por Git) con:

- `run.json`: configuración efectiva de entrenamiento y modelo, nombres de salida, semilla del
  plan, fold y semilla de entrenamiento, λ y términos de la pérdida, restricciones monitoreadas,
  plan de folds (ruta y SHA-256 canónico, #133), cohorte, animales de cada subconjunto,
  escalado, mejor época, commit de Git, entorno, tolerancia de recarga y archivos;
- `checkpoint.pt`: `state_dict` de la mejor época;
- `history.csv`: pérdidas de datos, bio y total por época (#181);
- `violations.csv`: violaciones por época y subconjunto (#179), si se monitorearon;
- `metrics.csv`: métricas de D-03 del test del fold;
- `predictions.csv`: `(z_1, z_2, ln T)` de cada animal de test.

`load_compositional_run` valida que `run.json` tenga todos los campos de
`REQUIRED_RUN_FIELDS` y reconstruye el modelo (con `MODEL_OUTPUT_NAMES`, #222) y los escalados;
`predict_compositional` vuelve a predecir `(z_1, z_2, ln T)`. En el mismo dispositivo y con las
mismas versiones, la recarga reproduce `predictions.csv` dentro de `RELOAD_ATOL`.

El registro es local y en archivos: `docs/process/cost-policy.md` excluye el seguimiento de
experimentos alojado de pago. No guarda datos crudos ni rutas absolutas del equipo.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import torch
from torch import Tensor
from torch_geometric.data import HeteroData
from torch_geometric.loader import DataLoader

from nutrigraphdt.constraints.contracts import CONSTRAINTS_CONTRACT_VERSION
from nutrigraphdt.data.split import split_content_sha256
from nutrigraphdt.models.composition import COMPOSITIONAL_TARGET_VERSION, MODEL_OUTPUT_NAMES
from nutrigraphdt.models.gnn.base import GraphMetadata, SCFAGraphModel
from nutrigraphdt.models.gnn.batching import for_training
from nutrigraphdt.models.gnn.factory import GNNModelConfig, build_model, parse_model_config
from nutrigraphdt.models.metrics import EvaluationReport
from nutrigraphdt.models.training.config import TrainingConfig, parse_training_config
from nutrigraphdt.models.training.scaling import (
    FeatureScaler,
    TargetScaler,
    scalers_from_dict,
    scalers_to_dict,
)
from nutrigraphdt.models.training.taxon_identity import TaxonLineageEncoder
from nutrigraphdt.models.training.tracking import (
    CHECKPOINT_FILE,
    HISTORY_FILE,
    METRICS_FILE,
    PREDICTIONS_FILE,
    RUN_FILE,
    _cpu_state,
    _portable_path,
    _write_rows,
    environment_info,
    git_info,
    metadata_from_dict,
    metadata_to_dict,
)

if TYPE_CHECKING:
    from nutrigraphdt.models.training.compositional import CompositionalTargetTransform

COMPOSITIONAL_RUN_FORMAT_VERSION: Final[str] = "1.1.0"
VIOLATIONS_FILE: Final[str] = "violations.csv"
RELOAD_ATOL: Final[float] = 1e-5
"""Tolerancia absoluta de la recarga sobre `(z_1, z_2, ln T)`.

En el mismo dispositivo y con las mismas versiones de torch y torch-geometric, la recarga da
los mismos valores (`float32`). La tolerancia cubre el redondeo de `float32` entre plataformas
o núcleos distintos (CPU y GPU), no un cambio de modelo."""

REQUIRED_RUN_FIELDS: Final[tuple[str, ...]] = (
    "format_version",
    "run_id",
    "created_at",
    "variant",
    "edges_arm",
    "dataset_id",
    "seed",
    "fold",
    "train_seed",
    "plan",
    "cohort",
    "sample_ids",
    "training_config",
    "model_config",
    "target_names",
    "constraint_lambda",
    "constraint_terms",
    "monitored_constraints",
    "constraints_contract_version",
    "compositional_target_version",
    "metadata",
    "scaling",
    "best_epoch",
    "epochs_run",
    "stopped_early",
    "duration_seconds",
    "git",
    "environment",
    "reload_atol",
    "files",
)
"""Campos que `run.json` debe tener para que la corrida se pueda recargar y rastrear."""

PLAN_FIELDS: Final[tuple[str, ...]] = ("file", "sha256", "version", "k")
SAMPLE_SUBSETS: Final[tuple[str, ...]] = ("train", "inner_val", "test")


class IncompleteRunError(ValueError):
    """`run.json` no tiene los metadatos necesarios o su formato no es compatible."""


def plan_content_sha256(plan: Mapping[str, Any]) -> str:
    """SHA-256 canónico del plan de folds: el mismo JSON canónico que las particiones (#133)."""
    return split_content_sha256(plan)


@dataclass(frozen=True)
class CompositionalRunRecord:
    """Todo lo que se registra de un fold entrenado con el objetivo composicional.

    `model` debe tener los pesos de la mejor época. `history`, `violations` y `predictions` son
    filas planas (`CompositionalEpochRecord.to_dict()`, `ViolationLogRow.to_dict()` y las
    predicciones de `FoldEvaluation`). `plan` describe el plan de folds con `PLAN_FIELDS`;
    `sample_ids` da los animales de `train` (interno), `inner_val` y `test`.
    """

    model: SCFAGraphModel
    model_config: GNNModelConfig
    training_config: TrainingConfig
    feature_scaler: FeatureScaler
    target_scaler: TargetScaler
    variant: str
    edges_arm: str
    dataset_id: str
    seed: int
    fold: int
    plan: Mapping[str, Any]
    cohort: Mapping[str, Any]
    sample_ids: Mapping[str, Sequence[str]]
    monitored_constraints: Sequence[str]
    history: Sequence[Mapping[str, Any]]
    violations: Sequence[Mapping[str, Any]]
    metrics: EvaluationReport
    predictions: Sequence[Mapping[str, Any]]
    best_epoch: int
    stopped_early: bool
    duration_seconds: float
    source: Mapping[str, Any] = field(default_factory=dict)
    taxon_identity: Mapping[str, Any] | None = None
    """Vocabulario de linaje y configuración del fold (#266); `None` si no se usó."""


@dataclass(frozen=True)
class LoadedCompositionalRun:
    """Corrida recargada: modelo en modo `eval` con la mejor época y sus escalados."""

    run_dir: Path
    info: Mapping[str, Any]
    model: SCFAGraphModel
    model_config: GNNModelConfig
    training_config: TrainingConfig
    feature_scaler: FeatureScaler
    target_scaler: TargetScaler
    taxon_encoder: TaxonLineageEncoder | None = None

    @property
    def run_id(self) -> str:
        return str(self.info["run_id"])

    @property
    def transform(self) -> CompositionalTargetTransform:
        """Transformación del objetivo con el escalado guardado."""
        from nutrigraphdt.models.training.compositional import CompositionalTargetTransform

        return CompositionalTargetTransform(self.target_scaler)


def make_compositional_run_id(
    variant: str, edges_arm: str, seed: int, fold: int, now: datetime | None = None
) -> str:
    """`<AAAAMMDD-HHMMSS>_<variante>_<brazo>_s<semilla>_f<fold>`, con la hora en UTC."""
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    return f"{moment:%Y%m%d-%H%M%S}_{variant}_{edges_arm}_s{seed}_f{fold}"


def save_compositional_run(
    record: CompositionalRunRecord,
    runs_dir: str | Path,
    *,
    repo_root: str | Path | None = None,
    now: datetime | None = None,
) -> Path:
    """Escribe `runs_dir/<run_id>/` y devuelve su ruta.

    `repo_root` (por defecto, el directorio actual) sirve para leer el commit de Git y dejar
    relativa la ruta del plan.

    Raises:
        FileExistsError: si ya existe una corrida con el mismo `run_id`.
        IncompleteRunError: si el plan o los subconjuntos no traen sus campos.
    """
    missing_plan = [name for name in PLAN_FIELDS if name not in record.plan]
    missing_subsets = [name for name in SAMPLE_SUBSETS if name not in record.sample_ids]
    if missing_plan or missing_subsets:
        raise IncompleteRunError(
            f"Faltan campos del plan {missing_plan} o subconjuntos {missing_subsets}."
        )
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    run_id = make_compositional_run_id(
        record.variant, record.edges_arm, record.seed, record.fold, moment
    )
    run_dir = Path(runs_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    torch.save(_cpu_state(record.model), run_dir / CHECKPOINT_FILE)
    _write_rows(run_dir / HISTORY_FILE, record.history)
    if record.violations:
        _write_rows(run_dir / VIOLATIONS_FILE, record.violations)
    (run_dir / METRICS_FILE).write_text(record.metrics.to_csv(), encoding="utf-8", newline="")
    _write_rows(run_dir / PREDICTIONS_FILE, record.predictions)

    plan = dict(record.plan)
    plan_file = plan.get("file")
    if plan_file is not None:
        plan["file"] = _portable_path(Path(str(plan_file)), root)
    config = record.training_config
    info = {
        "format_version": COMPOSITIONAL_RUN_FORMAT_VERSION,
        "run_id": run_id,
        "created_at": moment.isoformat(timespec="seconds"),
        "variant": record.variant,
        "edges_arm": record.edges_arm,
        "dataset_id": record.dataset_id,
        "seed": record.seed,
        "fold": record.fold,
        "train_seed": config.seed,
        "plan": plan,
        "cohort": dict(record.cohort),
        "sample_ids": {name: sorted(record.sample_ids[name]) for name in SAMPLE_SUBSETS},
        "source": dict(record.source),
        "training_config": config.model_dump(mode="json"),
        "model_config": record.model_config.model_dump(mode="json"),
        "target_names": list(record.model.target_names),
        "constraint_lambda": config.constraint_lambda,
        "constraint_terms": list(config.constraint_terms),
        "monitored_constraints": list(record.monitored_constraints),
        "constraints_contract_version": CONSTRAINTS_CONTRACT_VERSION,
        "compositional_target_version": COMPOSITIONAL_TARGET_VERSION,
        "metadata": metadata_to_dict(record.model.metadata),
        "scaling": scalers_to_dict(record.feature_scaler, record.target_scaler),
        "taxon_identity": dict(record.taxon_identity) if record.taxon_identity else None,
        "best_epoch": record.best_epoch,
        "epochs_run": len(record.history),
        "stopped_early": record.stopped_early,
        "duration_seconds": record.duration_seconds,
        "git": git_info(root),
        "environment": environment_info(config.device),
        "reload_atol": RELOAD_ATOL,
        "files": {
            "checkpoint": CHECKPOINT_FILE,
            "history": HISTORY_FILE,
            "violations": VIOLATIONS_FILE if record.violations else None,
            "metrics": METRICS_FILE,
            "predictions": PREDICTIONS_FILE,
        },
    }
    (run_dir / RUN_FILE).write_text(
        json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return run_dir


def run_metadata_problems(info: Mapping[str, Any]) -> list[str]:
    """Problemas de `run.json`: campos que faltan, formato incompatible o salidas mal nombradas.

    Una lista vacía significa que la corrida se puede recargar y rastrear.
    """
    problems = [f"falta '{name}'" for name in REQUIRED_RUN_FIELDS if name not in info]
    version = str(info.get("format_version", ""))
    if "format_version" in info and (
        version.split(".")[0] != COMPOSITIONAL_RUN_FORMAT_VERSION.split(".")[0]
    ):
        problems.append(f"formato {version!r} no compatible con {COMPOSITIONAL_RUN_FORMAT_VERSION}")
    plan = info.get("plan")
    if isinstance(plan, Mapping):
        # `file` es nulo para un plan en memoria; su hash, versión y k siempre se registran.
        problems += [
            f"falta 'plan.{name}'"
            for name in PLAN_FIELDS
            if name not in plan or (name != "file" and plan[name] is None)
        ]
    elif "plan" in info:
        problems.append("'plan' debe ser un objeto")
    sample_ids = info.get("sample_ids")
    if isinstance(sample_ids, Mapping):
        problems += [f"falta 'sample_ids.{n}'" for n in SAMPLE_SUBSETS if n not in sample_ids]
    if "target_names" in info and list(info["target_names"]) != list(MODEL_OUTPUT_NAMES):
        problems.append(
            f"'target_names' es {info['target_names']!r}; se esperaba {list(MODEL_OUTPUT_NAMES)}"
        )
    return problems


def load_compositional_run(
    run_dir: str | Path, *, device: str | torch.device = "cpu"
) -> LoadedCompositionalRun:
    """Reconstruye el modelo de la mejor época y los escalados de una corrida, sin reentrenar.

    Raises:
        FileNotFoundError: si falta `run.json` o `checkpoint.pt`.
        IncompleteRunError: si `run.json` tiene problemas (`run_metadata_problems`).
    """
    directory = Path(run_dir)
    info = json.loads((directory / RUN_FILE).read_text(encoding="utf-8"))
    problems = run_metadata_problems(info)
    if problems:
        raise IncompleteRunError(f"{directory / RUN_FILE}: " + "; ".join(problems) + ".")
    source = str(directory / RUN_FILE)
    model_config = parse_model_config(info["model_config"], source=source)
    training_config = parse_training_config(info["training_config"], source=source)
    feature_scaler, target_scaler = scalers_from_dict(info["scaling"])
    identity = info.get("taxon_identity")
    taxon_encoder = TaxonLineageEncoder.from_dict(identity) if identity else None
    model = build_model(
        model_config, metadata_from_dict(info["metadata"]), target_names=MODEL_OUTPUT_NAMES
    )
    state = torch.load(directory / CHECKPOINT_FILE, map_location=device, weights_only=True)
    model.load_state_dict(state)
    model.to(device)
    model.eval()
    return LoadedCompositionalRun(
        run_dir=directory,
        info=info,
        model=model,
        model_config=model_config,
        training_config=training_config,
        feature_scaler=feature_scaler,
        target_scaler=target_scaler,
        taxon_encoder=taxon_encoder,
    )


def predict_compositional(
    loaded: LoadedCompositionalRun, graphs: Sequence[HeteroData], *, batch_size: int = 32
) -> tuple[list[str], Tensor]:
    """`sample_id` y `(z_1, z_2, ln T)` des-escalados de `graphs` con la corrida recargada.

    `graphs` deben tener las aristas inversas y los tipos alineados con los del entrenamiento;
    se codifican con el vocabulario de linaje de la corrida, si lo tiene, y se escalan con el
    `FeatureScaler` guardado.
    """
    prepared = loaded.taxon_encoder.transform(graphs) if loaded.taxon_encoder else list(graphs)
    loader = DataLoader(
        loaded.feature_scaler.transform([for_training(graph) for graph in prepared]),
        batch_size=batch_size,
    )
    device = next(loaded.model.parameters()).device
    outputs: list[Tensor] = []
    sample_ids: list[str] = []
    with torch.no_grad():
        for batch in loader:
            output = loaded.model(batch.to(device))
            outputs.append(loaded.transform.inverse_transform(output.cpu()))
            sample_ids.extend(str(s) for s in batch.sample_id)
    return sample_ids, torch.cat(outputs)


def graph_metadata_matches(loaded: LoadedCompositionalRun, metadata: GraphMetadata) -> bool:
    """`True` si los grafos nuevos tienen las mismas columnas y relaciones que el entrenamiento."""
    return metadata_to_dict(metadata) == dict(loaded.info["metadata"])


__all__ = [
    "COMPOSITIONAL_RUN_FORMAT_VERSION",
    "PLAN_FIELDS",
    "RELOAD_ATOL",
    "REQUIRED_RUN_FIELDS",
    "SAMPLE_SUBSETS",
    "VIOLATIONS_FILE",
    "CompositionalRunRecord",
    "IncompleteRunError",
    "LoadedCompositionalRun",
    "graph_metadata_matches",
    "load_compositional_run",
    "make_compositional_run_id",
    "plan_content_sha256",
    "predict_compositional",
    "run_metadata_problems",
    "save_compositional_run",
]
