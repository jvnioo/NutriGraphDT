"""Pruebas del análisis de nodos huérfanos y componentes desconectados (VG-04).

Cada regla CON-01 a CON-04 y la excepción X-01 de `docs/graph-integrity-rules.md` se prueba
con grafos mínimos escritos a mano, donde el resultado esperado se ve a simple vista. Los grafos
generados se contrastan con una implementación de referencia independiente.

Ninguna condición de conectividad es `ERROR`, y el análisis nunca modifica el grafo.
"""

from __future__ import annotations

import copy
import json
import random
import re
from pathlib import Path
from typing import Any

import pytest

from nutrigraphdt.data.synthetic import (
    NodeCountConfig,
    SyntheticEdgeConfig,
    SyntheticNodeConfig,
    generate_scenario_dataset,
    generate_synthetic_dataset,
)
from nutrigraphdt.graph.validation import Finding, Severity, find_connectivity_findings
from nutrigraphdt.graph.validation.connectivity import (
    DEFAULT_NON_MODULATING_CONTROL_LABELS,
    ISOLATED_NODE_EXCEPTIONS,
)

Record = dict[str, Any]

RULES = Path(__file__).resolve().parents[2] / "docs" / "graph-integrity-rules.md"
GRAPH = "synthetic:graph:0001"


def node(node_type: str, number: int, graph_id: str = GRAPH, **attributes: Any) -> Record:
    """Nodo mínimo: el análisis de conectividad solo usa su identidad y `control_label`."""
    return {
        "graph_id": graph_id,
        "node_type": node_type,
        "node_id": f"synthetic:{node_type}:{number:04d}",
        "source_id": "SYNTHETIC_V1",
        "attributes": attributes,
        "missing_mask": {},
    }


def edge(source: Record, relation: str, target: Record, graph_id: str = GRAPH) -> Record:
    return {
        "graph_id": graph_id,
        "source_type": source["node_type"],
        "source_id": source["node_id"],
        "relation_type": relation,
        "target_type": target["node_type"],
        "target_id": target["node_id"],
        "evidence_id": "SYNTHETIC_V1",
        "evidence_status": "synthetic",
        "evidence_method": "synthetic_generator",
        "attributes": {},
    }


def _rules(findings: list[Finding]) -> list[str]:
    return [finding.rule_id for finding in findings]


def _only(findings: list[Finding], rule_id: str) -> Finding:
    assert _rules(findings) == [rule_id], findings
    return findings[0]


@pytest.fixture
def chain() -> tuple[list[Record], list[Record]]:
    """diet -> substrate -> taxon -> function -> metabolite, conectados en una cadena."""
    diet, substrate, taxon, function, metabolite = (
        node("diet", 1),
        node("substrate", 1),
        node("taxon", 1),
        node("function", 1),
        node("metabolite", 1),
    )
    edges = [
        edge(diet, "provides", substrate),
        edge(substrate, "available_to", taxon),
        edge(taxon, "has_capacity", function),
        edge(function, "produces", metabolite),
    ]
    return [diet, substrate, taxon, function, metabolite], edges


# ---------------------------------------------------------------------------
# Implementación de referencia para los grafos generados
# ---------------------------------------------------------------------------


def _reference(dataset: Any) -> dict[str, tuple[set[tuple[str, str]], list[int]]]:
    """Nodos aislados y tamaños de componentes (>= 2) por propagación de etiquetas."""
    result: dict[str, tuple[set[tuple[str, str]], list[int]]] = {}
    for instance in dataset.instances:
        keys = {
            (item.node_type, item.node_id)
            for item in dataset.nodes
            if item.graph_id == instance.graph_id
        }
        pairs = [
            ((item.source_type, item.source_id), (item.target_type, item.target_id))
            for item in dataset.edges
            if item.graph_id == instance.graph_id
        ]
        label = {key: key for key in keys}
        changed = True
        while changed:
            changed = False
            for source, target in pairs:
                smallest = min(label[source], label[target])
                for key in (source, target):
                    if label[key] != smallest:
                        label[key] = smallest
                        changed = True
        sizes: dict[tuple[str, str], int] = {}
        for value in label.values():
            sizes[value] = sizes.get(value, 0) + 1
        linked = {key for pair in pairs if pair[0] != pair[1] for key in pair}
        result[instance.graph_id] = (keys - linked, sorted(s for s in sizes.values() if s >= 2))
    return result


# ---------------------------------------------------------------------------
# Grafos generados
# ---------------------------------------------------------------------------


