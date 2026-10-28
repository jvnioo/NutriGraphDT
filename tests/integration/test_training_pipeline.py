"""Integración de `run_training` sobre la cohorte sintética (A52-P3, #154).

Escalado con `train`, entrenamiento, registro de la corrida y recarga sin reentrenar, dentro del
proceso y sin descargas. Requiere el extra `graph`.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from torch_geometric.loader import DataLoader  # noqa: E402

from nutrigraphdt.data.split import DatasetSplit, create_split  # noqa: E402
from nutrigraphdt.graph.heterodata import build_synthetic_graphs  # noqa: E402
from nutrigraphdt.models.baselines import build_synthetic_cohort  # noqa: E402
from nutrigraphdt.models.gnn import parse_model_config  # noqa: E402
from nutrigraphdt.models.metrics import DEFAULT_SCFA_TARGETS  # noqa: E402
from nutrigraphdt.models.training import (  # noqa: E402
    PreparedDataLoaders,
    TrainingConfig,
    predict,
    prepare_training_graphs,
)
from nutrigraphdt.models.training.pipeline import SUBSETS, TrainingRun, run_training  # noqa: E402
from nutrigraphdt.models.training.tracking import (  # noqa: E402
    CHECKPOINT_FILE,
    PREDICTIONS_FILE,
    RUN_FILE,
    load_run,
    read_rows,
)

SEED = 7
BATCH_SIZE = 4


@pytest.fixture(scope="module")
def prepared() -> tuple[PreparedDataLoaders, DatasetSplit]:
    cohort = build_synthetic_cohort(12, first_seed=1)
    split = create_split(
        [
            {"sample_id": inst.sample_id, "diet_treatment": inst.diet_treatment}
            for inst in cohort.instances
        ],
        group_key=None,
        stratify_key="diet_treatment",
        seed=42,
        dataset_id="synthetic_cohort",
    )
    built = build_synthetic_graphs(cohort)
    loaders = prepare_training_graphs(
        built.dataset, built.graphs, split, batch_size=BATCH_SIZE, seed=SEED
    )
    return loaders, split


def _run(
    prepared: PreparedDataLoaders, split: DatasetSplit, runs_dir: Path, **overrides: Any
) -> TrainingRun:
    values: dict[str, Any] = {
        "lr": 1e-2,
        "weight_decay": 1e-4,
        "batch_size": BATCH_SIZE,
        "max_epochs": 3,
        "patience": 3,
        "seed": SEED,
        "dataset_id": "synthetic_cohort",
        "split_file": "configs/splits/d1_holofood.json",
    }
    values.update(overrides)
    return run_training(
        prepared,
        parse_model_config({"variant": "homo_sage", "hidden_channels": 8}),
        TrainingConfig.model_validate(values),
        split,
        split_file=None,
        runs_dir=runs_dir,
        repo_root=runs_dir.parent,
        source={"kind": "synthetic", "n_samples": 12},
    )


def _with_graphs(prepared: PreparedDataLoaders, **graphs: Any) -> PreparedDataLoaders:
    return dataclasses.replace(prepared, graphs={**prepared.graphs, **graphs})


def test_reloaded_run_predicts_exactly_what_it_recorded(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path
) -> None:
    loaders, split = prepared
    run = _run(loaders, split, tmp_path / "runs")

    loaded = load_run(run.run_dir)
    saved = read_rows(run.run_dir / PREDICTIONS_FILE)
    assert [row["subset"] for row in saved] == [
        subset for subset in SUBSETS for _ in loaders.graphs[subset]
    ]
    for subset in SUBSETS:
        graphs = loaded.feature_scaler.transform(loaders.graphs[subset])
        predictions = predict(
            loaded.model, DataLoader(graphs, batch_size=BATCH_SIZE), loaded.target_scaler
        )
        rows = [row for row in saved if row["subset"] == subset]
        assert [row["sample_id"] for row in rows] == list(predictions.sample_ids)
        for row, values in zip(rows, predictions.predicted.tolist(), strict=True):
            for target, value in zip(DEFAULT_SCFA_TARGETS, values, strict=True):
                assert float(row[f"predicted_{target}"]) == value


def test_same_seed_reproduces_the_checkpoint_and_predictions(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path
) -> None:
    loaders, split = prepared
    first = _run(loaders, split, tmp_path / "a")
    second = _run(loaders, split, tmp_path / "b")

    a = torch.load(first.run_dir / CHECKPOINT_FILE, weights_only=True)
    b = torch.load(second.run_dir / CHECKPOINT_FILE, weights_only=True)
    assert set(a) == set(b)
    for name in a:
        assert torch.equal(a[name], b[name]), name
    assert (first.run_dir / PREDICTIONS_FILE).read_bytes() == (
        second.run_dir / PREDICTIONS_FILE
    ).read_bytes()
    assert first.result.history == second.result.history


def test_another_seed_changes_the_trained_weights(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path
) -> None:
    """Control del test anterior: la semilla sí determina los pesos."""
    loaders, split = prepared
    first = _run(loaders, split, tmp_path / "a")
    other = _run(loaders, split, tmp_path / "b", seed=SEED + 1)

    a = torch.load(first.run_dir / CHECKPOINT_FILE, weights_only=True)
    b = torch.load(other.run_dir / CHECKPOINT_FILE, weights_only=True)
    assert any(not torch.equal(a[name], b[name]) for name in a)


def test_scaling_is_fitted_with_train_only(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path
) -> None:
    loaders, split = prepared
    reference = _run(loaders, split, tmp_path / "reference", max_epochs=1, patience=1)

    altered = {}
    for subset in ("val", "test"):
        graphs = []
        for graph in loaders.graphs[subset]:
            copy = graph.clone()
            copy.y_graph = copy.y_graph * 100.0 + 7.0
            for node_type in copy.node_types:
                if "x" in copy[node_type] and copy[node_type].x.numel():
                    copy[node_type].x = copy[node_type].x * 50.0 + 3.0
            graphs.append(copy)
        altered[subset] = tuple(graphs)
    run = _run(
        _with_graphs(loaders, **altered), split, tmp_path / "altered", max_epochs=1, patience=1
    )

    def scaling(run: TrainingRun) -> Any:
        return json.loads((run.run_dir / RUN_FILE).read_text(encoding="utf-8"))["scaling"]

    assert scaling(run) == scaling(reference)


def test_subset_without_graphs_is_left_out_of_predictions_and_metrics(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path
) -> None:
    loaders, split = prepared
    run = _run(_with_graphs(loaders, test=()), split, tmp_path / "runs", max_epochs=1, patience=1)

    saved = read_rows(run.run_dir / PREDICTIONS_FILE)
    assert {row["subset"] for row in saved} == {"train", "val"}
    assert {row.split for row in run.report.rows} == {"train", "val"}


def test_empty_train_is_rejected_before_training(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path
) -> None:
    loaders, split = prepared

    with pytest.raises(ValueError, match="train no tiene grafos"):
        _run(_with_graphs(loaders, train=()), split, tmp_path / "runs")
    assert not (tmp_path / "runs").exists()
