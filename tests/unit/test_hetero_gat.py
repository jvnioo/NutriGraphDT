"""Tests de `hetero_gat` (A41-4, #80). Requiere el extra `graph`."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from torch import nn  # noqa: E402
from torch.nn.parameter import UninitializedParameter  # noqa: E402
from torch_geometric.data import HeteroData  # noqa: E402
from torch_geometric.loader import DataLoader  # noqa: E402
from torch_geometric.nn import GATConv, HeteroConv  # noqa: E402

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
    HeteroGAT,
    ModelConfig,
    add_graph_target,
    initialize_lazy_parameters,
    masked_mse_loss,
)
from nutrigraphdt.models.gnn.components import EXCLUDED_FROM_READOUT  # noqa: E402

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

    def source(source_id: str, file_name: str) -> Any:
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


def _model(graphs: list[HeteroData], **kwargs: Any) -> HeteroGAT:
    torch.manual_seed(42)
    model = HeteroGAT(_metadata(graphs), CONFIG, **kwargs)
    initialize_lazy_parameters(model)
    model.eval()
    return model


def _batch(graphs: list[HeteroData]) -> HeteroData:
    batch: HeteroData = next(iter(DataLoader(graphs, batch_size=len(graphs))))
    return batch


def _relation_modules(
    layer: HeteroConv, metadata: GraphMetadata
) -> list[tuple[tuple[str, str, str], nn.Module]]:
    modules = list(layer.convs.values())
    assert len(modules) == len(metadata.edge_types)
    return list(zip(metadata.edge_types, modules, strict=True))


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

    def test_one_gat_convolution_per_metadata_relation(
        self, synthetic_graphs: list[HeteroData]
    ) -> None:
        model = _model(synthetic_graphs)
        assert len(model.metadata.edge_types) == 22
        for layer in model.convs:
            assert isinstance(layer, HeteroConv)
            assert layer.aggr == "sum"
            relations = _relation_modules(layer, model.metadata)
            assert all(isinstance(module, GATConv) for _, module in relations)
            assert all(module.heads == 4 and module.concat for _, module in relations)
            assert all(
                module.out_channels == CONFIG.hidden_channels // 4 for _, module in relations
            )
            assert all(not module.add_self_loops for _, module in relations)

    @pytest.mark.parametrize("relation_aggr", sorted(HETERO_RELATION_AGGREGATIONS))
    def test_relation_aggregations(
        self, relation_aggr: str, synthetic_graphs: list[HeteroData]
    ) -> None:
        model = _model(synthetic_graphs, relation_aggr=relation_aggr)
        output = model(_batch(synthetic_graphs))
        assert torch.isfinite(output).all()
        assert all(layer.aggr == relation_aggr for layer in model.convs)

    def test_concat_false_averages_heads_and_keeps_hidden_width(
        self, synthetic_graphs: list[HeteroData]
    ) -> None:
        model = _model(synthetic_graphs, heads=3, concat=False)
        assert all(
            module.out_channels == CONFIG.hidden_channels
            and module.heads == 3
            and not module.concat
            for layer in model.convs
            for module in layer.convs.values()
        )
        output = model(_batch(synthetic_graphs))
        assert tuple(output.shape) == (len(synthetic_graphs), 3)
        assert torch.isfinite(output).all()

    def test_attention_predictions_and_weights_match_normal_forward(
        self, synthetic_graphs: list[HeteroData]
    ) -> None:
        model = _model(synthetic_graphs)
        batch = _batch(synthetic_graphs)
        expected = model(batch)
        prediction, weights = model.forward_with_attention(batch)

        torch.testing.assert_close(prediction, expected)
        assert set(weights) == {
            (layer, edge_type)
            for layer in range(CONFIG.num_layers)
            for edge_type in batch.edge_types
        }
        for (_layer, edge_type), (edge_index, alpha) in weights.items():
            assert tuple(edge_index.shape) == tuple(batch[edge_type].edge_index.shape)
            assert edge_index.size(1) == batch[edge_type].edge_index.size(1)
            assert tuple(alpha.shape) == (edge_index.size(1), model.heads)

    def test_forward_uses_heteroconv_again_after_attention_failure(
        self,
        synthetic_graphs: list[HeteroData],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        model = _model(synthetic_graphs)
        graph = synthetic_graphs[0]
        relation_conv = next(iter(model.convs[0].convs.values()))
        original_relation_forward = relation_conv.forward

        def fail_attention(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("simulated attention failure")

        monkeypatch.setattr(relation_conv, "forward", fail_attention)
        with pytest.raises(RuntimeError, match="simulated attention failure"):
            model.forward_with_attention(graph)

        monkeypatch.setattr(relation_conv, "forward", original_relation_forward)
        hetero_conv = model.convs[0]
        original_hetero_forward = hetero_conv.forward
        called = False

        def track_hetero_forward(*args: Any, **kwargs: Any) -> Any:
            nonlocal called
            called = True
            return original_hetero_forward(*args, **kwargs)

        monkeypatch.setattr(hetero_conv, "forward", track_hetero_forward)
        output = model(graph)
        assert called
        assert tuple(output.shape) == (1, 3)

    @pytest.mark.parametrize(
        ("heads", "concat", "message"),
        [
            (0, True, "heads"),
            (True, True, "heads"),
            (4, 1, "concat"),
            (3, True, "divisible"),
        ],
    )
    def test_invalid_head_configuration(
        self,
        heads: int,
        concat: bool,
        message: str,
        synthetic_graphs: list[HeteroData],
    ) -> None:
        with pytest.raises(ValueError, match=message):
            HeteroGAT(_metadata(synthetic_graphs), CONFIG, heads=heads, concat=concat)

    def test_invalid_relation_aggregation(self, synthetic_graphs: list[HeteroData]) -> None:
        with pytest.raises(ValueError, match="relation_aggr"):
            HeteroGAT(_metadata(synthetic_graphs), CONFIG, relation_aggr="cat")

    def test_targets_do_not_change_prediction(self, synthetic_graphs: list[HeteroData]) -> None:
        model = _model(synthetic_graphs)
        graph = synthetic_graphs[0].clone()
        before = model(graph)
        graph["metabolite"].y = torch.randn_like(graph["metabolite"].y)
        graph["metabolite"].y_mask = ~graph["metabolite"].y_mask
        graph.y_graph = torch.randn(1, 3)
        graph.y_graph_mask = torch.zeros(1, 3, dtype=torch.bool)
        torch.testing.assert_close(model(graph), before)


class TestLazyInitialization:
    @pytest.mark.parametrize("training", [True, False])
    def test_initializes_full_metadata_for_sparse_d1_batch(
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
        model = HeteroGAT(metadata, CONFIG)
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

        for edge_type, module in _relation_modules(model.convs[0], model.metadata):
            gradients = [parameter.grad for parameter in module.parameters()]
            assert all(gradient is not None for gradient in gradients), edge_type
            assert (
                sum(float(gradient.abs().sum()) for gradient in gradients if gradient is not None)
                > 0
            ), edge_type

    def test_final_layer_excluded_destinations_have_no_gradient(
        self, synthetic_graphs: list[HeteroData]
    ) -> None:
        model = _model(synthetic_graphs)
        batch = _batch(synthetic_graphs)
        masked_mse_loss(model(batch), batch.y_graph, batch.y_graph_mask).backward()

        excluded = [
            (edge_type, module)
            for edge_type, module in _relation_modules(model.convs[-1], model.metadata)
            if edge_type[2] in EXCLUDED_FROM_READOUT
        ]
        assert excluded
        for edge_type, module in excluded:
            assert all(parameter.grad is None for parameter in module.parameters()), edge_type
