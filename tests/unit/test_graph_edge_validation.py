"""Pruebas del validador de aristas y consistencia de relaciones (VG-03, VG-08).

Cada regla EDG-01 a EDG-13 de `docs/graph/graph-integrity-rules.md` tiene casos negativos
construidos alterando un solo campo de un grafo sintético válido. Casi todos exigen exactamente el
hallazgo esperado, para detectar también falsos positivos y duplicados. Los grafos válidos no deben
producir ningún hallazgo.

Las pruebas verifican estructura, no validez biológica.
"""

from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from nutrigraphdt.data.synthetic import (
    ALLOWED_RELATIONS,
    NodeCountConfig,
    SyntheticEdgeConfig,
    SyntheticNodeConfig,
    find_edge_errors,
    generate_scenario_dataset,
    generate_synthetic_dataset,
)
from nutrigraphdt.graph.validation import Finding, Severity, find_edge_findings

Record = dict[str, Any]

SPEC = (
    Path(__file__).resolve().parents[2] / "docs" / "synthetic-dataset" / "synthetic-dataset-spec.md"
)

DIET_PROVIDES = ("diet", "provides", "substrate")
AVAILABLE_TO = ("substrate", "available_to", "taxon")
HAS_CAPACITY = ("taxon", "has_capacity", "function")
PRODUCES = ("function", "produces", "metabolite")
MEASURED_IN = ("metabolite", "measured_in", "host")
EXHIBITS = ("host", "exhibits", "phenotype")
INTERACTS_WITH = ("taxon", "interacts_with", "taxon")
CROSS_FEEDS = ("function", "cross_feeds", "function")

COMMON_FIELDS = [
    "graph_id",
    "source_type",
    "source_id",
    "relation_type",
    "target_type",
    "target_id",
    "evidence_id",
    "evidence_status",
    "evidence_method",
]


@dataclass
class Graph:
    """Copia mutable, con la forma de los registros JSONL, de un grafo sintético válido."""

    nodes: list[Record]
    edges: list[Record]
    metadata: Record

    def edge(self, edge_type: tuple[str, str, str], position: int = 0) -> Record:
        matches = [
            edge
            for edge in self.edges
            if (edge["source_type"], edge["relation_type"], edge["target_type"]) == edge_type
        ]
        assert len(matches) > position, f"el grafo de prueba no tiene aristas {edge_type}"
        return matches[position]

    def node(self, node_type: str, node_id: str) -> Record:
        return next(
            node
            for node in self.nodes
            if node["node_type"] == node_type and node["node_id"] == node_id
        )

    def findings(self, *, with_metadata: bool = True) -> list[Finding]:
        metadata = self.metadata if with_metadata else None
        return find_edge_findings(self.nodes, self.edges, metadata=metadata)


def _graph_from(dataset: Any) -> Graph:
    return Graph(
        nodes=copy.deepcopy([node.to_dict() for node in dataset.nodes]),
        edges=copy.deepcopy([edge.to_dict() for edge in dataset.edges]),
        metadata=copy.deepcopy(dataset.metadata),
    )


@pytest.fixture
def graph() -> Graph:
    return _graph_from(generate_synthetic_dataset())


def _only(findings: list[Finding], rule_id: str) -> Finding:
    """Exige un único hallazgo, de la regla indicada, y lo devuelve."""
    assert [finding.rule_id for finding in findings] == [rule_id], findings
    return findings[0]


# ---------------------------------------------------------------------------
# Grafos válidos: sin hallazgos
# ---------------------------------------------------------------------------


def test_default_synthetic_graph_has_no_findings(graph: Graph) -> None:
    assert graph.findings() == []
    assert graph.findings(with_metadata=False) == []


def test_scenario_dataset_has_no_findings() -> None:
    dataset = generate_scenario_dataset()

    assert find_edge_findings(dataset.nodes, dataset.edges, metadata=dataset.metadata) == []


