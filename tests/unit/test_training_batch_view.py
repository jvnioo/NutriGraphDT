"""Quitar la trazabilidad de los lotes acelera el entrenamiento sin cambiar resultados (#266)."""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")

from torch_geometric.data import HeteroData  # noqa: E402

from nutrigraphdt.constraints import D06_PROPIONATE_BOUND_NAME, constraint_catalog  # noqa: E402
from nutrigraphdt.graph.builder import add_reverse_edges  # noqa: E402
from nutrigraphdt.graph.heterodata import build_synthetic_graphs  # noqa: E402
from nutrigraphdt.models.baselines import build_synthetic_cohort  # noqa: E402
from nutrigraphdt.models.gnn import load_model_config  # noqa: E402
from nutrigraphdt.models.gnn.base import GraphMetadata  # noqa: E402
from nutrigraphdt.models.gnn.batching import align_graph_types, for_training  # noqa: E402
from nutrigraphdt.models.gnn.target import add_graph_target  # noqa: E402
from nutrigraphdt.models.training import TrainingConfig, compositional  # noqa: E402


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


def test_view_drops_provenance_and_keeps_what_the_model_reads(
    graphs: dict[str, HeteroData],
) -> None:
    graph = next(iter(graphs.values()))
    view = for_training(graph)

    assert "raw_attributes" not in view["taxon"]
    assert "node_id" not in view["taxon"]
    edge_type = ("taxon", "has_capacity", "function")
    assert "evidence_status" not in view[edge_type]
    assert torch.equal(view["taxon"].x, graph["taxon"].x)
    assert torch.equal(view["taxon"].missing_mask, graph["taxon"].missing_mask)
    assert torch.equal(view[edge_type].edge_index, graph[edge_type].edge_index)
    assert torch.equal(view.y_graph, graph.y_graph)
    assert view.sample_id == graph.sample_id


def test_view_does_not_modify_the_graph_and_can_be_applied_twice(
    graphs: dict[str, HeteroData],
) -> None:
    graph = next(iter(graphs.values()))
    view = for_training(for_training(graph))

    assert "raw_attributes" in graph["taxon"]
    assert "evidence_status" in graph["taxon", "has_capacity", "function"]
    assert "raw_attributes" not in view["taxon"]


def _fold(graphs: dict[str, HeteroData]) -> compositional.FoldEvaluation:
    ids = sorted(graphs)
    return compositional.run_compositional_fold(
        seed=1,
        fold=0,
        model_name="hetero_sage",
        edges_arm="x",
        train_ids=ids[:12],
        test_ids=ids[12:],
        graphs=graphs,
        pens={s: f"pen{i // 2}" for i, s in enumerate(ids)},
        diets={s: f"dieta{i % 2}" for i, s in enumerate(ids)},
        days={s: "7" for s in ids},
        model_config=load_model_config("configs/models/hetero_sage.yaml"),
        metadata=GraphMetadata.from_graphs(list(graphs.values())),
        config=TrainingConfig.model_validate(
            {
                "lr": 1e-2,
                "weight_decay": 1e-4,
                "batch_size": 4,
                "max_epochs": 4,
                "patience": 4,
                "seed": 7,
                "dataset_id": "synthetic_cohort",
                "split_file": "configs/splits/d1_holofood.json",
                "constraint_lambda": 0.5,
                "constraint_terms": [D06_PROPIONATE_BOUND_NAME],
            }
        ),
        inner_folds=3,
        monitor_constraints=(constraint_catalog()[D06_PROPIONATE_BOUND_NAME],),
    )


def test_results_are_identical_with_and_without_the_provenance(
    graphs: dict[str, HeteroData], monkeypatch: pytest.MonkeyPatch
) -> None:
    fast = _fold(graphs)
    monkeypatch.setattr(compositional, "for_training", lambda graph: graph)
    full = _fold(graphs)

    assert fast.predictions == full.predictions
    assert fast.best_epoch == full.best_epoch
    assert fast.violations == full.violations
    for first, second in zip(fast.history, full.history, strict=True):
        assert first.val_data_loss == second.val_data_loss
        assert first.train_data_loss == second.train_data_loss
