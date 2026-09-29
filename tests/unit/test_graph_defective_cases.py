"""Suite transversal de grafos defectuosos (VG-06).

Parte de un grafo mínimo, válido y escrito a mano, y aplica un catálogo de defectos. Cada caso
introduce **un** defecto dirigido a una regla identificable de `docs/graph-integrity-rules.md`,
ejecuta **todos** los validadores y exige el conjunto exacto de hallazgos. Así se comprueba que
el defecto se detecta con su severidad y que no provoca hallazgos espurios en otros
validadores. Cuando un defecto implica otros por construcción (por ejemplo, un nodo de tipo
desconocido deja aristas sin extremo), el caso los declara y explica.

Las pruebas unitarias de cada validador cubren sus variantes. Esta suite cubre lo transversal:
cobertura de todas las reglas, interacción entre validadores y regresiones.

Todo el contenido es sintético y no representa observaciones reales.
"""

from __future__ import annotations

import copy
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pytest

from nutrigraphdt import __version__
from nutrigraphdt.data.synthetic import (
    Edge,
    InstanceRecord,
    Node,
    NodeCountConfig,
    SyntheticDataset,
    SyntheticNodeConfig,
    generate_scenario_dataset,
    generate_synthetic_dataset,
)
from nutrigraphdt.data.synthetic.export import build_metadata
from nutrigraphdt.graph.validation import (
    Finding,
    Severity,
    find_connectivity_findings,
    find_edge_findings,
    find_node_findings,
)

Record = dict[str, Any]
EdgeType = tuple[str, str, str]

RULES = Path(__file__).resolve().parents[2] / "docs" / "graph-integrity-rules.md"
GRAPH_ID = "synthetic:defects:0001"

VG07_RULES = (
    frozenset({"INS-05", "INS-06"})
    | {f"OUT-0{n}" for n in range(1, 5)}
    | {f"MET-0{n}" for n in range(1, 4)}
)
"""Reglas asignadas a VG-07 (pares de instancias, salidas y metadatos); fuera de esta suite."""


# ---------------------------------------------------------------------------
# Grafo mínimo válido
# ---------------------------------------------------------------------------


def _node(node_type: str, number: int, **attributes: Any) -> Record:
    return {
        "graph_id": GRAPH_ID,
        "node_id": f"synthetic:{node_type}:{number:04d}",
        "node_type": node_type,
        "source_id": "SYNTHETIC_V1",
        "attributes": attributes,
        "missing_mask": {},
    }


def _edge(source: Record, relation: str, target: Record, **attributes: Any) -> Record:
    return {
        "graph_id": GRAPH_ID,
        "source_type": source["node_type"],
        "source_id": source["node_id"],
        "relation_type": relation,
        "target_type": target["node_type"],
        "target_id": target["node_id"],
        "evidence_id": "SYNTHETIC_V1",
        "evidence_status": "synthetic",
        "evidence_method": "synthetic_generator",
        "attributes": attributes,
    }


