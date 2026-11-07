"""Comparación técnica de la identidad de los taxones en D1 (#266, decisión de #239, sección 4).

Entrena las GNN en todos los folds del plan versionado con el objetivo composicional, en cuatro
brazos, y los compara con `ridge` sobre tablas que tienen la misma información:

- `gnn_actual`: sin nodos `function`, `a_t` y encoder lineal. Referencia: bloque `taxon` constante.
- `gnn_mlp`: sin nodos `function`, `MLP(a_t)`. Solo la forma de la distribución.
- `gnn_functional`: con `has_capacity` y `produces`, `a_t` y encoder lineal. La ruta funcional.
- `gnn_functional_lineage`: con esas aristas y `a_t · onehot(familia)`. Lo que se adoptó.
- `ridge_design`: tabla con el diseño. Sin microbioma.
- `ridge_family`: diseño y perfil por familia. Un modelo tabular con la misma información.
- `ridge_genus`: diseño y abundancias de los 876 taxones. La tabla ancha.

Los brazos usan los mismos folds y la misma semilla de entrenamiento por fold. Todo lo que se ajusta
(vocabulario de familias, escalados, `alpha` y detención temprana) usa solo el train del fold.

Escribe en `--output` (por defecto `reports/gnn/d1_taxon_identity/`):

- `report.md`: método, métricas por brazo, comparaciones pareadas y conclusión;
- `metrics.csv`: métricas agregadas entre folds y semillas;
- `fold_metrics.csv`: una fila por semilla, fold, modelo, brazo, grupo y métrica, incremental;
- `folds.csv`: estado, épocas y tamaño del vocabulario de cada fold, incremental;
- `paired.csv`: las comparaciones pareadas;
- `run.json`: configuración, plan, cohorte, Git, entorno y duración.

Uso:

    python scripts/build_graph.py --save-graphs --overwrite   # si no están guardados
    python scripts/evaluate_taxon_identity.py --device cuda
    python scripts/evaluate_taxon_identity.py --device cuda --resume   # retoma una corrida cortada

Requiere los extras `graph` y `baselines`. Código de salida: `0` si escribió el reporte; `2` si
faltan datos o ningún fold terminó.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any, Final

from nutrigraphdt.models.baselines import LinearBaselineConfig
from nutrigraphdt.models.composition import compositional_target
from nutrigraphdt.models.compositional_baselines import ridge_fold_report
from nutrigraphdt.models.cross_validation import aggregate_fold_reports
from nutrigraphdt.models.gnn.base import GraphMetadata
from nutrigraphdt.models.gnn.factory import load_model_config
from nutrigraphdt.models.metrics import EvaluationReport, MetricRow
from nutrigraphdt.models.paired_comparison import paired_comparison
from nutrigraphdt.models.training import load_training_config, run_compositional_fold
from nutrigraphdt.models.training.cv_inputs import CVInputs, load_d1_cv_inputs
from nutrigraphdt.models.training.taxon_identity import (
    TaxonIdentityConfig,
    TaxonLineageEncoder,
    group_profile,
    without_functional_structure,
)
from nutrigraphdt.models.training.tracking import environment_info, git_info

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = REPO_ROOT / "configs" / "sources.json"
DEFAULT_GRAPHS = REPO_ROOT / "artifacts" / "graphs" / "D1_holofood"
DEFAULT_PLAN = REPO_ROOT / "configs" / "splits" / "d1_holofood_cv.json"
DEFAULT_TRAINING_CONFIG = REPO_ROOT / "configs" / "training" / "default.json"
DEFAULT_MODEL_CONFIGS = REPO_ROOT / "configs" / "models"
DEFAULT_LINEAR_CONFIG = REPO_ROOT / "configs" / "baselines" / "linear.json"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "gnn" / "d1_taxon_identity"
BASELINE_METRICS = REPO_ROOT / "reports" / "baselines" / "d1_composition" / "metrics.csv"

VARIANTS: Final = ("homo_sage", "hetero_sage", "hetero_gat")
TRAIN_SEED_BASE: Final = 42000
"""La misma base de semillas de entrenamiento de #142 y #185."""

