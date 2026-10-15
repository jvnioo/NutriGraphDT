"""Pruebas de integración para `scripts/report_gnn.py` (A45-3)."""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from scripts.report_gnn import _read_evaluation_report  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
TRAIN_SCRIPT = REPO_ROOT / "scripts" / "train_gnn.py"
REPORT_SCRIPT = REPO_ROOT / "scripts" / "report_gnn.py"
BASELINE_RUN_PATH = REPO_ROOT / "reports" / "baselines" / "run.json"
BASELINE_REPORT_PATH = REPO_ROOT / "reports" / "baselines" / "report.csv"
VARIANTS = ("homo_sage", "hetero_sage", "hetero_gat")


def _run_script(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        cwd=REPO_ROOT,
        check=False,
    )


@pytest.fixture(scope="session")
def trained_runs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Genera una vez corridas reales, breves, y alineadas al run.json de baselines."""
    baseline = json.loads(BASELINE_RUN_PATH.read_text(encoding="utf-8"))
    runs_root = tmp_path_factory.mktemp("gnn-runs")
    run_dirs: dict[str, Path] = {}
    for variant in VARIANTS:
        variant_runs = runs_root / variant
        completed = _run_script(
            TRAIN_SCRIPT,
            "--model",
            variant,
            "--dataset",
            "synthetic",
            "--n-samples",
            str(baseline["n_samples"]),
            "--first-seed",
            str(baseline["first_seed"]),
            "--split-seed",
            str(baseline["split_seed"]),
            "--max-epochs",
            "2",
            "--runs-dir",
            str(variant_runs),
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        (run_dir,) = variant_runs.iterdir()
        run_dirs[variant] = run_dir
    return run_dirs


def _report_args(run_dirs: dict[str, Path], output: Path) -> list[str]:
    args = [
        "--baseline-run-json",
        str(BASELINE_RUN_PATH),
        "--baseline-report-csv",
        str(BASELINE_REPORT_PATH),
        "--output",
        str(output),
    ]
    for variant in VARIANTS:
        args.extend((f"--{variant.replace('_', '-')}-run", str(run_dirs[variant])))
    return args


def test_real_metrics_csv_round_trips_through_evaluation_report(
    trained_runs: dict[str, Path],
) -> None:
    for run_dir in trained_runs.values():
        metrics_path = run_dir / "metrics.csv"
        report = _read_evaluation_report(metrics_path)
        assert report.to_csv().encode("utf-8") == metrics_path.read_bytes()


def test_generates_report_and_only_copies_run_metadata(
    tmp_path: Path, trained_runs: dict[str, Path]
) -> None:
    output = tmp_path / "report"
    completed = _run_script(REPORT_SCRIPT, *_report_args(trained_runs, output))

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert {path.name for path in output.iterdir()} == {
        "report.md",
        "report.csv",
        *(f"run_{variant}.json" for variant in VARIANTS),
    }
    for variant in VARIANTS:
        assert (output / f"run_{variant}.json").read_bytes() == (
            trained_runs[variant] / "run.json"
        ).read_bytes()

    report = (output / "report.md").read_text(encoding="utf-8")
    assert "AGCC no dependen de las entradas" in report
    assert "no permiten afirmar que una variante supere al baseline" in report
    assert "dummy_mean" in report
    with BASELINE_REPORT_PATH.open(encoding="utf-8", newline="") as handle:
        baseline_rows = csv.DictReader(handle)
        dummy_mae_val = next(
            row
            for row in baseline_rows
            if row["model"] == "dummy_mean" and row["split"] == "val" and row["metric"] == "mae"
        )
    expected_baseline_row = " | ".join(
        (
            "dummy_mean",
            "val",
            "mae",
            *(
                f"{float(dummy_mae_val[target]):.4f}"
                for target in ("acetate", "propionate", "butyrate")
            ),
            f"{float(dummy_mae_val['average']):.4f}",
        )
    )
    assert f"| {expected_baseline_row} |" in report
    with (output / "report.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["model"] for row in rows} == set(VARIANTS)
    assert {row["split"] for row in rows} == {"val", "test"}


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("source", "n_samples"), -1, "source.n_samples"),
        (("source", "first_seed"), -1, "source.first_seed"),
        (("source", "split_seed"), -1, "source.split_seed"),
        (("split", "seed"), -1, "split.seed"),
        (("split", "counts", "train"), -1, "split.counts"),
        (("split", "sha256"), "different-partition", "split.sha256"),
        (("variant",), "hetero_gat", "variante"),
    ],
)
def test_rejects_run_metadata_that_does_not_match_baseline(
    tmp_path: Path,
    trained_runs: dict[str, Path],
    path: tuple[str, ...],
    value: Any,
    message: str,
) -> None:
    changed_runs: dict[str, Path] = {}
    for variant in VARIANTS:
        target = tmp_path / variant
        shutil.copytree(trained_runs[variant], target)
        changed_runs[variant] = target

    run_path = changed_runs["homo_sage"] / "run.json"
    info = json.loads(run_path.read_text(encoding="utf-8"))
    nested: dict[str, Any] = info
    for key in path[:-1]:
        nested = nested[key]
    nested[path[-1]] = value
    run_path.write_text(json.dumps(info), encoding="utf-8")

    output = tmp_path / "report"
    completed = _run_script(REPORT_SCRIPT, *_report_args(changed_runs, output))

    assert completed.returncode == 2
    assert message in completed.stderr
    assert not output.exists()
