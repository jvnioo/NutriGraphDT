"""Reevaluación de las GNN en D1 con el objetivo composicional y CV por corral (#142).

Repite las evaluaciones de A45-4 a A45-6 (#104 a #106) y la búsqueda acotada de A45-5 (#105)
bajo el marco nuevo de la respuesta de Investigación del 16-10-2026 (D-03 y D-07): objetivo
composicional del contrato v2 (sección 1; #146), cohorte oficial
(`configs/cohorts/d1_holofood.json`) y validación cruzada agrupada por corral
(`configs/splits/d1_holofood_cv.json`, #139).

Dos fases, sin que ningún dato de evaluación de un fold intervenga en la selección ni en la
detención temprana (criterio de aceptación):

1. **Selección (A45-5 bajo CV).** La grilla de `hidden_channels` × `num_layers` de A45-5 se
   evalúa solo con animales de entrenamiento: en cada fold de las `--selection-seeds` primeras
   semillas del plan se aparta un val interno por corral (`split_inner_validation`) y se elige,
   por variante, la combinación con menor pérdida composicional en ese val interno.
2. **Evaluación.** Cada variante se entrena en cada fold con detención temprana sobre el val
   interno del train del fold y se evalúa en el test del fold con `evaluate_composition`
   (métricas de D-03, globales y por día). Se repite con y sin aristas `inferred` (ablación
   V-01, respuesta 3) y se agrega con `aggregate_fold_reports` (media y desviación entre folds
   y entre semillas).

Escribe en `--output` (por defecto `reports/gnn/d1_composition/`):

- `report.md`: comparación con los baselines composicionales y `day_only` (#140), declaración
  del criterio de F4 con su incertidumbre, ablación y limitaciones.
- `metrics.csv`: métricas agregadas por variante y brazo de la ablación.
- `fold_metrics.csv`: métricas de cada (semilla, fold, variante, brazo), escrita de forma
  incremental (sirve aunque la corrida se interrumpa).
- `predictions.csv`: salida `(z_1, z_2, ln T)` de cada animal de test, incremental.
- `folds.csv`: diagnóstico por fold (mejor época, épocas, tamaños), incremental.
- `selection.csv` / `selection.json`: grilla de A45-5 bajo CV y configuración elegida.
- `run.json`: metadatos de la ejecución.

Uso:

    pip install -e ".[dev,baselines,graph]"
    python scripts/build_graph.py --save-graphs --overwrite   # si no están guardados
    python scripts/evaluate_gnn_d1_composition.py

    # Humo rápido: una semilla, una variante, pocas épocas
    python scripts/evaluate_gnn_d1_composition.py --seeds 0 --variants homo_sage \
        --arms with_inferred --selection-seeds 1 --max-epochs 5 --patience 2

Código de salida: `0` si escribió el reporte; `2` si faltan datos o grafos.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from nutrigraphdt.data.cohort import load_cohort
from nutrigraphdt.data.config import load_sources
from nutrigraphdt.graph.builder import add_reverse_edges
from nutrigraphdt.graph.heterodata import load_graphs
from nutrigraphdt.models.composition import ALL_DAYS, COMPOSITIONAL_TARGET_VERSION
from nutrigraphdt.models.cross_validation import PenFoldPlan, aggregate_fold_reports
from nutrigraphdt.models.gnn import MODEL_VARIANTS, load_model_config
from nutrigraphdt.models.gnn.base import GraphMetadata
from nutrigraphdt.models.gnn.batching import align_graph_types
from nutrigraphdt.models.gnn.factory import GNNModelConfig
from nutrigraphdt.models.gnn.target import add_graph_target
from nutrigraphdt.models.metrics import EvaluationReport, MetricRow
from nutrigraphdt.models.training.compositional import (
    INFERRED_STATUS,
    CompositionalTargetTransform,
    FoldEvaluation,
    drop_inferred_edges,
    run_compositional_fold,
    split_inner_validation,
    train_compositional_model,
)
from nutrigraphdt.models.training.config import TrainingConfig, load_training_config
from nutrigraphdt.models.training.scaling import FeatureScaler
from nutrigraphdt.models.training.tuning import GRID_HIDDEN_CHANNELS, GRID_NUM_LAYERS, grid_configs

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = REPO_ROOT / "configs" / "sources.json"
DEFAULT_PLAN = REPO_ROOT / "configs" / "splits" / "d1_holofood_cv.json"
DEFAULT_GRAPHS = REPO_ROOT / "artifacts" / "graphs" / "D1_holofood"
DEFAULT_TRAINING_CONFIG = REPO_ROOT / "configs" / "training" / "default.json"
DEFAULT_MODEL_CONFIGS = REPO_ROOT / "configs" / "models"
DEFAULT_BASELINE_METRICS = REPO_ROOT / "reports" / "baselines" / "d1_composition" / "metrics.csv"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "gnn" / "d1_composition"
METADATA_SOURCE = "D1_holofood_metadata"

WITH_INFERRED = "with_inferred"
WITHOUT_INFERRED = "without_inferred"
ARMS = (WITH_INFERRED, WITHOUT_INFERRED)
CV_SPLIT = "cv"

EXIT_OK = 0
EXIT_INPUT = 2

FOLD_METRICS_HEADER = ["seed", "fold", "model", "edges_arm"]
PREDICTIONS_HEADER = [
    "sample_id",
    "seed",
    "fold",
    "model",
    "edges_arm",
    "sampling_day",
    "z1",
    "z2",
    "log_total",
]
FOLDS_HEADER = [
    "seed",
    "fold",
    "model",
    "edges_arm",
    "status",
    "best_epoch",
    "epochs_run",
    "stopped_early",
    "duration_seconds",
    "n_train",
    "n_inner_val",
    "n_test",
    "error",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fmt(value: float, digits: int = 2) -> str:
    return "—" if math.isnan(value) else f"{value:.{digits}f}"


def _fmt_pm(rows: Mapping[str, MetricRow], target: str, digits: int = 2) -> str:
    mean = rows.get("mean")
    if mean is None:
        return "—"
    value = mean.targets.get(target, math.nan) if target != "average" else mean.average
    std_row = rows.get("std")
    std = (
        (std_row.targets.get(target, math.nan) if target != "average" else std_row.average)
        if std_row
        else math.nan
    )
    if math.isnan(std):
        return _fmt(value, digits)
    return f"{_fmt(value, digits)} ± {_fmt(std, digits)}"


def _aggregate_rows(
    report: EvaluationReport, model: str, base_metric: str, group: str = ALL_DAYS
) -> dict[str, MetricRow]:
    rows: dict[str, MetricRow] = {}
    for row in report.rows:
        if row.model != model or row.group != group:
            continue
        for aggregate in ("mean", "std", "seed_std", "n"):
            if row.metric == f"{base_metric}_{aggregate}":
                rows[aggregate] = row
    return rows


def _load_baseline_metrics(path: Path) -> EvaluationReport:
    """Lee el `metrics.csv` de #140 (agregado) como `EvaluationReport`."""
    rows: list[MetricRow] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            targets = {
                name: float(record[name])
                for name in ("acetate", "propionate", "butyrate", "log_total")
                if record.get(name)
            }
            rows.append(
                MetricRow(
                    record["model"],
                    record["metric"],
                    targets,
                    float(record["average"]) if record.get("average") else math.nan,
                    split=record.get("split") or None,
                    group=record.get("group") or None,
                )
            )
    return EvaluationReport(rows=tuple(rows))


