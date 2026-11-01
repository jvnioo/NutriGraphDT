"""Trazabilidad de las corridas composicionales por fold (A68-P3, #180).

Usa la cohorte sintética de `build_synthetic_cohort` (no hay datos reales): entrena un fold,
guarda la corrida, la recarga y comprueba que reproduce las predicciones dentro de la
tolerancia documentada. Requiere los extras `graph` y `baselines`.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")

from torch_geometric.data import HeteroData  # noqa: E402

from nutrigraphdt.constraints import D06_PROPIONATE_BOUND_NAME, constraint_catalog  # noqa: E402
from nutrigraphdt.graph.builder import add_reverse_edges  # noqa: E402
from nutrigraphdt.graph.heterodata import build_synthetic_graphs  # noqa: E402
from nutrigraphdt.models.baselines import build_synthetic_cohort  # noqa: E402
from nutrigraphdt.models.composition import MODEL_OUTPUT_NAMES  # noqa: E402
from nutrigraphdt.models.gnn import load_model_config  # noqa: E402
from nutrigraphdt.models.gnn.base import GraphMetadata  # noqa: E402
from nutrigraphdt.models.gnn.batching import align_graph_types  # noqa: E402
from nutrigraphdt.models.gnn.target import add_graph_target  # noqa: E402
from nutrigraphdt.models.training import TrainingConfig  # noqa: E402
from nutrigraphdt.models.training.compositional import (  # noqa: E402
    FoldEvaluation,
    run_compositional_fold,
)
from nutrigraphdt.models.training.compositional_tracking import (  # noqa: E402
    RELOAD_ATOL,
    REQUIRED_RUN_FIELDS,
    IncompleteRunError,
    graph_metadata_matches,
    load_compositional_run,
    plan_content_sha256,
    predict_compositional,
    run_metadata_problems,
)

PLAN = {"file": "configs/splits/plan.json", "sha256": "abc", "version": "1.0.0", "k": 2}


@pytest.fixture(scope="module")
def graphs() -> dict[str, HeteroData]:
    built = build_synthetic_graphs(build_synthetic_cohort(16, first_seed=1))
    prepared: dict[str, HeteroData] = {}
    for graph_id, graph in built.graphs.items():
        with_target = add_graph_target(add_reverse_edges(graph))
        with_target.graph_id = graph_id
        prepared[str(with_target.sample_id)] = with_target
    align_graph_types(list(prepared.values()), inplace=True)
    return prepared


@pytest.fixture(scope="module")
def saved(
    graphs: dict[str, HeteroData], tmp_path_factory: pytest.TempPathFactory
) -> FoldEvaluation:
    ids = sorted(graphs)
    config = TrainingConfig.model_validate(
        {
            "lr": 1e-2,
            "weight_decay": 1e-4,
            "batch_size": 4,
            "max_epochs": 3,
            "patience": 2,
            "seed": 7,
            "dataset_id": "synthetic_cohort",
            "split_file": "configs/splits/d1_holofood.json",
            "constraint_lambda": 0.5,
            "constraint_terms": [D06_PROPIONATE_BOUND_NAME],
        }
    )
    return run_compositional_fold(
        seed=1,
        fold=0,
        model_name="hetero_sage",
        edges_arm="with_inferred",
        train_ids=ids[:12],
        test_ids=ids[12:],
        graphs=graphs,
        pens={s: f"pen{i // 2}" for i, s in enumerate(ids)},
        diets={s: f"dieta{i % 2}" for i, s in enumerate(ids)},
        days={s: "7" for s in ids},
        model_config=load_model_config("configs/models/hetero_sage.yaml"),
        metadata=GraphMetadata.from_graphs(list(graphs.values())),
        config=config,
        inner_folds=3,
        monitor_constraints=(constraint_catalog()[D06_PROPIONATE_BOUND_NAME],),
        runs_dir=tmp_path_factory.mktemp("runs"),
        run_context={"dataset_id": "synthetic_cohort", "plan": PLAN, "cohort": {"size": 16}},
    )


def _info(evaluation: FoldEvaluation) -> dict:
    assert evaluation.run_dir is not None
    return json.loads((evaluation.run_dir / "run.json").read_text(encoding="utf-8"))


def test_run_records_configuration_provenance_seed_fold_and_lambda(
    saved: FoldEvaluation,
) -> None:
    info = _info(saved)
    assert run_metadata_problems(info) == []
    assert set(REQUIRED_RUN_FIELDS) <= set(info)
    assert (info["variant"], info["edges_arm"], info["seed"], info["fold"]) == (
        "hetero_sage",
        "with_inferred",
        1,
        0,
    )
    assert info["train_seed"] == 7
    assert info["constraint_lambda"] == 0.5
    assert info["constraint_terms"] == [D06_PROPIONATE_BOUND_NAME]
    assert info["monitored_constraints"] == [D06_PROPIONATE_BOUND_NAME]
    assert info["target_names"] == list(MODEL_OUTPUT_NAMES)
    assert info["plan"]["sha256"] == "abc"
    assert info["best_epoch"] == saved.best_epoch
    assert sorted(info["sample_ids"]["test"]) == sorted(p["sample_id"] for p in saved.predictions)
    assert not set(info["sample_ids"]["test"]) & set(info["sample_ids"]["train"])
    assert saved.run_id is not None and saved.run_id.endswith("_hetero_sage_with_inferred_s1_f0")
    files = info["files"]
    assert all((saved.run_dir / name).exists() for name in files.values() if name)  # type: ignore[operator]


def test_reload_reproduces_the_saved_predictions(
    saved: FoldEvaluation, graphs: dict[str, HeteroData]
) -> None:
    assert saved.run_dir is not None
    loaded = load_compositional_run(saved.run_dir)
    assert loaded.model.target_names == MODEL_OUTPUT_NAMES
    test_ids = [p["sample_id"] for p in saved.predictions]
    assert graph_metadata_matches(loaded, GraphMetadata.from_graphs(list(graphs.values())))

    sample_ids, output = predict_compositional(loaded, [graphs[s] for s in test_ids])

    with (saved.run_dir / "predictions.csv").open(encoding="utf-8") as handle:
        stored = {row["sample_id"]: row for row in csv.DictReader(handle)}
    for row, sample_id in enumerate(sample_ids):
        for column, name in enumerate(("z1", "z2", "log_total")):
            assert abs(float(output[row, column]) - float(stored[sample_id][name])) <= RELOAD_ATOL


@pytest.mark.parametrize("field", ["plan", "train_seed", "constraint_lambda", "scaling"])
def test_incomplete_metadata_is_detected_before_reloading(
    saved: FoldEvaluation, tmp_path: Path, field: str
) -> None:
    assert saved.run_dir is not None
    info = _info(saved)
    del info[field]
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "run.json").write_text(json.dumps(info), encoding="utf-8")
    (broken / "checkpoint.pt").write_bytes((saved.run_dir / "checkpoint.pt").read_bytes())

    assert f"falta '{field}'" in run_metadata_problems(info)
    with pytest.raises(IncompleteRunError, match=field):
        load_compositional_run(broken)


def test_concentration_output_names_and_missing_plan_hash_are_reported(
    saved: FoldEvaluation,
) -> None:
    info = _info(saved)
    info["target_names"] = ["acetate", "propionate", "butyrate"]
    info["plan"] = {**info["plan"], "sha256": None}
    problems = run_metadata_problems(info)
    assert any("target_names" in p for p in problems)
    assert "falta 'plan.sha256'" in problems


def test_plan_hash_ignores_key_order_and_line_endings(tmp_path: Path) -> None:
    plan = {"k": 2, "seeds": [0], "assignments": {"0": {"A": 0, "B": 1}}}
    lf = tmp_path / "lf.json"
    crlf = tmp_path / "crlf.json"
    lf.write_text(json.dumps(plan, indent=2), encoding="utf-8", newline="\n")
    reordered = {"assignments": plan["assignments"], "seeds": [0], "k": 2}
    crlf.write_text(json.dumps(reordered, indent=2), encoding="utf-8", newline="\r\n")
    digests = {
        plan_content_sha256(json.loads(path.read_text(encoding="utf-8"))) for path in (lf, crlf)
    }
    assert len(digests) == 1
