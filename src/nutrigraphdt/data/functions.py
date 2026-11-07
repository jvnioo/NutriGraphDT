"""Anotación funcional del grafo de D1: `has_capacity` y `produces` (#175, #257).

Reúne las tablas versionadas que aprobó Investigación:

- `configs/taxonomy/s04_silva132_gtdb_r207.tsv`: enlaces SILVA 132 → GTDB r207 (S-04, #236);
- `configs/functions/has_capacity_d1.tsv`: qué KO de `produces` trae cada género `1:1` en el
  catálogo MGnify chicken-gut v1.0.1, generada con `scripts/build_capacity_table.py`;
- `configs/functions/scfa_produces_d1.tsv`: qué AGCC libera cada KO según KEGG (#257).

Los nodos conservan el identificador SILVA, porque es el de las lecturas de D1. El género GTDB solo
sirve para consultar el catálogo: `g__Tyzzerella` recibe las funciones de `g__Anaerotignum`, y
`g__Bifidobacterium`, que es `1:N`, no recibe ninguna aunque el catálogo tenga ese nombre. Nunca se
une SILVA con GTDB por coincidencia de nombre (contrato v2 §6, D-04).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from nutrigraphdt.data.taxonomy import SilvaGtdbMapping

CATALOGUE_EVIDENCE_SOURCE: Final = "mgnify-chicken-gut@v1.0.1"
"""`evidence_source` de `has_capacity` (R-01, pregunta 5; decisión de #236, sección 7)."""

ANNOTATION_SOURCE: Final = "eggNOG-mapper 2.1.3 (MGnify genomes pipeline v2.0.0)"
"""Anotación de los genomas del catálogo; va en `function` y en `has_capacity` (EDG-08)."""

FUNCTION_TYPE: Final = "kegg_ortholog"
"""`function_type` de los nodos de función de D1 (decisión de #257, sección 1)."""

ANNOTATED_METHOD: Final = "database_annotation"

S04_TABLE_VERSION: Final = "2.0"
"""Versión de la decisión de #236 que emite `s04_silva132_gtdb_r207.tsv`."""

DEFAULT_S04_TABLE: Final = Path("configs/taxonomy/s04_silva132_gtdb_r207.tsv")
DEFAULT_CAPACITY_TABLE: Final = Path("configs/functions/has_capacity_d1.tsv")
DEFAULT_PRODUCES_TABLE: Final = Path("configs/functions/scfa_produces_d1.tsv")

CAPACITY_COLUMNS: Final = (
    "silva_taxon_id",
    "gtdb_taxon_id",
    "function_id",
    "species_with_ko",
    "species",
)


@dataclass(frozen=True)
class CapacityRow:
    """Un género `1:1` y un KO de los aprobados que trae alguna de sus especies del catálogo."""

    taxon_id: str
    gtdb_taxon_id: str
    function_id: str
    species_with_ko: int
    species: int


@dataclass(frozen=True)
class ProducesRow:
    """Una relación `function → produces → metabolite` aprobada (#257)."""

    function_id: str
    metabolite_id: str
    evidence_method: str
    evidence_source: str


def _data_rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        lines = (line for line in handle if not line.startswith("#"))
        yield from csv.DictReader(lines, delimiter="\t")


def load_produces_table(path: Path | str = DEFAULT_PRODUCES_TABLE) -> tuple[ProducesRow, ...]:
    """Relaciones `produces` aprobadas.

    Raises:
        ValueError: si una fila no es una anotación de base de datos con `<base>@<versión>`.
    """
    rows: list[ProducesRow] = []
    for line in _data_rows(Path(path)):
        row = ProducesRow(
            function_id=line["function_id"],
            metabolite_id=line["metabolite_id"],
            evidence_method=line["evidence_method"],
            evidence_source=line["evidence_source"],
        )
        if row.evidence_method != ANNOTATED_METHOD or "@" not in row.evidence_source:
            raise ValueError(
                f"{path}: {row.function_id} → {row.metabolite_id} debe declarar "
                f"{ANNOTATED_METHOD} con evidence_source '<base>@<versión>'."
            )
        rows.append(row)
    return tuple(rows)


def load_capacity_table(path: Path | str = DEFAULT_CAPACITY_TABLE) -> tuple[CapacityRow, ...]:
    """Filas de `has_capacity_d1.tsv`, sin validar contra S-04 (ver `FunctionalAnnotations`)."""
    return tuple(
        CapacityRow(
            taxon_id=line["silva_taxon_id"],
            gtdb_taxon_id=line["gtdb_taxon_id"],
            function_id=line["function_id"],
            species_with_ko=int(line["species_with_ko"]),
            species=int(line["species"]),
        )
        for line in _data_rows(Path(path))
    )


@dataclass(frozen=True)
class FunctionalAnnotations:
    """Tablas de la ruta taxón → función → metabolito, ya contrastadas entre sí."""

    capacity: tuple[CapacityRow, ...]
    produces: tuple[ProducesRow, ...]
    taxon_links: dict[str, Any]
    """Tabla S-04 con la forma que EDG-04 lee de `metadata.json`."""

    @classmethod
    def load(
        cls,
        s04_table: Path | str = DEFAULT_S04_TABLE,
        capacity_table: Path | str = DEFAULT_CAPACITY_TABLE,
        produces_table: Path | str = DEFAULT_PRODUCES_TABLE,
    ) -> FunctionalAnnotations:
        """Carga las tres tablas y comprueba que se unen.

        Raises:
            ValueError: si una fila de capacidad parte de un taxón sin enlace `1:1`, contradice el
                género GTDB de S-04 o apunta a una función sin relación `produces` aprobada.
        """
        mapping = SilvaGtdbMapping.load_tsv(s04_table, version=S04_TABLE_VERSION)
        capacity = load_capacity_table(capacity_table)
        produces = load_produces_table(produces_table)
        check_capacity(capacity, mapping, {row.function_id for row in produces})
        return cls(capacity, produces, mapping.to_metadata_dict())


def check_capacity(
    capacity: Iterable[CapacityRow], mapping: SilvaGtdbMapping, functions: set[str]
) -> None:
    """Exige enlace `1:1` con el mismo género GTDB y una función aprobada en cada fila."""
    for row in capacity:
        gtdb = mapping.map_silva_to_gtdb(row.taxon_id)
        if gtdb is None:
            raise ValueError(f"{row.taxon_id} no tiene enlace 1:1 en S-04: no genera has_capacity.")
        if gtdb != row.gtdb_taxon_id:
            raise ValueError(
                f"{row.taxon_id} enlaza con {gtdb} en S-04, no con {row.gtdb_taxon_id}."
            )
        if row.function_id not in functions:
            raise ValueError(f"{row.function_id} no tiene una relación produces aprobada.")
        if not 0 < row.species_with_ko <= row.species:
            raise ValueError(
                f"{row.taxon_id}, {row.function_id}: soporte inválido "
                f"{row.species_with_ko}/{row.species}."
            )


__all__ = [
    "ANNOTATED_METHOD",
    "ANNOTATION_SOURCE",
    "CAPACITY_COLUMNS",
    "CATALOGUE_EVIDENCE_SOURCE",
    "DEFAULT_CAPACITY_TABLE",
    "DEFAULT_PRODUCES_TABLE",
    "DEFAULT_S04_TABLE",
    "FUNCTION_TYPE",
    "S04_TABLE_VERSION",
    "CapacityRow",
    "FunctionalAnnotations",
    "ProducesRow",
    "check_capacity",
    "load_capacity_table",
    "load_produces_table",
]
