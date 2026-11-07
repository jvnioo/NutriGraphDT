#!/usr/bin/env python3
"""Construye la tabla S-04 (SILVA 132 → GTDB r207) para todos los géneros de D1 (#236).

Evidencia: cada genoma de GTDB r207 trae en `ssu_silva_blast_subject_id` la secuencia SILVA
(`acceso.inicio.fin`) con la que mejor alinea su 16S. Esa secuencia se busca en la taxonomía
de **SILVA 132 Ref** (`taxmap_slv_ssu_ref_132.txt.gz`), que asigna a cada secuencia su ruta y,
con `tax_slv_ssu_132.txt`, su género SILVA 132. Así, la etiqueta es de SILVA 132, la versión de
D1, y no la de la versión más reciente que trae la columna `ssu_silva_taxonomy` de GTDB.
Los genomas cuyo mejor alineamiento es una secuencia ausente de SILVA 132 Ref quedan fuera.

Solo cuentan genomas de aislados (`ncbi_genome_category = none`) cuyo alineamiento tiene al
menos `--min-identity` de identidad (94,5 %, el umbral de género de Yarza et al. 2014,
doi:10.1038/nrmicro3330). Los MAG quedan fuera porque su 16S puede venir de otro organismo
(contaminación del binning; GTDB r207, `FILE_DESCRIPTIONS.txt`). Cada especie de GTDB recibe el
género SILVA 132 mayoritario de esos genomas, de modo que una especie con muchos genomas
secuenciados no pesa más que otra. Para cada género de D1 se cuentan las especies GTDB que lo
llevan, por género GTDB.

Clasificación (parámetros en la línea de comandos; los valores por defecto son los de la
decisión de Investigación, `docs/research/decision_has_capacity_D1.md`):

- `1:1`: al menos `--min-species` especies llevan el género SILVA y el género GTDB más
  frecuente reúne al menos `--share` de ellas;
- `1:N`: hay al menos `--min-species` especies y ningún género GTDB alcanza `--share`, o lo
  alcanza pero el catálogo trae otro género con la misma raíz (por ejemplo, `Barnesiella_A`
  junto a `Barnesiella`), que la evidencia de aislados no puede descartar;
- `sin par`: menos de `--min-species` especies (evidencia insuficiente).

Uso solo de la biblioteca estándar. Entradas, todas públicas y sin costo:

- `data/raw/D1_holofood/abundance_ssu_caecum.tsv` (`scripts/fetch_holofood.py`);
- `bac120_metadata_r207.tar.gz` y `ar53_metadata_r207.tar.gz` de
  https://data.gtdb.ecogenomic.org/releases/release207/207.0/ (CC BY-SA 4.0);
- `taxmap_slv_ssu_ref_132.txt.gz` y `tax_slv_ssu_132.txt` de
  https://www.arb-silva.de/fileadmin/silva_databases/release_132/Exports/taxonomy/ (CC BY 4.0);
- `genomes-all_metadata.tsv` de
  https://ftp.ebi.ac.uk/pub/databases/metagenomics/mgnify_genomes/chicken-gut/v1.0.1/

    python docs/research/build_s04_silva132_gtdb_r207.py \\
        --gtdb-dir <dir> --silva-dir <dir> --catalogue-metadata genomes-all_metadata.tsv
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import re
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

ABUNDANCE = Path("data/raw/D1_holofood/abundance_ssu_caecum.tsv")
TABLE = Path("configs/taxonomy/s04_silva132_gtdb_r207.tsv")
EVIDENCE = Path("docs/research/s04_silva132_gtdb_r207_evidence.tsv")
GTDB_FILES = ("bac120_metadata_r207.tar.gz", "ar53_metadata_r207.tar.gz")
TOP_GENERA = 5


def table_header(args: argparse.Namespace) -> str:
    """Comentarios de la tabla: fuentes con versión y parámetros de la regla."""
    mags = "incluidos" if args.include_mags else "excluidos (solo aislados)"
    return (
        "# Tabla de equivalencias SILVA 132 → GTDB r207 de los géneros de D1 (S-04, #236)\n"
        "# Generada por docs/research/build_s04_silva132_gtdb_r207.py. Decisión y regla:\n"
        "# docs/research/decision_has_capacity_D1.md. Evidencia por fila:\n"
        "# docs/research/s04_silva132_gtdb_r207_evidence.tsv.\n"
        "# Fuentes: GTDB r207 (bac120_metadata_r207, ar53_metadata_r207); SILVA 132 Ref\n"
        "# (taxmap_slv_ssu_ref_132, tax_slv_ssu_132); MGnify chicken-gut v1.0.1\n"
        "# (genomes-all_metadata.tsv); D1: abundance_ssu_caecum.tsv (MGnify SSU, SILVA 132).\n"
        f"# Regla: 1:1 si >= {args.min_species} especies GTDB llevan el género SILVA 132 y el\n"
        f"# género GTDB dominante reúne >= {args.share:.0%} de ellas, sin otro género de la misma\n"
        f"# raíz en el catálogo; identidad >= {args.min_identity} %; MAG {mags}.\n"
        "# Relaciones: 1:1 (unívoco), 1:N (dividido en GTDB), sin par (evidencia insuficiente)\n"
        "# Formato: silva_taxon_id\\tgtdb_taxon_id\\trelationship\\tnotes\n"
    )


def silva_name(name: str) -> str:
    """Nombre de SILVA en la forma de MGnify: espacios como guion bajo."""
    return name.strip().replace(" ", "_")


def gtdb_genus(taxonomy: str) -> str:
    match = re.search(r"g__([^;]*)", taxonomy)
    return match.group(1) if match else ""


def gtdb_species(taxonomy: str) -> str:
    match = re.search(r"s__([^;]*)", taxonomy)
    return match.group(1) if match else ""


def d1_genera(path: Path) -> tuple[Counter[str], float, float]:
    """Lecturas por género en todos los animales de la tabla, el total y el total a género."""
    reads: Counter[str] = Counter()
    total = 0.0
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        next(reader)
        for row in reader:
            count = sum(float(value) for value in row[1:])
            total += count
            match = re.search(r"(?:^|;)g__([^;]+)", row[0])
            if match:
                reads[match.group(1)] += count
    return reads, total, float(sum(reads.values()))


def silva132_genus_by_sequence(silva_dir: Path) -> dict[tuple[str, str, str], str]:
    """Género SILVA 132 de cada secuencia de SILVA 132 Ref, según el rango de su ruta."""
    rank_of: dict[str, str] = {}
    with (silva_dir / "tax_slv_ssu_132.txt").open(encoding="utf-8") as handle:
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            if len(fields) >= 3:
                rank_of[fields[0]] = fields[2]
    genus_of_path: dict[str, str] = {}
    mapping: dict[tuple[str, str, str], str] = {}
    with gzip.open(silva_dir / "taxmap_slv_ssu_ref_132.txt.gz", "rt", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        next(reader)
        for accession, start, stop, path, *_ in reader:
            genus = genus_of_path.get(path)
            if genus is None:
                genus = ""
                parts = path.rstrip(";").split(";")
                for depth in range(1, len(parts) + 1):
                    prefix = ";".join(parts[:depth]) + ";"
                    if rank_of.get(prefix) == "genus":
                        genus = silva_name(parts[depth - 1])
                genus_of_path[path] = genus
            if genus:
                mapping[(accession, start, stop)] = genus
    return mapping


def species_labels(
    gtdb_dir: Path,
    silva: dict[tuple[str, str, str], str],
    min_identity: float,
    isolates_only: bool,
) -> tuple[dict[str, tuple[str, str]], Counter[str]]:
    """Género SILVA 132 mayoritario de cada especie GTDB y su género GTDB."""
    csv.field_size_limit(10**9)
    votes: dict[str, Counter[str]] = defaultdict(Counter)
    genus_of_species: dict[str, str] = {}
    stats: Counter[str] = Counter()
    for name in GTDB_FILES:
        with tarfile.open(gtdb_dir / name) as archive:
            member = next(item for item in archive.getmembers() if item.isfile())
            handle = archive.extractfile(member)
            if handle is None:
                raise ValueError(f"{member.name} no se puede leer.")
            text = io.TextIOWrapper(handle, encoding="utf-8", newline="")
            for row in csv.DictReader(text, delimiter="\t"):
                stats["genomes"] += 1
                if isolates_only and row["ncbi_genome_category"] != "none":
                    stats["not_isolate"] += 1
                    continue
                identity = row["ssu_silva_blast_perc_identity"]
                if identity in {"", "none"} or float(identity) < min_identity:
                    stats["below_identity"] += 1
                    continue
                subject = row["ssu_silva_blast_subject_id"]
                parts = tuple(subject.rsplit(".", 2))
                genus = silva.get(parts) if len(parts) == 3 else None  # type: ignore[arg-type]
                if not genus:
                    stats["without_silva132_label"] += 1
                    continue
                stats["with_silva132_label"] += 1
                species = gtdb_species(row["gtdb_taxonomy"])
                votes[species][genus] += 1
                genus_of_species[species] = gtdb_genus(row["gtdb_taxonomy"])
    labels = {
        species: (counter.most_common(1)[0][0], genus_of_species[species])
        for species, counter in votes.items()
    }
    stats["species_with_label"] = len(labels)
    return labels, stats


def catalogue_genera(path: Path) -> Counter[str]:
    """Especies representativas del catálogo por género GTDB."""
    counts: Counter[str] = Counter()
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row["Genome"] == row["Species_rep"]:
                counts[gtdb_genus(row["Lineage"])] += 1
    return counts


def same_stem_variants(genus: str, catalogue: Counter[str]) -> list[str]:
    """Géneros del catálogo con la misma raíz que `genus` (sufijos `_A`, `_B`…), salvo él."""
    stem = re.sub(r"_[A-Z]+$", "", genus)
    return sorted(
        found
        for found in catalogue
        if found != genus and (found == stem or found.startswith(f"{stem}_"))
    )


def classify(
    top: list[tuple[str, int]], n: int, share: float, min_species: int, variants: list[str]
) -> str:
    if n < min_species:
        return "sin par"
    return "1:1" if top[0][1] / n >= share and not variants else "1:N"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--gtdb-dir", type=Path, required=True)
    parser.add_argument("--silva-dir", type=Path, required=True)
    parser.add_argument("--catalogue-metadata", type=Path, required=True)
    parser.add_argument("--abundance", type=Path, default=ABUNDANCE)
    parser.add_argument("--min-identity", type=float, default=94.5)
    parser.add_argument(
        "--include-mags", action="store_true", help="cuenta también MAG y genomas de célula única"
    )
    parser.add_argument("--share", type=float, default=0.9)
    parser.add_argument("--min-species", type=int, default=3)
    parser.add_argument("--table", type=Path, default=TABLE)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    args = parser.parse_args()

    reads, total, at_genus = d1_genera(args.abundance)
    labels, stats = species_labels(
        args.gtdb_dir,
        silva132_genus_by_sequence(args.silva_dir),
        args.min_identity,
        not args.include_mags,
    )
    catalogue = catalogue_genera(args.catalogue_metadata)

    by_silva: dict[str, Counter[str]] = defaultdict(Counter)
    for silva_genus, genus in labels.values():
        by_silva[silva_genus][genus] += 1

    rows = []
    for name in sorted(reads, key=lambda item: (-reads[item], item)):
        counter = by_silva.get(name, Counter())
        n = sum(counter.values())
        top = counter.most_common(TOP_GENERA)
        dominant = top[0][0] if top else ""
        variants = same_stem_variants(dominant, catalogue) if dominant else []
        relationship = classify(top, n, args.share, args.min_species, variants)
        rows.append(
            {
                "silva_taxon_id": f"g__{name}",
                "pct_genus_reads": f"{100 * reads[name] / at_genus:.3f}",
                "gtdb_species_with_label": str(n),
                "gtdb_genera_top": ", ".join(f"{genus}:{count}" for genus, count in top),
                "dominant_share": f"{top[0][1] / n:.3f}" if n else "",
                "dominant_gtdb_genus": f"g__{dominant}" if dominant else "",
                "catalogue_species_of_dominant": str(catalogue.get(dominant, 0)) if top else "",
                "catalogue_same_stem": ", ".join(f"{g}:{catalogue[g]}" for g in variants),
                "relationship": relationship,
            }
        )

    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    with args.evidence.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)

    with args.table.open("w", encoding="utf-8", newline="") as handle:
        handle.write(table_header(args))
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["silva_taxon_id", "gtdb_taxon_id", "relationship", "notes"])
        for row in rows:
            n = int(row["gtdb_species_with_label"])
            if row["relationship"] == "sin par":
                note = f"{n} especies GTDB r207 con etiqueta SILVA 132; evidencia insuficiente"
                gtdb = ""
            else:
                note = (
                    f"{n} especies GTDB r207 con etiqueta SILVA 132: {row['gtdb_genera_top']}; "
                    f"catálogo: {row['catalogue_species_of_dominant']} especies del dominante"
                )
                if row["catalogue_same_stem"]:
                    note += f", y {row['catalogue_same_stem']} con la misma raíz"
                gtdb = row["dominant_gtdb_genus"] if row["relationship"] == "1:1" else ""
            writer.writerow([row["silva_taxon_id"], gtdb, row["relationship"], note])

    one = [row for row in rows if row["relationship"] == "1:1"]
    linked = [row for row in one if row["catalogue_species_of_dominant"] not in {"", "0"}]
    linked_reads = sum(reads[row["silva_taxon_id"].removeprefix("g__")] for row in linked)
    print(
        f"GTDB r207: {stats['genomes']} genomas; {stats['not_isolate']} no son aislados, "
        f"{stats['below_identity']} bajo la identidad mínima o sin 16S, "
        f"{stats['with_silva132_label']} con etiqueta SILVA 132 "
        f"({stats['species_with_label']} especies)."
    )
    print(
        f"D1: {len(rows)} géneros. 1:1 {len(one)}, de ellos {len(linked)} en el catálogo "
        f"({100 * linked_reads / at_genus:.1f} % de las lecturas a género, "
        f"{100 * linked_reads / total:.1f} % del total)."
    )
    print(f"Tabla: {args.table}. Evidencia: {args.evidence}")


if __name__ == "__main__":
    main()
