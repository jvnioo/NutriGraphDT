"""Tests de la pérdida compuesta del entrenamiento composicional (#166)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from torch_geometric.data import HeteroData  # noqa: E402
from torch_geometric.loader import DataLoader  # noqa: E402

import nutrigraphdt.models.training.compositional as compositional_training  # noqa: E402
from nutrigraphdt.constraints import (  # noqa: E402
    D06_PROPIONATE_BOUND_NAME,
    FunctionalConstraint,
    constraint_catalog,
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
    registered = constraint_catalog()[CONSTRAINT_NAME]
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
        compositional_training,
        "constraint_catalog",
        lambda: {CONSTRAINT_NAME: _violated_test_constraint()},
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


def test_d06_constraint_is_used_by_training_with_positive_lambda(
    graphs: dict[str, HeteroData],
) -> None:
    train, val, transform, _ = _inputs(graphs)
    model = _model(graphs)
    forward = model.forward

    def violating_output(batch: HeteroData) -> torch.Tensor:
        output = forward(batch)
        physical_output = output.new_tensor([[math.log(6.0), 0.0, math.log(8.0)]])
        scaled_output = transform.scaler.transform(physical_output)
        return output - output.detach() + scaled_output

    model.forward = violating_output
    config = _config(
        constraint_lambda=1.0,
        constraint_terms=[D06_PROPIONATE_BOUND_NAME],
    )
    set_seed(SEED)
    result = train_compositional_model(model, train, val, config, transform)

    assert result.history[0].train_bio_loss > 0.0
    assert result.history[0].val_bio_loss > 0.0
    assert result.history[0].train_total_loss == pytest.approx(
        result.history[0].train_data_loss
        + config.constraint_lambda * result.history[0].train_bio_loss
    )


def test_masked_animals_do_not_contribute_to_bio_loss(
    graphs: dict[str, HeteroData], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        compositional_training,
        "constraint_catalog",
        lambda: {CONSTRAINT_NAME: _violated_test_constraint()},
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
        compositional_training,
        "constraint_catalog",
        lambda: {CONSTRAINT_NAME: _violated_test_constraint()},
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
        compositional_training,
        "constraint_catalog",
        lambda: {CONSTRAINT_NAME: _violated_test_constraint()},
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
        compositional_training,
        "constraint_catalog",
        lambda: {CONSTRAINT_NAME: _violated_test_constraint()},
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


# ---------------------------------------------------------------------------
# Registro separado y reanudación (A66-P1, #181)
# ---------------------------------------------------------------------------


def _resumable_config(**overrides: object) -> TrainingConfig:
    values: dict[str, object] = {
        "max_epochs": 4,
        "patience": 10,
        "constraint_lambda": 0.5,
        "constraint_terms": [CONSTRAINT_NAME],
    }
    values.update(overrides)
    return _config(**values)


def test_total_loss_is_rebuilt_from_its_logged_components(
    graphs: dict[str, HeteroData],
) -> None:
    train, val, transform, _ = _inputs(graphs)
    model = _model(graphs)
    forward = model.forward

    def violating_output(batch: HeteroData) -> torch.Tensor:
        output = forward(batch)
        physical_output = output.new_tensor([[math.log(6.0), 0.0, math.log(8.0)]])
        return output - output.detach() + transform.scaler.transform(physical_output)

    model.forward = violating_output
    config = _resumable_config(
        max_epochs=3, constraint_lambda=0.25, constraint_terms=[D06_PROPIONATE_BOUND_NAME]
    )
    set_seed(SEED)
    history = train_compositional_model(model, train, val, config, transform).history

    assert len(history) == 3
    assert all(record.train_bio_loss > 0.0 for record in history)
    for record in history:
        row = record.to_dict()
        assert row["constraint_lambda"] == 0.25
        for subset in ("train", "val"):
            assert row[f"{subset}_total_loss"] == (
                row[f"{subset}_data_loss"] + row["constraint_lambda"] * row[f"{subset}_bio_loss"]
            )


def test_resumed_training_matches_the_uninterrupted_run(
    graphs: dict[str, HeteroData], tmp_path: Path
) -> None:
    from nutrigraphdt.models.training.compositional import (
        CompositionalTrainingState,
        load_training_state,
        save_training_state,
    )

    train, val, transform, _ = _inputs(graphs)
    config = _resumable_config()
    states: list[CompositionalTrainingState] = []
    set_seed(SEED)
    uninterrupted = train_compositional_model(
        _model(graphs), train, val, config, transform, on_epoch_end=states.append
    )
    assert [state.epoch for state in states] == [1, 2, 3, 4]

    saved = save_training_state(states[1], tmp_path / "state.pt")
    set_seed(SEED + 1)  # La reanudación no depende del estado aleatorio de quien la llama.
    resumed = train_compositional_model(
        _model(graphs), train, val, config, transform, resume_from=load_training_state(saved)
    )

    assert [r.to_dict() for r in resumed.history] == [r.to_dict() for r in uninterrupted.history]
    assert (resumed.best_epoch, resumed.best_val_loss) == (
        uninterrupted.best_epoch,
        uninterrupted.best_val_loss,
    )
    for name, value in uninterrupted.model.state_dict().items():
        assert torch.equal(resumed.model.state_dict()[name], value), name


def test_resume_rejects_a_different_configuration(graphs: dict[str, HeteroData]) -> None:
    from nutrigraphdt.models.training.compositional import (
        CompositionalTrainingError,
        CompositionalTrainingState,
    )

    train, val, transform, _ = _inputs(graphs)
    states: list[CompositionalTrainingState] = []
    set_seed(SEED)
    train_compositional_model(
        _model(graphs),
        train,
        val,
        _resumable_config(max_epochs=1),
        transform,
        on_epoch_end=states.append,
    )
    with pytest.raises(CompositionalTrainingError, match="otra configuración"):
        train_compositional_model(
            _model(graphs),
            train,
            val,
            _resumable_config(constraint_lambda=1.0),
            transform,
            resume_from=states[0],
        )


def test_resume_after_early_stop_does_not_train_again(graphs: dict[str, HeteroData]) -> None:
    from nutrigraphdt.models.training.compositional import CompositionalTrainingState

    train, val, transform, _ = _inputs(graphs)
    config = _resumable_config(max_epochs=6, patience=1, lr=1e-6)
    states: list[CompositionalTrainingState] = []
    set_seed(SEED)
    first = train_compositional_model(
        _model(graphs), train, val, config, transform, on_epoch_end=states.append
    )
    stopped = states[-1]
    assert first.stopped_early and stopped.epochs_without_improvement >= config.patience

    again = train_compositional_model(
        _model(graphs), train, val, config, transform, resume_from=stopped
    )
    assert again.stopped_early
    assert [r.to_dict() for r in again.history] == [r.to_dict() for r in first.history]


# ---------------------------------------------------------------------------
# Registro de violaciones por época (A66-P3, #179)
# ---------------------------------------------------------------------------


def _log_output(acetate: float, propionate: float, butyrate: float) -> list[float]:
    """`(z_1, z_2, ln T)` de unas concentraciones en mmol/kg."""
    return [
        math.log(propionate / acetate),
        math.log(butyrate / acetate),
        math.log(acetate + propionate + butyrate),
    ]


def test_violation_log_reproduces_a_hand_computed_case() -> None:
    from nutrigraphdt.models.training.compositional import violation_log_rows

    d06 = constraint_catalog()[D06_PROPIONATE_BOUND_NAME]
    acetate_bound = constraint_catalog()[CONSTRAINT_NAME]
    # p_p = 6/8 = 0,75 → h = 3·0,75 − 2 = 0,25 (viola); p_p = 1/3 → h = −1; p_p = 1/4 → h = −1,25.
    # El cuarto animal no tiene objetivo válido: no entra en el denominador.
    output = torch.tensor(
        [
            _log_output(1.0, 6.0, 1.0),
            _log_output(1.0, 1.0, 1.0),
            _log_output(2.0, 1.0, 1.0),
            _log_output(1.0, 50.0, 1.0),
        ],
        dtype=torch.float64,
    )
    valid = torch.tensor([True, True, True, False])
    rows = violation_log_rows(
        output, valid, ["a", "b", "c", "d"], (d06, acetate_bound), epoch=3, subset="val"
    )

    d06_row, acetate_row = rows
    assert (d06_row.epoch, d06_row.subset, d06_row.constraint) == (3, "val", d06.metadata.name)
    assert (d06_row.space, d06_row.unit) == ("fractions", "1")
    assert (d06_row.sample_count, d06_row.excluded_sample_count) == (3, 1)
    assert d06_row.violation_count == 1
    assert d06_row.violation_rate_percent == pytest.approx(100.0 / 3.0)
    assert d06_row.mean_magnitude == pytest.approx(0.25 / 3.0)
    assert d06_row.conditional_mean_magnitude == pytest.approx(0.25)
    assert d06_row.worst_case_magnitude == pytest.approx(0.25)
    assert d06_row.joint_feasibility_percent == pytest.approx(200.0 / 3.0)
    assert (acetate_row.space, acetate_row.unit) == ("concentrations", "mmol/kg")
    assert acetate_row.violation_count == 0
    assert acetate_row.conditional_mean_magnitude is None


def test_monitoring_with_zero_lambda_does_not_change_training(
    graphs: dict[str, HeteroData],
) -> None:
    train, val, transform, _ = _inputs(graphs)
    config = _config(max_epochs=3, patience=10)
    monitored = tuple(constraint_catalog().values())

    set_seed(SEED)
    plain = train_compositional_model(_model(graphs), train, val, config, transform)
    set_seed(SEED)
    logged = train_compositional_model(
        _model(graphs), train, val, config, transform, monitor_constraints=monitored
    )

    assert plain.violations == ()
    assert [r.to_dict() for r in logged.history] == [r.to_dict() for r in plain.history]
    for name, value in plain.model.state_dict().items():
        assert torch.equal(logged.model.state_dict()[name], value), name
    assert len(logged.violations) == 3 * 2 * len(monitored)
    assert {(row.epoch, row.subset) for row in logged.violations} == {
        (epoch, subset) for epoch in (1, 2, 3) for subset in ("train", "val")
    }
    by_subset = {
        row.subset: row.sample_count + row.excluded_sample_count for row in logged.violations
    }
    assert by_subset == {"train": len(train), "val": len(val)}


def test_violation_log_survives_resumption(graphs: dict[str, HeteroData], tmp_path: Path) -> None:
    from nutrigraphdt.models.training.compositional import (
        CompositionalTrainingState,
        load_training_state,
        save_training_state,
    )

    train, val, transform, _ = _inputs(graphs)
    config = _resumable_config(max_epochs=3)
    monitored = (constraint_catalog()[D06_PROPIONATE_BOUND_NAME],)
    states: list[CompositionalTrainingState] = []
    set_seed(SEED)
    full = train_compositional_model(
        _model(graphs),
        train,
        val,
        config,
        transform,
        on_epoch_end=states.append,
        monitor_constraints=monitored,
    )
    assert len(states[0].violations) == 2  # train y val de la época 1

    saved = save_training_state(states[0], tmp_path / "state.pt")
    resumed = train_compositional_model(
        _model(graphs),
        train,
        val,
        config,
        transform,
        resume_from=load_training_state(saved),
        monitor_constraints=monitored,
    )
    assert resumed.violations == full.violations
