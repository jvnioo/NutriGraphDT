"""Pruebas de `nutrigraphdt.models.comparison` (A45-6, #106)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pytest

from nutrigraphdt.models.comparison import (
    CSV_COLUMNS,
    GNN_VARIANTS,
    PENDING,
    ComparisonError,
    DatasetSources,
    alignment_problems,
    assess_criterion,
    load_dataset,
    read_evaluation_csv,
    split_file_digests,
    summary_table,
    to_csv,
    to_markdown,
)
from nutrigraphdt.models.metrics import DEFAULT_SCFA_TARGETS, METRIC_NAMES

SIZES = {"train": 6, "val": 2, "test": 2}
HEADER = ["model", "split", "metric", *DEFAULT_SCFA_TARGETS, "average"]


def _write_report(path: Path, rmse: dict[str, float]) -> None:
    """`report.csv` con todas las métricas; el RMSE promedio de cada modelo es `rmse[modelo]`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        for model, value in rmse.items():
            for split in ("val", "test"):
                for metric in METRIC_NAMES:
                    average = value + (0.5 if split == "val" else 0.0)
                    if metric != "rmse":
                        average = 0.0
                    writer.writerow([model, split, metric, average, average, average, average])


def _baseline_run(**extra: Any) -> dict[str, Any]:
    return {"dataset_id": "toy", "subset_sizes": dict(SIZES), **extra}


def _synthetic_gnn_run(**overrides: Any) -> dict[str, Any]:
    run: dict[str, Any] = {
        "dataset_id": "toy",
        "source": {"dataset": "synthetic", "n_samples": 10, "first_seed": 1, "split_seed": 42},
        "split": {"file": None, "seed": 42, "counts": dict(SIZES), "sha256": "abc"},
        "git": {"commit": "c0ffee", "dirty": False},
    }
    run.update(overrides)
    return run


def _d1_gnn_run(sha: str, **overrides: Any) -> dict[str, Any]:
    run: dict[str, Any] = {
        "dataset_id": "toy",
        "split": {"file": "configs/splits/toy.json", "sha256": sha},
        "subsets": {name: {"graphs": 9, "with_all_scfa": n} for name, n in SIZES.items()},
        "git": {"commit": "c0ffee", "dirty": False},
    }
    run.update(overrides)
    return run


def _synthetic(tmp_path: Path, gnn_rmse: dict[str, float] | None = None) -> DatasetSources:
    sources = DatasetSources(
        name="synthetic",
        label="Sintético",
        baseline_dir=tmp_path / "baselines",
        gnn_dir=tmp_path / "gnn",
    )
    _write_report(sources.baseline_dir / "report.csv", {"dummy_mean": 5.0, "ridge": 4.0})
    (sources.baseline_dir / "run.json").write_text(
        json.dumps(_baseline_run(n_samples=10, first_seed=1, split_seed=42)), encoding="utf-8"
    )
    gnn_rmse = gnn_rmse if gnn_rmse is not None else {v: 4.5 for v in GNN_VARIANTS}
    _write_report(sources.gnn_dir / "report.csv", gnn_rmse)
    for variant in gnn_rmse:
        (sources.gnn_dir / f"run_{variant}.json").write_text(
            json.dumps(_synthetic_gnn_run()), encoding="utf-8"
        )
    return sources


def _d1(tmp_path: Path, split_bytes: bytes = b'{\n  "version": "1"\n}\n') -> DatasetSources:
    split_file = tmp_path / "configs" / "splits" / "toy.json"
    split_file.parent.mkdir(parents=True)
    split_file.write_bytes(split_bytes)
    sources = DatasetSources(
        name="d1",
        label="D1",
        baseline_dir=tmp_path / "baselines" / "d1",
        gnn_dir=tmp_path / "gnn" / "d1",
        split_file=split_file,
    )
    _write_report(sources.baseline_dir / "report.csv", {"dummy_mean": 5.0, "ridge": 4.0})
    (sources.baseline_dir / "run.json").write_text(json.dumps(_baseline_run()), encoding="utf-8")
    _write_report(sources.gnn_dir / "report.csv", {v: 3.0 for v in GNN_VARIANTS})
    sha = hashlib.sha256(split_bytes).hexdigest()
    for variant in GNN_VARIANTS:
        (sources.gnn_dir / f"run_{variant}.json").write_text(
            json.dumps(_d1_gnn_run(sha)), encoding="utf-8"
        )
    return sources


