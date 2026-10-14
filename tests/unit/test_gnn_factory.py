"""Configuración YAML y fábrica de modelos GNN (A41-8, #84). Requiere el extra `graph`."""

from __future__ import annotations

from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from torch.nn.parameter import UninitializedParameter  # noqa: E402
from torch_geometric.data import HeteroData  # noqa: E402
from torch_geometric.loader import DataLoader  # noqa: E402

from nutrigraphdt.data.synthetic import generate_scenario_dataset  # noqa: E402
from nutrigraphdt.graph.builder import add_reverse_edges  # noqa: E402
from nutrigraphdt.graph.heterodata import build_synthetic_graphs  # noqa: E402
from nutrigraphdt.models.gnn import (  # noqa: E402
    MODEL_VARIANTS,
    GraphMetadata,
    HeteroGAT,
    HeteroGATConfig,
    HeteroSAGE,
    HomoSAGE,
    ModelConfig,
    ModelConfigError,
    add_graph_target,
    build_model,
    load_model_config,
    parse_model_config,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs" / "models"
MODEL_CLASSES = {"homo_sage": HomoSAGE, "hetero_sage": HeteroSAGE, "hetero_gat": HeteroGAT}


@pytest.fixture(scope="module")
def graphs() -> list[HeteroData]:
    built = build_synthetic_graphs(generate_scenario_dataset()).graphs
    return [add_graph_target(add_reverse_edges(built[graph_id])) for graph_id in sorted(built)]


@pytest.fixture(scope="module")
def metadata(graphs: list[HeteroData]) -> GraphMetadata:
    return GraphMetadata.from_graphs(graphs)


class TestRepositoryConfigs:
    @pytest.mark.parametrize("variant", MODEL_VARIANTS)
    def test_each_variant_has_a_config_with_the_design_defaults(self, variant: str) -> None:
        cfg = load_model_config(CONFIG_DIR / f"{variant}.yaml")
        assert cfg.variant == variant
        assert cfg.common() == ModelConfig()

    def test_hetero_gat_initial_values(self) -> None:
        cfg = load_model_config(CONFIG_DIR / "hetero_gat.yaml")
        assert isinstance(cfg, HeteroGATConfig)
        assert (cfg.heads, cfg.concat, cfg.relation_aggr) == (4, True, "sum")


class TestBuildModel:
    @pytest.mark.parametrize("variant", MODEL_VARIANTS)
    def test_builds_the_declared_variant(
        self, variant: str, metadata: GraphMetadata, graphs: list[HeteroData]
    ) -> None:
        torch.manual_seed(0)
        model = build_model(load_model_config(CONFIG_DIR / f"{variant}.yaml"), metadata)

        assert type(model) is MODEL_CLASSES[variant]
        assert model.config == ModelConfig()
        assert not any(isinstance(p, UninitializedParameter) for p in model.parameters())
        torch.optim.Adam(model.parameters())

        model.eval()
        batch = next(iter(DataLoader(graphs, batch_size=len(graphs))))
        with torch.no_grad():
            output = model(batch)
        assert output.shape == (len(graphs), 3)
        assert torch.isfinite(output).all()

    def test_variant_specific_values_reach_the_model(self, metadata: GraphMetadata) -> None:
        cfg = parse_model_config(
            {"variant": "hetero_gat", "hidden_channels": 12, "heads": 3, "relation_aggr": "mean"}
        )
        model = build_model(cfg, metadata)
        assert isinstance(model, HeteroGAT)
        assert (model.heads, model.relation_aggr) == (3, "mean")
        assert model.config.hidden_channels == 12

    def test_changing_variant_only_requires_editing_the_yaml(
        self, tmp_path: Path, metadata: GraphMetadata
    ) -> None:
        path = tmp_path / "model.yaml"
        path.write_text("variant: homo_sage\naggr: max\n", encoding="utf-8")
        first = build_model(load_model_config(path), metadata)
        path.write_text("variant: hetero_sage\naggr: max\n", encoding="utf-8")
        second = build_model(load_model_config(path), metadata)

        assert isinstance(first, HomoSAGE)
        assert isinstance(second, HeteroSAGE)
        assert first.aggr == second.aggr == "max"


class TestInvalidConfigs:
    @pytest.mark.parametrize(
        ("data", "fragment"),
        [
            ({}, "variant"),
            ({"variant": "gcn"}, "gcn"),
            ({"variant": "homo_sage", "heads": 4}, "heads"),
            ({"variant": "homo_sage", "aggr": "median"}, "aggr"),
            ({"variant": "hetero_sage", "relation_aggr": "max"}, "relation_aggr"),
            ({"variant": "homo_sage", "hidden_channels": 0}, "hidden_channels"),
            ({"variant": "homo_sage", "hidden_channels": True}, "hidden_channels"),
            ({"variant": "homo_sage", "hidden_channels": "64"}, "hidden_channels"),
            ({"variant": "homo_sage", "num_layers": 1.5}, "num_layers"),
            ({"variant": "homo_sage", "dropout": 1.0}, "dropout"),
            ({"variant": "hetero_gat", "heads": 0}, "heads"),
            ({"variant": "hetero_gat", "concat": "yes"}, "concat"),
            ({"variant": "hetero_gat", "hidden_channels": 10, "heads": 4}, "divisible"),
        ],
    )
    def test_rejected_with_the_offending_field(
        self, data: dict[str, object], fragment: str
    ) -> None:
        with pytest.raises(ModelConfigError, match=fragment):
            parse_model_config(data)

    def test_divisibility_only_applies_with_concat(self) -> None:
        cfg = parse_model_config(
            {"variant": "hetero_gat", "hidden_channels": 10, "heads": 4, "concat": False}
        )
        assert isinstance(cfg, HeteroGATConfig)

    def test_message_names_the_file(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.yaml"
        path.write_text("variant: homo_sage\ndropout: -0.1\n", encoding="utf-8")
        with pytest.raises(ModelConfigError, match=r"broken\.yaml.*\n.*dropout"):
            load_model_config(path)

    @pytest.mark.parametrize("content", ["variant: [homo_sage\n", "- homo_sage\n", ""])
    def test_rejects_malformed_or_non_mapping_yaml(self, tmp_path: Path, content: str) -> None:
        path = tmp_path / "model.yaml"
        path.write_text(content, encoding="utf-8")
        with pytest.raises(ModelConfigError):
            load_model_config(path)

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_model_config(tmp_path / "absent.yaml")
