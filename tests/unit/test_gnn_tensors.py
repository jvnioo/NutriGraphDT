"""Tests tensoriales comunes para las tres variantes GNN. Requiere el extra `graph`."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from torch_geometric.data import HeteroData  # noqa: E402
from torch_geometric.loader import DataLoader  # noqa: E402

from nutrigraphdt.data.synthetic import generate_scenario_dataset  # noqa: E402
from nutrigraphdt.graph.builder import add_reverse_edges  # noqa: E402
from nutrigraphdt.graph.heterodata import build_synthetic_graphs  # noqa: E402
from nutrigraphdt.models.gnn import (  # noqa: E402
    EXCLUDED_FROM_READOUT,
    GraphMetadata,
    HeteroGAT,
    HeteroSAGE,
    HomoSAGE,
    ModelConfig,
    SCFAGraphModel,
    add_graph_target,
    initialize_lazy_parameters,
    masked_mse_loss,
)

ModelFactory: TypeAlias = Callable[[GraphMetadata, ModelConfig], SCFAGraphModel]
CONFIG = ModelConfig(hidden_channels=8, num_layers=2, dropout=0.0)
VARIANTS = ("homo_sage", "hetero_sage", "hetero_gat")
MISSING_RELATION = ("substrate", "available_to", "taxon")
# Cota holgada para un modelo recién inicializado con features estandarizadas; detecta escalas
# como las de las features crudas (salidas en 1e7-1e8).
MAX_ABS_INITIAL_OUTPUT = 1e3


def _make_model(
    variant: str,
    metadata: GraphMetadata,
    *,
    seed: int = 42,
    config: ModelConfig = CONFIG,
) -> SCFAGraphModel:
    factories: dict[str, ModelFactory] = {
        "homo_sage": HomoSAGE,
        "hetero_sage": HeteroSAGE,
        "hetero_gat": HeteroGAT,
    }
    torch.manual_seed(seed)
    model = factories[variant](metadata, config).cpu()
    initialize_lazy_parameters(model)
    return model


def _standardize_features(graphs: list[HeteroData]) -> None:
    """Estandariza `x` por tipo y columna con las celdas observadas de todos los grafos.

    `prototype-0.1` entrega features crudas (`additive` llega a 1e9) y el escalado real es de
    A44-2 (#96). Sin esto, la salida queda en 1e7-1e8 y los tests no reflejan el régimen de
    entrenamiento. Las celdas faltantes conservan su valor.
    """
    node_types = sorted({node_type for graph in graphs for node_type in graph.node_types})
    for node_type in node_types:
        stores = [graph[node_type] for graph in graphs if "x" in graph[node_type]]
        if not stores or stores[0].x.size(1) == 0:
            continue
        x = torch.cat([store.x for store in stores])
        observed = ~torch.cat([store.missing_mask for store in stores])
        count = observed.sum(dim=0).clamp(min=1)
        mean = torch.where(observed, x, 0.0).sum(dim=0) / count
        variance = (torch.where(observed, x - mean, 0.0) ** 2).sum(dim=0) / count
        std = torch.where(variance > 0, variance.sqrt(), torch.ones_like(variance))
        for store in stores:
            store.x = torch.where(store.missing_mask, store.x, (store.x - mean) / std)


@pytest.fixture(scope="module")
def synthetic_graphs() -> list[HeteroData]:
    """Grafos sintéticos con aristas inversas, targets por grafo y features estandarizadas."""
    graphs = build_synthetic_graphs(generate_scenario_dataset()).graphs
    prepared = [
        add_graph_target(add_reverse_edges(graphs[graph_id])) for graph_id in sorted(graphs)
    ]
    _standardize_features(prepared)
    return prepared


@pytest.fixture(params=("complete", "missing_relation"))
def synthetic_batch(
    request: pytest.FixtureRequest, synthetic_graphs: list[HeteroData]
) -> HeteroData:
    """Lote completo, o sin una relación de la metadata (el modelo la declara, el lote no)."""
    graphs = list(synthetic_graphs)
    if request.param == "missing_relation":
        reduced = graphs[0].clone()
        del reduced[MISSING_RELATION]
        graphs[0] = reduced
    return next(iter(DataLoader(graphs, batch_size=len(graphs))))


@pytest.fixture
def controlled_graph(synthetic_graphs: list[HeteroData]) -> tuple[GraphMetadata, HeteroData]:
    """Grafo sintético denso con features para todos los tipos, solo para probar gradientes."""
    synthetic_metadata = GraphMetadata.from_graphs(synthetic_graphs)
    metadata = GraphMetadata(
        node_channels={node_type: 3 for node_type in synthetic_metadata.node_types},
        edge_types=synthetic_metadata.edge_types,
    )
    graph = HeteroData()
    generator = torch.Generator(device="cpu").manual_seed(8216)
    nodes_per_type = 3
    for node_type in metadata.node_types:
        graph[node_type].x = torch.randn((nodes_per_type, 3), generator=generator)
        graph[node_type].missing_mask = torch.zeros((nodes_per_type, 3), dtype=torch.bool)
    for source, relation, target in metadata.edge_types:
        source_count = graph[source].num_nodes
        target_count = graph[target].num_nodes
        graph[(source, relation, target)].edge_index = torch.stack(
            [
                torch.arange(source_count).repeat_interleave(target_count),
                torch.arange(target_count).repeat(source_count),
            ]
        )
    graph.y_graph = torch.tensor([[0.25, -0.5, 0.75]], dtype=torch.float32)
    graph.y_graph_mask = torch.ones((1, 3), dtype=torch.bool)
    return metadata, graph


@pytest.mark.parametrize("variant", VARIANTS, ids=VARIANTS)
def test_batch_output_has_one_three_target_row_per_graph(
    variant: str, synthetic_batch: HeteroData, synthetic_graphs: list[HeteroData]
) -> None:
    metadata = GraphMetadata.from_graphs(synthetic_graphs)
    model = _make_model(variant, metadata)

    output = model(synthetic_batch)

    assert tuple(output.shape) == (synthetic_batch.num_graphs, 3)


@pytest.mark.parametrize("variant", VARIANTS, ids=VARIANTS)
def test_prediction_and_masked_loss_are_finite(
    variant: str, synthetic_batch: HeteroData, synthetic_graphs: list[HeteroData]
) -> None:
    metadata = GraphMetadata.from_graphs(synthetic_graphs)
    model = _make_model(variant, metadata)

    output = model(synthetic_batch)
    loss = masked_mse_loss(output, synthetic_batch.y_graph, synthetic_batch.y_graph_mask)

    assert torch.isfinite(output).all()
    assert float(output.abs().max()) < MAX_ABS_INITIAL_OUTPUT
    assert bool(synthetic_batch.y_graph_mask.any())
    assert torch.isfinite(loss)


@pytest.mark.parametrize("variant", VARIANTS, ids=VARIANTS)
def test_cpu_initialization_and_eval_forward_are_deterministic(
    variant: str, synthetic_batch: HeteroData, synthetic_graphs: list[HeteroData]
) -> None:
    metadata = GraphMetadata.from_graphs(synthetic_graphs)
    first_model = _make_model(variant, metadata, seed=8216).eval()
    second_model = _make_model(variant, metadata, seed=8216).eval()

    with torch.no_grad():
        first_output = first_model(synthetic_batch)
        second_output = second_model(synthetic_batch)
        repeated_output = first_model(synthetic_batch)

    assert torch.equal(first_output, second_output)
    assert torch.equal(first_output, repeated_output)


@pytest.mark.parametrize("variant", VARIANTS, ids=VARIANTS)
def test_controlled_graph_gives_every_parameter_a_gradient(
    variant: str, controlled_graph: tuple[GraphMetadata, HeteroData]
) -> None:
    """Con todas las relaciones y destinos con varios vecinos, ningún parámetro queda sin
    gradiente: las convoluciones que no afectarían la predicción no se crean (#111)."""
    metadata, graph = controlled_graph
    model = _make_model(variant, metadata)
    model.train()
    loss = masked_mse_loss(model(graph), graph.y_graph, graph.y_graph_mask)
    loss.backward()

    without_gradient = [
        name
        for name, parameter in model.named_parameters()
        if parameter.grad is None or not bool(torch.count_nonzero(parameter.grad))
    ]

    assert without_gradient == []
    if isinstance(model, (HeteroSAGE, HeteroGAT)):
        final_destinations = {edge_type[2] for edge_type in model.convs[-1].convs}
        assert final_destinations.isdisjoint(EXCLUDED_FROM_READOUT)
