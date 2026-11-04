#!/usr/bin/env python3
"""Contrasta la tabla S-04 con los metadatos de GTDB r207 y el catálogo chicken-gut v1.0.1.

Para cada género de la tabla informa a qué géneros GTDB corresponden los genomas cuya etiqueta
`ssu_silva_taxonomy` lleva ese género, y qué géneros del mismo nombre (exacto o con sufijo `_A`,
`_B`…) tienen genomas en el catálogo. Usa solo la biblioteca estándar.

Esa columna de GTDB no está en SILVA 132 (distingue, por ejemplo, Limosilactobacillus), así que el
resultado es evidencia indicativa para la curación de S-04, no un mapeo SILVA 132 directo.

Uso, con bac120_metadata_r207.tar.gz de
https://data.gtdb.ecogenomic.org/releases/release207/207.0/ ya descargado:

    python docs/research/verify_s04_gtdb_r207.py --gtdb-metadata bac120_metadata_r207.tar.gz
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import tarfile
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

TABLE = Path("configs/taxonomy/s04_silva_gtdb_minimal.tsv")
OUTPUT = Path("docs/research/s04_gtdb_r207_evidence.tsv")
CATALOGUE_URL = (
    "https://www.ebi.ac.uk/metagenomics/api/v1/genome-catalogues/chicken-gut-v1-0-1/genomes"
)
SILVA_GENUS_FIELD = 5
TOP_GTDB_GENERA = 6


def genus(lineage: str) -> str:
    match = re.search(r"g__([^;]*)", lineage)
    return match.group(1) if match else ""


def catalogue_genera() -> Counter[str]:
    counts: Counter[str] = Counter()
    page = 1
    while True:
        query = urllib.parse.urlencode({"page": page, "page_size": 100})
        request = urllib.request.Request(
            f"{CATALOGUE_URL}?{query}",
            headers={"Accept": "application/json", "User-Agent": "nutrigraphdt-s04-review"},
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            items = json.load(response)["data"]
        counts.update(genus(item["attributes"]["taxon-lineage"]) for item in items)
        if len(items) < 100:
            return counts
        page += 1


def silva_to_gtdb(metadata: Path) -> dict[str, Counter[str]]:
    csv.field_size_limit(10**9)
    mapping: dict[str, Counter[str]] = defaultdict(Counter)
    with tarfile.open(metadata) as archive:
        member = next(item for item in archive.getmembers() if item.isfile())
        handle = archive.extractfile(member)
        if handle is None:
            raise ValueError(f"{member.name} no se puede leer.")
        text = io.TextIOWrapper(handle, encoding="utf-8", newline="")
        for row in csv.DictReader(text, delimiter="\t"):
            parts = [part.strip() for part in row["ssu_silva_taxonomy"].split(";")]
            if len(parts) > SILVA_GENUS_FIELD and parts[SILVA_GENUS_FIELD]:
                mapping[parts[SILVA_GENUS_FIELD]][genus(row["gtdb_taxonomy"])] += 1
    return mapping


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--gtdb-metadata", type=Path, required=True)
    args = parser.parse_args()

    silva = silva_to_gtdb(args.gtdb_metadata)
    catalogue = catalogue_genera()
    with TABLE.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader((ln for ln in handle if not ln.startswith("#")), delimiter="\t"))

    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(
            [
                "silva_taxon_id",
                "table_relationship",
                "genomes_with_silva_label",
                "gtdb_genera_top",
                "catalogue_genera_same_stem",
            ]
        )
        for row in rows:
            name = row["silva_taxon_id"].removeprefix("g__")
            gtdb = silva.get(name, Counter())
            same_stem = sorted(
                (found, count)
                for found, count in catalogue.items()
                if found == name or found.startswith(f"{name}_")
            )
            writer.writerow(
                [
                    row["silva_taxon_id"],
                    row["relationship"],
                    sum(gtdb.values()),
                    ", ".join(f"{g}:{n}" for g, n in gtdb.most_common(TOP_GTDB_GENERA)),
                    ", ".join(f"{g}:{n}" for g, n in same_stem),
                ]
            )
    print(f"{len(rows)} géneros; {sum(catalogue.values())} genomas del catálogo. Archivo: {OUTPUT}")


if __name__ == "__main__":
    main()
