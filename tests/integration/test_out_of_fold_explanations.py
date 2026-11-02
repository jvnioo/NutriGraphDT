"""Explicación fuera de fold (C-05, #241) sobre corridas guardadas de la cohorte sintética.

Entrena 2 semillas × 2 folds de 12 animales sintéticos (pocas épocas: lo que se prueba es la
elección del modelo, no su calidad), guarda cada corrida con `run_compositional_fold` y
comprueba que cada animal se explica solo con el modelo del fold en que estuvo en test, con el
escalado de esa corrida, y que un fold fallido no se reemplaza. Explica con
`EdgeGradientSaliency`: `GNNExplainer` de PyG falla con los tipos de arista vacíos que deja
`align_graph_types` en esta cohorte. Requiere los extras `graph` y `baselines`.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")

from torch_geometric.data import HeteroData  # noqa: E402

from nutrigraphdt.explainability import HeteroExplainer  # noqa: E402
from nutrigraphdt.explainability.contract import Explanation, RunRef  # noqa: E402
from nutrigraphdt.explainability.out_of_fold import (  # noqa: E402
    FoldRun,
    OutOfFoldError,
    explain_out_of_fold,
    index_runs,
    plan_out_of_fold,
)
from nutrigraphdt.models.composition import MODEL_OUTPUT_NAMES  # noqa: E402
from nutrigraphdt.models.gnn import load_model_config  # noqa: E402
from nutrigraphdt.models.gnn.base import GraphMetadata, SCFAGraphModel  # noqa: E402
from nutrigraphdt.models.training import TrainingConfig  # noqa: E402
from nutrigraphdt.models.training.compositional import run_compositional_fold  # noqa: E402
from nutrigraphdt.models.training.compositional_tracking import (  # noqa: E402
    load_compositional_run,
)
from nutrigraphdt.models.training.cv_inputs import synthetic_cohort_graphs  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SEEDS = (0, 1)
PLAN = {"file": "configs/splits/plan.json", "sha256": "a" * 64, "version": "1.0.0", "k": 2}
OUTPUTS = MODEL_OUTPUT_NAMES[:2]
EXPLAINER_SEEDS = range(5)


@pytest.fixture(scope="module")
def graphs() -> dict[str, HeteroData]:
    return synthetic_cohort_graphs(12, first_seed=1)


@pytest.fixture(scope="module")
def runs_dir(graphs: dict[str, HeteroData], tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("runs")
    ids = sorted(graphs)
    metadata = GraphMetadata.from_graphs(list(graphs.values()))
    for seed in SEEDS:
        order = ids[seed:] + ids[:seed]  # otra partición en cada semilla
        halves = (order[:6], order[6:])
        for fold, test_ids in enumerate(halves):
            config = TrainingConfig.model_validate(
                {
                    "lr": 1e-2,
                    "weight_decay": 1e-4,
                    "batch_size": 4,
                    "max_epochs": 2,
                    "patience": 2,
                    "seed": 100 * seed + fold,
                    "dataset_id": "synthetic_cohort",
                    "split_file": "configs/splits/plan.json",
                }
            )
            run_compositional_fold(
                seed=seed,
                fold=fold,
                model_name="hetero_sage",
                edges_arm="with_inferred",
                train_ids=halves[1 - fold],
                test_ids=test_ids,
                graphs=graphs,
                pens={s: f"pen{i}" for i, s in enumerate(ids)},
                diets={s: f"dieta{i % 2}" for i, s in enumerate(ids)},
                days={s: "7" for s in ids},
                model_config=load_model_config(REPO_ROOT / "configs/models/hetero_sage.yaml"),
                metadata=metadata,
                config=config,
                inner_folds=2,
                runs_dir=directory,
                run_context={"dataset_id": "synthetic_cohort", "plan": PLAN},
            )
    return directory


def _recording_explainer(calls: list[dict[str, Any]]) -> Any:
    def explain(
        model: SCFAGraphModel, graph: HeteroData, run: RunRef, output: str, seed: int
    ) -> Explanation:
        calls.append({"run_id": run.run_id, "sample_id": str(graph.sample_id), "graph": graph})
        explainer = HeteroExplainer(
            model, algorithm="edge_saliency", node_mask_type=None, top_k=3, seed=seed
        )
        return explainer.explain(graph, run=run, target=output)

    return explain


def test_animal_is_never_explained_with_a_model_that_trained_on_it(
    graphs: dict[str, HeteroData], runs_dir: Path
) -> None:
    runs = index_runs(runs_dir, variant="hetero_sage")
    assert len(runs) == len(SEEDS) * 2
    plan = plan_out_of_fold(runs, graphs, SEEDS)
    assert plan.explanation_counts() == {s: len(SEEDS) for s in graphs}

    calls: list[dict[str, Any]] = []
    results = explain_out_of_fold(
        plan,
        graphs,
        _recording_explainer(calls),
        outputs=OUTPUTS,
        explainer_seeds=EXPLAINER_SEEDS,
        repo_root=REPO_ROOT,
    )
    by_id = {run.run_id: run for run in runs}
    assert len(calls) == len(graphs) * len(SEEDS) * len(OUTPUTS) * len(EXPLAINER_SEEDS)
    for call in calls:
        run = by_id[call["run_id"]]
        assert call["sample_id"] in run.test
        assert not run.saw(call["sample_id"])
    # Cada animal se explicó con modelos distintos en cada semilla del plan.
    for sample_id in graphs:
        used = {c["run_id"] for c in calls if c["sample_id"] == sample_id}
        assert len(used) == len(SEEDS)

    assert len(results) == len(graphs) * len(OUTPUTS)
    for result in results:
        assert result.count == len(SEEDS) and result.missing_seeds == ()
        assert result.plan_phi is not None and result.plan_ci is not None
        for report in result.by_seed.values():
            assert report.seeds == tuple(EXPLAINER_SEEDS)
            assert all(e.run.run_id in by_id for e in report.explanations)


def test_graph_is_scaled_with_the_fold_scaler(
    graphs: dict[str, HeteroData], runs_dir: Path
) -> None:
    runs = index_runs(runs_dir, variant="hetero_sage")
    plan = plan_out_of_fold(runs, graphs, SEEDS)
    calls: list[dict[str, Any]] = []
    explain_out_of_fold(
        plan,
        graphs,
        _recording_explainer(calls),
        outputs=OUTPUTS[:1],
        explainer_seeds=EXPLAINER_SEEDS,
        repo_root=REPO_ROOT,
    )
    by_id = {run.run_id: run for run in runs}
    call = calls[0]
    loaded = load_compositional_run(by_id[call["run_id"]].run_dir)
    expected = loaded.feature_scaler.transform([graphs[call["sample_id"]]])[0]
    for node_type in expected.node_types:
        assert torch.equal(call["graph"][node_type].x, expected[node_type].x)


def test_failed_fold_is_reported_not_replaced(
    graphs: dict[str, HeteroData], runs_dir: Path, tmp_path: Path
) -> None:
    copy = tmp_path / "runs"
    shutil.copytree(runs_dir, copy)
    failed = next(r for r in index_runs(copy, variant="hetero_sage") if r.seed == 1)
    (failed.run_dir / "checkpoint.pt").unlink()

    runs = index_runs(copy, variant="hetero_sage")
    plan = plan_out_of_fold(runs, graphs, SEEDS)
    counts = plan.explanation_counts()
    for sample_id in graphs:
        if sample_id in failed.test:
            assert counts[sample_id] == 1 and plan.missing[sample_id] == (1,)
        else:
            assert counts[sample_id] == 2 and plan.missing[sample_id] == ()


def _run(run_id: str, seed: int, fold: int, test: set[str], train: set[str]) -> FoldRun:
    return FoldRun(
        run_dir=Path(run_id),
        run_id=run_id,
        variant="hetero_sage",
        edges_arm="with_inferred",
        dataset_id="D1_holofood",
        seed=seed,
        fold=fold,
        train=frozenset(train),
        inner_val=frozenset(),
        test=frozenset(test),
    )


def test_inconsistent_runs_are_rejected() -> None:
    leaked = _run("r0", 0, 0, {"a", "b"}, {"b", "c"})
    with pytest.raises(OutOfFoldError, match="test y en entrenamiento"):
        plan_out_of_fold([leaked], ["a"], [0])

    twice = [_run("r0", 0, 0, {"a"}, {"b"}), _run("r1", 0, 1, {"a"}, {"b"})]
    with pytest.raises(OutOfFoldError, match="varios folds"):
        plan_out_of_fold(twice, ["a"], [0])

    repeated = [_run("r0", 0, 0, {"a"}, {"b"}), _run("r1", 0, 0, {"b"}, {"a"})]
    with pytest.raises(OutOfFoldError, match="más de una corrida"):
        plan_out_of_fold(repeated, ["a", "b"], [0])