# --- lectura -----------------------------------------------------------------------------


def test_read_evaluation_csv_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "report.csv"
    _write_report(path, {"ridge": 4.0})
    report = read_evaluation_csv(path)
    assert len(report.rows) == 2 * len(METRIC_NAMES)
    row = report.get_row("rmse", model="ridge", split="test")
    assert row is not None and row.average == 4.0
    assert dict(row.targets) == {name: 4.0 for name in DEFAULT_SCFA_TARGETS}


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("model,split,metric,acetate,average\n", "faltan columnas"),
        (",".join(HEADER) + "\nridge,val,rmse,1,x,1,1\n", "no numérico"),
        (",".join(HEADER) + "\nridge,val,rmse,1,nan,1,1\n", "no finito"),
    ],
)
def test_read_evaluation_csv_rejects_invalid_files(
    tmp_path: Path, content: str, message: str
) -> None:
    path = tmp_path / "report.csv"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ComparisonError, match=message):
        read_evaluation_csv(path)


def test_missing_baseline_report_is_an_error(tmp_path: Path) -> None:
    sources = _synthetic(tmp_path)
    (sources.baseline_dir / "report.csv").unlink()
    with pytest.raises(ComparisonError, match="Falta"):
        load_dataset(sources)


def test_incomplete_metrics_are_an_error(tmp_path: Path) -> None:
    sources = _synthetic(tmp_path)
    path = sources.gnn_dir / "report.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(line for line in lines if ",test,r2," not in line), "utf-8")
    with pytest.raises(ComparisonError, match="todas las métricas"):
        load_dataset(sources)


# --- alineación --------------------------------------------------------------------------


def test_aligned_synthetic_runs_have_no_problems(tmp_path: Path) -> None:
    sources = _synthetic(tmp_path)
    baseline = _baseline_run(n_samples=10, first_seed=1, split_seed=42)
    assert alignment_problems(sources, baseline, _synthetic_gnn_run()) == []


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"dataset_id": "otro"}, "dataset_id"),
        (
            {
                "source": {
                    "dataset": "synthetic",
                    "n_samples": 11,
                    "first_seed": 1,
                    "split_seed": 42,
                }
            },
            "source.n_samples",
        ),
        (
            {
                "source": {
                    "dataset": "synthetic",
                    "n_samples": 10,
                    "first_seed": 2,
                    "split_seed": 42,
                }
            },
            "source.first_seed",
        ),
        (
            {"split": {"seed": 7, "counts": dict(SIZES), "sha256": "abc"}},
            "split.seed",
        ),
        (
            {"split": {"seed": 42, "counts": {"train": 5, "val": 3, "test": 2}, "sha256": "a"}},
            "split.counts",
        ),
    ],
)
def test_misaligned_synthetic_runs_are_reported(
    tmp_path: Path, override: dict[str, Any], fragment: str
) -> None:
    sources = _synthetic(tmp_path)
    baseline = _baseline_run(n_samples=10, first_seed=1, split_seed=42)
    problems = alignment_problems(sources, baseline, _synthetic_gnn_run(**override))
    assert any(fragment in problem for problem in problems)


