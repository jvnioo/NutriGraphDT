"""Ciclo completo con restricciones sobre una cohorte sintética mínima (A66-P4, #184).

Recorre, sin datos reales ni descargas, lo que hace una corrida de A68 con la configuración
versionada `configs/training/test_constrained_cycle.json` (λ = 0,5 con la cota de D-06):

plan de folds por corral → entrenamiento con pérdida compuesta y val interno → registro de
violaciones → checkpoint y `run.json` por fold → agregación de métricas y violaciones → recarga
→ reanudación.

Cada alteración deliberada de λ, de los folds o del checkpoint debe producir una falla
detectable. Requiere los extras `graph` y `baselines`. Con `NUTRIGRAPHDT_REQUIRE_GRAPH=1`, la
sesión falla en vez de omitir la prueba si falta `graph` (`tests/conftest.py`).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")

from torch_geometric.data import HeteroData  # noqa: E402

from nutrigraphdt.constraints import constraint_catalog  # noqa: E402
from nutrigraphdt.graph.builder import add_reverse_edges  # noqa: E402
from nutrigraphdt.graph.heterodata import build_synthetic_graphs  # noqa: E402
from nutrigraphdt.models.baselines import build_synthetic_cohort  # noqa: E402
from nutrigraphdt.models.cross_validation import (  # noqa: E402
    CrossValidationError,
    CVAnimal,
    PenFoldPlan,
    aggregate_fold_reports,
    make_pen_folds,
    verify_plan,
)
from nutrigraphdt.models.gnn import build_model, load_model_config  # noqa: E402
from nutrigraphdt.models.gnn.base import GraphMetadata  # noqa: E402
from nutrigraphdt.models.gnn.batching import align_graph_types  # noqa: E402
from nutrigraphdt.models.gnn.target import add_graph_target  # noqa: E402
from nutrigraphdt.models.training import load_training_config, set_seed  # noqa: E402
from nutrigraphdt.models.training.compositional import (  # noqa: E402
    CompositionalTargetTransform,
    CompositionalTrainingError,
    CompositionalTrainingState,
    FoldEvaluation,
    aggregate_violation_log,
    load_training_state,
    run_compositional_fold,
    save_training_state,
    split_inner_validation,
    train_compositional_model,
)
from nutrigraphdt.models.training.compositional_tracking import (  # noqa: E402
    RELOAD_ATOL,
    IncompleteRunError,
    load_compositional_run,
    predict_compositional,
)
from nutrigraphdt.models.training.scaling import FeatureScaler  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = REPO_ROOT / "configs" / "training" / "test_constrained_cycle.json"
MODEL_CONFIG = REPO_ROOT / "configs" / "models" / "hetero_sage.yaml"
N_ANIMALS = 20
PLAN_SEEDS = tuple(range(10))
EVALUATED_SEED = 0


@pytest.fixture(scope="module")
def graphs() -> dict[str, HeteroData]:
    built = build_synthetic_graphs(build_synthetic_cohort(N_ANIMALS, first_seed=1))
    prepared: dict[str, HeteroData] = {}
    for graph_id, graph in built.graphs.items():
        with_target = add_graph_target(add_reverse_edges(graph))
        with_target.graph_id = graph_id
        prepared[str(with_target.sample_id)] = with_target
    align_graph_types(list(prepared.values()), inplace=True)
    return prepared


@pytest.fixture(scope="module")
def animals(graphs: dict[str, HeteroData]) -> list[CVAnimal]:
    """Dos dietas con cinco corrales cada una, dos animales por corral (ficticio)."""
    return [
        CVAnimal(sample_id, f"{'AB'[i % 2]}{i // 4}", "AB"[i % 2], "7")
        for i, sample_id in enumerate(sorted(graphs))
    ]


@pytest.fixture(scope="module")
def plan(animals: list[CVAnimal]) -> PenFoldPlan:
    return make_pen_folds(animals, dataset_id="synthetic_cohort", k=2, seeds=PLAN_SEEDS)


def _run_fold(
    graphs: dict[str, HeteroData],
    animals: list[CVAnimal],
    train_ids: tuple[str, ...],
    test_ids: tuple[str, ...],
    fold: int,
    runs_dir: Path,
) -> FoldEvaluation:
    config = load_training_config(CONFIG)
    return run_compositional_fold(
        seed=EVALUATED_SEED,
        fold=fold,
        model_name="hetero_sage",
        edges_arm="with_inferred",
        train_ids=train_ids,
        test_ids=test_ids,
        graphs=graphs,
        pens={a.sample_id: a.pen_code for a in animals},
        diets={a.sample_id: a.diet for a in animals},
        days={a.sample_id: str(a.sampling_day) for a in animals},
        model_config=load_model_config(MODEL_CONFIG),
        metadata=GraphMetadata.from_graphs(list(graphs.values())),
        config=config.model_copy(update={"seed": config.seed + fold}),
        inner_folds=2,
        monitor_constraints=tuple(constraint_catalog().values()),
        runs_dir=runs_dir,
        run_context={
            "dataset_id": "synthetic_cohort",
            "plan": {"file": None, "sha256": "en-memoria", "version": "1.0.0", "k": 2},
            "cohort": {"size": N_ANIMALS},
        },
    )


@pytest.fixture(scope="module")
def cycle(
    graphs: dict[str, HeteroData],
    animals: list[CVAnimal],
    plan: PenFoldPlan,
    tmp_path_factory: pytest.TempPathFactory,
) -> list[FoldEvaluation]:
    verify_plan(plan, animals)
    runs_dir = tmp_path_factory.mktemp("runs")
    return [
        _run_fold(graphs, animals, train, test, fold, runs_dir)
        for fold, (train, test) in enumerate(plan.folds(EVALUATED_SEED))
    ]


def _run_info(evaluation: FoldEvaluation) -> dict[str, Any]:
    assert evaluation.run_dir is not None
    return json.loads((evaluation.run_dir / "run.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Flujo completo
# ---------------------------------------------------------------------------


def test_every_fold_trains_with_the_versioned_constrained_config(
    cycle: list[FoldEvaluation],
) -> None:
    config = load_training_config(CONFIG)
    assert config.constraint_lambda > 0
    assert len(cycle) == 2
    for evaluation in cycle:
        assert evaluation.history
        assert {record.constraint_lambda for record in evaluation.history} == {
            config.constraint_lambda
        }
        info = _run_info(evaluation)
        assert info["constraint_lambda"] == config.constraint_lambda
        assert info["constraint_terms"] == list(config.constraint_terms)
        for record in evaluation.history:
            assert record.train_total_loss == pytest.approx(
                record.train_data_loss + config.constraint_lambda * record.train_bio_loss
            )


def test_folds_never_share_animals_or_pens(
    cycle: list[FoldEvaluation], animals: list[CVAnimal]
) -> None:
    pens = {a.sample_id: a.pen_code for a in animals}
    tests = [set(_run_info(e)["sample_ids"]["test"]) for e in cycle]
    assert not tests[0] & tests[1]
    assert tests[0] | tests[1] == set(pens)
    for evaluation in cycle:
        ids = _run_info(evaluation)["sample_ids"]
        groups = {name: {pens[s] for s in ids[name]} for name in ("train", "inner_val", "test")}
        assert not groups["train"] & groups["test"]
        assert not groups["inner_val"] & groups["test"]
        assert not groups["train"] & groups["inner_val"]


def test_violations_are_logged_per_epoch_subset_and_aggregated(
    cycle: list[FoldEvaluation],
) -> None:
    monitored = set(constraint_catalog())
    for evaluation in cycle:
        subsets = {row.subset for row in evaluation.violations}
        assert subsets == {"train", "val", "test"}
        train_rows = [row for row in evaluation.violations if row.subset == "train"]
        assert len(train_rows) == evaluation.epochs_run * len(monitored)
        assert evaluation.run_dir is not None
        with (evaluation.run_dir / "violations.csv").open(encoding="utf-8") as handle:
            assert len(list(csv.DictReader(handle))) == len(evaluation.violations)
    aggregates = aggregate_violation_log([(e.seed, row) for e in cycle for row in e.violations])
    assert {row.constraint for row in aggregates} == monitored
    assert {row.n for row in aggregates} == {2}


def test_metrics_aggregate_over_folds(cycle: list[FoldEvaluation]) -> None:
    aggregate = aggregate_fold_reports({(e.seed, e.fold): e.report for e in cycle})
    metrics = {row.metric for row in aggregate.rows}
    assert {"fraction_mae_pp_mean", "fraction_mae_pp_n", "log_total_r2_mean"} <= metrics
    (n_row,) = [
        r for r in aggregate.rows if r.metric == "fraction_mae_pp_n" and r.group in (None, "all")
    ]
    assert n_row.average == 2.0


def test_reloaded_checkpoints_reproduce_the_test_predictions(
    cycle: list[FoldEvaluation], graphs: dict[str, HeteroData]
) -> None:
    for evaluation in cycle:
        assert evaluation.run_dir is not None
        loaded = load_compositional_run(evaluation.run_dir)
        expected = {p["sample_id"]: p for p in evaluation.predictions}
        ids, output = predict_compositional(loaded, [graphs[s] for s in sorted(expected)])
        for row, sample_id in enumerate(ids):
            for column, name in enumerate(("z1", "z2", "log_total")):
                assert abs(float(output[row, column]) - expected[sample_id][name]) <= RELOAD_ATOL


def test_second_execution_continues_from_the_saved_state(
    graphs: dict[str, HeteroData], animals: list[CVAnimal], plan: PenFoldPlan, tmp_path: Path
) -> None:
    inputs = _fold_inputs(graphs, animals, plan)
    config = load_training_config(CONFIG)
    states: list[CompositionalTrainingState] = []
    set_seed(config.seed)
    train, val, transform = inputs
    first = train_compositional_model(
        _fresh_model(graphs), train, val, config, transform, on_epoch_end=states.append
    )
    saved = save_training_state(states[1], tmp_path / "state.pt")

    second = train_compositional_model(
        _fresh_model(graphs), train, val, config, transform, resume_from=load_training_state(saved)
    )

    assert [r.to_dict() for r in second.history] == [r.to_dict() for r in first.history]
    for name, value in first.model.state_dict().items():
        assert torch.equal(second.model.state_dict()[name], value), name


# ---------------------------------------------------------------------------
# Alteraciones deliberadas
# ---------------------------------------------------------------------------


def test_altered_lambda_is_detected_when_resuming(
    graphs: dict[str, HeteroData], animals: list[CVAnimal], plan: PenFoldPlan
) -> None:
    train, val, transform = _fold_inputs(graphs, animals, plan)
    config = load_training_config(CONFIG)
    states: list[CompositionalTrainingState] = []
    set_seed(config.seed)
    train_compositional_model(
        _fresh_model(graphs),
        train,
        val,
        config.model_copy(update={"max_epochs": 1}),
        transform,
        on_epoch_end=states.append,
    )
    altered = config.model_copy(update={"constraint_lambda": 2 * config.constraint_lambda})
    with pytest.raises(CompositionalTrainingError, match="otra configuración"):
        train_compositional_model(
            _fresh_model(graphs), train, val, altered, transform, resume_from=states[0]
        )


def test_altered_folds_are_rejected(
    graphs: dict[str, HeteroData], animals: list[CVAnimal], plan: PenFoldPlan, tmp_path: Path
) -> None:
    by_pen: dict[str, list[str]] = {}
    for animal in animals:
        by_pen.setdefault(animal.pen_code, []).append(animal.sample_id)
    first, second = next(ids for ids in by_pen.values() if len(ids) == 2)
    assignment = dict(plan.assignments[EVALUATED_SEED])
    assignment[first] = 1 - assignment[second]  # un corral repartido entre los dos folds
    leaky = PenFoldPlan(plan.dataset_id, plan.k, (EVALUATED_SEED,), {EVALUATED_SEED: assignment})

    with pytest.raises(CrossValidationError, match="corral"):
        verify_plan(leaky, animals)
    train, test = leaky.folds(EVALUATED_SEED)[0]
    with pytest.raises(CompositionalTrainingError, match="Fuga entre train y test"):
        _run_fold(graphs, animals, train, test, 0, tmp_path)


def test_altered_checkpoint_is_detected(
    cycle: list[FoldEvaluation], graphs: dict[str, HeteroData], tmp_path: Path
) -> None:
    evaluation = cycle[0]
    assert evaluation.run_dir is not None
    copy = tmp_path / "run"
    copy.mkdir()
    for path in evaluation.run_dir.iterdir():
        (copy / path.name).write_bytes(path.read_bytes())
    state = torch.load(copy / "checkpoint.pt", weights_only=True)
    # Sesgo de la última capa de la cabeza: cualquier cambio llega a las tres salidas.
    head_bias = [name for name in state if name.startswith("head.") and name.endswith("bias")][-1]
    state[head_bias] = state[head_bias] + 1.0
    torch.save(state, copy / "checkpoint.pt")

    loaded = load_compositional_run(copy)
    expected = {p["sample_id"]: p for p in evaluation.predictions}
    ids, output = predict_compositional(loaded, [graphs[s] for s in sorted(expected)])
    deviation = max(
        abs(float(output[row, column]) - expected[sample_id][name])
        for row, sample_id in enumerate(ids)
        for column, name in enumerate(("z1", "z2", "log_total"))
    )
    assert deviation > RELOAD_ATOL

    (copy / "checkpoint.pt").unlink()
    with pytest.raises(FileNotFoundError):
        load_compositional_run(copy)
    info = json.loads((copy / "run.json").read_text(encoding="utf-8"))
    del info["scaling"]
    (copy / "run.json").write_text(json.dumps(info), encoding="utf-8")
    with pytest.raises(IncompleteRunError, match="scaling"):
        load_compositional_run(copy)


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _fold_inputs(
    graphs: dict[str, HeteroData], animals: list[CVAnimal], plan: PenFoldPlan
) -> tuple[list[HeteroData], list[HeteroData], CompositionalTargetTransform]:
    train_ids, _ = plan.folds(EVALUATED_SEED)[0]
    inner_train, inner_val = split_inner_validation(
        train_ids,
        {a.sample_id: a.pen_code for a in animals},
        {a.sample_id: a.diet for a in animals},
        seed=0,
        inner_folds=2,
    )
    train = [graphs[s] for s in inner_train]
    val = [graphs[s] for s in inner_val]
    scaler = FeatureScaler.fit(train)
    return scaler.transform(train), scaler.transform(val), CompositionalTargetTransform.fit(train)


def _fresh_model(graphs: dict[str, HeteroData]) -> Any:
    from nutrigraphdt.models.composition import MODEL_OUTPUT_NAMES

    return build_model(
        load_model_config(MODEL_CONFIG),
        GraphMetadata.from_graphs(list(graphs.values())),
        target_names=MODEL_OUTPUT_NAMES,
    )
