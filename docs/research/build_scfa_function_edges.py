#!/usr/bin/env python3
"""Relaciones `function → produces → metabolite` de D1 y su unión con `has_capacity` (#257).

La función es un ortólogo de KEGG (KO). El conjunto se limita a los KO del paso terminal que
libera acetato, propionato o n-butirato desde su acil-CoA o acil-fosfato, según la decisión de
Investigación (`docs/research/decision_produces_D1.md`). Para cada par KO → AGCC el script
comprueba en KEGG REST que el KO esté enlazado a las reacciones declaradas y que esas reacciones
contengan el compuesto. Si KEGG ya no lo sostiene, se detiene en lugar de escribir la arista.

Con `--eggnog-dir`, mide además qué KO del conjunto tienen las especies representativas del
catálogo MGnify chicken-gut v1.0.1 de cada género `1:1` de la tabla S-04. Es la regla de
`has_capacity` de la decisión, aplicada como vista previa para #175. Los archivos
`<especie>_eggNOG.tsv` que falten se descargan del FTP del catálogo.

Solo usa la biblioteca estándar y servicios públicos sin costo (KEGG REST es de uso libre para
fines académicos; FTP de MGnify).

    python docs/research/build_scfa_function_edges.py --kegg-release 120.0 \\
        --catalogue-metadata genomes-all_metadata.tsv --eggnog-dir <dir>
"""

from __future__ import annotations

import argparse
import csv
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

KEGG_REST = "https://rest.kegg.jp"
CATALOGUE_FTP = (
    "https://ftp.ebi.ac.uk/pub/databases/metagenomics/mgnify_genomes/chicken-gut/v1.0.1/"
    "species_catalogue"
)
S04_TABLE = Path("configs/taxonomy/s04_silva132_gtdb_r207.tsv")
PRODUCES = Path("configs/functions/scfa_produces_d1.tsv")
CAPACITY = Path("docs/research/scfa_has_capacity_preview.tsv")

COMPOUNDS = {"acetate": "C00033", "propionate": "C00163", "butyrate": "C00246"}

# (KO, metabolito, reacciones KEGG, ruta). La ruta es la del paso terminal que libera el AGCC.
SCFA_FUNCTIONS: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    ("K00925", "acetate", ("R00315",), "ackA, acetato quinasa; ruta Pta-AckA (módulo M00579)"),
    ("K01026", "propionate", ("R00928", "R01449"), "pct, propionato CoA-transferasa; acrilato"),
    ("K22214", "propionate", ("R11773",), "scpC, propionil-CoA:succinil-CoA transferasa"),
    ("K00932", "propionate", ("R01353",), "tdcD, propionato quinasa"),
    ("K19697", "propionate", ("R01353",), "pduW, propionato quinasa; ruta del propanodiol"),
    ("K00929", "butyrate", ("R01688",), "buk, butirato quinasa; ruta Ptb-Buk"),
    ("K01034", "butyrate", ("R01179", "R01365"), "atoD, CoA-transferasa (subunidad alfa)"),
    ("K01035", "butyrate", ("R01179", "R01365"), "atoA, CoA-transferasa (subunidad beta)"),
    ("K19709", "butyrate", ("R01179",), "ydiF, butiril-CoA:acetato CoA-transferasa"),
)


