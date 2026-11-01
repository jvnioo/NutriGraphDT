"""Evaluación pareada con y sin restricciones en D1 y en la cohorte sintética (A68-P2, #185).

Entrena cada variante GNN en todos los folds del plan versionado con dos brazos pareados (mismos
folds, mismas semillas de entrenamiento; protocolo A55-P1 §1.3):

- `free` ($M_0$): λ = 0;
- `constrained` ($M_C$): la λ que eligió el barrido de #178 para la variante
  (`reports/constraints/lambda_sweep/<dataset>/selection.json`), con los términos de su
  configuración (`configs/constraints/lambda_sweep_<dataset>.json`).

Cada fold registra las violaciones de todas las restricciones del catálogo por época y en su test
(#179) y guarda su corrida con checkpoint (#180). Escribe en `--output` (por defecto
`reports/constraints/<dataset>/`) los artefactos del protocolo §8:

- `report.md`: método, métricas globales y por día de cada brazo, violaciones, comparación
  pareada (Δ, IC del t corregido, p, Wilcoxon y d) y advertencias;
- `metrics.csv`: métricas de D-03 agregadas por variante, brazo, grupo y métrica;
- `fold_metrics.csv`: una fila por semilla, fold, variante, brazo, grupo y métrica;
- `violations.csv`: violaciones del test por variante, brazo, fold y restricción;
  `epoch_violations.csv`: las de cada época; `violations_summary.csv`: el agregado;
- `paired.csv`: comparación pareada `constrained − free` por variante y métrica;
- `folds.csv`: estado, semilla de entrenamiento, `run_id` y tamaños de cada fold;
- `predictions.csv`: `(z_1, z_2, ln T)` de cada animal de test;
- `run.json`: procedencia (commit, SHA-256 del plan, de la cohorte y de la selección), versiones,
  entorno, semillas y duración.

Uso:
    python scripts/evaluate_constraints.py --dataset synthetic --device cuda
    python scripts/evaluate_constraints.py --dataset d1 --device cuda

Requiere los extras `graph` y `baselines`. Código de salida: `0` si escribió el reporte; `2` si
faltan datos, la selección de λ o algún fold falló en los dos brazos.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from nutrigraphdt.constraints import CONSTRAINTS_CONTRACT_VERSION, constraint_catalog
from nutrigraphdt.models.composition import COMPOSITIONAL_TARGET_VERSION
from nutrigraphdt.models.cross_validation import aggregate_fold_reports, fold_table
from nutrigraphdt.models.gnn import load_model_config
from nutrigraphdt.models.metrics import EvaluationReport, MetricRow
from nutrigraphdt.models.paired_comparison import paired_comparison
from nutrigraphdt.models.training.compositional import (
    TEST_SUBSET,
    VIOLATION_LOG_COLUMNS,
    FoldEvaluation,
    ViolationAggregate,
    aggregate_violation_log,
    run_compositional_fold,
)
from nutrigraphdt.models.training.compositional_tracking import plan_content_sha256
from nutrigraphdt.models.training.config import TrainingConfig, load_training_config
from nutrigraphdt.models.training.cv_inputs import (
    CVInputs,
    load_d1_cv_inputs,
    load_synthetic_cv_inputs,
)
from nutrigraphdt.models.training.lambda_sweep import load_lambda_sweep_config
from nutrigraphdt.models.training.tracking import environment_info, git_info

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASETS = ("d1", "synthetic")
ARMS = ("free", "constrained")
DEFAULT_SOURCES = REPO_ROOT / "configs" / "sources.json"
DEFAULT_GRAPHS = REPO_ROOT / "artifacts" / "graphs" / "D1_holofood"
DEFAULT_TRAINING_CONFIG = REPO_ROOT / "configs" / "training" / "default.json"
DEFAULT_MODEL_CONFIGS = REPO_ROOT / "configs" / "models"
COHORT_CONFIG = REPO_ROOT / "configs" / "cohorts" / "d1_holofood.json"
BASELINE_METRICS = REPO_ROOT / "reports" / "baselines" / "d1_composition" / "metrics.csv"
PLANS = {
    "d1": REPO_ROOT / "configs" / "splits" / "d1_holofood_cv.json",
    "synthetic": REPO_ROOT / "configs" / "splits" / "synthetic_cohort_cv.json",
}
PAIRED_METRICS = ("fraction_mae_pp", "fraction_r2", "log_total_mae", "reconstructed_mae")
"""Métricas de D-03 (grupo `all`) comparadas por fold; la primaria del protocolo es la primera."""

FOLD_HEADER = ["seed", "fold", "model", "arm", "constraint_lambda"]
METRIC_COLUMNS = [
    "split",
    "group",
    "metric",
    "acetate",
    "propionate",
    "butyrate",
    "log_total",
    "average",
]
FOLDS_HEADER = [
    *FOLD_HEADER,
    "train_seed",
    "run_id",
    "status",
    "best_epoch",
    "epochs_run",
    "n_train",
    "n_inner_val",
    "n_test",
    "error",
]
VIOLATIONS_HEADER = [*FOLD_HEADER, *VIOLATION_LOG_COLUMNS]
PREDICTIONS_HEADER = [
    "sample_id",
    "seed",
    "fold",
    "model",
    "arm",
    "sampling_day",
    "z1",
    "z2",
    "log_total",
]

EXIT_OK = 0
EXIT_INPUT = 2


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(REPO_ROOT).as_posix()
        if resolved.is_relative_to(REPO_ROOT)
        else path.as_posix()
    )


def _append(path: Path, header: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    write_header = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(header), restval="", lineterminator="\n")
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def _fmt(value: float | None, digits: int = 2) -> str:
    return "—" if value is None or math.isnan(value) else f"{value:.{digits}f}"


# ---------------------------------------------------------------------------
# Entrenamiento pareado
# ---------------------------------------------------------------------------


def run_arms(
    *,
    inputs: CVInputs,
    variants: Sequence[str],
    lambdas: Mapping[str, float],
    terms: Sequence[str],
    base_training: TrainingConfig,
    train_seed_base: int,
    seeds: Sequence[int],
    output: Path,
    runs_dir: Path | None,
) -> dict[tuple[str, str], list[FoldEvaluation]]:
    """Entrena los dos brazos de cada variante en los mismos folds; escribe de forma incremental."""
    monitored = tuple(constraint_catalog().values())
    plan_info = {
        "file": str(inputs.plan_path),
        "sha256": plan_content_sha256(json.loads(inputs.plan_path.read_text(encoding="utf-8"))),
        "version": inputs.plan.version,
        "k": inputs.plan.k,
    }
    evaluations: dict[tuple[str, str], list[FoldEvaluation]] = {}
    total = len(variants) * len(ARMS) * len(seeds) * inputs.plan.k
    done = 0
    for variant in variants:
        model_config = load_model_config(DEFAULT_MODEL_CONFIGS / f"{variant}.yaml")
        for arm in ARMS:
            constraint_lambda = lambdas[variant] if arm == "constrained" else 0.0
            for seed in seeds:
                for fold, (train_ids, test_ids) in enumerate(inputs.plan.folds(seed)):
                    done += 1
                    train_seed = train_seed_base + seed * 100 + fold
                    config = base_training.model_copy(
                        update={
                            "seed": train_seed,
                            "constraint_lambda": constraint_lambda,
                            "constraint_terms": tuple(terms) if constraint_lambda > 0 else (),
                        }
                    )
                    key = {
                        "seed": seed,
                        "fold": fold,
                        "model": variant,
                        "arm": arm,
                        "constraint_lambda": constraint_lambda,
                    }
                    try:
                        evaluation = run_compositional_fold(
                            seed=seed,
                            fold=fold,
                            model_name=variant,
                            edges_arm=arm,
                            train_ids=train_ids,
                            test_ids=test_ids,
                            graphs=inputs.graphs,
                            pens=inputs.pens,
                            diets=inputs.diets,
                            days=inputs.days,
                            model_config=model_config,
                            metadata=inputs.metadata,
                            config=config,
                            monitor_constraints=monitored,
                            runs_dir=runs_dir,
                            run_context={
                                "dataset_id": inputs.dataset_id,
                                "plan": plan_info,
                                "cohort": dict(inputs.cohort),
                                "source": dict(inputs.source),
                                "repo_root": REPO_ROOT,
                            },
                        )
                    except (ValueError, RuntimeError) as error:
                        _append(
                            output / "folds.csv",
                            FOLDS_HEADER,
                            [
                                {
                                    **key,
                                    "train_seed": train_seed,
                                    "status": "error",
                                    "error": str(error).replace("\n", " "),
                                }
                            ],
                        )
                        print(f"[{done}/{total}] {variant} {arm} s{seed} f{fold}: ERROR {error}")
                        continue
                    evaluations.setdefault((variant, arm), []).append(evaluation)
                    _append(
                        output / "fold_metrics.csv",
                        [*FOLD_HEADER, *METRIC_COLUMNS],
                        [{**key, **record} for record in evaluation.report.to_records()],
                    )
                    _append(
                        output / "predictions.csv",
                        PREDICTIONS_HEADER,
                        [
                            {
                                **{k: v for k, v in prediction.items() if k != "edges_arm"},
                                "arm": arm,
                            }
                            for prediction in evaluation.predictions
                        ],
                    )
                    _append(
                        output / "epoch_violations.csv",
                        VIOLATIONS_HEADER,
                        [{**key, **row.to_dict()} for row in evaluation.violations],
                    )
                    _append(
                        output / "violations.csv",
                        VIOLATIONS_HEADER,
                        [
                            {**key, **row.to_dict()}
                            for row in evaluation.violations
                            if row.subset == TEST_SUBSET
                        ],
                    )
                    _append(
                        output / "folds.csv",
                        FOLDS_HEADER,
                        [
                            {
                                **key,
                                "train_seed": train_seed,
                                "run_id": evaluation.run_id or "",
                                "status": "ok",
                                "best_epoch": evaluation.best_epoch,
                                "epochs_run": evaluation.epochs_run,
                                "n_train": evaluation.n_train,
                                "n_inner_val": evaluation.n_inner_val,
                                "n_test": evaluation.n_test,
                            }
                        ],
                    )
                    print(
                        f"[{done}/{total}] {variant} {arm} λ={constraint_lambda:g} s{seed} "
                        f"f{fold}: {evaluation.epochs_run} épocas",
                        flush=True,
                    )
    return evaluations


# ---------------------------------------------------------------------------
# Agregación y comparación pareada
# ---------------------------------------------------------------------------


def _metric_by_fold(
    evaluations: Sequence[FoldEvaluation], metric: str
) -> dict[tuple[int, int], float]:
    values = {}
    for evaluation in evaluations:
        for row in evaluation.report.rows:
            if row.metric == metric and row.group in (None, "all"):
                values[(evaluation.seed, evaluation.fold)] = float(row.average)
    return values


def _test_rate_by_fold(
    evaluations: Sequence[FoldEvaluation], constraint: str
) -> dict[tuple[int, int], float]:
    return {
        (evaluation.seed, evaluation.fold): row.violation_rate_percent
        for evaluation in evaluations
        for row in evaluation.violations
        if row.subset == TEST_SUBSET and row.constraint == constraint
    }


def paired_rows(
    evaluations: Mapping[tuple[str, str], Sequence[FoldEvaluation]],
    variants: Sequence[str],
    ratio: float,
    feasibility: str,
) -> list[dict[str, Any]]:
    """`constrained − free` por variante y métrica, sobre los folds que terminaron en ambos."""
    rows: list[dict[str, Any]] = []
    for variant in variants:
        free = evaluations.get((variant, "free"), [])
        constrained = evaluations.get((variant, "constrained"), [])
        series = [
            (metric, _metric_by_fold(free, metric), _metric_by_fold(constrained, metric))
            for metric in PAIRED_METRICS
        ]
        series.append(
            (
                f"VR_percent:{feasibility}",
                _test_rate_by_fold(free, feasibility),
                _test_rate_by_fold(constrained, feasibility),
            )
        )
        for metric, base, other in series:
            keys = sorted(set(base) & set(other))
            if len(keys) < 2:
                continue
            result = paired_comparison({key: other[key] - base[key] for key in keys}, ratio)
            rows.append(
                {
                    "model": variant,
                    "metric": metric,
                    "free_mean": statistics.fmean(base[key] for key in keys),
                    "constrained_mean": statistics.fmean(other[key] for key in keys),
                    **result.to_dict(),
                }
            )
    return rows


def _test_train_ratio(evaluations: Mapping[tuple[str, str], Sequence[FoldEvaluation]]) -> float:
    return statistics.fmean(
        evaluation.n_test / (evaluation.n_train + evaluation.n_inner_val)
        for fold_evaluations in evaluations.values()
        for evaluation in fold_evaluations
    )


def _load_baselines(path: Path) -> dict[str, dict[str, str]]:
    """Filas `fraction_mae_pp_mean` y `_std` (grupo `all`) de los baselines de #140."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        return {
            f"{row['model']}:{row['metric']}": row
            for row in csv.DictReader(handle)
            if row.get("group") == "all"
            and row["metric"] in ("fraction_mae_pp_mean", "fraction_mae_pp_std")
        }