def minimal_records() -> tuple[Record, list[Record], list[Record]]:
    """Instancia, 10 nodos (los ocho tipos) y 12 aristas (las once relaciones), conexos."""
    diet = _node(
        "diet",
        1,
        name="synthetic_basal_diet",
        ingredients=["synthetic_maize", "synthetic_soybean_meal"],
        composition=[{"component_id": "crude_protein", "value": 215.0, "unit": "g/kg"}],
        source_version="synthetic-v1",
    )
    additive = _node(
        "additive",
        1,
        category="probiotic",
        substance="synthetic_strain_a",
        dose=0.5,
        dose_unit="g/kg",
        control_label="supplemented",
    )
    substrate = _node(
        "substrate",
        1,
        chemical_id="synthetic:chemical:0001",
        name="synthetic_starch",
        quantity=300.0,
        unit="g/kg",
    )
    taxon_1, taxon_2 = (
        _node(
            "taxon",
            number,
            taxonomy_id=f"synthetic:taxonomy:{number:04d}",
            taxonomy_level="genus",
            abundance=0.25,
            abundance_unit="relative_abundance",
            quantification_method="synthetic_16s",
        )
        for number in (1, 2)
    )
    function_1, function_2 = (
        _node(
            "function",
            number,
            function_id=f"synthetic:function-id:{number:04d}",
            function_type="enzyme",
            annotation_source="synthetic_annotation",
            annotation_value=1.0,
            annotation_value_type="presence",
            unit="presence",
        )
        for number in (1, 2)
    )
    metabolite = _node(
        "metabolite",
        1,
        chemical_id="synthetic:chemical:0101",
        name="synthetic_butyrate",
        sample_matrix="cecal_content",
        concentration=12.5,
        unit="umol/g",
    )
    host = _node(
        "host",
        1,
        species="chicken",
        gut_segment="cecum",
        cohort_id="synthetic:cohort:0001",
        covariates={"body_weight_g": 1500.0, "sex": "female"},
    )
    phenotype = _node(
        "phenotype", 1, trait="synthetic_weight_gain", timepoint="day_21", value=0.5, unit="g"
    )
    nodes = [
        diet,
        additive,
        substrate,
        taxon_1,
        taxon_2,
        function_1,
        function_2,
        metabolite,
        host,
        phenotype,
    ]
    edges = [
        _edge(diet, "provides", substrate, proportion=300.0, unit="g/kg"),
        _edge(substrate, "available_to", taxon_1),
        _edge(taxon_1, "has_capacity", function_1, annotation_source="synthetic_annotation"),
        _edge(taxon_2, "has_capacity", function_2, annotation_source="synthetic_annotation"),
        _edge(function_1, "produces", metabolite),
        _edge(metabolite, "measured_in", host, sample_matrix="cecal_content"),
        _edge(additive, "modulates", taxon_1),
        _edge(additive, "modulates", function_1),
        _edge(metabolite, "associated_with", phenotype),
        _edge(host, "exhibits", phenotype, timepoint="day_21"),
        _edge(taxon_1, "interacts_with", taxon_2, interaction_type="competition"),
        _edge(function_1, "cross_feeds", function_2, substrate_id=substrate["node_id"]),
    ]
    instance = InstanceRecord(
        graph_id=GRAPH_ID,
        species="chicken",
        gut_segment="cecum",
        study_id="SYNTHETIC_V1",
        sample_id="synthetic:sample:0001",
        scenario_id="basal",
        diet_treatment="synthetic_basal_diet",
        generator_version=__version__,
    ).to_dict()
    return instance, nodes, edges


def minimal_dataset() -> SyntheticDataset:
    instance, nodes, edges = minimal_records()
    node_objects = [Node.from_dict(node) for node in nodes]
    edge_objects = [Edge.from_dict(edge) for edge in edges]
    instances = [InstanceRecord.from_dict(instance)]
    metadata = build_metadata(
        dataset_id="synthetic-defects-v1",
        random_seed=0,
        configuration={"edges": {"non_modulating_control_labels": ["control_basal"]}},
        instances=instances,
        nodes=node_objects,
        edges=edge_objects,
        outputs=[],
        interaction_types=["competition"],
    )
    return SyntheticDataset(
        metadata=metadata, instances=instances, nodes=node_objects, edges=edge_objects
    )


# ---------------------------------------------------------------------------
# Grafo mutable y ejecución de todos los validadores
# ---------------------------------------------------------------------------


@dataclass
class Graph:
    """Registros mutables del grafo mínimo y, en los casos de tensores, su `HeteroData`."""

    instances: list[Record]
    nodes: list[Record]
    edges: list[Record]
    metadata: Record
    data: Any = None

    def node(self, node_type: str, number: int = 1) -> Record:
        node_id = f"synthetic:{node_type}:{number:04d}"
        return next(
            node
            for node in self.nodes
            if node["node_type"] == node_type and node["node_id"] == node_id
        )

    def edge(self, edge_type: EdgeType, position: int = 0) -> Record:
        matches = [
            edge
            for edge in self.edges
            if (edge["source_type"], edge["relation_type"], edge["target_type"]) == edge_type
        ]
        return matches[position]

    def findings(self) -> list[Finding]:
        """Hallazgos de todos los validadores de registros y, si hay `HeteroData`, de tensores."""
        findings = [
            *find_node_findings(self.instances, self.nodes, metadata=self.metadata),
            *find_edge_findings(self.nodes, self.edges, metadata=self.metadata),
            *find_connectivity_findings(self.nodes, self.edges, metadata=self.metadata),
        ]
        if self.data is not None:
            from nutrigraphdt.graph.validation.tensors import find_tensor_findings

            findings += find_tensor_findings(
                self.data, instance=self.instances[0], edges=self.edges, metadata=self.metadata
            )
        return findings


