"""Consolida las métricas de corridas GNN ya entrenadas (A45-3, A45-4).

Lee las corridas registradas por `scripts/train_gnn.py`, verifica sus metadatos frente al
registro de baselines y escribe un reporte reproducible sin copiar checkpoints.

Uso:

    python scripts/report_gnn.py --homo-sage-run runs/<run_id> \\
        --hetero-sage-run runs/<run_id> --hetero-gat-run runs/<run_id>
    python scripts/report_gnn.py --dataset d1 --homo-sage-run runs/<run_id> \\
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

from nutrigraphdt.data.split import split_file_digests
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
DEFAULT_D1_BASELINE_RUN = REPO_ROOT / "reports" / "baselines" / "d1" / "run.json"
DEFAULT_D1_BASELINE_REPORT = REPO_ROOT / "reports" / "baselines" / "d1" / "report.csv"
DEFAULT_D1_OUTPUT = REPO_ROOT / "reports" / "gnn" / "d1"
DEFAULT_D1_SPLIT = REPO_ROOT / "configs" / "splits" / "d1_holofood.json"
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


def _validate_d1_run(
    run_dir: Path,
    expected_variant: str,
    baseline: Mapping[str, Any],
    *,
    split_config_path: Path,
    expected_split: Mapping[str, Any],
    expected_split_sha256: frozenset[str],
) -> tuple[dict[str, Any], EvaluationReport]:
    run_path = run_dir / RUN_FILE
    if not run_path.is_file():
        raise ValueError(f"Falta el archivo de trazabilidad: {run_path}.")
    info = _read_json(run_path)

    if info.get("variant") != expected_variant:
        raise ValueError(
            f"{run_path}: variante {info.get('variant')!r}; se esperaba {expected_variant!r}."
        )
    if info.get("dataset_id") != baseline.get("dataset_id"):
        raise ValueError(f"{run_path}: dataset_id no coincide con reports/baselines/d1/run.json.")

    split = _require_mapping(info.get("split"), label="split", source=run_path)
    if split.get("dataset_id") != baseline.get("dataset_id"):
        raise ValueError(f"{run_path}: split.dataset_id no coincide con el baseline D1.")
    registered_split = split.get("file")
    if not isinstance(registered_split, str) or not registered_split:
        raise ValueError(f"{run_path}: split.file ausente o inválido.")
    registered_path = Path(registered_split)
    if not registered_path.is_absolute():
        registered_path = REPO_ROOT / registered_path
    if registered_path.resolve() != split_config_path.resolve():
        raise ValueError(
            f"{run_path}: split.file no coincide con la configuración {split_config_path}."
        )
    if split.get("version") != expected_split.get("version"):
        raise ValueError(f"{run_path}: split.version no coincide con {split_config_path}.")
    # Hash canónico (#133) o, en corridas anteriores, de los bytes del archivo con LF o CRLF.
    if split.get("sha256") not in expected_split_sha256:
        raise ValueError(f"{run_path}: split.sha256 no coincide con {split_config_path}.")

    subset_sizes = _require_mapping(
        baseline.get("subset_sizes"), label="subset_sizes en baseline D1", source=run_path
    )
    run_subsets = _require_mapping(info.get("subsets"), label="subsets", source=run_path)
    for subset in ("train", "val", "test"):
        summary = _require_mapping(
            run_subsets.get(subset), label=f"subsets.{subset}", source=run_path
        )
        observed = summary.get("with_all_scfa")
        expected = subset_sizes.get(subset)
        if (
            isinstance(observed, bool)
            or not isinstance(observed, int)
            or isinstance(expected, bool)
            or not isinstance(expected, int)
            or observed != expected
        ):
            raise ValueError(
                f"{run_path}: subsets.{subset}.with_all_scfa={observed!r} no coincide con "
                f"subset_sizes.{subset} de reports/baselines/d1/run.json ({expected!r})."
            )
        for count_name in ("received", "deliverable", "with_any_scfa"):
            count = summary.get(count_name)
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError(f"{run_path}: subsets.{subset}.{count_name} ausente o inválido.")

    duration = info.get("duration_seconds")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)):
        raise ValueError(f"{run_path}: duration_seconds ausente o inválido.")
    if not math.isfinite(duration) or duration < 0:
        raise ValueError(f"{run_path}: duration_seconds debe ser finito y no negativo.")
    environment = _require_mapping(info.get("environment"), label="environment", source=run_path)
    if not isinstance(environment.get("device"), str) or not environment["device"]:
        raise ValueError(f"{run_path}: environment.device ausente o inválido.")
    git = _require_mapping(info.get("git"), label="git", source=run_path)
    if git.get("commit") is not None and not isinstance(git.get("commit"), str):
        raise ValueError(f"{run_path}: git.commit debe ser texto o null.")
    if git.get("dirty") is not None and not isinstance(git.get("dirty"), bool):
        raise ValueError(f"{run_path}: git.dirty debe ser booleano o null.")

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


def _build_d1_markdown(
    report: EvaluationReport,
    comparison: EvaluationReport,
    baseline: Mapping[str, Any],
    run_infos: Mapping[str, Mapping[str, Any]],
) -> str:
    split = baseline["subset_sizes"]
    first = next(iter(run_infos.values()))
    subsets = first["subsets"]
    counts_table = [
        "| Subconjunto | Con tres AGCC | Recibidos | Entregables | Con algún AGCC |",
        "| :--- | ---: | ---: | ---: | ---: |",
    ]
    for subset in ("train", "val", "test"):
        summary = subsets[subset]
        counts_table.append(
            f"| {subset} | {split[subset]} | {summary['received']} | "
            f"{summary['deliverable']} | {summary['with_any_scfa']} |"
        )

    run_table = [
        "| Variante | Dispositivo | Duración (s) | Commit | Dirty |",
        "| :--- | :--- | ---: | :--- | :--- |",
    ]
    for variant, _ in VARIANT_ARGUMENTS:
        info = run_infos[variant]
        git = info["git"]
        commit = git.get("commit") or "no registrado"
        dirty_value = git.get("dirty")
        dirty = "sí" if dirty_value is True else "no" if dirty_value is False else "no registrado"
        run_table.append(
            f"| {variant} | {info['environment']['device']} | "
            f"{info['duration_seconds']:.2f} | `{commit}` | {dirty} |"
        )

    return (
        "# Evaluación de variantes GNN en D1 HoloFood (A45-4)\n\n"
        f"- **Dataset:** `{baseline['dataset_id']}`.\n"
        f"- **Partición:** `{first['split']['file']}`, versión "
        f"`{first['split']['version']}`, SHA-256 `{first['split']['sha256']}`; "
        "verificada en las tres corridas contra la configuración indicada.\n"
        "- El reporte consolida corridas existentes; no entrena modelos. Los valores de "
        "`dummy_mean` proceden de `reports/baselines/d1/report.csv`.\n\n"
        "## Métricas GNN\n\n"
        f"{report.to_markdown()}\n\n"
        "## Comparación con `dummy_mean`\n\n"
        f"{comparison.to_markdown()}\n\n"
        "## Conteos por subconjunto\n\n"
        f"{chr(10).join(counts_table)}\n\n"
        "## Duración y trazabilidad de las corridas\n\n"
        "La duración se reporta en segundos y corresponde al dispositivo indicado para cada "
        "corrida.\n\n"
        f"{chr(10).join(run_table)}\n\n"
        "## Advertencias\n\n"
        "- D1 no incluye el tratamiento dietario en las entradas de la GNN; los baselines sí "
        "usan esa información, por lo que la comparación debe considerar esta diferencia.\n"
        "- En D1 los taxones están aislados y las variantes no aprovechan diferencias "
        "estructurales de sus convoluciones; el dataset no permite medirlas.\n"
        f"- `val` contiene solo {split['val']} animales con los tres AGCC, por lo que las "
        "métricas de "
        "validación tienen una muestra pequeña.\n"
    )


def generate_report(
    run_dirs: Mapping[str, Path],
    *,
    dataset: str = "synthetic",
    baseline_run_path: Path | None = None,
    baseline_report_path: Path | None = None,
    output: Path | None = None,
    split_config_path: Path = DEFAULT_D1_SPLIT,
) -> None:
    """Valida las corridas y escribe el reporte y los run.json sin copiar archivos pesados."""
    if dataset not in {"synthetic", "d1"}:
        raise ValueError(f"Dataset no válido: {dataset!r}. Use 'synthetic' o 'd1'.")
    if dataset == "synthetic":
        baseline_run_path = baseline_run_path or DEFAULT_BASELINE_RUN
        baseline_report_path = baseline_report_path or DEFAULT_BASELINE_REPORT
        output = output or DEFAULT_OUTPUT
    else:
        baseline_run_path = baseline_run_path or DEFAULT_D1_BASELINE_RUN
        baseline_report_path = baseline_report_path or DEFAULT_D1_BASELINE_REPORT
        output = output or DEFAULT_D1_OUTPUT

    baseline = _read_json(baseline_run_path)
    expected_split: dict[str, Any] | None = None
    expected_split_sha256: frozenset[str] | None = None
    resolved_split_config = split_config_path.resolve()
    if dataset == "d1":
        expected_split = _read_json(resolved_split_config)
        if expected_split.get("dataset_id") != baseline.get("dataset_id"):
            raise ValueError(
                f"{resolved_split_config}: dataset_id no coincide con "
                "reports/baselines/d1/run.json."
            )
        if not isinstance(expected_split.get("version"), str):
            raise ValueError(f"{resolved_split_config}: version ausente o inválida.")
        try:
            expected_split_sha256 = split_file_digests(resolved_split_config)
        except OSError as error:
            raise ValueError(f"No se pudo leer {resolved_split_config}: {error}.") from error

    reports: list[EvaluationReport] = []
    partition_hash: str | None = None
    run_infos: dict[str, dict[str, Any]] = {}

    for variant, _ in VARIANT_ARGUMENTS:
        run_dir = run_dirs[variant]
        if dataset == "synthetic":
            info, report = _validate_run(run_dir, variant, baseline)
        else:
            assert expected_split is not None
            assert expected_split_sha256 is not None
            info, report = _validate_d1_run(
                run_dir,
                variant,
                baseline,
                split_config_path=resolved_split_config,
                expected_split=expected_split,
                expected_split_sha256=expected_split_sha256,
            )
        current_hash = info["split"]["sha256"]
        # En D1 cada corrida ya se comparó con el archivo de partición, cuyo hash puede estar
        # registrado en forma canónica o de bytes (#133); en el sintético se exige igualdad.
        if dataset == "synthetic" and partition_hash is not None and current_hash != partition_hash:
            raise ValueError(
                f"{run_dir / RUN_FILE}: split.sha256 no coincide con la partición "
                "de las otras corridas GNN."
            )
        partition_hash = current_hash
        reports.append(report)
        run_infos[variant] = info

    baseline_report = _validate_baseline_report(baseline_report_path)
    _validate_targets(reports, baseline_report)
    combined = combine_reports(reports)
    dummy_mean = EvaluationReport(
        rows=tuple(row for row in baseline_report.rows if row.model == "dummy_mean")
    )
    comparison = combine_reports([dummy_mean, combined])

    output.mkdir(parents=True, exist_ok=True)
    (output / "report.csv").write_text(combined.to_csv(), encoding="utf-8", newline="")
    markdown = (
        _build_markdown(combined, comparison, baseline)
        if dataset == "synthetic"
        else _build_d1_markdown(combined, comparison, baseline, run_infos)
    )
    (output / "report.md").write_text(
        markdown + "\n",
        encoding="utf-8",
        newline="",
    )
    for variant, _ in VARIANT_ARGUMENTS:
        shutil.copyfile(run_dirs[variant] / RUN_FILE, output / f"run_{variant}.json")


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset", choices=("synthetic", "d1"), default="synthetic")
    for variant, argument in VARIANT_ARGUMENTS:
        parser.add_argument(
            f"--{variant.replace('_', '-')}-run",
            dest=argument,
            type=Path,
            required=True,
            help=f"Directorio de corrida registrada para {variant}.",
        )
    parser.add_argument("--baseline-run-json", type=Path)
    parser.add_argument("--baseline-report-csv", type=Path)
    parser.add_argument("--split-config", type=Path, default=DEFAULT_D1_SPLIT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    run_dirs = {variant: getattr(args, argument) for variant, argument in VARIANT_ARGUMENTS}
    try:
        generate_report(
            run_dirs,
            dataset=args.dataset,
            baseline_run_path=args.baseline_run_json,
            baseline_report_path=args.baseline_report_csv,
            output=args.output,
            split_config_path=args.split_config,
        )
    except (OSError, ValueError, KeyError) as error:
        print(f"No se pudo generar el reporte GNN: {error}", file=sys.stderr)
        return 2

    print(f"Reporte GNN escrito en {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
