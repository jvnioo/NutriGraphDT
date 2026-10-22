"""Prueba de integración de `scripts/plot_gnn_runs.py` (A45-7, #107).

Las figuras requieren matplotlib (extra `plots`); la verificación de entradas y de los archivos
versionados en `reports/gnn/figures/` no lo requiere.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
from test_gnn_diagnostics import write_report, write_run  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "plot_gnn_runs.py"
FIGURES = REPO_ROOT / "reports" / "gnn" / "figures"
VARIANTS = ("homo_sage", "hetero_sage", "hetero_gat")
needs_matplotlib = pytest.mark.skipif(
    importlib.util.find_spec("matplotlib") is None,
    reason='Las figuras requieren matplotlib (pip install -e ".[plots]").',
)


def _run(*args: str, extra_path: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "MPLBACKEND": "Agg"}
    if extra_path is not None:
        env["PYTHONPATH"] = os.pathsep.join(
            [str(extra_path), *filter(None, [os.environ.get("PYTHONPATH")])]
        )
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=REPO_ROOT,
        check=False,
    )


@pytest.fixture
def runs(tmp_path: Path) -> list[Path]:
    return [write_run(tmp_path / "runs", variant, "synthetic") for variant in VARIANTS]


@needs_matplotlib
def test_generates_figures_and_diagnostics(tmp_path: Path, runs: list[Path]) -> None:
    report = write_report(tmp_path / "report.csv", dict.fromkeys(VARIANTS, 5.0))
    output = tmp_path / "figures"
    completed = _run(*map(str, reversed(runs)), "--report", str(report), "--output", str(output))
    assert completed.returncode == 0, completed.stderr
    for name in ("learning_curves_synthetic.png", "predictions_synthetic.png"):
        assert (output / name).read_bytes().startswith(b"\x89PNG")
    diagnostics = json.loads((output / "diagnostics_synthetic.json").read_text("utf-8"))
    assert [d["variant"] for d in diagnostics["diagnoses"]] == list(VARIANTS)
    assert diagnostics["runs"][0]["git"]["commit"] == "abcdef1234567"
    text = (output / "diagnostics_synthetic.md").read_text(encoding="utf-8")
    assert "![predictions_synthetic](predictions_synthetic.png)" in text


@needs_matplotlib
def test_same_runs_give_identical_png(tmp_path: Path, runs: list[Path]) -> None:
    outputs = [tmp_path / "a", tmp_path / "b"]
    for output in outputs:
        args = (*map(str, runs), "--no-report-check", "--output", str(output))
        assert _run(*args).returncode == 0
    for name in ("learning_curves_synthetic.png", "predictions_synthetic.png"):
        assert (outputs[0] / name).read_bytes() == (outputs[1] / name).read_bytes()


def test_runs_that_differ_from_the_report_exit_with_code_2(
    tmp_path: Path, runs: list[Path]
) -> None:
    report = write_report(tmp_path / "report.csv", dict.fromkeys(VARIANTS, 6.0))
    output = tmp_path / "figures"
    completed = _run(*map(str, runs), "--report", str(report), "--output", str(output))
    assert completed.returncode == 2
    assert "no coinciden con el reporte" in completed.stderr
    assert not output.exists()


def test_runs_from_two_datasets_exit_with_code_2(tmp_path: Path) -> None:
    first = write_run(tmp_path, "homo_sage", "synthetic")
    second = write_run(tmp_path, "hetero_gat", "d1")
    completed = _run(str(first), str(second), "--no-report-check")
    assert completed.returncode == 2
    assert "datasets distintos" in completed.stderr


def test_missing_matplotlib_exits_with_code_2(tmp_path: Path, runs: list[Path]) -> None:
    blocker = tmp_path / "blocker"
    (blocker / "matplotlib").mkdir(parents=True)
    (blocker / "matplotlib" / "__init__.py").write_text(
        'raise ImportError("matplotlib no disponible")\n', encoding="utf-8"
    )
    output = tmp_path / "figures"
    completed = _run(
        *map(str, runs), "--no-report-check", "--output", str(output), extra_path=blocker
    )
    assert completed.returncode == 2
    assert ".[plots]" in completed.stderr
    assert not output.exists()


@pytest.mark.parametrize("dataset", ["synthetic", "d1"])
def test_versioned_figures_match_the_gnn_reports(dataset: str) -> None:
    """Las figuras versionadas vienen de corridas cuyas métricas son las de A45-3 y A45-4."""
    diagnostics = json.loads((FIGURES / f"diagnostics_{dataset}.json").read_text("utf-8"))
    for name in diagnostics["figures"]:
        assert (FIGURES / name).read_bytes().startswith(b"\x89PNG")
    assert (FIGURES / f"diagnostics_{dataset}.md").is_file()
    with (REPO_ROOT / "reports" / "gnn" / dataset / "report.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        report = {
            (row["model"], row["split"], row["metric"]): float(row["average"])
            for row in csv.DictReader(handle)
        }
    assert [d["variant"] for d in diagnostics["diagnoses"]] == list(VARIANTS)
    for diagnosis, run in zip(diagnostics["diagnoses"], diagnostics["runs"], strict=True):
        variant = diagnosis["variant"]
        assert diagnosis["test"]["rmse_average"] == pytest.approx(
            report[(variant, "test", "rmse")], abs=1e-5
        )
        assert diagnosis["val_rmse_average"]["best_epoch"] == pytest.approx(
            report[(variant, "val", "rmse")], abs=1e-5
        )
        assert run["git"]["dirty"] is False
        assert run["seed"] == 42