def test_d1_alignment_checks_split_file_hash_and_subsets(tmp_path: Path) -> None:
    sources = _d1(tmp_path)
    assert sources.split_file is not None
    digests = split_file_digests(sources.split_file)
    good = _d1_gnn_run(hashlib.sha256(sources.split_file.read_bytes()).hexdigest())
    assert alignment_problems(sources, _baseline_run(), good, split_sha256=digests) == []

    wrong_hash = _d1_gnn_run("0" * 64)
    assert any(
        "sha256" in p
        for p in alignment_problems(sources, _baseline_run(), wrong_hash, split_sha256=digests)
    )
    wrong_file = _d1_gnn_run(good["split"]["sha256"], split={"file": "otra.json", "sha256": ""})
    assert any("split.file" in p for p in alignment_problems(sources, _baseline_run(), wrong_file))
    subsets = {name: {"with_all_scfa": n} for name, n in SIZES.items()}
    subsets["val"] = {"with_all_scfa": 3}
    wrong_subsets = _d1_gnn_run(good["split"]["sha256"], subsets=subsets)
    assert any(
        "subsets.val" in p for p in alignment_problems(sources, _baseline_run(), wrong_subsets)
    )


def test_split_hash_accepts_lf_and_crlf_copies(tmp_path: Path) -> None:
    lf = b'{\n  "version": "1"\n}\n'
    crlf = lf.replace(b"\n", b"\r\n")
    path = tmp_path / "split.json"
    path.write_bytes(lf)
    assert hashlib.sha256(crlf).hexdigest() in split_file_digests(path)
    path.write_bytes(crlf)
    assert hashlib.sha256(lf).hexdigest() in split_file_digests(path)
    assert hashlib.sha256(lf + b" ").hexdigest() not in split_file_digests(path)


def test_d1_run_recorded_on_windows_is_accepted_on_linux(tmp_path: Path) -> None:
    sources = _d1(tmp_path)
    assert sources.split_file is not None
    crlf_sha = hashlib.sha256(sources.split_file.read_bytes().replace(b"\n", b"\r\n")).hexdigest()
    for variant in GNN_VARIANTS:
        (sources.gnn_dir / f"run_{variant}.json").write_text(
            json.dumps(_d1_gnn_run(crlf_sha)), encoding="utf-8"
        )
    assert load_dataset(sources).pending == ()


def test_misaligned_variant_stops_the_comparison(tmp_path: Path) -> None:
    sources = _synthetic(tmp_path)
    (sources.gnn_dir / "run_hetero_gat.json").write_text(
        json.dumps(_synthetic_gnn_run(dataset_id="otro")), encoding="utf-8"
    )
    with pytest.raises(ComparisonError, match="run_hetero_gat.json no está alineado"):
        load_dataset(sources)


# --- pendientes y criterio ---------------------------------------------------------------


def test_missing_variant_is_pending_not_omitted(tmp_path: Path) -> None:
    sources = _synthetic(tmp_path, gnn_rmse={"homo_sage": 4.5})
    comparison = load_dataset(sources)
    assert comparison.pending == ("hetero_sage", "hetero_gat")
    assert comparison.gnns == GNN_VARIANTS

    rows = list(csv.DictReader(io.StringIO(to_csv([comparison]))))
    pending = [r for r in rows if r["status"] == PENDING]
    assert {r["model"] for r in pending} == {"hetero_sage", "hetero_gat"}
    assert len(pending) == 2 * 2 * len(METRIC_NAMES)
    assert all(r["average"] == "" for r in pending)
    assert f"`hetero_gat` | {PENDING}" in summary_table(comparison)
    assert "**Pendientes:** `hetero_sage`, `hetero_gat`" in to_markdown([comparison], "cmd")


def test_variant_with_run_but_without_rows_is_pending(tmp_path: Path) -> None:
    sources = _synthetic(tmp_path, gnn_rmse={"homo_sage": 4.5})
    (sources.gnn_dir / "run_hetero_gat.json").write_text(
        json.dumps(_synthetic_gnn_run()), encoding="utf-8"
    )
    assert "hetero_gat" in load_dataset(sources).pending


def test_no_gnn_report_marks_all_variants_pending(tmp_path: Path) -> None:
    sources = _synthetic(tmp_path)
    (sources.gnn_dir / "report.csv").unlink()
    comparison = load_dataset(sources)
    assert comparison.pending == GNN_VARIANTS
    result = assess_criterion(comparison)
    assert not result.met and result.best_gnn is None