def record_graph() -> Graph:
    dataset = minimal_dataset()
    return Graph(
        instances=[instance.to_dict() for instance in dataset.instances],
        nodes=copy.deepcopy([node.to_dict() for node in dataset.nodes]),
        edges=copy.deepcopy([edge.to_dict() for edge in dataset.edges]),
        metadata=copy.deepcopy(dataset.metadata),
    )


def tensor_graph(builder: Callable[..., tuple[Any, Record]]) -> Graph:
    dataset = minimal_dataset()
    graph = record_graph()
    graph.data, graph.metadata = builder(dataset, GRAPH_ID)
    return graph


# ---------------------------------------------------------------------------
# Catálogo de defectos
# ---------------------------------------------------------------------------

PROVIDES: EdgeType = ("diet", "provides", "substrate")
AVAILABLE_TO: EdgeType = ("substrate", "available_to", "taxon")
HAS_CAPACITY: EdgeType = ("taxon", "has_capacity", "function")
PRODUCES: EdgeType = ("function", "produces", "metabolite")
MEASURED_IN: EdgeType = ("metabolite", "measured_in", "host")
MODULATES_TAXON: EdgeType = ("additive", "modulates", "taxon")
MODULATES_FUNCTION: EdgeType = ("additive", "modulates", "function")
INTERACTS_WITH: EdgeType = ("taxon", "interacts_with", "taxon")
CROSS_FEEDS: EdgeType = ("function", "cross_feeds", "function")


@dataclass(frozen=True)
class Case:
    """Un defecto dirigido a una regla, con todos los hallazgos que debe producir."""

    case_id: str
    rule_id: str
    severity: Severity
    mutate: Callable[[Graph], None]
    expected: tuple[str, ...]
    layer: Literal["records", "tensors"] = "records"
    note: str = ""


def _set(target: Record, key: str, value: Any) -> None:
    target[key] = value


def _drop(target: Record, key: str) -> None:
    del target[key]


def _append_copy(items: list[Record], item: Record, **changes: Any) -> None:
    duplicate = copy.deepcopy(item)
    duplicate.update(changes)
    items.append(duplicate)


def _mark_missing(node: Record, attribute: str, *, masked: bool) -> None:
    node["attributes"][attribute] = None
    if masked:
        node["missing_mask"][attribute] = True


def _remove_node(graph: Graph, node: Record) -> None:
    graph.nodes.remove(node)


def _remove_edges(graph: Graph, *edge_types: EdgeType) -> None:
    for edge_type in edge_types:
        graph.edges.remove(graph.edge(edge_type))


def _store_edge(graph: Graph, edge_type: EdgeType) -> None:
    import torch

    store = graph.data[edge_type]
    store.edge_index = torch.tensor([[0], [0]])
    store.edge_attr = torch.zeros((1, 0))
    store.evidence_id = ["SYNTHETIC_V1"]
    store.evidence_status = ["synthetic"]
    store.evidence_method = ["synthetic_generator"]
    store.raw_attributes = [{}]


def _swap_taxon_rows(graph: Graph) -> None:
    store = graph.data["taxon"]
    store.node_id = list(reversed(store.node_id))


def _tensor(graph: Graph, owner: Any, name: str, transform: Callable[[Any], Any]) -> None:
    store = graph.data[owner]
    store[name] = transform(store[name])


def _set_tensor_value(graph: Graph, owner: Any, name: str, index: Any, value: Any) -> None:
    graph.data[owner][name][index] = value


ERROR, WARNING, INFO = Severity.ERROR, Severity.WARNING, Severity.INFO

