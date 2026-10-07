"""Grafos heterogéneos reales desde la fuente D1 HoloFood (A39-1 #35, A39-2 #36).

Recorre el flujo completo sobre el fixture real `tests/fixtures/holofood/`: `DataPipeline` →
`attach_sample_context` → `build_hetero_graph` → `audit_built_graphs`. Fija los hallazgos
bloqueantes conocidos (EDG-04, INS-03 y MET-01, ver `docs/real-graph-validation-report.md`):
si una decisión de Investigación cambia las reglas, esta prueba debe actualizarse junto con el
reporte. Requiere el extra `graph`.
"""

from __future__ import annotations

import csv
import dataclasses
from pathlib import Path

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from nutrigraphdt.data.config import load_sources  # noqa: E402
from nutrigraphdt.data.integration import attach_sample_context  # noqa: E402
from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader  # noqa: E402
from nutrigraphdt.data.pipeline import DataPipeline  # noqa: E402
from nutrigraphdt.graph.audit import BuildAudit, audit_built_graphs  # noqa: E402
from nutrigraphdt.graph.builder import HeteroGraphs, build_hetero_graph  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "holofood"
SOURCES = load_sources(REPO_ROOT / "configs" / "sources.json")

KNOWN_BLOCKING_RULES = {"EDG-04", "INS-03", "MET-01"}


def _source(source_id: str, file_name: str):  # type: ignore[no-untyped-def]
    return dataclasses.replace(SOURCES[source_id], path_or_url=str(FIXTURES / file_name))


@pytest.fixture(scope="module")
def built() -> tuple[HeteroGraphs, BuildAudit]:
    abundance = _source("D1_holofood", "abundance_ssu_caecum.tsv")
    tables = DataPipeline({"D1_holofood": abundance}).run(["D1_holofood"]).dataset
    tables, _ = attach_sample_context(
        tables,
        metadata=MetadataLoader(_source("D1_holofood_metadata", "metadata.tsv")).load(),
        metabolites=MetaboliteLoader(
            _source("D1_holofood_scfa_content", "scfa_caecum_content.tsv")
        ).load(),
    )
    result = build_hetero_graph(tables)
    return result, audit_built_graphs(result)


def test_one_graph_per_animal_with_taxa_host_diet_and_scfa(
    built: tuple[HeteroGraphs, BuildAudit],
) -> None:
    graphs, _ = built
    assert len(graphs.graphs) == 6
    for data in graphs.graphs.values():
        assert data["taxon"].num_nodes == 439
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


def test_tensors_pass_every_rule_and_only_known_policy_errors_block(
    built: tuple[HeteroGraphs, BuildAudit],
) -> None:
    _, audit = built
    rules = {finding.rule_id for finding in audit.report.findings}
    assert not {rule for rule in rules if rule.startswith("TEN")}
    assert {finding.rule_id for finding in audit.report.errors} == KNOWN_BLOCKING_RULES
    assert audit.contracts.invalid_edges == 0
