"""Pruebas de `nutrigraphdt.models.diagnostics` (A45-7, #107)."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import pytest

from nutrigraphdt.models.diagnostics import (
    RunDataError,
    diagnose,
    diagnoses_to_markdown,
    load_run,
    order_runs,
    report_mismatches,
)
from nutrigraphdt.models.metrics import DEFAULT_SCFA_TARGETS, METRIC_NAMES

TARGETS = DEFAULT_SCFA_TARGETS


def write_run(
    root: Path,
    variant: str = "homo_sage",
    dataset: str = "d1",
    *,
    train_loss: list[float] | None = None,
    val_loss: list[float] | None = None,
    val_rmse: list[float] | None = None,
    best_epoch: int = 2,
    test_points: list[tuple[float, float]] | None = None,
    metric_value: float = 5.0,
) -> Path:
    """Corrida mínima con el formato de `run_training`."""
    run_dir = root / f"run_{variant}_{dataset}"
    run_dir.mkdir(parents=True)
    train_loss = train_loss or [1.0, 0.8, 0.6, 0.4]
    val_loss = val_loss or [1.2, 1.0, 1.1, 1.3]
    val_rmse = val_rmse or [10.0, 8.0, 9.0, 9.5]
    info: dict[str, Any] = {
        "run_id": f"20261015-000000_{variant}_s42",
        "variant": variant,
        "seed": 42,
        "source": {"dataset": dataset},
        "best_epoch": best_epoch,
        "stopped_early": True,
        "git": {"commit": "abcdef1234567", "dirty": False},
        "split": {"file": "configs/splits/x.json", "sha256": "f" * 64, "counts": {}},
    }
    (run_dir / "run.json").write_text(json.dumps(info), encoding="utf-8")

    header = ["epoch", "train_loss", "val_loss"]
    header += [f"val_rmse_{t}" for t in (*TARGETS, "average")] + ["improved"]
    with (run_dir / "history.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for i, (tl, vl, vr) in enumerate(zip(train_loss, val_loss, val_rmse, strict=True)):
            writer.writerow([i + 1, tl, vl, vr, vr, vr, vr, i + 1 == best_epoch])

    test_points = test_points or [(1.0, 2.0), (2.0, 2.5), (3.0, 3.5), (4.0, 3.0)]
    with (run_dir / "predictions.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["sample_id", "graph_id", "subset"]
            + [f"measured_{t}" for t in TARGETS]
            + [f"predicted_{t}" for t in TARGETS]
        )
        writer.writerow(["s0", "g0", "train", 1, 1, 1, 1, 1, 1])
        for i, (measured, predicted) in enumerate(test_points):
            writer.writerow(
                [f"t{i}", f"g{i}", "test"] + [measured] * len(TARGETS) + [predicted] * len(TARGETS)
            )

    with (run_dir / "metrics.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["model", "split", "metric", *TARGETS, "average"])
        for split in ("train", "val", "test"):
            for metric in METRIC_NAMES:
                writer.writerow([variant, split, metric] + [metric_value] * (len(TARGETS) + 1))
    return run_dir


def write_report(path: Path, variants: dict[str, float]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["model", "split", "metric", *TARGETS, "average"])
        for variant, value in variants.items():
            for split in ("val", "test"):
                for metric in METRIC_NAMES:
                    writer.writerow([variant, split, metric] + [value] * (len(TARGETS) + 1))
    return path


# --- lectura -----------------------------------------------------------------------------


def test_load_run_reads_all_files(tmp_path: Path) -> None:
    run = load_run(write_run(tmp_path))
    assert (run.variant, run.dataset, run.best_epoch) == ("homo_sage", "d1", 2)
    assert [row.epoch for row in run.history] == [1, 2, 3, 4]
    assert run.history[1].improved and not run.history[0].improved
    assert len(run.subset("test")) == 4
    assert run.metric("test", "rmse") == 5.0


@pytest.mark.parametrize("name", ["run.json", "history.csv", "predictions.csv", "metrics.csv"])
def test_missing_file_is_an_error(tmp_path: Path, name: str) -> None:
    run_dir = write_run(tmp_path)
    (run_dir / name).unlink()
    with pytest.raises(RunDataError, match="Falta"):
        load_run(run_dir)


def test_best_epoch_must_be_in_history(tmp_path: Path) -> None:
    with pytest.raises(RunDataError, match="mejor época"):
        load_run(write_run(tmp_path, best_epoch=9))


def test_non_numeric_history_is_an_error(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    path = run_dir / "history.csv"
    path.write_text(path.read_text(encoding="utf-8").replace("0.8", "x", 1), encoding="utf-8")
    with pytest.raises(RunDataError, match="no numérico"):
        load_run(run_dir)


def test_epochs_must_be_consecutive(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    path = run_dir / "history.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([lines[0], *lines[2:]]) + "\n", encoding="utf-8")
    with pytest.raises(RunDataError, match="épocas"):
        load_run(run_dir)


def test_missing_source_dataset_is_an_error(tmp_path: Path) -> None:
    run_dir = write_run(tmp_path)
    info = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    del info["source"]
    (run_dir / "run.json").write_text(json.dumps(info), encoding="utf-8")
    with pytest.raises(RunDataError, match="source.dataset"):
        load_run(run_dir)


# --- orden y verificación ----------------------------------------------------------------


def test_runs_are_ordered_by_variant(tmp_path: Path) -> None:
    runs = [load_run(write_run(tmp_path, v)) for v in ("hetero_gat", "homo_sage", "hetero_sage")]
    assert [r.variant for r in order_runs(runs)] == ["homo_sage", "hetero_sage", "hetero_gat"]


def test_runs_from_different_datasets_are_rejected(tmp_path: Path) -> None:
    runs = [
        load_run(write_run(tmp_path, "homo_sage", "d1")),
        load_run(write_run(tmp_path, "hetero_gat", "synthetic")),
    ]
    with pytest.raises(RunDataError, match="datasets distintos"):
        order_runs(runs)


def test_repeated_variant_is_rejected(tmp_path: Path) -> None:
    runs = [load_run(write_run(tmp_path / "a")), load_run(write_run(tmp_path / "b"))]
    with pytest.raises(RunDataError, match="repetidas"):
        order_runs(runs)


def test_no_runs_is_rejected() -> None:
    with pytest.raises(RunDataError, match="No se indicaron"):
        order_runs([])


def test_report_check_passes_when_metrics_match(tmp_path: Path) -> None:
    run = load_run(write_run(tmp_path, metric_value=5.0))
    report = write_report(tmp_path / "report.csv", {"homo_sage": 5.0, "ridge": 9.0})
    assert report_mismatches(run, report) == []


def test_report_check_detects_differences(tmp_path: Path) -> None:
    run = load_run(write_run(tmp_path, metric_value=5.0))
    report = write_report(tmp_path / "report.csv", {"homo_sage": 5.001})
    problems = report_mismatches(run, report)
    assert len(problems) == 2 * len(METRIC_NAMES) * (len(TARGETS) + 1)
    assert "val/mae/acetate" in problems[0]


def test_report_check_tolerates_float32_rounding(tmp_path: Path) -> None:
    run = load_run(write_run(tmp_path, metric_value=5.0))
    report = write_report(tmp_path / "report.csv", {"homo_sage": 5.0000003})
    assert report_mismatches(run, report) == []


def test_report_check_detects_missing_variant_or_file(tmp_path: Path) -> None:
    run = load_run(write_run(tmp_path))
    report = write_report(tmp_path / "report.csv", {"ridge": 5.0})
    assert report_mismatches(run, report) == [f"homo_sage no está en {report}"]
    assert report_mismatches(run, tmp_path / "nada.csv")[0].startswith("falta")


# --- diagnóstico -------------------------------------------------------------------------


def test_diagnosis_reads_best_and_last_epoch(tmp_path: Path) -> None:
    d = diagnose(load_run(write_run(tmp_path)))
    assert (d.best_epoch, d.epochs_run, d.stopped_early) == (2, 4, True)
    assert (d.train_loss_best, d.train_loss_last) == (0.8, 0.4)
    assert (d.val_loss_best, d.val_loss_last) == (1.0, 1.3)
    assert (d.val_rmse_first, d.val_rmse_best, d.val_rmse_last) == (10.0, 8.0, 9.5)
    assert d.test_rmse == 5.0


def test_diagnosis_spread_and_correlation_use_test_only(tmp_path: Path) -> None:
    points = [(1.0, 2.0), (2.0, 2.5), (3.0, 3.5), (4.0, 3.0)]
    d = diagnose(load_run(write_run(tmp_path, test_points=points)))
    measured, predicted = zip(*points, strict=True)
    import statistics

    expected_spread = statistics.stdev(predicted) / statistics.stdev(measured)
    assert d.spread_ratio["acetate"] == pytest.approx(expected_spread)
    assert d.correlation["butyrate"] == pytest.approx(statistics.correlation(measured, predicted))


def test_constant_prediction_has_zero_spread_and_no_correlation(tmp_path: Path) -> None:
    points = [(1.0, 3.0), (2.0, 3.0), (5.0, 3.0)]
    d = diagnose(load_run(write_run(tmp_path, test_points=points)))
    assert d.spread_ratio["acetate"] == 0.0
    assert math.isnan(d.correlation["acetate"])


def test_diagnosis_needs_two_test_points(tmp_path: Path) -> None:
    with pytest.raises(RunDataError, match="menos de 2"):
        diagnose(load_run(write_run(tmp_path, test_points=[(1.0, 1.0)])))


def test_markdown_lists_provenance_figures_and_figures(tmp_path: Path) -> None:
    runs = order_runs([load_run(write_run(tmp_path, v)) for v in ("homo_sage", "hetero_gat")])
    text = diagnoses_to_markdown(
        [diagnose(r) for r in runs], runs, ["learning_curves_d1.png"], "cmd"
    )
    assert "# Curvas de aprendizaje y predicciones — D1 HoloFood (A45-7)" in text
    assert "1 mmol/kg = 1 µmol/g de digesta" in text
    assert "![learning_curves_d1](learning_curves_d1.png)" in text
    assert "| `homo_sage` | `20261015-000000_homo_sage_s42` | 42 | `abcdef1` | no |" in text
    assert "| `hetero_gat` | 2 / 4 | 0.800 → 0.400 | 1.000 → 1.300 | 10.00 → 8.00 |" in text
    assert text.index("`homo_sage` | 2 / 4") < text.index("`hetero_gat` | 2 / 4")
