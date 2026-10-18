"""Trazabilidad de corridas: registro, checkpoint y recarga (A44-5, #99).

Cada entrenamiento deja un directorio `runs/<run_id>/` (ignorado por Git) con lo necesario para
saber exactamente qué se entrenó y volver a predecir sin reentrenar:

- `run.json`: configuración efectiva de entrenamiento y modelo, semilla, commit de Git,
  versiones, partición (versión y SHA-256), conteos por subconjunto, escalado, mejor época y
  duración;
- `history.csv`: una fila por época, con la pérdida de `train` y las métricas de `val`;
- `metrics.csv`: `EvaluationReport.to_csv()`;
- `predictions.csv`: `sample_id`, subconjunto, valor medido y predicho por AGCC;
- `checkpoint.pt`: `state_dict` de la mejor época.

El registro es local y en archivos: `docs/process/cost-policy.md` excluye el seguimiento de
experimentos alojado de pago. No guarda datos crudos ni rutas absolutas del equipo.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import platform
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import torch
import torch_geometric
from torch import Tensor

from nutrigraphdt.data.split import DatasetSplit
from nutrigraphdt.models.gnn.base import GraphMetadata, SCFAGraphModel
from nutrigraphdt.models.gnn.factory import GNNModelConfig, build_model, parse_model_config
from nutrigraphdt.models.metrics import EvaluationReport
from nutrigraphdt.models.training.config import TrainingConfig, parse_training_config
from nutrigraphdt.models.training.dataloaders import SubsetSummary
from nutrigraphdt.models.training.scaling import (
    FeatureScaler,
    TargetScaler,
    scalers_from_dict,
    scalers_to_dict,
)

RUN_FORMAT_VERSION: Final[str] = "1.0.0"
RUN_FILE: Final[str] = "run.json"
HISTORY_FILE: Final[str] = "history.csv"
METRICS_FILE: Final[str] = "metrics.csv"
PREDICTIONS_FILE: Final[str] = "predictions.csv"
CHECKPOINT_FILE: Final[str] = "checkpoint.pt"
DEFAULT_RUNS_DIR: Final[Path] = Path("runs")


@dataclass(frozen=True)
class RunRecord:
    """Todo lo que se registra de una corrida.

    `history` y `predictions` son filas planas: `EpochRecord.to_dict()` y
    `Predictions.to_records(subset)` del bucle de A44-3 (#97). `split_file` es el archivo de la
    partición, o `None` si se creó en memoria (cohorte sintética). `model` debe tener los pesos
    que se quieren guardar (los de la mejor época). `source` describe de dónde salieron los
    grafos (por ejemplo, los parámetros de la cohorte sintética) y se guarda tal cual.
    """

    model: SCFAGraphModel
    model_config: GNNModelConfig
    training_config: TrainingConfig
    feature_scaler: FeatureScaler
    target_scaler: TargetScaler
    split: DatasetSplit
    split_file: str | Path | None
    summary: Mapping[str, SubsetSummary]
    history: Sequence[Mapping[str, Any]]
    metrics: EvaluationReport
    predictions: Sequence[Mapping[str, Any]]
    best_epoch: int
    stopped_early: bool
    duration_seconds: float
    source: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LoadedRun:
    """Corrida recargada con `load_run`: modelo en modo `eval` con los pesos guardados."""

    run_dir: Path
    info: Mapping[str, Any]
    model: SCFAGraphModel
    model_config: GNNModelConfig
    training_config: TrainingConfig
    feature_scaler: FeatureScaler
    target_scaler: TargetScaler

    @property
    def run_id(self) -> str:
        return str(self.info["run_id"])


def make_run_id(variant: str, seed: int, now: datetime | None = None) -> str:
    """`<AAAAMMDD-HHMMSS>_<variante>_s<semilla>`, con la hora en UTC."""
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    return f"{moment:%Y%m%d-%H%M%S}_{variant}_s{seed}"


def save_run(
    record: RunRecord,
    runs_dir: str | Path = DEFAULT_RUNS_DIR,
    *,
    repo_root: str | Path | None = None,
    now: datetime | None = None,
) -> Path:
    """Escribe `runs_dir/<run_id>/` con los cinco archivos y devuelve su ruta.

    `repo_root` (por defecto, el directorio actual) sirve para leer el commit de Git y para
    registrar `split_file` como ruta relativa. Un archivo de partición fuera del repositorio se
    registra solo por su nombre.

    Raises:
        FileExistsError: si ya existe una corrida con el mismo `run_id`.
    """
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    variant = record.model_config.variant
    run_id = make_run_id(variant, record.training_config.seed, moment)
    run_dir = Path(runs_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    torch.save(_cpu_state(record.model), run_dir / CHECKPOINT_FILE)
    _write_rows(run_dir / HISTORY_FILE, record.history)
    (run_dir / METRICS_FILE).write_text(record.metrics.to_csv(), encoding="utf-8", newline="")
    _write_rows(run_dir / PREDICTIONS_FILE, record.predictions)

    info = {
        "format_version": RUN_FORMAT_VERSION,
        "run_id": run_id,
        "created_at": moment.isoformat(timespec="seconds"),
        "variant": variant,
        "seed": record.training_config.seed,
        "dataset_id": record.training_config.dataset_id,
        "source": dict(record.source),
        "training_config": record.training_config.model_dump(mode="json"),
        "model_config": record.model_config.model_dump(mode="json"),
        "metadata": metadata_to_dict(record.model.metadata),
        "split": split_info(record.split, record.split_file, root),
        "subsets": {name: _summary_to_dict(item) for name, item in record.summary.items()},
        "scaling": scalers_to_dict(record.feature_scaler, record.target_scaler),
        "best_epoch": record.best_epoch,
        "epochs_run": len(record.history),
        "stopped_early": record.stopped_early,
        "duration_seconds": record.duration_seconds,
        "git": git_info(root),
        "environment": environment_info(record.training_config.device),
        "files": {
            "history": HISTORY_FILE,
            "metrics": METRICS_FILE,
            "predictions": PREDICTIONS_FILE,
            "checkpoint": CHECKPOINT_FILE,
        },
    }
    (run_dir / RUN_FILE).write_text(
        json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return run_dir


def load_run(run_dir: str | Path, *, device: str | torch.device = "cpu") -> LoadedRun:
    """Reconstruye modelo y escalado de una corrida guardada, sin reentrenar.

    Construye el modelo con `build_model` desde la configuración y los metadatos de `run.json`
    y carga `checkpoint.pt` con `weights_only=True`. El modelo queda en modo `eval`.

    Raises:
        FileNotFoundError: si falta `run.json` o `checkpoint.pt`.
        ValueError: si el formato de la corrida no es compatible.
    """
    directory = Path(run_dir)
    info = json.loads((directory / RUN_FILE).read_text(encoding="utf-8"))
    version = str(info.get("format_version", ""))
    if version.split(".")[0] != RUN_FORMAT_VERSION.split(".")[0]:
        raise ValueError(
            f"{directory / RUN_FILE}: formato {version!r} no compatible con {RUN_FORMAT_VERSION}."
        )
    model_config = parse_model_config(info["model_config"], source=str(directory / RUN_FILE))
    training_config = parse_training_config(
        info["training_config"], source=str(directory / RUN_FILE)
    )
    feature_scaler, target_scaler = scalers_from_dict(info["scaling"])
    model = build_model(model_config, metadata_from_dict(info["metadata"]))
    state = torch.load(directory / CHECKPOINT_FILE, map_location=device, weights_only=True)
    model.load_state_dict(state)
    model.to(device)
    model.eval()
    return LoadedRun(
        run_dir=directory,
        info=info,
        model=model,
        model_config=model_config,
        training_config=training_config,
        feature_scaler=feature_scaler,
        target_scaler=target_scaler,
    )


def read_rows(path: str | Path) -> list[dict[str, str]]:
    """Filas de un CSV de la corrida (`history.csv`, `predictions.csv`) como texto."""
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def metadata_to_dict(metadata: GraphMetadata) -> dict[str, Any]:
    """`GraphMetadata` serializable: columnas por tipo de nodo y tripletas de arista."""
    return {
        "node_channels": dict(metadata.node_channels),
        "edge_types": [list(edge_type) for edge_type in metadata.edge_types],
    }


def metadata_from_dict(data: Mapping[str, Any]) -> GraphMetadata:
    """Inversa de `metadata_to_dict`."""
    edge_types = tuple((str(s), str(r), str(t)) for s, r, t in data["edge_types"])
    return GraphMetadata(
        {str(t): int(c) for t, c in data["node_channels"].items()},
        edge_types,
    )


def split_info(
    split: DatasetSplit, split_file: str | Path | None, repo_root: str | Path
) -> dict[str, Any]:
    """Versión, conteos y SHA-256 de la partición.

    Con archivo, el hash es el de sus bytes y la ruta queda relativa a `repo_root` (o solo el
    nombre si está fuera). Sin archivo, el hash es el del JSON canónico de `split.to_dict()`.
    """
    file: str | None = None
    if split_file is None:
        canonical = json.dumps(split.to_dict(), sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    else:
        path = Path(split_file)
        if not path.is_absolute():
            path = Path(repo_root) / path
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        file = _portable_path(path, Path(repo_root))
    return {
        "file": file,
        "dataset_id": split.dataset_id,
        "version": split.version,
        "seed": split.seed,
        "counts": {name: len(split[name]) for name in ("train", "val", "test")},
        "sha256": digest,
    }


def git_info(repo_root: str | Path) -> dict[str, Any]:
    """Commit de `HEAD` y si había cambios sin confirmar en archivos versionados.

    Devuelve `None` en ambos campos si Git no está disponible o `repo_root` no es un repositorio.
    """
    commit = _git(repo_root, "rev-parse", "HEAD")
    if commit is None:
        return {"commit": None, "dirty": None}
    status = _git(repo_root, "status", "--porcelain", "--untracked-files=no")
    return {"commit": commit, "dirty": None if status is None else bool(status)}


def environment_info(device: str = "cpu") -> dict[str, str]:
    """Versiones de Python, torch y torch-geometric, sistema operativo y dispositivo.

    Con `device` en GPU (`cuda` o `cuda:N`, también para ROCm) agrega el nombre de la tarjeta y
    la versión de CUDA o de ROCm con que se compiló torch.
    """
    info = {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "torch_geometric": torch_geometric.__version__,
        "platform": platform.system(),
        "device": device,
    }
    if device.startswith("cuda") and torch.cuda.is_available():
        info["device_name"] = torch.cuda.get_device_name(torch.device(device))
        backend = getattr(torch.version, "hip", None) or torch.version.cuda
        info["gpu_backend"] = f"{'rocm' if torch.version.hip else 'cuda'} {backend}"
    return info


def _git(repo_root: str | Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _portable_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.name


def _summary_to_dict(summary: SubsetSummary) -> dict[str, int]:
    return {
        "received": summary.received,
        "deliverable": summary.deliverable,
        "with_any_scfa": summary.with_any_scfa,
        "with_all_scfa": summary.with_all_scfa,
        "outside_cohort": summary.outside_cohort,
    }


def _cpu_state(model: SCFAGraphModel) -> dict[str, Tensor]:
    return {name: value.detach().cpu() for name, value in model.state_dict().items()}


def _write_rows(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        fieldnames.extend(name for name in row if name not in fieldnames)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows({name: _cell(value) for name, value in row.items()} for row in rows)
    path.write_text(buffer.getvalue(), encoding="utf-8")


def _cell(value: Any) -> Any:
    # `repr` de un float es la representación más corta que vuelve exactamente al mismo valor.
    if isinstance(value, float):
        return repr(value)
    return "" if value is None else value


__all__ = [
    "CHECKPOINT_FILE",
    "DEFAULT_RUNS_DIR",
    "HISTORY_FILE",
    "METRICS_FILE",
    "PREDICTIONS_FILE",
    "RUN_FILE",
    "RUN_FORMAT_VERSION",
    "LoadedRun",
    "RunRecord",
    "environment_info",
    "git_info",
    "load_run",
    "make_run_id",
    "metadata_from_dict",
    "metadata_to_dict",
    "read_rows",
    "save_run",
    "split_info",
]