def kegg(path: str) -> str:
    request = urllib.request.Request(
        f"{KEGG_REST}/{path}", headers={"User-Agent": "nutrigraphdt-research"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def check_in_kegg() -> str:
    """Comprueba cada KO → reacción → compuesto en KEGG y devuelve la fecha de la base KO."""
    for ko, metabolite, reactions, _ in SCFA_FUNCTIONS:
        linked = {line.split("\t")[1] for line in kegg(f"link/reaction/ko:{ko}").splitlines()}
        for reaction in reactions:
            if f"rn:{reaction}" not in linked:
                raise SystemExit(f"KEGG ya no enlaza {ko} con {reaction}.")
            equation = next(
                line for line in kegg(f"get/{reaction}").splitlines() if line.startswith("EQUATION")
            )
            if COMPOUNDS[metabolite] not in equation:
                raise SystemExit(f"{reaction} no contiene {COMPOUNDS[metabolite]} ({metabolite}).")
    info = kegg("info/ko")
    match = re.search(r"Last update\s+(\S+)", info)
    return match.group(1) if match else "desconocida"


def write_produces(path: Path, release: str, updated: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(
            "# Relaciones function → produces → metabolite aprobadas para D1 (#257)\n"
            "# Generada por docs/research/build_scfa_function_edges.py; decisión en\n"
            "# docs/research/decision_produces_D1.md.\n"
            f"# KEGG Release {release} (base KO actualizada el {updated}), consultada por REST.\n"
            "# Formato: function_id\\tmetabolite_id\\tevidence_method\\tevidence_source\\tnotes\n"
        )
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(
            ["function_id", "metabolite_id", "evidence_method", "evidence_source", "notes"]
        )
        for ko, metabolite, reactions, route in SCFA_FUNCTIONS:
            writer.writerow(
                [
                    f"ko:{ko}",
                    metabolite,
                    "database_annotation",
                    f"KEGG@{release}",
                    f"{route}; {', '.join(reactions)}; {COMPOUNDS[metabolite]}",
                ]
            )


def one_to_one_genera(table: Path) -> dict[str, str]:
    """Género GTDB → género SILVA de cada fila `1:1` de la tabla S-04."""
    linked: dict[str, str] = {}
    with table.open(encoding="utf-8", newline="") as handle:
        rows = csv.reader((line for line in handle if not line.startswith("#")), delimiter="\t")
        next(rows)
        for silva, gtdb, relationship, *_ in rows:
            if relationship == "1:1" and gtdb:
                linked[gtdb.removeprefix("g__")] = silva
    return linked


def catalogue_species(metadata: Path, genera: set[str]) -> dict[str, list[str]]:
    """Especies representativas del catálogo por género GTDB, solo de `genera`."""
    species: dict[str, list[str]] = defaultdict(list)
    with metadata.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            match = re.search(r"g__([^;]*)", row["Lineage"])
            if row["Genome"] == row["Species_rep"] and match and match.group(1) in genera:
                species[match.group(1)].append(row["Genome"])
    return species


def annotated_kos(eggnog_dir: Path, genome: str) -> set[str]:
    """KO anotados por eggNOG en el genoma; descarga el archivo si falta."""
    path = eggnog_dir / f"{genome}_eggNOG.tsv"
    if not path.exists():
        url = f"{CATALOGUE_FTP}/{genome[:11]}/{genome}/genome/{genome}_eggNOG.tsv"
        urllib.request.urlretrieve(url, path)
    kos: set[str] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        header: list[str] | None = None
        for row in csv.reader(handle, delimiter="\t"):
            if row and row[0] == "#query":
                header = row
                continue
            if header is None or not row or row[0].startswith("#"):
                continue
            value = dict(zip(header, row, strict=False)).get("KEGG_ko", "-")
            kos.update(k.removeprefix("ko:") for k in value.split(",") if k != "-")
    return kos


def write_capacity(args: argparse.Namespace) -> None:
    linked = one_to_one_genera(args.s04_table)
    species = catalogue_species(args.catalogue_metadata, set(linked))
    args.eggnog_dir.mkdir(parents=True, exist_ok=True)
    wanted = {ko for ko, *_ in SCFA_FUNCTIONS}
    with args.capacity.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(
            ["silva_taxon_id", "gtdb_taxon_id", "function_id", "species_with_ko", "species"]
        )
        for genus in sorted(species):
            genomes = species[genus]
            found = [annotated_kos(args.eggnog_dir, genome) & wanted for genome in genomes]
            for ko in sorted(wanted):
                count = sum(ko in kos for kos in found)
                if count:
                    writer.writerow([linked[genus], f"g__{genus}", f"ko:{ko}", count, len(genomes)])
    print(f"{len(species)} géneros con especies en el catálogo. Vista previa: {args.capacity}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--kegg-release", required=True, help="por ejemplo, 120.0")
    parser.add_argument("--produces", type=Path, default=PRODUCES)
    parser.add_argument("--s04-table", type=Path, default=S04_TABLE)
    parser.add_argument("--catalogue-metadata", type=Path)
    parser.add_argument("--eggnog-dir", type=Path)
    parser.add_argument("--capacity", type=Path, default=CAPACITY)
    args = parser.parse_args()

    updated = check_in_kegg()
    write_produces(args.produces, args.kegg_release, updated)
    print(f"{len(SCFA_FUNCTIONS)} relaciones comprobadas en KEGG ({updated}): {args.produces}")
    if args.eggnog_dir is not None:
        if args.catalogue_metadata is None:
            parser.error("--eggnog-dir requiere --catalogue-metadata.")
        write_capacity(args)


if __name__ == "__main__":
    main()
