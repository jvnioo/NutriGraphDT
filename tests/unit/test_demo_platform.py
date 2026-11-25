"""Corrida activa de la Web App y caché del motor (A88-P3, #300)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nutrigraphdt.demo import platform


def test_active_run_comes_from_the_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(platform.RUN_ENV, raising=False)
    assert platform.active_run_name() == "synthetic"


def test_environment_overrides_the_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(platform.RUN_ENV, "d1_fixture")
    assert platform.active_run_name() == "d1_fixture"


def test_unknown_run_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(platform.RUN_ENV, raising=False)
    config = tmp_path / "platform.json"
    config.write_text(json.dumps({"run": "otra"}), encoding="utf-8")
    with pytest.raises(platform.PlatformConfigError, match="otra"):
        platform.active_run_name(config)


def test_run_metadata_reads_the_frozen_run_without_the_model() -> None:
    metadata = platform.run_metadata("synthetic")

    assert metadata["is_synthetic"] is True
    assert metadata["dataset_id"] == "synthetic_cohort"
    assert metadata["n_animals"] == {"train": 12, "inner_val": 4, "test": 4}
    assert metadata["contract_version"] == "1.0.0"
    assert metadata["commit"]
    assert any(row["metric"] == "fraction_mae_pp" for row in metadata["metrics"])


def test_engine_is_loaded_once_per_process() -> None:
    pytest.importorskip("torch")
    pytest.importorskip("torch_geometric")
    pytest.importorskip("sklearn")
    pytest.importorskip("streamlit")
    from nutrigraphdt.demo import cache

    cache.engine.clear()
    cache.ENGINE_LOADS.clear()
    first = cache.engine("synthetic")
    second = cache.engine("synthetic")

    assert first is second
    assert cache.ENGINE_LOADS["synthetic"] == 1
