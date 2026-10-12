"""`scripts/run_linear_baselines.py` sobre una cohorte sintética (A40-4, #74).

Comprueba el criterio de aceptación: los baselines entrenan con datos sintéticos y reportan
métricas en validación y prueba. Requiere el extra `baselines`.
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
SCRIPT = REPO_ROOT / "scripts" / "run_linear_baselines.py"


def test_script_trains_and_reports_val_and_test(tmp_path: Path) -> None:
    output = tmp_path / "linear"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--n-samples", "20", "--output", str(output)],
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
        (model, split)
        for model in ("dummy_mean", "ridge", "elasticnet")
        for split in ("val", "test")
    }

    run = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert run["n_samples"] == 20
    assert sum(run["subset_sizes"].values()) == 20
    assert set(run["best_params"]) == {"dummy_mean", "ridge", "elasticnet"}
    assert (output / "report.md").read_text(encoding="utf-8").startswith("| model |")