@pytest.mark.parametrize("seed", [1, 7, 42, 99])
@pytest.mark.parametrize(
    "counts",
    [
        NodeCountConfig(),
        NodeCountConfig(
            diet=1,
            additive=1,
            substrate=1,
            taxon=1,
            function=1,
            metabolite=1,
            host=1,
            phenotype=1,
        ),
        NodeCountConfig(
            diet=3,
            additive=6,
            substrate=10,
            taxon=14,
            function=11,
            metabolite=8,
            host=2,
            phenotype=5,
        ),
    ],
    ids=["default", "minimal", "beyond-catalog"],
)
def test_generated_graphs_have_no_findings(seed: int, counts: NodeCountConfig) -> None:
    dataset = generate_synthetic_dataset(
        SyntheticNodeConfig(random_seed=seed, counts=counts),
        SyntheticEdgeConfig(random_seed=seed),
    )

    assert find_edge_findings(dataset.nodes, dataset.edges, metadata=dataset.metadata) == []


def test_dense_graph_with_every_relation_has_no_findings() -> None:
    dataset = generate_synthetic_dataset(
        edge_config=SyntheticEdgeConfig(
            relation_probabilities=dict.fromkeys(ALLOWED_RELATIONS, 1.0)
        )
    )

    assert {edge.edge_type for edge in dataset.edges} == set(ALLOWED_RELATIONS)
    assert find_edge_findings(dataset.nodes, dataset.edges, metadata=dataset.metadata) == []


def test_reverse_edges_of_the_same_relation_are_not_duplicates(graph: Graph) -> None:
    pairs = {(edge["source_id"], edge["target_id"]) for edge in graph.edges}

    assert any((target, source) in pairs for source, target in pairs)
    assert graph.findings() == []


# ---------------------------------------------------------------------------
# Comportamiento general
# ---------------------------------------------------------------------------


def test_edge_objects_and_jsonl_records_give_the_same_findings() -> None:
    dataset = generate_synthetic_dataset()
    edges = [
        replace(edge, evidence_status="observed") if position == 0 else edge
        for position, edge in enumerate(dataset.edges)
    ]

    from_objects = find_edge_findings(dataset.nodes, edges, metadata=dataset.metadata)
    from_records = find_edge_findings(
        [node.to_dict() for node in dataset.nodes],
        [edge.to_dict() for edge in edges],
        metadata=dataset.metadata,
    )

    assert from_objects == from_records
    assert [finding.rule_id for finding in from_objects] == ["EDG-04"]


def test_reports_every_finding_not_only_the_first(graph: Graph) -> None:
    graph.edge(MEASURED_IN)["attributes"]["sample_matrix"] = "plasma"
    graph.edge(HAS_CAPACITY)["evidence_status"] = "annotated"
    graph.edge(PRODUCES)["target_id"] = "synthetic:metabolite:9999"
    graph.edge(INTERACTS_WITH)["attributes"]["interaction_type"] = "mutualism"

    rule_ids = sorted(finding.rule_id for finding in graph.findings())

    assert rule_ids == ["EDG-02", "EDG-04", "EDG-07", "EDG-12"]


def test_does_not_modify_the_records(graph: Graph) -> None:
    graph.edges.append(copy.deepcopy(graph.edge(PRODUCES)))
    graph.edge(CROSS_FEEDS)["attributes"]["substrate_id"] = "synthetic:substrate:9999"
    before = copy.deepcopy((graph.nodes, graph.edges, graph.metadata))

    graph.findings()

    assert (graph.nodes, graph.edges, graph.metadata) == before


def test_findings_are_json_serializable(graph: Graph) -> None:
    graph.edges.append(copy.deepcopy(graph.edge(PRODUCES)))
    graph.edge(DIET_PROVIDES)["attributes"]["proportion"] = math.nan
    graph.edge(HAS_CAPACITY)["relation_type"] = None

    findings = graph.findings()

    assert findings
    for finding in findings:
        encoded = json.dumps(finding.to_dict(), allow_nan=False)
        assert json.loads(encoded) == finding.to_dict()