def test_default_and_scenario_graphs_are_connected() -> None:
    for dataset in (generate_synthetic_dataset(), generate_scenario_dataset()):
        assert (
            find_connectivity_findings(dataset.nodes, dataset.edges, metadata=dataset.metadata)
            == []
        )


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
def test_generated_graphs_match_the_reference_implementation(
    seed: int, counts: NodeCountConfig
) -> None:
    dataset = generate_synthetic_dataset(
        SyntheticNodeConfig(random_seed=seed, counts=counts),
        SyntheticEdgeConfig(random_seed=seed),
    )
    (isolated, component_sizes) = _reference(dataset)[GRAPH]

    findings = find_connectivity_findings(dataset.nodes, dataset.edges, metadata=dataset.metadata)

    reported = {
        (finding.location["node_type"], node_id)
        for finding in findings
        if finding.rule_id in {"CON-01", "CON-02"}
        for node_id in finding.location["node_ids"]
    }
    assert reported == isolated
    components = [finding for finding in findings if finding.rule_id == "CON-04"]
    if len(component_sizes) > 1:
        assert len(components) == 1
        assert sorted(c["size"] for c in components[0].location["components"]) == component_sizes
    else:
        assert components == []
    assert all(finding.severity is not Severity.ERROR for finding in findings)


def test_beyond_catalog_profile_isolates_the_control_additive_by_design() -> None:
    dataset = generate_synthetic_dataset(
        SyntheticNodeConfig(
            counts=NodeCountConfig(
                diet=3,
                additive=6,
                substrate=10,
                taxon=14,
                function=11,
                metabolite=8,
                host=2,
                phenotype=5,
            )
        )
    )

    finding = _only(
        find_connectivity_findings(dataset.nodes, dataset.edges, metadata=dataset.metadata),
        "CON-02",
    )

    assert finding.severity is Severity.INFO
    assert finding.location == {
        "node_type": "additive",
        "node_ids": ["synthetic:additive:0005"],
        "exception": "X-01",
    }


# ---------------------------------------------------------------------------
# Comportamiento general
# ---------------------------------------------------------------------------


def test_exceptions_match_the_specification() -> None:
    text = RULES.read_text(encoding="utf-8")
    section = text.split("### Excepciones admitidas para nodos aislados", 1)[1]
    section = section.split("###", 1)[0]
    specified = set(re.findall(r"^\| (X-\d\d) \|", section, flags=re.MULTILINE))

    assert set(ISOLATED_NODE_EXCEPTIONS) == specified == {"X-01"}
    assert DEFAULT_NON_MODULATING_CONTROL_LABELS == ("control_basal",)


def test_does_not_modify_the_records(chain: tuple[list[Record], list[Record]]) -> None:
    nodes, edges = chain
    nodes.append(node("taxon", 2))
    before = copy.deepcopy((nodes, edges))

    find_connectivity_findings(nodes, edges)

    assert (nodes, edges) == before


def test_findings_do_not_depend_on_the_order_of_the_records() -> None:
    dataset = generate_synthetic_dataset(
        SyntheticNodeConfig(counts=NodeCountConfig(1, 1, 1, 1, 1, 1, 1, 1))
    )
    nodes = list(dataset.nodes)
    edges = list(dataset.edges)
    expected = find_connectivity_findings(nodes, edges)
    rng = random.Random(0)

    for _ in range(5):
        rng.shuffle(nodes)
        rng.shuffle(edges)
        assert find_connectivity_findings(nodes, edges) == expected
    assert _rules(expected) == ["CON-04"]


def test_findings_are_json_serializable(chain: tuple[list[Record], list[Record]]) -> None:
    nodes, edges = chain
    host, phenotype = node("host", 1), node("phenotype", 1)
    nodes += [host, phenotype, node("taxon", 2)]
    edges.append(edge(host, "exhibits", phenotype))

    findings = find_connectivity_findings(nodes, edges)

    assert _rules(findings) == ["CON-01", "CON-04"]
    for finding in findings:
        assert json.loads(json.dumps(finding.to_dict(), allow_nan=False)) == finding.to_dict()


def test_edges_are_treated_as_undirected() -> None:
    taxon, other, function = node("taxon", 1), node("taxon", 2), node("function", 1)
    edges = [edge(taxon, "has_capacity", function), edge(other, "has_capacity", function)]

    assert find_connectivity_findings([taxon, other, function], edges) == []


