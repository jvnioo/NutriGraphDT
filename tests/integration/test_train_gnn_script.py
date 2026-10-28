"""Prueba de integración de `scripts/train_gnn.py` (A44-6, #100).

Entrena 2 épocas sobre una cohorte sintética mínima en un proceso independiente y verifica los
archivos de la corrida. Requiere el extra `graph`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from torch_geometric.loader import DataLoader  # noqa: E402

from nutrigraphdt.data.split import create_split  # noqa: E402
from nutrigraphdt.graph.heterodata import build_synthetic_graphs  # noqa: E402
from nutrigraphdt.models.baselines import SYNTHETIC_COHORT_ID, build_synthetic_cohort  # noqa: E402
from nutrigraphdt.models.training import load_run, predict, prepare_training_graphs  # noqa: E402
from nutrigraphdt.models.training.tracking import (  # noqa: E402
    CHECKPOINT_FILE,
    HISTORY_FILE,
    METRICS_FILE,
    PREDICTIONS_FILE,
    RUN_FILE,
    read_rows,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "train_gnn.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        cwd=REPO_ROOT,
        check=False,
    )


@pytest.mark.parametrize("model", ["homo_sage", "hetero_gat"])
def test_two_epochs_on_a_minimal_synthetic_cohort(tmp_path: Path, model: str) -> None:
    runs = tmp_path / "runs"
    completed = _run(
        "--model",
        model,
        "--dataset",
        "synthetic",
        "--n-samples",
        "10",
        "--max-epochs",
        "2",
        "--runs-dir",
        str(runs),
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    (run_dir,) = runs.iterdir()
    assert run_dir.name.endswith(f"_{model}_s42")
    for name in (RUN_FILE, HISTORY_FILE, METRICS_FILE, PREDICTIONS_FILE, CHECKPOINT_FILE):
        assert (run_dir / name).is_file(), name

    info = json.loads((run_dir / RUN_FILE).read_text(encoding="utf-8"))
    assert info["variant"] == model
    assert info["dataset_id"] == SYNTHETIC_COHORT_ID
    assert info["training_config"]["max_epochs"] == 2
    assert info["epochs_run"] == 2
    assert info["source"] == {
        "dataset": "synthetic",
        "n_samples": 10,
        "first_seed": 1,
        "split_seed": 42,
    }
    assert info["split"]["file"] is None
    assert info["environment"]["device"] == "cpu"
    assert "device_name" not in info["environment"]
    assert str(tmp_path) not in (run_dir / RUN_FILE).read_text(encoding="utf-8")

    assert len(read_rows(run_dir / HISTORY_FILE)) == 2
    predictions = read_rows(run_dir / PREDICTIONS_FILE)
    counts = {subset: info["subsets"][subset]["with_any_scfa"] for subset in info["subsets"]}
    for subset, count in counts.items():
        assert sum(row["subset"] == subset for row in predictions) == count
    metrics = read_rows(run_dir / METRICS_FILE)
    assert {row["split"] for row in metrics} == {"train", "val", "test"}


def test_reloaded_run_reproduces_its_predictions(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    completed = _run(
        "--model",
        "hetero_sage",
        "--dataset",
        "synthetic",
        "--n-samples",
        "10",
        "--max-epochs",
        "2",
        "--runs-dir",
        str(runs),
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    (run_dir,) = runs.iterdir()

    cohort = build_synthetic_cohort(10, 1)
    split = create_split(
        [
            {"sample_id": inst.sample_id, "diet_treatment": inst.diet_treatment}
            for inst in cohort.instances
        ],
        group_key=None,
        stratify_key="diet_treatment",
        seed=42,
        dataset_id=SYNTHETIC_COHORT_ID,
    )
    built = build_synthetic_graphs(cohort)
    prepared = prepare_training_graphs(built.dataset, built.graphs, split, batch_size=16)
    loaded = load_run(run_dir)

    saved = read_rows(run_dir / PREDICTIONS_FILE)
    for subset in ("train", "val", "test"):
        graphs = loaded.feature_scaler.transform(prepared.graphs[subset])
        records = predict(
            loaded.model, DataLoader(graphs, batch_size=16), loaded.target_scaler
        ).to_records(subset)
        rows = [row for row in saved if row["subset"] == subset]
        assert [row["sample_id"] for row in rows] == [record["sample_id"] for record in records]
        for row, record in zip(rows, records, strict=True):
            for target in ("acetate", "propionate", "butyrate"):
                assert float(row[f"predicted_{target}"]) == record[f"predicted_{target}"]


def test_model_config_must_match_the_requested_variant(tmp_path: Path) -> None:
    completed = _run(
        "--model",
        "homo_sage",
        "--dataset",
        "synthetic",
        "--model-config",
        str(REPO_ROOT / "configs" / "models" / "hetero_gat.yaml"),
        "--runs-dir",
        str(tmp_path / "runs"),
    )

    assert completed.returncode == 2
    assert "no coincide" in completed.stderr
    assert not (tmp_path / "runs").exists()


def test_d1_without_saved_graphs_fails_with_a_clear_message(tmp_path: Path) -> None:
    completed = _run(
        "--model",
        "homo_sage",
        "--dataset",
        "d1",
        "--graphs-dir",
        str(tmp_path / "missing"),
        "--runs-dir",
        str(tmp_path / "runs"),
    )

    assert completed.returncode == 2
    assert "No se pudo preparar el entrenamiento" in completed.stderr


def test_d1_trains_only_on_the_cohort(
    tmp_path: Path, holofood_fixture_graphs: Path, holofood_fixture_sources: Path
) -> None:
    # 10000 lecturas dejan fuera a SAMEA112904764 (8187), el de menor profundidad del fixture.
    runs = tmp_path / "runs"
    completed = _run(
        "--model",
        "homo_sage",
        "--dataset",
        "d1",
        "--graphs-dir",
        str(holofood_fixture_graphs),
        "--sources",
        str(holofood_fixture_sources),
        "--min-ssu-reads",
        "10000",
        "--split-file",
        str(REPO_ROOT / "tests" / "fixtures" / "holofood" / "split.json"),
        "--max-epochs",
        "1",
        "--runs-dir",
        str(runs),
    )

    assert completed.returncode == 0, completed.stderr
    (run_dir,) = runs.iterdir()
    info = json.loads((run_dir / RUN_FILE).read_text(encoding="utf-8"))
    cohort = info["source"]["cohort"]
    assert (cohort["min_ssu_reads"], cohort["size"]) == (10000, 5)
    assert cohort["steps"][-1]["removed"] == ["SAMEA112904764"]
    subsets = info["subsets"]
    assert sum(subsets[name]["outside_cohort"] for name in ("train", "val", "test")) == 1
    assert sum(subsets[name]["with_all_scfa"] for name in ("train", "val", "test")) == 5
    predicted = {row["sample_id"] for row in read_rows(run_dir / PREDICTIONS_FILE)}
    assert "SAMEA112904764" not in predicted
    assert len(predicted) == 5
