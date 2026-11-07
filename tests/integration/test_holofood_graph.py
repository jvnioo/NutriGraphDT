"""Grafos heterogéneos reales desde la fuente D1 HoloFood (A39-1 #35, A39-2 #36).

Recorre el flujo completo sobre el fixture real `tests/fixtures/holofood/`: `DataPipeline` →
`attach_sample_context` → `build_hetero_graph` → `audit_built_graphs`. Con las reglas 1.3.0
(propuesta de `docs/graph/evidence-and-scenario-proposal.md` corregida por Investigación), los
grafos reales con AGCC no tienen `ERROR` y son entregables, y uno sin AGCC no lo es (NOD-12,
D-08); si Investigación cambia esas reglas, esta prueba debe actualizarse junto con
`docs/graph/real-graph-validation-report.md`. Requiere el extra `graph`.
"""

from __future__ import annotations

import csv
import dataclasses
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from nutrigraphdt.data.config import load_sources  # noqa: E402
from nutrigraphdt.data.functions import FunctionalAnnotations  # noqa: E402
from nutrigraphdt.data.integration import attach_sample_context  # noqa: E402
from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader  # noqa: E402
from nutrigraphdt.data.pipeline import DataPipeline  # noqa: E402
from nutrigraphdt.data.schema import NormalizedTabularDataset  # noqa: E402
from nutrigraphdt.data.taxonomy import lineage_group  # noqa: E402
from nutrigraphdt.graph.audit import BuildAudit, audit_built_graphs  # noqa: E402
from nutrigraphdt.graph.builder import (  # noqa: E402
    HeteroGraphs,
    add_reverse_edges,
    build_hetero_graph,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "holofood"
SOURCES = load_sources(REPO_ROOT / "configs" / "sources.json")


def _source(source_id: str, file_name: str):  # type: ignore[no-untyped-def]
    return dataclasses.replace(SOURCES[source_id], path_or_url=str(FIXTURES / file_name))


def _tables() -> NormalizedTabularDataset:
    abundance = _source("D1_holofood", "abundance_ssu_caecum.tsv")
    tables = DataPipeline({"D1_holofood": abundance}).run(["D1_holofood"]).dataset
    tables, _ = attach_sample_context(
        tables,
        metadata=MetadataLoader(_source("D1_holofood_metadata", "metadata.tsv")).load(),
        metabolites=MetaboliteLoader(
            _source("D1_holofood_scfa_content", "scfa_caecum_content.tsv")
        ).load(),
    )
    return tables


@pytest.fixture(scope="module")
def built() -> tuple[HeteroGraphs, BuildAudit]:
    result = build_hetero_graph(_tables())
    return result, audit_built_graphs(result)


def test_one_graph_per_animal_with_taxa_host_diet_and_scfa(
    built: tuple[HeteroGraphs, BuildAudit],
) -> None:
    graphs, _ = built
    assert len(graphs.graphs) == 6
    for data in graphs.graphs.values():
        # Contrato v2 §6 (#150): p__Actinobacteria y c__Actinobacteria ya no se suman en
        # un solo nodo por colisión, pasando de 439 a 440 nodos taxonómicos distintos.
        assert data["taxon"].num_nodes == 440
        assert data["host"].num_nodes == 1
        assert data["diet"].num_nodes == 1
        assert data["metabolite"].num_nodes == 8
        assert bool(data["metabolite"].y_mask.all())
        assert data["metabolite", "measured_in", "host"].edge_index.shape == (2, 8)
        assert not data.is_synthetic


def test_targets_match_the_source_values(built: tuple[HeteroGraphs, BuildAudit]) -> None:
    graphs, _ = built
    with (FIXTURES / "scfa_caecum_content.tsv").open(encoding="utf-8") as handle:
        rows = {row["sample_id"]: row for row in csv.DictReader(handle, delimiter="\t")}
    for graph_id, data in graphs.graphs.items():
        sample = graph_id.split(":", 1)[1]
        acetate = data["metabolite"].node_id.index("acetate")
        expected = float(rows[sample]["Acetic acid"])
        assert float(data["metabolite"].y[acetate, 0]) == pytest.approx(expected)


def test_taxa_declare_their_rank(built: tuple[HeteroGraphs, BuildAudit]) -> None:
    graphs, _ = built
    taxa = [n for n in graphs.records.nodes if n["node_type"] == "taxon"]
    levels = {n["attributes"]["taxonomy_level"] for n in taxa}
    assert {"genus", "species"} <= levels
    assert sum(level is None for level in levels) <= 1


def test_real_graphs_have_no_errors_and_are_deliverable(
    built: tuple[HeteroGraphs, BuildAudit],
) -> None:
    graphs, audit = built
    rules = {finding.rule_id for finding in audit.report.findings}
    assert not {rule for rule in rules if rule.startswith("TEN")}
    assert not audit.report.errors, audit.report.errors[:3]
    assert set(audit.report.deliverable_graph_ids) == set(graphs.graphs)
    assert audit.contracts.invalid_edges == 0
    assert audit.contracts.invalid_nodes == 0


def test_a_real_graph_without_scfa_is_not_deliverable() -> None:
    tables = _tables()
    dropped = tables.targets[0].graph_id
    tables = dataclasses.replace(
        tables, targets=[t for t in tables.targets if t.graph_id != dropped]
    )

    audit = audit_built_graphs(build_hetero_graph(tables))

    assert [(f.rule_id, f.graph_id) for f in audit.report.errors] == [("NOD-12", dropped)]
    assert audit.report.errors[0].location["node_types"] == ["metabolite"]
    assert dropped not in audit.report.deliverable_graph_ids
    assert len(audit.report.deliverable_graph_ids) == 5


# ---------------------------------------------------------------------------
# Agregación a género y ruta taxón → función → metabolito (#175)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def annotated() -> tuple[HeteroGraphs, BuildAudit]:
    source = SOURCES["D1_holofood"]
    abundance = dataclasses.replace(
        source,
        path_or_url=str(FIXTURES / "abundance_ssu_caecum.tsv"),
        options={**source.options, "aggregate_to_genus": True},
    )
    tables = DataPipeline({"D1_holofood": abundance}).run(["D1_holofood"]).dataset
    tables, _ = attach_sample_context(
        tables,
        metadata=MetadataLoader(_source("D1_holofood_metadata", "metadata.tsv")).load(),
        metabolites=MetaboliteLoader(
            _source("D1_holofood_scfa_content", "scfa_caecum_content.tsv")
        ).load(),
    )
    result = build_hetero_graph(
        tables,
        annotations=FunctionalAnnotations.load(
            REPO_ROOT / "configs" / "taxonomy" / "s04_silva132_gtdb_r207.tsv",
            REPO_ROOT / "configs" / "functions" / "has_capacity_d1.tsv",
            REPO_ROOT / "configs" / "functions" / "scfa_produces_d1.tsv",
        ),
    )
    return result, audit_built_graphs(result)


def _edges(records_edges: list[dict[str, Any]], relation: str) -> list[dict[str, Any]]:
    return [edge for edge in records_edges if edge["relation_type"] == relation]


def test_taxa_are_genera_or_residuals_and_still_sum_to_one(
    annotated: tuple[HeteroGraphs, BuildAudit],
) -> None:
    built_graphs, _ = annotated
    for data in built_graphs.graphs.values():
        ids = data["taxon"].node_id
        assert not [taxon for taxon in ids if taxon.startswith("s__")]
        assert not [t for t in ids if t.startswith("g__") and ";" in t]
        assert float(data["taxon"].x.sum()) == pytest.approx(1.0, abs=1e-4)
        # Una especie sin género en su linaje no crea un género con el nombre de su familia.
        assert "g__Coriobacteriaceae" not in ids


def test_annotated_graphs_are_deliverable_and_have_no_new_findings(
    annotated: tuple[HeteroGraphs, BuildAudit],
) -> None:
    built_graphs, audit = annotated
    assert not audit.report.errors, audit.report.errors[:3]
    assert set(audit.report.deliverable_graph_ids) == set(built_graphs.graphs)
    assert audit.contracts.invalid_nodes == 0
    assert audit.contracts.invalid_edges == 0
    rules = {finding.rule_id for finding in audit.report.findings}
    assert not {rule for rule in rules if rule.startswith("TEN")}
    assert not rules & {"EDG-04", "EDG-05", "EDG-08", "NOD-11"}


def test_only_one_to_one_genera_of_the_table_get_capacity(
    annotated: tuple[HeteroGraphs, BuildAudit],
) -> None:
    built_graphs, _ = annotated
    edges = _edges(built_graphs.records.edges, "has_capacity")
    assert edges
    sources = {edge["source_id"] for edge in edges}
    assert sources <= set(built_graphs.records.metadata["taxon_links"]["one_to_one"])
    assert "g__Faecalibacterium" in sources
    # El nombre SILVA se conserva: el enlace es con g__Anaerotignum.
    assert "g__Tyzzerella" in sources
    assert not {"g__Bifidobacterium", "g__Anaerotignum", "g__Bacteroides"} & sources
    assert not [source for source in sources if ";" in source]
    for edge in edges:
        assert edge["evidence_status"] == "annotated"
        assert edge["evidence_method"] == "database_annotation"
        assert edge["evidence_source"] == "mgnify-chicken-gut@v1.0.1"
        assert edge["target_id"].startswith("ko:K")


def test_produces_links_only_carried_functions_and_measured_scfa(
    annotated: tuple[HeteroGraphs, BuildAudit],
) -> None:
    built_graphs, _ = annotated
    records = built_graphs.records
    edges = _edges(records.edges, "produces")
    assert edges
    for edge in edges:
        assert edge["evidence_source"] == "KEGG@120.0"
        assert edge["target_id"] in {"acetate", "propionate", "butyrate"}
    function_ids = {node["node_id"] for node in records.nodes if node["node_type"] == "function"}
    assert {edge["source_id"] for edge in edges} <= function_ids
    assert {edge["target_id"] for edge in _edges(records.edges, "has_capacity")} == function_ids
    # pduW e ydiF no tienen portador entre los géneros enlazados.
    assert not {"ko:K19697", "ko:K19709"} & function_ids


def test_edges_reach_the_tensors_with_their_reverse_relations(
    annotated: tuple[HeteroGraphs, BuildAudit],
) -> None:
    built_graphs, _ = annotated
    data = add_reverse_edges(next(iter(built_graphs.graphs.values())))
    assert data["taxon", "has_capacity", "function"].edge_index.size(1) > 0
    assert data["function", "produces", "metabolite"].edge_index.size(1) > 0
    assert data["function", "rev_has_capacity", "taxon"].edge_index.size(1) > 0
    assert data["function"].x.shape[1] == 0


def test_taxon_nodes_keep_the_lineage_up_to_the_working_rank(
    annotated: tuple[HeteroGraphs, BuildAudit],
) -> None:
    built_graphs, _ = annotated
    taxa = {n["node_id"]: n for n in built_graphs.records.nodes if n["node_type"] == "taxon"}
    faecali = taxa["g__Faecalibacterium"]["attributes"]
    assert faecali["taxonomy_level"] == "genus"
    assert faecali["taxonomy_id"].endswith("f__Ruminococcaceae;g__Faecalibacterium")
    assert lineage_group(faecali["taxonomy_id"]) == "f__Ruminococcaceae"