ACTUAL: Final = "gnn_actual"
MLP: Final = "gnn_mlp"
FUNCTIONAL: Final = "gnn_functional"
LINEAGE: Final = "gnn_functional_lineage"
GNN_ARMS: Final = (ACTUAL, MLP, FUNCTIONAL, LINEAGE)
RIDGE_DESIGN: Final = "ridge_design"
RIDGE_FAMILY: Final = "ridge_family"
RIDGE_GENUS: Final = "ridge_genus"
RIDGE_ARMS: Final = (RIDGE_DESIGN, RIDGE_FAMILY, RIDGE_GENUS)
TABULAR: Final = "tabular"
"""Valor de `model` de las filas de `ridge`, que no dependen de la variante de GNN."""

METRICS: Final = ("fraction_mae_pp", "fraction_r2", "log_total_mae", "reconstructed_mae")
HIGHER_IS_BETTER: Final = frozenset({"fraction_r2"})
"""Métricas de D-03; la primaria del protocolo es la primera."""

FOLD_HEADER: Final = ["seed", "fold", "model", "arm"]
METRIC_COLUMNS: Final = [
    "split",
    "group",
    "metric",
    "acetate",
    "propionate",
    "butyrate",
    "log_total",
    "average",
]
TARGET_COLUMNS: Final = ("acetate", "propionate", "butyrate", "log_total")
FOLDS_HEADER: Final = [
    *FOLD_HEADER,
    "train_seed",
    "status",
    "best_epoch",
    "epochs_run",
    "n_train",
    "n_inner_val",
    "n_test",
    "vocabulary_size",
    "duration_seconds",
    "error",
]

COVERAGE: Final = (
    ("Acetato", 35, 36.1, 16.1),
    ("n-Butirato", 14, 35.8, 16.0),
    ("Propionato", 7, 2.1, 0.9),
)
"""Cobertura de la ruta por AGCC, de `docs/research/decision_minimal_graph_D1.md`, sección 5."""

EXIT_OK: Final = 0
EXIT_INPUT: Final = 2

Key = tuple[str, str]
FoldReports = dict[Key, dict[tuple[int, int], EvaluationReport]]


def _append(path: Path, header: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(header), lineterminator="\n")
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def _record_fold(
    output: Path, key: Mapping[str, Any], report: EvaluationReport, fold_row: Mapping[str, Any]
) -> None:
    _append(
        output / "fold_metrics.csv",
        [*FOLD_HEADER, *METRIC_COLUMNS],
        [{**key, **record} for record in report.to_records()],
    )
    _append(output / "folds.csv", FOLDS_HEADER, [{**key, **fold_row}])


def _load_done(output: Path) -> FoldReports:
    """Reportes por fold de una corrida anterior, para `--resume`."""
    path = output / "fold_metrics.csv"
    reports: dict[tuple[str, str, int, int], list[MetricRow]] = {}
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            targets = {
                name: float(row[name]) for name in TARGET_COLUMNS if row.get(name) not in ("", None)
            }
            # Las filas de `ridge` llevan como modelo el nombre de su tabla.
            model = TABULAR if row["arm"] in RIDGE_ARMS else row["model"]
            key = (model, row["arm"], int(row["seed"]), int(row["fold"]))
            reports.setdefault(key, []).append(
                MetricRow(
                    model=row["model"],
                    metric=row["metric"],
                    targets=targets,
                    average=float(row["average"]),
                    split=row["split"] or None,
                    group=row["group"] or None,
                )
            )
    done: FoldReports = {}
    for (model, arm, seed, fold), rows in reports.items():
        done.setdefault((model, arm), {})[(seed, fold)] = EvaluationReport(rows=tuple(rows))
    return done


def _graphs_for(inputs: CVInputs, arm: str) -> tuple[Mapping[str, Any], GraphMetadata]:
    if arm in (FUNCTIONAL, LINEAGE):
        return inputs.graphs, inputs.metadata
    graphs = {s: without_functional_structure(g) for s, g in inputs.graphs.items()}
    return graphs, GraphMetadata.from_graphs(graphs.values())