CASES: tuple[Case, ...] = (
    # --- Instancias (INS) ---
    Case(
        "repeated-graph-id",
        "INS-01",
        ERROR,
        lambda g: _append_copy(g.instances, g.instances[0]),
        ("INS-01",),
    ),
    Case(
        "missing-sample-id",
        "INS-01",
        ERROR,
        lambda g: _drop(g.instances[0], "sample_id"),
        ("INS-01",),
    ),
    Case(
        "incompatible-schema-version",
        "INS-02",
        ERROR,
        lambda g: _set(g.instances[0], "schema_version", "2.0.0"),
        ("INS-02",),
    ),
    Case(
        "unknown-scenario",
        "INS-03",
        ERROR,
        lambda g: _set(g.instances[0], "scenario_id", "treatment"),
        ("INS-03",),
    ),
    Case(
        "host-of-another-species",
        "INS-04",
        ERROR,
        lambda g: _set(g.node("host")["attributes"], "species", "pig"),
        ("INS-04",),
    ),
    # --- Nodos (NOD) ---
    Case(
        "unknown-node-type",
        "NOD-01",
        ERROR,
        lambda g: _set(g.node("taxon", 2), "node_type", "microbe"),
        ("NOD-01", "EDG-02", "EDG-02", "CON-01", "CON-03"),
        note=(
            "Las dos aristas de taxon 2 quedan sin extremo (EDG-02), y el nodo 'microbe' queda "
            "aislado en un tipo que ninguna arista referencia (CON-01, CON-03)."
        ),
    ),
    Case(
        "empty-source-id",
        "NOD-02",
        ERROR,
        lambda g: _set(g.node("taxon"), "source_id", ""),
        ("NOD-02",),
    ),
    Case(
        "repeated-node-id",
        "NOD-03",
        ERROR,
        lambda g: _append_copy(g.nodes, g.node("taxon", 2)),
        ("NOD-03",),
    ),
    Case(
        "real-looking-domain-id",
        "NOD-04",
        ERROR,
        lambda g: _set(g.node("taxon")["attributes"], "taxonomy_id", "NCBI:txid816"),
        ("NOD-04",),
    ),
    Case(
        "missing-required-attribute",
        "NOD-05",
        ERROR,
        lambda g: _drop(g.node("metabolite")["attributes"], "unit"),
        ("NOD-05",),
    ),
    Case(
        "composition-item-without-unit",
        "NOD-06",
        ERROR,
        lambda g: _drop(g.node("diet")["attributes"]["composition"][0], "unit"),
        ("NOD-06",),
    ),
    Case(
        "null-without-mask",
        "NOD-07",
        ERROR,
        lambda g: _mark_missing(g.node("taxon"), "abundance", masked=False),
        ("NOD-07",),
    ),
    Case(
        "masked-missing-value",
        "NOD-08",
        WARNING,
        lambda g: _mark_missing(g.node("taxon", 2), "abundance", masked=True),
        ("NOD-08",),
    ),
    Case(
        "attribute-outside-contract",
        "NOD-09",
        WARNING,
        lambda g: _set(g.node("substrate")["attributes"], "color", "white"),
        ("NOD-09",),
    ),
    Case(
        "negative-quantity",
        "NOD-10",
        WARNING,
        lambda g: _set(g.node("substrate")["attributes"], "quantity", -1.0),
        ("NOD-10",),
    ),
    Case(
        "undeclared-function-type",
        "NOD-11",
        WARNING,
        lambda g: _set(g.node("function")["attributes"], "function_type", "operon"),
        ("NOD-11",),
    ),
    Case(
        "missing-node-type",
        "NOD-12",
        ERROR,
        lambda g: _remove_node(g, g.node("phenotype")),
        ("NOD-12", "EDG-02", "EDG-02"),
        note="Las dos aristas que llegaban al fenotipo quedan sin extremo (EDG-02).",
    ),
    # --- Aristas (EDG) ---
    Case(
        "taxon-to-metabolite",
        "EDG-01",
        ERROR,
        lambda g: g.edges.append(
            _edge(g.node("taxon"), "produces", g.node("metabolite")),
        ),
        ("EDG-01",),
    ),
    Case(
        "missing-endpoint",
        "EDG-02",
        ERROR,
        lambda g: _set(g.edge(MODULATES_FUNCTION), "target_id", "synthetic:function:9999"),
        ("EDG-02",),
    ),
    Case(
        "missing-endpoint-on-a-bridge",
        "EDG-02",
        ERROR,
        lambda g: _set(g.edge(PRODUCES), "target_id", "synthetic:metabolite:9999"),
        ("EDG-02", "CON-04"),
        note=(
            "produces es el único puente hacia metabolito, huésped y fenotipo. Una arista que no "
            "resuelve no conecta nada, así que el grafo se parte en dos componentes (CON-04)."
        ),
    ),
    Case(
        "empty-evidence-method",
        "EDG-03",
        ERROR,
        lambda g: _set(g.edge(AVAILABLE_TO), "evidence_method", ""),
        ("EDG-03",),
    ),
    Case(
        "non-synthetic-evidence",
        "EDG-04",
        ERROR,
        lambda g: _set(g.edge(AVAILABLE_TO), "evidence_status", "observed"),
        ("EDG-04",),
    ),
    Case(
        "missing-edge-attribute",
        "EDG-05",
        ERROR,
        lambda g: _drop(g.edge(PROVIDES)["attributes"], "unit"),
        ("EDG-05",),
    ),
    Case(
        "cross-feeding-without-substrate",
        "EDG-06",
        ERROR,
        lambda g: _set(g.edge(CROSS_FEEDS)["attributes"], "substrate_id", "synthetic:x:0001"),
        ("EDG-06",),
    ),
    Case(
        "mixed-sample-matrix",
        "EDG-07",
        ERROR,
        lambda g: _set(g.edge(MEASURED_IN)["attributes"], "sample_matrix", "plasma"),
        ("EDG-07",),
    ),
    Case(
        "other-annotation-source",
        "EDG-08",
        WARNING,
        lambda g: _set(g.edge(HAS_CAPACITY)["attributes"], "annotation_source", "other_db"),
        ("EDG-08",),
    ),
    Case(
        "identical-edges",
        "EDG-09",
        ERROR,
        lambda g: _append_copy(g.edges, g.edge(PRODUCES)),
        ("EDG-09",),
    ),
    Case(
        "same-edge-other-evidence",
        "EDG-10",
        WARNING,
        lambda g: _append_copy(g.edges, g.edge(PRODUCES), evidence_id="SYNTHETIC_V1_BIS"),
        ("EDG-10",),
    ),
    Case(
        "self-interaction",
        "EDG-11",
        WARNING,
        lambda g: _append_copy(
            g.edges, g.edge(INTERACTS_WITH), target_id=g.node("taxon")["node_id"]
        ),
        ("EDG-11",),
    ),
    Case(
        "undeclared-interaction-type",
        "EDG-12",
        WARNING,
        lambda g: _set(g.edge(INTERACTS_WITH)["attributes"], "interaction_type", "mutualism"),
        ("EDG-12",),
    ),
    # --- Conectividad (CON) ---
    Case(
        "isolated-taxon",
        "CON-01",
        WARNING,
        lambda g: _append_copy(g.nodes, g.node("taxon", 2), node_id="synthetic:taxon:0003"),
        ("CON-01",),
    ),
    Case(
        "isolated-control-additive",
        "CON-02",
        INFO,
        lambda g: g.nodes.append(
            _node(
                "additive",
                2,
                category="control",
                substance="synthetic_none",
                dose=0.0,
                dose_unit="g/kg",
                control_label="control_basal",
            )
        ),
        ("CON-02",),
    ),
    Case(
        "additive-without-edges",
        "CON-03",
        WARNING,
        lambda g: _remove_edges(g, MODULATES_TAXON, MODULATES_FUNCTION),
        ("CON-01", "CON-03"),
        note="El único aditivo, no de control, queda aislado (CON-01) y su tipo sin aristas.",
    ),
    Case(
        "diet-component-split",
        "CON-04",
        WARNING,
        lambda g: _remove_edges(g, AVAILABLE_TO),
        ("CON-04",),
    ),
    # --- Tensores (TEN) ---
    Case(
        "relation-to-missing-type",
        "TEN-01",
        ERROR,
        lambda g: _store_edge(g, ("taxon", "feeds", "ghost")),
        ("TEN-01",),
        layer="tensors",
    ),
    Case(
        "undefined-num-nodes",
        "TEN-02",
        ERROR,
        lambda g: g.data["taxon"].__delattr__("x"),
        ("TEN-02", "TEN-06"),
        layer="tensors",
        note="Sin x, PyG no puede inferir num_nodes; TEN-06 informa el tensor ausente.",
    ),
    Case(
        "one-dimensional-edge-index",
        "TEN-03",
        ERROR,
        lambda g: _tensor(g, HAS_CAPACITY, "edge_index", lambda index: index[0]),
        ("TEN-03",),
        layer="tensors",
    ),
    Case(
        "index-out-of-range",
        "TEN-04",
        ERROR,
        lambda g: _set_tensor_value(g, HAS_CAPACITY, "edge_index", (1, 0), 99),
        ("TEN-04",),
        layer="tensors",
    ),
    Case(
        "int32-edge-index",
        "TEN-05",
        ERROR,
        lambda g: _tensor(g, HAS_CAPACITY, "edge_index", lambda index: index.int()),
        ("TEN-05",),
        layer="tensors",
    ),
    Case(
        "integer-features",
        "TEN-06",
        ERROR,
        lambda g: _tensor(g, "taxon", "x", lambda x: x.long()),
        ("TEN-06",),
        layer="tensors",
    ),
    Case(
        "float-mask",
        "TEN-07",
        ERROR,
        lambda g: _tensor(g, "taxon", "missing_mask", lambda mask: mask.float()),
        ("TEN-07",),
        layer="tensors",
    ),
    Case(
        "short-node-id",
        "TEN-08",
        ERROR,
        lambda g: _tensor(g, "function", "node_id", lambda ids: ids[:-1]),
        ("TEN-08",),
        layer="tensors",
    ),
    Case(
        "short-evidence-id",
        "TEN-09",
        ERROR,
        lambda g: _tensor(g, HAS_CAPACITY, "evidence_id", lambda ids: ids[:-1]),
        ("TEN-09",),
        layer="tensors",
    ),
    Case(
        "nan-feature",
        "TEN-10",
        ERROR,
        lambda g: _set_tensor_value(g, "taxon", "x", (0, 0), float("nan")),
        ("TEN-10",),
        layer="tensors",
    ),
    Case(
        "swapped-taxon-rows",
        "TEN-11",
        ERROR,
        _swap_taxon_rows,
        ("TEN-11",) * 4,
        layer="tensors",
        note=(
            "Intercambiar los dos taxones cambia el significado de las cuatro relaciones que los "
            "tocan: available_to, has_capacity, modulates e interacts_with."
        ),
    ),
    Case(
        "global-species",
        "TEN-12",
        ERROR,
        lambda g: setattr(g.data, "species", "pig"),
        ("TEN-12",),
        layer="tensors",
    ),
)


