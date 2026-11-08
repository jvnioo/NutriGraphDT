"""Construcción de la tabla reproducible de comparación de restricciones (A73-P2)."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

from nutrigraphdt.data.split import split_content_sha256

D06_CONSTRAINT: Final = "d06.hydrogen.propionate_bound"
_PREDICTIVE_METRICS: Final = (
    ("fraction_mae_pp", "fraction_mae_pp"),
    ("fraction_r2", "fraction_r2"),
    ("log_total_mae", "log_total_mae"),
    ("reconstructed_mae", "reconstructed_mae"),
)
_VIOLATION_METRICS: Final = (
    ("vr", "violation_rate_percent"),
    ("vwm", "worst_case_magnitude"),
    ("fr_joint", "joint_feasibility_percent"),
    ("vmm", "mean_magnitude"),
)
_GROUP_ORDER: Final = {"all": 0, "7": 1, "21": 2, "35": 3}
_OUTPUT_COLUMNS: Final = (
    "dataset",
    "cohort",
    "model",
    "arm",
    "group",
    "constraint",
    "fraction_mae_pp_mean",
    "fraction_mae_pp_std",
    "fraction_r2_mean",
    "fraction_r2_std",
    "log_total_mae_mean",
    "log_total_mae_std",
    "reconstructed_mae_mean",
    "reconstructed_mae_std",
    "vr_mean",
    "vr_std",
    "vwm_mean",
    "vwm_std",
    "fr_joint_mean",
    "fr_joint_std",
    "vmm_mean",
    "vmm_std",
    "n_folds",
)


def _read_json(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: se esperaba un objeto JSON.")
    return data


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: falta la cabecera CSV.")
        return list(reader)


def _required_number(value: str | None, context: str) -> str:
    if value is None or value == "":
        raise ValueError(f"{context}: valor numérico ausente.")
    try:
        number = float(value)
    except ValueError as error:
        raise ValueError(f"{context}: valor no numérico {value!r}.") from error
    if not math.isfinite(number):
        raise ValueError(f"{context}: valor numérico no finito {value!r}.")
    return value


def _index_unique(
    rows: Sequence[dict[str, str]], keys: tuple[str, ...], source: Path
) -> dict[tuple[str, ...], dict[str, str]]:
    indexed: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        key = tuple(row[name] for name in keys)
        if key in indexed:
            raise ValueError(f"{source}: clave duplicada {key!r}.")
        indexed[key] = row
    return indexed


def _validate_reference_plan(
    *,
    comparison_run: Mapping[str, object],
    baseline_run: Mapping[str, object],
    plan_path: Path,
) -> str:
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes.decode("utf-8"))
    if not isinstance(plan, Mapping):
        raise ValueError(f"{plan_path}: el plan debe ser un objeto JSON.")
    canonical_digest = split_content_sha256(plan)
    comparison_canonical = comparison_run.get("plan_canonical_sha256")
    if comparison_canonical != canonical_digest:
        raise ValueError(
            "El plan local no coincide con plan_canonical_sha256 de la comparación D1."
        )

    raw_digests = {
        hashlib.sha256(plan_bytes).hexdigest(),
        hashlib.sha256(plan_bytes.replace(b"\r\n", b"\n")).hexdigest(),
    }
    comparison_raw = comparison_run.get("plan_sha256")
    if comparison_raw not in raw_digests:
        raise ValueError("El plan local no coincide con plan_sha256 de la comparación D1.")

    baseline_canonical = baseline_run.get("plan_canonical_sha256")
    if baseline_canonical is not None:
        if baseline_canonical != canonical_digest:
            raise ValueError(
                "El baseline D1 usa un plan canónico distinto; referencia no comparable."
            )
    else:
        baseline_raw = baseline_run.get("plan_sha256")
        if not isinstance(baseline_raw, str) or baseline_raw not in raw_digests:
            raise ValueError(
                "El baseline D1 no registra un hash del plan comparable con el plan local."
            )
    return canonical_digest


def _metric_row(
    metrics: Mapping[tuple[str, ...], dict[str, str]],
    *,
    model: str,
    arm: str,
    split: str,
    group: str,
    metric: str,
) -> dict[str, str]:
    key = (model, arm, split, group, metric)
    try:
        return metrics[key]
    except KeyError as error:
        raise ValueError(f"Falta la métrica requerida {key!r}.") from error


def _validate_metric_coverage(
    metrics: Mapping[tuple[str, ...], dict[str, str]],
    *,
    dataset: str,
    split: str,
    groups: Sequence[str],
    arms: Sequence[str],
) -> None:
    for group in groups:
        models: dict[str, set[str]] = {}
        for model, arm, row_split, row_group, _ in metrics:
            if row_split == split and row_group == group and arm in arms:
                models.setdefault(model, set()).add(arm)
        if not models:
            raise ValueError(f"Faltan métricas de {dataset} para group={group!r}.")
        incomplete = {model: sorted(set(arms) - present) for model, present in models.items()}
        incomplete = {model: missing for model, missing in incomplete.items() if missing}
        if incomplete:
            raise ValueError(
                f"Faltan brazos {incomplete!r} en métricas de {dataset}, group={group!r}."
            )


def _violation_row(
    violations: Mapping[tuple[str, ...], dict[str, str]],
    *,
    model: str,
    arm: str,
    metric: str,
) -> dict[str, str]:
    key = (model, arm, "test", D06_CONSTRAINT, metric)
    try:
        return violations[key]
    except KeyError as error:
        raise ValueError(f"Falta la métrica de violación requerida {key!r}.") from error


def _comparison_rows(
    *,
    dataset: str,
    cohort: str,
    group: str,
    metric_index: Mapping[tuple[str, ...], dict[str, str]],
    violation_index: Mapping[tuple[str, ...], dict[str, str]],
    split: str,
    arms: Sequence[str],
) -> list[dict[str, str]]:
    models = sorted(
        {key[0] for key in metric_index if key[1] in arms and key[2] == split and key[3] == group}
    )
    result: list[dict[str, str]] = []
    for model in models:
        for arm in arms:
            if (model, arm, split, group, "fraction_mae_pp_mean") not in metric_index:
                continue
            row = {column: "" for column in _OUTPUT_COLUMNS}
            row.update(
                {
                    "dataset": dataset,
                    "cohort": cohort,
                    "model": model,
                    "arm": arm,
                    "group": group,
                    "constraint": D06_CONSTRAINT,
                }
            )
            for output_name, metric_name in _PREDICTIVE_METRICS:
                for statistic in ("mean", "std"):
                    metric = f"{metric_name}_{statistic}"
                    values = _metric_row(
                        metric_index,
                        model=model,
                        arm=arm,
                        split=split,
                        group=group,
                        metric=metric,
                    )
                    row[f"{output_name}_{statistic}"] = _required_number(
                        values["average"], f"{model}/{arm}/{group}/{metric}"
                    )
            fraction_count = _metric_row(
                metric_index,
                model=model,
                arm=arm,
                split=split,
                group=group,
                metric="fraction_mae_pp_n",
            )
            row["n_folds"] = _required_number(
                fraction_count["average"], f"{model}/{arm}/{group}/n_folds"
            )
            for output_name, metric_name in _VIOLATION_METRICS:
                values = _violation_row(
                    violation_index,
                    model=model,
                    arm=arm,
                    metric=metric_name,
                )
                row[f"{output_name}_mean"] = _required_number(
                    values["mean"], f"{model}/{arm}/{metric_name}/mean"
                )
                row[f"{output_name}_std"] = _required_number(
                    values["std"], f"{model}/{arm}/{metric_name}/std"
                )
            result.append(row)
    return result


def _baseline_rows(metrics_path: Path, groups: Sequence[str]) -> list[dict[str, str]]:
    indexed = _index_unique(
        _read_csv(metrics_path), ("model", "split", "group", "metric"), metrics_path
    )
    result: list[dict[str, str]] = []
    for model in ("dummy_mean", "day_only"):
        for group in groups:
            if (model, "cv", group, "fraction_mae_pp_mean") not in indexed:
                raise ValueError(f"Falta la referencia {model} para group={group!r}.")
            row = {column: "" for column in _OUTPUT_COLUMNS}
            row.update(
                {
                    "dataset": "d1",
                    "cohort": "D1 HoloFood",
                    "model": model,
                    "arm": "reference",
                    "group": group,
                    "constraint": D06_CONSTRAINT,
                }
            )
            for output_name, metric_name in _PREDICTIVE_METRICS:
                for statistic in ("mean", "std"):
                    metric = f"{metric_name}_{statistic}"
                    values = indexed.get((model, "cv", group, metric))
                    if values is None:
                        raise ValueError(
                            f"Falta la métrica de referencia {model}/{group}/{metric}."
                        )
                    row[f"{output_name}_{statistic}"] = _required_number(
                        values["average"], f"{model}/{group}/{metric}"
                    )
            count = indexed.get((model, "cv", group, "fraction_mae_pp_n"))
            if count is not None:
                row["n_folds"] = _required_number(count["average"], f"{model}/{group}/n_folds")
            result.append(row)
    return result


def _format_pair(row: Mapping[str, str], name: str, *, percent: bool = False) -> str:
    mean, std = row[f"{name}_mean"], row[f"{name}_std"]
    if not mean or not std:
        return "—"
    suffix = "%" if percent else ""
    return f"{float(mean):.4f} ± {float(std):.4f}{suffix}"


def _render_table(rows: Sequence[dict[str, str]]) -> list[str]:
    headings = (
        "Cohorte",
        "Modelo",
        "Brazo",
        "Grupo",
        "MAE fracciones (pp)",
        "R² fracciones",
        "MAE ln T",
        "MAE reconstruido",
        "VR",
        "VWM",
        "FR conjunta",
        "VMM",
    )
    lines = ["| " + " | ".join(headings) + " |", "|" + "|".join("---" for _ in headings) + "|"]
    for row in rows:
        values = (
            row["cohort"],
            row["model"],
            row["arm"],
            row["group"],
            _format_pair(row, "fraction_mae_pp"),
            _format_pair(row, "fraction_r2"),
            _format_pair(row, "log_total_mae"),
            _format_pair(row, "reconstructed_mae"),
            _format_pair(row, "vr", percent=True),
            _format_pair(row, "vwm"),
            _format_pair(row, "fr_joint", percent=True),
            _format_pair(row, "vmm"),
        )
        lines.append("| " + " | ".join(values) + " |")
    return lines


def _arms_identical(rows: Sequence[dict[str, str]], groups: Sequence[str]) -> bool:
    values = tuple(
        column for column in _OUTPUT_COLUMNS if column.endswith("_mean") or column.endswith("_std")
    )
    indexed = {(row["dataset"], row["model"], row["group"], row["arm"]): row for row in rows}
    pairs = {
        (row["dataset"], row["model"], row["group"])
        for row in rows
        if row["dataset"] == "d1"
        and row["group"] in groups
        and row["arm"] in {"free", "constrained"}
    }
    if not pairs:
        return False
    for dataset, model, group in pairs:
        free = indexed.get((dataset, model, group, "free"))
        constrained = indexed.get((dataset, model, group, "constrained"))
        if free is None or constrained is None:
            return False
        if any(free[column] != constrained[column] for column in values):
            return False
    return True


def _write_report(
    path: Path,
    *,
    rows: Sequence[dict[str, str]],
    canonical_digest: str,
    baseline_models: Sequence[str],
) -> None:
    main_rows = [row for row in rows if row["group"] == "all"]
    day_rows = [row for row in rows if row["dataset"] == "d1" and row["group"] in {"7", "21", "35"}]
    identical = _arms_identical(rows, ("all", "7", "21", "35"))
    reference_names = ", ".join(f"`{model}`" for model in baseline_models) or "ninguno"
    main_text = "\n".join(_render_table(main_rows))
    day_text = "\n".join(_render_table(day_rows))
    if identical:
        interpretation = (
            "En los agregados versionados de D1, `free` y `constrained` son idénticos. "
            "D-06 §6 explica que la cota `p_p ≤ 2/3` no se activa en D1; por tanto, "
            "«Factibilidad sin costo» significa que no costó nada porque no hizo nada. "
            "Estos resultados no aportan evidencia de beneficio bioquímico."
        )
    else:
        interpretation = (
            "Los agregados versionados de D1 no son idénticos entre `free` y `constrained`. "
            "D-06 §6 indica que la cota `p_p ≤ 2/3` no se activa en D1; esta diferencia "
            "descriptiva requiere revisión y no constituye evidencia de beneficio bioquímico."
        )
    references_status = (
        f"Comparables con D1: {reference_names}. Hash canónico verificado: `{canonical_digest}`."
    )
    report = f"""# Comparación de modelos con y sin restricciones