def test_findings_are_deterministic(graph: Graph) -> None:
    graph.edges.append(copy.deepcopy(graph.edge(PRODUCES)))
    graph.edge(EXHIBITS)["attributes"]["timepoint"] = "day_99"

    assert graph.findings() == graph.findings()


def _relations_in_the_specification() -> dict[tuple[str, str, str], dict[str, str]]:
    """Transcribe la tabla "Relaciones permitidas" de DS-01 como fuente independiente."""
    row = re.compile(r"^\| `\('(\w+)', '(\w+)', '(\w+)'\)` \|[^|]*\| ([^|]*) \|")
    relations: dict[tuple[str, str, str], dict[str, str]] = {}
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        match = row.match(line)
        if match is None:
            continue
        source, relation, target, attributes = match.groups()
        required = dict(re.findall(r"`(\w+): (\w+)`", attributes))
        relations[(source, relation, target)] = required
    return relations


def test_relation_catalog_matches_the_specification() -> None:
    specified = _relations_in_the_specification()

    assert len(specified) == 11
    assert {
        edge_type: dict(spec.required_attributes) for edge_type, spec in ALLOWED_RELATIONS.items()
    } == specified


@pytest.mark.parametrize(
    "mutate",
    [
        lambda edge: replace(edge, relation_type="produces", source_type="taxon"),
        lambda edge: replace(edge, target_id="synthetic:metabolite:9999"),
        lambda edge: replace(edge, evidence_method=""),
        lambda edge: replace(edge, evidence_status="inferred"),
        lambda edge: replace(edge, attributes={}),
    ],
    ids=["tuple", "endpoint", "common-field", "evidence", "attributes"],
)
def test_detects_the_same_contract_defects_as_find_edge_errors(mutate: Any) -> None:
    """Coherencia con `find_edge_errors` (DS-03) en las reglas que ambas funciones cubren."""
    dataset = generate_synthetic_dataset()
    position = next(
        index for index, edge in enumerate(dataset.edges) if edge.edge_type == MEASURED_IN
    )
    edges = list(dataset.edges)
    edges[position] = mutate(edges[position])

    errors = find_edge_errors(dataset.nodes, edges)
    findings = find_edge_findings(dataset.nodes, edges)

    assert errors
    assert any(finding.severity is Severity.ERROR for finding in findings)
    assert find_edge_errors(dataset.nodes, dataset.edges) == []


# ---------------------------------------------------------------------------
# EDG-01: tuplas permitidas
# ---------------------------------------------------------------------------


def test_edg01_detects_a_tuple_outside_the_catalog(graph: Graph) -> None:
    edge = graph.edge(PRODUCES)
    edge["source_type"] = "taxon"
    edge["source_id"] = "synthetic:taxon:0001"

    finding = _only(graph.findings(), "EDG-01")

    assert finding.severity is Severity.ERROR
    assert finding.location["edge_type"] == ["taxon", "produces", "metabolite"]
    assert "inversa" not in finding.message


def test_edg01_rejects_implicit_inverse_relations(graph: Graph) -> None:
    edge = graph.edge(DIET_PROVIDES)
    edge["source_type"], edge["target_type"] = edge["target_type"], edge["source_type"]
    edge["source_id"], edge["target_id"] = edge["target_id"], edge["source_id"]

    finding = _only(graph.findings(), "EDG-01")

    assert finding.location["edge_type"] == ["substrate", "provides", "diet"]
    assert "inversa" in finding.message


def test_edg01_reports_unknown_node_type_without_a_redundant_edg02(graph: Graph) -> None:
    graph.edge(AVAILABLE_TO)["source_type"] = "microbe"

    finding = _only(graph.findings(), "EDG-01")

    assert finding.location["edge_type"] == ["microbe", "available_to", "taxon"]


