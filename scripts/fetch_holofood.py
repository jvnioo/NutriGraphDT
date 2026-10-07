"""Descarga la fuente D1 (HoloFood, pollo) y la deja en el formato de los loaders.

Uso:

    python scripts/fetch_holofood.py                 # salida en data/raw/D1_holofood
    python scripts/fetch_holofood.py --refresh       # ignora la caché y vuelve a descargar

Consulta tres servicios públicos de EMBL-EBI, sin credenciales:

- HoloFood Data Portal (https://www.holofooddata.org/api): lista de muestras, fichas de
  animales (dieta, sexo, peso, día de muestreo) y AGCC de las muestras de metabolómica
  dirigida;
- MGnify (https://www.ebi.ac.uk/metagenomics/api/v1): tablas de abundancia taxonómica SSU
  (pipeline 5.0) de los estudios de ciego de pollo de HoloFood;
- ENA Portal API: correspondencia entre las corridas de esas tablas y sus BioSamples.

Escribe en el directorio de salida `abundance_ssu_caecum.tsv`, `scfa_caecum_content.tsv`,
`scfa_caecum_tissue.tsv`, `metadata.tsv`, `sample_map.tsv` y `manifest.json`. Las respuestas
crudas quedan en `_cache/`, de modo que una segunda ejecución no repite las ~1600 consultas.
`data/raw/` está ignorado por Git: los datos se regeneran con este script, no se versionan.
Ver `docs/data-sources/holofood-source.md`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nutrigraphdt.data.acquisition.holofood import (
    CAECUM_MATRICES,
    METADATA_COLUMNS,
    SCFA_MARKERS,
    RunLink,
    abundance_table,
    animal_metadata_row,
    body_site,
    caecal_run_links,
    merge_by_animal,
    parse_mgnify_taxonomy,
    rows_table,
    scfa_row,
)

HOLOFOOD_API = "https://www.holofooddata.org/api"
HOLOFOOD_EXPORT = "https://www.holofooddata.org/export/samples"
MGNIFY_API = "https://www.ebi.ac.uk/metagenomics/api/v1"
ENA_FILEREPORT = "https://www.ebi.ac.uk/ena/portal/api/filereport"
MGNIFY_PIPELINE = "5.0"
SSU_LABEL = "Taxonomic assignments SSU"
USER_AGENT = "NutriGraphDT/0.1 (academic research prototype)"
WORKERS = 4


class Fetcher:
    """GET con reintentos y caché en disco por URL."""

    def __init__(self, cache_dir: Path, refresh: bool) -> None:
        self.cache_dir = cache_dir
        self.refresh = refresh
        self.requests = 0
        cache_dir.mkdir(parents=True, exist_ok=True)

    def text(self, url: str) -> str:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        path = self.cache_dir / key
        if path.exists() and not self.refresh:
            return path.read_text(encoding="utf-8")
        body = self._get(url)
        path.write_text(body, encoding="utf-8")
        return body

    def json(self, url: str) -> Any:
        return json.loads(self.text(url))

    def optional_json(self, url: str) -> Any | None:
        """Como `json`, pero devuelve `None` si el recurso no existe (404)."""
        try:
            return self.json(url)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise

    def _get(self, url: str) -> str:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        for attempt in range(6):
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    self.requests += 1
                    return str(response.read().decode("utf-8"))
            except OSError as error:  # URLError, timeouts y conexiones cortadas
                if isinstance(error, urllib.error.HTTPError) and error.code == 404:
                    raise
                wait = 2**attempt
                print(f"  reintento en {wait}s ({url}): {error}", file=sys.stderr)
                time.sleep(wait)
        raise RuntimeError(f"No se pudo descargar {url}")


def _tsv(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text), delimiter="\t"))


def _paged(fetcher: Fetcher, url: str) -> list[dict[str, Any]]:
    """Recorre las páginas de una lista del portal HoloFood (`items`, `count`)."""
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        separator = "&" if "?" in url else "?"
        data = fetcher.json(f"{url}{separator}page={page}")
        items.extend(data["items"])
        if not data["items"] or len(items) >= int(data["count"]):
            return items
        page += 1


def _chicken_studies(fetcher: Fetcher) -> list[dict[str, Any]]:
    """Estudios de MGnify de HoloFood pollo que publican una tabla SSU del pipeline 5.0."""
    found = fetcher.json(f"{MGNIFY_API}/studies?search=HoloFood&page_size=100")["data"]
    studies: list[dict[str, Any]] = []
    for study in sorted(found, key=lambda item: item["id"]):
        attributes = study["attributes"]
        if "chicken" not in attributes["study-name"].lower():
            continue
        downloads = fetcher.json(f"{MGNIFY_API}/studies/{study['id']}/downloads")["data"]
        for item in downloads:
            label = item["attributes"]["description"]["label"]
            pipeline = item["relationships"]["pipeline"]["data"]["id"]
            if label == SSU_LABEL and pipeline == MGNIFY_PIPELINE:
                studies.append(
                    {
                        "mgnify_study": study["id"],
                        "bioproject": attributes["bioproject"],
                        "name": attributes["study-name"],
                        "ssu_url": item["links"]["self"],
                    }
                )
    return studies


def _write(path: Path, content: str) -> dict[str, Any]:
    path.write_text(content, encoding="utf-8", newline="\n")
    data = content.encode("utf-8")
    return {
        "file": path.name,
        "bytes": len(data),
        "rows": max(content.count("\n") - 1, 0),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def fetch(output: Path, refresh: bool) -> dict[str, Any]:
    fetcher = Fetcher(output / "_cache", refresh)

    print("1/5 Muestras y animales del portal HoloFood…")
    samples = {row["accession"]: row for row in _tsv(fetcher.text(HOLOFOOD_EXPORT))}
    chicken = {
        item["accession"] for item in _paged(fetcher, f"{HOLOFOOD_API}/animals?system=chicken")
    }

    print("2/5 Tablas SSU de MGnify y corridas de ENA…")
    studies = _chicken_studies(fetcher)
    tables: dict[str, dict[str, dict[str, float]]] = {}
    run_to_study: dict[str, str] = {}
    run_rows: list[dict[str, str]] = []
    for study in studies:
        columns, counts = parse_mgnify_taxonomy(fetcher.text(study["ssu_url"]))
        tables[study["mgnify_study"]] = counts
        for column in columns:
            run_to_study.setdefault(column, study["mgnify_study"])
        query = urllib.parse.urlencode(
            {
                "accession": study["bioproject"],
                "result": "read_run",
                "fields": "run_accession,sample_accession",
                "format": "tsv",
            }
        )
        run_rows.extend(_tsv(fetcher.text(f"{ENA_FILEREPORT}?{query}")))
    links = [
        link
        for link in caecal_run_links(run_rows, samples, run_to_study)
        if link.animal_accession in chicken
    ]
    abundance = merge_by_animal(tables, links)

    print("3/5 AGCC de las muestras de metabolómica dirigida…")
    targeted = sorted(
        accession
        for accession, row in samples.items()
        if row["sample_type"] == "metabolomic_targeted" and row["animal"] in chicken
    )
    with ThreadPoolExecutor(WORKERS) as pool:
        fetched = list(
            pool.map(lambda acc: fetcher.optional_json(f"{HOLOFOOD_API}/samples/{acc}"), targeted)
        )
    missing_samples = [acc for acc, item in zip(targeted, fetched, strict=True) if item is None]
    details = [item for item in fetched if item is not None]
    scfa: dict[str, dict[str, dict[str, str]]] = {matrix: {} for matrix in CAECUM_MATRICES.values()}
    scfa_samples: dict[str, dict[str, str]] = {matrix: {} for matrix in CAECUM_MATRICES.values()}
    duplicates: Counter[str] = Counter()
    for detail in details:
        matrix = CAECUM_MATRICES.get(body_site(detail) or "")
        if matrix is None:
            continue
        animal = str(detail["animal"])
        if animal in scfa[matrix]:
            duplicates[matrix] += 1
            continue
        scfa[matrix][animal] = {"sample_id": animal, **scfa_row(detail)}
        scfa_samples[matrix][animal] = str(detail["accession"])

    print("4/5 Fichas de los animales…")
    animals = sorted(set(abundance) | {a for rows in scfa.values() for a in rows})
    with ThreadPoolExecutor(WORKERS) as pool:
        animal_details = list(
            pool.map(lambda acc: fetcher.optional_json(f"{HOLOFOOD_API}/animals/{acc}"), animals)
        )
    missing_animals = [acc for acc, item in zip(animals, animal_details, strict=True) if not item]
    metadata = [animal_metadata_row(detail) for detail in animal_details if detail]

    print("5/5 Escribiendo tablas…")
    runs_by_animal: dict[str, list[RunLink]] = {}
    for link in links:
        runs_by_animal.setdefault(link.animal_accession, []).append(link)
    codes = {row["sample_id"]: row["animal_code"] for row in metadata}
    sample_map = []
    for animal in animals:
        runs = runs_by_animal.get(animal, [])
        sample_map.append(
            {
                "sample_id": animal,
                "animal_code": codes.get(animal, ""),
                "metagenome_sample": ";".join(sorted({run.sample_accession for run in runs})),
                "metagenome_runs": ";".join(run.run_accession for run in runs),
                "mgnify_study": ";".join(sorted({run.mgnify_study for run in runs})),
                "scfa_content_sample": scfa_samples["content"].get(animal, ""),
                "scfa_tissue_sample": scfa_samples["tissue"].get(animal, ""),
            }
        )
    scfa_columns = ["sample_id", *SCFA_MARKERS]
    files = [
        _write(output / "abundance_ssu_caecum.tsv", abundance_table(abundance)),
        _write(
            output / "scfa_caecum_content.tsv",
            rows_table(scfa_columns, (scfa["content"][a] for a in sorted(scfa["content"]))),
        ),
        _write(
            output / "scfa_caecum_tissue.tsv",
            rows_table(scfa_columns, (scfa["tissue"][a] for a in sorted(scfa["tissue"]))),
        ),
        _write(output / "metadata.tsv", rows_table(METADATA_COLUMNS, metadata)),
        _write(output / "sample_map.tsv", rows_table(list(sample_map[0]), sample_map)),
    ]
    with_metagenome = set(abundance)
    manifest = {
        "source_id": "D1_holofood",
        "retrieved_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "citation": "Rogers et al. (2025) Database baae112. DOI: 10.1093/database/baae112",
        "services": {
            "holofood_api": HOLOFOOD_API,
            "holofood_export": HOLOFOOD_EXPORT,
            "mgnify_api": MGNIFY_API,
            "ena_filereport": ENA_FILEREPORT,
        },
        "mgnify_pipeline": MGNIFY_PIPELINE,
        "mgnify_studies": studies,
        "counts": {
            "chicken_animals_in_portal": len(chicken),
            "caecal_metagenome_runs": len(links),
            "animals_with_caecal_metagenome": len(with_metagenome),
            "animals_with_scfa_content": len(scfa["content"]),
            "animals_with_scfa_tissue": len(scfa["tissue"]),
            "animals_with_metagenome_and_scfa_content": len(with_metagenome & set(scfa["content"])),
            "animals_with_metagenome_and_scfa_tissue": len(with_metagenome & set(scfa["tissue"])),
            "duplicate_scfa_samples_skipped": dict(duplicates),
            "animals_without_portal_record": missing_animals,
            "samples_without_portal_record": missing_samples,
            "http_requests": fetcher.requests,
        },
        "files": files,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga la fuente D1 (HoloFood, pollo).")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw/D1_holofood"),
        help="Directorio de salida (por defecto: data/raw/D1_holofood).",
    )
    parser.add_argument(
        "--refresh", action="store_true", help="Ignora la caché y vuelve a descargar."
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = fetch(args.output, args.refresh)
    print(json.dumps(manifest["counts"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
