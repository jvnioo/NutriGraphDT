"""Tests del bucle de entrenamiento con detención temprana (A44-3, #97).

Requiere el extra `graph`.
"""

from __future__ import annotations

import dataclasses

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from torch_geometric.data import HeteroData  # noqa: E402
from torch_geometric.loader import DataLoader  # noqa: E402

from nutrigraphdt.data.split import DatasetSplit, create_split  # noqa: E402
from nutrigraphdt.graph.heterodata import build_synthetic_graphs  # noqa: E402
from nutrigraphdt.graph.validation.pipeline import GraphRecords  # noqa: E402
from nutrigraphdt.models.baselines import build_synthetic_cohort  # noqa: E402
from nutrigraphdt.models.gnn import (  # noqa: E402
    HeteroSAGE,
    HomoSAGEConfig,
    ModelConfig,
    build_model,
)
from nutrigraphdt.models.training import (  # noqa: E402
    SELECTION_METRIC,
    FeatureScaler,
    IdentityTargetScaler,
    NonFiniteError,
    PreparedDataLoaders,
    TargetScaler,
    TrainingConfig,
    TrainingResult,
    predict,
    prepare_training_graphs,
    set_seed,
    train_model,
)

N_SAMPLES = 16
SEED = 42
BATCH_SIZE = 4

CohortGraphs = tuple[GraphRecords, dict[str, HeteroData], DatasetSplit]


@pytest.fixture(scope="module")
def cohort_graphs() -> CohortGraphs:
    cohort = build_synthetic_cohort(N_SAMPLES, first_seed=1)
    split = create_split(
        [
            {"sample_id": inst.sample_id, "diet_treatment": inst.diet_treatment}
            for inst in cohort.instances
        ],
        group_key=None,
        stratify_key="diet_treatment",
        seed=SEED,
    )
    built = build_synthetic_graphs(cohort)
    return built.dataset, dict(built.graphs), split


def _config(**overrides: object) -> TrainingConfig:
    values: dict[str, object] = {
        "lr": 1e-2,
        "weight_decay": 1e-4,
        "batch_size": BATCH_SIZE,
        "max_epochs": 30,
        "patience": 30,
        "seed": SEED,
        "dataset_id": "synthetic_cohort",
        "split_file": "configs/splits/d1_holofood.json",
    }
    values.update(overrides)
    return TrainingConfig.model_validate(values)


def _loaders(cohort_graphs: CohortGraphs) -> PreparedDataLoaders:
    """`DataLoader` con features escaladas con `train` (A44-2) y target en unidades de la fuente."""
    records, graphs, split = cohort_graphs
    prepared = prepare_training_graphs(records, graphs, split, batch_size=BATCH_SIZE, seed=SEED)
    scaler = FeatureScaler.fit(prepared.graphs["train"])
    scaled = scaler.transform_subsets(prepared.graphs)
    return dataclasses.replace(
        prepared,
        train=DataLoader(
            scaled["train"],
            batch_size=BATCH_SIZE,
            shuffle=True,
            generator=torch.Generator().manual_seed(SEED),
        ),
        val=DataLoader(scaled["val"], batch_size=BATCH_SIZE),
        test=DataLoader(scaled["test"], batch_size=BATCH_SIZE),
        graphs={subset: tuple(items) for subset, items in scaled.items()},
    )


def _train(
    loaders: PreparedDataLoaders, config: TrainingConfig, *, scaled_target: bool = True
) -> TrainingResult:
    set_seed(config.seed)
    model = build_model(HomoSAGEConfig(variant="homo_sage", hidden_channels=16), loaders.metadata)
    target_scaler = TargetScaler.fit(list(loaders.graphs["train"])) if scaled_target else None
    return train_model(model, loaders, config, target_scaler)


def test_training_loss_decreases_on_small_synthetic_cohort(cohort_graphs: CohortGraphs) -> None:
    result = _train(_loaders(cohort_graphs), _config())

    losses = [record.train_loss for record in result.history]
    assert len(losses) == 30
    assert losses[-1] < losses[0]
    assert all(torch.isfinite(torch.tensor(losses)))


def test_altering_test_produces_the_same_model(cohort_graphs: CohortGraphs) -> None:
    reference = _train(_loaders(cohort_graphs), _config(max_epochs=8))

    loaders = _loaders(cohort_graphs)
    altered = []
    for graph in loaders.graphs["test"]:
        copy = graph.clone()
        copy.y_graph = copy.y_graph * 100.0 + 7.0
        for node_type in copy.node_types:
            if "x" in copy[node_type]:
                copy[node_type].x = torch.randn_like(copy[node_type].x) * 50.0
        altered.append(copy)
    loaders = dataclasses.replace(loaders, test=DataLoader(altered, batch_size=BATCH_SIZE))
    result = _train(loaders, _config(max_epochs=8))

    assert result.history == reference.history
    expected = reference.model.state_dict()
    for name, value in result.model.state_dict().items():
        assert torch.equal(value, expected[name]), name


