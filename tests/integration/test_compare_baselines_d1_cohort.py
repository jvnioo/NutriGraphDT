"""`compare_baselines.py --dataset d1` usa solo la cohorte supervisada (#138).

Requiere los extras `graph` (verificación del target con `add_graph_target`) y `baselines`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")

REPO_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "compare_baselines_script", REPO_ROOT / "scripts" / "compare_baselines.py"
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
_load_d1_dataset = _MODULE._load_d1_dataset


def test_d1_tabular_dataset_is_restricted_to_the_cohort(holofood_fixture_sources: Path) -> None:
    dataset, groups, meta = _load_d1_dataset(holofood_fixture_sources, min_ssu_reads=10000)

    assert len(dataset) == 5
    assert "SAMEA112904764" not in dataset.sample_ids
    assert meta["cohort"]["size"] == 5
    assert meta["cohort"]["steps"][-1]["removed"] == ["SAMEA112904764"]
    assert meta["target_verification"]["verified_samples"] == 5
    assert set(dataset.sample_ids) <= set(groups)


def test_official_threshold_keeps_the_six_fixture_animals(holofood_fixture_sources: Path) -> None:
    dataset, _, meta = _load_d1_dataset(holofood_fixture_sources)

    assert len(dataset) == 6
    assert meta["cohort"]["min_ssu_reads"] == 1000
