"""Tests de la GNN homogénea de referencia `homo_sage` (A41-2, #78). Requiere el extra `graph`."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from torch_geometric.data import HeteroData  # noqa: E402
from torch_geometric.loader import DataLoader  # noqa: E402
from torch_geometric.nn import SAGEConv  # noqa: E402

from nutrigraphdt.data.config import load_sources  # noqa: E402
from nutrigraphdt.data.integration import attach_sample_context  # noqa: E402
from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader  # noqa: E402
from nutrigraphdt.data.pipeline import DataPipeline  # noqa: E402
from nutrigraphdt.data.synthetic import generate_scenario_dataset  # noqa: E402
from nutrigraphdt.graph.builder import add_reverse_edges, build_hetero_graph  # noqa: E402
from nutrigraphdt.graph.heterodata import build_synthetic_graphs  # noqa: E402
from nutrigraphdt.models.gnn import (  # noqa: E402
    GraphMetadata,
    HomoSAGE,
    ModelConfig,
    SCFAGraphModel,
    add_graph_target,
    masked_mse_loss,
)

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
    """Grafos reales del fixture de HoloFood (D1), con inversas y target por grafo."""
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


def _model(graphs: list[HeteroData], config: ModelConfig = CONFIG, **kwargs: str) -> HomoSAGE:
    torch.manual_seed(42)
    model = HomoSAGE(GraphMetadata.from_graphs(graphs), config, **kwargs)
    model.eval()
    return model


def _batch(graphs: list[HeteroData]) -> HeteroData:
    batch: HeteroData = next(iter(DataLoader(graphs, batch_size=len(graphs))))
    return batch


class TestForward:
    def test_synthetic_batch_shape_without_nan(self, synthetic_graphs: list[HeteroData]) -> None:
        # Criterio de aceptación: [N_objetivo, 3] sin NaN; N_objetivo = grafos del lote (A41-1).
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

    @pytest.mark.parametrize("fixture", ["synthetic_graphs", "d1_graphs"])
    def test_batch_equals_graph_by_graph(
        self, fixture: str, request: pytest.FixtureRequest
    ) -> None:
        graphs: list[HeteroData] = request.getfixturevalue(fixture)
        model = _model(graphs)
        expected = torch.cat([model(graph) for graph in graphs])
        torch.testing.assert_close(model(_batch(graphs)), expected, rtol=1e-4, atol=1e-5)

    @pytest.mark.parametrize("aggr", ["mean", "max", "sum"])
    def test_aggregations(self, aggr: str, synthetic_graphs: list[HeteroData]) -> None:
        output = _model(synthetic_graphs, aggr=aggr)(_batch(synthetic_graphs))
        assert torch.isfinite(output).all()

    @pytest.mark.parametrize("num_layers", [1, 3])
    def test_number_of_layers(self, num_layers: int, synthetic_graphs: list[HeteroData]) -> None:
        config = ModelConfig(hidden_channels=8, num_layers=num_layers, dropout=0.0)
        model = _model(synthetic_graphs, config)
        assert len(model.convs) == num_layers
        assert tuple(model(_batch(synthetic_graphs)).shape) == (len(synthetic_graphs), 3)


class TestHomogeneous:
    def test_inherits_common_interface(self, synthetic_graphs: list[HeteroData]) -> None:
        model = _model(synthetic_graphs)
        assert isinstance(model, SCFAGraphModel)
        assert model.target_names == ("acetate", "propionate", "butyrate")

    def test_one_shared_convolution_per_layer(self, synthetic_graphs: list[HeteroData]) -> None:
        # La convolución no depende de los tipos: sus parámetros son los mismos con 2 o 22
        # tipos de arista.
        model = _model(synthetic_graphs)
        for conv in model.convs:
            assert isinstance(conv, SAGEConv)
            assert (conv.in_channels, conv.out_channels) == (8, 8)
            assert conv.aggr == "mean"
        conv_parameters = sum(p.numel() for p in model.convs.parameters())
        assert conv_parameters == 2 * (8 * 8 + 8 * 8 + 8)

    def test_convolve_matches_manual_homogeneous_graph(self) -> None:
        metadata = GraphMetadata({"a": 1, "b": 1}, (("a", "to", "b"),))
        model = HomoSAGE(metadata, CONFIG)
        generator = torch.Generator().manual_seed(0)
        h_dict = {
            "a": torch.randn(2, 8, generator=generator),
            "b": torch.randn(3, 8, generator=generator),
        }
        edge_index = torch.tensor([[0, 1, 1], [0, 2, 1]])
        output = model.convolve(0, h_dict, {("a", "to", "b"): edge_index})
        # Nodos de `a` en las filas 0-1 y de `b` en las 2-4 del grafo homogéneo.
        x = torch.cat([h_dict["a"], h_dict["b"]])
        homogeneous_edges = torch.stack([edge_index[0], edge_index[1] + 2])
        expected = model.convs[0](x, homogeneous_edges)
        torch.testing.assert_close(output["a"], expected[:2])
        torch.testing.assert_close(output["b"], expected[2:])

    def test_relation_type_is_ignored(self) -> None:
        # Con la misma conectividad, renombrar la relación no cambia la convolución.
        metadata = GraphMetadata({"a": 1, "b": 1}, (("a", "to", "b"), ("a", "other", "b")))
        model = HomoSAGE(metadata, CONFIG)
        h_dict = {"a": torch.randn(2, 8), "b": torch.randn(2, 8)}
        edge_index = torch.tensor([[0, 1], [1, 0]])
        first = model.convolve(0, h_dict, {("a", "to", "b"): edge_index})
        second = model.convolve(0, h_dict, {("a", "other", "b"): edge_index})
        for node_type in h_dict:
            torch.testing.assert_close(first[node_type], second[node_type])

    def test_graph_without_edges(self) -> None:
        model = HomoSAGE(GraphMetadata({"host": 1}, ()), CONFIG)
        output = model.convolve(0, {"host": torch.randn(1, 8)}, {})
        assert tuple(output["host"].shape) == (1, 8)

    def test_isolated_types_reach_the_output(self, d1_graphs: list[HeteroData]) -> None:
        # Peso corporal estandarizado (§6.2 del diseño): el valor crudo satura la cabeza.
        model = _model(d1_graphs)
        graph = d1_graphs[0].clone()
        graph["host"].x = torch.zeros_like(graph["host"].x)
        before = model(graph)
        graph["taxon"].x = graph["taxon"].x + 1.0
        assert not torch.allclose(model(graph), before)

    def test_invalid_aggregation(self, synthetic_graphs: list[HeteroData]) -> None:
        with pytest.raises(ValueError, match="aggr"):
            HomoSAGE(GraphMetadata.from_graphs(synthetic_graphs), CONFIG, aggr="median")


class TestTraining:
    def test_targets_do_not_change_the_output(self, synthetic_graphs: list[HeteroData]) -> None:
        model = _model(synthetic_graphs)
        graph = synthetic_graphs[0].clone()
        before = model(graph)
        graph["metabolite"].y = torch.randn_like(graph["metabolite"].y)
        graph["metabolite"].y_mask = ~graph["metabolite"].y_mask
        graph.y_graph = torch.randn(1, 3)
        graph.y_graph_mask = torch.zeros(1, 3, dtype=torch.bool)
        torch.testing.assert_close(model(graph), before)

    def test_gradient_reaches_convolutions(self, synthetic_graphs: list[HeteroData]) -> None:
        model = _model(synthetic_graphs)
        model.train()
        batch = _batch(synthetic_graphs)
        masked_mse_loss(model(batch), batch.y_graph, batch.y_graph_mask).backward()
        for name, parameter in model.named_parameters():
            if name.startswith(("convs.", "head.", "encoder.projections")):
                assert parameter.grad is not None, name
                assert parameter.grad.abs().sum() > 0, name
