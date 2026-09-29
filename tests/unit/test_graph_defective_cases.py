"""Suite transversal de grafos defectuosos (VG-06).

Parte de un grafo mínimo, válido y escrito a mano, y aplica un catálogo de defectos. Cada caso
introduce **un** defecto dirigido a una regla identificable de `docs/graph-integrity-rules.md`,
ejecuta **todos** los validadores y exige el conjunto exacto de hallazgos. Así se comprueba que
el defecto se detecta con su severidad y que no provoca hallazgos espurios en otros
validadores. Cuando un defecto implica otros por construcción (por ejemplo, un nodo de tipo
desconocido deja aristas sin extremo), el caso los declara y explica.

Las pruebas unitarias de cada validador cubren sus variantes. Esta suite cubre lo transversal:
cobertura de todas las reglas, interacción entre validadores y regresiones. Desde VG-07 ejecuta
los validadores mediante la interfaz común `validate_graph`, y cubre también los pares de
escenarios (INS-05, INS-06), las salidas (OUT) y los metadatos (MET).

Salvo en los casos de MET-03, `counts` de `metadata.json` se recalcula después de aplicar el
defecto: el caso modela un dataset exportado con ese defecto, y así no arrastra un MET-03 que no
es el defecto probado.

Todo el contenido es sintético y no representa observaciones reales.
"""

from __future__ import annotations

import copy
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import pytest

from nutrigraphdt import __version__
from nutrigraphdt.data.synthetic import (
    Edge,
    InstanceRecord,
    Node,
    NodeCountConfig,
    NodeType,
    SyntheticDataset,
    SyntheticNodeConfig,
    generate_scenario_dataset,
    generate_synthetic_dataset,
)
from nutrigraphdt.data.synthetic.export import build_metadata
from nutrigraphdt.graph.validation import Finding, RawDataset, Severity, validate_graph

Record = dict[str, Any]
EdgeType = tuple[str, str, str]

RULES = Path(__file__).resolve().parents[2] / "docs" / "graph-integrity-rules.md"
GRAPH_ID = "synthetic:defects:0001"
INTERVENTION_ID = "synthetic:defects:0002"


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
    outputs: list[Record] = field(default_factory=list)
    data: Any = None

    def node(self, node_type: str, number: int = 1, graph_id: str = GRAPH_ID) -> Record:
        node_id = f"synthetic:{node_type}:{number:04d}"
        return next(
            node
            for node in self.nodes
            if node["graph_id"] == graph_id
            and node["node_type"] == node_type
            and node["node_id"] == node_id
        )

    def edge(self, edge_type: EdgeType, position: int = 0) -> Record:
        matches = [
            edge
            for edge in self.edges
            if (edge["source_type"], edge["relation_type"], edge["target_type"]) == edge_type
        ]
        return matches[position]

    def recount(self) -> None:
        """Recalcula `counts` como lo haría el exportador con los registros actuales."""
        counts: dict[str, Any] = {}
        for instance in self.instances:
            graph_id = instance.get("graph_id") if isinstance(instance, dict) else None
            if isinstance(graph_id, str) and graph_id:
                counts[graph_id] = {
                    "nodes": {node_type.value: 0 for node_type in NodeType},
                    "edges": {},
                    "outputs": 0,
                }

        def entry(record: Record) -> Any:
            graph_id = record.get("graph_id")
            return counts.get(graph_id) if isinstance(graph_id, str) else None

        for node in self.nodes:
            node_counts = entry(node)
            node_type = node.get("node_type")
            if node_counts is not None and isinstance(node_type, str) and node_type:
                node_counts["nodes"][node_type] = node_counts["nodes"].get(node_type, 0) + 1
        for edge in self.edges:
            edge_counts = entry(edge)
            types = [edge.get(name) for name in ("source_type", "relation_type", "target_type")]
            if edge_counts is not None and all(isinstance(value, str) and value for value in types):
                key = "|".join(types)
                edge_counts["edges"][key] = edge_counts["edges"].get(key, 0) + 1
        for output in self.outputs:
            output_counts = entry(output)
            if output_counts is not None:
                output_counts["outputs"] += 1
        self.metadata["counts"] = counts

    def findings(self) -> list[Finding]:
        """Hallazgos de todas las reglas, mediante la interfaz común `validate_graph`."""
        records = RawDataset(
            metadata=self.metadata,
            instances=self.instances,
            nodes=self.nodes,
            edges=self.edges,
            outputs=self.outputs,
        )
        heterodata = None if self.data is None else {GRAPH_ID: self.data}
        return list(validate_graph(records, heterodata=heterodata).findings)


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
    recount: bool = True
    """Recalcular `counts` tras el defecto; `False` solo en los casos que prueban MET-03."""


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


