"""Genera `configs/functions/has_capacity_d1.tsv` desde el catálogo MGnify (#175, #257).

Cruza los géneros `1:1` de la tabla S-04, por su identificador GTDB, con la anotación eggNOG de las
especies representativas del catálogo chicken-gut v1.0.1, y conserva solo los KO con una relación
`produces` aprobada. La regla es la de `docs/research/decision_produces_D1.md`, sección 4.

Uso:

    python scripts/build_capacity_table.py

Descarga `genomes-all_metadata.tsv` y un `<genoma>_eggNOG.tsv` por especie (unos 130 MB, del FTP
público de EMBL-EBI, sin credenciales) en `--catalogue-dir`, ignorado por Git. Una segunda
ejecución reutiliza lo descargado. Si la tabla S-04 cambia, hay que regenerar esta tabla y
reconstruir los grafos.

Código de salida: `0` si escribió la tabla, `2` si falta o no se puede leer una entrada.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from nutrigraphdt.data.acquisition.mgnify_catalogue import (
    CATALOGUE_URL,
    METADATA_FILE,
    annotated_kos,
    capacity_rows,
    download,
    eggnog_url,
    species_by_genus,
    write_capacity_table,
)
from nutrigraphdt.data.functions import (
    DEFAULT_CAPACITY_TABLE,
    DEFAULT_PRODUCES_TABLE,
    DEFAULT_S04_TABLE,
    S04_TABLE_VERSION,
    load_produces_table,
)
from nutrigraphdt.data.taxonomy import SilvaGtdbMapping

DEFAULT_CATALOGUE_DIR = Path("data/raw/mgnify_chicken_gut_v1.0.1")

HEADER = (
    "# has_capacity de D1: KO aprobados que trae cada género 1:1 de S-04 en el catálogo (#175)\n"
    "# Generada por scripts/build_capacity_table.py; regla en docs/research/decision_produces_D1.md"
    ", sección 4.\n"
    "# Fuentes: {s04} (decisión de #236, v{version}); {produces} (#257);\n"
    "# MGnify chicken-gut v1.0.1, genomes pipeline v2.0.0: genomes-all_metadata.tsv y\n"
    "# <genoma>_eggNOG.tsv (eggNOG-mapper 2.1.3, columna KEGG_ko).\n"
    "# species_with_ko/species: especies representativas del género con el KO; es soporte, no entra"
    " al grafo.\n"
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera la tabla has_capacity de D1 (#175).")
    parser.add_argument("--s04-table", type=Path, default=DEFAULT_S04_TABLE)
    parser.add_argument("--produces-table", type=Path, default=DEFAULT_PRODUCES_TABLE)
    parser.add_argument("--catalogue-dir", type=Path, default=DEFAULT_CATALOGUE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_CAPACITY_TABLE)
    args = parser.parse_args(argv)

    try:
        mapping = SilvaGtdbMapping.load_tsv(args.s04_table, version=S04_TABLE_VERSION)
        functions = frozenset(row.function_id for row in load_produces_table(args.produces_table))
        links = {
            taxon: gtdb
            for taxon in sorted(mapping.one_to_one_taxa())
            if (gtdb := mapping.map_silva_to_gtdb(taxon)) is not None
        }
        metadata = args.catalogue_dir / METADATA_FILE
        download(f"{CATALOGUE_URL}/{METADATA_FILE}", metadata)
        species = species_by_genus(metadata)

        def annotations(genome: str) -> frozenset[str]:
            path = args.catalogue_dir / "eggnog" / f"{genome}_eggNOG.tsv"
            download(eggnog_url(genome), path)
            return annotated_kos(path)

        rows = capacity_rows(links, species, functions, annotations)
    except (OSError, KeyError, ValueError) as error:
        print(f"No se pudo generar la tabla: {error}", file=sys.stderr)
        return 2

    header = HEADER.format(
        s04=args.s04_table, version=S04_TABLE_VERSION, produces=args.produces_table
    )
    write_capacity_table(rows, args.output, header=header)
    linked = sum(gtdb in species for gtdb in links.values())
    print(
        f"{len(links)} enlaces 1:1, {linked} con especies en el catálogo. {len(rows)} filas, "
        f"{len({row.taxon_id for row in rows})} géneros, "
        f"{len({row.function_id for row in rows})} funciones: {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
