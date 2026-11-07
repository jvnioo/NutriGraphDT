"""Capacidad funcional desde el catálogo MGnify chicken-gut v1.0.1 (#175, #257).

Aplica la regla de la decisión de #257 (sección 4): un género tiene `has_capacity` hacia un KO si
al menos una de sus especies representativas lo trae en su anotación eggNOG (`KEGG_ko`). Solo se
miran los géneros `1:1` de la tabla S-04, por su identificador GTDB, y los KO con una relación
`produces` aprobada. Lo que falta en un MAG incompleto no demuestra ausencia, y la capacidad
anotada no es actividad demostrada.

Es parte pura más una descarga: `capacity_rows` no toca la red y recibe la función que resuelve la
anotación de cada genoma, así que se prueba con tablas pequeñas.
"""

from __future__ import annotations

import csv
import re
import urllib.request
from collections import defaultdict
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Final

from nutrigraphdt.data.functions import CAPACITY_COLUMNS, CapacityRow

CATALOGUE_URL: Final = (
    "https://ftp.ebi.ac.uk/pub/databases/metagenomics/mgnify_genomes/chicken-gut/v1.0.1"
)
METADATA_FILE: Final = "genomes-all_metadata.tsv"
USER_AGENT: Final = "nutrigraphdt-data"
_GENUS: Final = re.compile(r"(?:^|;)g__([^;]*)")


def species_by_genus(metadata: Path) -> dict[str, list[str]]:
    """Genomas representativos del catálogo por género GTDB con prefijo (`g__X`)."""
    species: dict[str, list[str]] = defaultdict(list)
    with metadata.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            match = _GENUS.search(row["Lineage"])
            if row["Genome"] == row["Species_rep"] and match and match.group(1):
                species[f"g__{match.group(1)}"].append(row["Genome"])
    return dict(species)


def annotated_kos(path: Path) -> frozenset[str]:
    """KO (`ko:Kxxxxx`) de un `<genoma>_eggNOG.tsv`, según su columna `KEGG_ko`."""
    kos: set[str] = set()
    column: int | None = None
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle, delimiter="\t"):
            if row and row[0] == "#query":
                column = row.index("KEGG_ko")
            elif column is not None and row and not row[0].startswith("#"):
                value = row[column] if len(row) > column else "-"
                kos.update(ko for ko in value.split(",") if ko.startswith("ko:"))
    return frozenset(kos)


def capacity_rows(
    links: Mapping[str, str],
    species: Mapping[str, list[str]],
    functions: frozenset[str],
    annotations: Callable[[str], frozenset[str]],
) -> list[CapacityRow]:
    """Filas de capacidad de los enlaces `1:1` (`{silva_taxon_id: gtdb_taxon_id}`).

    Un género GTDB que el catálogo no trae no genera filas. Dos géneros SILVA con el mismo género
    GTDB generan filas por separado: cada enlace es unívoco desde el lado de SILVA (decisión de
    #236, sección 6, punto 5).
    """
    rows: list[CapacityRow] = []
    for taxon_id, gtdb in links.items():
        genomes = species.get(gtdb, [])
        found = [annotations(genome) & functions for genome in genomes]
        for function_id in sorted(functions):
            count = sum(function_id in kos for kos in found)
            if count:
                rows.append(CapacityRow(taxon_id, gtdb, function_id, count, len(genomes)))
    rows.sort(key=lambda row: (row.gtdb_taxon_id, row.function_id, row.taxon_id))
    return rows


def write_capacity_table(rows: list[CapacityRow], path: Path, *, header: str) -> None:
    """Escribe `has_capacity_d1.tsv` con sus comentarios de procedencia."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(header)
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(CAPACITY_COLUMNS)
        for row in rows:
            writer.writerow(
                [
                    row.taxon_id,
                    row.gtdb_taxon_id,
                    row.function_id,
                    row.species_with_ko,
                    row.species,
                ]
            )


def eggnog_url(genome: str) -> str:
    """URL del `<genoma>_eggNOG.tsv` en el FTP del catálogo."""
    return f"{CATALOGUE_URL}/species_catalogue/{genome[:11]}/{genome}/genome/{genome}_eggNOG.tsv"


def download(url: str, path: Path) -> None:
    """Descarga `url` en `path` si aún no existe (un archivo parcial no queda con ese nombre)."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.name}.partial")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        partial.write_bytes(response.read())
    partial.replace(path)


__all__ = [
    "CATALOGUE_URL",
    "METADATA_FILE",
    "annotated_kos",
    "capacity_rows",
    "download",
    "eggnog_url",
    "species_by_genus",
    "write_capacity_table",
]