def _add_intervention(graph: Graph) -> None:
    """Agrega un escenario intervenido válido: solo cambia la variable declarada."""
    intervention = copy.deepcopy(graph.instances[0])
    intervention.update(
        graph_id=INTERVENTION_ID,
        scenario_id="intervention",
        diet_treatment="synthetic_basal_diet:crude_protein=270.0",
    )
    graph.instances.append(intervention)
    for items in (graph.nodes, graph.edges):
        for record in [record for record in items if record["graph_id"] == GRAPH_ID]:
            _append_copy(items, record, graph_id=INTERVENTION_ID)
    diet = graph.node("diet", graph_id=INTERVENTION_ID)
    diet["attributes"]["composition"][0]["value"] = 270.0


def _rename_intervention_taxon(graph: Graph) -> None:
    """Cambia el `node_id` de un taxón intervenido, de forma coherente con sus aristas."""
    _add_intervention(graph)
    old_id = graph.node("taxon", 2, graph_id=INTERVENTION_ID)["node_id"]
    new_id = "synthetic:taxon:0099"
    graph.node("taxon", 2, graph_id=INTERVENTION_ID)["node_id"] = new_id
    for edge in graph.edges:
        if edge["graph_id"] != INTERVENTION_ID:
            continue
        for side in ("source", "target"):
            if edge[f"{side}_type"] == "taxon" and edge[f"{side}_id"] == old_id:
                edge[f"{side}_id"] = new_id


def _drop_intervention_edge(graph: Graph) -> None:
    """Quita del escenario intervenido una arista que no es puente (el aditivo sigue conectado)."""
    _add_intervention(graph)
    graph.edges.remove(
        next(
            edge
            for edge in graph.edges
            if edge["graph_id"] == INTERVENTION_ID
            and (edge["source_type"], edge["relation_type"], edge["target_type"])
            == MODULATES_FUNCTION
        )
    )


def _change_intervention_value(graph: Graph) -> None:
    _add_intervention(graph)
    graph.node("metabolite", graph_id=INTERVENTION_ID)["attributes"]["concentration"] = 99.0


