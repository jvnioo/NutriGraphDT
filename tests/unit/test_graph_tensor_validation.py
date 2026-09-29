"""Pruebas del validador de dimensiones y tipos de tensores (VG-05).

Cada regla TEN-01 a TEN-13 de `docs/graph-integrity-rules.md` tiene casos negativos construidos
alterando un solo tensor o atributo de un `HeteroData` válido, producido por el fixture
`heterodata_builder` (correspondencia de DS-01, no el constructor canónico). Casi todos exigen
exactamente el hallazgo esperado. Los grafos válidos no deben producir ningún hallazgo.

Requieren el extra `graph`; sin PyTorch Geometric se omiten.
"""

from __future__ import annotations

import copy
import json
import math
import warnings
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from nutrigraphdt.data.synthetic import (  # noqa: E402
    NodeCountConfig,
    SyntheticEdgeConfig,
    SyntheticNodeConfig,
    generate_scenario_dataset,
    generate_synthetic_dataset,
)
from nutrigraphdt.graph.validation import Finding, Severity  # noqa: E402
from nutrigraphdt.graph.validation.tensors import (  # noqa: E402
    INSTANCE_FIELDS,
    MAX_REPORTED_POSITIONS,
    find_tensor_findings,
)

Builder = Callable[..., tuple[Any, dict[str, Any]]]

PROVIDES = ("diet", "provides", "substrate")
HAS_CAPACITY = ("taxon", "has_capacity", "function")
MEASURED_IN = ("metabolite", "measured_in", "host")

BEYOND_CATALOG = NodeCountConfig(
    diet=3,
    additive=6,
    substrate=10,
    taxon=14,
    function=11,
    metabolite=8,
    host=2,
    phenotype=5,
)


@dataclass
class Graph:
    """`HeteroData` válido de una instancia, con sus registros y metadatos."""

    dataset: Any
    data: Any
    metadata: dict[str, Any]
    instance: dict[str, Any]

    def findings(self) -> list[Finding]:
        return find_tensor_findings(
            self.data,
            instance=self.instance,
            nodes=self.dataset.nodes,
            edges=self.dataset.edges,
            metadata=self.metadata,
        )


def _graph(builder: Builder, dataset: Any, *, features: bool = True, position: int = 0) -> Graph:
    instance = dataset.instances[position]
    data, metadata = builder(dataset, instance.graph_id, features=features)
    return Graph(dataset=dataset, data=data, metadata=metadata, instance=instance.to_dict())


@pytest.fixture
def graph(heterodata_builder: Builder) -> Graph:
    return _graph(heterodata_builder, generate_synthetic_dataset())


def _rules(findings: list[Finding]) -> list[str]:
    return [finding.rule_id for finding in findings]


def _only(findings: list[Finding], rule_id: str) -> Finding:
    assert _rules(findings) == [rule_id], findings
    return findings[0]


