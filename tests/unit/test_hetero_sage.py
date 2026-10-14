"""Tests de `hetero_sage` (A41-3, #79). Requiere el extra `graph`."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from torch import nn  # noqa: E402
from torch.nn.parameter import UninitializedParameter  # noqa: E402
from torch_geometric.data import HeteroData  # noqa: E402
from torch_geometric.loader import DataLoader  # noqa: E402
from torch_geometric.nn import HeteroConv, SAGEConv  # noqa: E402

from nutrigraphdt.data.config import load_sources  # noqa: E402
from nutrigraphdt.data.integration import attach_sample_context  # noqa: E402
from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader  # noqa: E402
from nutrigraphdt.data.pipeline import DataPipeline  # noqa: E402
from nutrigraphdt.data.synthetic import generate_scenario_dataset  # noqa: E402
from nutrigraphdt.graph.builder import add_reverse_edges, build_hetero_graph  # noqa: E402
from nutrigraphdt.graph.heterodata import build_synthetic_graphs  # noqa: E402
from nutrigraphdt.models.gnn import (  # noqa: E402
    HETERO_RELATION_AGGREGATIONS,
    GraphMetadata,
    HeteroSAGE,
    ModelConfig,
    add_graph_target,
    initialize_lazy_parameters,
    masked_mse_loss,
)
from nutrigraphdt.models.gnn.base import layer_edge_types  # noqa: E402
from nutrigraphdt.models.gnn.components import EXCLUDED_FROM_READOUT  # noqa: E402
from nutrigraphdt.models.gnn.homo_sage import SAGE_AGGREGATIONS  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "holofood"
CONFIG = ModelConfig(hidden_channels=8, num_layers=2, dropout=0.0)


@pytest.fixture(scope="module")
def synthetic_graphs() -> list[HeteroData]:
    """Grafos sintéticos con las once tripletas, con inversas y target por grafo."""
    graphs = build_synthetic_graphs(generate_scenario_dataset()).graphs
    return [add_graph_target(add_reverse_edges(graphs[gid])) for gid in sorted(graphs)]


@pytest.fixture(scope="module")
def d1_graphs() -> list[HeteroData]:
    """Grafos D1 del fixture de HoloFood, con relaciones inversas y target."""
    sources = load_sources(REPO_ROOT / "configs" / "sources.json")

    def source(source_id: str, file_name: str):  # type: ignore[no-untyped-def]
        return dataclasses.replace(sources[source_id], path_or_url=str(FIXTURES / file_name))

    abundance = source("D1_holofood", "abundance_ssu_caecum.tsv")
    tables = DataPipeline({"D1_holofood": abundance}).run(["D1_holofood"]).dataset
    tables, _ = attach_sample_context(
        tables,
        metadata=MetadataLoader(source("D1_holofood_metadata", "metadata.tsv")).load(),
        metabolites=MetaboliteLoader(
            source("D1_holofood_scfa_content", "scfa_caecum_content.tsv")
        ).load(),
    )
    graphs = build_hetero_graph(tables).graphs
    return [add_graph_target(add_reverse_edges(graphs[gid])) for gid in sorted(graphs)]


def _metadata(graphs: list[HeteroData]) -> GraphMetadata:
    return GraphMetadata.from_graphs(graphs)


def _model(graphs: list[HeteroData], **kwargs: str) -> HeteroSAGE:
    torch.manual_seed(42)
    model = HeteroSAGE(_metadata(graphs), CONFIG, **kwargs)
    initialize_lazy_parameters(model)
    model.eval()
    return model


def _batch(graphs: list[HeteroData]) -> HeteroData:
    batch: HeteroData = next(iter(DataLoader(graphs, batch_size=len(graphs))))
    return batch


def _relation_modules(
    layer: HeteroConv, edge_types: tuple[tuple[str, str, str], ...]
) -> list[tuple[tuple[str, str, str], nn.Module]]:
    modules = list(layer.convs.values())
    assert len(modules) == len(edge_types)
    return list(zip(edge_types, modules, strict=True))


class TestForward:
    def test_synthetic_batch_shape_without_nan(self, synthetic_graphs: list[HeteroData]) -> None:
        output = _model(synthetic_graphs)(_batch(synthetic_graphs))
        assert output.dtype == torch.float32
        assert tuple(output.shape) == (len(synthetic_graphs), 3)
        assert torch.isfinite(output).all()

    def test_single_graph(self, synthetic_graphs: list[HeteroData]) -> None:
        output = _model(synthetic_graphs)(synthetic_graphs[0])
        assert tuple(output.shape) == (1, 3)
        assert torch.isfinite(output).all()

    def test_d1_batch(self, d1_graphs: list[HeteroData]) -> None:
        output = _model(d1_graphs)(_batch(d1_graphs))
        assert tuple(output.shape) == (len(d1_graphs), 3)
        assert torch.isfinite(output).all()

    def test_one_sage_convolution_per_metadata_relation(
        self, synthetic_graphs: list[HeteroData]
    ) -> None:
        model = _model(synthetic_graphs)
        metadata = model.metadata
        assert len(metadata.edge_types) == 22
        per_layer = layer_edge_types(metadata, CONFIG.num_layers)
        assert per_layer[0] == metadata.edge_types
        for layer, edge_types in zip(model.convs, per_layer, strict=True):
            assert isinstance(layer, HeteroConv)
            assert layer.aggr == "sum"
            relations = _relation_modules(layer, edge_types)
            assert all(isinstance(module, SAGEConv) for _, module in relations)
            assert all(module.aggr == "mean" for _, module in relations)

    def test_final_layer_has_no_convolution_toward_excluded_destinations(
        self, synthetic_graphs: list[HeteroData]
    ) -> None:
        model = _model(synthetic_graphs)
        final_edge_types = layer_edge_types(model.metadata, CONFIG.num_layers)[-1]
        expected = tuple(
            edge_type
            for edge_type in model.metadata.edge_types
            if edge_type[2] not in EXCLUDED_FROM_READOUT
        )
        assert final_edge_types == expected
        assert len(expected) < len(model.metadata.edge_types)
        _relation_modules(model.convs[-1], final_edge_types)

    @pytest.mark.parametrize("aggr", sorted(SAGE_AGGREGATIONS))
    def test_neighbor_aggregations(self, aggr: str, synthetic_graphs: list[HeteroData]) -> None:
        model = _model(synthetic_graphs, aggr=aggr)
        output = model(_batch(synthetic_graphs))
        assert torch.isfinite(output).all()
        assert all(module.aggr == aggr for layer in model.convs for module in layer.convs.values())

    @pytest.mark.parametrize("relation_aggr", sorted(HETERO_RELATION_AGGREGATIONS))
    def test_relation_aggregations(
        self, relation_aggr: str, synthetic_graphs: list[HeteroData]
    ) -> None:
        model = _model(synthetic_graphs, relation_aggr=relation_aggr)
        output = model(_batch(synthetic_graphs))
        assert torch.isfinite(output).all()
        assert all(layer.aggr == relation_aggr for layer in model.convs)

    def test_invalid_aggregations(self, synthetic_graphs: list[HeteroData]) -> None:
        metadata = _metadata(synthetic_graphs)
        with pytest.raises(ValueError, match="aggr"):
            HeteroSAGE(metadata, CONFIG, aggr="median")
        with pytest.raises(ValueError, match="relation_aggr"):
            HeteroSAGE(metadata, CONFIG, relation_aggr="cat")


class TestLazyInitialization:
    @pytest.mark.parametrize("training", [True, False])
    def test_initializes_full_metadata_for_sparse_d1_batch_and_preserves_mode(
        self,
        training: bool,
        d1_graphs: list[HeteroData],
        synthetic_graphs: list[HeteroData],
    ) -> None:
        d1_metadata = _metadata(d1_graphs)
        schema_metadata = _metadata(synthetic_graphs)
        assert len(d1_metadata.edge_types) == 2
        assert len(schema_metadata.edge_types) == 22
        metadata = GraphMetadata(
            {**schema_metadata.node_channels, **d1_metadata.node_channels},
            schema_metadata.edge_types,
        )
        model = HeteroSAGE(metadata, CONFIG)
        model.train(training)

        initialize_lazy_parameters(model)

        assert model.training is training
        assert not any(
            isinstance(parameter, UninitializedParameter) for parameter in model.parameters()
        )
        output = model(_batch(d1_graphs))
        assert tuple(output.shape) == (len(d1_graphs), 3)
        assert torch.isfinite(output).all()


class TestTraining:
    def test_every_relation_receives_gradient_in_first_layer(
        self, synthetic_graphs: list[HeteroData]
    ) -> None:
        model = _model(synthetic_graphs)
        model.train()
        batch = _batch(synthetic_graphs)
        masked_mse_loss(model(batch), batch.y_graph, batch.y_graph_mask).backward()

        relations = _relation_modules(model.convs[0], model.metadata.edge_types)
        assert len(relations) == 22
        for edge_type, module in relations:
            gradients = [parameter.grad for parameter in module.parameters()]
            assert all(gradient is not None for gradient in gradients), edge_type
            assert (
                sum(float(gradient.abs().sum()) for gradient in gradients if gradient is not None)
                > 0
            ), edge_type

    def test_every_final_layer_relation_receives_gradient(
        self, synthetic_graphs: list[HeteroData]
    ) -> None:
        model = _model(synthetic_graphs)
        model.train()
        batch = _batch(synthetic_graphs)
        masked_mse_loss(model(batch), batch.y_graph, batch.y_graph_mask).backward()

        final_edge_types = layer_edge_types(model.metadata, CONFIG.num_layers)[-1]
        for edge_type, module in _relation_modules(model.convs[-1], final_edge_types):
            gradients = [parameter.grad for parameter in module.parameters()]
            assert all(gradient is not None for gradient in gradients), edge_type
            assert (
                sum(float(gradient.abs().sum()) for gradient in gradients if gradient is not None)
                > 0
            ), edge_type

    def test_targets_do_not_change_prediction(self, synthetic_graphs: list[HeteroData]) -> None:
        model = _model(synthetic_graphs)
        graph = synthetic_graphs[0].clone()
        before = model(graph)
        graph["metabolite"].y = torch.randn_like(graph["metabolite"].y)
        graph["metabolite"].y_mask = ~graph["metabolite"].y_mask
        graph.y_graph = torch.randn(1, 3)
        graph.y_graph_mask = torch.zeros(1, 3, dtype=torch.bool)
        torch.testing.assert_close(model(graph), before)