def test_repeated_node_ids_count_once(chain: tuple[list[Record], list[Record]]) -> None:
    nodes, edges = chain
    nodes.append(copy.deepcopy(nodes[0]))

    assert find_connectivity_findings(nodes, edges) == []


def test_instances_are_analyzed_separately(chain: tuple[list[Record], list[Record]]) -> None:
    nodes, edges = chain
    other = "synthetic:graph:0002"
    lone = node("taxon", 1, graph_id=other)

    findings = find_connectivity_findings([*nodes, lone], edges)

    # La cadena de la primera instancia no aporta hallazgos; la segunda solo tiene un taxón.
    assert _rules(findings) == ["CON-01", "CON-03"]
    assert {finding.graph_id for finding in findings} == {other}


# ---------------------------------------------------------------------------
# CON-01 y CON-02: nodos aislados
# ---------------------------------------------------------------------------


def test_con01_warns_about_an_isolated_node(chain: tuple[list[Record], list[Record]]) -> None:
    nodes, edges = chain
    nodes.append(node("taxon", 2))

    finding = _only(find_connectivity_findings(nodes, edges), "CON-01")

    assert finding.severity is Severity.WARNING
    assert finding.location == {"node_type": "taxon", "node_ids": ["synthetic:taxon:0002"]}
    assert finding.observed == "1 nodo(s) aislado(s)"


def test_con01_counts_isolated_nodes_by_type(chain: tuple[list[Record], list[Record]]) -> None:
    nodes, edges = chain
    nodes += [node("metabolite", 2), node("taxon", 3), node("taxon", 2)]

    findings = find_connectivity_findings(nodes, edges)

    assert _rules(findings) == ["CON-01", "CON-01"]
    assert [finding.location for finding in findings] == [
        {"node_type": "taxon", "node_ids": ["synthetic:taxon:0002", "synthetic:taxon:0003"]},
        {"node_type": "metabolite", "node_ids": ["synthetic:metabolite:0002"]},
    ]
    assert findings[0].observed == "2 nodo(s) aislado(s)"


def test_con01_a_self_loop_does_not_connect_a_node(
    chain: tuple[list[Record], list[Record]],
) -> None:
    nodes, edges = chain
    lonely = node("taxon", 2)
    nodes.append(lonely)
    edges.append(edge(lonely, "interacts_with", lonely))

    finding = _only(find_connectivity_findings(nodes, edges), "CON-01")

    assert finding.location["node_ids"] == ["synthetic:taxon:0002"]


@pytest.mark.parametrize(
    "target",
    [
        {"node_type": "function", "node_id": "synthetic:function:9999"},
        {"node_type": "function", "node_id": "synthetic:function:0001", "graph": "other"},
    ],
    ids=["missing-endpoint", "other-instance"],
)
def test_con01_edges_that_do_not_resolve_connect_nothing(target: dict[str, str]) -> None:
    taxon = node("taxon", 1)
    function = node("function", 1, graph_id="synthetic:graph:0002")
    dangling = edge(taxon, "has_capacity", {"node_type": "function", "node_id": target["node_id"]})

    findings = find_connectivity_findings([taxon, function], [dangling])

    assert _rules(findings) == ["CON-01", "CON-03", "CON-01", "CON-03"]
    assert {finding.graph_id for finding in findings} == {GRAPH, "synthetic:graph:0002"}


def test_con02_admits_an_isolated_control_additive(
    chain: tuple[list[Record], list[Record]],
) -> None:
    nodes, edges = chain
    nodes.append(node("additive", 1, control_label="control_basal"))
    taxon = nodes[2]
    active = node("additive", 2, control_label="supplemented")
    nodes.append(active)
    edges.append(edge(active, "modulates", taxon))

    finding = _only(find_connectivity_findings(nodes, edges), "CON-02")

    assert finding.severity is Severity.INFO
    assert finding.location == {
        "node_type": "additive",
        "node_ids": ["synthetic:additive:0001"],
        "exception": "X-01",
    }


@pytest.mark.parametrize(
    ("node_type", "control_label"),
    [
        ("additive", "supplemented"),
        ("additive", ["control_basal"]),
        ("additive", None),
        ("taxon", "control_basal"),
    ],
)
def test_con02_does_not_apply_outside_x01(
    chain: tuple[list[Record], list[Record]], node_type: str, control_label: Any
) -> None:
    nodes, edges = chain
    taxon = nodes[2]
    active = node("additive", 9, control_label="supplemented")
    nodes += [active, node(node_type, 2, control_label=control_label)]
    edges.append(edge(active, "modulates", taxon))

    finding = _only(find_connectivity_findings(nodes, edges), "CON-01")

    assert finding.location["node_type"] == node_type