def test_best_epoch_weights_are_restored(cohort_graphs: CohortGraphs) -> None:
    loaders = _loaders(cohort_graphs)
    config = _config(lr=5e-2, max_epochs=25)
    set_seed(config.seed)
    model = build_model(HomoSAGEConfig(variant="homo_sage", hidden_channels=16), loaders.metadata)
    target_scaler = TargetScaler.fit(list(loaders.graphs["train"]))
    result = train_model(model, loaders, config, target_scaler)

    best = result.history[result.best_epoch - 1]
    assert best.improved
    assert result.best_val_rmse == min(record.val_rmse for record in result.history)
    report = predict(result.model, loaders.val, target_scaler).evaluate("gnn", split="val")
    rmse = report.get_row("rmse")
    assert rmse is not None
    assert rmse.average == pytest.approx(result.best_val_rmse, rel=1e-6)


def test_early_stopping_after_patience_epochs_without_improvement(
    cohort_graphs: CohortGraphs,
) -> None:
    result = _train(_loaders(cohort_graphs), _config(lr=0.5, max_epochs=200, patience=3))

    assert result.stopped_early
    assert result.epochs_run < 200
    assert result.epochs_run == result.best_epoch + 3
    assert not any(record.improved for record in result.history[-3:])


def test_identity_scaling_trains_without_a44_2(cohort_graphs: CohortGraphs) -> None:
    loaders = _loaders(cohort_graphs)
    result = _train(loaders, _config(max_epochs=3), scaled_target=False)

    assert result.epochs_run == 3
    predictions = predict(result.model, loaders.val)
    assert predictions.predicted.shape == (len(loaders.graphs["val"]), 3)
    assert bool(torch.isfinite(predictions.predicted).all())


def test_history_records_train_loss_and_val_metrics(cohort_graphs: CohortGraphs) -> None:
    result = _train(_loaders(cohort_graphs), _config(max_epochs=2))

    row = result.history[0].to_dict()
    assert row["epoch"] == 1
    for key in ("train_loss", "val_loss", "val_rmse_average", "val_mae_acetate", "val_r2_butyrate"):
        assert key in row
    assert result.history[0].val_rmse == result.history[0].val_metrics[SELECTION_METRIC]


def test_predict_returns_measured_and_predicted_in_source_units(
    cohort_graphs: CohortGraphs,
) -> None:
    loaders = _loaders(cohort_graphs)
    target_scaler = TargetScaler.fit(list(loaders.graphs["train"]))
    set_seed(SEED)
    model = build_model(HomoSAGEConfig(variant="homo_sage", hidden_channels=16), loaders.metadata)

    predictions = predict(model, loaders.val, target_scaler)

    val_graphs = loaders.graphs["val"]
    assert predictions.sample_ids == tuple(str(graph.sample_id) for graph in val_graphs)
    assert torch.equal(predictions.measured, torch.cat([graph.y_graph for graph in val_graphs]))
    model.eval()
    with torch.no_grad():
        scaled = torch.cat([model(batch) for batch in loaders.val])
    assert torch.allclose(predictions.predicted, target_scaler.inverse_transform(scaled))
    assert model.training is False
    records = predictions.to_records("val")
    assert records[0]["subset"] == "val"
    assert set(records[0]) >= {"sample_id", "measured_acetate", "predicted_butyrate"}


def test_predict_restores_training_mode(cohort_graphs: CohortGraphs) -> None:
    loaders = _loaders(cohort_graphs)
    set_seed(SEED)
    model = build_model(HomoSAGEConfig(variant="homo_sage", hidden_channels=16), loaders.metadata)
    model.train()

    predict(model, loaders.val)

    assert model.training


def test_non_finite_features_stop_training_with_clear_error(cohort_graphs: CohortGraphs) -> None:
    loaders = _loaders(cohort_graphs)
    broken = [graph.clone() for graph in loaders.graphs["train"]]
    node_type = next(t for t in broken[0].node_types if broken[0][t].x.size(1) > 0)
    broken[0][node_type].x[0, 0] = float("nan")
    loaders = dataclasses.replace(loaders, train=DataLoader(broken, batch_size=BATCH_SIZE))

    with pytest.raises(NonFiniteError, match="NaN o infinitos"):
        _train(loaders, _config(max_epochs=2))


def test_val_without_complete_samples_is_rejected(cohort_graphs: CohortGraphs) -> None:
    loaders = _loaders(cohort_graphs)
    partial = []
    for graph in loaders.graphs["val"]:
        copy = graph.clone()
        copy.y_graph_mask = torch.tensor([[True, False, True]])
        partial.append(copy)
    loaders = dataclasses.replace(loaders, val=DataLoader(partial, batch_size=BATCH_SIZE))

    with pytest.raises(ValueError, match="detención temprana"):
        _train(loaders, _config(max_epochs=1))


def test_lazy_parameters_are_initialized_before_the_optimizer(cohort_graphs: CohortGraphs) -> None:
    loaders = _loaders(cohort_graphs)
    set_seed(SEED)
    model = HeteroSAGE(loaders.metadata, ModelConfig(hidden_channels=16))
    assert any(isinstance(p, torch.nn.parameter.UninitializedParameter) for p in model.parameters())

    result = train_model(model, loaders, _config(max_epochs=2))

    assert result.epochs_run == 2
    assert not any(
        isinstance(p, torch.nn.parameter.UninitializedParameter) for p in model.parameters()
    )


def test_identity_target_scaler_masks_missing_cells() -> None:
    scaler = IdentityTargetScaler()
    y = torch.tensor([[1.0, 2.0, 3.0]])
    mask = torch.tensor([[True, False, True]])

    assert torch.equal(scaler.transform(y, mask), torch.tensor([[1.0, 0.0, 3.0]]))
    assert torch.equal(scaler.inverse_transform(y), y)
