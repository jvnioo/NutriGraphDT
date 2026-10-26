"""Pruebas de integración del reporte GNN D1 con el fixture HoloFood."""

from __future__ import annotations

import csv
import dataclasses
import hashlib
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

from nutrigraphdt.data.config import load_sources  # noqa: E402
from nutrigraphdt.data.integration import attach_sample_context  # noqa: E402
from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader  # noqa: E402
from nutrigraphdt.data.pipeline import DataPipeline  # noqa: E402
from nutrigraphdt.data.split import get_split  # noqa: E402
from nutrigraphdt.graph.audit import audit_built_graphs  # noqa: E402
from nutrigraphdt.graph.builder import build_hetero_graph  # noqa: E402
from nutrigraphdt.models.gnn import load_model_config  # noqa: E402
from nutrigraphdt.models.metrics import METRIC_NAMES  # noqa: E402
from nutrigraphdt.models.training import (  # noqa: E402
    apply_overrides,
    load_training_config,
    prepare_training_graphs,
)
from nutrigraphdt.models.training.pipeline import run_training  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "holofood"
SPLIT_CONFIG = FIXTURES / "split.json"
REPORT_SCRIPT = REPO_ROOT / "scripts" / "report_gnn.py"
VARIANTS = ("homo_sage", "hetero_sage", "hetero_gat")
TARGETS = ("acetate", "propionate", "butyrate")


def _run_report(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPORT_SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        cwd=REPO_ROOT,
        check=False,
    )


def _fixture_graphs() -> dict[str, Any]:
    sources = load_sources(REPO_ROOT / "configs" / "sources.json")

    def fixture_source(source_id: str, file_name: str) -> Any:
        return dataclasses.replace(sources[source_id], path_or_url=str(FIXTURES / file_name))

    abundance = fixture_source("D1_holofood", "abundance_ssu_caecum.tsv")
    tables = DataPipeline({"D1_holofood": abundance}).run(["D1_holofood"]).dataset
    tables, _ = attach_sample_context(
        tables,
        metadata=MetadataLoader(fixture_source("D1_holofood_metadata", "metadata.tsv")).load(),
        metabolites=MetaboliteLoader(
            fixture_source("D1_holofood_scfa_content", "scfa_caecum_content.tsv")
        ).load(),
    )
    built = build_hetero_graph(tables)
    audit = audit_built_graphs(built)
    assert not audit.report.errors
    assert set(audit.report.deliverable_graph_ids) == set(built.graphs)
    return built.graphs


@pytest.fixture(scope="module")
def d1_runs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    graphs = _fixture_graphs()
    split = get_split(split_file=SPLIT_CONFIG)
    config = apply_overrides(
        load_training_config(REPO_ROOT / "configs" / "training" / "default.json"),
        {"max_epochs": 1, "patience": 1, "split_file": str(SPLIT_CONFIG)},
    )
    prepared = prepare_training_graphs(
        None, graphs, split, validated=True, batch_size=config.batch_size, seed=config.seed
    )
    assert all(
        prepared.summary[subset].with_all_scfa == len(split[subset])
        for subset in ("train", "val", "test")
    )

    runs_root = tmp_path_factory.mktemp("gnn-d1-runs")
    run_dirs: dict[str, Path] = {}
    for variant in VARIANTS:
        run = run_training(
            prepared,
            load_model_config(REPO_ROOT / "configs" / "models" / f"{variant}.yaml"),
            config,
            split,
            split_file=SPLIT_CONFIG,
            runs_dir=runs_root / variant,
            repo_root=REPO_ROOT,
            source={"dataset": "d1", "fixture": True},
        )
        run_dirs[variant] = run.run_dir
    return run_dirs


@pytest.fixture
def d1_baseline(tmp_path: Path, d1_runs: dict[str, Path]) -> tuple[Path, Path, dict[str, Any]]:
    info = json.loads((d1_runs["homo_sage"] / "run.json").read_text(encoding="utf-8"))
    baseline = {
        "dataset_id": info["dataset_id"],
        "subset_sizes": {
            subset: info["subsets"][subset]["with_all_scfa"] for subset in ("train", "val", "test")
        },
    }
    baseline_run_path = tmp_path / "baseline-run.json"
    baseline_run_path.write_text(json.dumps(baseline), encoding="utf-8")

    baseline_report_path = tmp_path / "baseline-report.csv"
    fields = ("model", "split", "metric", *TARGETS, "average")
    with baseline_report_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for subset in ("val", "test"):
            for metric in METRIC_NAMES:
                writer.writerow(
                    {
                        "model": "dummy_mean",
                        "split": subset,
                        "metric": metric,
                        **dict.fromkeys(TARGETS, "0.0"),
                        "average": "0.0",
                    }
                )
    return baseline_run_path, baseline_report_path, baseline


