"""Tests de la trazabilidad de corridas (A44-5, #99).

Requiere el extra `graph`.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from torch_geometric.data import HeteroData  # noqa: E402
from torch_geometric.loader import DataLoader  # noqa: E402

from nutrigraphdt.data.split import DatasetSplit, create_split  # noqa: E402
from nutrigraphdt.graph.heterodata import build_synthetic_graphs  # noqa: E402
from nutrigraphdt.models.baselines import build_synthetic_cohort  # noqa: E402
from nutrigraphdt.models.gnn import SCFAGraphModel, build_model, parse_model_config  # noqa: E402
from nutrigraphdt.models.metrics import DEFAULT_SCFA_TARGETS, evaluate_predictions  # noqa: E402
from nutrigraphdt.models.training import (  # noqa: E402
    FeatureScaler,
    PreparedDataLoaders,
    TargetScaler,
    TrainingConfig,
    prepare_training_graphs,
    set_seed,
)
from nutrigraphdt.models.training.tracking import (  # noqa: E402
    CHECKPOINT_FILE,
    HISTORY_FILE,
    METRICS_FILE,
    PREDICTIONS_FILE,
    RUN_FILE,
    RunRecord,
    git_info,
    load_run,
    make_run_id,
    read_rows,
    save_run,
    split_info,
)

NOW = datetime(2026, 10, 14, 15, 30, 5, tzinfo=UTC)
SUBSETS = ("train", "val", "test")


@pytest.fixture(scope="module")
def prepared() -> tuple[PreparedDataLoaders, DatasetSplit]:
    cohort = build_synthetic_cohort(10, first_seed=1)
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
    return prepare_training_graphs(built.dataset, built.graphs, split, batch_size=4), split


def _training_config(**overrides: Any) -> TrainingConfig:
    values: dict[str, Any] = {
        "lr": 1e-3,
        "weight_decay": 1e-4,
        "batch_size": 4,
        "max_epochs": 2,
        "patience": 2,
        "seed": 7,
        "dataset_id": "synthetic_cohort",
        "split_file": "configs/splits/d1_holofood.json",
    }
    values.update(overrides)
    return TrainingConfig.model_validate(values)


def _predict_rows(
    model: SCFAGraphModel,
    graphs: dict[str, list[HeteroData]],
    feature_scaler: FeatureScaler,
    target_scaler: TargetScaler,
) -> list[dict[str, Any]]:
    """Filas de `predictions.csv` con el mismo formato que `Predictions.to_records` (A44-3)."""
    rows: list[dict[str, Any]] = []
    model.eval()
    for subset in SUBSETS:
        loader = DataLoader(feature_scaler.transform(graphs[subset]), batch_size=4)
        with torch.no_grad():
            for batch in loader:
                predicted = target_scaler.inverse_transform(model(batch)).tolist()
                measured = batch.y_graph.tolist()
                mask = batch.y_graph_mask.tolist()
                for row, sample_id in enumerate(batch.sample_id):
                    record: dict[str, Any] = {
                        "sample_id": sample_id,
                        "graph_id": batch.graph_id[row],
                        "subset": subset,
                    }
                    for column, target in enumerate(DEFAULT_SCFA_TARGETS):
                        record[f"measured_{target}"] = (
                            measured[row][column] if mask[row][column] else None
                        )
                    for column, target in enumerate(DEFAULT_SCFA_TARGETS):
                        record[f"predicted_{target}"] = predicted[row][column]
                    rows.append(record)
    return rows


def _record(
    prepared: tuple[PreparedDataLoaders, DatasetSplit],
    variant: str = "homo_sage",
    *,
    split_file: str | Path | None = None,
) -> tuple[RunRecord, dict[str, list[HeteroData]]]:
    loaders, split = prepared
    graphs = {subset: list(loaders.graphs[subset]) for subset in SUBSETS}
    feature_scaler = FeatureScaler.fit(graphs["train"])
    target_scaler = TargetScaler.fit(graphs["train"])
    config = _training_config()
    set_seed(config.seed)
    model_config = parse_model_config({"variant": variant, "hidden_channels": 8})
    model = build_model(model_config, loaders.metadata)
    with torch.no_grad():  # pesos distintos de la inicialización, como tras entrenar
        for parameter in model.parameters():
            parameter.add_(0.01 * torch.randn_like(parameter))
    rows = _predict_rows(model, graphs, feature_scaler, target_scaler)
    test_rows = [row for row in rows if row["subset"] == "test"]
    report = evaluate_predictions(
        [[row[f"measured_{t}"] for t in DEFAULT_SCFA_TARGETS] for row in test_rows],
        [[row[f"predicted_{t}"] for t in DEFAULT_SCFA_TARGETS] for row in test_rows],
        variant,
        split="test",
    )
    history = [
        {"epoch": 1, "train_loss": 1.25, "val_loss": 1.5, "val_rmse_average": 3.0},
        {"epoch": 2, "train_loss": 0.75, "val_loss": 1.25, "val_rmse_average": 2.5},
    ]
    record = RunRecord(
        model=model,
        model_config=model_config,
        training_config=config,
        feature_scaler=feature_scaler,
        target_scaler=target_scaler,
        split=split,
        split_file=split_file,
        summary=loaders.summary,
        history=history,
        metrics=report,
        predictions=rows,
        best_epoch=2,
        stopped_early=False,
        duration_seconds=1.5,
        source={"kind": "synthetic", "n_samples": 10},
    )
    return record, graphs


@pytest.mark.parametrize("variant", ["homo_sage", "hetero_gat"])
def test_load_run_reproduces_predictions_exactly(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path, variant: str
) -> None:
    record, graphs = _record(prepared, variant)
    run_dir = save_run(record, tmp_path / "runs", repo_root=tmp_path, now=NOW)

    torch.manual_seed(123)  # otra inicialización: los pesos tienen que venir del checkpoint
    loaded = load_run(run_dir)
    rows = _predict_rows(loaded.model, graphs, loaded.feature_scaler, loaded.target_scaler)

    saved = read_rows(run_dir / PREDICTIONS_FILE)
    assert len(saved) == len(rows) == sum(len(graphs[s]) for s in SUBSETS)
    for saved_row, row in zip(saved, rows, strict=True):
        assert saved_row["sample_id"] == row["sample_id"]
        assert saved_row["subset"] == row["subset"]
        for target in DEFAULT_SCFA_TARGETS:
            assert float(saved_row[f"predicted_{target}"]) == row[f"predicted_{target}"]
            assert float(saved_row[f"measured_{target}"]) == row[f"measured_{target}"]
    assert not loaded.model.training


def test_run_directory_has_every_file_and_the_effective_configuration(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path
) -> None:
    record, _ = _record(prepared)
    run_dir = save_run(record, tmp_path / "runs", repo_root=tmp_path, now=NOW)

    assert run_dir.name == "20261014-153005_homo_sage_s7"
    for name in (RUN_FILE, HISTORY_FILE, METRICS_FILE, PREDICTIONS_FILE, CHECKPOINT_FILE):
        assert (run_dir / name).is_file(), name
    info = json.loads((run_dir / RUN_FILE).read_text(encoding="utf-8"))
    assert info["training_config"] == record.training_config.model_dump(mode="json")
    assert info["model_config"]["variant"] == "homo_sage"
    assert info["model_config"]["hidden_channels"] == 8
    assert info["seed"] == 7
    assert info["dataset_id"] == "synthetic_cohort"
    assert info["training_config"]["constraint_lambda"] == 0.0
    assert info["training_config"]["constraint_terms"] == []
    assert info["constraint_lambda"] == 0.0
    assert info["constraint_terms"] == []
    info.pop("constraints_contract_version")
    assert (
        not {
            "nonnegativity_policy_version",
            "nonnegativity_policy",
            "unrepresentable_output",
        }
        & info.keys()
    )
    assert info["source"] == {"kind": "synthetic", "n_samples": 10}
    assert info["best_epoch"] == 2
    assert info["epochs_run"] == 2
    assert info["duration_seconds"] == 1.5
    assert info["split"]["version"] == record.split.version
    assert len(info["split"]["sha256"]) == 64
    assert info["subsets"]["train"]["deliverable"] == record.summary["train"].deliverable
    assert set(info["scaling"]) == {"feature_scaler", "target_scaler"}
    assert set(info["environment"]) >= {"python", "torch", "torch_geometric"}
    assert set(info["git"]) == {"commit", "dirty"}


def test_history_and_metrics_files(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path
) -> None:
    record, _ = _record(prepared)
    run_dir = save_run(record, tmp_path / "runs", repo_root=tmp_path, now=NOW)

    history = read_rows(run_dir / HISTORY_FILE)
    assert [row["epoch"] for row in history] == ["1", "2"]
    assert float(history[1]["train_loss"]) == 0.75
    assert (run_dir / METRICS_FILE).read_bytes() == record.metrics.to_csv().encode("utf-8")


def test_record_has_no_absolute_paths_or_raw_data(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    split_file = repo / "configs" / "splits" / "split.json"
    prepared[1].save(split_file)
    record, _ = _record(prepared, split_file=split_file)
    run_dir = save_run(record, repo / "runs", repo_root=repo, now=NOW)

    for name in (RUN_FILE, HISTORY_FILE, METRICS_FILE, PREDICTIONS_FILE):
        text = (run_dir / name).read_text(encoding="utf-8")
        assert str(tmp_path) not in text, name
        assert str(Path.home()) not in text, name
        assert "raw_attributes" not in text, name
    info = json.loads((run_dir / RUN_FILE).read_text(encoding="utf-8"))
    assert info["split"]["file"] == "configs/splits/split.json"


def test_split_outside_the_repository_is_recorded_by_name(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path
) -> None:
    split_file = tmp_path / "elsewhere" / "split.json"
    prepared[1].save(split_file)
    record, _ = _record(prepared, split_file=split_file)
    run_dir = save_run(record, tmp_path / "runs", repo_root=tmp_path / "repo", now=NOW)

    info = json.loads((run_dir / RUN_FILE).read_text(encoding="utf-8"))
    assert info["split"]["file"] == "split.json"


def test_same_run_id_is_not_overwritten(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path
) -> None:
    record, _ = _record(prepared)
    save_run(record, tmp_path / "runs", repo_root=tmp_path, now=NOW)

    with pytest.raises(FileExistsError):
        save_run(record, tmp_path / "runs", repo_root=tmp_path, now=NOW)


def test_run_id_uses_utc_time_variant_and_seed() -> None:
    assert make_run_id("hetero_gat", 42, NOW) == "20261014-153005_hetero_gat_s42"


def test_git_info_outside_a_repository(tmp_path: Path) -> None:
    assert git_info(tmp_path) == {"commit": None, "dirty": None}


def test_load_run_rejects_an_incompatible_format(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path
) -> None:
    record, _ = _record(prepared)
    run_dir = save_run(record, tmp_path / "runs", repo_root=tmp_path, now=NOW)
    info = json.loads((run_dir / RUN_FILE).read_text(encoding="utf-8"))
    info["format_version"] = "2.0.0"
    (run_dir / RUN_FILE).write_text(json.dumps(info), encoding="utf-8")

    with pytest.raises(ValueError, match="no compatible"):
        load_run(run_dir)


def test_split_hash_is_the_same_for_lf_and_crlf_files_and_without_file(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path
) -> None:
    """#133: el hash registrado no depende del fin de línea del archivo de partición."""
    split = prepared[1]
    lf = tmp_path / "lf.json"
    split.save(lf)
    crlf = tmp_path / "crlf.json"
    crlf.write_bytes(lf.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))

    hashes = {
        split_info(split, lf, tmp_path)["sha256"],
        split_info(split, crlf, tmp_path)["sha256"],
        split_info(split, None, tmp_path)["sha256"],
    }
    assert len(hashes) == 1


