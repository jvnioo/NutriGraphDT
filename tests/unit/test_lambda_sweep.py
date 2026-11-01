"""Barrido acotado de λ con selección solo por validación interna (A68-P1, #178).

Usa la cohorte sintética (sin datos reales). Comprueba la configuración versionada, el
presupuesto, que ningún animal de test de un fold entre en su entrenamiento ni en su selección,
el criterio de elección y el script de punta a punta. Requiere los extras `graph` y `baselines`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")

from torch_geometric.data import HeteroData  # noqa: E402

from nutrigraphdt.models.cross_validation import PenFoldPlan  # noqa: E402
from nutrigraphdt.models.gnn import load_model_config  # noqa: E402
from nutrigraphdt.models.training import load_training_config  # noqa: E402
from nutrigraphdt.models.training.cv_inputs import (  # noqa: E402
    CVInputs,
    load_synthetic_cv_inputs,
    synthetic_cv_plan,
)
from nutrigraphdt.models.training.lambda_sweep import (  # noqa: E402
    LambdaSweepConfig,
    LambdaSweepConfigError,
    SweepRow,
    load_lambda_sweep_config,
    run_lambda_sweep,
    select_lambdas,
    trainings_needed,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SWEEP_CONFIGS = REPO_ROOT / "configs" / "constraints"
D06 = "d06.hydrogen.propionate_bound"


def _config(**overrides: Any) -> LambdaSweepConfig:
    values: dict[str, Any] = {
        "version": "test",
        "dataset_id": "synthetic_cohort",
        "grid": [0.0, 1.0],
        "constraint_terms": [D06],
        "feasibility_constraint": D06,
        "selection_seeds": [0],
        "variants": ["homo_sage"],
        "inner_folds": 2,
        "max_epochs": 2,
        "patience": 5,
        "train_seed_base": 1000,
        "max_trainings": 10,
        "criterion": "val_data_loss_mean",
        "tie_break": "smallest_lambda",
    }
    values.update(overrides)
    return LambdaSweepConfig.model_validate(values)


@pytest.fixture(scope="module")
def small_inputs(tmp_path_factory: pytest.TempPathFactory) -> CVInputs:
    plan_path = tmp_path_factory.mktemp("plan") / "plan.json"
    synthetic_cv_plan(n_animals=20, first_seed=1).save(plan_path)
    return load_synthetic_cv_inputs(plan_path)


class _RecordingGraphs(Mapping[str, HeteroData]):
    """Mapping que registra qué animales se leen."""

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


# ---------------------------------------------------------------------------
# Configuración y presupuesto
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dataset", ["d1", "synthetic"])
def test_versioned_configs_fit_their_budget(dataset: str) -> None:
    config = load_lambda_sweep_config(SWEEP_CONFIGS / f"lambda_sweep_{dataset}.json")
    plan_name = "d1_holofood_cv.json" if dataset == "d1" else "synthetic_cohort_cv.json"
    plan = PenFoldPlan.load(REPO_ROOT / "configs" / "splits" / plan_name)
    assert config.grid[0] == 0.0
    assert set(config.selection_seeds) <= set(plan.seeds)
    assert trainings_needed(config, plan) <= config.max_trainings
    assert config.dataset_id == plan.dataset_id


def test_versioned_synthetic_plan_is_reproducible() -> None:
    stored = PenFoldPlan.load(REPO_ROOT / "configs" / "splits" / "synthetic_cohort_cv.json")
    assert stored.to_dict() == synthetic_cv_plan().to_dict()


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"grid": [0.1, 1.0]}, "λ = 0"),
        ({"grid": [0.0, 1.0, 0.5]}, "ordenada"),
        ({"grid": [0.0, -1.0]}, "no negativos"),
        ({"constraint_terms": ["inexistente"]}, "desconocidas"),
        ({"variants": ["mlp"]}, "variantes desconocidas"),
    ],
)
def test_invalid_configs_are_rejected(override: dict[str, Any], fragment: str) -> None:
    with pytest.raises(ValueError, match=fragment):
        _config(**override)


def test_budget_is_checked_before_training(
    small_inputs: CVInputs, monkeypatch: pytest.MonkeyPatch
) -> None:
    import nutrigraphdt.models.training.lambda_sweep as sweep

    def unexpected(*args: object, **kwargs: object) -> None:
        raise AssertionError("No debe entrenar si el barrido supera el presupuesto.")

    monkeypatch.setattr(sweep, "train_compositional_model", unexpected)
    with pytest.raises(LambdaSweepConfigError, match="presupuesto"):
        run_lambda_sweep(
            config=_config(max_trainings=3),
            plan=small_inputs.plan,
            graphs=small_inputs.graphs,
            pens=small_inputs.pens,
            diets=small_inputs.diets,
            model_configs={"homo_sage": load_model_config("configs/models/homo_sage.yaml")},
            metadata=small_inputs.metadata,
            base_training=load_training_config("configs/training/test_constrained_cycle.json"),
        )


# ---------------------------------------------------------------------------
# Auditoría: el test de cada fold no interviene
# ---------------------------------------------------------------------------


def test_sweep_never_reads_the_test_of_a_fold(small_inputs: CVInputs) -> None:
    graphs = _RecordingGraphs(small_inputs.graphs)
    config = _config()
    read_by_row: list[tuple[SweepRow, set[str]]] = []

    def record(row: SweepRow) -> None:
        read_by_row.append((row, set(graphs.read)))
        graphs.read.clear()

    rows = run_lambda_sweep(
        config=config,
        plan=small_inputs.plan,
        graphs=graphs,
        pens=small_inputs.pens,
        diets=small_inputs.diets,
        model_configs={"homo_sage": load_model_config("configs/models/homo_sage.yaml")},
        metadata=small_inputs.metadata,
        base_training=load_training_config("configs/training/test_constrained_cycle.json"),
        on_row=record,
    )

    assert len(rows) == trainings_needed(config, small_inputs.plan)
    assert {row.status for row in rows} == {"ok"}
    for row, read in read_by_row:
        train, test = small_inputs.plan.folds(row.seed)[row.fold]
        assert read, "el fold debe leer su train"
        assert read <= set(train)
        assert not read & set(test)
        assert row.n_train + row.n_inner_val == len(train)
        assert row.feasibility_violation_rate_percent is not None


# ---------------------------------------------------------------------------
# Criterio de elección
# ---------------------------------------------------------------------------


def _row(variant: str, lam: float, fold: int, loss: float | None, vr: float = 0.0) -> SweepRow:
    return SweepRow(
        variant=variant,
        constraint_lambda=lam,
        seed=0,
        fold=fold,
        train_seed=fold,
        status="ok" if loss is not None else "error",
        best_epoch=1 if loss is not None else None,
        epochs_run=1 if loss is not None else None,
        val_data_loss=loss,
        val_bio_loss=0.0 if loss is not None else None,
        val_total_loss=loss,
        feasibility_violation_rate_percent=vr if loss is not None else None,
        n_train=4,
        n_inner_val=2,
        duration_seconds=0.1 if loss is not None else None,
        error="" if loss is not None else "falló",
    )


def test_selection_filters_infeasible_then_minimizes_then_breaks_ties() -> None:
    config = _config(grid=[0.0, 1.0, 10.0, 100.0], variants=["homo_sage", "hetero_sage"])
    rows = [
        # homo_sage: λ = 0 viola en un fold; λ = 1 y 10 empatan exactamente; λ = 100 falla.
        _row("homo_sage", 0.0, 0, 0.5, vr=10.0),
        _row("homo_sage", 0.0, 1, 0.5),
        _row("homo_sage", 1.0, 0, 0.8),
        _row("homo_sage", 1.0, 1, 0.6),
        _row("homo_sage", 10.0, 0, 0.6),
        _row("homo_sage", 10.0, 1, 0.8),
        _row("homo_sage", 100.0, 0, 0.1),
        _row("homo_sage", 100.0, 1, None),
        # hetero_sage: todas factibles y todas iguales (la penalización no actuó).
        *(_row("hetero_sage", lam, fold, 0.7) for lam in config.grid for fold in (0, 1)),
    ]
    selections = select_lambdas(rows, config)

    homo = selections["homo_sage"]
    assert homo.selected_lambda == 1.0
    assert "empate exacto" in homo.reason
    by_lambda = {c.constraint_lambda: c for c in homo.candidates}
    assert not by_lambda[0.0].feasible
    assert not by_lambda[100.0].complete
    # Todas empatan: se elige la menor λ > 0; λ = 0 es el brazo libre y no es candidata.
    assert selections["hetero_sage"].selected_lambda == 1.0
    assert 0.0 in {c.constraint_lambda for c in selections["hetero_sage"].candidates}


def test_selection_falls_back_to_all_when_nothing_is_feasible() -> None:
    config = _config(grid=[0.0, 1.0])
    rows = [_row("homo_sage", 0.0, 0, 0.4, vr=5.0), _row("homo_sage", 1.0, 0, 0.3, vr=1.0)]
    selection = select_lambdas(rows, config)["homo_sage"]
    assert selection.selected_lambda == 1.0
    assert not selection.any_feasible
    assert "ninguna factible" in selection.reason


def test_selection_fails_when_no_lambda_completed() -> None:
    with pytest.raises(LambdaSweepConfigError, match="todos los folds"):
        select_lambdas([_row("homo_sage", 0.0, 0, 0.1), _row("homo_sage", 1.0, 0, None)], _config())


# ---------------------------------------------------------------------------
# Script de punta a punta
# ---------------------------------------------------------------------------


def test_script_writes_sweep_selection_and_report(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    synthetic_cv_plan(n_animals=20, first_seed=1).save(plan_path)
    config_path = tmp_path / "sweep.json"
    config_path.write_text(json.dumps(_config().model_dump(mode="json")), encoding="utf-8")
    output = tmp_path / "out"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "sweep_constraint_lambda.py"),
            "--dataset",
            "synthetic",
            "--config",
            str(config_path),
            "--plan",
            str(plan_path),
            "--training-config",
            str(REPO_ROOT / "configs" / "training" / "test_constrained_cycle.json"),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        cwd=REPO_ROOT,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    sweep_lines = (output / "sweep.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(sweep_lines) == 1 + 2 * 5  # cabecera + 2 λ × 5 folds de una semilla
    selection = json.loads((output / "selection.json").read_text(encoding="utf-8"))
    assert selection["test_used"] is False
    assert selection["selections"]["homo_sage"]["selected_lambda"] == 1.0
    run_meta = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert run_meta["trainings"] == 10
    assert run_meta["test_used"] is False
    report = (output / "report.md").read_text(encoding="utf-8")
    assert "El test de los folds no se lee" in report
    assert "Cohorte sintética" in report

    # Volver a elegir desde `sweep.csv` no reentrena y da la misma elección.
    again = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "sweep_constraint_lambda.py"),
            "--dataset",
            "synthetic",
            "--config",
            str(config_path),
            "--plan",
            str(plan_path),
            "--output",
            str(output),
            "--from-sweep",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        cwd=REPO_ROOT,
        check=False,
    )
    assert again.returncode == 0, again.stderr
    reselected = json.loads((output / "selection.json").read_text(encoding="utf-8"))
    assert reselected["selections"] == selection["selections"]
    assert json.loads((output / "run.json").read_text(encoding="utf-8"))["reselected"] is True
