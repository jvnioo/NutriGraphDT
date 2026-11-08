"""Construcción de la tabla reproducible de comparación de restricciones (A73-P2)."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean, stdev
from typing import Final

from nutrigraphdt.data.split import split_content_sha256
from nutrigraphdt.models.paired_comparison import (
    CATEGORIES,
    DELTA_ROPE_PP,
    PairedComparison,
    delta_category,
    paired_comparison,
)

D06_CONSTRAINT: Final = "d06.hydrogen.propionate_bound"
_PREDICTIVE_METRICS: Final = (
    ("fraction_mae_pp", "fraction_mae_pp"),
    ("fraction_r2", "fraction_r2"),
    ("log_total_mae", "log_total_mae"),
    ("reconstructed_mae", "reconstructed_mae"),
)
_VIOLATION_METRICS: Final = (
    ("vr", "violation_rate_percent"),
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
    "vwm_max",
    "fr_joint_mean",
    "fr_joint_std",
    "vmm_mean",
    "vmm_std",
    "n_folds",
)
_PAIRED_STATISTIC_COLUMNS: Final = (
    "dataset",
    "variant",
    "metric",
    "contrast",
    "n_folds",
    "n_seeds",
    "delta",
    "ci_95_low",
    "ci_95_high",
    "t_statistic",
    "degrees_of_freedom",
    "p_t_corrected",
    "p_wilcoxon",
    "cohen_d",
    "undefined_reason",
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


def _required_integer(value: str | None, context: str) -> str:
    number = float(_required_number(value, context))
    if not number.is_integer():
        raise ValueError(f"{context}: se esperaba un entero, se obtuvo {value!r}.")
    return str(int(number))


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
            row["n_folds"] = _required_integer(
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
            vwm = _violation_row(
                violation_index,
                model=model,
                arm=arm,
                metric="worst_case_magnitude",
            )
            row["vwm_max"] = _required_number(vwm["max"], f"{model}/{arm}/worst_case_magnitude/max")
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
                row["n_folds"] = _required_integer(count["average"], f"{model}/{group}/n_folds")
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
        "VWM (máx.)",
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
            row["vwm_max"] or "—",
            _format_pair(row, "fr_joint", percent=True),
            _format_pair(row, "vmm"),
        )
        lines.append("| " + " | ".join(values) + " |")
    return lines


def _arms_identical(rows: Sequence[dict[str, str]], dataset: str, groups: Sequence[str]) -> bool:
    values = tuple(
        column
        for column in _OUTPUT_COLUMNS
        if column.endswith("_mean") or column.endswith("_std") or column == "vwm_max"
    )
    indexed = {(row["dataset"], row["model"], row["group"], row["arm"]): row for row in rows}
    pairs = {
        (row["dataset"], row["model"], row["group"])
        for row in rows
        if row["dataset"] == dataset
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


def _dataset_reading(
    rows: Sequence[dict[str, str]], dataset: str, groups: Sequence[str]
) -> tuple[bool, bool]:
    dataset_rows = [
        row
        for row in rows
        if row["dataset"] == dataset
        and row["group"] in groups
        and row["arm"] in {"free", "constrained"}
    ]
    if not dataset_rows:
        raise ValueError(f"No hay filas comparables para dataset={dataset!r}.")
    arms_identical = _arms_identical(rows, dataset, groups)
    zero_vr = all(float(row["vr_mean"]) == 0.0 for row in dataset_rows)
    return arms_identical, zero_vr


def _dataset_reading_text(dataset_label: str, arms_identical: bool, zero_vr: bool) -> str:
    arms = "son idénticos" if arms_identical else "no son idénticos"
    vr = "VR = 0" if zero_vr else "VR no es 0"
    return f"{dataset_label}: los brazos {arms} y {vr}."


def _undefined_reason(row: Mapping[str, str]) -> str:
    reasons: list[str] = []
    try:
        std_delta = float(row["std_delta"])
    except (KeyError, ValueError):
        std_delta = math.nan
    if std_delta == 0.0:
        reasons.append("Desviación de las diferencias entre folds = 0; t y p no definidos.")
        if row.get("p_wilcoxon", row.get("wilcoxon_p_value", "nan")).lower() == "nan":
            reasons.append(
                "Wilcoxon no definido porque las diferencias por semilla son todas cero."
            )
        if row.get("cohen_d", "nan").lower() == "nan":
            reasons.append("d de Cohen no definida porque la desviación es cero.")
    else:
        if row.get("p_wilcoxon", row.get("wilcoxon_p_value", "")).lower() == "nan":
            reasons.append("Wilcoxon no definido para estas medias por semilla.")
    return " ".join(reasons)


def _paired_csv_statistics(path: Path, dataset: str) -> list[dict[str, str]]:
    source_rows = _read_csv(path)
    indexed = _index_unique(source_rows, ("model", "metric"), path)
    result: list[dict[str, str]] = []
    for (variant, metric), source in sorted(indexed.items()):
        row = {
            "dataset": dataset,
            "variant": variant,
            "metric": metric,
            "contrast": "constrained − free",
            "n_folds": source["n_folds"],
            "n_seeds": source["n_seeds"],
            "delta": source["mean_delta"],
            "ci_95_low": source["ci_low"],
            "ci_95_high": source["ci_high"],
            "t_statistic": source["t_statistic"],
            "degrees_of_freedom": source["degrees_of_freedom"],
            "p_t_corrected": source["p_value"],
            "p_wilcoxon": source["wilcoxon_p_value"],
            "cohen_d": source["cohen_d"],
        }
        row["undefined_reason"] = _undefined_reason(
            {
                **row,
                "std_delta": source["std_delta"],
                "wilcoxon_p_value": source["wilcoxon_p_value"],
            }
        )
        result.append(row)
    return result


def _fold_metrics_by_key(
    path: Path, *, variant: str, arm: str | None
) -> dict[tuple[int, int, str, str], float]:
    result: dict[tuple[int, int, str, str], float] = {}
    for row in _read_csv(path):
        if row["model"] != variant or row["group"] not in {"all", "7", "21", "35"}:
            continue
        if arm is not None and row.get("arm") != arm:
            continue
        key = (int(row["seed"]), int(row["fold"]), row["group"], row["metric"])
        if key in result:
            raise ValueError(f"{path}: métrica de fold duplicada para {variant}/{arm}/{key}.")
        result[key] = float(_required_number(row["average"], f"{path}/{variant}/{key}"))
    return result


def _fold_values_by_seed(
    metrics: Mapping[tuple[int, int, str, str], float], metric: str
) -> dict[tuple[int, int], float]:
    values = {
        (seed, fold): value
        for (seed, fold, group, fold_metric), value in metrics.items()
        if group == "all" and fold_metric == metric
    }
    if not values:
        raise ValueError(f"No hay folds para la métrica primaria {metric!r}.")
    return values


def _fold_ratios(path: Path, variant: str) -> dict[tuple[int, int], float]:
    ratios: dict[tuple[int, int], float] = {}
    for row in _read_csv(path):
        if row["model"] != variant or row["arm"] != "free":
            continue
        key = (int(row["seed"]), int(row["fold"]))
        if key in ratios:
            raise ValueError(f"{path}: fold duplicado para {variant}/{key}.")
        if row["status"] != "ok":
            raise ValueError(f"{path}: fold fallido para {variant}/{key}: {row['status']}.")
        n_test = int(row["n_test"])
        n_train = int(row["n_train"]) + int(row["n_inner_val"])
        if n_test <= 0 or n_train <= 0:
            raise ValueError(f"{path}: tamaños no positivos para {variant}/{key}.")
        ratios[key] = n_test / n_train
    if not ratios:
        raise ValueError(f"{path}: no hay folds libres exitosos para {variant}.")
    return ratios


def _paired_result_row(
    *,
    dataset: str,
    variant: str,
    metric: str,
    contrast: str,
    deltas: Mapping[tuple[int, int], float],
    ratio: float,
) -> dict[str, str]:
    result: PairedComparison = paired_comparison(deltas, ratio)
    row = {
        "dataset": dataset,
        "variant": variant,
        "metric": metric,
        "contrast": contrast,
        "n_folds": str(result.n_folds),
        "n_seeds": str(result.n_seeds),
        "delta": repr(result.mean_delta),
        "ci_95_low": repr(result.ci_low),
        "ci_95_high": repr(result.ci_high),
        "t_statistic": repr(result.t_statistic),
        "degrees_of_freedom": str(result.degrees_of_freedom),
        "p_t_corrected": repr(result.p_value),
        "p_wilcoxon": repr(result.wilcoxon_p_value),
        "cohen_d": repr(result.cohen_d),
    }
    row["undefined_reason"] = _undefined_reason(
        {
            **row,
            "std_delta": repr(result.std_delta),
            "wilcoxon_p_value": row["p_wilcoxon"],
        }
    )
    return row


@dataclass(frozen=True)
class _DayOnlyDiagnostics:
    positive_seed_count: int
    n_seeds: int
    mean_delta: float
    fold_std_delta: float


def _day_only_diagnostics(
    deltas: Mapping[tuple[int, int], float],
) -> _DayOnlyDiagnostics:
    deltas_by_seed: dict[int, list[float]] = {}
    for (seed, _), delta in deltas.items():
        deltas_by_seed.setdefault(seed, []).append(delta)
    seed_means = [fmean(values) for values in deltas_by_seed.values()]
    return _DayOnlyDiagnostics(
        positive_seed_count=sum(mean > 0.0 for mean in seed_means),
        n_seeds=len(seed_means),
        mean_delta=fmean(deltas.values()),
        fold_std_delta=stdev(deltas.values()),
    )


def _day_only_statistics(
    *,
    d1_dir: Path,
    baseline_dir: Path,
) -> tuple[
    list[dict[str, str]],
    dict[str, bool],
    dict[tuple[str, str], _DayOnlyDiagnostics],
]:
    d1_fold_path = d1_dir / "fold_metrics.csv"
    baseline_fold_path = baseline_dir / "fold_metrics.csv"
    variants = sorted(
        {
            row["model"]
            for row in _read_csv(d1_fold_path)
            if row["arm"] == "free" and row["group"] == "all" and row["metric"] == "fraction_mae_pp"
        }
    )
    baseline_rows = _read_csv(baseline_fold_path)
    baseline_by_variant: dict[str, dict[tuple[int, int], float]] = {}
    for variant in variants:
        baseline_values: dict[tuple[int, int], float] = {}
        for row in baseline_rows:
            if (
                row["model"] == "day_only"
                and row["group"] == "all"
                and row["metric"] == "fraction_mae_pp"
            ):
                key = (int(row["seed"]), int(row["fold"]))
                if key in baseline_values:
                    raise ValueError(f"{baseline_fold_path}: day_only tiene clave duplicada {key}.")
                baseline_values[key] = float(
                    _required_number(row["average"], f"{baseline_fold_path}/day_only/{key}")
                )
        if not baseline_values:
            raise ValueError(f"{baseline_fold_path}: no contiene day_only para group=all.")
        baseline_by_variant[variant] = baseline_values

    result_rows: list[dict[str, str]] = []
    identical_by_variant: dict[str, bool] = {}
    diagnostics_by_comparison: dict[tuple[str, str], _DayOnlyDiagnostics] = {}
    for variant in variants:
        free_metrics = _fold_metrics_by_key(d1_fold_path, variant=variant, arm="free")
        constrained_metrics = _fold_metrics_by_key(d1_fold_path, variant=variant, arm="constrained")
        identical = bool(free_metrics) and free_metrics == constrained_metrics
        identical_by_variant[variant] = identical
        free_values = _fold_values_by_seed(free_metrics, "fraction_mae_pp")
        constrained_values = _fold_values_by_seed(constrained_metrics, "fraction_mae_pp")
        baseline_values = baseline_by_variant[variant]
        if set(free_values) != set(baseline_values):
            raise ValueError(
                f"Folds free/day_only no coinciden para {variant}: "
                f"faltan en baseline={sorted(set(free_values) - set(baseline_values))}, "
                f"sobran en baseline={sorted(set(baseline_values) - set(free_values))}."
            )
        ratios = _fold_ratios(d1_dir / "folds.csv", variant)
        if set(ratios) != set(free_values):
            raise ValueError(
                f"Folds de `folds.csv` no coinciden con `fold_metrics.csv` para {variant}."
            )
        ratio = fmean(ratios[key] for key in sorted(free_values))

        free_deltas = {key: free_values[key] - baseline_values[key] for key in free_values}
        diagnostics_by_comparison[(variant, "free − day_only")] = _day_only_diagnostics(free_deltas)
        result_rows.append(
            _paired_result_row(
                dataset="d1",
                variant=variant,
                metric="fraction_mae_pp",
                contrast="free − day_only",
                deltas=free_deltas,
                ratio=ratio,
            )
        )
        if not identical:
            if set(constrained_values) != set(baseline_values):
                raise ValueError(f"Folds constrained/day_only no coinciden para {variant}.")
            constrained_deltas = {
                key: constrained_values[key] - baseline_values[key] for key in constrained_values
            }
            diagnostics_by_comparison[(variant, "constrained − day_only")] = _day_only_diagnostics(
                constrained_deltas
            )
            result_rows.append(
                _paired_result_row(
                    dataset="d1",
                    variant=variant,
                    metric="fraction_mae_pp",
                    contrast="constrained − day_only",
                    deltas=constrained_deltas,
                    ratio=ratio,
                )
            )
    return result_rows, identical_by_variant, diagnostics_by_comparison


def _fmt_stat(value: str) -> str:
    try:
        number = float(value)
    except ValueError:
        return "—"
    return "—" if not math.isfinite(number) else f"{number:.4f}"


def _day_only_interpretation(row: Mapping[str, str]) -> tuple[str, str]:
    low, high = float(row["ci_95_low"]), float(row["ci_95_high"])
    category = delta_category(low, high, DELTA_ROPE_PP)
    effect_size = float(row["cohen_d"])
    effect_label = (
        "no definido"
        if not math.isfinite(effect_size)
        else "despreciable"
        if abs(effect_size) < 0.2
        else "pequeña"
        if abs(effect_size) < 0.5
        else "mediana"
        if abs(effect_size) < 0.8
        else "grande"
    )
    name = CATEGORIES[category - 1]
    return name, effect_label


def _render_inference_section(
    rows: Sequence[dict[str, str]],
    identical_by_variant: Mapping[str, bool],
    diagnostics_by_comparison: Mapping[tuple[str, str], _DayOnlyDiagnostics],
) -> str:
    constrained_free = [row for row in rows if row["contrast"] == "constrained − free"]
    day_only = [
        row for row in rows if row["dataset"] == "d1" and row["contrast"] == "free − day_only"
    ]
    constrained_day_only = [
        row
        for row in rows
        if row["dataset"] == "d1" and row["contrast"] == "constrained − day_only"
    ]
    identical_names = sorted(
        variant for variant, identical in identical_by_variant.items() if identical
    )
    identical_text = ", ".join(f"`{variant}`" for variant in identical_names) or "ninguna variante"
    lines = [
        "## Inferencia pareada (A73-P3)",
        "",
        "La tabla `paired_statistics.csv` conserva los estadísticos calculados por fold.",
        "En estos datos, `constrained − free` tiene Δ = 0 y su IC es [0, 0]; los estadísticos",
        "no definidos se muestran como «—» con el motivo en la tabla, nunca como p = 1.",
        "",
        "### constrained − free",
        "",
        (
            "| Conjunto | Variante | Métrica | Δ | IC 95 % | t corregido | gl | p (t) | "
            "p (Wilcoxon) | d | Motivo |"
        ),
        "|---|---|---|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in constrained_free:
        interval = f"[{_fmt_stat(row['ci_95_low'])}, {_fmt_stat(row['ci_95_high'])}]"
        lines.append(
            "| "
            + " | ".join(
                (
                    row["dataset"],
                    row["variant"],
                    row["metric"],
                    _fmt_stat(row["delta"]),
                    interval,
                    _fmt_stat(row["t_statistic"]),
                    row["degrees_of_freedom"],
                    _fmt_stat(row["p_t_corrected"]),
                    _fmt_stat(row["p_wilcoxon"]),
                    _fmt_stat(row["cohen_d"]),
                    row["undefined_reason"] or "—",
                )
            )
            + " |"
        )

    lines.extend(
        (
            "",
            "### Comparación obligatoria free − day_only (D1)",
            "",
            "Se usa Δ = MAE(free) − MAE(day_only), por fold. Negativo favorece a la GNN.",
            f"El contraste `constrained − day_only` no se duplica para {identical_text}, cuyos",
            "brazos coinciden en todos los registros de `fold_metrics.csv`; el código verifica",
            "esa igualdad. Si una variante no es idéntica, se calculan y presentan",
            "ambos contrastes.",
            "",
            (
                "| Variante | Contraste | n | Δ (pp) | IC 95 % (pp) | t corregido | gl | "
                "p (t) | p (Wilcoxon) | Semillas con Δ > 0 | d | Categoría §4.3/Tabla 4 | "
                "d: magnitud |"
            ),
            "|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---|---|",
        )
    )
    for row in (*day_only, *constrained_day_only):
        category, effect_label = _day_only_interpretation(row)
        diagnostics = diagnostics_by_comparison[(row["variant"], row["contrast"])]
        interval = f"[{_fmt_stat(row['ci_95_low'])}, {_fmt_stat(row['ci_95_high'])}]"
        lines.append(
            "| "
            + " | ".join(
                (
                    row["variant"],
                    row["contrast"],
                    row["n_folds"],
                    _fmt_stat(row["delta"]),
                    interval,
                    _fmt_stat(row["t_statistic"]),
                    row["degrees_of_freedom"],
                    _fmt_stat(row["p_t_corrected"]),
                    _fmt_stat(row["p_wilcoxon"]),
                    f"{diagnostics.positive_seed_count}/{diagnostics.n_seeds}",
                    _fmt_stat(row["cohen_d"]),
                    category,
                    effect_label,
                )
            )
            + " |"
        )

    for row in day_only:
        diagnostics = diagnostics_by_comparison[(row["variant"], row["contrast"])]
        try:
            wilcoxon_p = float(row["p_wilcoxon"])
            ci_low = float(row["ci_95_low"])
            ci_high = float(row["ci_95_high"])
        except ValueError:
            continue
        if not (math.isfinite(wilcoxon_p) and wilcoxon_p < 0.05 and ci_low <= 0.0 <= ci_high):
            continue

        positive_count = diagnostics.positive_seed_count
        negative_count = diagnostics.n_seeds - positive_count
        if positive_count > negative_count:
            direction = (
                f"Δ > 0 en {positive_count}/{diagnostics.n_seeds} semillas, lo que muestra "
                "una desventaja consistente frente a `day_only`."
            )
        elif negative_count > positive_count:
            direction = (
                f"Δ < 0 en {negative_count}/{diagnostics.n_seeds} semillas; el signo favorece "
                "a la GNN, no indica una desventaja frente a `day_only`."
            )
        else:
            direction = (
                f"Δ > 0 en {positive_count}/{diagnostics.n_seeds} semillas; los signos no "
                "muestran una dirección mayoritaria."
            )
        mean_abs = abs(diagnostics.mean_delta)
        fold_std = diagnostics.fold_std_delta
        if mean_abs < fold_std:
            magnitude = (
                f"La magnitud media |Δ| = {mean_abs:.4f} pp es menor que la desviación "
                f"estándar entre folds (sΔ = {fold_std:.4f} pp), pequeña frente a esa "
                "variabilidad."
            )
        else:
            magnitude = (
                f"La magnitud media |Δ| = {mean_abs:.4f} pp no es menor que la desviación "
                f"estándar entre folds (sΔ = {fold_std:.4f} pp)."
            )
        category, _ = _day_only_interpretation(row)
        lines.extend(
            (
                "",
                f"**{row['variant']} — lectura de Wilcoxon.** {direction} {magnitude}",
                f"Aunque Wilcoxon de medias por semilla da p = {wilcoxon_p:.4f} (< 0,05), "
                "el IC del t "
                "corregido incluye 0. Wilcoxon es una prueba anticonservadora de sensibilidad: "
                f"esto no cambia la categoría «{category}» ni la conclusión de §6.3 y no se "
                "presenta como superioridad.",
            )
        )

    if not day_only:
        raise ValueError("No hay comparaciones D1 free − day_only para escribir el reporte.")
    if not any(float(row["ci_95_high"]) < 0.0 for row in day_only):
        lines.extend(
            (
                "",
                "Con estos datos, ninguna variante satisface U < 0; por tanto, las GNN no",
                "demuestran aprender más que la edad del animal según la regla de §6.3.",
            )
        )
    nonconclusive = [
        row
        for row in day_only
        if float(row["ci_95_low"]) <= DELTA_ROPE_PP <= float(row["ci_95_high"])
    ]
    if nonconclusive:
        names = ", ".join(f"`{row['variant']}`" for row in nonconclusive)
        lines.append(
            f"El IC también alcanza +δ = {DELTA_ROPE_PP:.1f} pp para {names}; "
            "esas comparaciones son «No concluyentes» según la Tabla 4."
        )
    else:
        lines.append(
            "Ningún IC de free − day_only alcanza +δ; las categorías de equivalencia/no "
            "inferioridad se muestran en la tabla y no prueban equivalencia poblacional."
        )
    lines.extend(
        (
            "",
            f"El margen δ = {DELTA_ROPE_PP:.1f} pp es provisional de Investigación (P-02), no un",
            "umbral biológico consensuado. §4.3 distingue significancia de relevancia práctica:",
            "se informa la categoría determinada por el IC y δ, además de la magnitud",
            "de d de Cohen",
            "(<0,2 despreciable; <0,5 pequeña; <0,8 mediana; en otro caso grande). No se usa un",
            "p < 0,05 aislado como criterio de superioridad; §6.3 requiere U < 0 y U < −δ para",
            "«supera holgadamente». El p de Wilcoxon es una sensibilidad anticonservadora.",
            "No se aplicó corrección por multiplicidad a las tres comparaciones",
            "free − day_only; se",
            "reportan por variante y no como una prueba familiar conjunta.",
            "",
            "La comparación contra `day_only` **no aplica** a la cohorte sintética: no hay allí",
            "baseline versionado y no se fabricó uno.",
        )
    )
    return "\n".join(lines)


def _write_report(
    path: Path,
    *,
    rows: Sequence[dict[str, str]],
    canonical_digest: str,
    baseline_models: Sequence[str],
    paired_statistics: Sequence[dict[str, str]],
    identical_by_variant: Mapping[str, bool],
    day_only_diagnostics: Mapping[tuple[str, str], _DayOnlyDiagnostics],
) -> None:
    main_rows = [row for row in rows if row["group"] == "all"]
    day_rows = [row for row in rows if row["dataset"] == "d1" and row["group"] in {"7", "21", "35"}]
    d1_identical, d1_zero_vr = _dataset_reading(rows, "d1", ("all", "7", "21", "35"))
    synthetic_identical, synthetic_zero_vr = _dataset_reading(rows, "synthetic", ("all",))
    reference_names = ", ".join(f"`{model}`" for model in baseline_models) or "ninguno"
    main_text = "\n".join(_render_table(main_rows))
    day_text = "\n".join(_render_table(day_rows))
    readings = "\n".join(
        (
            _dataset_reading_text("D1", d1_identical, d1_zero_vr),
            _dataset_reading_text("Cohorte sintética", synthetic_identical, synthetic_zero_vr),
        )
    )
    if d1_zero_vr and synthetic_zero_vr:
        activation = (
            "La restricción no se activó en ninguno de los dos conjuntos, así que esta "
            "comparación no la pone a prueba."
        )
    else:
        active_datasets = [
            label
            for label, zero_vr in (
                ("D1", d1_zero_vr),
                ("cohorte sintética", synthetic_zero_vr),
            )
            if not zero_vr
        ]
        activation = "Los datos muestran VR distinto de cero en " + ", ".join(active_datasets) + "."
    references_status = (
        f"Comparables con D1: {reference_names}. Hash canónico verificado: `{canonical_digest}`."
    )
    report = f"""# Comparación de modelos con y sin restricciones