# ---------------------------------------------------------------------------
# Carga y preparación de grafos
# ---------------------------------------------------------------------------


def _load_metadata(path_or_url: str | None) -> dict[str, dict[str, str]]:
    if path_or_url is None:
        raise FileNotFoundError(f"La fuente {METADATA_SOURCE} no tiene archivo local.")
    with Path(path_or_url).open(encoding="utf-8", newline="") as handle:
        return {
            row["sample_id"]: row
            for row in csv.DictReader(handle, delimiter="\t")
            if row.get("sample_id")
        }


def _prepare_graphs(
    graphs_dir: Path, cohort_ids: frozenset[str]
) -> tuple[dict[str, Any], GraphMetadata, dict[str, int]]:
    """Grafos entregables de la cohorte con target composicional, listos para los folds.

    Devuelve `(grafos por sample_id, metadatos, conteo de aristas por estado de evidencia)`.
    """
    report = json.loads((graphs_dir / "report.json").read_text(encoding="utf-8"))
    status = report["validation"]["graphs"]
    evidence_counts: dict[str, int] = {}
    prepared: dict[str, Any] = {}
    for graph_id, graph in load_graphs(graphs_dir / "graphs").items():
        if not status.get(graph_id, {}).get("deliverable", False):
            continue
        sample_id = str(graph.sample_id)
        if sample_id not in cohort_ids:
            continue
        for edge_type in graph.edge_types:
            for value in getattr(graph[edge_type], "evidence_status", []) or []:
                evidence_counts[str(value)] = evidence_counts.get(str(value), 0) + 1
        with_target = add_graph_target(add_reverse_edges(graph))
        with_target.graph_id = graph_id
        if not bool(with_target.y_graph_mask.all()):
            continue
        prepared[sample_id] = with_target
    if not prepared:
        raise ValueError("Ningún grafo entregable de la cohorte tiene los tres AGCC.")
    metadata = GraphMetadata.from_graphs(list(prepared.values()))
    align_graph_types(list(prepared.values()), inplace=True)
    return prepared, metadata, evidence_counts


# ---------------------------------------------------------------------------
# Fase 1: grilla de A45-5 bajo validación cruzada (sin tocar el test de cada fold)
# ---------------------------------------------------------------------------


def _inner_val_loss(
    *,
    train_ids: Sequence[str],
    graphs: Mapping[str, Any],
    pens: Mapping[str, str],
    diets: Mapping[str, str],
    model_config: GNNModelConfig,
    metadata: GraphMetadata,
    config: TrainingConfig,
    inner_folds: int = 5,
) -> float:
    """Pérdida composicional de la configuración en el val interno del train de un fold."""
    from nutrigraphdt.models.training.config import set_seed

    set_seed(config.seed)
    inner_train, inner_val = split_inner_validation(
        train_ids, pens, diets, seed=config.seed, inner_folds=inner_folds
    )
    train_graphs = [graphs[s] for s in inner_train]
    val_graphs = [graphs[s] for s in inner_val]
    feature_scaler = FeatureScaler.fit(train_graphs)
    transform = CompositionalTargetTransform.fit(train_graphs)
    from nutrigraphdt.models.gnn.factory import build_model

    model = build_model(model_config, metadata)
    result = train_compositional_model(
        model,
        feature_scaler.transform(train_graphs),
        feature_scaler.transform(val_graphs),
        config,
        transform,
    )
    return result.best_val_loss


