"""Pruebas de las estadísticas descriptivas y el subgrafo de muestra (A35-4, #31).

Usan grafos pequeños construidos a mano, con valores calculables de antemano, y grafos sin
`node_id` ni features para comprobar que la herramienta sirve con cualquier `HeteroData`.

Requieren el extra `graph`.
"""

from __future__ import annotations

import json

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from torch_geometric.data import HeteroData  # noqa: E402

from nutrigraphdt.graph.stats import (  # noqa: E402
    compute_stats,
    format_stats,
    resolve_node,
    sample_subgraph,
    to_mermaid,
)


def _graph() -> HeteroData:
    """3 taxones, 2 metabolitos y 1 huésped aislado; componentes {t0,t1,m0}, {t2,m1}, {h0}."""
    data = HeteroData()
    data["taxon"].x = torch.zeros((3, 1))
    data["taxon"].node_id = ["t:0", "t:1", "t:2"]
    data["metabolite"].x = torch.zeros((2, 0))
    data["metabolite"].node_id = ["m:0", "m:1"]
    data["host"].num_nodes = 1
    data["taxon", "produces", "metabolite"].edge_index = torch.tensor([[0, 1, 2], [0, 0, 1]])
    data["taxon", "interacts_with", "taxon"].edge_index = torch.tensor([[0], [1]])
    data.graph_id = "test:graph"
    return data


def test_counts_degree_and_components() -> None:
    stats = compute_stats(_graph())

    assert stats.graph_id == "test:graph"
    assert stats.nodes == {"taxon": 3, "metabolite": 2, "host": 1}
    assert stats.edges == {
        ("taxon", "produces", "metabolite"): 3,
        ("taxon", "interacts_with", "taxon"): 1,
    }
    assert (stats.num_nodes, stats.num_edges) == (6, 4)
    assert stats.mean_degree == pytest.approx(8 / 6)
    # taxon: t0=2, t1=2, t2=1; metabolite: m0=2, m1=1; host aislado.
    assert stats.mean_degree_by_type == pytest.approx(
        {"taxon": 5 / 3, "metabolite": 3 / 2, "host": 0.0}
    )
    assert (stats.num_components, stats.largest_component, stats.isolated_nodes) == (3, 3, 1)


def test_to_dict_is_json_serializable_and_text_summary_lists_types() -> None:
    stats = compute_stats(_graph())

    encoded = json.loads(json.dumps(stats.to_dict(), allow_nan=False))
    lines = "\n".join(format_stats(stats))

    assert encoded["edges"] == {"taxon|produces|metabolite": 3, "taxon|interacts_with|taxon": 1}
    assert encoded["num_components"] == 3
    assert "host: 1 (0.000)" in lines
    assert "taxon|produces|metabolite: 3" in lines


def test_graph_without_ids_edges_or_nodes() -> None:
    data = HeteroData()
    data["a"].num_nodes = 2
    stats = compute_stats(data)
    assert (stats.graph_id, stats.num_edges, stats.mean_degree) == (None, 0, 0.0)
    assert (stats.num_components, stats.isolated_nodes) == (2, 2)

    empty = compute_stats(HeteroData())
    assert (empty.num_nodes, empty.mean_degree, empty.largest_component) == (0, 0.0, 0)


@pytest.mark.parametrize(
    ("edge_index", "message"),
    [
        (torch.tensor([[0, 3], [0, 0]]), "fuera de los 3 nodos de taxon"),
        (torch.tensor([[-1], [0]]), "fuera de los 3 nodos de taxon"),
        (torch.tensor([0, 1]), r"forma \[2, E\]"),
    ],
)
def test_inconsistent_edge_index_is_rejected(edge_index: object, message: str) -> None:
    data = _graph()
    data["taxon", "produces", "metabolite"].edge_index = edge_index

    with pytest.raises(ValueError, match=message):
        compute_stats(data)


def test_relation_to_missing_node_type_is_rejected() -> None:
    data = _graph()
    data["taxon", "feeds", "ghost"].edge_index = torch.tensor([[0], [0]])

    with pytest.raises(ValueError, match="'ghost'"):
        compute_stats(data)


def test_sample_starts_at_highest_degree_node_and_keeps_internal_edges() -> None:
    subgraph = sample_subgraph(_graph(), hops=1)

    # t0, t1 y m0 empatan con grado 2; gana t0 por orden de tipo y fila.
    assert subgraph.seed == ("taxon", 0)
    assert subgraph.nodes == (("taxon", 0), ("taxon", 1), ("metabolite", 0))
    assert set(subgraph.edges) == {
        (("taxon", 0), "produces", ("metabolite", 0)),
        (("taxon", 1), "produces", ("metabolite", 0)),
        (("taxon", 0), "interacts_with", ("taxon", 1)),
    }


def test_sample_respects_hops_max_nodes_and_is_deterministic() -> None:
    data = _graph()

    assert sample_subgraph(data, seed=("taxon", 2), hops=0).nodes == (("taxon", 2),)
    assert len(sample_subgraph(data, hops=5, max_nodes=2).nodes) == 2
    assert sample_subgraph(data, hops=2) == sample_subgraph(data, hops=2)
    with pytest.raises(ValueError, match="no existe"):
        sample_subgraph(data, seed=("taxon", 9))
    with pytest.raises(ValueError, match="max_nodes"):
        sample_subgraph(data, max_nodes=0)
    with pytest.raises(ValueError, match="no tiene nodos"):
        sample_subgraph(HeteroData())


def test_resolve_node_by_id_or_row() -> None:
    data = _graph()
    data["taxon"].node_id = ["synthetic:taxon:0001", "x", "y"]

    assert resolve_node(data, "taxon:synthetic:taxon:0001") == ("taxon", 0)
    assert resolve_node(data, "host:0") == ("host", 0)
    with pytest.raises(ValueError, match="tipo:id"):
        resolve_node(data, "ghost:0")
    with pytest.raises(ValueError, match="No existe"):
        resolve_node(data, "host:1")


def test_mermaid_declares_nodes_edges_and_one_class_per_type() -> None:
    data = _graph()
    data["taxon"].node_id = ['t"0', "t:1", "t:2"]

    diagram = to_mermaid(data, sample_subgraph(data, hops=1))

    assert diagram.startswith("flowchart LR\n")
    assert 'n0["taxon<br/>t#quot;0"]' in diagram
    assert "n0 -->|interacts_with| n1" in diagram
    assert "class n0,n1 type0" in diagram
    assert "class n2 type1" in diagram
    assert "type2" not in diagram  # host no está en la muestra


def test_mermaid_without_node_ids_uses_row_numbers() -> None:
    data = HeteroData()
    data["a"].num_nodes = 2
    data["a", "to", "a"].edge_index = torch.tensor([[0], [1]])

    diagram = to_mermaid(data, sample_subgraph(data))

    assert 'n0["a<br/>#0"]' in diagram and "n0 -->|to| n1" in diagram