Tabla de métricas para D1 y la cohorte sintética, generada desde los CSV versionados.
Los valores se presentan como media ± desviación estándar entre folds (`_mean` y `_std`);
no se usa `_seed_std`. Las métricas predictivas son macro-promedios (`average`). `FR conjunta`
es la factibilidad conjunta en porcentaje; `VR` y `FR` son porcentajes. `VWM` es
el máximo de `worst_case_magnitude` (columna `max`) y `VMM` es `mean_magnitude`, ambos de
`violations_summary.csv`; VWM representa el peor caso de todos los folds. La tabla no recalcula
violaciones desde predicciones. Las restricciones estructurales se omiten: sus métricas valen 0
por construcción en estos modelos composicionales.

## Resultados principales

{main_text}

## D1 por día de muestreo

Desglose de D1 para los días 7, 21 y 35, según el protocolo §6.1.

{day_text}

Advertencia: el R² por día no es interpretable porque cada fold tiene pocos animales por día y
muy poca varianza en el objetivo. Esto produce valores extremos (por ejemplo, el día 7); se
conservan sin modificación, pero no deben interpretarse como capacidad predictiva por día.

## Referencias

Las referencias `dummy_mean` y `day_only` proceden de
`reports/baselines/d1_composition/metrics.csv`;
se incluyen solo para D1. {references_status} La cohorte sintética no tiene referencias baseline:
**no aplica**; no se han fabricado valores.