def test_edg01_is_not_evaluated_when_a_type_is_not_text(graph: Graph) -> None:
    graph.edge(AVAILABLE_TO)["relation_type"] = None

    finding = _only(graph.findings(), "EDG-03")

    assert finding.location["field"] == "relation_type"
    assert "edge_type" not in finding.location


# ---------------------------------------------------------------------------
# EDG-02: extremos existentes en la misma instancia
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("endpoint", ["source", "target"])
def test_edg02_detects_a_missing_endpoint(graph: Graph, endpoint: str) -> None:
    edge = graph.edge(PRODUCES)
    edge[f"{endpoint}_id"] = "synthetic:missing:0001"

    finding = _only(graph.findings(), "EDG-02")

    assert finding.severity is Severity.ERROR
    assert finding.location["endpoint"] == endpoint
    assert finding.location["node_id"] == "synthetic:missing:0001"
    assert finding.observed == "no existe en la instancia"


def test_edg02_detects_an_endpoint_of_another_type(graph: Graph) -> None:
    graph.edge(INTERACTS_WITH)["target_id"] = "synthetic:function:0001"

    finding = _only(graph.findings(), "EDG-02")

    assert finding.location["node_type"] == "taxon"
    assert finding.location["endpoint"] == "target"


def test_edg02_detects_edges_between_instances() -> None:
    first = generate_synthetic_dataset()
    second = generate_synthetic_dataset(
        SyntheticNodeConfig(graph_id="synthetic:graph:0002", counts=NodeCountConfig(taxon=12))
    )
    nodes = [node.to_dict() for node in (*first.nodes, *second.nodes)]
    edges = [edge.to_dict() for edge in (*first.edges, *second.edges)]
    edge = next(
        edge
        for edge in edges
        if edge["graph_id"] == "synthetic:graph:0001" and edge["relation_type"] == "interacts_with"
    )
    edge["target_id"] = "synthetic:taxon:0012"

    finding = _only(find_edge_findings(nodes, edges), "EDG-02")

    assert finding.graph_id == "synthetic:graph:0001"
    assert "synthetic:graph:0002" in finding.observed


def test_edg02_is_evaluated_on_tuples_outside_the_catalog(graph: Graph) -> None:
    edge = graph.edge(PRODUCES)
    edge["source_type"] = "taxon"
    edge["source_id"] = "synthetic:taxon:9999"

    assert sorted(finding.rule_id for finding in graph.findings()) == ["EDG-01", "EDG-02"]


# ---------------------------------------------------------------------------
# EDG-03 y EDG-04: campos comunes y evidencia
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", COMMON_FIELDS)
@pytest.mark.parametrize("value", ["", None, 5, "<absent>"])
def test_edg03_detects_invalid_common_field(graph: Graph, field: str, value: Any) -> None:
    edge = graph.edge(HAS_CAPACITY)
    if value == "<absent>":
        del edge[field]
    else:
        edge[field] = value

    finding = _only(graph.findings(), "EDG-03")

    assert finding.severity is Severity.ERROR
    assert finding.location["field"] == field


def test_edg03_detects_unknown_evidence_status_without_edg04(graph: Graph) -> None:
    graph.edge(HAS_CAPACITY)["evidence_status"] = "confirmed"

    finding = _only(graph.findings(), "EDG-03")

    assert finding.location["field"] == "evidence_status"
    assert finding.observed == '"confirmed"'


@pytest.mark.parametrize("value", [None, 3, [], "edge"])
def test_edg03_detects_an_edge_that_is_not_an_object(graph: Graph, value: Any) -> None:
    graph.edges.insert(2, value)

    finding = _only(graph.findings(), "EDG-03")

    assert finding.graph_id is None
    assert finding.location == {"edge_record_index": 2}