def _pyg_accepts(data: Any) -> bool:
    """Resultado de `HeteroData.validate()` sobre una copia, sin advertencias."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return bool(copy.deepcopy(data).validate(raise_on_error=False))


def _assert_same(before: Any, after: Any) -> None:
    """Igualdad estructural, con tensores comparados por `dtype`, forma y valores."""
    if isinstance(before, torch.Tensor):
        assert isinstance(after, torch.Tensor)
        assert before.dtype == after.dtype and before.shape == after.shape
        assert torch.equal(before, after) or (
            before.is_floating_point() and torch.allclose(before, after, equal_nan=True)
        )
    elif isinstance(before, dict):
        assert isinstance(after, dict) and before.keys() == after.keys()
        for key in before:
            _assert_same(before[key], after[key])
    elif isinstance(before, list | tuple):
        assert type(before) is type(after) and len(before) == len(after)
        for item_before, item_after in zip(before, after, strict=True):
            _assert_same(item_before, item_after)
    else:
        assert before == after


def _remove_column(graph: Graph, edge_type: tuple[str, str, str], column: int) -> None:
    """Quita una columna de una relación manteniendo alineados sus tensores y listas."""
    store = graph.data[edge_type]
    keep = [index for index in range(store.edge_index.size(1)) if index != column]
    store.edge_index = store.edge_index[:, keep]
    store.edge_attr = store.edge_attr[keep]
    for name in ("evidence_id", "evidence_status", "evidence_method", "raw_attributes"):
        store[name] = [store[name][index] for index in keep]


# ---------------------------------------------------------------------------
# Grafos válidos: sin hallazgos
# ---------------------------------------------------------------------------


def test_default_graph_has_no_findings(graph: Graph) -> None:
    assert graph.findings() == []
    assert _pyg_accepts(graph.data)


def test_graph_without_features_matches_the_exported_metadata(heterodata_builder: Builder) -> None:
    dataset = generate_synthetic_dataset()
    graph = _graph(heterodata_builder, dataset, features=False)

    assert graph.metadata["node_feature_schema"] == {}
    assert all(store.x.shape[1] == 0 for _, store in graph.data.node_items())
    assert graph.findings() == []


def test_scenario_graphs_have_no_findings(heterodata_builder: Builder) -> None:
    dataset = generate_scenario_dataset()

    for position in range(len(dataset.instances)):
        graph = _graph(heterodata_builder, dataset, position=position)
        assert graph.findings() == []


@pytest.mark.parametrize("seed", [1, 42])
@pytest.mark.parametrize(
    "counts",
    [NodeCountConfig(), NodeCountConfig(1, 1, 1, 1, 1, 1, 1, 1), BEYOND_CATALOG],
    ids=["default", "minimal", "beyond-catalog"],
)
def test_generated_graphs_have_no_findings(
    heterodata_builder: Builder, seed: int, counts: NodeCountConfig
) -> None:
    dataset = generate_synthetic_dataset(
        SyntheticNodeConfig(random_seed=seed, counts=counts),
        SyntheticEdgeConfig(random_seed=seed),
    )
    graph = _graph(heterodata_builder, dataset)

    assert graph.findings() == []
    assert _pyg_accepts(graph.data)


# ---------------------------------------------------------------------------
# Comportamiento general
# ---------------------------------------------------------------------------


def _break_everything(graph: Graph) -> None:
    ghost = graph.data["taxon", "feeds", "ghost"]
    ghost.edge_index = torch.tensor([[0], [0]])
    graph.data["taxon"].x[0, 0] = math.nan
    graph.data[HAS_CAPACITY].edge_index[1, 0] = 999
    graph.data.species = "pig"


def test_does_not_modify_the_graph(graph: Graph) -> None:
    _break_everything(graph)
    node_types = list(graph.data.node_types)
    edge_types = list(graph.data.edge_types)
    before = copy.deepcopy(graph.data.to_dict())

    graph.findings()

    assert list(graph.data.node_types) == node_types
    assert list(graph.data.edge_types) == edge_types
    _assert_same(before, graph.data.to_dict())


def test_pyg_validate_mutates_the_graph_and_this_validator_does_not(graph: Graph) -> None:
    """Razón para no llamar a `HeteroData.validate()` (ver el docstring de `tensors`)."""
    graph.data["taxon", "feeds", "ghost"].edge_index = torch.tensor([[0], [0]])
    probe = copy.deepcopy(graph.data)

    rules = _rules(graph.findings())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        probe.validate(raise_on_error=False)

    assert "TEN-01" in rules
    assert "ghost" not in graph.data.node_types
    assert "ghost" in probe.node_types


def test_findings_are_json_serializable_errors(graph: Graph) -> None:
    _break_everything(graph)

    findings = graph.findings()

    assert findings
    for finding in findings:
        assert finding.severity is Severity.ERROR
        encoded = json.dumps(finding.to_dict(), allow_nan=False)
        assert json.loads(encoded) == finding.to_dict()


def test_findings_are_deterministic(graph: Graph) -> None:
    _break_everything(graph)

    assert graph.findings() == graph.findings()


def test_instance_record_and_dictionary_give_the_same_findings(graph: Graph) -> None:
    graph.data.species = "pig"
    record = graph.dataset.instances[0]

    from_record = find_tensor_findings(
        graph.data,
        instance=record,
        nodes=graph.dataset.nodes,
        edges=graph.dataset.edges,
        metadata=graph.metadata,
    )

    assert from_record == graph.findings()
    assert _rules(from_record) == ["TEN-12"]


# ---------------------------------------------------------------------------
# TEN-01 y TEN-02: tipos referenciados
# ---------------------------------------------------------------------------


def _complete_edge_store(graph: Graph, edge_type: tuple[str, str, str]) -> None:
    store = graph.data[edge_type]
    store.edge_index = torch.tensor([[0], [0]])
    store.edge_attr = torch.zeros((1, 0))
    store.evidence_id = ["SYNTHETIC_V1"]
    store.evidence_status = ["synthetic"]
    store.evidence_method = ["synthetic_generator"]
    store.raw_attributes = [{}]


def test_ten01_detects_a_relation_to_a_missing_node_type(graph: Graph) -> None:
    _complete_edge_store(graph, ("taxon", "feeds", "ghost"))

    finding = _only(graph.findings(), "TEN-01")

    assert finding.location == {"edge_type": ["taxon", "feeds", "ghost"], "node_type": "ghost"}
    assert not _pyg_accepts(graph.data)


def test_ten02_detects_undefined_num_nodes(graph: Graph) -> None:
    del graph.data["taxon"].x

    findings = graph.findings()

    # Sin `x`, PyG no puede inferir `num_nodes`; TEN-06 informa el tensor ausente.
    assert _rules(findings) == ["TEN-02", "TEN-06"]
    assert findings[0].location["node_type"] == "taxon"
    assert list(HAS_CAPACITY) in findings[0].location["edge_types"]
    assert not _pyg_accepts(graph.data)


# ---------------------------------------------------------------------------
# TEN-03 a TEN-05: edge_index
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mutate",
    [
        lambda index: torch.cat([index, index[:1]]),
        lambda index: index[0],
        lambda index: index.tolist(),
        lambda index: None,
    ],
    ids=["three-rows", "one-dimension", "list", "absent"],
)
def test_ten03_detects_edge_index_with_wrong_shape(graph: Graph, mutate: Any) -> None:
    store = graph.data[HAS_CAPACITY]
    value = mutate(store.edge_index)
    if value is None:
        del store.edge_index
    else:
        store.edge_index = value

    finding = _only(graph.findings(), "TEN-03")

    assert finding.location == {"edge_type": list(HAS_CAPACITY), "tensor": "edge_index"}


@pytest.mark.parametrize(("row", "endpoint"), [(0, "source"), (1, "target")])
def test_ten04_detects_indices_out_of_range(graph: Graph, row: int, endpoint: str) -> None:
    node_type = HAS_CAPACITY[0] if row == 0 else HAS_CAPACITY[2]
    limit = graph.data[node_type].num_nodes
    graph.data[HAS_CAPACITY].edge_index[row, 2] = limit

    finding = _only(graph.findings(), "TEN-04")

    assert finding.location["row"] == endpoint
    assert finding.location["limit"] == limit
    assert finding.location["columns"] == [2]
    assert finding.location["values"] == [limit]
    assert not _pyg_accepts(graph.data)


def test_ten04_detects_negative_indices_in_both_rows(graph: Graph) -> None:
    graph.data[HAS_CAPACITY].edge_index[:, 0] = -1

    findings = graph.findings()

    assert _rules(findings) == ["TEN-04", "TEN-04"]
    assert [finding.location["row"] for finding in findings] == ["source", "target"]


@pytest.mark.parametrize("dtype", [torch.int32, torch.float32])
def test_ten05_detects_edge_index_that_is_not_long(graph: Graph, dtype: Any) -> None:
    store = graph.data[HAS_CAPACITY]
    store.edge_index = store.edge_index.to(dtype)

    finding = _only(graph.findings(), "TEN-05")

    assert finding.observed == str(dtype)
    # PyG no comprueba el dtype: por eso TEN-05 existe.
    assert _pyg_accepts(graph.data)


@pytest.mark.parametrize("value", [999.0, 1.5])
def test_ten04_is_not_evaluated_on_non_integer_indices(graph: Graph, value: float) -> None:
    store = graph.data[HAS_CAPACITY]
    store.edge_index = store.edge_index.float()
    store.edge_index[1, 0] = value

    # Sin dtype entero los valores no son índices; TEN-05 ya informa el defecto.
    finding = _only(graph.findings(), "TEN-05")

    assert finding.observed == "torch.float32"


# ---------------------------------------------------------------------------
# TEN-06 a TEN-08: almacenes de nodos
# ---------------------------------------------------------------------------


def test_ten06_detects_features_that_are_not_floating_point(graph: Graph) -> None:
    graph.data["taxon"].x = graph.data["taxon"].x.long()

    finding = _only(graph.findings(), "TEN-06")

    assert finding.observed == "torch.int64"


def test_ten06_detects_columns_different_from_the_declared_schema(graph: Graph) -> None:
    store = graph.data["taxon"]
    store.x = torch.cat([store.x, torch.zeros_like(store.x)], dim=1)
    store.missing_mask = torch.cat([store.missing_mask, store.missing_mask], dim=1)

    finding = _only(graph.findings(), "TEN-06")

    assert finding.location["declared_columns"] == 1
    assert finding.observed == json.dumps([store.x.shape[0], 2])


def test_ten06_detects_rows_different_from_num_nodes(graph: Graph) -> None:
    store = graph.data["taxon"]
    rows = store.x.shape[0]
    store.num_nodes = rows
    store.x = torch.cat([store.x, store.x[:1]])
    store.missing_mask = torch.cat([store.missing_mask, store.missing_mask[:1]])

    finding = _only(graph.findings(), "TEN-06")

    assert finding.expected == f"[{rows}, 1]"


def test_ten06_and_ten09_reject_columns_that_are_not_declared(
    heterodata_builder: Builder,
) -> None:
    dataset = generate_synthetic_dataset()
    data, _ = heterodata_builder(dataset, dataset.instances[0].graph_id)

    findings = find_tensor_findings(
        data,
        instance=dataset.instances[0],
        nodes=dataset.nodes,
        edges=dataset.edges,
        metadata=dataset.metadata,
    )

    # El metadata exportado no declara columnas; DS-01 prohíbe inferir su orden.
    assert _rules(findings) == ["TEN-06"] * 6 + ["TEN-09"]
    assert {finding.location.get("node_type") for finding in findings[:6]} == {
        "additive",
        "substrate",
        "taxon",
        "function",
        "metabolite",
        "phenotype",
    }


def test_ten06_detects_a_malformed_schema_entry(graph: Graph) -> None:
    graph.metadata["node_feature_schema"]["taxon"] = {"columns": ["abundance"]}

    finding = _only(graph.findings(), "TEN-06")

    assert finding.location == {"node_type": "taxon", "schema": "node_feature_schema"}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda mask: mask.float(),
        lambda mask: mask[:, :0],
        lambda mask: None,
    ],
    ids=["not-boolean", "other-shape", "absent"],
)
def test_ten07_detects_invalid_missing_mask(graph: Graph, mutate: Any) -> None:
    store = graph.data["function"]
    value = mutate(store.missing_mask)
    if value is None:
        del store.missing_mask
    else:
        store.missing_mask = value

    finding = _only(graph.findings(), "TEN-07")

    assert finding.location == {"node_type": "function", "tensor": "missing_mask"}


@pytest.mark.parametrize(
    ("attribute", "mutate"),
    [
        ("node_id", lambda value: value[:-1]),
        ("source_id", lambda value: "SYNTHETIC_V1"),
        ("raw_attributes", lambda value: None),
    ],
    ids=["short-node-id", "text-source-id", "absent-raw-attributes"],
)
def test_ten08_detects_lists_not_aligned_with_x(graph: Graph, attribute: str, mutate: Any) -> None:
    store = graph.data["function"]
    value = mutate(store[attribute])
    if value is None:
        del store[attribute]
    else:
        store[attribute] = value

    finding = _only(graph.findings(), "TEN-08")

    assert finding.location == {"node_type": "function", "attribute": attribute}


def test_ten08_detects_repeated_node_ids(graph: Graph) -> None:
    store = graph.data["metabolite"]
    store.node_id = [store.node_id[0], *store.node_id[:-1]]

    findings = graph.findings()

    # El ID repetido también cambia el significado de las aristas de esas filas (TEN-11), y el
    # último metabolito ya no está en el almacén (TEN-13).
    assert _rules(findings)[0] == "TEN-08"
    assert set(_rules(findings)) == {"TEN-08", "TEN-11", "TEN-13"}
    assert findings[0].location["repeated"] == [store.node_id[0]]


# ---------------------------------------------------------------------------
# TEN-13: nodos del almacén frente a nodes.jsonl
# ---------------------------------------------------------------------------


def _add_isolated_record(graph: Graph, node_type: str, node_id: str) -> None:
    """Agrega a los registros un nodo sin aristas que el `HeteroData` no contiene."""
    template = next(node for node in graph.dataset.nodes if node.node_type == node_type)
    graph.dataset = replace(
        graph.dataset, nodes=[*graph.dataset.nodes, replace(template, node_id=node_id)]
    )


def test_ten13_detects_an_isolated_node_lost_in_the_conversion(graph: Graph) -> None:
    _add_isolated_record(graph, "taxon", "synthetic:taxon:0099")

    finding = _only(graph.findings(), "TEN-13")

    assert finding.location == {
        "node_type": "taxon",
        "missing_count": 1,
        "missing": ["synthetic:taxon:0099"],
        "extra_count": 0,
        "extra": [],
    }


def test_ten13_detects_an_isolated_node_with_a_wrong_id(heterodata_builder: Builder) -> None:
    """TEN-11 no lo detecta: el nodo no tiene aristas que cambien de significado."""
    dataset = generate_synthetic_dataset(SyntheticNodeConfig(counts=BEYOND_CATALOG))
    beyond = _graph(heterodata_builder, dataset)
    store = beyond.data["additive"]
    isolated = "synthetic:additive:0005"  # aditivo de control sin aristas (X-01)
    store.node_id = [
        "synthetic:additive:9999" if node_id == isolated else node_id for node_id in store.node_id
    ]

    finding = _only(beyond.findings(), "TEN-13")

    assert finding.location["missing"] == [isolated]
    assert finding.location["extra"] == ["synthetic:additive:9999"]


def test_ten13_detects_a_node_type_without_store(graph: Graph) -> None:
    del graph.data["phenotype"]
    for edge_type in [key for key in graph.data.edge_types if "phenotype" in key]:
        del graph.data[edge_type]
    expected = sorted(node.node_id for node in graph.dataset.nodes if node.node_type == "phenotype")

    findings = graph.findings()

    ten13 = [finding for finding in findings if finding.rule_id == "TEN-13"]
    assert len(ten13) == 1
    assert ten13[0].location["missing"] == expected
    # Las aristas de los fenotipos también se perdieron (TEN-11).
    assert set(_rules(findings)) == {"TEN-11", "TEN-13"}


def test_ten13_is_not_evaluated_when_node_id_is_not_aligned(graph: Graph) -> None:
    store = graph.data["function"]
    store.node_id = store.node_id[:-1]

    # TEN-08 ya informa la lista desalineada.
    _only(graph.findings(), "TEN-08")


# ---------------------------------------------------------------------------
# TEN-09: almacenes de aristas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("edge_type", "mutate"),
    [
        (PROVIDES, lambda store: store.__delattr__("edge_attr")),
        (PROVIDES, lambda store: setattr(store, "edge_attr", store.edge_attr.long())),
        (PROVIDES, lambda store: setattr(store, "edge_attr", store.edge_attr[:, :0])),
        (HAS_CAPACITY, lambda store: setattr(store, "edge_attr", store.edge_attr[1:])),
        (HAS_CAPACITY, lambda store: setattr(store, "evidence_id", store.evidence_id[1:])),
        (HAS_CAPACITY, lambda store: store.__delattr__("raw_attributes")),
        (MEASURED_IN, lambda store: setattr(store, "evidence_status", "synthetic")),
    ],
    ids=[
        "absent-edge-attr",
        "integer-edge-attr",
        "undeclared-width",
        "edge-attr-rows",
        "short-evidence-id",
        "absent-raw-attributes",
        "text-evidence-status",
    ],
)
def test_ten09_detects_edge_features_not_aligned_with_edge_index(
    graph: Graph, edge_type: tuple[str, str, str], mutate: Any
) -> None:
    mutate(graph.data[edge_type])

    finding = _only(graph.findings(), "TEN-09")

    assert finding.location["edge_type"] == list(edge_type)


def test_ten09_detects_a_malformed_schema_entry(graph: Graph) -> None:
    graph.metadata["edge_feature_schema"]["diet|provides|substrate"] = "proportion"

    finding = _only(graph.findings(), "TEN-09")

    assert finding.location == {"edge_type": list(PROVIDES), "schema": "edge_feature_schema"}


# ---------------------------------------------------------------------------
# TEN-10: valores no finitos
# ---------------------------------------------------------------------------


def test_ten10_detects_nan_even_in_masked_positions(graph: Graph) -> None:
    store = graph.data["taxon"]
    store.missing_mask[3, 0] = True
    store.x[3, 0] = math.nan

    finding = _only(graph.findings(), "TEN-10")

    assert finding.location == {
        "node_type": "taxon",
        "tensor": "x",
        "non_finite_count": 1,
        "positions": [[3, 0]],
    }


def test_ten10_detects_infinite_edge_features(graph: Graph) -> None:
    graph.data[PROVIDES].edge_attr[1, 0] = -math.inf

    finding = _only(graph.findings(), "TEN-10")

    assert finding.location["edge_type"] == list(PROVIDES)
    assert finding.location["positions"] == [[1, 0]]


def test_ten10_detects_non_finite_targets(graph: Graph) -> None:
    rows = graph.data["metabolite"].num_nodes
    y = torch.ones(rows)
    y[0] = math.nan
    graph.data["metabolite"].y = y

    finding = _only(graph.findings(), "TEN-10")

    assert finding.location["tensor"] == "y"


def test_ten10_lists_a_bounded_number_of_positions(heterodata_builder: Builder) -> None:
    graph = _graph(
        heterodata_builder, generate_synthetic_dataset(SyntheticNodeConfig(counts=BEYOND_CATALOG))
    )
    graph.data["taxon"].x[:] = math.nan

    finding = _only(graph.findings(), "TEN-10")

    assert finding.location["non_finite_count"] == 14
    assert len(finding.location["positions"]) == MAX_REPORTED_POSITIONS


# ---------------------------------------------------------------------------
# TEN-11: significado de las aristas
# ---------------------------------------------------------------------------


def test_ten11_detects_rows_assigned_to_the_wrong_nodes(graph: Graph) -> None:
    store = graph.data["taxon"]
    node_ids = list(store.node_id)
    node_ids[0], node_ids[1] = node_ids[1], node_ids[0]
    store.node_id = node_ids

    findings = graph.findings()

    assert findings
    assert set(_rules(findings)) == {"TEN-11"}
    assert all("taxon" in finding.location["edge_type"] for finding in findings)


def test_ten11_does_not_require_a_column_order(graph: Graph) -> None:
    store = graph.data[HAS_CAPACITY]
    order = list(reversed(range(store.edge_index.size(1))))
    store.edge_index = store.edge_index[:, order]
    store.raw_attributes = [store.raw_attributes[index] for index in order]

    assert graph.findings() == []


def test_ten11_detects_a_lost_edge(graph: Graph) -> None:
    _remove_column(graph, HAS_CAPACITY, 0)

    finding = _only(graph.findings(), "TEN-11")

    assert finding.location["missing_record_count"] == 1
    assert finding.location["unmatched_column_count"] == 0


def test_ten11_detects_a_relation_missing_from_the_graph(graph: Graph) -> None:
    edges = graph.data[MEASURED_IN].edge_index.size(1)
    del graph.data[MEASURED_IN]

    finding = _only(graph.findings(), "TEN-11")

    assert finding.location["edge_type"] == list(MEASURED_IN)
    assert finding.location["missing_record_count"] == edges


def test_ten11_detects_columns_without_records(graph: Graph) -> None:
    _complete_edge_store(graph, ("taxon", "ghost_relation", "function"))

    finding = _only(graph.findings(), "TEN-11")

    assert finding.location["unmatched_column_count"] == 1
    assert finding.location["unmatched_columns"][0]["column"] == 0


# ---------------------------------------------------------------------------
# TEN-12: atributos globales
# ---------------------------------------------------------------------------


def test_ten12_stores_every_instance_field(graph: Graph) -> None:
    assert set(INSTANCE_FIELDS) == set(graph.instance)


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("species", "pig"),
        ("graph_id", None),
        ("is_synthetic", 1),
        ("sample_id", "tensor"),
        ("timepoint", "day_21"),
    ],
    ids=["different", "absent", "bool-as-int", "tensor", "null-timepoint-set"],
)
def test_ten12_detects_global_attributes_different_from_the_instance(
    graph: Graph, attribute: str, value: Any
) -> None:
    if value is None:
        delattr(graph.data, attribute)
    elif value == "tensor":
        setattr(graph.data, attribute, torch.tensor([1]))
    else:
        setattr(graph.data, attribute, value)

    finding = _only(graph.findings(), "TEN-12")

    assert finding.location == {"attribute": attribute}


def test_ten12_detects_a_declared_timepoint_that_the_graph_lost(graph: Graph) -> None:
    graph.instance["timepoint"] = "day_21"

    finding = _only(graph.findings(), "TEN-12")

    assert finding.observed == "atributo ausente"


def test_ten12_accepts_null_timepoint_as_an_absent_attribute(graph: Graph) -> None:
    assert graph.instance["timepoint"] is None
    assert getattr(graph.data, "timepoint", None) is None
    assert graph.findings() == []
