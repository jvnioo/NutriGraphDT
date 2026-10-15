"""Consolida las métricas de corridas GNN sintéticas ya entrenadas (A45-3).

Lee las corridas registradas por `scripts/train_gnn.py`, verifica sus metadatos frente al
registro de baselines y escribe un reporte reproducible sin copiar checkpoints.

Uso:

    python scripts/report_gnn.py --homo-sage-run runs/<run_id> \\
        --hetero-sage-run runs/<run_id> --hetero-gat-run runs/<run_id>
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from nutrigraphdt.models.metrics import (
    METRIC_NAMES,
    EvaluationReport,
    MetricRow,
    combine_reports,
)
from nutrigraphdt.models.training.tracking import RUN_FILE

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE_RUN = REPO_ROOT / "reports" / "baselines" / "run.json"
DEFAULT_BASELINE_REPORT = REPO_ROOT / "reports" / "baselines" / "report.csv"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "gnn" / "synthetic"
VARIANT_ARGUMENTS = (
    ("homo_sage", "homo_sage_run"),
    ("hetero_sage", "hetero_sage_run"),
    ("hetero_gat", "hetero_gat_run"),
)
RESERVED_METRIC_COLUMNS = {"model", "split", "metric", "average"}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: JSON inválido: {error.msg}.") from error
    if not isinstance(content, dict):
        raise ValueError(f"{path}: se esperaba un objeto JSON.")
    return content


def _read_evaluation_report(path: Path) -> EvaluationReport:
    """Lee el CSV de `EvaluationReport` conservando orden y representación numérica."""
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames
            if fields is None or len(fields) != len(set(fields)):
                raise ValueError(f"{path}: encabezado CSV ausente o con columnas duplicadas.")
            missing = RESERVED_METRIC_COLUMNS.difference(fields)
            if missing:
                raise ValueError(
                    f"{path}: faltan columnas requeridas: {', '.join(sorted(missing))}."
                )
            targets = [field for field in fields if field not in RESERVED_METRIC_COLUMNS]
            if not targets:
                raise ValueError(f"{path}: no hay columnas de objetivos en el CSV.")

            rows: list[MetricRow] = []
            for line_number, record in enumerate(reader, start=2):
                if None in record or any(value is None for value in record.values()):
                    raise ValueError(f"{path}: fila CSV incompleta en la línea {line_number}.")
                try:
                    targets_values = {name: float(record[name]) for name in targets}
                    average = float(record["average"])
                except (TypeError, ValueError) as error:
                    raise ValueError(
                        f"{path}: valor numérico inválido en la línea {line_number}."
                    ) from error
                if not all(math.isfinite(value) for value in (*targets_values.values(), average)):
                    raise ValueError(f"{path}: valor no finito en la línea {line_number}.")
                rows.append(
                    MetricRow(
                        model=record["model"],
                        split=record["split"],
                        metric=record["metric"],
                        targets=targets_values,
                        average=average,
                    )
                )
    except OSError as error:
        raise ValueError(f"No se pudo leer {path}: {error}.") from error
    except csv.Error as error:
        raise ValueError(f"{path}: CSV inválido: {error}.") from error
    return EvaluationReport(rows=tuple(rows))


def _require_mapping(value: Any, *, label: str, source: Path) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{source}: falta el objeto {label} o no es válido.")
    return value


def _validate_run(
    run_dir: Path,
    expected_variant: str,
    baseline: Mapping[str, Any],
) -> tuple[dict[str, Any], EvaluationReport]:
    run_path = run_dir / RUN_FILE
    if not run_path.is_file():
        raise ValueError(f"Falta el archivo de trazabilidad: {run_path}.")
    info = _read_json(run_path)

    if info.get("variant") != expected_variant:
        raise ValueError(
            f"{run_path}: variante {info.get('variant')!r}; se esperaba {expected_variant!r}."
        )

    source = _require_mapping(info.get("source"), label="source", source=run_path)
    split = _require_mapping(info.get("split"), label="split", source=run_path)
    training_config = _require_mapping(
        info.get("training_config"), label="training_config", source=run_path
    )
    subset_sizes = _require_mapping(
        baseline.get("subset_sizes"), label="subset_sizes en baseline run.json", source=run_path
    )

    if source.get("dataset") != "synthetic":
        raise ValueError(f"{run_path}: source.dataset debe ser 'synthetic'.")
    for key in ("n_samples", "first_seed", "split_seed"):
        if key not in baseline or source.get(key) != baseline[key]:
            raise ValueError(
                f"{run_path}: source.{key}={source.get(key)!r} no coincide con "
                f"reports/baselines/run.json ({baseline.get(key)!r})."
            )
    for key in ("dataset_id",):
        if info.get(key) != baseline.get(key) or split.get(key) != baseline.get(key):
            raise ValueError(
                f"{run_path}: dataset_id no coincide con el de reports/baselines/run.json."
            )
    if split.get("seed") != baseline.get("split_seed"):
        raise ValueError(
            f"{run_path}: split.seed no coincide con split_seed de reports/baselines/run.json."
        )
    if info.get("seed") != baseline.get("split_seed") or training_config.get(
        "seed"
    ) != baseline.get("split_seed"):
        raise ValueError(
            f"{run_path}: semilla de entrenamiento no coincide con split_seed "
            "de reports/baselines/run.json."
        )

    counts = _require_mapping(split.get("counts"), label="split.counts", source=run_path)
    if dict(counts) != dict(subset_sizes):
        raise ValueError(
            f"{run_path}: split.counts={dict(counts)!r} no coincide con "
            f"subset_sizes de reports/baselines/run.json ({dict(subset_sizes)!r})."
        )
    if not isinstance(split.get("sha256"), str) or not split["sha256"]:
        raise ValueError(f"{run_path}: split.sha256 ausente o inválido.")

    metrics_path = run_dir / "metrics.csv"
    report = _read_evaluation_report(metrics_path)
    selected = tuple(row for row in report.rows if row.split in {"val", "test"})
    if any(row.model != expected_variant for row in selected):
        raise ValueError(f"{metrics_path}: hay filas que no pertenecen a {expected_variant}.")
    for subset in ("val", "test"):
        subset_metrics = [row.metric for row in selected if row.split == subset]
        if len(subset_metrics) != len(METRIC_NAMES) or set(subset_metrics) != set(METRIC_NAMES):
            raise ValueError(f"{metrics_path}: se esperaba una fila de cada métrica en {subset}.")
    if not selected:
        raise ValueError(f"{metrics_path}: no contiene métricas de val y test.")
    return info, EvaluationReport(rows=selected)


def _validate_baseline_report(path: Path) -> EvaluationReport:
    report = _read_evaluation_report(path)
    rows = tuple(
        row for row in report.rows if row.model == "dummy_mean" and row.split in {"val", "test"}
    )
    for subset in ("val", "test"):
        subset_metrics = [row.metric for row in rows if row.split == subset]
        if len(subset_metrics) != len(METRIC_NAMES) or set(subset_metrics) != set(METRIC_NAMES):
            raise ValueError(f"{path}: dummy_mean debe tener una fila de cada métrica en {subset}.")
    if not rows:
        raise ValueError(f"{path}: no se encontraron métricas de dummy_mean para val y test.")
    return EvaluationReport(rows=rows)


def _validate_targets(reports: Sequence[EvaluationReport], baseline: EvaluationReport) -> None:
    expected = tuple(baseline.rows[0].targets)
    if any(tuple(row.targets) != expected for report in reports for row in report.rows):
        raise ValueError("Las métricas de GNN y dummy_mean no comparten las mismas columnas AGCC.")


def _build_markdown(
    report: EvaluationReport,
    comparison: EvaluationReport,
    baseline: Mapping[str, Any],
) -> str:
    sizes = baseline["subset_sizes"]
    first_seed = baseline["first_seed"]
    last_seed = first_seed + baseline["n_samples"] - 1
    return (
        "# Evaluación de variantes GNN en la cohorte sintética (A45-3)\n\n"
        f"- **Cohorte:** `{baseline['dataset_id']}` ({baseline['n_samples']} instancias; "
        f"semillas {first_seed} a {last_seed}).\n"
        f"- **Partición:** semilla `{baseline['split_seed']}` "
        f"({sizes['train']} train, {sizes['val']} val, {sizes['test']} test), "
        "verificada contra `reports/baselines/run.json`.\n"
        "- Las corridas y métricas se leen de los directorios de entrenamiento indicados; "
        "este script no entrena modelos.\n\n"
        "> [!WARNING]\n"
        "> Esta evaluación es exclusivamente sintética y no mide desempeño predictivo real. "
        "En el generador actual, los AGCC no dependen de las entradas; el resultado verifica "
        "el flujo de entrenamiento y evaluación, no la capacidad predictiva.\n"
        ">\n"
        "> Las diferencias pequeñas frente a `dummy_mean` no son interpretables en este "
        "generador y no permiten afirmar que una variante supere al baseline.\n\n"
        "## Métricas GNN\n\n"
        f"{report.to_markdown()}\n\n"
        "## Comparación con `dummy_mean`\n\n"
        "Los valores de `dummy_mean` se leen de `reports/baselines/report.csv`; "
        "las diferencias no se interpretan como evidencia de superioridad predictiva.\n\n"
        f"{comparison.to_markdown()}\n"
    )


def generate_report(
    run_dirs: Mapping[str, Path],
    *,
    baseline_run_path: Path = DEFAULT_BASELINE_RUN,
    baseline_report_path: Path = DEFAULT_BASELINE_REPORT,
    output: Path = DEFAULT_OUTPUT,
) -> None:
    """Valida las corridas y escribe el reporte y los run.json sin copiar archivos pesados."""
    baseline = _read_json(baseline_run_path)
    reports: list[EvaluationReport] = []
    partition_hash: str | None = None

    for variant, _ in VARIANT_ARGUMENTS:
        run_dir = run_dirs[variant]
        info, report = _validate_run(run_dir, variant, baseline)
        current_hash = info["split"]["sha256"]
        if partition_hash is not None and current_hash != partition_hash:
            raise ValueError(
                f"{run_dir / RUN_FILE}: split.sha256 no coincide con la partición "
                "de las otras corridas GNN."
            )
        partition_hash = current_hash
        reports.append(report)

    baseline_report = _validate_baseline_report(baseline_report_path)
    _validate_targets(reports, baseline_report)
    combined = combine_reports(reports)
    dummy_mean = EvaluationReport(
        rows=tuple(row for row in baseline_report.rows if row.model == "dummy_mean")
    )
    comparison = combine_reports([dummy_mean, combined])

    output.mkdir(parents=True, exist_ok=True)
    (output / "report.csv").write_text(combined.to_csv(), encoding="utf-8", newline="")
    (output / "report.md").write_text(
        _build_markdown(combined, comparison, baseline) + "\n",
        encoding="utf-8",
        newline="",
    )
    for variant, _ in VARIANT_ARGUMENTS:
        shutil.copyfile(run_dirs[variant] / RUN_FILE, output / f"run_{variant}.json")


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    for variant, argument in VARIANT_ARGUMENTS:
        parser.add_argument(
            f"--{variant.replace('_', '-')}-run",
            dest=argument,
            type=Path,
            required=True,
            help=f"Directorio de corrida registrada para {variant}.",
        )
    parser.add_argument("--baseline-run-json", type=Path, default=DEFAULT_BASELINE_RUN)
    parser.add_argument("--baseline-report-csv", type=Path, default=DEFAULT_BASELINE_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    run_dirs = {variant: getattr(args, argument) for variant, argument in VARIANT_ARGUMENTS}
    try:
        generate_report(
            run_dirs,
            baseline_run_path=args.baseline_run_json,
            baseline_report_path=args.baseline_report_csv,
            output=args.output,
        )
    except (OSError, ValueError, KeyError) as error:
        print(f"No se pudo generar el reporte GNN: {error}", file=sys.stderr)
        return 2

    print(f"Reporte GNN escrito en {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