@pytest.mark.parametrize("status", ["observed", "annotated", "inferred", "hypothetical"])
def test_edg04_detects_non_synthetic_evidence(graph: Graph, status: str) -> None:
    graph.edge(AVAILABLE_TO)["evidence_status"] = status

    finding = _only(graph.findings(), "EDG-04")

    assert finding.severity is Severity.ERROR
    assert finding.expected == '"synthetic"'
    assert finding.observed == json.dumps(status)


def _real(graph: Graph, edge_type: tuple[str, str, str], status: str, method: str) -> Graph:
    """Declara el dataset real y deja solo las aristas del tipo indicado, con esa evidencia."""
    graph.metadata["is_synthetic"] = False
    graph.edges = [
        edge
        for edge in graph.edges
        if (edge["source_type"], edge["relation_type"], edge["target_type"]) == edge_type
    ]
    assert graph.edges, f"el grafo de prueba no tiene aristas {edge_type}"
    for edge in graph.edges:
        edge["evidence_status"] = status
        edge["evidence_method"] = method
    return graph


def _edg04(graph: Graph) -> list[Finding]:
    return [finding for finding in graph.findings() if finding.rule_id == "EDG-04"]


@pytest.mark.parametrize(
    ("edge_type", "status", "method"),
    [
        (MEASURED_IN, "observed", "measurement"),
        (EXHIBITS, "observed", "measurement"),
        (DIET_PROVIDES, "annotated", "feed_table"),
        (HAS_CAPACITY, "annotated", "kegg"),
    ],
)
def test_edg04_admits_observed_and_annotated_evidence_in_real_data(
    graph: Graph, edge_type: tuple[str, str, str], status: str, method: str
) -> None:
    _real(graph, edge_type, status, method)

    assert _edg04(graph) == []


@pytest.mark.parametrize(
    ("edge_type", "status"),
    [(PRODUCES, "inferred"), (INTERACTS_WITH, "hypothetical"), (CROSS_FEEDS, "hypothetical")],
)
def test_edg04_warns_on_inferred_and_hypothetical_evidence_in_real_data(
    graph: Graph, edge_type: tuple[str, str, str], status: str
) -> None:
    _real(graph, edge_type, status, "model")

    findings = _edg04(graph)

    assert findings and all(f.severity is Severity.WARNING for f in findings)


@pytest.mark.parametrize(
    ("edge_type", "status", "method", "field"),
    [
        (MEASURED_IN, "synthetic", "generator", "evidence_status"),
        (MEASURED_IN, "observed", "co_occurrence", "evidence_method"),
        (PRODUCES, "observed", "measurement", "evidence_status"),
        (INTERACTS_WITH, "annotated", "kegg", "evidence_status"),
        (MEASURED_IN, "hypothetical", "model", "evidence_status"),
    ],
)
def test_edg04_rejects_evidence_outside_the_real_data_policy(
    graph: Graph, edge_type: tuple[str, str, str], status: str, method: str, field: str
) -> None:
    _real(graph, edge_type, status, method)

    findings = _edg04(graph)

    assert findings and all(f.severity is Severity.ERROR for f in findings)
    assert {f.location["field"] for f in findings} == {field}


def test_edg04_uses_the_origin_of_each_instance_when_instances_are_given(graph: Graph) -> None:
    graph.metadata["is_synthetic"] = False
    instances = [{"graph_id": graph.edges[0]["graph_id"], "is_synthetic": True}]

    findings = find_edge_findings(
        graph.nodes, graph.edges, metadata=graph.metadata, instances=instances
    )

    assert "EDG-04" not in {finding.rule_id for finding in findings}


# ---------------------------------------------------------------------------
# EDG-05: atributos obligatorios de la relación
# ---------------------------------------------------------------------------

REQUIRED_EDGE_ATTRIBUTES = [
    (edge_type, name)
    for edge_type, spec in ALLOWED_RELATIONS.items()
    for name in spec.required_attributes
]


