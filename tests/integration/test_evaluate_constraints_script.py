"""Evaluación pareada con y sin restricciones de punta a punta (A68-P2, #185).

Sobre una cohorte sintética de 20 animales (sin datos reales): los dos brazos se entrenan en los
mismos folds y con la misma semilla, y el reporte trae métricas, violaciones, comparación
pareada y corridas enlazadas. Requiere los extras `graph` y `baselines`.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")

from nutrigraphdt.models.training.cv_inputs import synthetic_cv_plan  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "evaluate_constraints.py"
D06 = "d06.hydrogen.propionate_bound"


@pytest.fixture(scope="module")
def evaluated(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("evaluate")
    plan = tmp / "plan.json"
    synthetic_cv_plan(n_animals=20, first_seed=1).save(plan)
    sweep = json.loads(
        (REPO_ROOT / "configs" / "constraints" / "lambda_sweep_synthetic.json").read_text(
            encoding="utf-8"
        )
    )
    sweep.update({"variants": ["homo_sage"], "max_epochs": 2, "patience": 5})
    sweep_path = tmp / "sweep.json"
    sweep_path.write_text(json.dumps(sweep), encoding="utf-8")
    selection = tmp / "selection.json"
    selection.write_text(
        json.dumps(
            {
                "dataset_id": "synthetic_cohort",
                "selections": {"homo_sage": {"selected_lambda": 10.0}},
            }
        ),
        encoding="utf-8",
    )
    output = tmp / "out"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--dataset",
            "synthetic",
            "--plan",
            str(plan),
            "--sweep-config",
            str(sweep_path),
            "--selection",
            str(selection),
            "--seeds",
            "0",
            "1",
            "--output",
            str(output),
            "--runs-dir",
            str(tmp / "runs"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        cwd=REPO_ROOT,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return output


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_both_arms_train_on_the_same_folds_and_seeds(evaluated: Path) -> None:
    folds = _rows(evaluated / "folds.csv")
    assert {row["status"] for row in folds} == {"ok"}
    by_arm = {
        arm: {(r["seed"], r["fold"], r["train_seed"]) for r in folds if r["arm"] == arm}
        for arm in ("free", "constrained")
    }
    assert by_arm["free"] == by_arm["constrained"]
    assert len(by_arm["free"]) == 2 * 5
    assert {r["constraint_lambda"] for r in folds if r["arm"] == "free"} == {"0.0"}
    assert {r["constraint_lambda"] for r in folds if r["arm"] == "constrained"} == {"10.0"}
    assert all(r["run_id"] for r in folds)


def test_outputs_follow_the_protocol_artifacts(evaluated: Path) -> None:
    for name in (
        "report.md",
        "metrics.csv",
        "fold_metrics.csv",
        "violations.csv",
        "epoch_violations.csv",
        "violations_summary.csv",
        "paired.csv",
        "folds.csv",
        "predictions.csv",
        "run.json",
    ):
        assert (evaluated / name).exists(), name
    run_meta = json.loads((evaluated / "run.json").read_text(encoding="utf-8"))
    assert run_meta["lambdas"] == {"homo_sage": 10.0}
    assert run_meta["constraint_terms"] == [D06]
    assert run_meta["folds_ok"] == 20
    assert run_meta["git"]["commit"]
    assert run_meta["plan_canonical_sha256"]
    violations = _rows(evaluated / "violations.csv")
    assert {row["subset"] for row in violations} == {"test"}
    assert {row["arm"] for row in violations} == {"free", "constrained"}


def test_paired_comparison_covers_primary_metric_and_feasibility(evaluated: Path) -> None:
    paired = {row["metric"]: row for row in _rows(evaluated / "paired.csv")}
    assert {"fraction_mae_pp", f"VR_percent:{D06}"} <= set(paired)
    primary = paired["fraction_mae_pp"]
    assert int(primary["n_folds"]) == 10
    assert int(primary["degrees_of_freedom"]) == 9
    report = (evaluated / "report.md").read_text(encoding="utf-8")
    assert "Comparación pareada `constrained − free`" in report
    assert "Clasificación pendiente" in report
    assert "Cohorte sintética" in report
