"""Diagnóstico de corridas GNN ya registradas (A45-7, #107).

Lee los archivos que deja `run_training` en cada corrida (A44-5): `run.json`, `history.csv`,
`metrics.csv` y `predictions.csv`. No entrena ni recarga el checkpoint, y no requiere PyTorch ni
matplotlib: las figuras se dibujan en `scripts/plot_gnn_runs.py` a partir de estos datos.

Además de cargar las corridas, este módulo:

- verifica que las métricas de cada corrida coincidan con el reporte consolidado del dataset
  (`reports/gnn/<dataset>/report.csv`, A45-3 y A45-4), para que las figuras correspondan a las
  corridas reportadas;
- resume cada corrida con cifras para detectar sobreajuste o un modelo que no aprende (ver
  `RunDiagnosis`). Las cifras se informan sin umbrales: la interpretación queda en
  `docs/models/gnn-evaluation.md`.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from nutrigraphdt.models.metrics import DEFAULT_SCFA_TARGETS

RUN_FILE: Final[str] = "run.json"
HISTORY_FILE: Final[str] = "history.csv"
METRICS_FILE: Final[str] = "metrics.csv"
PREDICTIONS_FILE: Final[str] = "predictions.csv"
VARIANT_ORDER: Final[tuple[str, ...]] = ("homo_sage", "hetero_sage", "hetero_gat")
DIAGNOSIS_SPLIT: Final[str] = "test"
REPORT_TOLERANCE: Final[float] = 1e-5

# Unidades de los AGCC en el target del grafo. El loader lleva µmol/g de digesta fresca (base
# húmeda, V-06 de la respuesta de Investigación) de D1 a mmol/kg
# con factor 1 (docs/data-sources/holofood-source.md); el generador sintético usa mmol/kg.
TARGET_UNITS: Final[Mapping[str, str]] = {"synthetic": "mmol/kg", "d1": "mmol/kg"}
UNIT_NOTES: Final[Mapping[str, str]] = {"d1": "1 mmol/kg = 1 µmol/g de digesta fresca, base húmeda"}
DATASET_LABELS: Final[Mapping[str, str]] = {
    "synthetic": "Cohorte sintética",
    "d1": "D1 HoloFood",
}
TARGET_LABELS: Final[Mapping[str, str]] = {
    "acetate": "Acetato",
    "propionate": "Propionato",
    "butyrate": "Butirato",
}


class RunDataError(ValueError):
    """Una corrida no se puede leer o no coincide con el reporte de su dataset."""


@dataclass(frozen=True)
class EpochRow:
    """Una fila de `history.csv`. Las pérdidas están en la escala estandarizada del target."""

    epoch: int
    train_loss: float
    val_loss: float
    val_rmse: Mapping[str, float]
    improved: bool


@dataclass(frozen=True)
class Prediction:
    sample_id: str
    subset: str
    measured: Mapping[str, float]
    predicted: Mapping[str, float]


@dataclass(frozen=True)
class RunData:
    """Lo necesario de una corrida para graficarla y diagnosticarla."""

    run_dir: Path
    info: Mapping[str, Any]
    history: tuple[EpochRow, ...]
    predictions: tuple[Prediction, ...]
    metrics: Mapping[tuple[str, str], Mapping[str, float]]

    @property
    def variant(self) -> str:
        return str(self.info["variant"])

    @property
    def dataset(self) -> str:
        return str(self.info["source"]["dataset"])

    @property
    def run_id(self) -> str:
        return str(self.info["run_id"])

    @property
    def best_epoch(self) -> int:
        return int(self.info["best_epoch"])

    def metric(self, split: str, metric: str, target: str = "average") -> float:
        return self.metrics[(split, metric)][target]

    def subset(self, name: str) -> tuple[Prediction, ...]:
        return tuple(p for p in self.predictions if p.subset == name)


@dataclass(frozen=True)
class RunDiagnosis:
    """Cifras para leer las curvas de una corrida.

    - `train_loss_*` y `val_loss_*`: pérdida (MSE estandarizada) en la mejor época y en la
      última. Si después de la mejor época `train` baja y `val` sube, hay sobreajuste.
    - `val_rmse_first`, `val_rmse_best`: RMSE promedio de `val` (unidades de la fuente) en la
      época 1 y en la mejor. Si casi no baja, el modelo no aprende más allá del inicio.
    - `spread_ratio`: desviación estándar de lo predicho dividida por la de lo medido, por AGCC,
      en `test`. Cerca de 0 significa que el modelo predice casi una constante.
    - `correlation`: correlación de Pearson entre medido y predicho, por AGCC, en `test`.
    """

    dataset: str
    variant: str
    run_id: str
    best_epoch: int
    epochs_run: int
    stopped_early: bool
    train_loss_best: float
    train_loss_last: float
    val_loss_best: float
    val_loss_last: float
    val_rmse_first: float
    val_rmse_best: float
    val_rmse_last: float
    test_rmse: float
    test_r2: float
    spread_ratio: Mapping[str, float]
    correlation: Mapping[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "variant": self.variant,
            "run_id": self.run_id,
            "best_epoch": self.best_epoch,
            "epochs_run": self.epochs_run,
            "stopped_early": self.stopped_early,
            "train_loss": {"best_epoch": self.train_loss_best, "last_epoch": self.train_loss_last},
            "val_loss": {"best_epoch": self.val_loss_best, "last_epoch": self.val_loss_last},
            "val_rmse_average": {
                "first_epoch": self.val_rmse_first,
                "best_epoch": self.val_rmse_best,
                "last_epoch": self.val_rmse_last,
            },
            "test": {
                "rmse_average": self.test_rmse,
                "r2_average": self.test_r2,
                "spread_ratio": dict(self.spread_ratio),
                "correlation": dict(self.correlation),
            },
        }


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------


def load_run(run_dir: Path, targets: Sequence[str] = DEFAULT_SCFA_TARGETS) -> RunData:
    """Lee una corrida registrada por `run_training`.

    Raises:
        RunDataError: si falta un archivo, una columna o un valor no es numérico.
    """
    run_dir = Path(run_dir)
    info = _read_json(run_dir / RUN_FILE)
    for key in ("variant", "run_id", "best_epoch"):
        if key not in info:
            raise RunDataError(f"{run_dir / RUN_FILE}: falta `{key}`.")
    source = info.get("source")
    if not isinstance(source, Mapping) or "dataset" not in source:
        raise RunDataError(f"{run_dir / RUN_FILE}: falta `source.dataset`.")
    history = _read_history(run_dir / HISTORY_FILE, targets)
    best = int(info["best_epoch"])
    if not any(row.epoch == best for row in history):
        raise RunDataError(f"{run_dir / HISTORY_FILE}: no tiene la mejor época ({best}).")
    return RunData(
        run_dir=run_dir,
        info=info,
        history=history,
        predictions=_read_predictions(run_dir / PREDICTIONS_FILE, targets),
        metrics=_read_metrics(run_dir / METRICS_FILE, targets),
    )


def order_runs(runs: Sequence[RunData]) -> tuple[RunData, ...]:
    """Ordena por variante (homo_sage, hetero_sage, hetero_gat; otras al final, por nombre).

    Raises:
        RunDataError: si las corridas son de datasets distintos o repiten variante.
    """
    if not runs:
        raise RunDataError("No se indicaron corridas.")
    datasets = {run.dataset for run in runs}
    if len(datasets) != 1:
        raise RunDataError(f"Las corridas son de datasets distintos: {sorted(datasets)}.")
    variants = [run.variant for run in runs]
    repeated = sorted({v for v in variants if variants.count(v) > 1})
    if repeated:
        raise RunDataError(f"Variantes repetidas: {repeated}; indique una corrida por variante.")

    def key(run: RunData) -> tuple[int, str]:
        index = VARIANT_ORDER.index(run.variant) if run.variant in VARIANT_ORDER else 99
        return index, run.variant

    return tuple(sorted(runs, key=key))


def report_mismatches(
    run: RunData, report_csv: Path, tolerance: float = REPORT_TOLERANCE
) -> list[str]:
    """Diferencias entre `metrics.csv` de la corrida y las filas de su variante en el reporte.

    Compara todas las métricas por AGCC y promedio de `val` y `test`. Una variante ausente del
    reporte también es una diferencia.
    """
    if not report_csv.is_file():
        return [f"falta {report_csv}"]
    with report_csv.open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row.get("model") == run.variant]
    if not rows:
        return [f"{run.variant} no está en {report_csv}"]
    problems: list[str] = []
    for row in rows:
        key = (row["split"], row["metric"])
        if key not in run.metrics:
            problems.append(f"{run.variant}: falta {key[0]}/{key[1]} en {METRICS_FILE}")
            continue
        for column, observed in run.metrics[key].items():
            expected = _to_float(row.get(column), report_csv)
            if abs(observed - expected) > tolerance:
                problems.append(
                    f"{run.variant} {key[0]}/{key[1]}/{column}: {observed:.6f} ≠ {expected:.6f}"
                )
    return problems


# ---------------------------------------------------------------------------
# Diagnóstico
# ---------------------------------------------------------------------------


def diagnose(
    run: RunData,
    split: str = DIAGNOSIS_SPLIT,
    targets: Sequence[str] = DEFAULT_SCFA_TARGETS,
) -> RunDiagnosis:
    best = next(row for row in run.history if row.epoch == run.best_epoch)
    first, last = run.history[0], run.history[-1]
    points = run.subset(split)
    if len(points) < 2:
        raise RunDataError(f"{run.run_dir}: {split} tiene menos de 2 predicciones.")
    spread: dict[str, float] = {}
    correlation: dict[str, float] = {}
    for target in targets:
        measured = [p.measured[target] for p in points]
        predicted = [p.predicted[target] for p in points]
        measured_sd = statistics.stdev(measured)
        spread[target] = statistics.stdev(predicted) / measured_sd if measured_sd else math.nan
        correlation[target] = _pearson(measured, predicted)
    return RunDiagnosis(
        dataset=run.dataset,
        variant=run.variant,
        run_id=run.run_id,
        best_epoch=run.best_epoch,
        epochs_run=len(run.history),
        stopped_early=bool(run.info.get("stopped_early", False)),
        train_loss_best=best.train_loss,
        train_loss_last=last.train_loss,
        val_loss_best=best.val_loss,
        val_loss_last=last.val_loss,
        val_rmse_first=first.val_rmse["average"],
        val_rmse_best=best.val_rmse["average"],
        val_rmse_last=last.val_rmse["average"],
        test_rmse=run.metric(split, "rmse"),
        test_r2=run.metric(split, "r2"),
        spread_ratio=spread,
        correlation=correlation,
    )


def diagnoses_to_markdown(
    diagnoses: Sequence[RunDiagnosis],
    runs: Sequence[RunData],
    figures: Sequence[str],
    command: str,
) -> str:
    """Página con las figuras, la procedencia de cada corrida y las cifras de diagnóstico."""
    dataset = diagnoses[0].dataset
    label = DATASET_LABELS.get(dataset, dataset)
    unit = TARGET_UNITS.get(dataset, "unidades de la fuente")
    lines = [
        f"# Curvas de aprendizaje y predicciones — {label} (A45-7)",
        "",
        f"Generado con `{command}` a partir de corridas registradas, sin reentrenar. "
        f"AGCC en {unit}{_note(dataset)}. La interpretación está en "
        "`docs/models/gnn-evaluation.md`.",
        "",
    ]
    lines += [f"![{Path(name).stem}]({name})" for name in figures]
    lines += [
        "",
        "## Corridas",
        "",
        "| Variante | `run_id` | Semilla | Commit | Dirty | Partición (SHA-256) |",
        "| :--- | :--- | ---: | :--- | :--- | :--- |",
    ]
    for run in runs:
        git = run.info.get("git") or {}
        split = run.info.get("split") or {}
        sha = split.get("sha256")
        lines.append(
            f"| `{run.variant}` | `{run.run_id}` | {run.info.get('seed', '—')} | "
            f"`{str(git.get('commit', '—'))[:7]}` | {'sí' if git.get('dirty') else 'no'} | "
            f"`{str(sha)[:12]}…` |"
        )
    lines += [
        "",
        "## Diagnóstico",
        "",
        "Pérdidas en la escala estandarizada del target; RMSE en "
        f"{unit}. `test`: dispersión = desviación estándar predicha / medida.",
        "",
        "| Variante | Mejor época / corridas | Pérdida train (mejor → última) | "
        "Pérdida val (mejor → última) | RMSE val (época 1 → mejor) | RMSE test | R² test |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for d in diagnoses:
        lines.append(
            f"| `{d.variant}` | {d.best_epoch} / {d.epochs_run} | "
            f"{d.train_loss_best:.3f} → {d.train_loss_last:.3f} | "
            f"{d.val_loss_best:.3f} → {d.val_loss_last:.3f} | "
            f"{d.val_rmse_first:.2f} → {d.val_rmse_best:.2f} | {d.test_rmse:.2f} | "
            f"{d.test_r2:.2f} |"
        )
    targets = list(diagnoses[0].spread_ratio)
    lines += [
        "",
        "| Variante | "
        + " | ".join(f"Dispersión {TARGET_LABELS.get(t, t).lower()}" for t in targets)
        + " | "
        + " | ".join(f"r {TARGET_LABELS.get(t, t).lower()}" for t in targets)
        + " |",
        "| :--- | " + " | ".join(["---:"] * (2 * len(targets))) + " |",
    ]
    for d in diagnoses:
        lines.append(
            f"| `{d.variant}` | "
            + " | ".join(_fmt(d.spread_ratio[t]) for t in targets)
            + " | "
            + " | ".join(_fmt(d.correlation[t]) for t in targets)
            + " |"
        )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RunDataError(f"Falta {path}.")
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RunDataError(f"{path}: JSON inválido ({error.msg}).") from error
    if not isinstance(content, dict):
        raise RunDataError(f"{path}: se esperaba un objeto JSON.")
    return content


def _rows(path: Path, required: set[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise RunDataError(f"Falta {path}.")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required.difference(reader.fieldnames or ())
        if missing:
            raise RunDataError(f"{path}: faltan columnas {sorted(missing)}.")
        rows = list(reader)
    if not rows:
        raise RunDataError(f"{path}: no tiene filas.")
    return rows


def _to_float(value: str | None, path: Path) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise RunDataError(f"{path}: valor no numérico {value!r}.") from error
    if not math.isfinite(number):
        raise RunDataError(f"{path}: valor no finito {value!r}.")
    return number


def _read_history(path: Path, targets: Sequence[str]) -> tuple[EpochRow, ...]:
    columns = {f"val_rmse_{t}" for t in (*targets, "average")}
    rows = _rows(path, {"epoch", "train_loss", "val_loss", "improved", *columns})
    history = tuple(
        EpochRow(
            epoch=int(_to_float(row["epoch"], path)),
            train_loss=_to_float(row["train_loss"], path),
            val_loss=_to_float(row["val_loss"], path),
            val_rmse={t: _to_float(row[f"val_rmse_{t}"], path) for t in (*targets, "average")},
            improved=row["improved"].strip().lower() == "true",
        )
        for row in rows
    )
    epochs = [row.epoch for row in history]
    if epochs != list(range(1, len(epochs) + 1)):
        raise RunDataError(f"{path}: las épocas no son 1, 2, …, n.")
    return history


def _read_predictions(path: Path, targets: Sequence[str]) -> tuple[Prediction, ...]:
    required = {"sample_id", "subset"}
    required |= {f"measured_{t}" for t in targets} | {f"predicted_{t}" for t in targets}
    return tuple(
        Prediction(
            sample_id=row["sample_id"],
            subset=row["subset"],
            measured={t: _to_float(row[f"measured_{t}"], path) for t in targets},
            predicted={t: _to_float(row[f"predicted_{t}"], path) for t in targets},
        )
        for row in _rows(path, required)
    )


def _read_metrics(path: Path, targets: Sequence[str]) -> dict[tuple[str, str], dict[str, float]]:
    columns = (*targets, "average")
    rows = _rows(path, {"split", "metric", *columns})
    return {
        (row["split"], row["metric"]): {c: _to_float(row[c], path) for c in columns} for row in rows
    }


def _pearson(x: Sequence[float], y: Sequence[float]) -> float:
    if statistics.stdev(x) == 0 or statistics.stdev(y) == 0:
        return math.nan
    return statistics.correlation(x, y)


def _note(dataset: str) -> str:
    note = UNIT_NOTES.get(dataset)
    return f" ({note})" if note else ""


def unit_label(dataset: str) -> str:
    """Unidad del target con su equivalencia, si la hay: `mmol/kg (1 mmol/kg = …)`."""
    return TARGET_UNITS.get(dataset, "unidades de la fuente") + _note(dataset)


def _fmt(value: float) -> str:
    return "—" if math.isnan(value) else f"{value:.2f}"


__all__ = [
    "DATASET_LABELS",
    "DIAGNOSIS_SPLIT",
    "HISTORY_FILE",
    "METRICS_FILE",
    "PREDICTIONS_FILE",
    "REPORT_TOLERANCE",
    "RUN_FILE",
    "TARGET_LABELS",
    "TARGET_UNITS",
    "UNIT_NOTES",
    "VARIANT_ORDER",
    "EpochRow",
    "Prediction",
    "RunData",
    "RunDataError",
    "RunDiagnosis",
    "diagnose",
    "diagnoses_to_markdown",
    "load_run",
    "order_runs",
    "report_mismatches",
    "unit_label",
]
