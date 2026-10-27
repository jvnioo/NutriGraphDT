"""Tests unitarios para el módulo de taxonomía, tabla S-04 y agregación a género (#150)."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from nutrigraphdt.data.loaders.abundance import AbundanceLoader
from nutrigraphdt.data.loaders.base import SourceMetadata
from nutrigraphdt.data.schema import (
    NormalizedEdgeRecord,
    NormalizedFeatureRecord,
    NormalizedInstanceRecord,
    NormalizedTabularDataset,
)
from nutrigraphdt.data.taxonomy import (
    SilvaGtdbEntry,
    SilvaGtdbMapping,
    aggregate_to_genus,
    parse_lineage_ranks,
    resolve_genus_and_residual,
)
from nutrigraphdt.graph.builder import records_from_tables

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_HOLOfood = REPO_ROOT / "tests" / "fixtures" / "holofood"
S04_MINIMAL_PATH = REPO_ROOT / "configs" / "taxonomy" / "s04_silva_gtdb_minimal.tsv"


class TestParseLineageRanks:
    """Verifica la extracción de rangos taxonómicos con prefijo de rango."""

    def test_parses_full_mgnify_lineage(self) -> None:
        lineage = (
            "sk__Bacteria;k__;p__Bacillota;c__Bacilli;o__Lactobacillales;"
            "f__Lactobacillaceae;g__Lactobacillus;s__Lactobacillus_johnsonii"
        )
        ranks = parse_lineage_ranks(lineage)
        assert ranks["phylum"] == "p__Bacillota"
        assert ranks["class"] == "c__Bacilli"
        assert ranks["order"] == "o__Lactobacillales"
        assert ranks["family"] == "f__Lactobacillaceae"
        assert ranks["genus"] == "g__Lactobacillus"
        assert ranks["species"] == "s__Lactobacillus_johnsonii"
        assert "domain" in ranks

    def test_parses_partial_lineage_stopping_at_family(self) -> None:
        lineage = (
            "sk__Bacteria;p__Firmicutes;c__Clostridia;o__Lachnospirales;f__Lachnospiraceae;g__;s__"
        )
        ranks = parse_lineage_ranks(lineage)
        assert ranks["family"] == "f__Lachnospiraceae"
        assert "genus" not in ranks
        assert "species" not in ranks

    def test_parses_metaphlan_pipe_lineage(self) -> None:
        lineage = "k__Bacteria|p__Bacteroidota|c__Bacteroidia|g__Bacteroides"
        ranks = parse_lineage_ranks(lineage)
        assert ranks["phylum"] == "p__Bacteroidota"
        assert ranks["genus"] == "g__Bacteroides"


class TestResolveGenusAndResidual:
    """Verifica la regla generalizada de nodos residuales del Contrato v2 §6."""

    def test_genus_level_returns_genus_not_residual(self) -> None:
        target_id, rank, is_residual = resolve_genus_and_residual("g__Lactobacillus", "genus")
        assert target_id == "g__Lactobacillus"
        assert rank == "genus"
        assert not is_residual

    def test_species_aggregates_to_genus(self) -> None:
        target_id, rank, is_residual = resolve_genus_and_residual(
            "s__Lactobacillus_johnsonii",
            "species",
            lineage="p__Bacillota;g__Lactobacillus;s__Lactobacillus_johnsonii",
        )
        assert target_id == "g__Lactobacillus"
        assert rank == "genus"
        assert not is_residual

    def test_species_without_lineage_extracts_binomial_genus(self) -> None:
        target_id, rank, is_residual = resolve_genus_and_residual(
            "s__Bacteroides_fragilis", "species"
        )
        assert target_id == "g__Bacteroides"
        assert rank == "genus"
        assert not is_residual

    def test_family_without_genus_goes_to_family_residual(self) -> None:
        lineage = "sk__Bacteria;p__Firmicutes;c__Clostridia;f__Lachnospiraceae;g__"
        target_id, rank, is_residual = resolve_genus_and_residual(
            "f__Lachnospiraceae", "family", lineage=lineage
        )
        assert target_id == "f__Lachnospiraceae;g__"
        assert rank == "family"
        assert is_residual

    def test_order_without_family_goes_to_order_residual(self) -> None:
        lineage = "sk__Bacteria;p__Bacteroidetes;c__Bacteroidia;o__Bacteroidales"
        target_id, rank, is_residual = resolve_genus_and_residual(
            "o__Bacteroidales", "order", lineage=lineage
        )
        assert target_id == "o__Bacteroidales;f__"
        assert rank == "order"
        assert is_residual

    def test_two_known_collisions_become_distinct_residual_nodes(self) -> None:
        # Colisión 1: p__Actinobacteria (filo) vs c__Actinobacteria (clase)
        p_id, p_rank, p_res = resolve_genus_and_residual("p__Actinobacteria", "phylum")
        c_id, c_rank, c_res = resolve_genus_and_residual("c__Actinobacteria", "class")

        assert p_res and c_res
        assert p_rank == "phylum"
        assert c_rank == "class"
        assert p_id == "p__Actinobacteria;c__"
        assert c_id == "c__Actinobacteria;o__"
        assert p_id != c_id, "p__Actinobacteria y c__Actinobacteria deben ser nodos distintos"

        # Colisión 2: p__Deferribacteres vs c__Deferribacteres
        p_def, _, _ = resolve_genus_and_residual("p__Deferribacteres", "phylum")
        c_def, _, _ = resolve_genus_and_residual("c__Deferribacteres", "class")
        assert p_def == "p__Deferribacteres;c__"
        assert c_def == "c__Deferribacteres;o__"
        assert p_def != c_def


class TestSilvaGtdbMapping:
    """Verifica la carga y consulta de la tabla de equivalencias S-04."""

    def test_loads_minimal_s04_tsv(self) -> None:
        mapping = SilvaGtdbMapping.load_tsv(S04_MINIMAL_PATH)
        assert mapping.source == "S-04"

        # Género 1:1 unívoco
        entry_ali = mapping.get_entry("g__Alistipes")
        assert entry_ali is not None
        assert entry_ali.is_one_to_one()
        assert mapping.map_silva_to_gtdb("g__Alistipes") == "g__Alistipes"

        # Género 1:N dividido en GTDB
        entry_bac = mapping.get_entry("g__Bacteroides")
        assert entry_bac is not None
        assert not entry_bac.is_one_to_one()
        assert entry_bac.relationship == "1:N"
        assert mapping.map_silva_to_gtdb("g__Bacteroides") is None

        # Género sin par
        entry_sub = mapping.get_entry("g__Subdoligranulum")
        assert entry_sub is not None
        assert entry_sub.relationship == "sin par"
        assert mapping.map_silva_to_gtdb("g__Subdoligranulum") is None

    def test_one_to_one_taxa_and_metadata_export(self) -> None:
        entries = [
            SilvaGtdbEntry("g__Alistipes", "g__Alistipes", "1:1"),
            SilvaGtdbEntry("g__Bacteroides", "g__Bacteroides", "1:N"),
            SilvaGtdbEntry("g__Lactobacillus", "g__Lactobacillus", "1:N"),
        ]
        mapping = SilvaGtdbMapping(entries, source="S-04", version="2.0.0")
        assert mapping.one_to_one_taxa() == frozenset({"g__Alistipes"})

        meta = mapping.to_metadata_dict()
        assert meta["source"] == "S-04"
        assert meta["version"] == "2.0.0"
        assert meta["one_to_one"] == ["g__Alistipes"]


class TestAggregateToGenus:
    """Verifica los criterios de aceptación de agregación a género y nodos residuales."""

    def test_relative_abundances_sum_to_one_after_aggregation(self) -> None:
        records: list[dict[str, Any]] = [
            # Muestra ANIMAL_1: mezcla de especie, género y filo residual
            {
                "sample_id": "ANIMAL_1",
                "taxon_id": "s__Lactobacillus_johnsonii",
                "taxon_level": "species",
                "value": 0.35,
                "lineage": "p__Bacillota;g__Lactobacillus;s__Lactobacillus_johnsonii",
            },
            {
                "sample_id": "ANIMAL_1",
                "taxon_id": "g__Lactobacillus",
                "taxon_level": "genus",
                "value": 0.15,
            },
            {
                "sample_id": "ANIMAL_1",
                "taxon_id": "g__Bacteroides",
                "taxon_level": "genus",
                "value": 0.20,
            },
            {
                "sample_id": "ANIMAL_1",
                "taxon_id": "f__Lachnospiraceae",
                "taxon_level": "family",
                "value": 0.20,
            },
            {
                "sample_id": "ANIMAL_1",
                "taxon_id": "p__Actinobacteria",
                "taxon_level": "phylum",
                "value": 0.10,
            },
        ]

        aggregated = aggregate_to_genus(records, normalize=True)
        sample_records = [r for r in aggregated if r["sample_id"] == "ANIMAL_1"]
        total = math.fsum(r["value"] for r in sample_records)
        assert math.isclose(total, 1.0, rel_tol=1e-9)

        # Lactobacillus debe sumar 0.35 + 0.15 = 0.50
        lac_record = next(r for r in sample_records if r["taxon_id"] == "g__Lactobacillus")
        assert math.isclose(lac_record["value"], 0.50, rel_tol=1e-9)
        assert not lac_record["is_residual"]

        # Lachnospiraceae debe ser nodo residual con 0.20
        lach_record = next(r for r in sample_records if r["taxon_id"] == "f__Lachnospiraceae;g__")
        assert math.isclose(lach_record["value"], 0.20, rel_tol=1e-9)
        assert lach_record["is_residual"]

        # p__Actinobacteria debe ser nodo residual con 0.10
        act_record = next(r for r in sample_records if r["taxon_id"] == "p__Actinobacteria;c__")
        assert math.isclose(act_record["value"], 0.10, rel_tol=1e-9)
        assert act_record["is_residual"]

    def test_both_known_collisions_remain_distinct_after_aggregation(self) -> None:
        records: list[dict[str, Any]] = [
            {
                "sample_id": "S1",
                "taxon_id": "p__Actinobacteria",
                "taxon_level": "phylum",
                "value": 0.4,
            },
            {
                "sample_id": "S1",
                "taxon_id": "c__Actinobacteria",
                "taxon_level": "class",
                "value": 0.2,
            },
            {
                "sample_id": "S1",
                "taxon_id": "p__Deferribacteres",
                "taxon_level": "phylum",
                "value": 0.3,
            },
            {
                "sample_id": "S1",
                "taxon_id": "c__Deferribacteres",
                "taxon_level": "class",
                "value": 0.1,
            },
        ]
        aggregated = aggregate_to_genus(records)
        taxa_ids = {r["taxon_id"] for r in aggregated}
        assert "p__Actinobacteria;c__" in taxa_ids
        assert "c__Actinobacteria;o__" in taxa_ids
        assert "p__Deferribacteres;c__" in taxa_ids
        assert "c__Deferribacteres;o__" in taxa_ids
        assert len(taxa_ids) == 4, "Las colisiones deben producir exactamente 4 nodos distintos"

    def test_residual_nodes_do_not_receive_functional_edges(self) -> None:
        """Verifica que los nodos residuales no reciban aristas has_capacity en GraphBuilder."""
        # 1. Crear dataset tabular normalizado con un género 1:1 y un nodo residual
        instances = [
            NormalizedInstanceRecord(
                graph_id="test:S1",
                sample_id="S1",
                species="chicken",
                gut_segment="cecum",
                study_id="study_1",
                scenario_id="observed",
                diet_treatment="CC",
                timepoint=21,
                is_synthetic=False,
                source_id="test",
            )
        ]
        features = [
            NormalizedFeatureRecord(
                graph_id="test:S1",
                node_id="g__Alistipes",
                node_type="taxon",
                feature_name="abundance",
                value=0.6,
                unit="relative_abundance",
                quality_flag="valid",
                raw_id=None,
                source_id="test",
                taxonomy_level="genus",
            ),
            NormalizedFeatureRecord(
                graph_id="test:S1",
                node_id="f__Lachnospiraceae;g__",
                node_type="taxon",
                feature_name="abundance",
                value=0.4,
                unit="relative_abundance",
                quality_flag="valid",
                raw_id=None,
                source_id="test",
                taxonomy_level="family",
            ),
        ]
        # Filas candidatas de capacidad funcional para ambos nodos
        edges = [
            NormalizedEdgeRecord(
                graph_id="test:S1",
                src_type="taxon",
                relation_type="has_capacity",
                dst_type="function",
                src_id="g__Alistipes",
                dst_id="func_kegg_1",
                evidence_status="annotated",
                evidence_method="functional_annotation",
                evidence_source="mgnify-chicken-gut@v1.0.1",
                source_id="test",
            ),
            NormalizedEdgeRecord(
                graph_id="test:S1",
                src_type="taxon",
                relation_type="has_capacity",
                dst_type="function",
                src_id="f__Lachnospiraceae;g__",
                dst_id="func_kegg_2",
                evidence_status="annotated",
                evidence_method="functional_annotation",
                evidence_source="mgnify-chicken-gut@v1.0.1",
                source_id="test",
            ),
        ]
        dataset = NormalizedTabularDataset(
            instances=instances,
            features=features,
            edges=edges,
            targets=[],
        )

        mapping = SilvaGtdbMapping.load_tsv(S04_MINIMAL_PATH)
        graph_records = records_from_tables(
            dataset,
            taxon_links=mapping.to_metadata_dict(),
        )

        # Solo g__Alistipes (con enlace 1:1 en S-04) debe recibir arista has_capacity.
        # f__Lachnospiraceae;g__ (nodo residual) NO debe recibir arista.
        capacity_edges = [e for e in graph_records.edges if e["relation_type"] == "has_capacity"]
        sources = {e["source_id"] for e in capacity_edges}
        assert "g__Alistipes" in sources
        assert "f__Lachnospiraceae;g__" not in sources
        assert graph_records.metadata["configuration"]["skipped_has_capacity"] == 1


class TestAbundanceLoaderWithGenusAggregation:
    """Verifica la integración de agregación a género en AbundanceLoader."""

    def test_load_aggregated_method_aggregates_holofood_fixture(self) -> None:
        fixture_path = FIXTURES_HOLOfood / "abundance_ssu_caecum.tsv"
        meta = SourceMetadata(
            source_id="D1_holofood",
            name="HoloFood",
            species="chicken",
            gut_segment="cecum",
            data_types=("microbiome",),
            path_or_url=str(fixture_path),
            format="tsv",
        )
        loader = AbundanceLoader(meta)
        mapping = SilvaGtdbMapping.load_tsv(S04_MINIMAL_PATH)

        payload = loader.load_aggregated(mapping_table=mapping)
        assert payload.extra["aggregated_to_genus"] is True

        # Verificar que la suma relativa por animal se mantenga en 1.0
        totals: dict[str, float] = {}
        for r in payload.raw_data:
            totals[r["sample_id"]] = totals.get(r["sample_id"], 0.0) + r["value"]
        assert all(math.isclose(v, 1.0, rel_tol=1e-9) for v in totals.values())

        # Verificar que los nodos residuales existan y estén marcados
        residuals = [r for r in payload.raw_data if r.get("is_residual")]
        assert len(residuals) > 0
        residual_ids = {r["taxon_id"] for r in residuals}
        assert any(";g__" in tid or ";o__" in tid or ";c__" in tid for tid in residual_ids)
