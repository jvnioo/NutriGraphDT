"""Pruebas de integración de `scripts/compare_baselines_d1_composition.py` (#140).

Comprueba el criterio de aceptación sobre el fixture de seis animales: un solo comando
regenera el reporte completo con el objetivo composicional, con `day_only` y `ridge_design`
en todas las tablas. Requiere el extra `baselines`.
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
SCRIPT = REPO_ROOT / "scripts" / "compare_baselines_d1_composition.py"
FIXTURE_IDS = sorted(
    [
        "SAMEA112904764",
        "SAMEA112904772",
        "SAMEA112904803",
        "SAMEA112904810",
        "SAMEA112904855",
        "SAMEA112904883",
    ]
)


def _write_fixture_plan(tmp_path: Path, sample_ids: list[str] | None = None) -> Path:
    ids = sample_ids or FIXTURE_IDS
    plan = {
        "dataset_id": "D1_holofood",
        "version": "1.0.0",
        "k": 2,
        "seeds": [0, 1],
        "assignments": {
            "0": {s: i % 2 for i, s in enumerate(ids)},
            "1": {s: (i + 1) % 2 for i, s in enumerate(ids)},
        },
    }
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def _write_configs(tmp_path: Path) -> tuple[Path, Path]:
    linear = {
        "ridge_alphas": [1.0],
        "elasticnet_alphas": [0.1],
        "elasticnet_l1_ratios": [0.5],
        "elasticnet_max_iter": 5000,
        "cv_folds": 2,
        "scoring": "neg_root_mean_squared_error",
    }
    trees = {
        "random_forest_n_estimators": [10],
        "random_forest_max_depth": [3],
        "random_forest_min_samples_leaf": [1],
        "hist_gradient_boosting_learning_rate": [0.1],
        "hist_gradient_boosting_max_iter": [20],
        "hist_gradient_boosting_max_depth": [3],
        "hist_gradient_boosting_min_samples_leaf": [1],
        "cv_folds": 2,
        "scoring": "neg_root_mean_squared_error",
        "random_state": 42,
        "permutation_repeats": 2,
    }
    linear_path = tmp_path / "linear.json"
    trees_path = tmp_path / "trees.json"
    linear_path.write_text(json.dumps(linear), encoding="utf-8")
    trees_path.write_text(json.dumps(trees), encoding="utf-8")
    return linear_path, trees_path


def _run_script(
    tmp_path: Path, sources: Path, plan: Path
) -> tuple[subprocess.CompletedProcess[str], Path]:
    linear_path, trees_path = _write_configs(tmp_path)
    output = tmp_path / "out"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--sources",
            str(sources),
            "--plan",
            str(plan),
            "--linear-config",
            str(linear_path),
            "--tree-config",
            str(trees_path),
            "--inner-folds",
            "2",
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
    return completed, output


def test_script_regenerates_the_full_report(tmp_path: Path, holofood_fixture_sources: Path) -> None:
    plan = _write_fixture_plan(tmp_path)
    completed, output = _run_script(tmp_path, holofood_fixture_sources, plan)
    assert completed.returncode == 0, completed.stderr

    report = (output / "report.md").read_text(encoding="utf-8")
    for model in (
        "dummy_mean",
        "day_only",
        "ridge_design",
        "ridge",
        "elasticnet",
        "random_forest",
        "hist_gradient_boosting",
    ):
        assert f"`{model}`" in report
    assert "Tabla 5" in report
    assert "34/15/7" in report
    assert "exploratoria" in report
    assert "pseudoconteo" in report

    with (output / "metrics.csv").open(encoding="utf-8") as handle:
        metrics = list(csv.DictReader(handle))
    day_only_rows = [r for r in metrics if r["model"] == "day_only"]
    assert {r["metric"] for r in day_only_rows} >= {
        "fraction_r2_mean",
        "fraction_mae_pp_mean",
        "log_total_r2_mean",
        "reconstructed_mae_mean",
    }
    assert {r["group"] for r in day_only_rows} >= {"all", "7", "21", "35"}

    with (output / "fold_metrics.csv").open(encoding="utf-8") as handle:
        folds = list(csv.DictReader(handle))
    assert {(r["seed"], r["fold"]) for r in folds} == {
        (str(seed), str(fold)) for seed in (0, 1) for fold in (0, 1)
    }

    with (output / "selections.csv").open(encoding="utf-8") as handle:
        selections = list(csv.DictReader(handle))
    assert {r["model"] for r in selections} == {
        "ridge_design",
        "ridge",
        "elasticnet",
        "random_forest",
        "hist_gradient_boosting",
    }

    run = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert run["n_samples"] == 6
    assert run["issue"] == 140
    assert run["models"][1] == "day_only"
    assert run["compositional_target_version"] == "1.0.0"


def test_script_fails_when_the_plan_does_not_match_the_cohort(
    tmp_path: Path, holofood_fixture_sources: Path
) -> None:
    plan = _write_fixture_plan(tmp_path, sample_ids=[*FIXTURE_IDS[:-1], "SAMEA000000000"])
    completed, _ = _run_script(tmp_path, holofood_fixture_sources, plan)
    assert completed.returncode == 2
    assert "no coinciden" in completed.stderr
