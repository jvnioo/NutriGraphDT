"""Tests de integración para el script scripts/explain_gnn.py (A71-P1)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "explain_gnn.py"


def test_explain_gnn_help() -> None:
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert res.returncode == 0
    assert "--runs-dir" in res.stdout
    assert "--algorithm" in res.stdout
    assert "--top-k" in res.stdout


def test_explain_gnn_run_on_subset_of_d1(tmp_path: Path) -> None:
    runs_dir = REPO_ROOT / "runs" / "constraints" / "d1"
    graphs_dir = REPO_ROOT / "artifacts" / "graphs" / "D1_holofood" / "graphs"

    # Si los artefactos no están presentes (ej. entorno mínimo), saltar el test
    if not runs_dir.exists() or not graphs_dir.exists():
        return

    out_dir = tmp_path / "reports"
    artifacts_dir = tmp_path / "artifacts"

    res = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--dataset",
            "d1",
            "--runs-dir",
            str(runs_dir),
            "--seeds",
            "0",
            "1",
            "--limit-animals",
            "2",
            "--output-dir",
            str(out_dir),
            "--artifacts-dir",
            str(artifacts_dir),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert res.returncode == 0, f"Error en explain_gnn: {res.stderr}"
    assert (out_dir / "stability.csv").exists()
    assert (out_dir / "top_k_elements.csv").exists()
    assert (out_dir / "report.md").exists()
    assert (out_dir / "summary.json").exists()
    assert len(list(artifacts_dir.glob("**/*.json"))) > 0