# ---------------------------------------------------------------------------
# Pruebas
# ---------------------------------------------------------------------------


def _specified_rules() -> set[str]:
    text = RULES.read_text(encoding="utf-8")
    return set(re.findall(r"^\| ((?:INS|NOD|EDG|CON|TEN|OUT|MET)-\d\d)\b", text, re.MULTILINE))


def _graph_for(case: Case, request: pytest.FixtureRequest) -> Graph:
    if case.layer == "tensors":
        return tensor_graph(request.getfixturevalue("heterodata_builder"))
    return record_graph()


def test_minimal_graph_has_no_findings(
    heterodata_builder: Callable[..., tuple[Any, Record]],
) -> None:
    assert record_graph().findings() == []
    assert tensor_graph(heterodata_builder).findings() == []


@pytest.mark.parametrize(
    "dataset",
    [
        generate_synthetic_dataset(),
        generate_synthetic_dataset(
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
        ),
        generate_scenario_dataset(),
    ],
    ids=["default", "beyond-catalog", "scenarios"],
)
def test_generated_graphs_have_no_errors_in_any_validator(
    dataset: SyntheticDataset, heterodata_builder: Callable[..., tuple[Any, Record]]
) -> None:
    findings = [
        *find_node_findings(dataset.instances, dataset.nodes, metadata=dataset.metadata),
        *find_edge_findings(dataset.nodes, dataset.edges, metadata=dataset.metadata),
        *find_connectivity_findings(dataset.nodes, dataset.edges, metadata=dataset.metadata),
    ]
    from nutrigraphdt.graph.validation.tensors import find_tensor_findings

    for instance in dataset.instances:
        data, metadata = heterodata_builder(dataset, instance.graph_id)
        findings += find_tensor_findings(
            data, instance=instance, edges=dataset.edges, metadata=metadata
        )

    assert [finding for finding in findings if finding.severity is Severity.ERROR] == []


@pytest.mark.parametrize("case", CASES, ids=[case.case_id for case in CASES])
def test_defect_is_detected_by_its_rule(case: Case, request: pytest.FixtureRequest) -> None:
    graph = _graph_for(case, request)
    case.mutate(graph)

    findings = graph.findings()

    assert Counter(finding.rule_id for finding in findings) == Counter(case.expected), (
        case.note or findings
    )
    targeted = [finding for finding in findings if finding.rule_id == case.rule_id]
    assert targeted, findings
    assert {finding.severity for finding in targeted} == {case.severity}


def test_every_rule_of_vg02_to_vg05_has_a_defective_case() -> None:
    specified = _specified_rules()
    covered = {case.rule_id for case in CASES}

    assert covered <= specified, covered - specified
    assert specified - VG07_RULES == covered


def test_every_case_targets_a_rule_it_expects() -> None:
    assert len({case.case_id for case in CASES}) == len(CASES)
    for case in CASES:
        assert case.rule_id in case.expected, case.case_id


def test_the_suite_is_deterministic() -> None:
    for case in CASES:
        if case.layer != "records":
            continue
        first, second = record_graph(), record_graph()
        case.mutate(first)
        case.mutate(second)
        assert first.findings() == second.findings(), case.case_id
