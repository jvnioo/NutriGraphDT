"""Pruebas de integración para la verificación de A73-P4."""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "compare_constraints.py"
VERSIONED_OUTPUT = REPO_ROOT / "reports" / "constraints" / "comparison"
VERSIONED_D1 = REPO_ROOT / "reports" / "constraints" / "d1"


def _run_verify(
    output_dir: Path | None = None,
    *,
    d1_dir: Path | None = None,
    env_overrides: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT), "--verify"]
    if output_dir is not None:
        command.extend(("--output", str(output_dir)))
    if d1_dir is not None:
        command.extend(("--d1-dir", str(d1_dir)))
    environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    if env_overrides is not None:
        environment.update(env_overrides)
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
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
    assert "304 celdas coinciden con metrics.csv." in completed.stdout
    assert "210 celdas coinciden con violations_summary.csv." in completed.stdout
    assert "OK: comparison.csv: 38 filas; todas las celdas coinciden." in completed.stdout
    assert "OK: paired_statistics.csv: 33 filas; todas las celdas coinciden." in completed.stdout
    assert "D1: commit " in completed.stdout
    assert "Sintético: commit " in completed.stdout
    assert completed.stdout.count("existe y es ancestro de HEAD.") >= 2
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


def test_verify_directly_detects_a_changed_metrics_source(tmp_path: Path) -> None:
    d1_dir = tmp_path / "d1"
    d1_dir.mkdir()
    required_files = (
        "run.json",
        "folds.csv",
        "fold_metrics.csv",
        "paired.csv",
        "metrics.csv",
        "violations_summary.csv",
    )
    for filename in required_files:
        shutil.copyfile(VERSIONED_D1 / filename, d1_dir / filename)

    metrics_path = d1_dir / "metrics.csv"
    with metrics_path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = reader.fieldnames
        rows = list(reader)
    assert fieldnames is not None
    source_row = next(
        row
        for row in rows
        if row["model"] == "hetero_gat"
        and row["arm"] == "constrained"
        and row["split"] == "test"
        and row["group"] == "all"
        and row["metric"] == "fraction_mae_pp_mean"
    )
    source_row["average"] = str(float(source_row["average"]) + 1.0)
    with metrics_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    completed = _run_verify(d1_dir=d1_dir)

    assert completed.returncode != 0
    assert "metrics.csv: celda no coincide en comparison.csv" in completed.stderr
    assert "fraction_mae_pp_mean" in completed.stderr
    assert "esperado=" in completed.stderr
    assert "encontrado=" in completed.stderr


def test_verify_succeeds_when_git_is_unavailable(tmp_path: Path) -> None:
    completed = _run_verify(env_overrides={"PATH": str(tmp_path)})

    assert completed.returncode == 0, completed.stderr
    assert "NO VERIFICABLE: D1: Git no está disponible" in completed.stdout
    assert "NO VERIFICABLE: Sintético: Git no está disponible" in completed.stdout
    assert "NO VERIFICABLE: Baseline D1: commit no está registrado" in completed.stdout
    assert "VERIFICACIÓN COMPLETA" in completed.stdout