# ---------------------------------------------------------------------------
# Reporte
# ---------------------------------------------------------------------------


def _aggregate_cell(report: EvaluationReport, metric: str, group: str = "all") -> str:
    """`media ± std` de una métrica agregada en un grupo (`all` o un día)."""
    groups = {group} | ({None} if group == "all" else set())
    rows: dict[str, MetricRow] = {row.metric: row for row in report.rows if row.group in groups}
    mean = rows.get(f"{metric}_mean")
    std = rows.get(f"{metric}_std")
    if mean is None:
        return "—"
    column = "log_total" if metric.startswith("log_total") else None
    mean_value = mean.targets.get(column) if column else mean.average
    std_value = (std.targets.get(column) if column else std.average) if std else None
    return f"{_fmt(mean_value)} ± {_fmt(std_value)}"


def build_report(context: Mapping[str, Any]) -> str:
    inputs: CVInputs = context["inputs"]
    variants: Sequence[str] = context["variants"]
    aggregates: Mapping[tuple[str, str], EvaluationReport] = context["aggregates"]
    violations: Mapping[tuple[str, str], Sequence[ViolationAggregate]] = context["violations"]
    paired: Sequence[Mapping[str, Any]] = context["paired"]
    lambdas: Mapping[str, float] = context["lambdas"]
    lines = [
        f"# Evaluación pareada con y sin restricciones en `{inputs.dataset_id}` (A68-P2, #185)",
        "",
        f"Generado con `python scripts/evaluate_constraints.py` en {context['elapsed']:.0f} s.",
        "",
        "## Método",
        "",
        f"- **Datos:** {len(inputs.graphs)} animales; plan `{_relative(inputs.plan_path)}` "
        f"(k = {inputs.plan.k}, semillas {list(context['seeds'])}).",
        "- **Objetivo y métricas:** objetivo composicional del contrato v2 §1 "
        f"(`COMPOSITIONAL_TARGET_VERSION = {COMPOSITIONAL_TARGET_VERSION}`) y métricas de D-03, "
        "globales y por día.",
        "- **Brazos pareados (protocolo §1.3):** `free` (λ = 0) y `constrained` (λ elegida por el "
        f"barrido de #178: {', '.join(f'`{v}` λ = {lambdas[v]:g}' for v in variants)}), con los "
        f"términos {list(context['terms'])}, en los mismos folds y con la misma semilla de "
        f"entrenamiento (`{context['train_seed_base']} + semilla·100 + fold`). Escalado, val "
        "interno y detención temprana solo con el train de cada fold.",
        f"- **Entrenamiento:** YAML por omisión de cada variante en `configs/models/`; máx. "
        f"{context['training'].max_epochs} épocas, paciencia {context['training'].patience}, "
        f"dispositivo `{context['training'].device}`.",
        "- **Estado de D-06:** v1.0 (29-10-2026), una sola restricción, "
        "`d06.hydrogen.propionate_bound` (p_p ≤ 2/3). Se monitorean todas las restricciones del "
        f"catálogo (contrato {CONSTRAINTS_CONTRACT_VERSION}).",
        "",
        "## Resultados globales (test de cada fold; media ± std entre folds)",
        "",
        "| Variante | Brazo | MAE fracciones (pp) | R² fracciones | MAE ln T | MAE reconstruido |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for variant in variants:
        for arm in ARMS:
            aggregate = aggregates.get((variant, arm))
            if aggregate is None:
                continue
            lines.append(
                f"| `{variant}` | {arm} | {_aggregate_cell(aggregate, 'fraction_mae_pp')} | "
                f"{_aggregate_cell(aggregate, 'fraction_r2')} | "
                f"{_aggregate_cell(aggregate, 'log_total_mae')} | "
                f"{_aggregate_cell(aggregate, 'reconstructed_mae')} |"
            )
    baselines = context["baselines"]
    if baselines:
        lines += ["", "Referencias de #140 (mismo plan, MAE de fracciones en pp):", ""]
        for model in ("dummy_mean", "day_only"):
            mean = baselines.get(f"{model}:fraction_mae_pp_mean")
            std = baselines.get(f"{model}:fraction_mae_pp_std")
            if mean is not None and std is not None:
                lines.append(
                    f"- `{model}`: {_fmt(float(mean['average']))} ± {_fmt(float(std['average']))}"
                )
    days = context["days"]
    if days:
        lines += [
            "",
            "## MAE de fracciones por día de muestreo (pp)",
            "",
            "| Variante | Brazo | " + " | ".join(f"Día {d}" for d in days) + " |",
            "|---|---|" + "---:|" * len(days),
        ]
        for variant in variants:
            for arm in ARMS:
                aggregate = aggregates.get((variant, arm))
                if aggregate is None:
                    continue
                cells = [_aggregate_cell(aggregate, "fraction_mae_pp", day) for day in days]
                lines.append(f"| `{variant}` | {arm} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Violaciones en el test del fold",
        "",
        "VR y FR en %, media ± std entre folds; VWM es el peor caso de todos los folds, en la "
        "unidad de cada restricción. Las estructurales valen 0 por construcción en la salida "
        "composicional.",
        "",
        "| Variante | Brazo | Restricción | Unidad | VR (%) | VWM (máx.) | FR (%) |",
        "|---|---|---|---|---:|---:|---:|",
    ]
    for variant in variants:
        for arm in ARMS:
            rows = violations.get((variant, arm), ())
            by_key = {(row.constraint, row.metric): row for row in rows}
            for constraint in sorted({row.constraint for row in rows}):
                vr = by_key[(constraint, "violation_rate_percent")]
                vwm = by_key[(constraint, "worst_case_magnitude")]
                fr = by_key[(constraint, "joint_feasibility_percent")]
                lines.append(
                    f"| `{variant}` | {arm} | `{constraint}` | {vr.unit} | "
                    f"{_fmt(vr.mean)} ± {_fmt(vr.std)} | {vwm.max:.4g} | "
                    f"{_fmt(fr.mean)} ± {_fmt(fr.std)} |"
                )
    lines += [
        "",
        "## Comparación pareada `constrained − free` (protocolo §4.2)",
        "",
        f"t corregido de Nadeau y Bengio (n_test/n_train = {context['ratio']:.3f}), IC 95 % "
        "bilateral, Wilcoxon sobre las medias por semilla y d de Cohen pareada. Si Δ = 0 en "
        "todos los folds, los dos brazos son idénticos y no hay estadístico.",
        "",
        "| Variante | Métrica | free | constrained | Δ | IC 95 % | p (t corr.) | "
        "p (Wilcoxon) | d |",
        "|---|---|---:|---:|---:|---|---:|---:|---:|",
    ]
    for row in paired:
        lines.append(
            f"| `{row['model']}` | `{row['metric']}` | {row['free_mean']:.4f} | "
            f"{row['constrained_mean']:.4f} | {row['mean_delta']:+.4f} | "
            f"[{row['ci_low']:+.4f}; {row['ci_high']:+.4f}] | {_fmt(row['p_value'], 3)} | "
            f"{_fmt(row['wilcoxon_p_value'], 3)} | {_fmt(row['cohen_d'])} |"
        )
    lines += [
        "",
        "## Advertencias y limitaciones",
        "",
        "- **Clasificación pendiente.** La decisión de §5 (δ, regla por IC y paso 1 de "
        "factibilidad) se está reescribiendo con Investigación (P-02, P-05 y P-07; #158 y PR "
        "#217). Este reporte informa Δ, IC y violaciones, pero no clasifica.",
        "- **Penalización inactiva si nadie viola la cota.** Con salidas composicionales, `L_bio` "
        "vale 0 y su gradiente también mientras ninguna predicción supere p_p = 2/3: en ese caso "
        "los dos brazos coinciden (D-06 §6).",
    ]
    if inputs.is_synthetic:
        lines.append(
            "- **Cohorte sintética.** Sus animales no son reales: cada uno es su propio grupo y "
            "no hay dietas ni días de muestreo. Sirve para comprobar el método, no la biología."
        )
    else:
        lines += [
            "- **Taxones aislados (S-04 sin integrar, #175).** La GNN usa los taxones solo por la "
            "lectura media; la ventaja estructural sigue sin probar.",
            "- **Desbalance 34/15/7 y dieta confundida con el día** (protocolo §6.2): toda "
            "comparación entre tratamientos es exploratoria.",
            "- " + context["missing_days"],
        ]
    lines += [
        f"- Folds fallidos: {context['failed']} (`status = error` en `folds.csv`).",
        "",
        "## Archivos",
        "",
        "`metrics.csv`, `fold_metrics.csv`, `violations.csv`, `epoch_violations.csv`, "
        "`violations_summary.csv`, `paired.csv`, `folds.csv`, `predictions.csv` y `run.json`. "
        "Cada fila de `folds.csv` enlaza su corrida (`run_id`) con checkpoint en `runs_dir`.",
        "",
    ]
    return "\n".join(lines)


def _missing_days_note(inputs: CVInputs, seeds: Sequence[int]) -> str:
    missing = [
        row
        for row in fold_table(inputs.plan, inputs.animals)
        if row.missing_days and row.seed in seeds
    ]
    if not missing:
        return "Todos los folds evaluados tienen los tres días de muestreo."
    folds = "; ".join(
        f"semilla {row.seed}, fold {row.fold}: sin el día {', '.join(row.missing_days)}"
        for row in missing
    )
    return (
        f"**Folds sin algún día ({len(missing)}):** {folds}; esas celdas se omiten de la "
        "agregación por día (`_n`)."
    )


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset", choices=DATASETS, required=True)
    parser.add_argument("--selection", type=Path, default=None)
    parser.add_argument("--sweep-config", type=Path, default=None)
    parser.add_argument("--plan", type=Path, default=None)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--graphs-dir", type=Path, default=DEFAULT_GRAPHS)
    parser.add_argument("--training-config", type=Path, default=DEFAULT_TRAINING_CONFIG)
    parser.add_argument("--variants", nargs="+", default=None)
    parser.add_argument("--seeds", nargs="+", type=int, default=None)
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--runs-dir", type=Path, default=None)
    parser.add_argument("--no-save-runs", action="store_true")
    args = parser.parse_args(argv)

    dataset = args.dataset
    selection_path = args.selection or (
        REPO_ROOT / "reports" / "constraints" / "lambda_sweep" / dataset / "selection.json"
    )
    sweep_config_path = args.sweep_config or (
        REPO_ROOT / "configs" / "constraints" / f"lambda_sweep_{dataset}.json"
    )
    output = args.output or REPO_ROOT / "reports" / "constraints" / dataset
    runs_dir = (
        None
        if args.no_save_runs
        else (args.runs_dir or REPO_ROOT / "runs" / "constraints" / dataset)
    )
    started = time.monotonic()
    try:
        sweep = load_lambda_sweep_config(sweep_config_path)
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
        plan_path = args.plan or PLANS[dataset]
        inputs = (
            load_d1_cv_inputs(args.sources, args.graphs_dir, plan_path)
            if dataset == "d1"
            else load_synthetic_cv_inputs(plan_path)
        )
        if selection["dataset_id"] != inputs.dataset_id:
            raise ValueError(
                f"La selección es de {selection['dataset_id']!r} y los datos de "
                f"{inputs.dataset_id!r}."
            )
        variants = list(args.variants or sweep.variants)
        lambdas = {
            variant: float(selection["selections"][variant]["selected_lambda"])
            for variant in variants
        }
        seeds = list(args.seeds or inputs.plan.seeds)
        unknown = sorted(set(seeds) - set(inputs.plan.seeds))
        if unknown:
            raise ValueError(f"Semillas que no están en el plan: {unknown}.")
        training = load_training_config(args.training_config).model_copy(
            update={
                "dataset_id": inputs.dataset_id,
                "max_epochs": sweep.max_epochs,
                "patience": sweep.patience,
                **({"device": args.device} if args.device else {}),
            }
        )
    except (FileNotFoundError, KeyError, ValueError) as error:
        print(f"No se pudo preparar la evaluación: {error}", file=sys.stderr)
        return EXIT_INPUT

    output.mkdir(parents=True, exist_ok=True)
    for name in (
        "fold_metrics.csv",
        "predictions.csv",
        "epoch_violations.csv",
        "violations.csv",
        "folds.csv",
    ):
        (output / name).unlink(missing_ok=True)
    evaluations = run_arms(
        inputs=inputs,
        variants=variants,
        lambdas=lambdas,
        terms=sweep.constraint_terms,
        base_training=training,
        train_seed_base=sweep.train_seed_base,
        seeds=seeds,
        output=output,
        runs_dir=runs_dir,
    )
    if not evaluations:
        print("Ningún fold terminó con éxito.", file=sys.stderr)
        return EXIT_INPUT

    aggregates = {
        key: aggregate_fold_reports({(e.seed, e.fold): e.report for e in fold_evaluations})
        for key, fold_evaluations in evaluations.items()
    }
    with (output / "metrics.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["model", "arm", *METRIC_COLUMNS], lineterminator="\n"
        )
        writer.writeheader()
        for (variant, arm), aggregate in sorted(aggregates.items()):
            for record in aggregate.to_records():
                writer.writerow({"model": variant, "arm": arm, **record})
    violation_aggregates = {
        key: aggregate_violation_log(
            [(e.seed, row) for e in fold_evaluations for row in e.violations]
        )
        for key, fold_evaluations in evaluations.items()
    }
    summary_header = ["model", "arm", *ViolationAggregate.__dataclass_fields__]
    with (output / "violations_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary_header, lineterminator="\n")
        writer.writeheader()
        for (variant, arm), rows in sorted(violation_aggregates.items()):
            for row in rows:
                writer.writerow({"model": variant, "arm": arm, **row.to_dict()})
    ratio = _test_train_ratio(evaluations)
    paired = paired_rows(evaluations, variants, ratio, sweep.feasibility_constraint)
    if paired:
        with (output / "paired.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(paired[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(paired)
    elapsed = time.monotonic() - started
    with (output / "folds.csv").open(encoding="utf-8") as handle:
        fold_rows = list(csv.DictReader(handle))
    failed = sum(1 for row in fold_rows if row["status"] != "ok")
    days = sorted({day for day in inputs.days.values() if day.isdigit()}, key=lambda d: float(d))
    report = build_report(
        {
            "inputs": inputs,
            "variants": variants,
            "aggregates": aggregates,
            "violations": violation_aggregates,
            "paired": paired,
            "lambdas": lambdas,
            "terms": sweep.constraint_terms,
            "seeds": seeds,
            "train_seed_base": sweep.train_seed_base,
            "training": training,
            "ratio": ratio,
            "baselines": _load_baselines(BASELINE_METRICS) if dataset == "d1" else {},
            "days": days,
            "missing_days": _missing_days_note(inputs, seeds),
            "failed": failed,
            "elapsed": elapsed,
        }
    )
    (output / "report.md").write_text(report, encoding="utf-8", newline="\n")
    run_meta = {
        "issue": 185,
        "command": "python scripts/evaluate_constraints.py",
        "argv": list(argv) if argv is not None else sys.argv[1:],
        "dataset_id": inputs.dataset_id,
        "plan": _relative(inputs.plan_path),
        "plan_sha256": _sha256(inputs.plan_path),
        "plan_canonical_sha256": plan_content_sha256(
            json.loads(inputs.plan_path.read_text(encoding="utf-8"))
        ),
        "cohort": dict(inputs.cohort),
        "cohort_config_sha256": _sha256(COHORT_CONFIG) if dataset == "d1" else None,
        "selection": _relative(selection_path),
        "selection_sha256": _sha256(selection_path),
        "sweep_config": _relative(sweep_config_path),
        "sweep_config_sha256": _sha256(sweep_config_path),
        "lambdas": lambdas,
        "constraint_terms": list(sweep.constraint_terms),
        "monitored_constraints": sorted(constraint_catalog()),
        "constraints_contract_version": CONSTRAINTS_CONTRACT_VERSION,
        "compositional_target_version": COMPOSITIONAL_TARGET_VERSION,
        "training_config": training.model_dump(mode="json"),
        "train_seed_base": sweep.train_seed_base,
        "seeds": seeds,
        "variants": variants,
        "arms": list(ARMS),
        "test_train_ratio": ratio,
        "folds_ok": len(fold_rows) - failed,
        "folds_failed": failed,
        "runs_dir": None if runs_dir is None else _relative(runs_dir),
        "git": git_info(REPO_ROOT),
        "environment": environment_info(training.device),
        "elapsed_seconds": round(elapsed, 1),
    }
    (output / "run.json").write_text(
        json.dumps(run_meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    print(report)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
