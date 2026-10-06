"""Pruebas del flujo dataset sintético -> `HeteroData` sobre un grafo mínimo (A35-3, #30).

Usan el fixture `minimal_synthetic_dataset` (ver `tests/conftest.py`): una instancia con
`MINIMAL_NODE_COUNTS` nodos y todas las relaciones permitidas con probabilidad 1. Los conteos
y dimensiones esperados están escritos a mano en las tablas de este módulo, no recalculados
desde el dataset, para que un cambio en el generador o en el constructor se detecte aquí.

Verifican el número de nodos y aristas por tipo, las dimensiones de `x`, `missing_mask`,
`edge_attr`, `edge_index` e `y`, y que ningún tensor de punto flotante contenga NaN ni infinitos,
también tras exportar a JSONL, convertir, serializar a `.pt` y volver a cargar.

Requieren el extra `graph`.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from nutrigraphdt.data.synthetic import (  # noqa: E402
    SyntheticDataset,
    export_dataset,
    generate_scenario_dataset,
    generate_synthetic_dataset,
    load_dataset,
)
from nutrigraphdt.graph.heterodata import (  # noqa: E402
    PrototypeGraphs,
    build_synthetic_graphs,
    load_graphs,
    save_graphs,
)

GRAPH_ID = "synthetic:graph:0001"

EXPECTED_NODES: dict[str, int] = {
    "diet": 1,
    "additive": 1,
    "substrate": 2,
    "taxon": 3,
    "function": 2,
    "metabolite": 2,
    "host": 1,
    "phenotype": 1,
}
"""Nodos por tipo: `MINIMAL_NODE_COUNTS`."""

EXPECTED_EDGES: dict[tuple[str, str, str], int] = {
    ("diet", "provides", "substrate"): 2,  # 1 x 2
    ("additive", "modulates", "taxon"): 3,  # 1 x 3 (el aditivo no es de control)
    ("additive", "modulates", "function"): 2,  # 1 x 2
    ("substrate", "available_to", "taxon"): 6,  # 2 x 3
    ("taxon", "has_capacity", "function"): 6,  # 3 x 2
    ("taxon", "interacts_with", "taxon"): 6,  # 3 x 2 pares ordenados, sin bucles
    ("function", "produces", "metabolite"): 4,  # 2 x 2
    ("function", "cross_feeds", "function"): 2,  # 2 x 1 pares ordenados, sin bucles
    ("metabolite", "measured_in", "host"): 2,  # 2 x 1
    ("metabolite", "associated_with", "phenotype"): 2,  # 2 x 1
    ("host", "exhibits", "phenotype"): 1,  # 1 x 1
}
"""Aristas por relación: con probabilidad 1 se conecta todo par candidato."""

EXPECTED_X_WIDTH: dict[str, int] = {
    "diet": 6,  # un componente de la composición por columna
    "additive": 1,  # dose (CFU/kg)
    "substrate": 1,  # quantity (g/kg)
    "taxon": 1,  # abundance (relative_abundance)
    "function": 1,  # annotation_value:abundance (CPM)
    "metabolite": 0,  # la concentración es el target
    "host": 2,  # covariates.age_days (d), covariates.body_weight_g (g)
    "phenotype": 0,  # resultado observado, no es una entrada
}
"""Columnas de `x` por tipo según la codificación `prototype-0.1`."""

EXPECTED_EDGE_ATTR_WIDTH: dict[tuple[str, str, str], int] = {
    ("diet", "provides", "substrate"): 1,  # proportion (g/kg)
}
"""Columnas de `edge_attr`; las relaciones ausentes tienen cero columnas."""

TARGET_TYPE = "metabolite"


@pytest.fixture
def minimal_build(minimal_synthetic_dataset: SyntheticDataset) -> PrototypeGraphs:
    return build_synthetic_graphs(minimal_synthetic_dataset)


@pytest.fixture
def minimal_graph(minimal_build: PrototypeGraphs) -> Any:
    return minimal_build.graphs[GRAPH_ID]


def _float_tensors(data: Any) -> list[tuple[str, Any]]:
    """Todos los tensores de punto flotante de un `HeteroData`, con su ubicación."""
    found = []
    for store in [*data.node_stores, *data.edge_stores]:
        for name, value in store.items():
            if isinstance(value, torch.Tensor) and value.is_floating_point():
                found.append((f"{store._key}.{name}", value))
    return found


def _assert_finite(data: Any) -> None:
    tensors = _float_tensors(data)
    assert tensors, "el grafo no tiene tensores de punto flotante"
    for where, tensor in tensors:
        assert not torch.isnan(tensor).any(), f"{where} contiene NaN"
        assert torch.isfinite(tensor).all(), f"{where} contiene valores no finitos"


# ---------------------------------------------------------------------------
# Construcción
# ---------------------------------------------------------------------------


def test_minimal_dataset_builds_one_graph_without_findings(minimal_build: PrototypeGraphs) -> None:
    assert list(minimal_build.graphs) == [GRAPH_ID]
    assert minimal_build.report.findings == ()
    assert minimal_build.graphs[GRAPH_ID].validate(raise_on_error=False) is True


# ---------------------------------------------------------------------------
# Número de nodos y aristas por tipo
# ---------------------------------------------------------------------------


def test_node_count_per_type(minimal_graph: Any) -> None:
    counts = {node_type: store.num_nodes for node_type, store in minimal_graph.node_items()}

    assert counts == EXPECTED_NODES
    for node_type, store in minimal_graph.node_items():
        assert len(store.node_id) == EXPECTED_NODES[node_type]
        assert len(set(store.node_id)) == EXPECTED_NODES[node_type]


def test_edge_count_per_type(minimal_graph: Any) -> None:
    counts = {
        edge_type: int(store.edge_index.size(1)) for edge_type, store in minimal_graph.edge_items()
    }

    assert counts == EXPECTED_EDGES
    for _, store in minimal_graph.edge_items():
        edges = int(store.edge_index.size(1))
        assert len(store.evidence_id) == edges
        assert len(store.raw_attributes) == edges


# ---------------------------------------------------------------------------
# Dimensiones de atributos
# ---------------------------------------------------------------------------


def test_node_feature_dimensions(minimal_graph: Any, minimal_build: PrototypeGraphs) -> None:
    schema = minimal_build.dataset.metadata["node_feature_schema"]

    for node_type, store in minimal_graph.node_items():
        expected = (EXPECTED_NODES[node_type], EXPECTED_X_WIDTH[node_type])
        assert tuple(store.x.shape) == expected, node_type
        assert store.x.dtype == torch.float32
        assert tuple(store.missing_mask.shape) == expected, node_type
        assert store.missing_mask.dtype == torch.bool
        assert len(schema[node_type]) == EXPECTED_X_WIDTH[node_type]


def test_edge_index_and_attribute_dimensions(minimal_graph: Any) -> None:
    for edge_type, store in minimal_graph.edge_items():
        edges = EXPECTED_EDGES[edge_type]
        source_type, _, target_type = edge_type
        assert tuple(store.edge_index.shape) == (2, edges)
        assert store.edge_index.dtype == torch.long
        assert int(store.edge_index.min()) >= 0
        assert int(store.edge_index[0].max()) < EXPECTED_NODES[source_type]
        assert int(store.edge_index[1].max()) < EXPECTED_NODES[target_type]
        width = EXPECTED_EDGE_ATTR_WIDTH.get(edge_type, 0)
        assert tuple(store.edge_attr.shape) == (edges, width), edge_type
        assert store.edge_attr.dtype == torch.float32


def test_target_dimensions(minimal_graph: Any) -> None:
    for node_type, store in minimal_graph.node_items():
        if node_type != TARGET_TYPE:
            assert "y" not in store
            continue
        assert tuple(store.y.shape) == (EXPECTED_NODES[TARGET_TYPE], 1)
        assert store.y.dtype == torch.float32
        assert tuple(store.y_mask.shape) == (EXPECTED_NODES[TARGET_TYPE], 1)
        assert bool(store.y_mask.all()) is True


# ---------------------------------------------------------------------------
# Ausencia de NaN
# ---------------------------------------------------------------------------


def test_minimal_graph_has_no_nan(minimal_graph: Any) -> None:
    _assert_finite(minimal_graph)


def test_missing_values_are_encoded_without_nan(
    minimal_synthetic_dataset: SyntheticDataset,
) -> None:
    taxon = min(
        (node for node in minimal_synthetic_dataset.nodes if node.node_type == "taxon"),
        key=lambda node: node.node_id,
    )
    missing = replace(
        taxon,
        attributes={**taxon.attributes, "abundance": None},
        missing_mask={"abundance": True},
    )
    dataset = replace(
        minimal_synthetic_dataset,
        nodes=[missing if node is taxon else node for node in minimal_synthetic_dataset.nodes],
    )

    data = build_synthetic_graphs(dataset).graphs[GRAPH_ID]

    _assert_finite(data)
    assert data["taxon"].x[0, 0].item() == 0.0
    assert data["taxon"].missing_mask.tolist() == [[True], [False], [False]]


@pytest.mark.parametrize(
    "dataset",
    [generate_scenario_dataset(), generate_synthetic_dataset()],
    ids=["scenarios", "default"],
)
def test_reference_datasets_have_no_nan(dataset: SyntheticDataset) -> None:
    build = build_synthetic_graphs(dataset)

    assert set(build.graphs) == {instance.graph_id for instance in dataset.instances}
    for data in build.graphs.values():
        _assert_finite(data)


# ---------------------------------------------------------------------------
# Flujo completo: JSONL -> HeteroData -> .pt
# ---------------------------------------------------------------------------


def test_exported_flow_preserves_counts_dimensions_and_values(
    minimal_synthetic_dataset: SyntheticDataset, tmp_path: Path
) -> None:
    export_dataset(minimal_synthetic_dataset, tmp_path / "dataset")
    build = build_synthetic_graphs(load_dataset(tmp_path / "dataset"))
    save_graphs(build.graphs, tmp_path / "graphs")

    loaded = load_graphs(tmp_path / "graphs")[GRAPH_ID]

    expected = build_synthetic_graphs(minimal_synthetic_dataset).graphs[GRAPH_ID]
    assert {t: s.num_nodes for t, s in loaded.node_items()} == EXPECTED_NODES
    assert {t: int(s.edge_index.size(1)) for t, s in loaded.edge_items()} == EXPECTED_EDGES
    for node_type, store in loaded.node_items():
        assert torch.equal(store.x, expected[node_type].x)
        assert torch.equal(store.missing_mask, expected[node_type].missing_mask)
    for edge_type, store in loaded.edge_items():
        assert torch.equal(store.edge_index, expected[edge_type].edge_index)
        assert torch.equal(store.edge_attr, expected[edge_type].edge_attr)
    assert torch.equal(loaded[TARGET_TYPE].y, expected[TARGET_TYPE].y)
    _assert_finite(loaded)