@pytest.mark.parametrize(("edge_type", "attribute"), REQUIRED_EDGE_ATTRIBUTES)
def test_edg05_detects_missing_required_attribute(
    graph: Graph, edge_type: tuple[str, str, str], attribute: str
) -> None:
    del graph.edge(edge_type)["attributes"][attribute]

    finding = _only(graph.findings(), "EDG-05")

    assert finding.severity is Severity.ERROR
    assert finding.location["attribute"] == attribute
    assert finding.observed == "campo ausente"


@pytest.mark.parametrize(
    ("edge_type", "attribute", "value"),
    [
        (DIET_PROVIDES, "proportion", "0.5"),
        (DIET_PROVIDES, "proportion", True),
        (DIET_PROVIDES, "proportion", math.nan),
        (DIET_PROVIDES, "proportion", math.inf),
        (DIET_PROVIDES, "proportion", None),
        (DIET_PROVIDES, "unit", ""),
        (HAS_CAPACITY, "annotation_source", 7),
        (MEASURED_IN, "sample_matrix", None),
        (EXHIBITS, "timepoint", ["day_21"]),
        (INTERACTS_WITH, "interaction_type", ""),
        (CROSS_FEEDS, "substrate_id", None),
    ],
)
def test_edg05_detects_attribute_with_wrong_type(
    graph: Graph, edge_type: tuple[str, str, str], attribute: str, value: Any
) -> None:
    graph.edge(edge_type)["attributes"][attribute] = value

    finding = _only(graph.findings(), "EDG-05")

    assert finding.location["attribute"] == attribute


@pytest.mark.parametrize("edge_type", [AVAILABLE_TO, DIET_PROVIDES])
@pytest.mark.parametrize("value", [None, [], "attributes", "<absent>"])
def test_edg05_detects_attributes_that_are_not_an_object(
    graph: Graph, edge_type: tuple[str, str, str], value: Any
) -> None:
    edge = graph.edge(edge_type)
    if value == "<absent>":
        del edge["attributes"]
    else:
        edge["attributes"] = value

    finding = _only(graph.findings(), "EDG-05")

    assert finding.location["field"] == "attributes"


def test_edg05_admits_relations_without_required_attributes(graph: Graph) -> None:
    graph.edge(AVAILABLE_TO)["attributes"] = {}

    assert graph.findings() == []


# ---------------------------------------------------------------------------
# EDG-13: atributos fuera del contrato de la relación
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "edge_type", [PRODUCES, DIET_PROVIDES], ids=["without-attributes", "with-attributes"]
)
def test_edg13_warns_about_attributes_outside_the_relation_contract(
    graph: Graph, edge_type: tuple[str, str, str]
) -> None:
    graph.edge(edge_type)["attributes"]["note"] = "no está en el contrato"
    graph.edge(edge_type)["attributes"]["confidence"] = 0.9

    finding = _only(graph.findings(), "EDG-13")

    assert finding.severity is Severity.WARNING
    assert finding.location["attributes"] == ["confidence", "note"]


def test_edg13_is_not_evaluated_on_tuples_outside_the_catalog(graph: Graph) -> None:
    edge = graph.edge(PRODUCES)
    edge["source_type"] = "taxon"
    edge["source_id"] = "synthetic:taxon:0001"
    edge["attributes"]["note"] = "sin contrato que comparar"

    _only(graph.findings(), "EDG-01")


def test_edg13_does_not_repeat_a_missing_required_attribute(graph: Graph) -> None:
    attributes = graph.edge(DIET_PROVIDES)["attributes"]
    attributes["units"] = attributes.pop("unit")

    findings = graph.findings()

    assert sorted(finding.rule_id for finding in findings) == ["EDG-05", "EDG-13"]


# ---------------------------------------------------------------------------
# EDG-06 a EDG-08: coherencia con los nodos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "substrate_id",
    ["synthetic:substrate:9999", "synthetic:taxon:0001", "synthetic:function:0001"],
    ids=["missing", "taxon", "function"],
)
def test_edg06_detects_substrate_id_that_is_not_a_substrate(
    graph: Graph, substrate_id: str
) -> None:
    graph.edge(CROSS_FEEDS)["attributes"]["substrate_id"] = substrate_id

    finding = _only(graph.findings(), "EDG-06")

    assert finding.severity is Severity.ERROR
    assert finding.location["attribute"] == "substrate_id"


