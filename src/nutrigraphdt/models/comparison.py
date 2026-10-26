"""Comparación GNN frente a baselines por dataset (A45-6, #106).

Lee los reportes ya generados, sin entrenar:

- baselines: `reports/baselines/` (cohorte sintética) y `reports/baselines/d1/` (D1), con su
  `report.csv` y `run.json`;
- GNN: `reports/gnn/synthetic/` y `reports/gnn/d1/`, con su `report.csv` y un
  `run_<variante>.json` por variante (A45-3, A45-4).

Antes de comparar verifica, con los `run.json`, que cada variante GNN use las mismas muestras y la
misma partición que los baselines del dataset. Una variante sin reporte queda marcada como
`pendiente` en lugar de omitirse. Las filas se unen con `combine_reports` (A40-2), así que el
formato es el de `EvaluationReport`. No requiere PyTorch ni scikit-learn.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from nutrigraphdt.models.metrics import (
    DEFAULT_SCFA_TARGETS,
    METRIC_NAMES,
    EvaluationReport,
    MetricRow,
    combine_reports,
)

GNN_VARIANTS: Final[tuple[str, ...]] = ("homo_sage", "hetero_sage", "hetero_gat")
SPLITS: Final[tuple[str, ...]] = ("val", "test")
BASELINE: Final[str] = "baseline"
GNN: Final[str] = "gnn"
OK: Final[str] = "ok"
PENDING: Final[str] = "pendiente"
CRITERION_SPLIT: Final[str] = "test"
CRITERION_METRIC: Final[str] = "rmse"
# El criterio se califica como provisional (revisión de #131 y respuesta de Investigación del
# 16-10-2026): ver la sección "Criterio de salida de F4" de docs/models/gnn-evaluation.md.
PROVISIONAL_NOTE: Final[tuple[str, ...]] = (
    "**Provisional.** Se evalúa sobre la partición 2.0.0 de D1, con un único `test` fijo de 21 "
    "animales y el objetivo en concentración. Las diferencias entre GNN y baselines no son "
    "concluyentes: no se midió la incertidumbre de muestreo de `test`. La respuesta de "
    "Investigación a la solicitud de revisión v1.1 (16-10-2026) cambia la evaluación de D1 a "
    "validación cruzada por corral sobre la cohorte oficial, con objetivo composicional.",
)
CSV_COLUMNS: Final[tuple[str, ...]] = (
    "dataset",
    "family",
    "model",
    "split",
    "metric",
    *DEFAULT_SCFA_TARGETS,
    "average",
    "status",
)


class ComparisonError(ValueError):
    """Los reportes no se pueden comparar (faltan, son inválidos o no están alineados)."""


@dataclass(frozen=True)
class DatasetSources:
    """Dónde están los reportes de un dataset.

    `split_file` es la partición versionada (D1) o `None` si la partición se creó en memoria a
    partir de la cohorte (sintético).
    """

    name: str
    label: str
    baseline_dir: Path
    gnn_dir: Path
    split_file: Path | None = None
    note: str | None = None


def default_sources(repo_root: Path) -> tuple[DatasetSources, ...]:
    """Las rutas por defecto del repositorio."""
    reports = repo_root / "reports"
    return (
        DatasetSources(
            name="synthetic",
            label="Cohorte sintética",
            baseline_dir=reports / "baselines",
            gnn_dir=reports / "gnn" / "synthetic",
            note=(
                "los AGCC no dependen de las entradas, así que el criterio solo verifica el "
                "procedimiento, no capacidad predictiva."
            ),
        ),
        DatasetSources(
            name="d1",
            label="D1 HoloFood",
            baseline_dir=reports / "baselines" / "d1",
            gnn_dir=reports / "gnn" / "d1",
            split_file=repo_root / "configs" / "splits" / "d1_holofood.json",
        ),
    )


@dataclass(frozen=True)
class DatasetComparison:
    """Filas de baselines y GNN de un dataset, ya verificadas."""

    sources: DatasetSources
    report: EvaluationReport
    families: Mapping[str, str]
    pending: tuple[str, ...]
    alignment: Mapping[str, Any] = field(default_factory=dict)

    @property
    def baselines(self) -> tuple[str, ...]:
        return tuple(m for m, f in self.families.items() if f == BASELINE)

    @property
    def gnns(self) -> tuple[str, ...]:
        return tuple(m for m, f in self.families.items() if f == GNN)

    def value(self, model: str, split: str, metric: str) -> float | None:
        row = self.report.get_row(metric, model=model, split=split)
        return None if row is None else row.average


@dataclass(frozen=True)
class CriterionResult:
    """Criterio de salida de F4 en un dataset: una GNN iguala o supera un baseline.

    Se compara el RMSE promedio de los tres AGCC en `test` (menor es mejor). `pairs` lista cada
    (GNN, baseline) en que la GNN tiene un RMSE menor o igual.
    """

    dataset: str
    pairs: tuple[tuple[str, str], ...]
    best_gnn: str | None
    best_baseline: str | None

    @property
    def met(self) -> bool:
        return bool(self.pairs)


# ---------------------------------------------------------------------------
# Lectura y verificación
# ---------------------------------------------------------------------------


def read_evaluation_csv(path: Path) -> EvaluationReport:
    """Lee un `report.csv` con el formato de `EvaluationReport.to_csv()`.

    Raises:
        ComparisonError: si falta el archivo, faltan columnas o hay valores no numéricos.
    """
    if not path.is_file():
        raise ComparisonError(f"Falta {path}.")
    required = {"model", "split", "metric", "average", *DEFAULT_SCFA_TARGETS}
    rows: list[MetricRow] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required.difference(reader.fieldnames or ())
        if missing:
            raise ComparisonError(f"{path}: faltan columnas {sorted(missing)}.")
        for line, record in enumerate(reader, start=2):
            try:
                targets = {name: float(record[name]) for name in DEFAULT_SCFA_TARGETS}
                average = float(record["average"])
            except (TypeError, ValueError) as error:
                raise ComparisonError(f"{path}: valor no numérico en la línea {line}.") from error
            if not all(math.isfinite(v) for v in (*targets.values(), average)):
                raise ComparisonError(f"{path}: valor no finito en la línea {line}.")
            rows.append(
                MetricRow(
                    model=record["model"],
                    metric=record["metric"],
                    targets=targets,
                    average=average,
                    split=record["split"] or None,
                )
            )
    return EvaluationReport(rows=tuple(rows))


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ComparisonError(f"Falta {path}.")
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ComparisonError(f"{path}: JSON inválido ({error.msg}).") from error
    if not isinstance(content, dict):
        raise ComparisonError(f"{path}: se esperaba un objeto JSON.")
    return content


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_file_digests(path: Path) -> frozenset[str]:
    """SHA-256 aceptados para el archivo de partición: sus bytes, con fines de línea LF y CRLF.

    `run.json` registra el hash de los bytes del archivo (A44-5). Con `core.autocrlf` de Git en
    Windows, el mismo archivo versionado queda con CRLF y su hash cambia; el contenido es el mismo.
    """
    raw = path.read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    return frozenset(hashlib.sha256(v).hexdigest() for v in (raw, lf, lf.replace(b"\n", b"\r\n")))


def alignment_problems(
    sources: DatasetSources,
    baseline_run: Mapping[str, Any],
    gnn_run: Mapping[str, Any],
    *,
    split_sha256: str | frozenset[str] | None = None,
) -> list[str]:
    """Diferencias entre el `run.json` de una GNN y el de los baselines del dataset.

    Comprueba que usen el mismo `dataset_id` y los mismos tamaños de subconjunto. En el
    sintético, además, la misma cohorte (`n_samples`, `first_seed`) y semilla de partición; en
    D1, el mismo archivo de partición (por SHA-256) y los mismos animales con los tres AGCC.
    """
    problems: list[str] = []
    split = gnn_run.get("split") if isinstance(gnn_run.get("split"), Mapping) else {}
    assert isinstance(split, Mapping)
    sizes = baseline_run.get("subset_sizes")
    if gnn_run.get("dataset_id") != baseline_run.get("dataset_id"):
        problems.append(
            f"dataset_id {gnn_run.get('dataset_id')!r} ≠ {baseline_run.get('dataset_id')!r}"
        )
    if not isinstance(sizes, Mapping):
        return [*problems, "el run.json de baselines no tiene subset_sizes"]

    if sources.split_file is None:
        source = gnn_run.get("source") if isinstance(gnn_run.get("source"), Mapping) else {}
        assert isinstance(source, Mapping)
        for key in ("n_samples", "first_seed", "split_seed"):
            if source.get(key) != baseline_run.get(key):
                problems.append(f"source.{key} {source.get(key)!r} ≠ {baseline_run.get(key)!r}")
        if split.get("seed") != baseline_run.get("split_seed"):
            problems.append(
                f"split.seed {split.get('seed')!r} ≠ {baseline_run.get('split_seed')!r}"
            )
        counts = split.get("counts")
        if not isinstance(counts, Mapping) or dict(counts) != dict(sizes):
            problems.append(f"split.counts {counts!r} ≠ subset_sizes {dict(sizes)!r}")
        return problems

    expected_name = sources.split_file.name
    registered = split.get("file")
    if not isinstance(registered, str) or Path(registered).name != expected_name:
        problems.append(f"split.file {registered!r} no es {expected_name}")
    accepted = {split_sha256} if isinstance(split_sha256, str) else split_sha256
    if accepted is not None and split.get("sha256") not in accepted:
        problems.append(f"split.sha256 no coincide con {expected_name}")
    subsets = gnn_run.get("subsets") if isinstance(gnn_run.get("subsets"), Mapping) else {}
    assert isinstance(subsets, Mapping)
    for subset in ("train", "val", "test"):
        summary = subsets.get(subset)
        observed = summary.get("with_all_scfa") if isinstance(summary, Mapping) else None
        if observed != sizes.get(subset):
            problems.append(
                f"subsets.{subset}.with_all_scfa {observed!r} ≠ subset_sizes {sizes.get(subset)!r}"
            )
    return problems


def load_dataset(
    sources: DatasetSources, variants: Sequence[str] = GNN_VARIANTS
) -> DatasetComparison:
    """Lee y verifica los reportes de un dataset.

    Raises:
        ComparisonError: si faltan los reportes de baselines, si un reporte es inválido o si
            alguna GNN no está alineada con los baselines.
    """
    baseline_run = read_json(sources.baseline_dir / "run.json")
    baseline = read_evaluation_csv(sources.baseline_dir / "report.csv")
    _check_complete(baseline, sources.baseline_dir / "report.csv")
    gnn_report_path = sources.gnn_dir / "report.csv"
    gnn_all = read_evaluation_csv(gnn_report_path) if gnn_report_path.is_file() else None

    split_sha: frozenset[str] | None = None
    if sources.split_file is not None:
        if not sources.split_file.is_file():
            raise ComparisonError(f"Falta la partición {sources.split_file}.")
        split_sha = split_file_digests(sources.split_file)

    families: dict[str, str] = {}
    for row in baseline.rows:
        families.setdefault(row.model, BASELINE)
    reports = [_select(baseline, SPLITS)]
    pending: list[str] = []
    runs: dict[str, dict[str, Any]] = {}
    for variant in variants:
        run_path = sources.gnn_dir / f"run_{variant}.json"
        rows = (
            EvaluationReport(rows=tuple(r for r in gnn_all.rows if r.model == variant))
            if gnn_all is not None
            else EvaluationReport(rows=())
        )
        families[variant] = GNN
        if not run_path.is_file() or not rows.rows:
            pending.append(variant)
            continue
        info = read_json(run_path)
        problems = alignment_problems(sources, baseline_run, info, split_sha256=split_sha)
        if problems:
            raise ComparisonError(
                f"{run_path} no está alineado con {sources.baseline_dir / 'run.json'}: "
                + "; ".join(problems)
            )
        _check_complete(rows, gnn_report_path)
        reports.append(_select(rows, SPLITS))
        runs[variant] = info

    alignment = {
        "dataset_id": baseline_run.get("dataset_id"),
        "subset_sizes": dict(baseline_run.get("subset_sizes") or {}),
        "split_file": None if sources.split_file is None else sources.split_file.name,
        "split_sha256": _common(info.get("split", {}).get("sha256") for info in runs.values()),
        "verified_runs": sorted(runs),
        "commits": sorted({str(info.get("git", {}).get("commit")) for info in runs.values()}),
    }
    return DatasetComparison(
        sources=sources,
        report=combine_reports(reports),
        families=families,
        pending=tuple(pending),
        alignment=alignment,
    )


# ---------------------------------------------------------------------------
# Criterio de F4 y salidas
# ---------------------------------------------------------------------------


def assess_criterion(comparison: DatasetComparison) -> CriterionResult:
    """¿Alguna GNN tiene RMSE promedio de `test` menor o igual que algún baseline?"""

    def rmse(model: str) -> float | None:
        return comparison.value(model, CRITERION_SPLIT, CRITERION_METRIC)

    gnns = [(m, v) for m in comparison.gnns if (v := rmse(m)) is not None]
    baselines = [(m, v) for m in comparison.baselines if (v := rmse(m)) is not None]
    pairs = tuple((g, b) for g, gv in gnns for b, bv in baselines if gv <= bv)
    return CriterionResult(
        dataset=comparison.sources.name,
        pairs=pairs,
        best_gnn=min(gnns, key=lambda item: item[1])[0] if gnns else None,
        best_baseline=min(baselines, key=lambda item: item[1])[0] if baselines else None,
    )


def to_csv(comparisons: Sequence[DatasetComparison]) -> str:
    """Una fila por dataset, modelo, subconjunto y métrica; las GNN pendientes, sin valores."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for comparison in comparisons:
        name = comparison.sources.name
        for row in comparison.report.rows:
            writer.writerow(
                [name, comparison.families[row.model], row.model, row.split, row.metric]
                + [_number(row.targets.get(t)) for t in DEFAULT_SCFA_TARGETS]
                + [_number(row.average), OK]
            )
        for variant in comparison.pending:
            for split in SPLITS:
                for metric in METRIC_NAMES:
                    writer.writerow(
                        [name, GNN, variant, split, metric]
                        + [""] * len(DEFAULT_SCFA_TARGETS)
                        + ["", PENDING]
                    )
    return buffer.getvalue()