## Lectura

D-06 §6 preveía que el efecto solo podía observarse en la cohorte sintética o en predicciones
fuera de rango. Según los datos:

{readings}

{activation} En D1, «Factibilidad sin costo» significa que no costó nada porque no hizo nada.
Esta comparación no aporta evidencia de beneficio bioquímico. La cohorte marcada como `synthetic`
es sintética y se interpreta por separado de D1. Las métricas son descriptivas y no sustituyen
la inferencia pareada de A73-P3.

{_render_inference_section(paired_statistics, identical_by_variant, day_only_diagnostics)}
"""
    path.write_text(report, encoding="utf-8", newline="\n")


def build_constraints_comparison(
    *,
    d1_dir: Path,
    synthetic_dir: Path,
    baseline_dir: Path,
    plan_path: Path,
    output_dir: Path,
) -> tuple[Path, Path, Path]:
    """Construye resultados descriptivos e inferencia pareada desde fuentes versionadas."""
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

    paired_statistics = _paired_csv_statistics(d1_dir / "paired.csv", "d1")
    paired_statistics.extend(_paired_csv_statistics(synthetic_dir / "paired.csv", "synthetic"))
    day_only_rows, identical_by_variant, day_only_diagnostics = _day_only_statistics(
        d1_dir=d1_dir,
        baseline_dir=baseline_dir,
    )
    paired_statistics.extend(day_only_rows)
    paired_statistics.sort(
        key=lambda row: (
            row["dataset"],
            row["variant"],
            row["contrast"],
            row["metric"],
        )
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "comparison.csv"
    report_path = output_dir / "report.md"
    paired_statistics_path = output_dir / "paired_statistics.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=_OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    with paired_statistics_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=_PAIRED_STATISTIC_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(paired_statistics)
    baseline_models = sorted({row["model"] for row in baseline_rows if row["group"] == "all"})
    _write_report(
        report_path,
        rows=rows,
        canonical_digest=canonical_digest,
        baseline_models=baseline_models,
        paired_statistics=paired_statistics,
        identical_by_variant=identical_by_variant,
        day_only_diagnostics=day_only_diagnostics,
    )
    return csv_path, report_path, paired_statistics_path


__all__ = ["D06_CONSTRAINT", "build_constraints_comparison"]