def test_checkpoint_holds_exactly_the_weights_of_the_saved_model(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path
) -> None:
    record, _ = _record(prepared)
    run_dir = save_run(record, tmp_path / "runs", repo_root=tmp_path, now=NOW)

    state = torch.load(run_dir / CHECKPOINT_FILE, weights_only=True)
    expected = record.model.state_dict()
    assert set(state) == set(expected)
    for name, value in state.items():
        assert value.device.type == "cpu", name
        assert torch.equal(value, expected[name].cpu()), name


def test_loaded_run_exposes_its_id_and_configuration(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path
) -> None:
    record, _ = _record(prepared)
    run_dir = save_run(record, tmp_path / "runs", repo_root=tmp_path, now=NOW)

    loaded = load_run(run_dir)

    assert loaded.run_id == run_dir.name
    assert loaded.model_config == record.model_config
    assert loaded.training_config == record.training_config
    assert loaded.target_scaler.mean_tuple == record.target_scaler.mean_tuple
    assert loaded.feature_scaler.stats == record.feature_scaler.stats


def test_load_run_applies_defaults_to_legacy_training_config(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path
) -> None:
    record, _ = _record(prepared)
    run_dir = save_run(record, tmp_path / "runs", repo_root=tmp_path, now=NOW)
    info = json.loads((run_dir / RUN_FILE).read_text(encoding="utf-8"))
    info["training_config"].pop("constraint_lambda")
    info["training_config"].pop("constraint_terms")
    info.pop("constraint_lambda")
    info.pop("constraint_terms")
    assert info["constraints_contract_version"] == "1.0.0"
    (run_dir / RUN_FILE).write_text(json.dumps(info), encoding="utf-8")

    loaded = load_run(run_dir)

    assert loaded.training_config.constraint_lambda == 0.0
    assert loaded.training_config.constraint_terms == ()