def test_edg06_detects_substrate_of_another_instance() -> None:
    first = generate_synthetic_dataset()
    second = generate_synthetic_dataset(
        SyntheticNodeConfig(graph_id="synthetic:graph:0002", counts=NodeCountConfig(substrate=6))
    )
    nodes = [*first.nodes, *second.nodes]
    edges = [edge.to_dict() for edge in (*first.edges, *second.edges)]
    edge = next(
        edge
        for edge in edges
        if edge["graph_id"] == "synthetic:graph:0001" and edge["relation_type"] == "cross_feeds"
    )
    edge["attributes"]["substrate_id"] = "synthetic:substrate:0006"

    finding = _only(find_edge_findings(nodes, edges), "EDG-06")

    assert finding.graph_id == "synthetic:graph:0001"


@pytest.mark.parametrize(
    ("edge_type", "attribute", "node_endpoint"),
    [
        (MEASURED_IN, "sample_matrix", "source"),
        (DIET_PROVIDES, "unit", "target"),
        (EXHIBITS, "timepoint", "target"),
    ],
)
def test_edg07_detects_edge_magnitude_different_from_its_node(
    graph: Graph, edge_type: tuple[str, str, str], attribute: str, node_endpoint: str
) -> None:
    edge = graph.edge(edge_type)
    node_type = edge[f"{node_endpoint}_type"]
    node_id = edge[f"{node_endpoint}_id"]
    node_value = graph.node(node_type, node_id)["attributes"][attribute]
    edge["attributes"][attribute] = "valor_distinto"

    finding = _only(graph.findings(), "EDG-07")

    assert finding.severity is Severity.ERROR
    assert finding.location["attribute"] == attribute
    assert finding.location["node_id"] == node_id
    assert finding.location["node_value"] == node_value
    assert finding.observed == '"valor_distinto"'


def test_edg07_is_not_evaluated_when_the_node_value_is_missing(graph: Graph) -> None:
    edge = graph.edge(MEASURED_IN)
    node = graph.node("metabolite", edge["source_id"])
    node["attributes"]["sample_matrix"] = None
    node["missing_mask"]["sample_matrix"] = True
    edge["attributes"]["sample_matrix"] = "plasma"

    assert graph.findings() == []


def test_edg07_is_not_evaluated_when_the_node_is_repeated(graph: Graph) -> None:
    edge = graph.edge(MEASURED_IN)
    duplicate = copy.deepcopy(graph.node("metabolite", edge["source_id"]))
    duplicate["attributes"]["sample_matrix"] = "plasma"
    graph.nodes.append(duplicate)
    # La arista coincide con la copia, pero no con el primer registro del nodo.
    edge["attributes"]["sample_matrix"] = "plasma"

    # NOD-03 informa el nodo repetido; la comparación sería ambigua.
    assert graph.findings() == []


def test_edg08_warns_about_annotation_source_different_from_the_function(graph: Graph) -> None:
    graph.edge(HAS_CAPACITY)["attributes"]["annotation_source"] = "other_annotation_db"

    finding = _only(graph.findings(), "EDG-08")

    assert finding.severity is Severity.WARNING
    assert finding.location["attribute"] == "annotation_source"
    assert finding.location["node_type"] == "function"


# ---------------------------------------------------------------------------
# EDG-09 y EDG-10: aristas repetidas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("copies", [1, 2])
def test_edg09_detects_identical_edges(graph: Graph, copies: int) -> None:
    original = graph.edge(PRODUCES)
    position = graph.edges.index(original)
    graph.edges.extend(copy.deepcopy(original) for _ in range(copies))

    finding = _only(graph.findings(), "EDG-09")

    assert finding.severity is Severity.ERROR
    assert finding.location["edge_record_indices"][0] == position
    assert len(finding.location["edge_record_indices"]) == copies + 1
    assert finding.observed == f"{copies + 1} repeticiones"