def summary_table(comparison: DatasetComparison) -> str:
    """Tabla compacta: RMSE, MAE y R² promedio en `val` y `test` por modelo."""
    header = (
        "| Familia | Modelo | RMSE val | RMSE test | MAE val | MAE test | R² val | R² test |\n"
        "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |"
    )
    lines = [header]
    for model, family in comparison.families.items():
        if model in comparison.pending:
            lines.append(f"| {family} | `{model}` | {PENDING} | | | | | |")
            continue
        cells = [
            _fmt(comparison.value(model, split, metric))
            for metric in ("rmse", "mae", "r2")
            for split in SPLITS
        ]
        lines.append(f"| {family} | `{model}` | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def to_markdown(comparisons: Sequence[DatasetComparison], command: str) -> str:
    """Reporte completo: verificación, criterio de F4, resumen y tablas por AGCC."""
    parts = [
        "# Comparación GNN frente a baselines (A45-6)",
        "",
        f"Generado con `{command}` a partir de `reports/baselines/` y `reports/gnn/`; no entrena "
        "modelos. Métricas en mmol/kg (en D1, de digesta fresca, base húmeda); `negative_pct` es "
        "el % de predicciones negativas. La interpretación y sus advertencias están en "
        "`docs/models/gnn-evaluation.md`.",
        "",
        "## Criterio de salida de F4 (provisional)",
        "",
        f"Una GNN iguala o supera un baseline si su RMSE promedio de `{CRITERION_SPLIT}` es menor "
        "o igual.",
        "",
        *PROVISIONAL_NOTE,
        "",
        "| Dataset | ¿Se cumple? (provisional) | Mejor GNN | Mejor baseline "
        "| GNN que igualan o superan a… |",
        "| :--- | :---: | :--- | :--- | :--- |",
    ]
    for comparison in comparisons:
        result = assess_criterion(comparison)
        detail = _pairs_text(result, comparison)
        parts.append(
            f"| {comparison.sources.label} | {'sí' if result.met else 'no'} | "
            f"`{result.best_gnn}` | `{result.best_baseline}` | {detail} |"
        )
    notes = [f"- {c.sources.label}: {c.sources.note}" for c in comparisons if c.sources.note]
    if notes:
        parts += ["", *notes]
    for comparison in comparisons:
        alignment = comparison.alignment
        parts += [
            "",
            f"## {comparison.sources.label}",
            "",
            f"- `dataset_id`: `{alignment.get('dataset_id')}`; muestras con los tres AGCC por "
            f"subconjunto: {_sizes(alignment.get('subset_sizes'))}.",
            f"- Partición: {_split_text(alignment)}.",
            f"- Verificado con los `run.json`: {_list(alignment.get('verified_runs'))}"
            f" (commit {_list(alignment.get('commits'))}).",
        ]
        if comparison.pending:
            parts.append(f"- **Pendientes:** {_list(comparison.pending)}.")
        parts += [
            "",
            "### Resumen (promedio de los tres AGCC)",
            "",
            summary_table(comparison),
            "",
            "### Detalle por AGCC",
            "",
            comparison.report.to_markdown(),
        ]
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _pairs_text(result: CriterionResult, comparison: DatasetComparison) -> str:
    """Qué baselines iguala o supera cada GNN, abreviado cuando son todos."""
    available = [
        m
        for m in comparison.baselines
        if comparison.value(m, CRITERION_SPLIT, CRITERION_METRIC) is not None
    ]
    beaten: dict[str, list[str]] = {}
    for gnn, baseline in result.pairs:
        beaten.setdefault(gnn, []).append(baseline)
    if not beaten:
        return "—"
    gnns = [g for g in comparison.gnns if g not in comparison.pending]
    if set(beaten) == set(gnns) and all(len(b) == len(available) for b in beaten.values()):
        return f"las {len(gnns)} GNN a los {len(available)} baselines"
    return "; ".join(
        f"`{g}`: " + ("todos" if len(b) == len(available) else ", ".join(f"`{x}`" for x in b))
        for g, b in beaten.items()
    )


def _select(report: EvaluationReport, splits: Sequence[str]) -> EvaluationReport:
    return EvaluationReport(rows=tuple(r for r in report.rows if r.split in splits))


def _check_complete(report: EvaluationReport, path: Path) -> None:
    for model in dict.fromkeys(row.model for row in report.rows):
        for split in SPLITS:
            found = {r.metric for r in report.rows if r.model == model and r.split == split}
            if not set(METRIC_NAMES) <= found:
                raise ComparisonError(f"{path}: {model} no tiene todas las métricas en {split}.")


def _common(values: Any) -> Any:
    found = set(values)
    return found.pop() if len(found) == 1 else None


def _number(value: float | None) -> str:
    return "" if value is None else repr(float(value))


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.4f}"


