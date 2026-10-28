"""Configuración del entrenamiento y control de semillas (A44-4, #98). Requiere el extra `graph`."""

from __future__ import annotations

import argparse
import json
import random
from collections.abc import Iterator
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

import numpy as np  # noqa: E402
from torch_geometric.data import HeteroData  # noqa: E402
from torch_geometric.loader import DataLoader  # noqa: E402

from nutrigraphdt.data.synthetic import generate_scenario_dataset  # noqa: E402
from nutrigraphdt.graph.builder import add_reverse_edges  # noqa: E402
from nutrigraphdt.graph.heterodata import build_synthetic_graphs  # noqa: E402
from nutrigraphdt.models.gnn import (  # noqa: E402
    GraphMetadata,
    HeteroSAGE,
    ModelConfig,
    add_graph_target,
    initialize_lazy_parameters,
)
from nutrigraphdt.models.training import (  # noqa: E402
    MAX_SEED,
    TrainingConfig,
    TrainingConfigError,
    add_override_arguments,
    apply_overrides,
    load_training_config,
    overrides_from_args,
    parse_training_config,
    set_seed,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "training" / "default.json"


@pytest.fixture(autouse=True)
def _restore_determinism() -> Iterator[None]:
    """`set_seed` cambia un estado global de PyTorch; se restaura para el resto de la suite."""
    previous = torch.are_deterministic_algorithms_enabled()
    yield
    torch.use_deterministic_algorithms(previous)


@pytest.fixture(scope="module")
def default() -> TrainingConfig:
    return load_training_config(DEFAULT_CONFIG)


@pytest.fixture(scope="module")
def graphs() -> list[HeteroData]:
    built = build_synthetic_graphs(generate_scenario_dataset()).graphs
    prepared = [add_graph_target(add_reverse_edges(built[graph_id])) for graph_id in sorted(built)]
    # Copias con un identificador propio, para que el orden de lotes tenga más de dos elementos.
    copies = []
    for index in range(8):
        graph = prepared[index % len(prepared)].clone()
        graph.run_index = index
        copies.append(graph)
    return copies


class TestDefaultConfig:
    def test_matches_the_design_initial_values(self, default: TrainingConfig) -> None:
        assert default.model_dump() == {
            "lr": 1e-3,
            "weight_decay": 1e-4,
            "batch_size": 16,
            "max_epochs": 200,
            "patience": 20,
            "seed": 42,
            "device": "cpu",
            "dataset_id": "D1_holofood",
            "split_file": "configs/splits/d1_holofood.json",
            "constraint_lambda": 0.0,
            "constraint_terms": (),
        }

    def test_round_trips_through_json(self, default: TrainingConfig) -> None:
        assert parse_training_config(json.loads(default.model_dump_json())) == default


class TestInvalidConfig:
    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("lr", 0.0),
            ("lr", -1e-3),
            ("weight_decay", -1e-4),
            ("batch_size", 0),
            ("max_epochs", 0),
            ("patience", 0),
            ("seed", -1),
            ("seed", MAX_SEED + 1),
            ("seed", True),
            ("batch_size", 16.0),
            ("batch_size", "16"),
            ("device", "tpu"),
            ("dataset_id", ""),
            ("constraint_lambda", -1.0),
            ("constraint_lambda", float("inf")),
            ("constraint_lambda", float("nan")),
            ("constraint_terms", "structural.simplex_closure"),
            ("constraint_terms", ["unknown.constraint"]),
            (
                "constraint_terms",
                ["structural.simplex_closure", "structural.simplex_closure"],
            ),
        ],
    )
    def test_out_of_range_or_wrong_type(
        self, default: TrainingConfig, field: str, value: object
    ) -> None:
        with pytest.raises(TrainingConfigError, match=field):
            parse_training_config({**default.model_dump(), field: value})

    def test_unknown_key(self, default: TrainingConfig) -> None:
        with pytest.raises(TrainingConfigError, match="learning_rate"):
            parse_training_config({**default.model_dump(), "learning_rate": 1e-3})

    def test_missing_key(self, default: TrainingConfig) -> None:
        data = default.model_dump()
        del data["patience"]
        with pytest.raises(TrainingConfigError, match="patience"):
            parse_training_config(data)

    def test_message_names_the_file(self, tmp_path: Path, default: TrainingConfig) -> None:
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({**default.model_dump(), "lr": 0}), encoding="utf-8")
        with pytest.raises(TrainingConfigError, match=r"bad\.json.*\n.*lr"):
            load_training_config(path)

    def test_malformed_json(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("{lr: 0.001}", encoding="utf-8")
        with pytest.raises(TrainingConfigError, match="JSON inválido"):
            load_training_config(path)

    def test_positive_lambda_requires_known_terms(self) -> None:
        values = {
            "lr": 1e-3,
            "weight_decay": 1e-4,
            "batch_size": 4,
            "max_epochs": 2,
            "patience": 1,
            "seed": 1,
            "dataset_id": "synthetic",
            "split_file": "split.json",
            "constraint_lambda": 1.0,
        }
        with pytest.raises(TrainingConfigError, match="requiere al menos un"):
            parse_training_config(values)

        config = parse_training_config(
            {
                **values,
                "constraint_terms": ["structural.simplex_closure"],
            }
        )
        assert config.constraint_terms == ("structural.simplex_closure",)


class TestOverrides:
    def _parse(self, argv: list[str]) -> argparse.Namespace:
        parser = argparse.ArgumentParser()
        add_override_arguments(parser)
        return parser.parse_args(argv)

    def test_only_explicit_arguments_override(self, default: TrainingConfig) -> None:
        overrides = overrides_from_args(self._parse(["--seed", "7", "--lr", "0.01"]))
        assert overrides == {"seed": 7, "lr": 0.01}

        effective = apply_overrides(default, overrides)
        assert (effective.seed, effective.lr) == (7, 0.01)
        assert effective.model_dump() == {**default.model_dump(), "seed": 7, "lr": 0.01}

    def test_classic_training_arguments_do_not_expose_constraint_flags(self) -> None:
        args = self._parse([])
        assert "constraint_lambda" not in vars(args)
        assert "constraint_terms" not in vars(args)
        assert overrides_from_args(args) == {}

    def test_override_is_validated(self, default: TrainingConfig) -> None:
        with pytest.raises(TrainingConfigError, match="patience"):
            apply_overrides(default, overrides_from_args(self._parse(["--patience", "0"])))

    def test_no_overrides_returns_the_same_config(self, default: TrainingConfig) -> None:
        assert apply_overrides(default, {}) is default


class TestSetSeed:
    def _initial_weights(self, graphs: list[HeteroData], seed: int) -> list[torch.Tensor]:
        set_seed(seed)
        model = HeteroSAGE(GraphMetadata.from_graphs(graphs), ModelConfig())
        initialize_lazy_parameters(model)
        return [p.detach().clone() for p in model.parameters()]

    def _batch_order(self, graphs: list[HeteroData], seed: int) -> list[list[int]]:
        set_seed(seed)
        loader = DataLoader(graphs, batch_size=3, shuffle=True)
        return [batch.run_index.tolist() for batch in loader]

    def test_same_seed_same_initial_weights(self, graphs: list[HeteroData]) -> None:
        first = self._initial_weights(graphs, 42)
        second = self._initial_weights(graphs, 42)
        assert len(first) == len(second) > 0
        assert all(torch.equal(a, b) for a, b in zip(first, second, strict=True))
        other = self._initial_weights(graphs, 43)
        assert not all(torch.equal(a, b) for a, b in zip(first, other, strict=True))

    def test_same_seed_same_batch_order(self, graphs: list[HeteroData]) -> None:
        first = self._batch_order(graphs, 42)
        assert first == self._batch_order(graphs, 42)
        assert sorted(i for batch in first for i in batch) == list(range(len(graphs)))
        assert any(self._batch_order(graphs, seed) != first for seed in range(43, 48))

    def test_seeds_python_numpy_and_enables_determinism(self) -> None:
        set_seed(11)
        values = (random.random(), float(np.random.rand()), float(torch.rand(1)))
        set_seed(11)
        assert values == (random.random(), float(np.random.rand()), float(torch.rand(1)))
        assert torch.are_deterministic_algorithms_enabled()

    @pytest.mark.parametrize("seed", [-1, MAX_SEED + 1, True, 1.5])
    def test_rejects_invalid_seed(self, seed: object) -> None:
        with pytest.raises(ValueError, match="seed"):
            set_seed(seed)  # type: ignore[arg-type]
