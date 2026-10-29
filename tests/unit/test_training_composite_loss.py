"""Tests de la pérdida compuesta del entrenamiento composicional (#166)."""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from torch_geometric.data import HeteroData  # noqa: E402
from torch_geometric.loader import DataLoader  # noqa: E402

import nutrigraphdt.models.training.compositional as compositional_training  # noqa: E402
from nutrigraphdt.constraints import (  # noqa: E402
    FunctionalConstraint,
    structural_constraints,
)
from nutrigraphdt.graph.builder import add_reverse_edges  # noqa: E402
from nutrigraphdt.graph.heterodata import build_synthetic_graphs  # noqa: E402
from nutrigraphdt.models.baselines import build_synthetic_cohort  # noqa: E402
from nutrigraphdt.models.composition import CompositionalReconstructionError  # noqa: E402
from nutrigraphdt.models.gnn import build_model, load_model_config  # noqa: E402
from nutrigraphdt.models.gnn.base import GraphMetadata  # noqa: E402
from nutrigraphdt.models.gnn.batching import align_graph_types  # noqa: E402
from nutrigraphdt.models.gnn.target import add_graph_target  # noqa: E402
from nutrigraphdt.models.training import (  # noqa: E402
    CompositionalTargetTransform,
    FeatureScaler,
    TrainingConfig,
    set_seed,
)
from nutrigraphdt.models.training.compositional import (  # noqa: E402
    _bio_loss,
    train_compositional_model,
)

SEED = 42
CONSTRAINT_NAME = "structural.non_negative.concentrations.acetate"


@pytest.fixture(scope="module")
def graphs() -> dict[str, HeteroData]:
    cohort = build_synthetic_cohort(16, first_seed=1)
    built = build_synthetic_graphs(cohort)
    prepared: dict[str, HeteroData] = {}
    for graph_id, graph in built.graphs.items():
        with_target = add_graph_target(add_reverse_edges(graph))
        with_target.graph_id = graph_id
        prepared[str(with_target.sample_id)] = with_target
    align_graph_types(list(prepared.values()), inplace=True)
    return prepared


def _config(**overrides: object) -> TrainingConfig:
    values: dict[str, object] = {
        "lr": 1e-2,
        "weight_decay": 1e-4,
        "batch_size": 4,
        "max_epochs": 1,
        "patience": 1,
        "seed": SEED,
        "dataset_id": "synthetic_cohort",
        "split_file": "configs/splits/d1_holofood.json",
    }
    values.update(overrides)
    return TrainingConfig.model_validate(values)


def _inputs(
    graphs: dict[str, HeteroData],
) -> tuple[list[HeteroData], list[HeteroData], CompositionalTargetTransform, FeatureScaler]:
    items = list(graphs.values())
    train_graphs, val_graphs = items[:12], items[12:]
    transform = CompositionalTargetTransform.fit(train_graphs)
    scaler = FeatureScaler.fit(train_graphs)
    return scaler.transform(train_graphs), scaler.transform(val_graphs), transform, scaler


def _model(graphs: dict[str, HeteroData]):
    return build_model(
        load_model_config("configs/models/homo_sage.yaml"),
        GraphMetadata.from_graphs(list(graphs.values())),
    )


def _violated_test_constraint() -> FunctionalConstraint:
    registered = next(
        constraint
        for constraint in structural_constraints()
        if constraint.metadata.name == CONSTRAINT_NAME
    )
    return FunctionalConstraint(registered.metadata, lambda concentrations: concentrations[:, 0])


def test_zero_lambda_never_calls_constraint_path(
    graphs: dict[str, HeteroData], monkeypatch: pytest.MonkeyPatch
) -> None:
    train, val, transform, _ = _inputs(graphs)

    def unexpected(*args: object, **kwargs: object) -> None:
        raise AssertionError("El camino de restricciones no debe ejecutarse con lambda cero.")

    monkeypatch.setattr(compositional_training, "compositional_constraint_inputs", unexpected)
    monkeypatch.setattr(compositional_training, "evaluate_constraints", unexpected)
    monkeypatch.setattr(compositional_training, "constraint_penalty", unexpected)
    set_seed(SEED)
    result = train_compositional_model(_model(graphs), train, val, _config(), transform)

    assert result.history
    assert all(record.train_bio_loss == record.val_bio_loss == 0.0 for record in result.history)
    assert all(record.train_data_loss == record.train_total_loss for record in result.history)
    assert all(record.val_data_loss == record.val_total_loss for record in result.history)


