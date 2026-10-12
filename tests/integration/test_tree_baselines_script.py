"""`scripts/run_tree_baselines.py` sobre una cohorte sintética (A40-5, #75).

Comprueba el criterio de aceptación: los baselines de árboles entrenan con datos sintéticos y
reportan métricas con el formato común, y además guardan la importancia de atributos. Usa una
grilla reducida para que la prueba sea rápida. Requiere el extra `baselines`.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("sklearn")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "run_tree_baselines.py"
MODELS = ("random_forest", "hist_gradient_boosting")

SMALL_GRID = {
    "random_forest_n_estimators": [20],
    "random_forest_max_depth": [None],
    "random_forest_min_samples_leaf": [1],
    "hist_gradient_boosting_learning_rate": [0.1],
    "hist_gradient_boosting_max_iter": [20],
    "hist_gradient_boosting_max_depth": [3],
    "hist_gradient_boosting_min_samples_leaf": [2],
    "cv_folds": 3,
    "scoring": "neg_root_mean_squared_error",
    "random_state": 42,
    "permutation_repeats": 3,
}


def test_script_trains_reports_and_saves_importances(tmp_path: Path) -> None:
    config = tmp_path / "trees.json"
    config.write_text(json.dumps(SMALL_GRID), encoding="utf-8")
    output = tmp_path / "trees"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--n-samples",
            "20",
            "--config",
            str(config),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        cwd=REPO_ROOT,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr

    with (output / "report.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert {(row["model"], row["split"]) for row in rows} == {
        (model, split) for model in MODELS for split in ("val", "test")
    }

    run = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert sum(run["subset_sizes"].values()) == 20
    assert set(run["best_params"]) == set(MODELS)

    with (output / "importances.csv").open(encoding="utf-8") as handle:
        importances = list(csv.DictReader(handle))
    for model in MODELS:
        model_rows = [row for row in importances if row["model"] == model]
        assert len(model_rows) == run["n_features"]
        means = [float(row["importance_mean"]) for row in model_rows]
        assert means == sorted(means, reverse=True)
        assert {row["split"] for row in model_rows} == {"val"}
