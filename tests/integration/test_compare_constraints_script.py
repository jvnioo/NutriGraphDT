"""Pruebas de integración para la verificación de A73-P4."""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "compare_constraints.py"
VERSIONED_OUTPUT = REPO_ROOT / "reports" / "constraints" / "comparison"


def _run_verify(output_dir: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT), "--verify"]
    if output_dir is not None:
        command.extend(("--output", str(output_dir)))
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        cwd=REPO_ROOT,
        check=False,
    )


def test_verify_passes_on_versioned_tables_without_overwriting_them() -> None:
    comparison_path = VERSIONED_OUTPUT / "comparison.csv"
    statistics_path = VERSIONED_OUTPUT / "paired_statistics.csv"
    original = {
        comparison_path: comparison_path.read_bytes(),
        statistics_path: statistics_path.read_bytes(),
    }

    completed = _run_verify()

    assert completed.returncode == 0, completed.stderr
    assert "OK: comparison.csv: 38 filas; todas las celdas coinciden." in completed.stdout
    assert "OK: paired_statistics.csv: 33 filas; todas las celdas coinciden." in completed.stdout
    assert "NO VERIFICABLE: D1: k no está registrado en run.json" in completed.stdout
    assert "NO VERIFICABLE: Sintético: cohort_config_sha256 es nulo" in completed.stdout
    assert "NO VERIFICABLE: Baseline D1: semillas no están registradas" in completed.stdout
    assert "VERIFICACIÓN COMPLETA" in completed.stdout
    assert {path: path.read_bytes() for path in original} == original


def test_verify_fails_with_cell_location_when_a_table_value_changes(tmp_path: Path) -> None:
    output_dir = tmp_path / "comparison"
    output_dir.mkdir()
    comparison_path = output_dir / "comparison.csv"
    shutil.copyfile(VERSIONED_OUTPUT / "comparison.csv", comparison_path)
    shutil.copyfile(
        VERSIONED_OUTPUT / "paired_statistics.csv",
        output_dir / "paired_statistics.csv",
    )
    with comparison_path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = reader.fieldnames
        rows = list(reader)
    assert fieldnames is not None
    rows[0]["fraction_mae_pp_mean"] = "999.0"
    with comparison_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    completed = _run_verify(output_dir)

    assert completed.returncode != 0
    assert "comparison.csv" in completed.stderr
    assert "celda no coincide" in completed.stderr
    assert "fraction_mae_pp_mean" in completed.stderr
