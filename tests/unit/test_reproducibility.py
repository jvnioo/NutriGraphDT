"""Pruebas de `nutrigraphdt.models.training.reproducibility` (A45-8, #108)."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from nutrigraphdt.models.training.reproducibility import (
    DIFFERS,
    OK,
    UNAVAILABLE,
    Check,
    ReproductionError,
    ReproductionReport,
    compare_info,
    compare_rows,
    compare_scaling,
    only_splits,
    read_run_info,
    report_rows,
    sibling,
    split_file_digests,
)

SPLIT_BYTES = b'{\n  "version": "2.0.0"\n}\n'
LF_SHA = hashlib.sha256(SPLIT_BYTES).hexdigest()
CRLF_SHA = hashlib.sha256(SPLIT_BYTES.replace(b"\n", b"\r\n")).hexdigest()


def run_info(**overrides: Any) -> dict[str, Any]:
    info: dict[str, Any] = {
        "run_id": "20261015-000000_homo_sage_s42",
        "variant": "homo_sage",
        "seed": 42,
        "dataset_id": "toy",
        "source": {"dataset": "d1", "graphs": "artifacts/graphs/D1_holofood"},
        "training_config": {"lr": 0.001, "seed": 42},
        "model_config": {"variant": "homo_sage", "hidden_channels": 64},
        "metadata": {"node_channels": {"taxon": 1}},
        "split": {"file": "configs/splits/x.json", "version": "2.0.0", "sha256": LF_SHA},
        "subsets": {"train": {"with_all_scfa": 3}},
        "scaling": {"target": {"mean": [10.0, 2.0], "std": [3.0, 1.0]}},
        "best_epoch": 4,
        "epochs_run": 24,
        "stopped_early": True,
        "git": {"commit": "a" * 40, "dirty": False},
        "environment": {"python": "3.13.1", "platform": "Windows", "device": "cpu"},
    }
    info.update(overrides)
    return info


def rows(*values: float) -> list[dict[str, str]]:
    return [
        {
            "sample_id": f"s{i}",
            "subset": "test",
            "predicted_acetate": repr(v),
            "measured_acetate": "1.0",
        }
        for i, v in enumerate(values)
    ]


# --- lectura -----------------------------------------------------------------------------


def test_read_run_info_from_directory_and_file(tmp_path: Path) -> None:
    (tmp_path / "run.json").write_text(json.dumps(run_info()), encoding="utf-8")
    directory, info = read_run_info(tmp_path)
    assert directory == tmp_path and info["variant"] == "homo_sage"
    assert read_run_info(tmp_path / "run.json")[0] == tmp_path


def test_renamed_copy_has_no_run_directory(tmp_path: Path) -> None:
    """Junto a `reports/gnn/<dataset>/run_<variante>.json` hay archivos de otras corridas."""
    copy_path = tmp_path / "run_homo_sage.json"
    copy_path.write_text(json.dumps(run_info()), encoding="utf-8")
    (tmp_path / "metrics.csv").write_text("x\n", encoding="utf-8")
    directory, info = read_run_info(copy_path)
    assert directory is None
    assert sibling(directory, info, "metrics", "metrics.csv") is None


@pytest.mark.parametrize(
    ("content", "message"),
    [("{", "JSON inválido"), ("[]", "objeto JSON"), ('{"run_id": "x"}', "faltan")],
)
def test_invalid_run_json_is_rejected(tmp_path: Path, content: str, message: str) -> None:
    (tmp_path / "run.json").write_text(content, encoding="utf-8")
    with pytest.raises(ReproductionError, match=message):
        read_run_info(tmp_path)


def test_missing_run_json_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ReproductionError, match="Falta"):
        read_run_info(tmp_path)


def test_sibling_uses_files_from_run_json(tmp_path: Path) -> None:
    (tmp_path / "otro.csv").write_text("x\n", encoding="utf-8")
    info = run_info(files={"metrics": "otro.csv"})
    assert sibling(tmp_path, info, "metrics", "metrics.csv") == tmp_path / "otro.csv"
    assert sibling(tmp_path, info, "history", "history.csv") is None


# --- run.json ----------------------------------------------------------------------------


def test_identical_info_passes_every_check() -> None:
    checks = compare_info(run_info(), run_info(run_id="otro", git={"commit": "b" * 40}))
    assert [c.status for c in checks] == [OK, OK, OK, OK]


@pytest.mark.parametrize(
    ("key", "value", "check_index"),
    [
        ("seed", 7, 0),
        ("source", {"dataset": "synthetic", "graphs": "artifacts/graphs/D1_holofood"}, 0),
        ("training_config", {"lr": 0.01, "seed": 42}, 0),
        ("model_config", {"variant": "homo_sage", "hidden_channels": 32}, 0),
        ("subsets", {"train": {"with_all_scfa": 4}}, 1),
        ("metadata", {"node_channels": {"taxon": 2}}, 1),
        ("best_epoch", 5, 3),
        ("epochs_run", 25, 3),
        ("stopped_early", False, 3),
    ],
)
def test_info_differences_are_reported(key: str, value: Any, check_index: int) -> None:
    checks = compare_info(run_info(), run_info(**{key: value}))
    assert checks[check_index].status == DIFFERS
    assert f"`{key}`" in checks[check_index].detail


def test_graphs_path_in_source_is_not_compared() -> None:
    new = run_info(source={"dataset": "d1", "graphs": "otra/carpeta"})
    assert compare_info(run_info(), new)[0].status == OK


def test_missing_outside_cohort_counts_as_zero() -> None:
    # Las corridas anteriores a #138 no registran `outside_cohort` en sus subconjuntos.
    new = run_info(subsets={"train": {"with_all_scfa": 3, "outside_cohort": 0}})
    assert compare_info(run_info(), new)[1].status == OK


def test_outside_cohort_difference_is_reported() -> None:
    new = run_info(subsets={"train": {"with_all_scfa": 3, "outside_cohort": 2}})
    check = compare_info(run_info(), new)[1]
    assert check.status == DIFFERS
    assert "`subsets`" in check.detail


def test_split_hash_from_crlf_copy_is_accepted_only_with_digests(tmp_path: Path) -> None:
    path = tmp_path / "split.json"
    path.write_bytes(SPLIT_BYTES)
    digests = split_file_digests(path)
    assert {LF_SHA, CRLF_SHA} <= digests
    windows = run_info(split={**run_info()["split"], "sha256": CRLF_SHA})

    assert compare_info(windows, run_info())[1].status == DIFFERS
    accepted = compare_info(windows, run_info(), split_digests=digests)[1]
    assert accepted.status == OK and "CRLF" in accepted.detail


def test_line_ending_tolerance_does_not_hide_other_split_changes(tmp_path: Path) -> None:
    path = tmp_path / "split.json"
    path.write_bytes(SPLIT_BYTES)
    digests = split_file_digests(path)
    other_version = run_info(split={**run_info()["split"], "sha256": CRLF_SHA, "version": "3"})
    assert compare_info(other_version, run_info(), split_digests=digests)[1].status == DIFFERS
    other_file = run_info(split={**run_info()["split"], "sha256": "0" * 64})
    assert compare_info(other_file, run_info(), split_digests=digests)[1].status == DIFFERS
    other_subsets = run_info(
        split={**run_info()["split"], "sha256": CRLF_SHA}, subsets={"train": {}}
    )
    assert compare_info(other_subsets, run_info(), split_digests=digests)[1].status == DIFFERS


def test_scaling_uses_relative_tolerance() -> None:
    original = run_info()["scaling"]
    close = copy.deepcopy(original)
    close["target"]["mean"][0] = 10.0 * (1 + 5e-7)
    far = copy.deepcopy(original)
    far["target"]["std"][1] = 1.001
    assert compare_scaling(original, close).status == OK
    result = compare_scaling(original, far)
    assert result.status == DIFFERS and "std[1]" in result.detail
    assert compare_scaling(None, original).status == UNAVAILABLE
    assert compare_scaling(original, {"target": {}}).status == DIFFERS


# --- filas -------------------------------------------------------------------------------


def test_rows_within_tolerance_are_ok() -> None:
    check = compare_rows("p", rows(1.0, 2.0), rows(1.00005, 2.0), ("sample_id", "subset"), 1e-4)
    assert check.status == OK
    assert check.max_diff == pytest.approx(5e-5)
    assert check.detail == "2 filas"


def test_rows_beyond_tolerance_say_where() -> None:
    check = compare_rows("p", rows(1.0, 2.0), rows(1.0, 2.01), ("sample_id", "subset"), 1e-4)
    assert check.status == DIFFERS
    assert "s1/test predicted_acetate" in check.detail


def test_rows_with_different_keys_differ() -> None:
    other = rows(1.0)
    other[0]["sample_id"] = "zz"
    assert compare_rows("p", rows(1.0), other, ("sample_id", "subset"), 1.0).status == DIFFERS


def test_unmeasured_value_only_matches_unmeasured() -> None:
    original = rows(1.0)
    original[0]["measured_acetate"] = ""
    assert compare_rows("p", original, original, ("sample_id",), 1e-4).status == OK
    assert compare_rows("p", original, rows(1.0), ("sample_id",), 1e-4).status == DIFFERS


def test_missing_original_rows_are_unavailable() -> None:
    check = compare_rows("p", None, rows(1.0), ("sample_id",), 1e-4, missing_reason="sin copia")
    assert check.status == UNAVAILABLE and check.detail == "sin copia"


def test_selected_columns_only() -> None:
    a, b = rows(1.0), rows(1.0)
    b[0]["measured_acetate"] = "9.0"
    assert compare_rows("p", a, b, ("sample_id",), 1e-4).status == DIFFERS
    columns = ["predicted_acetate"]
    assert compare_rows("p", a, b, ("sample_id",), 1e-4, columns=columns).status == OK


def test_report_rows_keep_only_the_variant_val_and_test(tmp_path: Path) -> None:
    report = tmp_path / "report.csv"
    report.write_text(
        "model,split,metric,acetate,average\n"
        "homo_sage,val,rmse,1,1\nhomo_sage,test,rmse,2,2\n"
        "homo_sage,train,rmse,3,3\nridge,test,rmse,4,4\n",
        encoding="utf-8",
    )
    found = report_rows(report, "homo_sage")
    assert found == [
        {"split": "val", "metric": "rmse", "acetate": "1", "average": "1"},
        {"split": "test", "metric": "rmse", "acetate": "2", "average": "2"},
    ]
    assert report_rows(report, "hetero_gat") is None
    assert report_rows(tmp_path / "nada.csv", "homo_sage") is None


def test_only_splits_drops_model_and_train() -> None:
    metrics = [
        {"model": "m", "split": "train", "metric": "mae"},
        {"model": "m", "split": "test", "metric": "mae"},
    ]
    assert only_splits(metrics, {"val", "test"}) == [{"split": "test", "metric": "mae"}]


# --- reporte -----------------------------------------------------------------------------


def test_report_is_reproduced_only_without_differences_and_with_metrics() -> None:
    metric = Check("Métricas (metrics.csv)", OK, max_diff=0.0, tolerance=1e-5)
    unavailable = Check("Predicciones (predictions.csv)", UNAVAILABLE)
    assert ReproductionReport(run_info(), run_info(), (metric, unavailable)).reproduced_ok
    differs = Check("Pesos del checkpoint", DIFFERS)
    assert not ReproductionReport(run_info(), run_info(), (metric, differs)).reproduced_ok
    no_metrics = Check("Métricas val y test (report.csv)", UNAVAILABLE)
    assert not ReproductionReport(run_info(), run_info(), (no_metrics,)).reproduced_ok


def test_report_markdown_and_dict() -> None:
    new = run_info(
        run_id="20261016-000000_homo_sage_s42",
        environment={"python": "3.13.14", "platform": "Linux", "device": "cpu"},
    )
    checks = (
        Check("Métricas (metrics.csv)", OK, "12 filas", 1.1e-6, 1e-5),
        Check("Pesos del checkpoint", DIFFERS, "16 tensores", 2.0, 1e-4),
    )
    report = ReproductionReport(run_info(), new, checks, ("Nota de prueba.",))
    text = report.to_markdown("cmd")
    assert text.startswith("# Reproducción de `20261015-000000_homo_sage_s42` (A45-8)")
    assert "**No se reproduce**: Pesos del checkpoint." in text
    assert "| Sistema | `Windows` | `Linux` |" in text
    assert "| Commit | `aaaaaaaaaaaa` |" in text
    assert "| Métricas (metrics.csv) | ok | 1.1e-06 | 1.0e-05 | 12 filas |" in text
    assert "- Nota de prueba." in text
    data = report.to_dict()
    assert data["reproduced"] is False
    assert data["original"]["platform"] == "Windows"
    assert data["tolerances"]["weights"] == 1e-4
    assert [c["status"] for c in data["checks"]] == [OK, DIFFERS]