def run_gnn_arms(
    inputs: CVInputs,
    variants: Sequence[str],
    arms: Sequence[str],
    seeds: Sequence[int],
    training: Any,
    identity: TaxonIdentityConfig,
    output: Path,
    done: FoldReports,
) -> None:
    """Entrena cada brazo de GNN en todos los folds y agrega sus reportes a `done`."""
    total = len(variants) * len(arms) * len(seeds) * inputs.plan.k
    count = 0
    for variant in variants:
        base_config = load_model_config(DEFAULT_MODEL_CONFIGS / f"{variant}.yaml")
        for arm in arms:
            graphs, metadata = _graphs_for(inputs, arm)
            model_config = base_config.model_copy(update={"nonlinear_taxon_encoder": arm == MLP})
            for seed in seeds:
                for fold, (train_ids, test_ids) in enumerate(inputs.plan.folds(seed)):
                    count += 1
                    if (seed, fold) in done.get((variant, arm), {}):
                        continue
                    train_seed = TRAIN_SEED_BASE + seed * 100 + fold
                    key = {"seed": seed, "fold": fold, "model": variant, "arm": arm}
                    try:
                        evaluation = run_compositional_fold(
                            seed=seed,
                            fold=fold,
                            model_name=variant,
                            edges_arm=arm,
                            train_ids=train_ids,
                            test_ids=test_ids,
                            graphs=graphs,
                            pens=inputs.pens,
                            diets=inputs.diets,
                            days=inputs.days,
                            model_config=model_config,
                            metadata=metadata,
                            config=training.model_copy(update={"seed": train_seed}),
                            taxon_identity=identity if arm == LINEAGE else None,
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
                        print(f"[{count}/{total}] {variant} {arm} s{seed} f{fold}: ERROR {error}")
                        continue
                    _record_fold(
                        output,
                        key,
                        evaluation.report,
                        {
                            "train_seed": train_seed,
                            "status": "ok",
                            "best_epoch": evaluation.best_epoch,
                            "epochs_run": evaluation.epochs_run,
                            "n_train": evaluation.n_train,
                            "n_inner_val": evaluation.n_inner_val,
                            "n_test": evaluation.n_test,
                            "vocabulary_size": len(evaluation.taxon_vocabulary),
                            "duration_seconds": round(evaluation.duration_seconds, 1),
                        },
                    )
                    done.setdefault((variant, arm), {})[(seed, fold)] = evaluation.report
                    print(
                        f"[{count}/{total}] {variant} {arm} s{seed} f{fold}: "
                        f"{evaluation.epochs_run} épocas, {evaluation.duration_seconds:.0f} s",
                        flush=True,
                    )


def _design_row(graph: Any) -> list[float]:
    return [float(v) for v in (*graph["host"].x[0].tolist(), *graph["diet"].x[0].tolist())]


def _output_row(graph: Any) -> tuple[list[float], tuple[float, float, float]]:
    measured = [float(v) for v in graph.y_graph[0].tolist()]
    return measured, compositional_target(*measured).model_output


def run_ridge_arms(
    inputs: CVInputs,
    seeds: Sequence[int],
    identity: TaxonIdentityConfig,
    linear: LinearBaselineConfig,
    output: Path,
    done: FoldReports,
) -> None:
    """`ridge` sobre el diseño, el perfil por familia y la tabla ancha, en los mismos folds."""
    for seed in seeds:
        for fold, (train_ids, test_ids) in enumerate(inputs.plan.folds(seed)):
            train = [inputs.graphs[s] for s in train_ids]
            test = [inputs.graphs[s] for s in test_ids]
            encoder = TaxonLineageEncoder.fit(train, identity)

            def family(graph: Any, encoder: TaxonLineageEncoder = encoder) -> list[float]:
                profile = group_profile(graph)
                known = [profile.get(group, 0.0) for group in encoder.vocabulary]
                return [*known, sum(profile.values()) - sum(known)]

            tables = {
                RIDGE_DESIGN: _design_row,
                RIDGE_FAMILY: lambda graph, table=family: [*_design_row(graph), *table(graph)],
                RIDGE_GENUS: lambda graph: [
                    *_design_row(graph),
                    *graph["taxon"].x[:, 0].tolist(),
                ],
            }
            for arm, table in tables.items():
                if (seed, fold) in done.get((TABULAR, arm), {}):
                    continue
                report = ridge_fold_report(
                    arm,
                    [table(graph) for graph in train],
                    [_output_row(graph)[1] for graph in train],
                    [inputs.pens[s] for s in train_ids],
                    [table(graph) for graph in test],
                    [_output_row(graph)[0] for graph in test],
                    [inputs.days[s] for s in test_ids],
                    linear,
                    split="test",
                )
                key = {"seed": seed, "fold": fold, "model": TABULAR, "arm": arm}
                _record_fold(
                    output,
                    key,
                    report,
                    {
                        "status": "ok",
                        "n_train": len(train_ids),
                        "n_test": len(test_ids),
                        "vocabulary_size": len(encoder.vocabulary) if arm == RIDGE_FAMILY else 0,
                    },
                )
                done.setdefault((TABULAR, arm), {})[(seed, fold)] = report
        print(f"ridge: semilla {seed} lista.", flush=True)


def _by_fold(reports: Mapping[tuple[int, int], EvaluationReport], metric: str) -> dict:
    return {
        key: float(row.average)
        for key, report in reports.items()
        for row in report.rows
        if row.metric == metric and row.group in (None, "all")
    }


def _comparisons(variants: Sequence[str]) -> list[tuple[Key, Key, str]]:
    pairs: list[tuple[Key, Key, str]] = []
    for variant in variants:
        pairs += [
            ((variant, LINEAGE), (variant, ACTUAL), "Lo adoptado frente a la GNN actual"),
            ((variant, FUNCTIONAL), (variant, ACTUAL), "Aporte de la ruta funcional"),
            ((variant, LINEAGE), (variant, FUNCTIONAL), "Aporte del linaje"),
            ((variant, MLP), (variant, ACTUAL), "Forma de la distribución, sin identidad"),
            ((variant, LINEAGE), (TABULAR, RIDGE_FAMILY), "Lo adoptado frente a ridge por familia"),
            (
                (variant, ACTUAL),
                (TABULAR, RIDGE_DESIGN),
                "GNN actual frente a ridge sobre el diseño",
            ),
        ]
    pairs.append(
        ((TABULAR, RIDGE_FAMILY), (TABULAR, RIDGE_DESIGN), "Perfil por familia frente al diseño")
    )
    pairs.append(((TABULAR, RIDGE_GENUS), (TABULAR, RIDGE_FAMILY), "Tabla ancha frente a familia"))
    return pairs


def paired_rows(done: FoldReports, variants: Sequence[str], ratio: float) -> list[dict[str, Any]]:
    """`brazo − referencia` por fold, para las métricas de D-03."""
    rows: list[dict[str, Any]] = []
    for arm, reference, description in _comparisons(variants):
        if arm not in done or reference not in done:
            continue
        for metric in METRICS:
            first = _by_fold(done[arm], metric)
            second = _by_fold(done[reference], metric)
            keys = sorted(set(first) & set(second))
            if len(keys) < 2:
                continue
            result = paired_comparison({key: first[key] - second[key] for key in keys}, ratio)
            rows.append(
                {
                    "comparison": description,
                    "model": arm[0],
                    "arm": arm[1],
                    "reference_model": reference[0],
                    "reference": reference[1],
                    "metric": metric,
                    "arm_mean": statistics.fmean(first[key] for key in keys),
                    "reference_mean": statistics.fmean(second[key] for key in keys),
                    **result.to_dict(),
                }
            )
    return rows


def _fmt(value: Any, digits: int = 2) -> str:
    return "—" if value in (None, "") else f"{float(value):.{digits}f}"


def _cell(aggregate: EvaluationReport, metric: str) -> str:
    mean = next(
        (
            row.average
            for row in aggregate.rows
            if row.metric == f"{metric}_mean" and row.group in (None, "all")
        ),
        None,
    )
    std = next(
        (
            row.average
            for row in aggregate.rows
            if row.metric == f"{metric}_std" and row.group in (None, "all")
        ),
        None,
    )
    return "—" if mean is None else f"{mean:.2f} ± {std:.2f}" if std is not None else f"{mean:.2f}"


def _baseline_context() -> list[dict[str, str]]:
    if not BASELINE_METRICS.exists():
        return []
    with BASELINE_METRICS.open(encoding="utf-8") as handle:
        return [
            row
            for row in csv.DictReader(handle)
            if row.get("model") == "day_only" and row.get("group") == "all"
        ]


def _significant(row: Mapping[str, Any]) -> bool:
    low, high = float(row["ci_low"]), float(row["ci_high"])
    return low > 0 or high < 0


def _improves(row: Mapping[str, Any]) -> bool:
    better_is_up = row["metric"] in HIGHER_IS_BETTER
    return _significant(row) and (float(row["mean_delta"]) > 0) == better_is_up


def conclusion_lines(paired: Sequence[Mapping[str, Any]], variants: Sequence[str]) -> list[str]:
    """Conclusión escrita de los resultados, con el criterio de la decisión de #239."""
    lines: list[str] = []
    against_family = [
        row
        for row in paired
        if row["arm"] == LINEAGE
        and row["reference"] == RIDGE_FAMILY
        and row["metric"] == "fraction_mae_pp"
    ]
    if any(_improves(row) for row in against_family):
        winners = ", ".join(f"`{row['model']}`" for row in against_family if _improves(row))
        lines.append(
            f"- **La GNN con aristas y linaje supera a `ridge` con la tabla por familia** en "
            f"`fraction_mae_pp`, con un IC 95 % corregido que excluye el cero, en {winners}."
        )
    else:
        lines.append(
            "- **La combinación no supera a `ridge` con la tabla por familia** en "
            "`fraction_mae_pp` (el IC 95 % corregido incluye el cero o favorece a `ridge`, en "
            "todas las variantes). Como pide la decisión de #239, se informa así: **el grafo no "
            "agrega capacidad predictiva en D1 y su aporte queda en la explicabilidad.**"
        )
    for reference, label in ((ACTUAL, "la GNN actual"),):
        rows = [
            row
            for row in paired
            if row["arm"] == LINEAGE
            and row["reference"] == reference
            and row["metric"] == "fraction_mae_pp"
        ]
        better = [row["model"] for row in rows if _improves(row)]
        lines.append(
            f"- Frente a {label}, la combinación mejora `fraction_mae_pp` en: "
            f"{', '.join(f'`{m}`' for m in better) or 'ninguna variante'}."
        )
    family_design = [
        row
        for row in paired
        if row["arm"] == RIDGE_FAMILY
        and row["reference"] == RIDGE_DESIGN
        and row["metric"] == "fraction_mae_pp"
    ]
    if family_design:
        verdict = "mejora" if _improves(family_design[0]) else "no mejora de forma distinguible"
        lines.append(f"- El perfil por familia {verdict} a `ridge` sobre el diseño.")
        if _improves(family_design[0]) and not any(_improves(row) for row in against_family):
            lines.append(
                "- **Hay señal del microbioma que `ridge` capta y la GNN no aprovecha, con la misma "
                "información de entrada.** Por eso, este resultado no permite atribuir la "
                "diferencia solo al grafo: también puede deberse a la arquitectura, a la escala de "
                "las columnas de linaje o al ajuste, que no se buscó por brazo. Ninguna de esas "
                "causas se probó aquí."
            )
    return lines


def _vocabulary_note(sizes: Sequence[int]) -> str:
    if not sizes:
        return "sin folds con linaje"
    if sizes[0] == sizes[-1]:
        return f"{sizes[0]} grupos en todos los folds"
    return f"de {sizes[0]} a {sizes[-1]} grupos por fold"


def build_report(context: Mapping[str, Any]) -> str:
    """`report.md` con el método, las métricas, las comparaciones y la conclusión."""
    aggregates: Mapping[Key, EvaluationReport] = context["aggregates"]
    variants: Sequence[str] = context["variants"]
    lines = [
        "# Identidad de los taxones en D1: comparación técnica (#266)",
        "",
        "Generado con `python scripts/evaluate_taxon_identity.py`, dispositivo "
        f"`{context['device']}` (última ejecución: {context['elapsed'] / 3600:.1f} h).",
        "",
        "## Método",
        "",
        "Implementa la comparación de la "
        "[decisión de #239](../../../docs/research/decision_taxon_identity_D1.md), sección 4.",
        "",
        f"- **Cohorte y folds:** {len(context['samples'])} animales; plan "
        f"`configs/splits/d1_holofood_cv.json` (k = {context['k']}, semillas "
        f"{list(context['seeds'])}), el de #139. Mismos folds y semilla de entrenamiento por fold "
        "en todos los brazos.",
        "- **Grafos:** agregados a género con `has_capacity` y `produces` (#175, #173). Los brazos "
        "`gnn_actual` y `gnn_mlp` quitan los nodos `function` y sus aristas.",
        f"- **Vocabulario de linaje:** prevalencia ≥ {context['identity'].min_prevalence} en el "
        f"train interno del fold y como máximo {context['identity'].top_k} grupos; "
        f"{context['vocabulary_note']}. El test y el val interno no intervienen.",
        "- **Objetivo y métricas:** composicional de D-03, fuera de fold.",
        *([f"- **Procedencia de la corrida:** {context['note']}"] if context.get("note") else []),
        "- **`ridge`:** diseño, diseño y perfil por familia, y diseño y los 876 taxones, con "
        "`alpha` elegido por `GroupKFold` interno por corral. Las tablas salen de los mismos "
        "grafos.",
        "",
        "## Resultados (media ± desviación entre folds y semillas)",
        "",
        "| Modelo | Brazo | `fraction_mae_pp` | `fraction_r2` | `log_total_mae` | "
        "`reconstructed_mae` | Folds |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for key in [
        *(k for k in aggregates if k[0] != TABULAR),
        *(k for k in aggregates if k[0] == TABULAR),
    ]:
        cells = " | ".join(_cell(aggregates[key], metric) for metric in METRICS)
        model = "—" if key[0] == TABULAR else f"`{key[0]}`"
        lines.append(f"| {model} | `{key[1]}` | {cells} | {context['fold_counts'][key]} |")
    baseline = context["day_only"]
    if baseline:
        by_metric = {row["metric"]: row["average"] for row in baseline}
        lines += [
            "",
            "Referencia de #140: `day_only` tiene `fraction_mae_pp` "
            f"{_fmt(by_metric.get('fraction_mae_pp_mean'))} y `fraction_r2` "
            f"{_fmt(by_metric.get('fraction_r2_mean'))}.",
        ]
    lines += [
        "",
        "## Comparaciones pareadas de `fraction_mae_pp`",
        "",
        "`Δ = brazo − referencia`, con el t corregido de Nadeau y Bengio. Valores negativos "
        "favorecen al brazo.",
        "",
        "| Comparación | Modelo | Media brazo | Media referencia | Δ | IC 95 % | p |",
        "|---|---|---:|---:|---:|---|---:|",
    ]
    for row in context["paired"]:
        if row["metric"] != "fraction_mae_pp":
            continue
        model = "—" if row["model"] == TABULAR else f"`{row['model']}`"
        lines.append(
            f"| {row['comparison']} | {model} | {_fmt(row['arm_mean'])} | "
            f"{_fmt(row['reference_mean'])} | {_fmt(row['mean_delta'])} | "
            f"[{_fmt(row['ci_low'])}, {_fmt(row['ci_high'])}] | {_fmt(row['p_value'], 3)} |"
        )
    lines += [
        "",
        "Las demás métricas están en `paired.csv`.",
        "",
        "## Conclusión",
        "",
        *conclusion_lines(context["paired"], variants),
        "",
        "## Cobertura de la ruta (decisión de #256, sección 5)",
        "",
        "Ninguna evaluación de D1 se llama «mecanística»: esta es una evaluación con estructura "
        "funcional anotada.",
        "",
        "| AGCC | Géneros con ruta | % lecturas a género | % del total de lecturas |",
        "|---|---:|---:|---:|",
        *[f"| {name} | {n} | {genus} | {total} |" for name, n, genus, total in COVERAGE],
        "",
        "## Limitaciones",
        "",
        "- Con 56 animales, las diferencias tienen una incertidumbre amplia; el IC corregido "
        "considera que los folds no son independientes.",
        "- Capacidad anotada no es actividad demostrada, y no se afirma ningún efecto de la dieta "
        "a través del microbioma (#258).",
        "- La identidad por familia no distingue géneros de una misma familia, salvo los 38 con "
        "aristas funcionales.",
        "- `top_k` y `min_prevalence` son elecciones de Desarrollo, no valores científicos.",
        "- Los hiperparámetros son los de `configs/models/`, sin búsqueda por brazo.",
        "",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--graphs-dir", type=Path, default=DEFAULT_GRAPHS)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--training-config", type=Path, default=DEFAULT_TRAINING_CONFIG)
    parser.add_argument("--linear-config", type=Path, default=DEFAULT_LINEAR_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS))
    parser.add_argument("--arms", nargs="+", choices=GNN_ARMS, default=list(GNN_ARMS))
    parser.add_argument("--seeds", nargs="+", type=int, default=None)
    parser.add_argument("--max-epochs", type=int, default=None)
    parser.add_argument("--patience", type=int, default=None)
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--resume", action="store_true", help="Retoma los folds ya escritos.")
    parser.add_argument("--note", default="", help="Nota de procedencia para el reporte.")
    args = parser.parse_args(argv)

    started = time.monotonic()
    try:
        inputs = load_d1_cv_inputs(args.sources, args.graphs_dir, args.plan)
        seeds = list(args.seeds if args.seeds is not None else inputs.plan.seeds)
        unknown = sorted(set(seeds) - set(inputs.plan.seeds))
        if unknown:
            raise ValueError(f"Semillas que no están en el plan: {unknown}.")
        updates: dict[str, Any] = {"dataset_id": inputs.dataset_id}
        if args.device:
            updates["device"] = args.device
        if args.max_epochs is not None:
            updates["max_epochs"] = args.max_epochs
        if args.patience is not None:
            updates["patience"] = args.patience
        training = load_training_config(args.training_config).model_copy(update=updates)
        linear = LinearBaselineConfig.load(args.linear_config)
    except (FileNotFoundError, KeyError, ValueError) as error:
        print(f"No se pudo preparar la comparación: {error}", file=sys.stderr)
        return EXIT_INPUT

    identity = TaxonIdentityConfig()
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.resume:
        for name in ("fold_metrics.csv", "folds.csv"):
            (args.output / name).unlink(missing_ok=True)
    done = _load_done(args.output) if args.resume else {}

    run_ridge_arms(inputs, seeds, identity, linear, args.output, done)
    run_gnn_arms(inputs, args.variants, args.arms, seeds, training, identity, args.output, done)

    gnn_done = {key: value for key, value in done.items() if key[0] != TABULAR and value}
    if not gnn_done:
        print("Ningún fold de GNN terminó con éxito.", file=sys.stderr)
        return EXIT_INPUT

    aggregates = {
        key: aggregate_fold_reports(reports) for key, reports in sorted(done.items()) if reports
    }
    with (args.output / "metrics.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["model", "arm", *METRIC_COLUMNS], lineterminator="\n"
        )
        writer.writeheader()
        for (model, arm), aggregate in aggregates.items():
            for record in aggregate.to_records():
                writer.writerow({"model": model, "arm": arm, **record})

    k = inputs.plan.k
    ratio = statistics.fmean(
        len(test) / len(train) for seed in seeds for train, test in inputs.plan.folds(seed)
    )
    paired = paired_rows(done, args.variants, ratio)
    if paired:
        with (args.output / "paired.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(paired[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(paired)

    with (args.output / "folds.csv").open(encoding="utf-8") as handle:
        fold_rows = list(csv.DictReader(handle))
    sizes = sorted(
        {int(row["vocabulary_size"]) for row in fold_rows if int(row["vocabulary_size"] or 0) > 0}
    )
    elapsed = time.monotonic() - started
    report = build_report(
        {
            "aggregates": aggregates,
            "variants": args.variants,
            "paired": paired,
            "elapsed": elapsed,
            "device": training.device,
            "samples": inputs.plan.sample_ids,
            "k": k,
            "seeds": seeds,
            "identity": identity,
            "vocabulary_note": _vocabulary_note(sizes),
            "fold_counts": {key: len(done[key]) for key in aggregates},
            "day_only": _baseline_context(),
            "note": args.note,
        }
    )
    (args.output / "report.md").write_text(report, encoding="utf-8", newline="\n")
    failed = sum(1 for row in fold_rows if row["status"] != "ok")
    run_info = {
        "issue": 266,
        "dataset_id": inputs.dataset_id,
        "command": "python scripts/evaluate_taxon_identity.py " + " ".join(argv or sys.argv[1:]),
        "plan": str(args.plan.relative_to(REPO_ROOT))
        if args.plan.is_absolute() and args.plan.is_relative_to(REPO_ROOT)
        else str(args.plan),
        "plan_version": inputs.plan.version,
        "cohort": dict(inputs.cohort),
        "seeds": seeds,
        "variants": list(args.variants),
        "arms": list(args.arms),
        "identity": asdict(identity),
        "training_config": training.model_dump(mode="json"),
        "train_seed_base": TRAIN_SEED_BASE,
        "folds_failed": failed,
        "elapsed_seconds": round(elapsed, 1),
        "resumed": args.resume,
        "note": args.note,
        "git": git_info(REPO_ROOT),
        "environment": environment_info(training.device),
    }
    (args.output / "run.json").write_text(
        json.dumps(run_info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    print(report)
    print(f"Archivos en {args.output} ({elapsed / 3600:.2f} h); folds fallidos: {failed}.")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