Tabla de métricas para D1 y la cohorte sintética, generada desde los CSV versionados.
Los valores se presentan como media ± desviación estándar entre folds (`_mean` y `_std`);
no se usa `_seed_std`. Las métricas predictivas son macro-promedios (`average`). `FR conjunta`
es la factibilidad conjunta en porcentaje; `VR` y `FR` son porcentajes. `VWM` es
`worst_case_magnitude` y `VMM` es `mean_magnitude`, ambos de `violations_summary.csv`.
La tabla no recalcula violaciones desde predicciones. Las restricciones estructurales se omiten:
sus métricas valen 0 por construcción en estos modelos composicionales.

## Resultados principales

{main_text}

## D1 por día de muestreo

Desglose de D1 para los días 7, 21 y 35, según el protocolo §6.1.

{day_text}

## Referencias

Las referencias `dummy_mean` y `day_only` proceden de
`reports/baselines/d1_composition/metrics.csv`;
se incluyen solo para D1. {references_status} La cohorte sintética no tiene referencias baseline:
**no aplica**; no se han fabricado valores.

## Lectura

{interpretation}
La cohorte marcada como `synthetic` es sintética y se interpreta por separado de D1. Las métricas
son descriptivas y no sustituyen la inferencia pareada de A73-P3.
"""
    path.write_text(report, encoding="utf-8", newline="\n")


def build_constraints_comparison(
    *,
    d1_dir: Path,
    synthetic_dir: Path,
    baseline_dir: Path,
    plan_path: Path,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Construye CSV y reporte Markdown desde los artefactos agregados versionados."""
    d1_run = _read_json(d1_dir / "run.json")
    baseline_run = _read_json(baseline_dir / "run.json")
    canonical_digest = _validate_reference_plan(
        comparison_run=d1_run,
        baseline_run=baseline_run,
        plan_path=plan_path,
    )

    d1_metrics_path = d1_dir / "metrics.csv"
    d1_violations_path = d1_dir / "violations_summary.csv"
    synthetic_metrics_path = synthetic_dir / "metrics.csv"
    synthetic_violations_path = synthetic_dir / "violations_summary.csv"
    d1_metrics = _index_unique(
        _read_csv(d1_metrics_path),
        ("model", "arm", "split", "group", "metric"),
        d1_metrics_path,
    )
    d1_violations = _index_unique(
        _read_csv(d1_violations_path),
        ("model", "arm", "subset", "constraint", "metric"),
        d1_violations_path,
    )
    synthetic_metrics = _index_unique(
        _read_csv(synthetic_metrics_path),
        ("model", "arm", "split", "group", "metric"),
        synthetic_metrics_path,
    )
    synthetic_violations = _index_unique(
        _read_csv(synthetic_violations_path),
        ("model", "arm", "subset", "constraint", "metric"),
        synthetic_violations_path,
    )

    d1_groups = ("all", "7", "21", "35")
    _validate_metric_coverage(
        d1_metrics,
        dataset="D1",
        split="test",
        groups=d1_groups,
        arms=("free", "constrained"),
    )
    _validate_metric_coverage(
        synthetic_metrics,
        dataset="cohorte sintética",
        split="test",
        groups=("all",),
        arms=("free", "constrained"),
    )
    rows: list[dict[str, str]] = []
    for group in d1_groups:
        rows.extend(
            _comparison_rows(
                dataset="d1",
                cohort="D1 HoloFood",
                group=group,
                metric_index=d1_metrics,
                violation_index=d1_violations,
                split="test",
                arms=("free", "constrained"),
            )
        )
    rows.extend(
        _comparison_rows(
            dataset="synthetic",
            cohort="cohorte sintética",
            group="all",
            metric_index=synthetic_metrics,
            violation_index=synthetic_violations,
            split="test",
            arms=("free", "constrained"),
        )
    )

    baseline_rows = _baseline_rows(baseline_dir / "metrics.csv", d1_groups)
    rows.extend(baseline_rows)
    rows.sort(
        key=lambda row: (
            0 if row["dataset"] == "d1" else 1,
            _GROUP_ORDER.get(row["group"], 99),
            row["model"],
            {"free": 0, "constrained": 1, "reference": 2}.get(row["arm"], 3),
        )
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "comparison.csv"
    report_path = output_dir / "report.md"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=_OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    baseline_models = sorted({row["model"] for row in baseline_rows if row["group"] == "all"})
    _write_report(
        report_path,
        rows=rows,
        canonical_digest=canonical_digest,
        baseline_models=baseline_models,
    )
    return csv_path, report_path


__all__ = ["D06_CONSTRAINT", "build_constraints_comparison"]
