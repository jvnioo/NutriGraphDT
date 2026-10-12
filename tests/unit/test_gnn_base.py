"""Tests del target por grafo y de la interfaz común de las GNN (A41-5, #81).

Usa los grafos reales del fixture de HoloFood (D1) y los sintéticos de escenarios. Requiere el
extra `graph`.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from torch import Tensor, nn  # noqa: E402
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
    EdgeType,
    GraphMetadata,
    ModelConfig,
    SCFAGraphModel,
    add_graph_target,
    canonical_scfa_name,
    graph_batch,
    masked_mse_loss,
)
from nutrigraphdt.models.metrics import DEFAULT_SCFA_TARGETS  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "holofood"
CONFIG = ModelConfig(hidden_channels=8, num_layers=2, dropout=0.0)


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


@pytest.fixture(scope="module")
def synthetic_graphs() -> list[HeteroData]:
    """Grafos sintéticos con las once tripletas, con inversas y target por grafo."""
    graphs = build_synthetic_graphs(generate_scenario_dataset()).graphs
    return [add_graph_target(add_reverse_edges(graphs[gid])) for gid in sorted(graphs)]


def _metabolite_value(graph: HeteroData, node_id: str) -> float:
    store = graph["metabolite"]
    return float(store.y[list(store.node_id).index(node_id), 0])


class _SageModel(SCFAGraphModel):
    """Variante mínima de prueba: una `HeteroConv` de `SAGEConv` por capa."""

    def __init__(self, metadata: GraphMetadata, config: ModelConfig) -> None:
        super().__init__(metadata, config)
        hidden = config.hidden_channels
        self.convs = nn.ModuleList(
            HeteroConv(
                {edge_type: SAGEConv(hidden, hidden) for edge_type in metadata.edge_types},
                aggr="sum",
            )
            for _ in range(config.num_layers)
        )

    def convolve(
        self,
        layer: int,
        h_dict: Mapping[str, Tensor],
        edge_index_dict: Mapping[EdgeType, Tensor],
    ) -> dict[str, Tensor]:
        output: dict[str, Tensor] = self.convs[layer](dict(h_dict), dict(edge_index_dict))
        return output


class _NoConvModel(SCFAGraphModel):
    """Sin convolución: solo encoder, residual, lectura y cabeza."""

    def convolve(
        self,
        layer: int,
        h_dict: Mapping[str, Tensor],
        edge_index_dict: Mapping[EdgeType, Tensor],
    ) -> dict[str, Tensor]:
        return {}


def _model(cls: type[SCFAGraphModel], graphs: list[HeteroData]) -> SCFAGraphModel:
    torch.manual_seed(42)
    model = cls(GraphMetadata.from_graphs(graphs), CONFIG)
    model.eval()
    return model


# ---------------------------------------------------------------------------
# Target por grafo
# ---------------------------------------------------------------------------


class TestGraphTarget:
    def test_canonical_names_use_exact_match(self) -> None:
        assert canonical_scfa_name("acetate") == "acetate"
        assert canonical_scfa_name(" Butyric_Acid ") == "butyrate"
        assert canonical_scfa_name("synthetic:metabolite:propionate") == "propionate"
        assert canonical_scfa_name("isobutyrate") is None
        assert canonical_scfa_name("valerate") is None

    def test_d1_target_comes_from_metabolite_nodes(self, d1_graphs: list[HeteroData]) -> None:
        for graph in d1_graphs:
            assert graph.y_graph.dtype == torch.float32
            assert tuple(graph.y_graph.shape) == tuple(graph.y_graph_mask.shape) == (1, 3)
            expected = [_metabolite_value(graph, name) for name in DEFAULT_SCFA_TARGETS]
            torch.testing.assert_close(graph.y_graph[0], torch.tensor(expected))
            assert graph.y_graph_mask.all()

    def test_d1_butyrate_is_not_isobutyrate(self, d1_graphs: list[HeteroData]) -> None:
        graph = d1_graphs[0]
        butyrate = float(graph.y_graph[0, DEFAULT_SCFA_TARGETS.index("butyrate")])
        assert butyrate == pytest.approx(_metabolite_value(graph, "butyrate"))
        assert butyrate != pytest.approx(_metabolite_value(graph, "isobutyrate"))

    def test_synthetic_target_uses_chemical_id(self, synthetic_graphs: list[HeteroData]) -> None:
        for graph in synthetic_graphs:
            store = graph["metabolite"]
            by_name = {
                record["chemical_id"]: float(store.y[row, 0])
                for row, record in enumerate(store.raw_attributes)
            }
            expected = [by_name[f"synthetic:metabolite:{name}"] for name in DEFAULT_SCFA_TARGETS]
            torch.testing.assert_close(graph.y_graph[0], torch.tensor(expected))
            assert graph.y_graph_mask.all()

    def test_unmeasured_scfa_is_masked(self, d1_graphs: list[HeteroData]) -> None:
        graph = d1_graphs[0].clone()
        row = list(graph["metabolite"].node_id).index("propionate")
        graph["metabolite"].y_mask[row, 0] = False
        add_graph_target(graph)
        assert graph.y_graph_mask.tolist() == [[True, False, True]]
        assert float(graph.y_graph[0, 1]) == 0.0

    def test_graph_without_metabolites(self) -> None:
        graph = HeteroData()
        graph["host"].x = torch.zeros(1, 1)
        add_graph_target(graph)
        assert graph.y_graph.tolist() == [[0.0, 0.0, 0.0]]
        assert not graph.y_graph_mask.any()

    def test_duplicate_target_is_rejected(self) -> None:
        graph = HeteroData()
        graph["metabolite"].x = torch.zeros(2, 0)
        graph["metabolite"].node_id = ["acetate", "acetic_acid"]
        graph["metabolite"].y = torch.ones(2, 1)
        graph["metabolite"].y_mask = torch.ones(2, 1, dtype=torch.bool)
        with pytest.raises(ValueError, match="más de un nodo|Más de un nodo"):
            add_graph_target(graph)

    def test_misshaped_y_is_rejected(self) -> None:
        graph = HeteroData()
        graph["metabolite"].node_id = ["acetate"]
        graph["metabolite"].y = torch.ones(1, 2)
        graph["metabolite"].y_mask = torch.ones(1, 1, dtype=torch.bool)
        with pytest.raises(ValueError, match="forma"):
            add_graph_target(graph)

    def test_batch_concatenates_targets(self, d1_graphs: list[HeteroData]) -> None:
        batch = next(iter(DataLoader(d1_graphs, batch_size=4)))
        assert tuple(batch.y_graph.shape) == tuple(batch.y_graph_mask.shape) == (4, 3)


class TestMaskedMseLoss:
    def test_only_masked_cells_count(self) -> None:
        prediction = torch.tensor([[1.0, 2.0, 3.0], [0.0, 0.0, 0.0]])
        target = torch.tensor([[2.0, 2.0, 100.0], [1.0, 0.0, 0.0]])
        mask = torch.tensor([[True, True, False], [True, False, False]])
        assert float(masked_mse_loss(prediction, target, mask)) == pytest.approx(2 / 3)

    def test_all_masked_is_zero_and_differentiable(self) -> None:
        prediction = torch.ones(2, 3, requires_grad=True)
        loss = masked_mse_loss(prediction, torch.zeros(2, 3), torch.zeros(2, 3, dtype=torch.bool))
        loss.backward()
        assert loss.item() == 0.0
        assert prediction.grad is not None

    def test_shape_and_dtype_are_checked(self) -> None:
        with pytest.raises(ValueError, match="misma forma"):
            masked_mse_loss(
                torch.zeros(2, 3), torch.zeros(2, 3), torch.zeros(1, 3, dtype=torch.bool)
            )
        with pytest.raises(ValueError, match="booleana"):
            masked_mse_loss(torch.zeros(2, 3), torch.zeros(2, 3), torch.ones(2, 3))


# ---------------------------------------------------------------------------
# GraphMetadata y ModelConfig
# ---------------------------------------------------------------------------


class TestGraphMetadata:
    def test_d1_metadata(self, d1_graphs: list[HeteroData]) -> None:
        metadata = GraphMetadata.from_graphs(d1_graphs)
        assert dict(metadata.node_channels) == {"diet": 0, "host": 1, "metabolite": 0, "taxon": 1}
        assert metadata.edge_types == (
            ("host", "rev_measured_in", "metabolite"),
            ("metabolite", "measured_in", "host"),
        )

    def test_synthetic_metadata_has_all_triplets(self, synthetic_graphs: list[HeteroData]) -> None:
        metadata = GraphMetadata.from_graphs(synthetic_graphs)
        assert len(metadata.node_types) == 8
        assert len(metadata.edge_types) == 22
        node_types, edge_types = metadata.to_pyg()
        assert node_types == list(metadata.node_types)
        assert edge_types == list(metadata.edge_types)

    def test_union_over_graphs(self) -> None:
        first, second = HeteroData(), HeteroData()
        first["host"].x = torch.zeros(1, 1)
        second["taxon"].x = torch.zeros(2, 3)
        metadata = GraphMetadata.from_graphs([first, second])
        assert dict(metadata.node_channels) == {"host": 1, "taxon": 3}

    def test_inconsistent_columns_are_rejected(self) -> None:
        first, second = HeteroData(), HeteroData()
        first["taxon"].x = torch.zeros(1, 1)
        second["taxon"].x = torch.zeros(1, 2)
        with pytest.raises(ValueError, match="esquema de features"):
            GraphMetadata.from_graphs([first, second])

    def test_empty_and_invalid(self) -> None:
        with pytest.raises(ValueError, match="al menos un grafo"):
            GraphMetadata.from_graphs([])
        with pytest.raises(ValueError, match="no está en node_channels"):
            GraphMetadata({"host": 1}, (("taxon", "affects", "host"),))
        with pytest.raises(ValueError, match="node_channels"):
            GraphMetadata({"host": -1}, ())

    def test_from_feature_schema(self) -> None:
        metadata = GraphMetadata.from_feature_schema(
            {"taxon": [{"name": "abundance"}], "host": [], "metabolite": []},
            [("metabolite", "measured_in", "host")],
        )
        assert dict(metadata.node_channels) == {"host": 0, "metabolite": 0, "taxon": 1}


class TestModelConfig:
    def test_initial_values_from_design(self) -> None:
        config = ModelConfig()
        assert (config.hidden_channels, config.num_layers, config.dropout) == (64, 2, 0.2)

    @pytest.mark.parametrize(
        "kwargs",
        [{"hidden_channels": 0}, {"num_layers": 0}, {"dropout": 1.0}, {"num_layers": True}],
    )
    def test_invalid_values(self, kwargs: dict[str, float]) -> None:
        with pytest.raises(ValueError):
            ModelConfig(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# SCFAGraphModel
# ---------------------------------------------------------------------------


class TestSCFAGraphModel:
    def test_base_class_is_abstract(self, d1_graphs: list[HeteroData]) -> None:
        with pytest.raises(TypeError):
            SCFAGraphModel(GraphMetadata.from_graphs(d1_graphs), CONFIG)  # type: ignore[abstract]

    def test_target_names(self, d1_graphs: list[HeteroData]) -> None:
        assert _model(_SageModel, d1_graphs).target_names == DEFAULT_SCFA_TARGETS

    def test_single_graph_output(self, d1_graphs: list[HeteroData]) -> None:
        output = _model(_SageModel, d1_graphs)(d1_graphs[0])
        assert output.dtype == torch.float32
        assert tuple(output.shape) == (1, 3)
        assert torch.isfinite(output).all()

    @pytest.mark.parametrize("fixture", ["d1_graphs", "synthetic_graphs"])
    def test_batch_equals_graph_by_graph(
        self, fixture: str, request: pytest.FixtureRequest
    ) -> None:
        graphs: list[HeteroData] = request.getfixturevalue(fixture)
        model = _model(_SageModel, graphs)
        batch = next(iter(DataLoader(graphs, batch_size=len(graphs))))
        output = model(batch)
        assert tuple(output.shape) == (len(graphs), 3)
        expected = torch.cat([model(graph) for graph in graphs])
        torch.testing.assert_close(output, expected, rtol=1e-4, atol=1e-5)

    def test_graph_batch(self, d1_graphs: list[HeteroData]) -> None:
        assert graph_batch(d1_graphs[0]) == (None, 1)
        batch_dict, num_graphs = graph_batch(next(iter(DataLoader(d1_graphs, batch_size=3))))
        assert num_graphs == 3
        assert batch_dict is not None and set(batch_dict) == set(d1_graphs[0].node_types)

    def test_isolated_types_survive_the_convolution(self, d1_graphs: list[HeteroData]) -> None:
        # En D1 taxon y diet no tienen aristas: con residual, su encoder llega a la lectura.
        # El peso corporal crudo (~100 g) satura la cabeza; en entrenamiento x está
        # estandarizada (§6.2 del diseño), así que aquí se usa un valor estandarizado.
        model = _model(_SageModel, d1_graphs)
        graph = d1_graphs[0].clone()
        graph["host"].x = torch.zeros_like(graph["host"].x)
        before = model(graph)
        graph["taxon"].x = graph["taxon"].x + 1.0
        assert not torch.allclose(model(graph), before)

    def test_targets_do_not_change_the_output(self, d1_graphs: list[HeteroData]) -> None:
        model = _model(_SageModel, d1_graphs)
        graph = d1_graphs[0].clone()
        before = model(graph)
        graph["metabolite"].y = torch.randn_like(graph["metabolite"].y)
        graph["metabolite"].y_mask = ~graph["metabolite"].y_mask
        graph.y_graph = torch.randn(1, 3)
        graph.y_graph_mask = torch.zeros(1, 3, dtype=torch.bool)
        torch.testing.assert_close(model(graph), before)

    def test_metabolite_nodes_do_not_enter_the_readout(self, d1_graphs: list[HeteroData]) -> None:
        # Sin convolución, el número de nodos metabolite (de 2 a 8 en D1) no cambia la salida.
        model = _model(_NoConvModel, d1_graphs)
        graph = d1_graphs[0]
        reduced = HeteroData()
        for node_type in graph.node_types:
            reduced[node_type].x = graph[node_type].x
            reduced[node_type].missing_mask = graph[node_type].missing_mask
        reduced["metabolite"].x = graph["metabolite"].x[:2]
        reduced["metabolite"].missing_mask = graph["metabolite"].missing_mask[:2]
        torch.testing.assert_close(model(reduced), model(graph))

    def test_gradient_reaches_encoder_and_head(self, synthetic_graphs: list[HeteroData]) -> None:
        model = _model(_SageModel, synthetic_graphs)
        model.train()
        batch = next(iter(DataLoader(synthetic_graphs, batch_size=len(synthetic_graphs))))
        loss = masked_mse_loss(model(batch), batch.y_graph, batch.y_graph_mask)
        loss.backward()
        for name, parameter in model.named_parameters():
            if name.startswith(("encoder.projections", "head.")):
                assert parameter.grad is not None, name
                assert parameter.grad.abs().sum() > 0, name