def _run_selection(
    *,
    variants: Sequence[str],
    plan: PenFoldPlan,
    selection_seeds: int,
    graphs: Mapping[str, Any],
    pens: Mapping[str, str],
    diets: Mapping[str, str],
    base_configs: Mapping[str, GNNModelConfig],
    metadata: GraphMetadata,
    config: TrainingConfig,
    train_seed_base: int,
    output: Path,
    inner_folds: int = 5,
) -> dict[str, GNNModelConfig]:
    """Grilla de A45-5 bajo CV: elige por variante la mejor capacidad sin leer ningún test."""
    seeds = list(plan.seeds)[:selection_seeds]
    folds = [(seed, fold) for seed in seeds for fold in range(plan.k)]
    selected: dict[str, GNNModelConfig] = {}
    selection_path = output / "selection.csv"
    write_header = not selection_path.exists()
    with selection_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["variant", "hidden_channels", "num_layers", "seed", "fold", "val_loss"],
            lineterminator="\n",
        )
        if write_header:
            writer.writeheader()
        for variant in variants:
            candidates = grid_configs(base_configs[variant], GRID_HIDDEN_CHANNELS, GRID_NUM_LAYERS)
            losses: dict[int, list[float]] = {index: [] for index in range(len(candidates))}
            for index, candidate in enumerate(candidates):
                for seed, fold in folds:
                    train_ids, _ = plan.folds(seed)[fold]
                    fold_config = config.model_copy(
                        update={"seed": train_seed_base + seed * 100 + fold}
                    )
                    try:
                        loss = _inner_val_loss(
                            train_ids=train_ids,
                            graphs=graphs,
                            pens=pens,
                            diets=diets,
                            model_config=candidate,
                            metadata=metadata,
                            config=fold_config,
                            inner_folds=inner_folds,
                        )
                        losses[index].append(loss)
                        row = {
                            "variant": variant,
                            "hidden_channels": candidate.hidden_channels,
                            "num_layers": candidate.num_layers,
                            "seed": seed,
                            "fold": fold,
                            "val_loss": f"{loss:.6f}",
                        }
                    except (ValueError, RuntimeError) as error:
                        row = {
                            "variant": variant,
                            "hidden_channels": candidate.hidden_channels,
                            "num_layers": candidate.num_layers,
                            "seed": seed,
                            "fold": fold,
                            "val_loss": f"ERROR: {error}",
                        }
                    writer.writerow(row)
                    handle.flush()
            available = [i for i in range(len(candidates)) if losses[i]]
            if not available:
                raise ValueError(
                    f"Ninguna combinación de la grilla entrenó con éxito para {variant}; "
                    "revise selection.csv."
                )
            best_index = min(
                available,
                key=lambda i: (
                    sum(losses[i]) / len(losses[i]),
                    candidates[i].hidden_channels,
                    candidates[i].num_layers,
                ),
            )
            selected[variant] = candidates[best_index]
            mean_loss = sum(losses[best_index]) / len(losses[best_index])
            print(
                f"{variant}: elegida {candidates[best_index].hidden_channels}×"
                f"{candidates[best_index].num_layers} (pérdida val interno {mean_loss:.4f}, "
                f"{len(losses[best_index])} folds)",
                flush=True,
            )
    (output / "selection.json").write_text(
        json.dumps(
            {
                "criterion": "mínima pérdida composicional en el val interno del train del fold",
                "test_used": False,
                "selection_seeds": seeds,
                "folds_per_seed": plan.k,
                "grid": {
                    "hidden_channels": list(GRID_HIDDEN_CHANNELS),
                    "num_layers": list(GRID_NUM_LAYERS),
                },
                "selected": {
                    variant: dict(config.model_dump()) for variant, config in selected.items()
                },
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return selected


# ---------------------------------------------------------------------------
# Fase 2: evaluación por fold
# ---------------------------------------------------------------------------


def _append_rows(path: Path, header: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    write_header = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(header), restval="", lineterminator="\n")
        if write_header:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)
        handle.flush()


def _run_evaluation(
    *,
    variants: Sequence[str],
    arms: Sequence[str],
    model_configs: Mapping[str, GNNModelConfig],
    plan: PenFoldPlan,
    graphs: Mapping[str, Any],
    pens: Mapping[str, str],
    diets: Mapping[str, str],
    days: Mapping[str, str],
    metadata: GraphMetadata,
    config: TrainingConfig,
    train_seed_base: int,
    output: Path,
    inner_folds: int = 5,
) -> dict[tuple[str, str], list[FoldEvaluation]]:
    """Entrena y evalúa cada variante y brazo en cada fold; escribe de forma incremental."""
    evaluations: dict[tuple[str, str], list[FoldEvaluation]] = {}
    total = len(variants) * len(arms) * len(plan.seeds) * plan.k
    done = 0
    for arm in arms:
        arm_graphs = (
            {sample_id: drop_inferred_edges(graph) for sample_id, graph in graphs.items()}
            if arm == WITHOUT_INFERRED
            else graphs
        )
        for variant in variants:
            for seed, fold, train_ids, test_ids in plan.iter_folds():
                done += 1
                fold_config = config.model_copy(
                    update={"seed": train_seed_base + seed * 100 + fold}
                )
                try:
                    evaluation = run_compositional_fold(
                        seed=seed,
                        fold=fold,
                        model_name=variant,
                        edges_arm=arm,
                        train_ids=train_ids,
                        test_ids=test_ids,
                        graphs=arm_graphs,
                        pens=pens,
                        diets=diets,
                        days=days,
                        model_config=model_configs[variant],
                        metadata=metadata,
                        config=fold_config,
                        inner_folds=inner_folds,
                    )
                except (ValueError, RuntimeError) as error:
                    _append_rows(
                        output / "folds.csv",
                        FOLDS_HEADER,
                        [
                            {
                                "seed": seed,
                                "fold": fold,
                                "model": variant,
                                "edges_arm": arm,
                                "status": "error",
                                "error": str(error).replace("\n", " "),
                            }
                        ],
                    )
                    print(f"[{done}/{total}] {variant} {arm} s{seed} f{fold}: ERROR {error}")
                    continue
                evaluations.setdefault((variant, arm), []).append(evaluation)
                _append_rows(
                    output / "fold_metrics.csv",
                    FOLD_METRICS_HEADER
                    + [
                        "split",
                        "group",
                        "metric",
                        "acetate",
                        "propionate",
                        "butyrate",
                        "log_total",
                        "average",
                    ],
                    [
                        {"seed": seed, "fold": fold, "model": variant, "edges_arm": arm, **record}
                        for record in evaluation.report.to_records()
                    ],
                )
                _append_rows(output / "predictions.csv", PREDICTIONS_HEADER, evaluation.predictions)
                _append_rows(
                    output / "folds.csv",
                    FOLDS_HEADER,
                    [
                        {
                            "seed": seed,
                            "fold": fold,
                            "model": variant,
                            "edges_arm": arm,
                            "status": "ok",
                            "best_epoch": evaluation.best_epoch,
                            "epochs_run": evaluation.epochs_run,
                            "stopped_early": evaluation.stopped_early,
                            "duration_seconds": f"{evaluation.duration_seconds:.2f}",
                            "n_train": evaluation.n_train,
                            "n_inner_val": evaluation.n_inner_val,
                            "n_test": evaluation.n_test,
                            "error": "",
                        }
                    ],
                )
                print(
                    f"[{done}/{total}] {variant} {arm} s{seed} f{fold}: "
                    f"{evaluation.epochs_run} épocas en {evaluation.duration_seconds:.1f} s",
                    flush=True,
                )
    return evaluations


# ---------------------------------------------------------------------------
# Reporte
# ---------------------------------------------------------------------------

METRIC_LABELS: Mapping[str, str] = {
    "fraction_r2": "R² de la fracción",
    "fraction_mae_pp": "MAE de la fracción (puntos porcentuales)",
    "reconstructed_r2": "R² de la cantidad reconstruida (mmol/kg)",
    "reconstructed_mae": "MAE de la cantidad reconstruida (mmol/kg)",
}

BASELINE_MODELS = (
    "dummy_mean",
    "day_only",
    "ridge_design",
    "ridge",
    "elasticnet",
    "random_forest",
    "hist_gradient_boosting",
)


def _variant_label(variant: str, arm: str) -> str:
    return variant if arm == WITH_INFERRED else f"{variant} (sin inferred)"


def _global_table(
    aggregates: Mapping[tuple[str, str], EvaluationReport],
    baselines: EvaluationReport | None,
    base_metric: str,
    arms: Sequence[str],
    variants: Sequence[str],
) -> list[str]:
    """Tabla global de una métrica: variantes GNN y baselines, media ± std por AGCC y macro."""
    lines = [
        f"### {METRIC_LABELS[base_metric]}",
        "",
        "| Modelo | Acetato | Propionato | Butirato | Macro |",
        "|---|---:|---:|---:|---:|",
    ]
    for arm in arms:
        for variant in variants:
            aggregate = aggregates.get((variant, arm))
            if aggregate is None:
                continue
            cells = _aggregate_rows(aggregate, variant, base_metric)
            lines.append(
                f"| `{_variant_label(variant, arm)}` | "
                + " | ".join(
                    _fmt_pm(cells, target)
                    for target in ("acetate", "propionate", "butyrate", "average")
                )
                + " |"
            )
    if baselines is not None:
        for model in BASELINE_MODELS:
            cells = _aggregate_rows(baselines, model, base_metric)
            if not cells:
                continue
            lines.append(
                f"| `{model}` (baseline #140) | "
                + " | ".join(
                    _fmt_pm(cells, target)
                    for target in ("acetate", "propionate", "butyrate", "average")
                )
                + " |"
            )
    return lines


def _log_total_table(
    aggregates: Mapping[tuple[str, str], EvaluationReport],
    baselines: EvaluationReport | None,
    arms: Sequence[str],
    variants: Sequence[str],
) -> list[str]:
    lines = ["### log T (total de los tres AGCC)", "", "| Modelo | R² | MAE |", "|---|---:|---:|"]
    entries: list[tuple[str, EvaluationReport, str]] = [
        (_variant_label(v, a), aggregates[(v, a)], v)
        for a in arms
        for v in variants
        if (v, a) in aggregates
    ]
    for label, aggregate, model in entries:
        r2 = _aggregate_rows(aggregate, model, "log_total_r2")
        mae = _aggregate_rows(aggregate, model, "log_total_mae")
        lines.append(f"| `{label}` | {_fmt_pm(r2, 'log_total')} | {_fmt_pm(mae, 'log_total')} |")
    if baselines is not None:
        for model in BASELINE_MODELS:
            r2 = _aggregate_rows(baselines, model, "log_total_r2")
            mae = _aggregate_rows(baselines, model, "log_total_mae")
            if not r2:
                continue
            lines.append(
                f"| `{model}` (baseline #140) | {_fmt_pm(r2, 'log_total')} | "
                f"{_fmt_pm(mae, 'log_total')} |"
            )
    return lines


def _macro_fraction_r2(report: EvaluationReport, model: str) -> tuple[float, float] | None:
    """(media, std) del R² macro de las fracciones, global."""
    cells = _aggregate_rows(report, model, "fraction_r2")
    mean = cells.get("mean")
    if mean is None or math.isnan(mean.average):
        return None
    std = cells.get("std")
    return mean.average, std.average if std is not None else math.nan


def _f4_declaration(
    aggregates: Mapping[tuple[str, str], EvaluationReport],
    baselines: EvaluationReport | None,
    variants: Sequence[str],
) -> list[str]:
    """Declaración del criterio de F4 con su incertidumbre, frente a `day_only` y los baselines."""
    gnn_stats = {
        variant: _macro_fraction_r2(aggregates[(variant, WITH_INFERRED)], variant)
        for variant in variants
        if (variant, WITH_INFERRED) in aggregates
    }
    gnn_stats = {v: s for v, s in gnn_stats.items() if s is not None}
    if not gnn_stats:
        return ["No hay ninguna variante GNN evaluada en todos los folds; no se declara F4."]
    best_variant = max(gnn_stats, key=lambda v: gnn_stats[v][0])
    best_mean, best_std = gnn_stats[best_variant]
    lines = [
        "El criterio de F4 pide que una GNN iguale o supere al menos un baseline, ahora con el "
        "objetivo composicional (D-03) y la validación cruzada por corral (D-07). Se evalúa con "
        "el **R² macro de las fracciones, global**, media ± desviación estándar entre los folds "
        "y semillas (las mismas 50 particiones para todos los modelos, así que las diferencias "
        "son pareadas).",
        "",
        f"- Mejor GNN: `{best_variant}` con {_fmt(best_mean)} ± {_fmt(best_std)}.",
    ]
    if baselines is not None:
        day_only = _macro_fraction_r2(baselines, "day_only")
        if day_only is not None:
            diff = best_mean - day_only[0]
            combined = math.sqrt(best_std**2 + day_only[1] ** 2)
            verdict = "iguala o supera" if best_mean >= day_only[0] else "no alcanza"
            lines.append(
                f"- `day_only`: {_fmt(day_only[0])} ± {_fmt(day_only[1])}. La mejor GNN "
                f"{verdict} a `day_only` (diferencia {_fmt(diff)}; la dispersión combinada de "
                f"las medias es {_fmt(combined)})."
            )
        best_baseline = max(
            (
                (model, stats)
                for model in BASELINE_MODELS
                if (stats := _macro_fraction_r2(baselines, model)) is not None
            ),
            key=lambda item: item[1][0],
            default=None,
        )
        if best_baseline is not None:
            model, (mean, std) = best_baseline
            verdict = "se cumple" if best_mean >= mean else "no se cumple"
            lines.append(
                f"- Mejor baseline: `{model}` con {_fmt(mean)} ± {_fmt(std)}. "
                f"**Criterio de F4: {verdict}** (`{best_variant}` {_fmt(best_mean)} ± "
                f"{_fmt(best_std)} frente a {_fmt(mean)} ± {_fmt(std)}; una diferencia menor "
                "que la dispersión entre folds no es concluyente)."
            )
    else:
        lines.append(
            "- No se encontró `metrics.csv` de los baselines de #140; la comparación con "
            "`day_only` y los baselines composicionales queda pendiente."
        )
    return lines


def build_report_markdown(context: Mapping[str, Any]) -> str:
    aggregates: Mapping[tuple[str, str], EvaluationReport] = context["aggregates"]
    baselines: EvaluationReport | None = context["baselines"]
    variants: Sequence[str] = context["variants"]
    arms: Sequence[str] = context["arms"]
    lines: list[str] = [
        "# GNN de D1 con objetivo composicional y validación cruzada por corral (#142)",
        "",
        f"Generado con `python scripts/evaluate_gnn_d1_composition.py` en "
        f"{context['elapsed_s']:.0f} s.",
        "",
        "## Método",
        "",
        f"- **Cohorte:** {context['n_samples']} animales de la cohorte oficial "
        f"(versión {context['cohort_version']}, ≥ {context['min_ssu_reads']} lecturas SSU) con "
        "los tres AGCC y su grafo entregable.",
        "- **Objetivo (D-03, contrato v2 §1, transformación v"
        f"{COMPOSITIONAL_TARGET_VERSION}`):** la cabeza de tres salidas predice "
        "`(z_1, z_2, ln T)` = (ln(propionato/acetato), ln(butirato/acetato), ln T); la pérdida "
        "es el MSE estandarizado (media y desviación del train del fold) sobre los animales con "
        "objetivo válido, sin pseudoconteo.",
        f"- **Validación (D-07, #139):** plan `{context['plan_path']}` "
        f"(k = {context['k']}, semillas {context['seeds'][0]} a {context['seeds'][-1]}; sha256 "
        f"`{context['plan_sha256'][:12]}…`). Cada celda es la media ± la desviación estándar "
        "entre los folds evaluados; la dispersión entre semillas está en `metrics.csv` "
        "(sufijo `_seed_std`).",
        "- **Sin fuga:** en cada fold, el escalado de features y del objetivo se ajusta solo "
        "con el train del fold y la detención temprana usa un **val interno** del train del "
        "fold, agrupado por corral y estratificado por dieta (un quinto de los corrales; "
        f"semilla derivada de la del fold, base {context['train_seed_base']}). El test del "
        "fold solo se evalúa al final.",
        "- **Selección de hiperparámetros (A45-5 repetida bajo CV):** la grilla "
        f"{list(GRID_HIDDEN_CHANNELS)} × {list(GRID_NUM_LAYERS)} de `hidden_channels` × "
        f"`num_layers` se evaluó solo con animales de entrenamiento de los folds de las "
        f"semillas {context['selection_seeds']} (val interno por corral; `selection.csv` y "
        f"`selection.json`). Configuraciones elegidas: {context['selected_note']}.",
        f"- **Entrenamiento:** lr {context['training']['lr']}, weight_decay "
        f"{context['training']['weight_decay']}, batch {context['training']['batch_size']}, "
        f"máx. {context['training']['max_epochs']} épocas, paciencia "
        f"{context['training']['patience']}, dispositivo `{context['training']['device']}`.",
        "",
        "## Criterio de salida de F4",
        "",
        *_f4_declaration(aggregates, baselines, variants),
        "",
        "## Resultados globales (predicción fuera de fold)",
        "",
        *_global_table(aggregates, baselines, "fraction_r2", arms, variants),
        "",
        *_global_table(aggregates, baselines, "fraction_mae_pp", arms, variants),
        "",
        *_log_total_table(aggregates, baselines, arms, variants),
        "",
        *_global_table(aggregates, baselines, "reconstructed_r2", arms, variants),
        "",
        *_global_table(aggregates, baselines, "reconstructed_mae", arms, variants),
        "",
        "## Resultados por día de muestreo",
        "",
        "R² macro de las fracciones y R² de log T por día (media ± std entre folds). Dentro de "
        "un día la varianza del objetivo es pequeña y el R² puede ser muy negativo; la "
        "comparación útil es la del global y la del MAE por día (`metrics.csv`).",
        "",
        "| Modelo | Día | R² macro fracciones | R² log T |",
        "|---|---|---:|---:|",
    ]
    for day in context["days"]:
        for arm in arms:
            for variant in variants:
                aggregate = aggregates.get((variant, arm))
                if aggregate is None:
                    continue
                frac = _aggregate_rows(aggregate, variant, "fraction_r2", day)
                log_t = _aggregate_rows(aggregate, variant, "log_total_r2", day)
                if not frac:
                    continue
                lines.append(
                    f"| `{_variant_label(variant, arm)}` | {day} | {_fmt_pm(frac, 'average')} | "
                    f"{_fmt_pm(log_t, 'log_total')} |"
                )
    lines += [
        "",
        "## Ablación de aristas `inferred` (V-01, respuesta 3)",
        "",
        context["ablation_note"],
        "",
        "## Advertencias y limitaciones",
        "",
        "- **Taxones aislados (S-04 pendiente).** Sin nodos de función ni aristas que los "
        "conecten, los 1315 taxones de cada grafo no reciben mensajes: la GNN solo puede "
        "usarlos por la lectura media, igual que un baseline tabular. La ventaja estructural "
        "de la GNN queda sin probar hasta cerrar S-04 (limitación L2/L3).",
        "- **Desbalance 34/15/7 (L1).** Toda comparación entre tratamientos es exploratoria.",
        "- **Dieta confundida con el día de muestreo** y **efecto del ensayo** "
        "(`trial_code`, que entra como covariable del huésped desde #147, sección 6 de la "
        "respuesta): ver `reports/baselines/d1_composition/report.md`.",
        "- **Folds sin el día 21.** En las semillas 3, 7 y 8 un fold no tiene animales del "
        "día 21; esas celdas se omiten de la agregación (`_n` en `metrics.csv`).",
        "- La incertidumbre informada es la dispersión entre folds y semillas del plan; la "
        "semilla de entrenamiento de la GNN es una por fold (derivada), así que el ruido de "
        "optimización no se marginaliza como en A45-5.",
        "",
        "## Archivos",
        "",
        "- `metrics.csv`: agregado por variante, brazo, grupo y métrica (`_mean`, `_std`, "
        "`_seed_std`, `_n`).",
        "- `fold_metrics.csv`: una fila por semilla, fold, variante, brazo, grupo y métrica.",
        "- `predictions.csv`: salida `(z_1, z_2, ln T)` por animal de test.",
        "- `folds.csv`: diagnóstico por fold (mejor época, épocas, tamaños, errores).",
        "- `selection.csv` / `selection.json`: grilla de A45-5 bajo CV y elección por variante.",
        "- `run.json`: procedencia, configuración y duración.",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--graphs-dir", type=Path, default=DEFAULT_GRAPHS)
    parser.add_argument("--config", type=Path, default=DEFAULT_TRAINING_CONFIG)
    parser.add_argument("--model-configs", type=Path, default=DEFAULT_MODEL_CONFIGS)
    parser.add_argument("--baseline-metrics", type=Path, default=DEFAULT_BASELINE_METRICS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--variants", nargs="+", choices=MODEL_VARIANTS, default=list(MODEL_VARIANTS)
    )
    parser.add_argument("--arms", nargs="+", choices=list(ARMS), default=list(ARMS))
    parser.add_argument(
        "--seeds",
        nargs="+",
        type=int,
        default=None,
        help="Semillas del plan a evaluar (por defecto, todas).",
    )
    parser.add_argument(
        "--selection-seeds",
        type=int,
        default=2,
        help="Semillas del plan usadas en la selección de hiperparámetros (0 la omite).",
    )
    parser.add_argument(
        "--train-seed-base",
        type=int,
        default=42000,
        help="Base de la semilla de entrenamiento de cada fold: base + semilla_plan*100 + fold.",
    )
    parser.add_argument(
        "--inner-folds",
        type=int,
        default=5,
        help="Folds del reparto interno del train de cada fold (val interno = 1/inner-folds "
        "de los corrales).",
    )
    parser.add_argument("--max-epochs", type=int, default=None)
    parser.add_argument("--patience", type=int, default=None)
    parser.add_argument("--device", type=str, default=None)
    args = parser.parse_args(argv)

    started = time.monotonic()
    try:
        sources = load_sources(args.sources)
        cohort = load_cohort(sources)
        metadata_rows = _load_metadata(sources[METADATA_SOURCE].path_or_url)
        cohort_ids = frozenset(cohort.sample_ids)
        graphs, metadata, evidence_counts = _prepare_graphs(args.graphs_dir, cohort_ids)
        plan = PenFoldPlan.load(args.plan)
        if args.seeds is not None:
            unknown = sorted(set(args.seeds) - set(plan.seeds))
            if unknown:
                raise ValueError(f"Semillas que no están en el plan: {unknown}.")
            plan = PenFoldPlan(
                dataset_id=plan.dataset_id,
                k=plan.k,
                seeds=tuple(args.seeds),
                assignments={s: plan.assignments[s] for s in args.seeds},
                cohort=dict(plan.cohort),
            )
        missing = [s for s in plan.sample_ids if s not in graphs]
        if missing:
            raise ValueError(
                f"Animales del plan sin grafo entregable con los tres AGCC: {missing}."
            )
        pens = {s: metadata_rows[s]["pen_code"] for s in plan.sample_ids}
        diets = {s: metadata_rows[s]["diet_treatment_code"] for s in plan.sample_ids}
        days = {s: metadata_rows[s]["sampling_day"] for s in plan.sample_ids}
        overrides = {
            key: value
            for key, value in (
                ("max_epochs", args.max_epochs),
                ("patience", args.patience),
                ("device", args.device),
            )
            if value is not None
        }
        config = load_training_config(args.config).model_copy(update=overrides)
        base_configs = {
            variant: load_model_config(args.model_configs / f"{variant}.yaml")
            for variant in args.variants
        }
    except (FileNotFoundError, KeyError, ValueError) as error:
        print(f"No se pudo preparar la evaluación: {error}", file=sys.stderr)
        return EXIT_INPUT

    args.output.mkdir(parents=True, exist_ok=True)
    inferred_edges = evidence_counts.get(INFERRED_STATUS, 0)
    arms = list(args.arms)
    if inferred_edges == 0 and WITHOUT_INFERRED in arms:
        # Sin aristas inferred, los dos brazos son el mismo grafo: se entrena una sola vez y
        # el reporte declara que la ablación no tiene efecto medible todavía (S-04 pendiente).
        arms.remove(WITHOUT_INFERRED)
        print(
            "Los grafos no tienen aristas inferred: el brazo without_inferred coincide con "
            "with_inferred y no se repite.",
            flush=True,
        )
    print(
        f"Grafos: {len(graphs)} animales; aristas por evidencia: {evidence_counts}.",
        flush=True,
    )

    if args.selection_seeds > 0:
        selected = _run_selection(
            variants=args.variants,
            plan=plan,
            selection_seeds=args.selection_seeds,
            graphs=graphs,
            pens=pens,
            diets=diets,
            base_configs=base_configs,
            metadata=metadata,
            config=config,
            train_seed_base=args.train_seed_base,
            output=args.output,
            inner_folds=args.inner_folds,
        )
    else:
        selected = base_configs

    evaluations = _run_evaluation(
        variants=args.variants,
        arms=arms,
        model_configs=selected,
        plan=plan,
        graphs=graphs,
        pens=pens,
        diets=diets,
        days=days,
        metadata=metadata,
        config=config,
        train_seed_base=args.train_seed_base,
        output=args.output,
        inner_folds=args.inner_folds,
    )
    if not evaluations:
        print("Ningún fold terminó con éxito; no se puede escribir el reporte.", file=sys.stderr)
        return EXIT_INPUT

    aggregates: dict[tuple[str, str], EvaluationReport] = {}
    all_rows: list[MetricRow] = []
    for (variant, arm), fold_evals in sorted(evaluations.items()):
        reports = {(ev.seed, ev.fold): ev.report for ev in fold_evals}
        aggregate = aggregate_fold_reports(reports)
        aggregates[(variant, arm)] = aggregate
        label = _variant_label(variant, arm)
        for row in aggregate.rows:
            all_rows.append(
                MetricRow(
                    label, row.metric, row.targets, row.average, split=CV_SPLIT, group=row.group
                )
            )
    combined = EvaluationReport(rows=tuple(all_rows))
    (args.output / "metrics.csv").write_text(
        combined.to_csv().replace("\r\n", "\n"), encoding="utf-8"
    )

    baselines = None
    if args.baseline_metrics.is_file():
        baselines = _load_baseline_metrics(args.baseline_metrics)

    if inferred_edges == 0:
        ablation_note = (
            "**Los grafos actuales de D1 no tienen ninguna arista `inferred`** (solo "
            "`metabolite → measured_in → host`, observada; los enlaces taxón–función–metabolito "
            "están pendientes, S-04). Por eso los brazos `with_inferred` y `without_inferred` "
            "son idénticos y el segundo no se repitió: la ablación queda implementada en "
            "`drop_inferred_edges` y verificada en tests, pero su efecto solo podrá medirse "
            "cuando el grafo incluya aristas inferidas."
        )
    elif WITHOUT_INFERRED in arms:
        ablation_note = (
            f"Los grafos tienen {inferred_edges} aristas `inferred`; el brazo "
            "`without_inferred` las elimina antes de entrenar. Comparar las dos columnas de "
            "las tablas globales."
        )
    else:
        ablation_note = (
            f"Esta corrida solo incluye el brazo `with_inferred`; los grafos tienen "
            f"{inferred_edges} aristas `inferred`."
        )

    selected_note = ", ".join(
        f"`{variant}` {config.hidden_channels}×{config.num_layers}"
        for variant, config in sorted(selected.items())
    )
    cohort_summary = cohort.summary()
    context: dict[str, Any] = {
        "elapsed_s": time.monotonic() - started,
        "n_samples": len(graphs),
        "cohort_version": cohort_summary["version"],
        "min_ssu_reads": cohort.min_ssu_reads,
        "k": plan.k,
        "seeds": list(plan.seeds),
        "plan_path": args.plan.relative_to(REPO_ROOT)
        if args.plan.is_absolute() and args.plan.is_relative_to(REPO_ROOT)
        else args.plan,
        "plan_sha256": _sha256(args.plan),
        "train_seed_base": args.train_seed_base,
        "selection_seeds": list(plan.seeds)[: args.selection_seeds],
        "selected_note": selected_note,
        "training": {
            "lr": config.lr,
            "weight_decay": config.weight_decay,
            "batch_size": config.batch_size,
            "max_epochs": config.max_epochs,
            "patience": config.patience,
            "device": config.device,
        },
        "aggregates": aggregates,
        "baselines": baselines,
        "variants": args.variants,
        "arms": arms,
        "days": sorted(
            set(days.values()), key=lambda d: (0, float(d)) if d.isdigit() else (1, 0.0)
        ),
        "ablation_note": ablation_note,
    }
    report_md = build_report_markdown(context)
    (args.output / "report.md").write_text(report_md, encoding="utf-8", newline="\n")

    run_meta = {
        "issue": 142,
        "dataset_id": "D1_holofood",
        "command": "python scripts/evaluate_gnn_d1_composition.py",
        "argv": list(argv) if argv is not None else sys.argv[1:],
        "sources": str(args.sources),
        "sources_sha256": _sha256(args.sources),
        "plan": str(args.plan),
        "plan_sha256": context["plan_sha256"],
        "graphs_dir": str(args.graphs_dir),
        "cohort": cohort_summary,
        "compositional_target_version": COMPOSITIONAL_TARGET_VERSION,
        "variants": args.variants,
        "arms": arms,
        "seeds": list(plan.seeds),
        "k": plan.k,
        "selection_seeds": context["selection_seeds"],
        "selected_configs": {
            variant: dict(model_config.model_dump())
            for variant, model_config in sorted(selected.items())
        },
        "training_config": json.loads(config.model_dump_json()),
        "train_seed_base": args.train_seed_base,
        "inner_folds": args.inner_folds,
        "inferred_edges": inferred_edges,
        "evidence_counts": evidence_counts,
        "folds_ok": sum(len(v) for v in evaluations.values()),
        "elapsed_seconds": round(time.monotonic() - started, 1),
    }
    (args.output / "run.json").write_text(
        json.dumps(run_meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )

    print(report_md)
    print(f"Archivos generados en {args.output.as_posix()}", flush=True)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