def test_criterion_uses_test_rmse_and_lists_beaten_baselines(tmp_path: Path) -> None:
    # dummy_mean 5.0, ridge 4.0 en test; las GNN 4.5 (val 5.0, peor que ridge en val 4.5).
    sources = _synthetic(
        tmp_path, gnn_rmse={"homo_sage": 4.5, "hetero_sage": 4.0, "hetero_gat": 6.0}
    )
    result = assess_criterion(load_dataset(sources))
    assert result.met
    assert set(result.pairs) == {
        ("homo_sage", "dummy_mean"),
        ("hetero_sage", "dummy_mean"),
        ("hetero_sage", "ridge"),  # igualar cuenta
    }
    assert result.best_gnn == "hetero_sage"
    assert result.best_baseline == "ridge"


def test_criterion_not_met_when_every_gnn_is_worse(tmp_path: Path) -> None:
    sources = _synthetic(tmp_path, gnn_rmse={v: 9.0 for v in GNN_VARIANTS})
    comparison = load_dataset(sources)
    assert not assess_criterion(comparison).met
    assert "| Sintético | no |" in to_markdown([comparison], "cmd")


def test_criterion_ignores_val(tmp_path: Path) -> None:
    sources = _synthetic(tmp_path, gnn_rmse={v: 4.5 for v in GNN_VARIANTS})
    before = assess_criterion(load_dataset(sources))
    path = sources.gnn_dir / "report.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(
        "\n".join(line.replace("5.0", "99.0") if ",val,rmse," in line else line for line in lines),
        encoding="utf-8",
    )
    assert assess_criterion(load_dataset(sources)) == before


# --- salidas -----------------------------------------------------------------------------


def test_csv_has_one_row_per_dataset_model_split_metric(tmp_path: Path) -> None:
    synthetic = load_dataset(_synthetic(tmp_path / "s"))
    d1 = load_dataset(_d1(tmp_path / "d"))
    rows = list(csv.DictReader(io.StringIO(to_csv([synthetic, d1]))))
    assert tuple(rows[0]) == CSV_COLUMNS
    keys = [(r["dataset"], r["model"], r["split"], r["metric"]) for r in rows]
    assert len(keys) == len(set(keys)) == 2 * 5 * 2 * len(METRIC_NAMES)
    assert {r["family"] for r in rows if r["model"] in GNN_VARIANTS} == {"gnn"}
    assert {r["family"] for r in rows if r["model"] in {"dummy_mean", "ridge"}} == {"baseline"}
    assert {r["split"] for r in rows} == {"val", "test"}
    assert {r["status"] for r in rows} == {"ok"}


def test_markdown_reports_criterion_alignment_and_per_target_detail(tmp_path: Path) -> None:
    d1 = load_dataset(_d1(tmp_path))
    text = to_markdown([d1], "python scripts/compare_models.py")
    assert "## Criterio de salida de F4 (provisional)" in text
    assert "**Provisional.**" in text and "no son concluyentes" in text
    assert "¿Se cumple? (provisional)" in text
    assert "mmol/kg (en D1, de digesta fresca, base húmeda)" in text
    assert "| D1 | sí | `homo_sage` | `ridge` | las 3 GNN a los 2 baselines |" in text
    assert "`configs/splits/toy.json`" in text
    assert "commit `c0ffee`" in text
    assert "| model | split | metric | acetate | propionate | butyrate | average |" in text


def test_only_val_and_test_rows_are_compared(tmp_path: Path) -> None:
    sources = _synthetic(tmp_path)
    path = sources.baseline_dir / "report.csv"
    with path.open("a", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerow(["ridge", "train", "rmse", 1, 1, 1, 1])
    comparison = load_dataset(sources)
    assert {row.split for row in comparison.report.rows} == {"val", "test"}
