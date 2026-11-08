from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from nutrigraphdt.data.split import split_content_sha256
from nutrigraphdt.models.constraints_comparison import (
    D06_CONSTRAINT,
    build_constraints_comparison,
)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _fixture_inputs(root: Path) -> tuple[Path, Path, Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    plan_path = root / "plan.json"
    plan = {"folds": [{"test": ["a"], "train": ["b"]}], "k": 1}
    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    digest = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    canonical_digest = split_content_sha256(plan)

    d1_dir = root / "d1"
    synthetic_dir = root / "synthetic"
    baseline_dir = root / "baseline"
    for directory in (d1_dir, synthetic_dir, baseline_dir):
        directory.mkdir()
    comparison_run = {
        "plan_sha256": digest,
        "plan_canonical_sha256": canonical_digest,
    }
    (d1_dir / "run.json").write_text(json.dumps(comparison_run), encoding="utf-8")
    (baseline_dir / "run.json").write_text(json.dumps({"plan_sha256": digest}), encoding="utf-8")

    metric_fields = ["model", "arm", "split", "group", "metric", "average"]
    metrics_by_dir = {d1_dir: [], synthetic_dir: []}
    groups_by_dir = {d1_dir: ("all", "7", "21", "35"), synthetic_dir: ("all",)}
    for directory, groups in groups_by_dir.items():
        dataset_model = "model_a"
        for group in groups:
            for arm in ("free", "constrained"):
                for metric, mean, std in (
                    ("fraction_mae_pp", "1.25", "0.5"),
                    ("fraction_r2", "0.25", "0.1"),
                    ("log_total_mae", "0.75", "0.2"),
                    ("reconstructed_mae", "2.5", "0.4"),
                ):
                    metrics_by_dir[directory].append(
                        {
                            "model": dataset_model,
                            "arm": arm,
                            "split": "test",
                            "group": group,
                            "metric": f"{metric}_mean",
                            "average": mean,
                        }
                    )
                    metrics_by_dir[directory].append(
                        {
                            "model": dataset_model,
                            "arm": arm,
                            "split": "test",
                            "group": group,
                            "metric": f"{metric}_std",
                            "average": std,
                        }
                    )
                metrics_by_dir[directory].append(
                    {
                        "model": dataset_model,
                        "arm": arm,
                        "split": "test",
                        "group": group,
                        "metric": "fraction_mae_pp_n",
                        "average": "5",
                    }
                )
        _write_csv(directory / "metrics.csv", metric_fields, metrics_by_dir[directory])

        violation_rows = []
        for arm in ("free", "constrained"):
            for metric, mean in (
                ("violation_rate_percent", "0"),
                ("worst_case_magnitude", "0.05"),
                ("joint_feasibility_percent", "100"),
                ("mean_magnitude", "0.01"),
            ):
                violation_rows.append(
                    {
                        "model": dataset_model,
                        "arm": arm,
                        "subset": "test",
                        "constraint": D06_CONSTRAINT,
                        "metric": metric,
                        "mean": mean,
                        "std": "0.0",
                        "n": "5",
                        "max": "0.75" if metric == "worst_case_magnitude" else mean,
                    }
                )
        _write_csv(
            directory / "violations_summary.csv",
            [
                "model",
                "arm",
                "subset",
                "constraint",
                "metric",
                "mean",
                "std",
                "n",
                "max",
            ],
            violation_rows,
        )

    baseline_rows = []
    for model in ("dummy_mean", "day_only"):
        for group in ("all", "7", "21", "35"):
            for metric, average in (
                ("fraction_mae_pp_mean", "4"),
                ("fraction_mae_pp_std", "1"),
                ("fraction_r2_mean", "0.2"),
                ("fraction_r2_std", "0.1"),
                ("log_total_mae_mean", "0.3"),
                ("log_total_mae_std", "0.05"),
                ("reconstructed_mae_mean", "5"),
                ("reconstructed_mae_std", "0.7"),
                ("fraction_mae_pp_n", "5"),
            ):
                baseline_rows.append(
                    {
                        "model": model,
                        "split": "cv",
                        "group": group,
                        "metric": metric,
                        "average": average,
                    }
                )
    _write_csv(
        baseline_dir / "metrics.csv",
        ["model", "split", "group", "metric", "average"],
        baseline_rows,
    )
    return d1_dir, synthetic_dir, baseline_dir, plan_path


def _generate(root: Path, output: Path) -> tuple[Path, Path]:
    d1, synthetic, baseline, plan = _fixture_inputs(root)
    return build_constraints_comparison(
        d1_dir=d1,
        synthetic_dir=synthetic,
        baseline_dir=baseline,
        plan_path=plan,
        output_dir=output,
    )


def test_builds_metrics_and_marks_synthetic_cohort_and_missing_references(
    tmp_path: Path,
) -> None:
    csv_path, report_path = _generate(tmp_path / "input", tmp_path / "output")
    with csv_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    synthetic = next(row for row in rows if row["dataset"] == "synthetic")
    reference = next(
        row for row in rows if row["arm"] == "reference" and row["model"] == "dummy_mean"
    )
    assert synthetic["cohort"] == "cohorte sintética"
    assert reference["model"] == "dummy_mean"
    assert reference["fraction_mae_pp_mean"] == "4"
    assert reference["vr_mean"] == ""
    assert synthetic["vr_mean"] == "0"
    assert synthetic["vwm_max"] == "0.75"
    assert "vwm_mean" not in synthetic
    assert "vwm_std" not in synthetic
    assert synthetic["fr_joint_mean"] == "100"
    assert synthetic["vmm_mean"] == "0.01"
    assert synthetic["fraction_mae_pp_std"] == "0.5"
    assert synthetic["n_folds"] == "5"
    assert int(synthetic["n_folds"]) == 5
    assert "no aplica" in report_path.read_text(encoding="utf-8")
    assert "no se usa `_seed_std`" in report_path.read_text(encoding="utf-8")
    report = report_path.read_text(encoding="utf-8")
    assert "VWM (máx.)" in report
    assert "D1: los brazos son idénticos y VR = 0." in report
    assert "Cohorte sintética: los brazos son idénticos y VR = 0." in report
    assert "La restricción no se activó en ninguno de los dos conjuntos" in report
    assert "el día 7" in report
    assert "restricciones estructurales se omiten" in report.lower()


def test_report_describes_nonidentical_synthetic_arms_from_data(tmp_path: Path) -> None:
    d1_dir, synthetic_dir, baseline_dir, plan_path = _fixture_inputs(tmp_path / "input")
    metrics_path = synthetic_dir / "metrics.csv"
    with metrics_path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = reader.fieldnames
        rows = list(reader)
    assert fieldnames is not None
    for row in rows:
        if (
            row["model"] == "model_a"
            and row["arm"] == "constrained"
            and row["metric"] == "fraction_mae_pp_mean"
        ):
            row["average"] = "9.0"
    _write_csv(metrics_path, fieldnames, rows)

    _, report_path = build_constraints_comparison(
        d1_dir=d1_dir,
        synthetic_dir=synthetic_dir,
        baseline_dir=baseline_dir,
        plan_path=plan_path,
        output_dir=tmp_path / "output",
    )
    report = report_path.read_text(encoding="utf-8")
    assert "Cohorte sintética: los brazos no son idénticos y VR = 0." in report


def test_rejects_baseline_with_a_different_plan(tmp_path: Path) -> None:
    d1_dir, synthetic_dir, baseline_dir, plan_path = _fixture_inputs(tmp_path / "input")
    (baseline_dir / "run.json").write_text(json.dumps({"plan_sha256": "0" * 64}), encoding="utf-8")
    with pytest.raises(ValueError, match="hash del plan comparable"):
        build_constraints_comparison(
            d1_dir=d1_dir,
            synthetic_dir=synthetic_dir,
            baseline_dir=baseline_dir,
            plan_path=plan_path,
            output_dir=tmp_path / "output",
        )


def test_accepts_baseline_hash_when_windows_plan_uses_crlf(tmp_path: Path) -> None:
    d1_dir, synthetic_dir, baseline_dir, plan_path = _fixture_inputs(tmp_path / "input")
    plan_lf = plan_path.read_bytes().replace(b"\r\n", b"\n")
    plan_crlf = plan_lf.replace(b"\n", b"\r\n")
    plan_path.write_bytes(plan_crlf)

    comparison_run_path = d1_dir / "run.json"
    comparison_run = json.loads(comparison_run_path.read_text(encoding="utf-8"))
    comparison_run["plan_sha256"] = hashlib.sha256(plan_crlf).hexdigest()
    comparison_run_path.write_text(json.dumps(comparison_run), encoding="utf-8")
    baseline_run_path = baseline_dir / "run.json"
    baseline_run = json.loads(baseline_run_path.read_text(encoding="utf-8"))
    baseline_run["plan_sha256"] = hashlib.sha256(plan_lf).hexdigest()
    baseline_run_path.write_text(json.dumps(baseline_run), encoding="utf-8")

    build_constraints_comparison(
        d1_dir=d1_dir,
        synthetic_dir=synthetic_dir,
        baseline_dir=baseline_dir,
        plan_path=plan_path,
        output_dir=tmp_path / "output",
    )


def test_output_is_deterministic(tmp_path: Path) -> None:
    csv_path_a, report_path_a = _generate(tmp_path / "first", tmp_path / "out-a")
    csv_path_b, report_path_b = _generate(tmp_path / "second", tmp_path / "out-b")
    assert csv_path_a.read_bytes() == csv_path_b.read_bytes()
    assert report_path_a.read_bytes() == report_path_b.read_bytes()
