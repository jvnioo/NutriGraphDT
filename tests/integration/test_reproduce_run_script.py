"""Prueba de integración de `scripts/reproduce_run.py` (A45-8, #108).

Entrena una corrida sintética breve con `train_gnn.py`, la reproduce desde su `run.json` y
verifica la comparación. Requiere los extras `graph` y `baselines`, como `train_gnn.py`.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("yaml")
pytest.importorskip("sklearn")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "reproduce_run.py"
TRAIN = REPO_ROOT / "scripts" / "train_gnn.py"
VERSIONED = REPO_ROOT / "reports" / "gnn" / "reproducibility"
GNN_REPORTS = REPO_ROOT / "reports" / "gnn"


def _run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        cwd=REPO_ROOT,
        check=False,
    )


@pytest.fixture(scope="module")
def original(tmp_path_factory: pytest.TempPathFactory) -> Path:
    runs = tmp_path_factory.mktemp("original")
    completed = _run(
        TRAIN,
        "--model",
        "hetero_sage",
        "--dataset",
        "synthetic",
        "--n-samples",
        "12",
        "--max-epochs",
        "3",
        "--runs-dir",
        str(runs),
    )
    assert completed.returncode == 0, completed.stderr
    (run_dir,) = runs.iterdir()
    return run_dir


@pytest.fixture(scope="module")
def reproduced(original: Path, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("reproduced")
    completed = _run(
        SCRIPT, str(original), "--runs-dir", str(root / "runs"), "--output", str(root / "out")
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    (new_dir,) = (root / "runs" / original.name).iterdir()
    return {"run": new_dir, "out": root / "out"}


def _checks(out: Path) -> dict[str, dict[str, object]]:
    data = json.loads((out / "synthetic_hetero_sage.json").read_text(encoding="utf-8"))
    return {check["name"]: check for check in data["checks"]}


def test_same_machine_reproduction_matches_every_file(reproduced: dict[str, Path]) -> None:
    data = json.loads((reproduced["out"] / "synthetic_hetero_sage.json").read_text("utf-8"))
    assert data["reproduced"] is True
    statuses = {check["name"]: check["status"] for check in data["checks"]}
    assert set(statuses.values()) == {"ok"}, statuses
    assert "Pesos del checkpoint" in statuses
    assert "Recarga del checkpoint original (load_run)" in statuses
    text = (reproduced["out"] / "synthetic_hetero_sage.md").read_text(encoding="utf-8")
    assert "**Se reproduce**" in text


def test_reproduction_uses_only_run_json(original: Path, reproduced: dict[str, Path]) -> None:
    before = json.loads((original / "run.json").read_text(encoding="utf-8"))
    after = json.loads((reproduced["run"] / "run.json").read_text(encoding="utf-8"))
    for key in ("training_config", "model_config", "source", "seed", "scaling"):
        assert after[key] == before[key]
    assert after["run_id"] != before["run_id"]


def test_changed_prediction_is_reported(
    original: Path, reproduced: dict[str, Path], tmp_path: Path
) -> None:
    tampered = tmp_path / "original"
    shutil.copytree(original, tampered)
    path = tampered / "predictions.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["predicted_butyrate"] = repr(float(rows[0]["predicted_butyrate"]) + 0.5)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    out = tmp_path / "out"
    completed = _run(
        SCRIPT, str(tampered), "--reproduced", str(reproduced["run"]), "--output", str(out)
    )
    assert completed.returncode == 1
    checks = _checks(out)
    assert checks["Predicciones (predictions.csv)"]["status"] == "difiere"
    # El checkpoint original ya no reproduce sus predicciones guardadas.
    assert checks["Recarga del checkpoint original (load_run)"]["status"] == "difiere"
    assert "NO se reproduce" in completed.stdout


def test_lone_run_json_compares_metrics_with_a_report(
    original: Path, reproduced: dict[str, Path], tmp_path: Path
) -> None:
    lone = tmp_path / "run_hetero_sage.json"
    shutil.copy2(original / "run.json", lone)
    report = tmp_path / "report.csv"
    with (original / "metrics.csv").open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row["split"] != "train"]
    with report.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    out = tmp_path / "out"
    completed = _run(
        SCRIPT,
        str(lone),
        "--reproduced",
        str(reproduced["run"]),
        "--report",
        str(report),
        "--output",
        str(out),
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    checks = _checks(out)
    assert checks[f"Métricas val y test ({report.as_posix()})"]["status"] == "ok"
    assert checks["Predicciones (predictions.csv)"]["status"] == "no disponible"
    assert checks["Pesos del checkpoint"]["status"] == "no disponible"


def test_missing_original_exits_with_code_2(tmp_path: Path) -> None:
    completed = _run(SCRIPT, str(tmp_path / "nada"), "--output", str(tmp_path / "out"))
    assert completed.returncode == 2
    assert "Falta" in completed.stderr


@pytest.mark.parametrize("variant", ["homo_sage", "hetero_sage", "hetero_gat"])
def test_versioned_a45_3_reproductions(variant: str) -> None:
    """Las reproducciones versionadas de A45-3 se reprodujeron y citan su run.json."""
    data = json.loads((VERSIONED / f"synthetic_{variant}.json").read_text(encoding="utf-8"))
    original = json.loads(
        (GNN_REPORTS / "synthetic" / f"run_{variant}.json").read_text(encoding="utf-8")
    )
    assert data["reproduced"] is True
    assert data["original"]["run_id"] == original["run_id"]
    assert data["original"]["commit"] == original["git"]["commit"]
    statuses = {c["name"]: c["status"] for c in data["checks"]}
    assert statuses["Métricas val y test (reports/gnn/synthetic/report.csv)"] == "ok"
    assert statuses["Recarga del checkpoint reproducido (load_run)"] == "ok"
    assert "difiere" not in statuses.values()