def _report_args(
    run_dirs: dict[str, Path],
    baseline_paths: tuple[Path, Path, dict[str, Any]],
    output: Path,
) -> list[str]:
    baseline_run_path, baseline_report_path, _ = baseline_paths
    args = [
        "--dataset",
        "d1",
        "--split-config",
        str(SPLIT_CONFIG),
        "--baseline-run-json",
        str(baseline_run_path),
        "--baseline-report-csv",
        str(baseline_report_path),
        "--output",
        str(output),
    ]
    for variant in VARIANTS:
        args.extend((f"--{variant.replace('_', '-')}-run", str(run_dirs[variant])))
    return args


def test_generates_d1_report_from_fixture_runs(
    tmp_path: Path,
    d1_runs: dict[str, Path],
    d1_baseline: tuple[Path, Path, dict[str, Any]],
) -> None:
    output = tmp_path / "d1-report"
    completed = _run_report(*_report_args(d1_runs, d1_baseline, output))

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert {path.name for path in output.iterdir()} == {
        "report.md",
        "report.csv",
        *(f"run_{variant}.json" for variant in VARIANTS),
    }
    report = (output / "report.md").read_text(encoding="utf-8")
    for expected in (
        "Conteos por subconjunto",
        "Duración y trazabilidad de las corridas",
        "Advertencias",
        "dummy_mean",
        "tratamiento dietario",
        "taxones están aislados",
        f"solo {d1_baseline[2]['subset_sizes']['val']} animales",
        "Commit",
        "Dirty",
    ):
        assert expected in report
    assert "| val | 2 |" in report
    assert all((output / f"run_{variant}.json").is_file() for variant in VARIANTS)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("split", "file"), "configs/splits/other.json", "split.file"),
        (("split", "version"), "9.9.9", "split.version"),
        (("split", "sha256"), "different-hash", "split.sha256"),
        (("dataset_id",), "other-dataset", "dataset_id"),
        (("subsets", "val", "with_all_scfa"), 99, "with_all_scfa"),
    ],
)
def test_rejects_mismatched_d1_run_metadata(
    tmp_path: Path,
    d1_runs: dict[str, Path],
    d1_baseline: tuple[Path, Path, dict[str, Any]],
    path: tuple[str, ...],
    value: Any,
    message: str,
) -> None:
    changed_runs: dict[str, Path] = {}
    for variant in VARIANTS:
        target = tmp_path / variant
        shutil.copytree(d1_runs[variant], target)
        changed_runs[variant] = target

    run_path = changed_runs["homo_sage"] / "run.json"
    info = json.loads(run_path.read_text(encoding="utf-8"))
    nested = info
    for key in path[:-1]:
        nested = nested[key]
    nested[path[-1]] = value
    run_path.write_text(json.dumps(info), encoding="utf-8")

    output = tmp_path / "invalid-report"
    completed = _run_report(*_report_args(changed_runs, d1_baseline, output))

    assert completed.returncode == 2
    assert message in completed.stderr
    assert not output.exists()


def test_accepts_non_cpu_device_and_reports_run_provenance(
    tmp_path: Path,
    d1_runs: dict[str, Path],
    d1_baseline: tuple[Path, Path, dict[str, Any]],
) -> None:
    changed_runs: dict[str, Path] = {}
    for variant in VARIANTS:
        target = tmp_path / variant
        shutil.copytree(d1_runs[variant], target)
        changed_runs[variant] = target

    run_path = changed_runs["homo_sage"] / "run.json"
    info = json.loads(run_path.read_text(encoding="utf-8"))
    info["environment"]["device"] = "cuda:0"
    info["git"] = {"commit": "test-commit", "dirty": True}
    run_path.write_text(json.dumps(info), encoding="utf-8")

    output = tmp_path / "provenance-report"
    completed = _run_report(*_report_args(changed_runs, d1_baseline, output))
    assert completed.returncode == 0, completed.stdout + completed.stderr

    report = (output / "report.md").read_text(encoding="utf-8")
    assert "| homo_sage | cuda:0 |" in report
    assert "`test-commit` | sí |" in report


def test_accepts_legacy_byte_hash_of_a_crlf_split_file(
    tmp_path: Path,
    d1_runs: dict[str, Path],
    d1_baseline: tuple[Path, Path, dict[str, Any]],
) -> None:
    """Una corrida registrada en Windows antes de #133 (hash de bytes con CRLF) sigue siendo válida,
    mezclada con corridas nuevas de hash canónico."""
    lf = SPLIT_CONFIG.read_bytes().replace(b"\r\n", b"\n")
    legacy_crlf = hashlib.sha256(lf.replace(b"\n", b"\r\n")).hexdigest()
    changed_runs: dict[str, Path] = {}
    for variant in VARIANTS:
        target = tmp_path / variant
        shutil.copytree(d1_runs[variant], target)
        changed_runs[variant] = target
    run_path = changed_runs["homo_sage"] / "run.json"
    info = json.loads(run_path.read_text(encoding="utf-8"))
    assert info["split"]["sha256"] != legacy_crlf
    info["split"]["sha256"] = legacy_crlf
    run_path.write_text(json.dumps(info), encoding="utf-8")

    output = tmp_path / "legacy-report"
    completed = _run_report(*_report_args(changed_runs, d1_baseline, output))

    assert completed.returncode == 0, completed.stdout + completed.stderr
