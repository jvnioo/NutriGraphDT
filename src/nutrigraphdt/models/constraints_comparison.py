"""Generación y verificación de la comparación reproducible A73-P2/P3/P4."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
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
_D1_COHORT_CONFIG: Final = Path("configs/cohorts/d1_holofood.json")
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


def _resolve_manifest_path(value: str, repo_root: Path) -> Path:
    normalized = value.replace("\\", "/")
    direct = Path(value)
    if not direct.is_absolute():
        return repo_root / direct
    if direct.exists():
        return direct
    for marker in ("configs/", "reports/"):
        offset = normalized.find(marker)
        if offset >= 0:
            return repo_root.joinpath(*PurePosixPath(normalized[offset:]).parts)
    raise ValueError(f"No se puede resolver la ruta de run.json dentro del repositorio: {value!r}.")


def _verify_manifest_hash(
    *,
    run: Mapping[str, object],
    label: str,
    path_key: str,
    hash_key: str,
    repo_root: Path,
    verified: list[str],
    unverifiable: list[str],
    fallback_path: Path | None = None,
) -> Path | None:
    declared_hash = run.get(hash_key)
    raw_path = run.get(path_key)
    if not isinstance(declared_hash, str) or not declared_hash:
        unverifiable.append(f"{label}: {hash_key} no está registrado.")
        return None
    if isinstance(raw_path, str) and raw_path:
        path = _resolve_manifest_path(raw_path, repo_root)
    elif fallback_path is not None:
        path = fallback_path
        unverifiable.append(
            f"{label}: run.json no registra {path_key}; se usa la ruta de entrada indicada."
        )
    else:
        unverifiable.append(f"{label}: {path_key} no está registrado para verificar {hash_key}.")
        return None
    if not path.is_file():
        raise ValueError(f"{label}: no existe el archivo declarado por run.json: {path}.")
    content = path.read_bytes()
    accepted_hashes = {
        hashlib.sha256(content).hexdigest(),
        hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest(),
    }
    if declared_hash not in accepted_hashes:
        raise ValueError(
            f"{label}: {hash_key} no coincide con {path} (hash registrado {declared_hash})."
        )
    verified.append(f"{label}: {hash_key} coincide con {path.name} (CRLF/LF normalizado).")
    return path


def _verify_source_manifest(
    *,
    source_dir: Path,
    label: str,
    repo_root: Path,
    fallback_plan: Path | None,
    verify_evaluation_folds: bool,
    verified: list[str],
    unverifiable: list[str],
) -> dict[str, object]:
    run_path = source_dir / "run.json"
    run = _read_json(run_path)
    raw_plan_path = run.get("plan")
    plan_path: Path | None = fallback_plan
    if isinstance(raw_plan_path, str) and raw_plan_path:
        if fallback_plan is not None:
            plan_path = fallback_plan
            if Path(raw_plan_path.replace("\\", "/")).name != fallback_plan.name:
                raise ValueError(
                    f"{label}: el plan registrado ({raw_plan_path}) no coincide con "
                    f"la entrada {fallback_plan}."
                )
        else:
            plan_path = _resolve_manifest_path(raw_plan_path, repo_root)
    else:
        unverifiable.append(f"{label}: run.json no registra la ruta del plan.")

    plan: dict[str, object] | None = None
    if plan_path is None:
        unverifiable.append(f"{label}: no se puede resolver el plan desde run.json.")
    elif not plan_path.is_file():
        raise ValueError(f"{label}: no existe el plan esperado: {plan_path}.")
    else:
        plan = _read_json(plan_path)
        plan_bytes = plan_path.read_bytes()
        raw_hash = run.get("plan_sha256")
        raw_hashes = {
            hashlib.sha256(plan_bytes).hexdigest(),
            hashlib.sha256(plan_bytes.replace(b"\r\n", b"\n")).hexdigest(),
        }
        if isinstance(raw_hash, str) and raw_hash:
            if raw_hash not in raw_hashes:
                raise ValueError(f"{label}: plan_sha256 no coincide con {plan_path}.")
            verified.append(f"{label}: plan_sha256 coincide (CRLF/LF normalizado).")
        else:
            unverifiable.append(f"{label}: plan_sha256 no está registrado.")
        canonical_hash = run.get("plan_canonical_sha256")
        if isinstance(canonical_hash, str) and canonical_hash:
            computed_canonical = split_content_sha256(plan)
            if canonical_hash != computed_canonical:
                raise ValueError(f"{label}: plan_canonical_sha256 no coincide con {plan_path}.")
            verified.append(f"{label}: plan_canonical_sha256 coincide.")
        else:
            unverifiable.append(f"{label}: plan_canonical_sha256 no está registrado.")

    for path_key, hash_key in (
        ("selection", "selection_sha256"),
        ("sweep_config", "sweep_config_sha256"),
    ):
        if path_key in run or hash_key in run:
            _verify_manifest_hash(
                run=run,
                label=label,
                path_key=path_key,
                hash_key=hash_key,
                repo_root=repo_root,
                verified=verified,
                unverifiable=unverifiable,
            )

    cohort_hash = run.get("cohort_config_sha256")
    if isinstance(cohort_hash, str) and cohort_hash:
        cohort_path = repo_root / _D1_COHORT_CONFIG
        if not cohort_path.is_file():
            raise ValueError(
                f"{label}: no se encuentra la configuración de cohorte del evaluador: "
                f"{cohort_path}."
            )
        actual_hashes = {
            hashlib.sha256(cohort_path.read_bytes()).hexdigest(),
            hashlib.sha256(cohort_path.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        }
        if cohort_hash not in actual_hashes:
            raise ValueError(f"{label}: cohort_config_sha256 no coincide con {cohort_path}.")
        verified.append(
            f"{label}: cohort_config_sha256 coincide con la ruta COHORT_CONFIG del evaluador."
        )
    else:
        unverifiable.append(f"{label}: cohort_config_sha256 es nulo o no está registrado.")

    if plan is not None:
        dataset_id = run.get("dataset_id")
        if dataset_id is not None and dataset_id != plan.get("dataset_id"):
            raise ValueError(f"{label}: dataset_id en run.json y plan no coincide.")
        run_cohort = run.get("cohort")
        plan_cohort = plan.get("cohort")
        if isinstance(run_cohort, Mapping) and isinstance(plan_cohort, Mapping):
            common_fields = set(run_cohort) & set(plan_cohort)
            mismatches = {
                field: (run_cohort[field], plan_cohort[field])
                for field in common_fields
                if run_cohort[field] != plan_cohort[field]
            }
            if mismatches:
                raise ValueError(
                    f"{label}: metadatos de cohorte no coinciden con el plan: {mismatches}."
                )
            if common_fields:
                verified.append(
                    f"{label}: cohorte coincide en los campos comunes con el plan "
                    f"({', '.join(sorted(common_fields))})."
                )
            else:
                unverifiable.append(f"{label}: run.json y plan no comparten campos de cohorte.")
        else:
            unverifiable.append(f"{label}: cohorte no está disponible en run.json o en el plan.")

        plan_seeds = plan.get("seeds")
        run_seeds = run.get("seeds")
        if isinstance(plan_seeds, list) and all(isinstance(seed, int) for seed in plan_seeds):
            if isinstance(run_seeds, list) and all(isinstance(seed, int) for seed in run_seeds):
                if run_seeds != plan_seeds:
                    raise ValueError(f"{label}: semillas de run.json y plan no coinciden.")
                verified.append(f"{label}: semillas de run.json coinciden con el plan.")
            else:
                unverifiable.append(f"{label}: semillas no están registradas en run.json.")
        else:
            unverifiable.append(f"{label}: semillas no están disponibles en el plan.")

        plan_k = plan.get("k")
        if isinstance(plan_k, int):
            if isinstance(run.get("k"), int):
                if run["k"] != plan_k:
                    raise ValueError(f"{label}: k de run.json no coincide con el plan.")
                verified.append(f"{label}: k={plan_k} coincide entre run.json y el plan.")
            else:
                unverifiable.append(
                    f"{label}: k no está registrado en run.json (k={plan_k} está en el plan)."
                )
        else:
            unverifiable.append(f"{label}: k no está registrado en el plan.")

    git_info = run.get("git")
    commit = git_info.get("commit") if isinstance(git_info, Mapping) else None
    if isinstance(commit, str) and commit:
        unverifiable.append(
            f"{label}: commit {commit} está registrado, pero no hay una columna de commit "
            "en los CSV de comparación con la que contrastarlo."
        )
    else:
        unverifiable.append(f"{label}: commit no está registrado en run.json.")

    if verify_evaluation_folds:
        if plan is None:
            unverifiable.append(f"{label}: no se pudieron verificar folds sin un plan resoluble.")
        else:
            _verify_evaluation_folds(
                source_dir=source_dir,
                label=label,
                run=run,
                plan=plan,
                verified=verified,
                unverifiable=unverifiable,
            )
    else:
        _verify_baseline_folds(source_dir, label, plan, verified, unverifiable)

    return run


def _verify_evaluation_folds(
    *,
    source_dir: Path,
    label: str,
    run: Mapping[str, object],
    plan: Mapping[str, object],
    verified: list[str],
    unverifiable: list[str],
) -> None:
    folds_path = source_dir / "folds.csv"
    fold_metrics_path = source_dir / "fold_metrics.csv"
    if not folds_path.is_file() or not fold_metrics_path.is_file():
        raise ValueError(f"{label}: faltan folds.csv o fold_metrics.csv.")
    fold_rows = _read_csv(folds_path)
    metric_rows = _read_csv(fold_metrics_path)
    key_fields = ("model", "arm", "seed", "fold")
    fold_index = _index_unique(fold_rows, key_fields, folds_path)
    declared_variants = run.get("variants")
    declared_arms = run.get("arms")
    plan_seeds = plan.get("seeds")
    plan_k = plan.get("k")
    if (
        not isinstance(declared_variants, list)
        or not all(isinstance(variant, str) for variant in declared_variants)
        or not isinstance(declared_arms, list)
        or not all(isinstance(arm, str) for arm in declared_arms)
    ):
        unverifiable.append(f"{label}: variants/arms no están registrados para validar folds.")
    elif isinstance(plan_seeds, list) and isinstance(plan_k, int):
        expected = {
            (variant, arm, str(seed), str(fold))
            for variant in declared_variants
            for arm in declared_arms
            for seed in plan_seeds
            for fold in range(plan_k)
        }
        actual = set(fold_index)
        if actual != expected:
            raise ValueError(
                f"{label}: folds.csv no cubre las combinaciones previstas; "
                f"faltan={sorted(expected - actual)[:5]}, sobran={sorted(actual - expected)[:5]}."
            )
        verified.append(
            f"{label}: folds.csv cubre {len(expected)} combinaciones de variantes, brazos, "
            "semillas y folds del plan."
        )
    else:
        unverifiable.append(f"{label}: cobertura de folds no verificable sin semillas y k.")

    status_counts = Counter(row["status"] for row in fold_rows)
    unknown_statuses = set(status_counts) - {"ok", "failed"}
    if unknown_statuses:
        raise ValueError(f"{label}: estados de fold no reconocidos: {sorted(unknown_statuses)}.")
    for field, status in (("folds_ok", "ok"), ("folds_failed", "failed")):
        declared_count = run.get(field)
        if isinstance(declared_count, int):
            if declared_count != status_counts.get(status, 0):
                raise ValueError(
                    f"{label}: {field}={declared_count} en run.json pero folds.csv tiene "
                    f"{status_counts.get(status, 0)} filas {status!r}."
                )
            verified.append(f"{label}: {field} coincide con folds.csv.")
        else:
            unverifiable.append(f"{label}: {field} no está registrado en run.json.")

    train_seed_base = run.get("train_seed_base")
    if isinstance(train_seed_base, int):
        train_seeds_by_fold: dict[tuple[str, str, str], set[str]] = {}
        for key, row in fold_index.items():
            model, _, seed, fold = key
            expected_train_seed = train_seed_base + int(seed) * 100 + int(fold)
            actual_train_seed = int(
                _required_integer(
                    row.get("train_seed"),
                    f"{folds_path}/{key}/train_seed",
                )
            )
            if actual_train_seed != expected_train_seed:
                raise ValueError(
                    f"{label}: train_seed={actual_train_seed} para {key}, "
                    f"se esperaba {expected_train_seed}."
                )
            train_seeds_by_fold.setdefault((model, seed, fold), set()).add(str(actual_train_seed))
        if any(len(values) != 1 for values in train_seeds_by_fold.values()):
            raise ValueError(f"{label}: las semillas de entrenamiento no están pareadas por fold.")
        verified.append(f"{label}: train_seed por fold coincide y está pareada entre brazos.")
    else:
        unverifiable.append(f"{label}: train_seed_base no está registrado en run.json.")

    lambdas = run.get("lambdas")
    arms = run.get("arms")
    if isinstance(lambdas, Mapping) and isinstance(arms, list):
        complete_lambda_metadata = True
        for key, fold_row in fold_index.items():
            model, arm, _, _ = key
            expected_lambda: float | None = None
            if arm == "free":
                expected_lambda = 0.0
            elif arm == "constrained":
                raw_lambda = lambdas.get(model)
                if isinstance(raw_lambda, (int, float)):
                    expected_lambda = float(raw_lambda)
                else:
                    complete_lambda_metadata = False
            if expected_lambda is None:
                continue
            actual_lambda = float(
                _required_number(fold_row.get("constraint_lambda"), f"{folds_path}/{key}/lambda")
            )
            if actual_lambda != expected_lambda:
                raise ValueError(
                    f"{label}: λ de {model}/{arm} en folds.csv es {actual_lambda}, "
                    f"run.json registra {expected_lambda}."
                )
        if complete_lambda_metadata:
            verified.append(f"{label}: λ efectiva por brazo coincide con run.json.")
        else:
            unverifiable.append(f"{label}: falta λ registrada para al menos una variante.")
    else:
        unverifiable.append(
            f"{label}: lambdas/arms no están registrados para verificar λ por brazo."
        )

    for row in metric_rows:
        key = tuple(row[field] for field in key_fields)
        matching_fold = fold_index.get(key)
        if matching_fold is None:
            raise ValueError(
                f"{label}: fold_metrics.csv contiene un fold ausente en folds.csv: {key}."
            )
        if row.get("constraint_lambda") != matching_fold.get("constraint_lambda"):
            raise ValueError(f"{label}: λ difiere entre folds.csv y fold_metrics.csv para {key}.")
    verified.append(f"{label}: fold_metrics.csv referencia folds y λ de folds.csv.")


def _verify_baseline_folds(
    source_dir: Path,
    label: str,
    plan: Mapping[str, object] | None,
    verified: list[str],
    unverifiable: list[str],
) -> None:
    path = source_dir / "fold_metrics.csv"
    rows = _read_csv(path)
    key_rows = [
        (int(row["seed"]), int(row["fold"]))
        for row in rows
        if row["model"] == "day_only"
        and row["group"] == "all"
        and row["metric"] == "fraction_mae_pp"
    ]
    keys = set(key_rows)
    if len(key_rows) != len(keys):
        raise ValueError(f"{label}: hay claves duplicadas de fold day_only en {path}.")
    seeds = plan.get("seeds") if plan is not None else None
    k = plan.get("k") if plan is not None else None
    if (
        not isinstance(seeds, list)
        or not all(isinstance(seed, int) for seed in seeds)
        or not isinstance(k, int)
    ):
        unverifiable.append(
            f"{label}: cobertura de folds de day_only no verificable sin semillas/k."
        )
        return
    expected = {(seed, fold) for seed in seeds for fold in range(k)}
    if keys != expected:
        raise ValueError(
            f"{label}: folds day_only no coinciden con el plan; "
            f"faltan={sorted(expected - keys)[:5]}, sobran={sorted(keys - expected)[:5]}."
        )
    verified.append(f"{label}: folds de day_only coinciden con semillas y k del plan D1.")


def _compare_csv_cells(
    actual_path: Path,
    expected_path: Path,
    *,
    label: str,
    key_columns: tuple[str, ...],
) -> str:
    actual_rows = _read_csv(actual_path)
    expected_rows = _read_csv(expected_path)
    with actual_path.open(encoding="utf-8", newline="") as stream:
        actual_fields = csv.DictReader(stream).fieldnames
    with expected_path.open(encoding="utf-8", newline="") as stream:
        expected_fields = csv.DictReader(stream).fieldnames
    if actual_fields != expected_fields:
        raise ValueError(
            f"{label}: cabecera distinta; esperada={expected_fields!r}, "
            f"encontrada={actual_fields!r}."
        )
    actual_index = _index_unique(actual_rows, key_columns, actual_path)
    expected_index = _index_unique(expected_rows, key_columns, expected_path)
    missing = sorted(set(expected_index) - set(actual_index))
    extra = sorted(set(actual_index) - set(expected_index))
    if missing or extra:
        raise ValueError(f"{label}: filas distintas; faltan={missing[:5]}, sobran={extra[:5]}.")
    for key in sorted(expected_index):
        expected_row, actual_row = expected_index[key], actual_index[key]
        for column in expected_fields or ():
            if expected_row[column] != actual_row[column]:
                raise ValueError(
                    f"{label}: celda no coincide en fila {key!r}, columna {column!r}; "
                    f"esperado={expected_row[column]!r}, encontrado={actual_row[column]!r}."
                )
    return f"{label}: {len(actual_rows)} filas; todas las celdas coinciden."


def verify_constraints_comparison(
    *,
    d1_dir: Path,
    synthetic_dir: Path,
    baseline_dir: Path,
    plan_path: Path,
    output_dir: Path,
    repo_root: Path,
) -> tuple[list[str], list[str]]:
    """Verifica las tablas existentes sin sobrescribirlas y reporta metadatos no verificables."""
    verified: list[str] = []
    unverifiable: list[str] = []
    d1_run = _verify_source_manifest(
        source_dir=d1_dir,
        label="D1",
        repo_root=repo_root,
        fallback_plan=plan_path,
        verify_evaluation_folds=True,
        verified=verified,
        unverifiable=unverifiable,
    )
    _verify_source_manifest(
        source_dir=synthetic_dir,
        label="Sintético",
        repo_root=repo_root,
        fallback_plan=None,
        verify_evaluation_folds=True,
        verified=verified,
        unverifiable=unverifiable,
    )
    d1_cohort = d1_run.get("cohort")
    baseline_run = _verify_source_manifest(
        source_dir=baseline_dir,
        label="Baseline D1",
        repo_root=repo_root,
        fallback_plan=plan_path,
        verify_evaluation_folds=False,
        verified=verified,
        unverifiable=unverifiable,
    )
    baseline_cohort = baseline_run.get("cohort")
    if isinstance(d1_cohort, Mapping) and isinstance(baseline_cohort, Mapping):
        shared = set(d1_cohort) & set(baseline_cohort)
        if not shared:
            unverifiable.append("Baseline D1: sin campos comunes para contrastar cohorte con D1.")
        elif any(d1_cohort[field] != baseline_cohort[field] for field in shared):
            raise ValueError("Baseline D1: cohorte no coincide con el manifiesto D1.")
        else:
            verified.append("Baseline D1: cohorte coincide con el manifiesto de D1.")

    with tempfile.TemporaryDirectory(prefix="nutrigraphdt-constraints-verify-") as directory:
        expected_dir = Path(directory)
        expected_comparison, _, expected_statistics = build_constraints_comparison(
            d1_dir=d1_dir,
            synthetic_dir=synthetic_dir,
            baseline_dir=baseline_dir,
            plan_path=plan_path,
            output_dir=expected_dir,
        )
        verified.append(
            _compare_csv_cells(
                output_dir / "comparison.csv",
                expected_comparison,
                label="comparison.csv",
                key_columns=("dataset", "model", "arm", "group"),
            )
        )
        verified.append(
            _compare_csv_cells(
                output_dir / "paired_statistics.csv",
                expected_statistics,
                label="paired_statistics.csv",
                key_columns=("dataset", "variant", "metric", "contrast"),
            )
        )
    return verified, unverifiable


__all__ = [
    "D06_CONSTRAINT",
    "build_constraints_comparison",
    "verify_constraints_comparison",
]
