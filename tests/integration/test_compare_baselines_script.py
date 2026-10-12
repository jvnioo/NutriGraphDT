"""Pruebas de integración para `scripts/compare_baselines.py` (A40-6, #76).

Comprueba el criterio de aceptación: un solo comando regenera la tabla comparativa completa
con los 5 modelos de referencia. Requiere el extra `baselines`.
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
SCRIPT = REPO_ROOT / "scripts" / "compare_baselines.py"


def test_script_generates_all_comparison_artifacts(tmp_path: Path) -> None:
    """Verifica que el script genere la tabla comparativa y todos los artefactos."""
    output = tmp_path / "baselines_comparison"
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

    # 1. Tabla comparativa Markdown
    comparison_md = (output / "baseline_comparison.md").read_text(encoding="utf-8")
    assert "# Tabla comparativa consolidada de baselines" in comparison_md
    assert "`dummy_mean`" in comparison_md
    assert "`ridge`" in comparison_md
    assert "`elasticnet`" in comparison_md
    assert "`random_forest`" in comparison_md
    assert "`hist_gradient_boosting`" in comparison_md

    # 2. Tabla comparativa CSV
    with (output / "baseline_comparison.csv").open(encoding="utf-8") as handle:
        comp_rows = list(csv.DictReader(handle))
    assert {(r["model"], r["split"]) for r in comp_rows} == {
        (model, split)
        for model in (
            "dummy_mean",
            "ridge",
            "elasticnet",
            "random_forest",
            "hist_gradient_boosting",
        )
        for split in ("val", "test")
    }

    # 3. Reporte completo detallado
    with (output / "report.csv").open(encoding="utf-8") as handle:
        report_rows = list(csv.DictReader(handle))
    assert {(r["model"], r["split"]) for r in report_rows} == {
        (model, split)
        for model in (
            "dummy_mean",
            "ridge",
            "elasticnet",
            "random_forest",
            "hist_gradient_boosting",
        )
        for split in ("val", "test")
    }
    assert (output / "report.md").is_file()

    # 4. Importancias de atributos para modelos de árboles
    with (output / "importances.csv").open(encoding="utf-8") as handle:
        imp_rows = list(csv.DictReader(handle))
    assert {r["model"] for r in imp_rows} == {"random_forest", "hist_gradient_boosting"}

    # 5. Metadatos de la corrida
    run = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert run["n_samples"] == 20
    assert sum(run["subset_sizes"].values()) == 20
    assert set(run["best_params"].keys()) == {
        "dummy_mean",
        "ridge",
        "elasticnet",
        "random_forest",
        "hist_gradient_boosting",
    }
