"""Baselines de D1 con el objetivo composicional bajo validación cruzada por corral (#140).

Repite los baselines de A45-2 (`scripts/compare_baselines.py --dataset d1`) con el objetivo
composicional de D-03 (dos log-razones más log T; contrato v2, sección 1) bajo la validación
cruzada por corral de #139 (`configs/splits/d1_holofood_cv.json`), y agrega `day_only` (solo el
día de muestreo) y `ridge_design` (ridge sobre los factores del diseño, comparable con la
Tabla 5 de la respuesta de Investigación del 16-10-2026).

Lee la descarga registrada en `configs/sources.json` (sin descargar nada), aplica la cohorte
oficial de `configs/cohorts/d1_holofood.json` y escribe en `--output` (por defecto
`reports/baselines/d1_composition/`):

- `report.md`: reporte con las tablas globales y por día, la comparación con la Tabla 5 y las
  advertencias de la sección 6 de la respuesta de Investigación.
- `metrics.csv`: métricas agregadas (media, desviación entre folds y entre semillas, n).
- `fold_metrics.csv`: métricas de cada (semilla, fold), globales y por día.
- `selections.csv`: hiperparámetros elegidos por la selección interna de cada fold.
- `run.json`: metadatos de la ejecución (procedencia, configuración, duración).

Uso:

    pip install -e ".[dev,baselines]"
    python scripts/compare_baselines_d1_composition.py

Código de salida: `0` si escribió el reporte; `2` si faltan datos o la cohorte no coincide con
el plan de folds.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from nutrigraphdt.data.cohort import load_cohort
from nutrigraphdt.data.config import load_sources
from nutrigraphdt.data.integration import attach_sample_context
from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader
from nutrigraphdt.data.pipeline import DataPipeline
from nutrigraphdt.models.baselines import LinearBaselineConfig, TreeBaselineConfig
from nutrigraphdt.models.composition import ALL_DAYS, COMPOSITIONAL_TARGET_VERSION
from nutrigraphdt.models.compositional_baselines import (
    CV_SPLIT,
    DAY_ONLY_NAME,
    DEFAULT_INNER_FOLDS,
    DESIGN_RIDGE_NAME,
    INVESTIGATION_TABLE5,
    MODEL_NAMES,
    aggregate_rows,
    prepare_compositional_data,
    run_compositional_baselines,
)
from nutrigraphdt.models.cross_validation import PenFoldPlan
from nutrigraphdt.models.metrics import EvaluationReport, MetricRow
from nutrigraphdt.models.tabular import build_tabular_dataset

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = REPO_ROOT / "configs" / "sources.json"
DEFAULT_PLAN = REPO_ROOT / "configs" / "splits" / "d1_holofood_cv.json"
DEFAULT_LINEAR_CONFIG = REPO_ROOT / "configs" / "baselines" / "linear.json"
DEFAULT_TREE_CONFIG = REPO_ROOT / "configs" / "baselines" / "trees.json"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "baselines" / "d1_composition"
METADATA_SOURCE = "D1_holofood_metadata"

EXIT_OK = 0
EXIT_INPUT = 2

DIET_LABELS: Mapping[str, str] = {
    "CC": "Control",
    "CO": "Probiótico",
    "CE": "Fitobiótico",
}

METRIC_LABELS: Mapping[str, str] = {
    "fraction_r2": "R² de la fracción",
    "fraction_mae_pp": "MAE de la fracción (puntos porcentuales)",
    "log_total_r2": "R² de log T",
    "log_total_mae": "MAE de log T",
    "reconstructed_r2": "R² de la cantidad reconstruida (mmol/kg)",
    "reconstructed_mae": "MAE de la cantidad reconstruida (mmol/kg)",
}

TABLE5_ROWS: tuple[tuple[str, str, str], ...] = (
    ("reconstructed_r2", "acetate", "Acetato, cantidad"),
    ("reconstructed_r2", "propionate", "Propionato, cantidad"),
    ("reconstructed_r2", "butyrate", "Butirato, cantidad"),
    ("reconstructed_r2", "average", "Promedio macro, cantidad"),
    ("fraction_r2", "acetate", "Acetato, fracción"),
    ("fraction_r2", "propionate", "Propionato, fracción"),
    ("fraction_r2", "butyrate", "Butirato, fracción"),
    ("fraction_r2", "average", "Promedio macro, fracción"),
    ("log_total_r2", "log_total", "Total, log T"),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fmt(value: float, digits: int = 2) -> str:
    return "—" if math.isnan(value) else f"{value:.{digits}f}"


def _fmt_pm(row: Mapping[str, MetricRow], target: str, digits: int = 2) -> str:
    """`media ± std` de una celda agregada; `—` si la métrica no está."""
    mean = row.get("mean")
    if mean is None:
        return "—"
    value = mean.targets.get(target, math.nan) if target != "average" else mean.average
    std_row = row.get("std")
    std = (
        (std_row.targets.get(target, math.nan) if target != "average" else std_row.average)
        if std_row
        else math.nan
    )
    if math.isnan(std):
        return _fmt(value, digits)
    return f"{_fmt(value, digits)} ± {_fmt(std, digits)}"


def _metric_table(
    aggregate: EvaluationReport, base_metric: str, groups: Sequence[str]
) -> list[str]:
    """Tabla por modelo y grupo de una métrica agregada: media ± std por AGCC y macro."""
    rows = [
        f"### {METRIC_LABELS[base_metric]}",
        "",
        "| Modelo | Grupo | Acetato | Propionato | Butirato | Macro |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for group in groups:
        label = "Global" if group == ALL_DAYS else f"Día {group}"
        for model in MODEL_NAMES:
            cells = aggregate_rows(aggregate, model, base_metric, group)
            if not cells:
                continue
            rows.append(
                f"| `{model}` | {label} | "
                + " | ".join(
                    _fmt_pm(cells, target)
                    for target in ("acetate", "propionate", "butyrate", "average")
                )
                + " |"
            )
    return rows


def _log_total_table(aggregate: EvaluationReport, groups: Sequence[str]) -> list[str]:
    rows = [
        "### log T (total de los tres AGCC, mmol/kg de digesta fresca)",
        "",
        "| Modelo | Grupo | R² | MAE |",
        "|---|---|---:|---:|",
    ]
    for group in groups:
        label = "Global" if group == ALL_DAYS else f"Día {group}"
        for model in MODEL_NAMES:
            r2 = aggregate_rows(aggregate, model, "log_total_r2", group)
            mae = aggregate_rows(aggregate, model, "log_total_mae", group)
            if not r2:
                continue
            rows.append(
                f"| `{model}` | {label} | {_fmt_pm(r2, 'log_total')} | "
                f"{_fmt_pm(mae, 'log_total')} |"
            )
    return rows


def _table5_comparison(aggregate: EvaluationReport) -> list[str]:
    """Comparación del `ridge_design` con la Tabla 5 de Investigación (columna Cohorte de 59)."""
    rows = [
        "| Objetivo (R² fuera de fold) | Tabla 5, cohorte de 59 | "
        f"`{DESIGN_RIDGE_NAME}`, cohorte de 56 |",
        "|---|---:|---:|",
    ]
    for metric, target, label in TABLE5_ROWS:
        reference = INVESTIGATION_TABLE5[metric].get(target, math.nan)
        cells = aggregate_rows(aggregate, DESIGN_RIDGE_NAME, metric, ALL_DAYS)
        ours = _fmt_pm(cells, target)
        rows.append(f"| {label} | {_fmt(reference)} | {ours} |")
    return rows


def build_report_markdown(context: Mapping[str, Any], aggregate: EvaluationReport) -> str:
    """Reporte completo: método, advertencias, resultados y comparación con la Tabla 5."""
    days = context["days"]
    lines: list[str] = [
        "# Baselines de D1 con objetivo composicional y validación cruzada por corral (#140)",
        "",
        f"Generado con `python scripts/compare_baselines_d1_composition.py` en "
        f"{context['elapsed_s']:.0f} s, sobre la descarga de D1 del {context['retrieved_at']}.",
        "",
        "## Método",
        "",
        f"- **Cohorte:** {context['cohort_size']} animales de la cohorte oficial "
        f"`{context['cohort_version']}` (≥ {context['min_ssu_reads']} lecturas SSU): "
        + ", ".join(
            f"{count} {DIET_LABELS.get(diet, diet)}" for diet, count in context["animals_by_diet"]
        )
        + ".",
        "- **Objetivo (D-03, contrato v2 §1, transformación v"
        f"{COMPOSITIONAL_TARGET_VERSION}`):** `z_1 = ln(propionato/acetato)`, "
        "`z_2 = ln(butirato/acetato)` y `ln T`, con `T = acetato + propionato + n-butirato` "
        "calculado por Desarrollo (no el «AGCC totales» del portal). Ningún animal de la "
        "cohorte tiene un AGCC igual a cero; si apareciera uno, quedaría sin objetivo "
        "composicional, sin pseudoconteo.",
        f"- **Validación (D-07, #139):** `StratifiedGroupKFold` agrupado por corral y "
        f"estratificado por dieta, k = {context['k']}, semillas {context['seeds'][0]} a "
        f"{context['seeds'][-1]} (plan `{context['plan_path']}`, sha256 "
        f"`{context['plan_sha256'][:12]}…`). Cada celda es la media ± la desviación estándar "
        "entre los 50 folds (10 semillas × 5 folds); la dispersión entre semillas está en "
        "`metrics.csv` (sufijo `_seed_std`).",
        "- **Ajuste sin fuga:** en cada fold, el escalado y la selección de hiperparámetros "
        f"(`GroupKFold` interno por corral, {context['inner_folds']} folds, grillas de "
        "`configs/baselines/`, el mismo criterio `neg_root_mean_squared_error` de A45-2 sobre "
        "las tres salidas) se ajustan solo con los animales de entrenamiento del fold.",
        "- **Modelos:** `dummy_mean` (media del entrenamiento), `day_only` (media del "
        "entrenamiento del mismo día de muestreo; solo usa el día), `ridge_design` (ridge "
        "sobre los factores del diseño: dieta, ensayo, día, sexo y raza en one-hot, "
        f"{len(context['design_features'])} columnas) y los baselines de A45-2 (`ridge`, "
        f"`elasticnet`, `random_forest`, `hist_gradient_boosting`) sobre la tabla completa "
        f"({context['n_features']} columnas: abundancias SSU, dieta y covariables del huésped).",
        "",
        "## Advertencias (respuesta de Investigación del 16-10-2026, sección 6; L1 del 25-10-2026)",
        "",
        "- **Desbalance 34/15/7 (L1).** La cohorte oficial de 56 animales tiene 34 Control, "
        "15 Probiótico y 7 Fitobiótico (no 37/15/7: es la cohorte de 56, limitación L1 de la "
        "respuesta del 25-10-2026). Toda comparación entre tratamientos es **exploratoria**.",
        "- **Dieta confundida con el día de muestreo.** " + context["day_diet_note"],
        "- **Efecto del ensayo.** El ensayo (`trial_code`) aporta 13 puntos de R² a "
        "log(propionato/acetato) sin que cambie la dieta (D-03); `ridge_design` lo captura y "
        "no separa dieta de ensayo.",
        "- **Folds sin el día 21.** En las semillas 3, 7 y 8 del plan un fold no tiene "
        "animales del día 21 (véase `reports/cv/d1_pen_folds.md`); esas celdas se omiten de "
        "la agregación y el sufijo `_n` de `metrics.csv` muestra 47 folds en lugar de 50.",
        "",
        "## Resultados globales (predicción fuera de fold)",
        "",
        *_metric_table(aggregate, "fraction_r2", [ALL_DAYS]),
        "",
        *_metric_table(aggregate, "fraction_mae_pp", [ALL_DAYS]),
        "",
        *_log_total_table(aggregate, [ALL_DAYS]),
        "",
        *_metric_table(aggregate, "reconstructed_r2", [ALL_DAYS]),
        "",
        *_metric_table(aggregate, "reconstructed_mae", [ALL_DAYS]),
        "",
        "## Resultados por día de muestreo",
        "",
        "R² macro de las fracciones y R² de log T por día. Las métricas completas por día "
        "están en `metrics.csv` y `fold_metrics.csv`. Dentro de un día la varianza del "
        "objetivo es pequeña, así que el denominador del R² tiende a cero y los valores "
        "pueden ser muy negativos (día 7 y log T del día 21); la comparación útil entre "
        "modelos es la del global y la del MAE por día.",
        "",
        "| Modelo | Día | R² macro fracciones | R² log T | folds (n) |",
        "|---|---|---:|---:|---:|",
    ]
    for day in days:
        for model in MODEL_NAMES:
            frac = aggregate_rows(aggregate, model, "fraction_r2", day)
            log_t = aggregate_rows(aggregate, model, "log_total_r2", day)
            if not frac:
                continue
            n = frac.get("n")
            n_folds = "—" if n is None or math.isnan(n.average) else f"{n.average:.0f}"
            lines.append(
                f"| `{model}` | {day} | {_fmt_pm(frac, 'average')} | "
                f"{_fmt_pm(log_t, 'log_total')} | {n_folds} |"
            )
    lines += [
        "",
        "## Comparación con la Tabla 5 de la respuesta de Investigación (16-10-2026)",
        "",
        "La Tabla 5 informa el R² fuera de fold de un ridge sobre los factores del diseño, "
        "con el mismo método de validación (StratifiedGroupKFold por corral, k = 5, 10 "
        "semillas), sobre su cohorte de 59 animales. Aquí se compara con `ridge_design` sobre "
        "la cohorte oficial de 56.",
        "",
        *_table5_comparison(aggregate),
        "",
        "**Causas de las diferencias esperables.** No se espera una igualdad exacta: (1) la "
        "Tabla 5 se calculó sobre 59 animales, antes de aplicar a la vez la exclusión de "
        "SAMEA112905124 y el umbral de 1000 lecturas (H-01/R-04: la cohorte oficial quedó en "
        "56); (2) la asignación de folds es la de este repositorio "
        "(`configs/splits/d1_holofood_cv.json`), porque `d07_corrales.py` de Investigación aún "
        "no está versionado (R-06); (3) el alpha del ridge se elige aquí por validación cruzada "
        "interna en cada fold (grilla de `configs/baselines/linear.json`), mientras que el "
        "procedimiento de selección de la Tabla 5 no está publicado; y (4) el día entra como "
        "variable categórica (one-hot). Las cantidades de la Tabla 5 en µmol/g equivalen a "
        "mmol/kg (factor 1, V-06) y se comparan con la cantidad reconstruida T × p.",
        "",
        "## El día de muestreo frente al diseño completo",
        "",
        "Investigación midió que el día aporta 25 de los 47 puntos de R² del diseño en "
        "log(propionato/acetato) (D-03, cohorte de 59). En esta corrida, el R² de la fracción "
        "de propionato es " + context["day_vs_design_note"],
        "",
        "## Preguntas abiertas",
        "",
        "- El aporte exacto del día y del ensayo por objetivo quedará cerrado cuando "
        "Investigación versione `d03_agcc.py` y `d07_corrales.py` en `docs/research/` (R-06, "
        "compromiso del 27-10-2026); entonces la comparación con la Tabla 5 puede hacerse "
        "sobre la misma asignación de folds.",
        "- `ridge`, `elasticnet` y los árboles usan la tabla completa (1315 taxones SSU y los "
        "factores del diseño); si no superan a `ridge_design`, el microbioma perfilado por SSU "
        "no aporta señal fuera del corral para este objetivo (limitación L2: el 55 % de la "
        "abundancia queda en nodos residuales).",
        "",
        "## Archivos",
        "",
        "- `metrics.csv`: agregado por modelo, grupo y métrica (`_mean`, `_std`, `_seed_std`, "
        "`_n`).",
        "- `fold_metrics.csv`: una fila por semilla, fold, modelo, grupo y métrica.",
        "- `selections.csv`: hiperparámetros elegidos en cada fold.",
        "- `run.json`: procedencia, configuración y duración.",
        "",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--linear-config", type=Path, default=DEFAULT_LINEAR_CONFIG)
    parser.add_argument("--tree-config", type=Path, default=DEFAULT_TREE_CONFIG)
    parser.add_argument("--inner-folds", type=int, default=DEFAULT_INNER_FOLDS)
    parser.add_argument(
        "--n-jobs",
        type=int,
        default=-1,
        help="Procesos en paralelo para los folds (-1: todos los núcleos; 1: serial). "
        "El resultado no cambia: cada fold es determinista.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    started = time.monotonic()
    try:
        sources = load_sources(args.sources)
        tables = DataPipeline({"D1_holofood": sources["D1_holofood"]}).run(["D1_holofood"]).dataset
        tables, _ = attach_sample_context(
            tables,
            metadata=MetadataLoader(sources[METADATA_SOURCE]).load(),
            metabolites=MetaboliteLoader(sources["D1_holofood_scfa_content"]).load(),
        )
        dataset = build_tabular_dataset(tables).filter_complete_targets()
        cohort = load_cohort(sources)
        dataset = dataset.filter_samples(cohort.sample_ids)
        with Path(sources[METADATA_SOURCE].path_or_url).open(
            encoding="utf-8", newline=""
        ) as handle:
            metadata = {
                row["sample_id"]: row
                for row in csv.DictReader(handle, delimiter="\t")
                if row.get("sample_id")
            }
        pens = {
            sample_id: metadata[sample_id]["pen_code"]
            for sample_id in dataset.sample_ids
            if metadata.get(sample_id, {}).get("pen_code")
        }
        plan = PenFoldPlan.load(args.plan)
        data = prepare_compositional_data(dataset, pens)
        linear_cfg = LinearBaselineConfig.load(args.linear_config)
        tree_cfg = TreeBaselineConfig.load(args.tree_config)
        result = run_compositional_baselines(
            data, plan, linear_cfg, tree_cfg, inner_folds=args.inner_folds, n_jobs=args.n_jobs
        )
    except (FileNotFoundError, KeyError, ValueError) as error:
        print(f"No se pudo generar el reporte: {error}", file=sys.stderr)
        return EXIT_INPUT
    elapsed = time.monotonic() - started

    days = sorted(set(data.days), key=lambda d: (0, float(d)) if d.isdigit() else (1, 0.0))
    diet_counts = Counter(
        str(metadata[s]["diet_treatment_code"]) for s in data.sample_ids if s in metadata
    )
    day35 = sorted(
        f"{count} {DIET_LABELS.get(diet, diet)}"
        for diet, count in Counter(
            str(metadata[s]["diet_treatment_code"])
            for s, day in zip(data.sample_ids, data.days, strict=True)
            if day == days[-1] and s in metadata
        ).items()
    )
    prop_frac_day = aggregate_rows(result.aggregate, DAY_ONLY_NAME, "fraction_r2", ALL_DAYS)
    prop_frac_design = aggregate_rows(result.aggregate, DESIGN_RIDGE_NAME, "fraction_r2", ALL_DAYS)
    day_value = prop_frac_day.get("mean")
    design_value = prop_frac_design.get("mean")
    day_vs_design_note = (
        f"{_fmt(day_value.targets['propionate']) if day_value else '—'} con `day_only` y "
        f"{_fmt(design_value.targets['propionate']) if design_value else '—'} con "
        f"`{DESIGN_RIDGE_NAME}` (media entre folds, cohorte de 56)."
    )
    context: dict[str, Any] = {
        "elapsed_s": elapsed,
        "retrieved_at": _manifest_retrieved_at(sources),
        "cohort_size": len(data.sample_ids),
        "cohort_version": cohort.summary()["version"],
        "min_ssu_reads": cohort.min_ssu_reads,
        "animals_by_diet": sorted(diet_counts.items()),
        "k": plan.k,
        "seeds": list(plan.seeds),
        "plan_path": args.plan.relative_to(REPO_ROOT)
        if args.plan.is_absolute() and args.plan.is_relative_to(REPO_ROOT)
        else args.plan,
        "plan_sha256": _sha256(args.plan),
        "inner_folds": args.inner_folds,
        "design_features": list(result.design_features),
        "n_features": result.n_features,
        "day_diet_note": (
            f"En el día {days[-1]} hay " + ", ".join(day35) + ", y el día explica buena parte "
            "de la composición; por eso se informan métricas por día y existe `day_only`."
        ),
        "day_vs_design_note": day_vs_design_note,
        "days": days,
    }

    args.output.mkdir(parents=True, exist_ok=True)
    report_md = build_report_markdown(context, result.aggregate)
    (args.output / "report.md").write_text(report_md, encoding="utf-8", newline="\n")
    (args.output / "metrics.csv").write_text(
        result.aggregate.to_csv().replace("\r\n", "\n"), encoding="utf-8"
    )
    _write_fold_metrics(args.output / "fold_metrics.csv", result.cv.fold_reports)
    _write_selections(args.output / "selections.csv", result.selections)
    run_meta = {
        "issue": 140,
        "dataset_id": "D1_holofood",
        "command": "python scripts/compare_baselines_d1_composition.py",
        "sources": str(args.sources),
        "sources_sha256": _sha256(args.sources),
        "plan": str(args.plan),
        "plan_sha256": context["plan_sha256"],
        "plan_cohort": dict(plan.cohort),
        "cohort": cohort.summary(),
        "manifest_retrieved_at": context["retrieved_at"],
        "models": list(MODEL_NAMES),
        "split_label": CV_SPLIT,
        "n_samples": len(data.sample_ids),
        "n_features": result.n_features,
        "design_features": list(result.design_features),
        "inner_folds": args.inner_folds,
        "n_jobs": args.n_jobs,
        "compositional_target_version": COMPOSITIONAL_TARGET_VERSION,
        "linear_config": linear_cfg.to_dict(),
        "tree_config": tree_cfg.to_dict(),
        "selection_frequency": _selection_frequency(result.selections),
        "elapsed_seconds": round(elapsed, 1),
    }
    (args.output / "run.json").write_text(
        json.dumps(run_meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )

    print(report_md)
    print(f"Archivos generados en {args.output.as_posix()} ({elapsed:.0f} s)")
    return EXIT_OK


def _manifest_retrieved_at(sources: Mapping[str, Any]) -> str:
    """Fecha de la descarga según el `manifest.json` junto a la tabla de abundancias."""
    source = sources["D1_holofood"]
    if source.path_or_url is None:
        return "desconocida"
    manifest = Path(source.path_or_url).parent / "manifest.json"
    if not manifest.is_file():
        return "desconocida"
    return str(json.loads(manifest.read_text(encoding="utf-8")).get("retrieved_at", "?"))


def _write_fold_metrics(
    path: Path, fold_reports: Mapping[tuple[int, int], EvaluationReport]
) -> None:
    rows: list[dict[str, Any]] = []
    for (seed, fold), report in sorted(fold_reports.items()):
        for row in report.rows:
            rows.append({"seed": seed, "fold": fold, **row.to_dict()})
    fieldnames: list[str] = []
    for row in rows:
        fieldnames.extend(key for key in row if key not in fieldnames)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, restval="", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_selections(path: Path, selections: Sequence[Any]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["seed", "fold", "model", "inner_folds", "params"])
        for selection in selections:
            writer.writerow(
                [
                    selection.seed,
                    selection.fold,
                    selection.model,
                    selection.inner_folds,
                    json.dumps(selection.params, sort_keys=True),
                ]
            )


def _selection_frequency(selections: Sequence[Any]) -> dict[str, dict[str, int]]:
    """Frecuencia de cada combinación de hiperparámetros elegida, por modelo."""
    by_model: dict[str, Counter[str]] = {}
    for selection in selections:
        counter = by_model.setdefault(selection.model, Counter())
        counter[json.dumps(selection.params, sort_keys=True)] += 1
    return {model: dict(counter.most_common()) for model, counter in sorted(by_model.items())}


if __name__ == "__main__":
    raise SystemExit(main())
