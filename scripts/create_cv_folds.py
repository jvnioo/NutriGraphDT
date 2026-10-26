"""Genera los folds de la validación cruzada por corral de D1 y su tabla de folds (D-07, #139).

Aplica `configs/cohorts/d1_holofood.json` (cohorte oficial, umbral de lecturas de la
configuración) a las tablas registradas en `configs/sources.json`, toma de los metadatos el
corral, la dieta y el día de muestreo de cada animal, y genera `StratifiedGroupKFold` (grupo
`pen_code`, estrato dieta, k = 5) para las semillas indicadas (por defecto 0 a 9).

Escribe:

- `configs/splits/d1_holofood_cv.json`: asignación versionada `seed → sample_id → fold`;
- `reports/cv/d1_pen_folds.md` y `.json`: tabla de folds por semilla (animales, corrales,
  dietas, días y días faltantes), resumen y comparación con los valores de D-07.

Con `--min-ssu-reads` se calcula la tabla para otro umbral (análisis de sensibilidad, por
ejemplo 5000) sin escribir la asignación oficial.

Uso:
    python scripts/create_cv_folds.py
    python scripts/create_cv_folds.py --seeds 100          # semillas 0..99 (comparación D-07)
    python scripts/create_cv_folds.py --min-ssu-reads 5000 --report-only

Requiere los datos de D1 descargados (`scripts/fetch_holofood.py`) y el extra `baselines`.
Código de salida: `0` si escribió los archivos; `2` si faltan datos o los folds no cumplen D-07.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from nutrigraphdt.data.cohort import CohortConfig, get_cohort_config, load_cohort
from nutrigraphdt.data.config import load_sources
from nutrigraphdt.models.cross_validation import (
    DEFAULT_K,
    CrossValidationError,
    CVAnimal,
    FoldRow,
    PenFoldPlan,
    fold_table,
    make_pen_folds,
    max_folds,
    summarize_fold_table,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = REPO_ROOT / "configs" / "sources.json"
DEFAULT_PLAN = REPO_ROOT / "configs" / "splits" / "d1_holofood_cv.json"
DEFAULT_REPORT = REPO_ROOT / "reports" / "cv"
METADATA_SOURCE = "D1_holofood_metadata"

# Valores que informa Investigación para D-07 (respuesta del 16-10-2026, sección 4.7 y Tabla 6),
# calculados sobre la cohorte de 59 animales. R-04 (25-10-2026) pide rehacer la tabla sobre 56.
INVESTIGATION_D07: Mapping[str, Any] = {
    "cohort_size": 59,
    "k": 5,
    "animals_per_fold": [11, 13],
    "pens_per_fold": [5, 8],
    "all_diets_in_every_fold": True,
    "seeds_with_a_fold_missing_a_day": "40 de 100",
}

EXIT_OK = 0
EXIT_INPUT = 2


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--cohort-config", type=Path, default=None)
    parser.add_argument("--min-ssu-reads", type=int, default=None)
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    parser.add_argument("--seeds", type=int, default=10, help="Semillas 0..N-1 (N ≥ 10).")
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--report-only", action="store_true", help="No escribe la asignación de folds."
    )
    args = parser.parse_args(argv)

    try:
        config = (
            CohortConfig.load(args.cohort_config) if args.cohort_config else get_cohort_config()
        )
        sources = load_sources(args.sources)
        cohort = load_cohort(sources, config, min_ssu_reads=args.min_ssu_reads)
        metadata = _read_metadata(sources[METADATA_SOURCE].path_or_url)
        animals = cohort_animals(sorted(cohort.sample_ids), metadata)
        threshold = args.min_ssu_reads or config.min_ssu_reads
        plan = make_pen_folds(
            animals,
            dataset_id=config.dataset_id,
            k=args.k,
            seeds=range(args.seeds),
            cohort={
                "config_version": config.version,
                "min_ssu_reads": threshold,
                "official": threshold == config.min_ssu_reads,
                "size": len(animals),
            },
        )
    except (FileNotFoundError, KeyError, ValueError, CrossValidationError) as error:
        print(f"No se pudieron generar los folds: {error}", file=sys.stderr)
        return EXIT_INPUT

    rows = fold_table(plan, animals)
    report = build_report(plan, animals, rows)
    suffix = "" if plan.cohort.get("official") else f"_{plan.cohort['min_ssu_reads']}"
    stem = f"{config.dataset_id.lower().split('_')[0]}_pen_folds{suffix}"
    args.report.mkdir(parents=True, exist_ok=True)
    (args.report / f"{stem}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    markdown = to_markdown(report, rows)
    (args.report / f"{stem}.md").write_text(markdown, encoding="utf-8", newline="\n")
    if not args.report_only and plan.cohort.get("official"):
        plan.save(args.plan)
        print(f"Asignación de folds: {args.plan}")
    print(markdown)
    return EXIT_OK


def cohort_animals(
    sample_ids: Sequence[str], metadata: Mapping[str, Mapping[str, str]]
) -> list[CVAnimal]:
    """Corral, dieta y día de muestreo de los animales de la cohorte."""
    missing = [s for s in sample_ids if s not in metadata]
    if missing:
        raise ValueError(f"Animales de la cohorte sin metadatos: {missing}.")
    return [CVAnimal.from_mapping(metadata[s]) for s in sample_ids]


def build_report(
    plan: PenFoldPlan, animals: Sequence[CVAnimal], rows: Sequence[FoldRow]
) -> dict[str, Any]:
    """Resumen, tabla de folds y comparación con D-07, serializables."""
    return {
        "dataset_id": plan.dataset_id,
        "plan_version": plan.version,
        "method": plan.method,
        "k": plan.k,
        "max_k": max_folds(animals),
        "seeds": list(plan.seeds),
        "cohort": dict(plan.cohort),
        "summary": summarize_fold_table(rows),
        "investigation_d07": dict(INVESTIGATION_D07),
        "folds": [
            {
                "seed": r.seed,
                "fold": r.fold,
                "animals": r.animals,
                "pens": r.pens,
                "animals_by_diet": dict(r.animals_by_diet),
                "pens_by_diet": dict(r.pens_by_diet),
                "days": list(r.days),
                "missing_days": list(r.missing_days),
            }
            for r in rows
        ],
    }


def to_markdown(report: Mapping[str, Any], rows: Sequence[FoldRow]) -> str:
    """Tabla de folds de D-07 y comparación con los valores de Investigación."""
    summary = report["summary"]
    cohort = report["cohort"]
    inv = report["investigation_d07"]
    kind = "oficial" if cohort.get("official") else "sensibilidad"
    diets = sorted({d for r in rows for d in r.animals_by_diet})
    lines = [
        f"# Validación cruzada por corral de {report['dataset_id']} (D-07)",
        "",
        "Generado con `python scripts/create_cv_folds.py`. Método: "
        f"`{report['method']}`, grupo `pen_code`, estrato dieta, k = {report['k']} "
        f"(máximo posible: {report['max_k']}), semillas {report['seeds'][0]} a "
        f"{report['seeds'][-1]}.",
        "",
        f"Cohorte: {cohort['size']} animales, umbral de "
        f"{cohort.get('min_ssu_reads', '—')} lecturas SSU ({kind}).",
        "",
        "## Comparación con D-07",
        "",
        "| Indicador | Investigación (cohorte de 59) | Desarrollo (esta cohorte) |",
        "|---|---|---|",
        f"| Animales | {inv['cohort_size']} | {cohort['size']} |",
        f"| k | {inv['k']} | {report['k']} |",
        "| Animales por fold | {} a {} | {} a {} |".format(
            *inv["animals_per_fold"], *summary["animals_per_fold"]
        ),
        "| Corrales por fold | {} a {} | {} a {} |".format(
            *inv["pens_per_fold"], *summary["pens_per_fold"]
        ),
        "| Las tres dietas en todos los folds | sí | sí (verificado) |",
        "| Semillas con algún fold sin un día de muestreo | "
        f"{inv['seeds_with_a_fold_missing_a_day']} | "
        f"{len(summary['seeds_with_a_fold_missing_a_day'])} de {summary['seeds']} |",
        "",
        "Investigación calculó sus valores sobre 59 animales; R-04 (25-10-2026) pide rehacer la "
        "tabla sobre la cohorte oficial de 56. La comparación exacta, fold por fold, queda "
        "pendiente de `d07_corrales.py` (R-06).",
        "",
        "## Folds por semilla",
        "",
        "| Semilla | Fold | Animales | Corrales | "
        + " | ".join(f"Animales {d}" for d in diets)
        + " | "
        + " | ".join(f"Corrales {d}" for d in diets)
        + " | Días | Días faltantes |",
        "|---:|---:|---:|---:|" + "---:|" * (2 * len(diets)) + "---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.seed} | {r.fold} | {r.animals} | {r.pens} | "
            + " | ".join(str(r.animals_by_diet.get(d, 0)) for d in diets)
            + " | "
            + " | ".join(str(r.pens_by_diet.get(d, 0)) for d in diets)
            + f" | {', '.join(r.days) or '—'} | {', '.join(r.missing_days) or '—'} |"
        )
    return "\n".join(lines) + "\n"


def _read_metadata(path: str | None) -> dict[str, dict[str, str]]:
    if path is None:
        raise ValueError(f"La fuente {METADATA_SOURCE!r} no define path_or_url.")
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return {
            row["sample_id"]: row
            for row in csv.DictReader(handle, delimiter="\t")
            if row.get("sample_id")
        }


if __name__ == "__main__":
    raise SystemExit(main())
