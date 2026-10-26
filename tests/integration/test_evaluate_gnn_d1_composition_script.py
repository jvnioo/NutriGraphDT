"""Pruebas de integración de `scripts/evaluate_gnn_d1_composition.py` (#142).

Sobre el fixture de seis animales: un solo comando entrena una variante en los folds del plan
de prueba y escribe el reporte con la comparación frente a los baselines de #140, la
declaración del criterio de F4 y la selección de hiperparámetros sin leer el test. Requiere
los extras `graph` y `baselines`.
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

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "evaluate_gnn_d1_composition.py"
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


def _write_fixture_plan(tmp_path: Path) -> Path:
    plan = {
        "dataset_id": "D1_holofood",
        "version": "1.0.0",
        "k": 2,
        "seeds": [0, 1],
        "assignments": {
            "0": {s: i % 2 for i, s in enumerate(FIXTURE_IDS)},
            "1": {s: (i + 1) % 2 for i, s in enumerate(FIXTURE_IDS)},
        },
    }
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def _run_script(
    tmp_path: Path, sources: Path, graphs: Path, *extra: str
) -> tuple[subprocess.CompletedProcess[str], Path]:
    output = tmp_path / "out"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--sources",
            str(sources),
            "--graphs-dir",
            str(graphs),
            "--plan",
            str(_write_fixture_plan(tmp_path)),
            "--variants",
            "homo_sage",
            "--seeds",
            "0",
            "1",
            "--inner-folds",
            "2",
            "--max-epochs",
            "2",
            "--patience",
            "2",
            "--output",
            str(output),
            *extra,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        cwd=REPO_ROOT,
        check=False,
    )
    return completed, output


def test_script_regenerates_the_full_report(
    tmp_path: Path, holofood_fixture_sources: Path, holofood_fixture_graphs: Path
) -> None:
    completed, output = _run_script(
        tmp_path, holofood_fixture_sources, holofood_fixture_graphs, "--selection-seeds", "0"
    )
    assert completed.returncode == 0, completed.stderr

    report = (output / "report.md").read_text(encoding="utf-8")
    assert "Criterio de salida de F4" in report
    assert "val interno" in report
    assert "`homo_sage`" in report
    assert "inferred" in report

    with (output / "fold_metrics.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert {r["model"] for r in rows} == {"homo_sage"}
    assert {r["metric"] for r in rows} >= {
        "fraction_r2",
        "fraction_mae_pp",
        "log_total_r2",
        "reconstructed_r2",
    }
    assert {r["split"] for r in rows} == {"test"}

    with (output / "metrics.csv").open(encoding="utf-8") as handle:
        metrics = list(csv.DictReader(handle))
    assert {r["metric"] for r in metrics} >= {"fraction_r2_mean", "fraction_r2_std"}

    folds = list(csv.DictReader((output / "folds.csv").open(encoding="utf-8")))
    assert len(folds) == 4  # 2 semillas × 2 folds
    assert {row["status"] for row in folds} == {"ok"}
    assert all(int(row["n_train"]) + int(row["n_inner_val"]) == 3 for row in folds)

    predictions = list(csv.DictReader((output / "predictions.csv").open(encoding="utf-8")))
    assert len(predictions) == 12  # 4 folds × 3 animales de test
    run_meta = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert run_meta["issue"] == 142
    assert run_meta["folds_ok"] == 4


def test_script_selection_no_toca_el_test(
    tmp_path: Path, holofood_fixture_sources: Path, holofood_fixture_graphs: Path
) -> None:
    completed, output = _run_script(
        tmp_path, holofood_fixture_sources, holofood_fixture_graphs, "--selection-seeds", "1"
    )
    assert completed.returncode == 0, completed.stderr
    selection = json.loads((output / "selection.json").read_text(encoding="utf-8"))
    assert selection["test_used"] is False
    assert selection["selected"]["homo_sage"]["variant"] == "homo_sage"
    with (output / "selection.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    # La grilla completa de A45-5 (3 × 3) en los 2 folds de la semilla de selección.
    assert len(rows) == 9 * 2