def _add_output(graph: Graph, **changes: Any) -> None:
    """Agrega una salida sintética válida sobre el metabolito, con los cambios indicados."""
    output: Record = {
        "graph_id": GRAPH_ID,
        "target_type": "metabolite",
        "target_id": graph.node("metabolite")["node_id"],
        "value": 12.5,
        "measured_or_predicted": "synthetic",
        "unit": "umol/g",
        "sample_matrix": "cecal_content",
        "model_version": None,
    }
    output.update(changes)
    graph.outputs.append(output)


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
    Case(
        "edge-attribute-outside-contract",
        "EDG-13",
        WARNING,
        lambda g: _set(g.edge(PRODUCES)["attributes"], "confidence", 0.9),
        ("EDG-13",),
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
    Case(
        "isolated-node-lost-in-conversion",
        "TEN-13",
        ERROR,
        lambda g: _append_copy(g.nodes, g.node("taxon", 2), node_id="synthetic:taxon:0003"),
        ("CON-01", "TEN-13"),
        layer="tensors",
        note=(
            "Los registros ganan un taxón sin aristas (CON-01, advertencia) que el HeteroData no "
            "contiene; TEN-11 no lo ve porque ninguna arista lo referencia."
        ),
    ),
    # --- Escenarios comparables (INS-05 a INS-07) ---
    Case(
        "intervention-with-other-node-ids",
        "INS-05",
        ERROR,
        _rename_intervention_taxon,
        ("INS-05", "INS-07", "INS-07"),
        note=(
            "El taxón renombrado cambia también los extremos de sus dos aristas (has_capacity e "
            "interacts_with), así que esas relaciones difieren entre escenarios (INS-07)."
        ),
    ),
    Case(
        "intervention-without-an-edge",
        "INS-07",
        WARNING,
        _drop_intervention_edge,
        ("INS-07",),
    ),
    Case(
        "intervention-changes-an-undeclared-value",
        "INS-06",
        WARNING,
        _change_intervention_value,
        ("INS-06",),
    ),
    # --- Salidas (OUT) ---
    Case(
        "output-to-missing-node",
        "OUT-01",
        ERROR,
        lambda g: _add_output(g, target_id="synthetic:metabolite:9999"),
        ("OUT-01",),
    ),
    Case(
        "model-version-without-prediction",
        "OUT-02",
        ERROR,
        lambda g: _add_output(g, model_version="synthetic-gnn-0.1"),
        ("OUT-02",),
    ),
    Case(
        "measured-output-in-synthetic-instance",
        "OUT-03",
        ERROR,
        lambda g: _add_output(g, measured_or_predicted="measured"),
        ("OUT-03",),
    ),
    Case(
        "output-without-unit",
        "OUT-04",
        ERROR,
        lambda g: _add_output(g, unit=""),
        ("OUT-04",),
    ),
    # --- Metadatos (MET) ---
    Case(
        "metadata-without-seed",
        "MET-01",
        ERROR,
        lambda g: _drop(g.metadata, "random_seed"),
        ("MET-01",),
    ),
    Case(
        "metadata-declares-real-data",
        "MET-02",
        ERROR,
        lambda g: _set(g.metadata, "is_synthetic", False),
        ("MET-02",),
    ),
    Case(
        "output-removed-after-export",
        "MET-03",
        ERROR,
        lambda g: _set(g.metadata["counts"][GRAPH_ID], "outputs", 1),
        ("MET-03",),
        recount=False,
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


def _mutated(case: Case, graph: Graph) -> Graph:
    case.mutate(graph)
    if case.recount:
        graph.recount()
    return graph


def test_minimal_graph_has_no_findings(
    heterodata_builder: Callable[..., tuple[Any, Record]],
) -> None:
    assert record_graph().findings() == []
    assert tensor_graph(heterodata_builder).findings() == []


def test_valid_intervention_and_output_add_no_findings() -> None:
    graph = record_graph()
    _add_intervention(graph)
    _add_output(graph)
    _add_output(graph, measured_or_predicted="predicted", model_version="synthetic-gnn-0.1")
    graph.recount()

    assert graph.findings() == []


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
    heterodata: dict[str, Any] = {}
    metadata: Record = {}
    for instance in dataset.instances:
        heterodata[instance.graph_id], metadata = heterodata_builder(dataset, instance.graph_id)
    records = RawDataset(
        metadata=metadata,
        instances=list(dataset.instances),
        nodes=list(dataset.nodes),
        edges=list(dataset.edges),
        outputs=list(dataset.outputs),
    )

    report = validate_graph(records, heterodata=heterodata)

    assert report.errors == ()
    assert "TEN" in report.evaluated and not report.not_evaluated
    assert report.deliverable_graph_ids == report.graph_ids


@pytest.mark.parametrize("case", CASES, ids=[case.case_id for case in CASES])
def test_defect_is_detected_by_its_rule(case: Case, request: pytest.FixtureRequest) -> None:
    graph = _mutated(case, _graph_for(case, request))

    findings = graph.findings()

    assert Counter(finding.rule_id for finding in findings) == Counter(case.expected), (
        case.note or findings
    )
    targeted = [finding for finding in findings if finding.rule_id == case.rule_id]
    assert targeted, findings
    assert {finding.severity for finding in targeted} == {case.severity}


def test_every_rule_of_the_specification_has_a_defective_case() -> None:
    specified = _specified_rules()
    covered = {case.rule_id for case in CASES}

    # INS 7 + NOD 12 + EDG 13 + CON 4 + OUT 4 + MET 3 + TEN 13 (versión 1.1.0).
    assert len(specified) == 56
    assert covered == specified, specified ^ covered


def test_every_case_targets_a_rule_it_expects() -> None:
    assert len({case.case_id for case in CASES}) == len(CASES)
    for case in CASES:
        assert case.rule_id in case.expected, case.case_id


def test_the_suite_is_deterministic() -> None:
    for case in CASES:
        if case.layer != "records":
            continue
        first = _mutated(case, record_graph())
        second = _mutated(case, record_graph())
        assert first.findings() == second.findings(), case.case_id
