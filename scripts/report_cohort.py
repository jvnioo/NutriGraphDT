"""Reporta la cohorte supervisada de D1 y su sensibilidad al umbral de lecturas (#138).

Aplica `configs/cohorts/d1_holofood.json` a las tablas registradas en `configs/sources.json`
y escribe, por cada umbral (el de la configuración y los de `sensitivity_min_ssu_reads`), los
animales que quedan en cada paso, por tratamiento y con sus corrales.

Uso:

    python scripts/report_cohort.py                    # salida en reports/cohort/
    python scripts/report_cohort.py --sources configs/sources.json --output reports/cohort

Código de salida: `0` si escribió el reporte; `2` si faltan datos o la configuración es inválida.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from nutrigraphdt.data.cohort import (
    CohortConfig,
    describe_cohort,
    get_cohort_config,
    load_cohort,
)
from nutrigraphdt.data.config import load_sources

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = REPO_ROOT / "configs" / "sources.json"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "cohort"
METADATA_SOURCE = "D1_holofood_metadata"
DIETS = (("CC", "Control"), ("CO", "Probiótico"), ("CE", "Fitobiótico"))
EXIT_OK = 0
EXIT_INPUT = 2


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument(
        "--cohort-config", type=Path, default=None, help="Por defecto, configs/cohorts/."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    try:
        config = (
            CohortConfig.load(args.cohort_config) if args.cohort_config else get_cohort_config()
        )
        sources = load_sources(args.sources)
        metadata = _read_metadata(sources[METADATA_SOURCE].path_or_url)
        report = build_report(sources, config, metadata)
        report["retrieved_at"] = _retrieved_at(sources)
    except (FileNotFoundError, KeyError, ValueError) as error:
        print(f"No se pudo reportar la cohorte: {error}", file=sys.stderr)
        return EXIT_INPUT

    stem = config.dataset_id.lower()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / f"{stem}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline=""
    )
    markdown = to_markdown(report)
    (args.output / f"{stem}.md").write_text(markdown, encoding="utf-8", newline="")
    print(markdown)
    return EXIT_OK


def build_report(
    sources: Mapping[str, Any],
    config: CohortConfig,
    metadata: Mapping[str, Mapping[str, str]],
) -> dict[str, Any]:
    """La cohorte con el umbral de la configuración y con cada umbral de sensibilidad."""
    thresholds = (config.min_ssu_reads, *config.sensitivity_min_ssu_reads)
    analyses = []
    for threshold in thresholds:
        cohort = load_cohort(sources, config, min_ssu_reads=threshold)
        analyses.append(
            {
                "min_ssu_reads": threshold,
                "official": threshold == config.min_ssu_reads,
                "size": len(cohort),
                "steps": describe_cohort(cohort, metadata),
                "sample_ids": sorted(cohort.sample_ids),
            }
        )
    return {
        "dataset_id": config.dataset_id,
        "version": config.version,
        "reference": config.reference,
        "targets": list(config.targets),
        "exclusions": [
            {"sample_id": item.sample_id, "reason": item.reason, "note": item.note}
            for item in config.exclusions
        ],
        "analyses": analyses,
    }


def to_markdown(report: Mapping[str, Any]) -> str:
    """Tabla de pasos por umbral, en el formato del Issue #138."""
    lines = [
        f"# Cohorte supervisada de {report['dataset_id']} (versión {report['version']})",
        "",
        "Generado con `python scripts/report_cohort.py`. Criterios en "
        f"`configs/cohorts/{report['dataset_id'].lower()}.json`; referencia: "
        f"{report['reference']}",
        "",
        "AGCC objetivo: " + ", ".join(f"`{name}`" for name in report["targets"]) + ".",
        "",
    ]
    if report.get("retrieved_at"):
        lines += [f"Descarga: `{report['retrieved_at']}` (`manifest.json`).", ""]
    for analysis in report["analyses"]:
        kind = "oficial" if analysis["official"] else "sensibilidad"
        lines += [
            f"## Umbral de {analysis['min_ssu_reads']} lecturas SSU ({kind}): "
            f"{analysis['size']} animales",
            "",
            "| Paso | Animales | " + " / ".join(code for code, _ in DIETS) + " | "
            "Corrales por tratamiento | Quitados |",
            "|---|---:|---|---|---|",
        ]
        for step in analysis["steps"]:
            animals = " / ".join(str(step["animals_by_diet"].get(code, 0)) for code, _ in DIETS)
            pens = " / ".join(str(step["pens_by_diet"].get(code, 0)) for code, _ in DIETS)
            removed = ", ".join(step["removed"]) or "—"
            lines.append(
                f"| {step['description']} | {step['count']} | {animals} | {pens} | {removed} |"
            )
        lines.append("")
    lines += [
        "Tratamientos: " + ", ".join(f"`{code}` {name}" for code, name in DIETS) + ".",
        "",
        "## Exclusiones configuradas",
        "",
        "| `sample_id` | Motivo | Nota |",
        "|---|---|---|",
    ]
    for item in report["exclusions"]:
        lines.append(f"| {item['sample_id']} | `{item['reason']}` | {item['note']} |")
    return "\n".join(lines) + "\n"


def _retrieved_at(sources: Mapping[str, Any]) -> str | None:
    """Fecha de la descarga según el `manifest.json` junto a la tabla de abundancias."""
    path = sources["D1_holofood"].path_or_url
    manifest = Path(path).parent / "manifest.json" if path else None
    if manifest is None or not manifest.is_file():
        return None
    try:
        value = json.loads(manifest.read_text(encoding="utf-8")).get("retrieved_at")
    except (OSError, json.JSONDecodeError):
        return None
    return str(value) if value else None


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
