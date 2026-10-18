"""Cuenta cuántos animales con AGCC sumarían los ensamblajes `ERZ…` de HoloFood (#141).

`fetch_holofood.py` usa solo los perfiles SSU de lecturas (`ERR…`): los de ensamblajes no son
comparables. Antes de reabrir esa decisión (V-05 y S-06 de la respuesta de Investigación a la
solicitud v1.1), este script cuenta, sin cambiar las tablas de `data/raw/`:

1. los animales con ensamblaje de metagenoma de contenido cecal en las tablas SSU de MGnify;
2. cuántos de ellos no tienen perfil de lecturas y sí tienen los tres AGCC de contenido, fuera
   de las exclusiones de la cohorte (perfiles de AGCC repetidos);
3. cuántos de esos alcanzan el umbral de lecturas SSU de la cohorte con su perfil de
   ensamblaje, y cuántos tienen corridas de lectura crudas en ENA que MGnify no perfiló.

Reutiliza la caché de `fetch_holofood.py` (`<data-dir>/_cache/`): solo descarga el reporte de
análisis de ENA de cada estudio. Escribe `assemblies.md` y `assemblies.json` en `--output`.

Uso:

    python scripts/count_holofood_assemblies.py
    python scripts/count_holofood_assemblies.py --exclusions configs/cohorts/d1_holofood.json

Código de salida: `0` si escribió el reporte; `2` si faltan las tablas de la descarga.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import urllib.parse
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from fetch_holofood import (
    ENA_FILEREPORT,
    HOLOFOOD_API,
    HOLOFOOD_EXPORT,
    Fetcher,
    _chicken_studies,
    _paged,
    _tsv,
)

from nutrigraphdt.data.acquisition.holofood import (
    AssemblyAnimal,
    assembly_animals,
    caecal_assembly_links,
    parse_mgnify_taxonomy,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "raw" / "D1_holofood"
DEFAULT_EXCLUSIONS = REPO_ROOT / "configs" / "cohorts" / "d1_holofood.json"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "holofood"
DEFAULT_MIN_SSU = 1000
SCFA_TARGETS = ("Acetic acid", "Propionic acid", "n-Butyric acid")
DIETS = (("CC", "Control"), ("CO", "Probiótico"), ("CE", "Fitobiótico"))
EXIT_OK = 0
EXIT_INPUT = 2


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument(
        "--exclusions",
        type=Path,
        default=DEFAULT_EXCLUSIONS,
        help="JSON con una lista `exclusions` de `{sample_id, ...}` (configuración de cohorte).",
    )
    parser.add_argument("--min-ssu-reads", type=int, default=DEFAULT_MIN_SSU)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--refresh", action="store_true", help="Ignora la caché.")
    args = parser.parse_args(argv)

    data_dir = args.data_dir
    try:
        read_animals = _abundance_animals(data_dir / "abundance_ssu_caecum.tsv")
        complete_scfa = _complete_scfa(data_dir / "scfa_caecum_content.tsv")
        metadata = _rows_by_sample(data_dir / "metadata.tsv")
    except (OSError, ValueError) as error:
        print(f"Faltan las tablas de la descarga: {error}", file=sys.stderr)
        return EXIT_INPUT
    excluded, exclusions_source = _exclusions(args.exclusions)

    fetcher = Fetcher(data_dir / "_cache", args.refresh)
    samples = {row["accession"]: row for row in _tsv(fetcher.text(HOLOFOOD_EXPORT))}
    chicken = {
        item["accession"] for item in _paged(fetcher, f"{HOLOFOOD_API}/animals?system=chicken")
    }
    studies = _chicken_studies(fetcher)

    tables: dict[str, dict[str, dict[str, float]]] = {}
    analysis_to_study: dict[str, str] = {}
    analysis_rows: list[dict[str, str]] = []
    runs_by_sample: dict[str, list[str]] = defaultdict(list)
    for study in studies:
        columns, counts = parse_mgnify_taxonomy(fetcher.text(study["ssu_url"]))
        tables[study["mgnify_study"]] = counts
        for column in columns:
            analysis_to_study.setdefault(column, study["mgnify_study"])
        analysis_rows.extend(_ena(fetcher, study["bioproject"], "analysis", "analysis_accession"))
        for row in _ena(fetcher, study["bioproject"], "read_run", "run_accession"):
            runs_by_sample[row["sample_accession"]].append(row["run_accession"])

    links = [
        link
        for link in caecal_assembly_links(analysis_rows, samples, analysis_to_study)
        if link.animal_accession in chicken
    ]
    animals = assembly_animals(
        links,
        tables,
        read_animals=read_animals,
        complete_scfa=complete_scfa,
        excluded=excluded,
        runs_by_sample=runs_by_sample,
    )
    report = build_report(
        animals,
        metadata,
        min_ssu_reads=args.min_ssu_reads,
        assembly_columns=sum(1 for column in analysis_to_study if column.startswith("ERZ")),
        exclusions_source=exclusions_source,
        retrieved_at=_retrieved_at(data_dir / "manifest.json"),
    )

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "assemblies.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline=""
    )
    markdown = to_markdown(report)
    (args.output / "assemblies.md").write_text(markdown, encoding="utf-8", newline="")
    print(markdown)
    print(f"Consultas nuevas: {fetcher.requests}", file=sys.stderr)
    return EXIT_OK


def build_report(
    animals: Sequence[AssemblyAnimal],
    metadata: Mapping[str, Mapping[str, str]],
    *,
    min_ssu_reads: int,
    assembly_columns: int,
    exclusions_source: str | None,
    retrieved_at: str | None,
) -> dict[str, Any]:
    """Conteos por paso y desglose de los animales que se sumarían."""
    assembly_only = [a for a in animals if not a.has_read_profile]
    with_scfa = [a for a in assembly_only if a.has_scfa]
    would_add = [a for a in with_scfa if not a.excluded]
    depths = [a.ssu_counts for a in would_add]
    return {
        "retrieved_at": retrieved_at,
        "exclusions_source": exclusions_source,
        "min_ssu_reads": min_ssu_reads,
        "assembly_columns": assembly_columns,
        "steps": {
            "animals_with_caecal_assembly": len(animals),
            "also_with_read_profile": len(animals) - len(assembly_only),
            "assembly_only": len(assembly_only),
            "assembly_only_with_scfa": len(with_scfa),
            "would_add": len(would_add),
            "would_add_reaching_min_ssu": sum(d >= min_ssu_reads for d in depths),
            "would_add_with_raw_reads": sum(bool(a.raw_runs) for a in would_add),
        },
        "assembly_ssu_counts": {
            "median": statistics.median(depths) if depths else None,
            "max": max(depths) if depths else None,
        },
        "would_add_by": _breakdown(would_add, metadata),
        "would_add": [
            {
                "sample_id": a.animal_accession,
                "ssu_counts": a.ssu_counts,
                "raw_runs": list(a.raw_runs),
            }
            for a in would_add
        ],
    }


def to_markdown(report: Mapping[str, Any]) -> str:
    """Tabla de pasos y desglose por tratamiento, día y ensayo."""
    steps = report["steps"]
    by = report["would_add_by"]
    depth = report["assembly_ssu_counts"]
    threshold = report["min_ssu_reads"]
    exclusions = report["exclusions_source"] or "ninguna (no se encontró la configuración)"
    lines = [
        "# Animales que sumarían los ensamblajes de HoloFood",
        "",
        "Generado con `python scripts/count_holofood_assemblies.py` (#141). "
        f"Descarga: `{report['retrieved_at'] or 'sin manifest.json'}`. "
        f"Exclusiones: {exclusions}.",
        "",
        "| Paso | Animales |",
        "|---|---:|",
        "| Con ensamblaje de metagenoma de contenido cecal en las tablas SSU de MGnify "
        f"({report['assembly_columns']} columnas `ERZ`) "
        f"| {steps['animals_with_caecal_assembly']} |",
        f"| − Ya tienen perfil de lecturas (`ERR`) | {steps['also_with_read_profile']} |",
        f"| = Solo con ensamblaje | {steps['assembly_only']} |",
        f"| … con los tres AGCC de contenido | {steps['assembly_only_with_scfa']} |",
        f"| … sin perfiles de AGCC repetidos: **sumarían** | **{steps['would_add']}** |",
        f"| … cuyo perfil de ensamblaje alcanza {threshold} conteos SSU "
        f"| {steps['would_add_reaching_min_ssu']} |",
        f"| … con corridas de lectura crudas en ENA sin perfil en MGnify "
        f"| {steps['would_add_with_raw_reads']} |",
        "",
        f"Conteos SSU de sus perfiles de ensamblaje: mediana {depth['median']}, "
        f"máximo {depth['max']}. Son asignaciones sobre contigs, no lecturas: no se comparan "
        "con el umbral de lecturas de la cohorte.",
        "",
        "| Desglose de los que sumarían | " + " / ".join(c for c, _ in DIETS) + " |",
        "|---|---|",
        "| Animales por tratamiento | "
        + " / ".join(str(by["animals_by_diet"].get(c, 0)) for c, _ in DIETS)
        + " |",
        "| Corrales por tratamiento | "
        + " / ".join(str(by["pens_by_diet"].get(c, 0)) for c, _ in DIETS)
        + " |",
        "",
        "Por día de muestreo: "
        + ", ".join(f"día {day}: {n}" for day, n in by["animals_by_day"].items())
        + ". Por ensayo: "
        + ", ".join(f"`{trial}`: {n}" for trial, n in by["animals_by_trial"].items())
        + ".",
        "",
        "Tratamientos: " + ", ".join(f"`{code}` {name}" for code, name in DIETS) + ".",
    ]
    return "\n".join(lines) + "\n"


def _breakdown(
    animals: Iterable[AssemblyAnimal], metadata: Mapping[str, Mapping[str, str]]
) -> dict[str, Any]:
    by_diet: Counter[str] = Counter()
    by_day: Counter[str] = Counter()
    by_trial: Counter[str] = Counter()
    pens: dict[str, set[str]] = defaultdict(set)
    missing = []
    for animal in animals:
        row = metadata.get(animal.animal_accession)
        if row is None:
            missing.append(animal.animal_accession)
            continue
        by_diet[row["diet_treatment_code"]] += 1
        by_day[row["sampling_day"]] += 1
        by_trial[row["trial_code"]] += 1
        pens[row["diet_treatment_code"]].add(row["pen_code"])
    return {
        "animals_by_diet": dict(sorted(by_diet.items())),
        "pens_by_diet": {diet: len(pens[diet]) for diet in sorted(pens)},
        "animals_by_day": dict(sorted(by_day.items(), key=lambda item: int(item[0]))),
        "animals_by_trial": dict(sorted(by_trial.items())),
        "without_metadata": missing,
    }


def _ena(fetcher: Fetcher, bioproject: str, result: str, accession: str) -> list[dict[str, str]]:
    query = urllib.parse.urlencode(
        {
            "accession": bioproject,
            "result": result,
            "fields": f"{accession},sample_accession",
            "format": "tsv",
        }
    )
    return _tsv(fetcher.text(f"{ENA_FILEREPORT}?{query}"))


def _abundance_animals(path: Path) -> set[str]:
    with path.open(encoding="utf-8") as handle:
        header = handle.readline().rstrip("\n").split("\t")
    if not header or header[0] != "taxon_lineage":
        raise ValueError(f"{path}: cabecera inesperada.")
    return set(header[1:])


def _complete_scfa(path: Path) -> set[str]:
    complete = set()
    for row in _read_tsv(path):
        try:
            [float(row[name]) for name in SCFA_TARGETS]
        except (KeyError, ValueError):
            continue
        complete.add(row["sample_id"])
    return complete


def _rows_by_sample(path: Path) -> dict[str, dict[str, str]]:
    return {row["sample_id"]: row for row in _read_tsv(path)}


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _exclusions(path: Path) -> tuple[set[str], str | None]:
    if not path.is_file():
        return set(), None
    data = json.loads(path.read_text(encoding="utf-8"))
    excluded = {str(item["sample_id"]) for item in data.get("exclusions", [])}
    version = data.get("version")
    try:
        shown = path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        shown = path.name
    return excluded, f"`{shown}`" + (f" (versión {version})" if version else "")


def _retrieved_at(manifest: Path) -> str | None:
    try:
        value = json.loads(manifest.read_text(encoding="utf-8")).get("retrieved_at")
    except (OSError, json.JSONDecodeError):
        return None
    return str(value) if value else None


if __name__ == "__main__":
    raise SystemExit(main())
