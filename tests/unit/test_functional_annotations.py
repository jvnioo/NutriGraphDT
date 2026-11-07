"""Tablas de la ruta taxón → función → metabolito de D1 y su cruce con el catálogo (#175)."""

from __future__ import annotations

from pathlib import Path

import pytest

from nutrigraphdt.data.acquisition.mgnify_catalogue import (
    annotated_kos,
    capacity_rows,
    species_by_genus,
)
from nutrigraphdt.data.functions import (
    CapacityRow,
    FunctionalAnnotations,
    check_capacity,
    load_produces_table,
)
from nutrigraphdt.data.taxonomy import SilvaGtdbEntry, SilvaGtdbMapping

REPO_ROOT = Path(__file__).resolve().parents[2]
S04 = REPO_ROOT / "configs" / "taxonomy" / "s04_silva132_gtdb_r207.tsv"
CAPACITY = REPO_ROOT / "configs" / "functions" / "has_capacity_d1.tsv"
PRODUCES = REPO_ROOT / "configs" / "functions" / "scfa_produces_d1.tsv"
KO = "ko:K00925"


@pytest.fixture(scope="module")
def annotations() -> FunctionalAnnotations:
    return FunctionalAnnotations.load(S04, CAPACITY, PRODUCES)


def test_versioned_tables_join_with_the_figures_of_the_decision(
    annotations: FunctionalAnnotations,
) -> None:
    assert len(annotations.capacity) == 62
    assert len({row.taxon_id for row in annotations.capacity}) == 38
    assert len({row.function_id for row in annotations.capacity}) == 7
    assert len(annotations.produces) == 9
    assert {row.metabolite_id for row in annotations.produces} == {
        "acetate",
        "propionate",
        "butyrate",
    }
    assert len(annotations.taxon_links["one_to_one"]) == 118


def test_only_one_to_one_genera_carry_functions(annotations: FunctionalAnnotations) -> None:
    taxa = {row.taxon_id for row in annotations.capacity}
    # `1:N` y `sin par`, aunque el catálogo tenga un género con ese nombre.
    assert not taxa & {"g__Bifidobacterium", "g__Parabacteroides", "g__Mucispirillum"}
    assert not any(";" in taxon or not taxon.startswith("g__") for taxon in taxa)
    assert taxa <= set(annotations.taxon_links["one_to_one"])


def test_the_catalogue_is_queried_with_the_gtdb_genus(annotations: FunctionalAnnotations) -> None:
    by_taxon = {row.taxon_id: row.gtdb_taxon_id for row in annotations.capacity}
    assert by_taxon["g__Tyzzerella"] == "g__Anaerotignum"
    assert by_taxon["g__Gardnerella"] == "g__Bifidobacterium"
    assert by_taxon["g__Faecalibacterium"] == "g__Faecalibacterium"


def _mapping() -> SilvaGtdbMapping:
    return SilvaGtdbMapping(
        [
            SilvaGtdbEntry("g__Uno", "g__UnoGtdb", "1:1"),
            SilvaGtdbEntry("g__Varios", None, "1:N"),
            SilvaGtdbEntry("g__Nada", None, "sin par"),
        ]
    )


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (CapacityRow("g__Varios", "g__Varios", KO, 1, 1), "enlace 1:1"),
        (CapacityRow("g__Nada", "g__Nada", KO, 1, 1), "enlace 1:1"),
        (CapacityRow("f__Fam;g__", "f__Fam;g__", KO, 1, 1), "enlace 1:1"),
        (CapacityRow("g__Uno", "g__Uno", KO, 1, 1), "enlaza con"),
        (CapacityRow("g__Uno", "g__UnoGtdb", "ko:K99999", 1, 1), "produces aprobada"),
        (CapacityRow("g__Uno", "g__UnoGtdb", KO, 3, 2), "soporte"),
        (CapacityRow("g__Uno", "g__UnoGtdb", KO, 0, 2), "soporte"),
    ],
)
def test_capacity_rows_must_join_with_s04_and_produces(row: CapacityRow, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        check_capacity([row], _mapping(), {KO})


def test_produces_rows_must_be_database_annotations(tmp_path: Path) -> None:
    table = tmp_path / "produces.tsv"
    table.write_text(
        "function_id\tmetabolite_id\tevidence_method\tevidence_source\tnotes\n"
        f"{KO}\tacetate\tdatabase_annotation\tKEGG\tsin versión\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="evidence_source"):
        load_produces_table(table)


def _write_metadata(path: Path) -> Path:
    lineage = "d__Bacteria;p__F;c__C;o__O;f__Fam;g__{};s__{}"
    rows = [
        ("G1", "G1", lineage.format("UnoGtdb", "a")),
        ("G2", "G2", lineage.format("UnoGtdb", "b")),
        ("G3", "G1", lineage.format("UnoGtdb", "a")),  # no representativo
        ("G4", "G4", lineage.format("Otro", "c")),
        ("G5", "G5", "d__Bacteria;p__F;c__C;o__O;f__Fam;g__;s__"),
    ]
    path.write_text(
        "Genome\tSpecies_rep\tLineage\n" + "".join(f"{g}\t{r}\t{ln}\n" for g, r, ln in rows),
        encoding="utf-8",
    )
    return path


def test_species_by_genus_keeps_representatives_only(tmp_path: Path) -> None:
    assert species_by_genus(_write_metadata(tmp_path / "metadata.tsv")) == {
        "g__UnoGtdb": ["G1", "G2"],
        "g__Otro": ["G4"],
    }


def test_annotated_kos_reads_the_kegg_column(tmp_path: Path) -> None:
    path = tmp_path / "G1_eggNOG.tsv"
    path.write_text(
        "## emapper\n"
        "#query\tseed\tKEGG_ko\tPFAMs\n"
        "gen1\ts\tko:K00925,ko:K00929\tA\n"
        "gen2\ts\t-\tB\n"
        "gen3\ts\tko:K00925\tC\n"
        "## fin\n",
        encoding="utf-8",
    )
    assert annotated_kos(path) == frozenset({"ko:K00925", "ko:K00929"})


def test_capacity_counts_species_and_ignores_other_functions_and_missing_genera() -> None:
    kos = {
        "G1": frozenset({KO, "ko:K00929", "ko:K11111"}),
        "G2": frozenset({KO}),
    }
    rows = capacity_rows(
        {"g__Uno": "g__UnoGtdb", "g__SinCatalogo": "g__Ausente"},
        {"g__UnoGtdb": ["G1", "G2"]},
        frozenset({KO, "ko:K00929"}),
        kos.__getitem__,
    )
    assert rows == [
        CapacityRow("g__Uno", "g__UnoGtdb", KO, 2, 2),
        CapacityRow("g__Uno", "g__UnoGtdb", "ko:K00929", 1, 2),
    ]


def test_two_silva_genera_with_the_same_gtdb_genus_get_their_own_rows() -> None:
    rows = capacity_rows(
        {"g__A": "g__Comun", "g__B": "g__Comun"},
        {"g__Comun": ["G1"]},
        frozenset({KO}),
        lambda _: frozenset({KO}),
    )
    assert {row.taxon_id for row in rows} == {"g__A", "g__B"}
