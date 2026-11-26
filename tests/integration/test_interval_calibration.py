"""Calibración del intervalo de la plataforma con la cohorte sintética (A101-P1b, #391).

El motor aplica el factor de `reports/uncertainty/synthetic/calibration.json` solo a una corrida
con la misma configuración; a las demás les deja el intervalo sin calibrar y dice por qué.
Requiere los extras `graph` y `baselines`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")

from nutrigraphdt import api  # noqa: E402
from nutrigraphdt.demo import results  # noqa: E402
from nutrigraphdt.models.uncertainty import IntervalCalibration  # noqa: E402
from nutrigraphdt.simulation import scenario_by_id  # noqa: E402


@pytest.fixture(scope="module")
def calibration() -> IntervalCalibration:
    return IntervalCalibration.load(api.DEFAULT_CALIBRATION_PATH)


@pytest.fixture(scope="module")
def engine() -> Any:
    return api.DEMO_RUNS["synthetic"].engine()


def _run_info(name: str) -> dict[str, Any]:
    path = api.DEMO_RUNS[name].run_dir / "run.json"
    return dict(json.loads(path.read_text(encoding="utf-8")))


def test_versioned_calibration_describes_the_platform_run(
    calibration: IntervalCalibration,
) -> None:
    assert calibration.dataset_id == "synthetic_cohort"
    assert calibration.method == "mc_dropout" and calibration.level == 0.8
    assert calibration.source == "reports/uncertainty/synthetic"
    assert calibration.n_folds == 50
    assert all(factor > 0 for factor in calibration.scale)
    assert calibration.mismatches(_run_info("synthetic")) == []


def test_other_runs_are_not_calibrated(calibration: IntervalCalibration) -> None:
    assert any(
        "constraint_lambda" in p for p in calibration.mismatches(_run_info("synthetic_constrained"))
    )
    assert any("dataset_id" in p for p in calibration.mismatches(_run_info("d1_fixture")))
    constrained = api.DEMO_RUNS["synthetic_constrained"].engine()
    assert constrained.calibration is None
    assert constrained.calibration_note.startswith("sin calibrar")
    interval = constrained.interval(scenario_by_id("basal").request())
    assert interval.method == api.INTERVAL_METHOD


def test_engine_applies_the_factor(engine: Any, calibration: IntervalCalibration) -> None:
    request = scenario_by_id("basal").request()
    calibrated = engine.interval(request)
    assert calibrated.method == api.CALIBRATED_INTERVAL_METHOD
    assert engine.calibration == calibration
    assert engine.calibration_note.startswith("calibrado")
    raw_engine = api.ScenarioEngine(engine.run_dir, engine.base, calibration_path=None)
    raw = raw_engine.interval(request)
    assert raw.method == api.INTERVAL_METHOD
    assert raw_engine.calibration_note.startswith("sin calibrar")
    assert calibrated.log_total is not None and raw.log_total is not None
    ratio = (calibrated.log_total.upper - calibrated.log_total.lower) / (
        raw.log_total.upper - raw.log_total.lower
    )
    assert ratio == pytest.approx(calibration.scale[2], rel=1e-6)


def test_missing_or_mismatched_file_leaves_the_interval_uncalibrated(
    engine: Any, calibration: IntervalCalibration, tmp_path: Path
) -> None:
    missing = api.ScenarioEngine(engine.run_dir, engine.base, calibration_path=tmp_path / "x.json")
    assert missing.calibration is None and "no existe" in missing.calibration_note
    other = IntervalCalibration.from_dict(
        {**calibration.to_dict(), "training": {**calibration.training, "max_epochs": 999}}
    )
    path = other.save(tmp_path / "calibration.json")
    mismatched = api.ScenarioEngine(engine.run_dir, engine.base, calibration_path=path)
    assert mismatched.calibration is None and "max_epochs" in mismatched.calibration_note


def test_caption_says_which_calibration_applies() -> None:
    calibrated = results.interval_caption(api.CALIBRATED_INTERVAL_METHOD, 0.8, "detalle")
    assert "**calibrado**" in calibrated and "reports/uncertainty/synthetic" in calibrated
    assert calibrated.endswith("Detalle: detalle")
    raw = results.interval_caption(api.INTERVAL_METHOD, 0.8)
    assert "**sin calibrar**" in raw
    assert results.CALIBRATED_METHOD == api.CALIBRATED_INTERVAL_METHOD