def test_load_run_restores_composite_loss_configuration(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path
) -> None:
    record, _ = _record(prepared)
    config = _training_config(
        constraint_lambda=0.25,
        constraint_terms=("structural.simplex_closure",),
    )
    run_dir = save_run(
        replace(record, training_config=config), tmp_path / "runs", repo_root=tmp_path, now=NOW
    )
    info = json.loads((run_dir / RUN_FILE).read_text(encoding="utf-8"))

    loaded = load_run(run_dir)

    assert info["constraint_lambda"] == 0.25
    assert info["constraint_terms"] == ["structural.simplex_closure"]
    assert loaded.training_config.constraint_lambda == 0.25
    assert loaded.training_config.constraint_terms == ("structural.simplex_closure",)


def test_load_run_without_checkpoint_fails(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path
) -> None:
    record, _ = _record(prepared)
    run_dir = save_run(record, tmp_path / "runs", repo_root=tmp_path, now=NOW)
    (run_dir / CHECKPOINT_FILE).unlink()

    with pytest.raises(FileNotFoundError):
        load_run(run_dir)


def test_checkpoint_that_does_not_match_the_configuration_is_rejected(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path
) -> None:
    """Los pesos no se cargan a medias en una arquitectura distinta de la registrada."""
    record, _ = _record(prepared)
    run_dir = save_run(record, tmp_path / "runs", repo_root=tmp_path, now=NOW)
    info = json.loads((run_dir / RUN_FILE).read_text(encoding="utf-8"))
    info["model_config"]["hidden_channels"] = 16
    (run_dir / RUN_FILE).write_text(json.dumps(info), encoding="utf-8")

    with pytest.raises(RuntimeError, match="size mismatch"):
        load_run(run_dir)


def test_checkpoint_with_missing_weights_is_rejected(
    prepared: tuple[PreparedDataLoaders, DatasetSplit], tmp_path: Path
) -> None:
    record, _ = _record(prepared)
    run_dir = save_run(record, tmp_path / "runs", repo_root=tmp_path, now=NOW)
    state = torch.load(run_dir / CHECKPOINT_FILE, weights_only=True)
    state.pop(next(iter(state)))
    torch.save(state, run_dir / CHECKPOINT_FILE)

    with pytest.raises(RuntimeError, match="Missing key"):
        load_run(run_dir)