def test_con02_reads_the_labels_declared_in_the_metadata(
    chain: tuple[list[Record], list[Record]],
) -> None:
    nodes, edges = chain
    taxon = nodes[2]
    active = node("additive", 9, control_label="supplemented")
    nodes += [
        active,
        node("additive", 1, control_label="placebo"),
        node("additive", 2, control_label="control_basal"),
    ]
    edges.append(edge(active, "modulates", taxon))
    metadata = {"configuration": {"edges": {"non_modulating_control_labels": ["placebo"]}}}

    findings = find_connectivity_findings(nodes, edges, metadata=metadata)

    assert _rules(findings) == ["CON-01", "CON-02"]
    assert findings[0].location["node_ids"] == ["synthetic:additive:0002"]
    assert findings[1].location["node_ids"] == ["synthetic:additive:0001"]


def test_con02_uses_the_default_labels_without_valid_metadata(
    chain: tuple[list[Record], list[Record]],
) -> None:
    nodes, edges = chain
    taxon = nodes[2]
    active = node("additive", 9, control_label="supplemented")
    nodes += [active, node("additive", 1, control_label="control_basal")]
    edges.append(edge(active, "modulates", taxon))

    for metadata in (None, {}, {"configuration": {"edges": {"non_modulating_control_labels": 3}}}):
        assert _rules(find_connectivity_findings(nodes, edges, metadata=metadata)) == ["CON-02"]


def test_connected_control_additive_produces_no_finding(
    chain: tuple[list[Record], list[Record]],
) -> None:
    nodes, edges = chain
    control = node("additive", 1, control_label="control_basal")
    nodes.append(control)
    edges.append(edge(control, "modulates", nodes[2]))

    assert find_connectivity_findings(nodes, edges) == []


# ---------------------------------------------------------------------------
# CON-03: tipos sin aristas
# ---------------------------------------------------------------------------


def test_con03_warns_about_a_node_type_without_edges(
    chain: tuple[list[Record], list[Record]],
) -> None:
    nodes, edges = chain
    nodes += [node("phenotype", 1), node("phenotype", 2)]

    findings = find_connectivity_findings(nodes, edges)

    assert _rules(findings) == ["CON-01", "CON-03"]
    assert findings[1].severity is Severity.WARNING
    assert findings[1].location == {"node_type": "phenotype", "node_count": 2}


def test_con03_has_no_exception_for_control_additives(
    chain: tuple[list[Record], list[Record]],
) -> None:
    nodes, edges = chain
    nodes.append(node("additive", 1, control_label="control_basal"))

    assert _rules(find_connectivity_findings(nodes, edges)) == ["CON-02", "CON-03"]


def test_con03_counts_a_self_loop_as_a_reference(
    chain: tuple[list[Record], list[Record]],
) -> None:
    nodes, edges = chain
    host = node("host", 1)
    nodes.append(host)
    edges.append(edge(host, "interacts_with", host))

    assert _rules(find_connectivity_findings(nodes, edges)) == ["CON-01"]


# ---------------------------------------------------------------------------
# CON-04: componentes desconectados
# ---------------------------------------------------------------------------


def test_con04_describes_every_component(chain: tuple[list[Record], list[Record]]) -> None:
    nodes, edges = chain
    host, phenotype, other = node("host", 1), node("phenotype", 1), node("phenotype", 2)
    nodes += [host, phenotype, other]
    edges += [edge(host, "exhibits", phenotype), edge(host, "exhibits", other)]

    finding = _only(find_connectivity_findings(nodes, edges), "CON-04")

    assert finding.severity is Severity.WARNING
    assert finding.location["component_count"] == 2
    first, second = finding.location["components"]
    assert first["size"] == 5
    assert first["node_types"] == {
        "diet": 1,
        "substrate": 1,
        "taxon": 1,
        "function": 1,
        "metabolite": 1,
    }
    assert second == {
        "size": 3,
        "node_types": {"host": 1, "phenotype": 2},
        "nodes": [
            ["host", "synthetic:host:0001"],
            ["phenotype", "synthetic:phenotype:0001"],
            ["phenotype", "synthetic:phenotype:0002"],
        ],
    }


def test_con04_ignores_isolated_nodes(chain: tuple[list[Record], list[Record]]) -> None:
    nodes, edges = chain
    nodes.append(node("taxon", 2))

    assert _rules(find_connectivity_findings(nodes, edges)) == ["CON-01"]