def test_edg10_warns_about_the_same_edge_with_different_evidence(graph: Graph) -> None:
    duplicate = copy.deepcopy(graph.edge(PRODUCES))
    duplicate["evidence_id"] = "SYNTHETIC_V1_BIS"
    graph.edges.append(duplicate)

    finding = _only(graph.findings(), "EDG-10")

    assert finding.severity is Severity.WARNING
    assert finding.location["evidence_ids"] == ["SYNTHETIC_V1", "SYNTHETIC_V1_BIS"]


def test_edg09_and_edg10_are_reported_together(graph: Graph) -> None:
    original = graph.edge(PRODUCES)
    identical = copy.deepcopy(original)
    different = copy.deepcopy(original)
    different["evidence_id"] = "SYNTHETIC_V1_BIS"
    graph.edges.extend([identical, different])

    assert [finding.rule_id for finding in graph.findings()] == ["EDG-09", "EDG-10"]


def test_edg09_ignores_equal_edges_of_different_instances() -> None:
    dataset = generate_scenario_dataset()
    basal = {
        (edge.edge_type, edge.source_id, edge.target_id)
        for edge in dataset.edges
        if edge.graph_id == dataset.instances[0].graph_id
    }
    intervened = {
        (edge.edge_type, edge.source_id, edge.target_id)
        for edge in dataset.edges
        if edge.graph_id == dataset.instances[1].graph_id
    }

    assert basal & intervened
    assert find_edge_findings(dataset.nodes, dataset.edges) == []


# ---------------------------------------------------------------------------
# EDG-11 y EDG-12: autolazos y vocabularios
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("edge_type", [INTERACTS_WITH, CROSS_FEEDS])
def test_edg11_warns_about_self_loops(graph: Graph, edge_type: tuple[str, str, str]) -> None:
    edge = graph.edge(edge_type)
    edge["target_id"] = edge["source_id"]

    finding = _only(graph.findings(), "EDG-11")

    assert finding.severity is Severity.WARNING
    assert finding.location["source_id"] == finding.location["target_id"]


def test_edg11_ignores_equal_ids_of_different_node_types(graph: Graph) -> None:
    """DS-01 solo exige `node_id` único dentro de `(graph_id, node_type)`."""
    edge = graph.edge(DIET_PROVIDES)
    shared = "synthetic:shared:0001"
    for node_type, endpoint in (("diet", "source"), ("substrate", "target")):
        old_id = edge[f"{endpoint}_id"]
        graph.node(node_type, old_id)["node_id"] = shared
        for other in graph.edges:
            for side in ("source", "target"):
                if other[f"{side}_type"] == node_type and other[f"{side}_id"] == old_id:
                    other[f"{side}_id"] = shared

    assert edge["source_id"] == edge["target_id"] == shared
    assert graph.findings() == []


def test_edg12_warns_about_values_outside_the_declared_vocabulary(graph: Graph) -> None:
    graph.edge(INTERACTS_WITH)["attributes"]["interaction_type"] = "mutualism"

    finding = _only(graph.findings(), "EDG-12")

    assert finding.severity is Severity.WARNING
    assert finding.observed == '"mutualism"'
    assert graph.findings(with_metadata=False) == []


def test_edg12_treats_an_undeclared_vocabulary_as_empty(graph: Graph) -> None:
    del graph.metadata["vocabularies"]["interaction_type"]
    interactions = sum(1 for edge in graph.edges if edge["relation_type"] == "interacts_with")

    findings = graph.findings()

    assert [finding.rule_id for finding in findings] == ["EDG-12"] * interactions
    assert findings[0].expected == "uno de [], declarado en metadata.json"
