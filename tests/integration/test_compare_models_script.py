"""Prueba de integración de `scripts/compare_models.py` (A45-6, #106).

Corre el script en un proceso independiente sobre los reportes versionados del repositorio y
sobre copias modificadas. No requiere PyTorch ni scikit-learn.
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

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "compare_models.py"
VERSIONED = REPO_ROOT / "reports" / "comparison"


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


@pytest.fixture
def repo_copy(tmp_path: Path) -> Path:
    """Copia de `reports/baselines`, `reports/gnn` y la partición de D1."""
    root = tmp_path / "repo"
    for relative in ("reports/baselines", "reports/gnn/synthetic", "reports/gnn/d1"):
        shutil.copytree(REPO_ROOT / relative, root / relative)
    split = root / "configs" / "splits" / "d1_holofood.json"
    split.parent.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "configs" / "splits" / "d1_holofood.json", split)
    return root


def test_versioned_reports_are_up_to_date(tmp_path: Path) -> None:
    completed = _run("--output", str(tmp_path))
    assert completed.returncode == 0, completed.stderr
    assert "criterio de F4" in completed.stdout
    for name in ("model_comparison.md", "model_comparison.csv"):
        generated = (tmp_path / name).read_text(encoding="utf-8")
        versioned = (VERSIONED / name).read_text(encoding="utf-8")
        assert generated.splitlines() == versioned.splitlines(), (
            f"reports/comparison/{name} no está al día; regenérelo con "
            "`python scripts/compare_models.py`."
        )


def test_every_row_comes_from_the_source_reports(tmp_path: Path) -> None:
    assert _run("--output", str(tmp_path)).returncode == 0
    with (tmp_path / "model_comparison.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    sources = {
        "synthetic": [
            REPO_ROOT / "reports/baselines/report.csv",
            REPO_ROOT / "reports/gnn/synthetic/report.csv",
        ],
        "d1": [
            REPO_ROOT / "reports/baselines/d1/report.csv",
            REPO_ROOT / "reports/gnn/d1/report.csv",
        ],
    }
    for dataset, paths in sources.items():
        expected = {}
        for path in paths:
            with path.open(encoding="utf-8", newline="") as handle:
                for record in csv.DictReader(handle):
                    if record["split"] in {"val", "test"}:
                        key = (record["model"], record["split"], record["metric"])
                        expected[key] = float(record["average"])
        observed = {
            (r["model"], r["split"], r["metric"]): float(r["average"])
            for r in rows
            if r["dataset"] == dataset
        }
        assert observed == pytest.approx(expected)


def test_missing_variant_is_marked_pending(repo_copy: Path) -> None:
    (repo_copy / "reports/gnn/d1/run_hetero_gat.json").unlink()
    output = repo_copy / "out"
    completed = _run("--repo-root", str(repo_copy), "--output", str(output))
    assert completed.returncode == 0, completed.stderr
    assert "pendientes: hetero_gat" in completed.stdout
    text = (output / "model_comparison.md").read_text(encoding="utf-8")
    assert "`hetero_gat` | pendiente" in text
    with (output / "model_comparison.csv").open(encoding="utf-8", newline="") as handle:
        statuses = {
            r["status"]
            for r in csv.DictReader(handle)
            if r["dataset"] == "d1" and r["model"] == "hetero_gat"
        }
    assert statuses == {"pendiente"}


def test_misaligned_run_exits_with_code_2(repo_copy: Path) -> None:
    path = repo_copy / "reports/gnn/d1/run_homo_sage.json"
    info = json.loads(path.read_text(encoding="utf-8"))
    info["subsets"]["test"]["with_all_scfa"] += 1
    path.write_text(json.dumps(info), encoding="utf-8")
    output = repo_copy / "out"
    completed = _run("--repo-root", str(repo_copy), "--output", str(output))
    assert completed.returncode == 2
    assert "subsets.test.with_all_scfa" in completed.stderr
    assert not output.exists()


def test_changed_split_file_exits_with_code_2(repo_copy: Path) -> None:
    split = repo_copy / "configs/splits/d1_holofood.json"
    split.write_bytes(split.read_bytes() + b"\n ")
    completed = _run("--repo-root", str(repo_copy), "--output", str(repo_copy / "out"))
    assert completed.returncode == 2
    assert "split.sha256" in completed.stderr


def test_missing_baselines_exit_with_code_2(repo_copy: Path) -> None:
    (repo_copy / "reports/baselines/d1/run.json").unlink()
    completed = _run("--repo-root", str(repo_copy), "--output", str(repo_copy / "out"))
    assert completed.returncode == 2
    assert "Falta" in completed.stderr