def test_positive_lambda_penalty_changes_training_gradients(
    graphs: dict[str, HeteroData], monkeypatch: pytest.MonkeyPatch
) -> None:
    train, val, transform, _ = _inputs(graphs)
    monkeypatch.setattr(
        compositional_training, "structural_constraints", lambda: (_violated_test_constraint(),)
    )
    config = _config(
        max_epochs=3,
        constraint_lambda=1.0,
        constraint_terms=[CONSTRAINT_NAME],
    )
    set_seed(SEED)
    constrained = train_compositional_model(_model(graphs), train, val, config, transform)
    constrained_state = {
        name: value.detach().clone() for name, value in constrained.model.state_dict().items()
    }

    set_seed(SEED)
    control = train_compositional_model(_model(graphs), train, val, _config(), transform)
    control_state = control.model.state_dict()

    assert constrained.history[0].train_bio_loss > 0
    assert constrained.history[0].val_bio_loss > 0
    assert constrained.history[0].train_total_loss > constrained.history[0].train_data_loss
    assert constrained.history[0].train_total_loss == pytest.approx(
        constrained.history[0].train_data_loss
        + config.constraint_lambda * constrained.history[0].train_bio_loss
    )
    assert constrained.best_val_loss == min(row.val_total_loss for row in constrained.history)
    assert any(
        not torch.equal(constrained_state[name], control_state[name]) for name in constrained_state
    )


def test_masked_animals_do_not_contribute_to_bio_loss(
    graphs: dict[str, HeteroData], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        compositional_training, "structural_constraints", lambda: (_violated_test_constraint(),)
    )
    _, _, transform, _ = _inputs(graphs)
    batch = next(iter(DataLoader(list(graphs.values())[:2], batch_size=2)))
    batch.y_graph_mask[1] = False
    first = torch.zeros((2, 3), requires_grad=True)
    changed_invalid = torch.tensor([[0.0, 0.0, 0.0], [1.0, -1.0, 2.0]], requires_grad=True)

    first_loss = _bio_loss(first, batch, transform, (_violated_test_constraint(),))
    changed_loss = _bio_loss(changed_invalid, batch, transform, (_violated_test_constraint(),))
    gradient = torch.autograd.grad(changed_loss, changed_invalid)[0]

    assert first_loss.item() == changed_loss.item()
    assert torch.equal(gradient[1], torch.zeros_like(gradient[1]))
    assert bool((gradient[0] != 0).any())


def test_all_invalid_batch_has_connected_zero_bio_loss(
    graphs: dict[str, HeteroData], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        compositional_training, "structural_constraints", lambda: (_violated_test_constraint(),)
    )
    _, _, transform, _ = _inputs(graphs)
    batch = next(iter(DataLoader(list(graphs.values())[:2], batch_size=2)))
    batch.y_graph_mask[:] = False
    output = torch.zeros((2, 3), requires_grad=True)

    loss = _bio_loss(output, batch, transform, (_violated_test_constraint(),))
    gradient = torch.autograd.grad(loss, output)[0]

    assert loss.item() == 0.0
    assert torch.equal(gradient, torch.zeros_like(output))


def test_reconstruction_error_propagates_during_training(
    graphs: dict[str, HeteroData], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        compositional_training, "structural_constraints", lambda: (_violated_test_constraint(),)
    )
    _, _, transform, _ = _inputs(graphs)
    batch = next(iter(DataLoader(list(graphs.values())[:1], batch_size=1)))

    with pytest.raises(CompositionalReconstructionError):
        _bio_loss(
            torch.tensor([[0.0, 0.0, 1_000_000.0]]),
            batch,
            transform,
            (_violated_test_constraint(),),
        )


def test_training_propagates_reconstruction_error(
    graphs: dict[str, HeteroData], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        compositional_training, "structural_constraints", lambda: (_violated_test_constraint(),)
    )
    train, val, transform, _ = _inputs(graphs)
    model = _model(graphs)
    forward = model.forward

    def unrepresentable_output(batch: HeteroData) -> torch.Tensor:
        output = forward(batch)
        return torch.cat((output[:, :2], torch.full_like(output[:, 2:], 1_000_000.0)), dim=1)

    model.forward = unrepresentable_output
    config = _config(constraint_lambda=1.0, constraint_terms=[CONSTRAINT_NAME])

    with pytest.raises(CompositionalReconstructionError):
        train_compositional_model(model, train, val, config, transform)


def test_classic_training_loop_rejects_positive_constraint_lambda(
    graphs: dict[str, HeteroData],
) -> None:
    from nutrigraphdt.models.training.loop import train_model
    from nutrigraphdt.models.training.pipeline import run_training

    config = _config(constraint_lambda=1.0, constraint_terms=[CONSTRAINT_NAME])
    with pytest.raises(ValueError, match="no admite constraint_lambda > 0"):
        train_model(
            _model(graphs),
            object(),  # The configuration rejection happens before loader use.
            config,
        )
    with pytest.raises(ValueError, match="no admite constraint_lambda > 0"):
        run_training(
            object(),  # The pipeline rejects before inspecting prepared data.
            object(),
            config,
            object(),
            split_file=None,
        )
