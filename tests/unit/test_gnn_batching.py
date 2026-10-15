"""Tests de `align_graph_types`: lotes de grafos con tipos de arista distintos (#119).

Requiere el extra `graph`.
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from torch_geometric.data import HeteroData  # noqa: E402
from torch_geometric.loader import DataLoader  # noqa: E402

from nutrigraphdt.data.split import create_split  # noqa: E402
from nutrigraphdt.graph.heterodata import build_synthetic_graphs  # noqa: E402
from nutrigraphdt.models.baselines import build_synthetic_cohort  # noqa: E402
from nutrigraphdt.models.gnn import (  # noqa: E402
    MODEL_VARIANTS,
    GraphMetadata,
    align_graph_types,
    build_model,
    parse_model_config,
)
from nutrigraphdt.models.gnn.sanity import prepare_overfit_batch  # noqa: E402
from nutrigraphdt.models.training import prepare_training_graphs  # noqa: E402

MODULATES = ("additive", "modulates", "taxon")
HAS_CAPACITY = ("taxon", "has_capacity", "function")


def _graph(with_modulates: bool) -> HeteroData:
    graph = HeteroData()
    graph["additive"].x = torch.ones(1, 2)
    graph["additive"].node_id = ["additive:0"]
    graph["taxon"].x = torch.ones(3, 2)
    graph["taxon"].node_id = ["taxon:0", "taxon:1", "taxon:2"]
    graph["function"].x = torch.ones(2, 1)
    graph[HAS_CAPACITY].edge_index = torch.tensor([[0, 2], [1, 0]])
    if with_modulates:
        graph[MODULATES].edge_index = torch.tensor([[0], [2]])
        graph[MODULATES].edge_attr = torch.ones(1, 4)
        graph[MODULATES].evidence_id = ["e:0"]
    return graph


def test_batch_without_alignment_would_reassign_edges() -> None:
    """Documenta el comportamiento de PyG que motiva la alineación."""
    graphs = [_graph(True), _graph(False), _graph(True)]
    batch = next(iter(DataLoader(graphs, batch_size=3)))
    source = batch["additive"].batch[batch[MODULATES].edge_index[0]]

    assert source.tolist() != [0, 2]


def test_aligned_batch_keeps_each_edge_in_its_graph() -> None:
    graphs = align_graph_types([_graph(True), _graph(False), _graph(True)])
    batch = next(iter(DataLoader(graphs, batch_size=3)))
    edge_index = batch[MODULATES].edge_index

    assert batch["additive"].batch[edge_index[0]].tolist() == [0, 2]
    assert batch["taxon"].batch[edge_index[1]].tolist() == [0, 2]
    assert batch[MODULATES].edge_attr.shape == (2, 4)


def test_missing_types_are_added_empty_with_the_same_attributes() -> None:
    first = _graph(True)
    second = _graph(False)
    second["host"].x = torch.ones(1, 3)
    second["host"].missing_mask = torch.zeros(1, 3, dtype=torch.bool)

    aligned_first, aligned_second = align_graph_types([first, second])

    assert aligned_second[MODULATES].edge_index.shape == (2, 0)
    assert aligned_second[MODULATES].edge_index.dtype == torch.long
    assert aligned_second[MODULATES].edge_attr.shape == (0, 4)
    assert aligned_second[MODULATES].evidence_id == []
    assert aligned_first["host"].x.shape == (0, 3)
    assert aligned_first["host"].missing_mask.dtype == torch.bool
    assert aligned_first["host"].num_nodes == 0
    assert set(aligned_first.edge_types) == set(aligned_second.edge_types)


def test_does_not_modify_the_input_unless_inplace() -> None:
    graphs = [_graph(True), _graph(False)]

    align_graph_types(graphs)
    assert MODULATES not in graphs[1].edge_types

    align_graph_types(graphs, inplace=True)
    assert MODULATES in graphs[1].edge_types


@pytest.fixture(scope="module")
def synthetic_val() -> list[HeteroData]:
    """Grafos de `val` de una cohorte sintética: no todos tienen las mismas relaciones."""
    cohort = build_synthetic_cohort(16, first_seed=1)
    split = create_split(
        [
            {"sample_id": inst.sample_id, "diet_treatment": inst.diet_treatment}
            for inst in cohort.instances
        ],
        group_key=None,
        stratify_key="diet_treatment",
        seed=42,
    )
    built = build_synthetic_graphs(cohort)
    prepared = prepare_training_graphs(built.dataset, built.graphs, split, batch_size=4)
    return list(prepared.graphs["val"])


def test_prepared_graphs_share_every_edge_type(synthetic_val: list[HeteroData]) -> None:
    edge_types = {tuple(sorted(graph.edge_types)) for graph in synthetic_val}

    assert len(edge_types) == 1


@pytest.mark.parametrize("variant", MODEL_VARIANTS)
def test_batched_prediction_equals_graph_by_graph(
    synthetic_val: list[HeteroData], variant: str
) -> None:
    torch.manual_seed(0)
    config = parse_model_config({"variant": variant, "hidden_channels": 16, "dropout": 0.0})
    model = build_model(config, GraphMetadata.from_graphs(synthetic_val))
    model.eval()
    with torch.no_grad():
        batched = model(next(iter(DataLoader(synthetic_val, batch_size=len(synthetic_val)))))
        single = torch.cat([model(graph) for graph in synthetic_val])

    assert torch.allclose(batched, single, atol=1e-5)


def test_overfit_batch_is_aligned() -> None:
    graphs = [_with_target(_graph(True), "g:0"), _with_target(_graph(False), "g:1")]
    data = prepare_overfit_batch(graphs)

    edge_index = data.batch[MODULATES].edge_index
    assert data.batch["additive"].batch[edge_index[0]].tolist() == [0]


def _with_target(graph: HeteroData, graph_id: str) -> HeteroData:
    graph.graph_id = graph_id
    graph.y_graph = torch.ones(1, 3)
    graph.y_graph_mask = torch.ones(1, 3, dtype=torch.bool)
    for node_type in graph.node_types:
        graph[node_type].missing_mask = torch.zeros_like(graph[node_type].x, dtype=torch.bool)
    return graph
