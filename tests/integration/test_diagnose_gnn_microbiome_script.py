"""`scripts/diagnose_gnn_microbiome.py`: la grilla no lee el test y la selección es determinista."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from types import ModuleType

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")

from torch_geometric.data import HeteroData  # noqa: E402

from nutrigraphdt.models.training import load_training_config  # noqa: E402
from nutrigraphdt.models.training.cv_inputs import (  # noqa: E402
    CVInputs,
    load_synthetic_cv_inputs,
    synthetic_cv_plan,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "diagnose_gnn_microbiome.py"


@pytest.fixture(scope="module")
def script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("diagnose_gnn_microbiome", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_grid_starts_with_the_current_configuration(script: ModuleType) -> None:
    grid = script.candidates()
    assert grid[0] == script.Candidate()
    assert len(grid) == 24
    assert len({candidate.name for candidate in grid}) == 24


def _rows(script: ModuleType, losses: Mapping[object, float]) -> list[dict[str, str]]:
    return [
        {
            "model": "homo_sage",
            "candidate": candidate.name,
            "status": "ok",
            "val_data_loss": str(loss),
        }
        for candidate, loss in losses.items()
    ]


def test_selection_takes_the_lowest_loss_and_breaks_ties_with_the_grid_order(
    script: ModuleType,
) -> None:
    grid = script.candidates()
    chosen = script.select(_rows(script, {grid[0]: 1.0, grid[5]: 0.5, grid[9]: 0.5}), ["homo_sage"])

    entry = chosen["selections"]["homo_sage"]
    assert entry["candidate"] == grid[5].name
    assert entry["baseline_val_data_loss"] == 1.0


def test_selection_ignores_candidates_with_failed_folds(script: ModuleType) -> None:
    grid = script.candidates()
    rows = [*_rows(script, {grid[0]: 1.0}), *_rows(script, {grid[0]: 1.0})]
    rows.append(_rows(script, {grid[5]: 0.1})[0])

    entry = script.select(rows, ["homo_sage"])["selections"]["homo_sage"]

    assert entry["candidate"] == grid[0].name


def test_identical_arms_have_no_p_value(script: ModuleType) -> None:
    assert script._p_value(float("nan")) == "—"
    assert script._p_value(0.1234) == "0.123"


class _Recording(Mapping[str, HeteroData]):
    def __init__(self, graphs: Mapping[str, HeteroData]) -> None:
        self._graphs = graphs
        self.read: set[str] = set()

    def __getitem__(self, key: str) -> HeteroData:
        self.read.add(key)
        return self._graphs[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._graphs)

    def __len__(self) -> int:
        return len(self._graphs)


def test_fitting_a_candidate_never_reads_the_test_of_the_fold(
    script: ModuleType, tmp_path: Path
) -> None:
    plan_path = tmp_path / "plan.json"
    synthetic_cv_plan(n_animals=20, first_seed=1).save(plan_path)
    inputs = load_synthetic_cv_inputs(plan_path)
    recording = _Recording(inputs.graphs)
    probe = CVInputs(
        dataset_id=inputs.dataset_id,
        graphs=recording,
        metadata=inputs.metadata,
        plan=inputs.plan,
        plan_path=plan_path,
        pens=inputs.pens,
        diets=inputs.diets,
        days=inputs.days,
        cohort=inputs.cohort,
    )
    training = load_training_config(REPO_ROOT / "configs" / "training" / "default.json").model_copy(
        update={"max_epochs": 1, "patience": 1, "batch_size": 4}
    )

    result = script.fit_inner(
        probe, "homo_sage", script.Candidate(profile_block=True, linear_head=True), 0, 0, training
    )

    train_ids, test_ids = inputs.plan.folds(0)[0]
    assert result.epochs_run == 1
    assert recording.read <= set(train_ids)
    assert not recording.read & set(test_ids)
