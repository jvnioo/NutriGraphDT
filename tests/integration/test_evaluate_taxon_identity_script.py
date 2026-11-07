"""`scripts/evaluate_taxon_identity.py`: partes sin entrenar (#266)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "evaluate_taxon_identity.py"


@pytest.fixture(scope="module")
def script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("evaluate_taxon_identity", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _row(script: ModuleType, reference: str, low: float, high: float, delta: float) -> dict:
    return {
        "arm": script.LINEAGE,
        "reference": reference,
        "model": "hetero_sage",
        "metric": "fraction_mae_pp",
        "ci_low": low,
        "ci_high": high,
        "mean_delta": delta,
    }


def test_conclusion_says_when_the_graph_does_not_beat_the_family_table(script: ModuleType) -> None:
    lines = script.conclusion_lines([_row(script, script.RIDGE_FAMILY, -0.1, 0.9, 0.4)], [])

    assert "no supera" in lines[0]
    assert "no agrega capacidad predictiva" in lines[0]


def test_conclusion_says_when_the_graph_beats_the_family_table(script: ModuleType) -> None:
    lines = script.conclusion_lines([_row(script, script.RIDGE_FAMILY, -0.9, -0.1, -0.5)], [])

    assert "supera a `ridge`" in lines[0]
    assert "`hetero_sage`" in lines[0]


def test_conclusion_does_not_blame_only_the_graph_when_ridge_finds_signal(
    script: ModuleType,
) -> None:
    family_better = {
        **_row(script, script.RIDGE_DESIGN, -0.5, -0.1, -0.3),
        "arm": script.RIDGE_FAMILY,
    }
    lines = script.conclusion_lines(
        [_row(script, script.RIDGE_FAMILY, 0.1, 0.9, 0.5), family_better], []
    )

    assert "no aprovecha" in lines[-1]
    assert "no se probó" in lines[-1] or "se probó aquí" in lines[-1]


def test_a_worse_significant_result_is_not_an_improvement(script: ModuleType) -> None:
    assert not script._improves(_row(script, script.RIDGE_FAMILY, 0.1, 0.9, 0.5))
    higher = {**_row(script, script.RIDGE_FAMILY, 0.1, 0.9, 0.5), "metric": "fraction_r2"}
    assert script._improves(higher)


def test_resume_reads_the_reports_already_written(script: ModuleType, tmp_path: Path) -> None:
    from nutrigraphdt.models.metrics import EvaluationReport, MetricRow

    report = EvaluationReport(
        rows=(
            MetricRow(
                "hetero_sage",
                "fraction_mae_pp",
                {"acetate": 1.0, "propionate": 2.0, "butyrate": 3.0},
                2.0,
                split="test",
                group="all",
            ),
        )
    )
    key = {"seed": 1, "fold": 2, "model": "hetero_sage", "arm": script.ACTUAL}

    script._record_fold(tmp_path, key, report, {"status": "ok"})
    done = script._load_done(tmp_path)

    restored = done[("hetero_sage", script.ACTUAL)][(1, 2)]
    assert restored.rows[0].average == 2.0
    assert restored.rows[0].targets["propionate"] == 2.0
    assert restored.rows[0].group == "all"


def test_resume_finds_the_ridge_folds_so_they_are_not_repeated(
    script: ModuleType, tmp_path: Path
) -> None:
    from nutrigraphdt.models.metrics import EvaluationReport, MetricRow

    # Como en `run_ridge_arms`: el reporte se llama como su tabla, el fold como `tabular`.
    report = EvaluationReport(
        rows=(MetricRow(script.RIDGE_FAMILY, "fraction_mae_pp", {}, 2.0, "test", "all"),)
    )
    key = {"seed": 0, "fold": 1, "model": script.TABULAR, "arm": script.RIDGE_FAMILY}

    script._record_fold(tmp_path, key, report, {"status": "ok"})
    done = script._load_done(tmp_path)

    assert (0, 1) in done[(script.TABULAR, script.RIDGE_FAMILY)]
    assert done[(script.TABULAR, script.RIDGE_FAMILY)][(0, 1)].rows[0].model == script.RIDGE_FAMILY


def test_missing_graphs_exit_with_code_2(script: ModuleType, tmp_path: Path) -> None:
    assert script.main(["--graphs-dir", str(tmp_path), "--output", str(tmp_path / "out")]) == 2