def _sizes(sizes: Any) -> str:
    if not isinstance(sizes, Mapping):
        return "—"
    return ", ".join(f"{k} {v}" for k, v in sizes.items())


def _list(values: Any) -> str:
    return ", ".join(f"`{v}`" for v in values) if values else "—"


def _split_text(alignment: Mapping[str, Any]) -> str:
    sha = alignment.get("split_sha256")
    short = f"SHA-256 `{sha[:12]}…`" if isinstance(sha, str) else "SHA-256 —"
    if alignment.get("split_file"):
        return f"`configs/splits/{alignment['split_file']}`, {short}"
    return f"creada en memoria con la semilla de `reports/baselines/run.json`, {short}"


__all__ = [
    "BASELINE",
    "CRITERION_METRIC",
    "CRITERION_SPLIT",
    "CSV_COLUMNS",
    "GNN",
    "GNN_VARIANTS",
    "OK",
    "PENDING",
    "PROVISIONAL_NOTE",
    "ComparisonError",
    "CriterionResult",
    "DatasetComparison",
    "DatasetSources",
    "alignment_problems",
    "assess_criterion",
    "default_sources",
    "file_sha256",
    "load_dataset",
    "read_evaluation_csv",
    "read_json",
    "split_file_digests",
    "summary_table",
    "to_csv",
    "to_markdown",
]
