"""Tests del entrenamiento GNN con objetivo composicional bajo CV por corral (#142).

Requiere el extra `graph` (y `baselines` para el reparto interno por corral).
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")

from torch_geometric.data import HeteroData  # noqa: E402

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
    CompositionalTargetTransform,
    CompositionalTrainingError,
    drop_inferred_edges,
    run_compositional_fold,
    split_inner_validation,
    train_compositional_model,
)

N_SAMPLES = 16
SEED = 42


def _config(**overrides: object) -> TrainingConfig:
    values: dict[str, object] = {
        "lr": 1e-2,
        "weight_decay": 1e-4,
        "batch_size": 4,
        "max_epochs": 3,
        "patience": 2,
        "seed": SEED,
        "dataset_id": "synthetic_cohort",
        "split_file": "configs/splits/d1_holofood.json",
    }
    values.update(overrides)
    return TrainingConfig.model_validate(values)


@pytest.fixture(scope="module")
def graphs() -> dict[str, HeteroData]:
    """Grafos sintéticos preparados como los entrega la preparación del script de #142."""
    cohort = build_synthetic_cohort(N_SAMPLES, first_seed=1)
    built = build_synthetic_graphs(cohort)
    prepared: dict[str, HeteroData] = {}
    for graph_id, graph in built.graphs.items():
        with_target = add_graph_target(add_reverse_edges(graph))
        with_target.graph_id = graph_id
        prepared[str(with_target.sample_id)] = with_target
    align_graph_types(list(prepared.values()), inplace=True)
    return prepared


@pytest.fixture(scope="module")
def context(graphs: dict[str, HeteroData]) -> dict[str, dict[str, str]]:
    ids = sorted(graphs)
    return {
        "pens": {s: f"pen{index // 2}" for index, s in enumerate(ids)},
        "diets": {s: f"dieta{index % 2}" for index, s in enumerate(ids)},
        "days": {s: "7" for s in ids},
    }


def test_transform_roundtrip(graphs: dict[str, HeteroData]) -> None:
    from nutrigraphdt.models.gnn.target import compositional_graph_target

    transform = CompositionalTargetTransform.fit(list(graphs.values()))
    assert transform.scaler.targets == MODEL_OUTPUT_NAMES
    graph = next(iter(graphs.values()))
    scaled = transform.transform(graph.y_graph, graph.y_graph_mask)
    assert scaled.shape == graph.y_graph.shape
    expected, _ = compositional_graph_target(graph.y_graph, graph.y_graph_mask)
    restored = transform.inverse_transform(scaled)
    assert torch.allclose(restored, expected, atol=1e-5)


def test_transform_enmascara_animales_invalidos(graphs: dict[str, HeteroData]) -> None:
    transform = CompositionalTargetTransform.fit(list(graphs.values()))
    graph = next(iter(graphs.values())).clone()
    graph.y_graph_mask = torch.zeros_like(graph.y_graph_mask)
    assert not bool(transform.validity(graph.y_graph, graph.y_graph_mask).any())
    scaled = transform.transform(graph.y_graph, graph.y_graph_mask)
    assert bool((scaled == 0).all())


def test_transform_sin_train_valido(graphs: dict[str, HeteroData]) -> None:
    graph = next(iter(graphs.values())).clone()
    graph.y_graph_mask = torch.zeros_like(graph.y_graph_mask)
    with pytest.raises(CompositionalTrainingError, match="objetivo composicional válido"):
        CompositionalTargetTransform.fit([graph])


def test_split_inner_validation_agrupa_por_corral(
    graphs: dict[str, HeteroData], context: dict[str, dict[str, str]]
) -> None:
    ids = sorted(graphs)
    train, val = split_inner_validation(ids, context["pens"], context["diets"], seed=1)
    assert set(train).isdisjoint(val)
    assert sorted((*train, *val)) == ids
    assert set(context["pens"][s] for s in train).isdisjoint(context["pens"][s] for s in val)
    again = split_inner_validation(ids, context["pens"], context["diets"], seed=1)
    assert again == (train, val)


def test_split_inner_validation_exige_corrales(
    graphs: dict[str, HeteroData], context: dict[str, dict[str, str]]
) -> None:
    ids = sorted(graphs)[:4]
    with pytest.raises(CompositionalTrainingError, match="corrales"):
        split_inner_validation(ids, context["pens"], context["diets"], seed=1, inner_folds=5)
    with pytest.raises(CompositionalTrainingError, match="sin corral o dieta"):
        split_inner_validation(ids, {}, context["diets"], seed=1)


def test_drop_inferred_edges() -> None:
    data = HeteroData()
    data["a"].x = torch.zeros((2, 1))
    data["b"].x = torch.zeros((2, 1))
    store = data[("a", "rel", "b")]
    store.edge_index = torch.tensor([[0, 1, 0], [1, 0, 1]])
    store.evidence_status = ["observed", "inferred", "inferred"]
    store.evidence_id = ["e1", "e2", "e3"]
    store.evidence_method = ["measurement", "model_prediction", "model_prediction"]
    filtered = drop_inferred_edges(data)
    kept = filtered[("a", "rel", "b")]
    assert kept.edge_index.shape == (2, 1)
    assert kept.evidence_status == ["observed"]
    assert kept.evidence_id == ["e1"]
    # El original no se modifica.
    assert data[("a", "rel", "b")].edge_index.shape == (2, 3)


def test_train_compositional_model(graphs: dict[str, HeteroData]) -> None:
    ids = sorted(graphs)
    metadata = GraphMetadata.from_graphs(list(graphs.values()))
    from nutrigraphdt.models.gnn import build_model
    from nutrigraphdt.models.training import FeatureScaler, set_seed

    set_seed(SEED)
    transform = CompositionalTargetTransform.fit([graphs[s] for s in ids[:12]])
    scaler = FeatureScaler.fit([graphs[s] for s in ids[:12]])
    model = build_model(load_model_config("configs/models/homo_sage.yaml"), metadata)
    result = train_compositional_model(
        model,
        scaler.transform([graphs[s] for s in ids[:12]]),
        scaler.transform([graphs[s] for s in ids[12:]]),
        _config(),
        transform,
    )
    assert 1 <= result.best_epoch <= result.epochs_run <= 3
    assert result.best_val_loss == min(r.val_loss for r in result.history)


def test_run_compositional_fold(
    graphs: dict[str, HeteroData], context: dict[str, dict[str, str]]
) -> None:
    ids = sorted(graphs)
    metadata = GraphMetadata.from_graphs(list(graphs.values()))
    evaluation = run_compositional_fold(
        seed=0,
        fold=0,
        model_name="homo_sage",
        edges_arm="with_inferred",
        train_ids=ids[:12],
        test_ids=ids[12:],
        graphs=graphs,
        pens=context["pens"],
        diets=context["diets"],
        days=context["days"],
        model_config=load_model_config("configs/models/homo_sage.yaml"),
        metadata=metadata,
        config=_config(),
        inner_folds=3,
    )
    assert evaluation.n_train + evaluation.n_inner_val == 12
    assert evaluation.n_test == 4
    assert len(evaluation.predictions) == 4
    metrics = {row.metric for row in evaluation.report.rows}
    assert {"fraction_r2", "log_total_r2", "reconstructed_mae"} <= metrics
    assert all(row.split == "test" for row in evaluation.report.rows)


def test_run_compositional_fold_sin_grafo(
    graphs: dict[str, HeteroData], context: dict[str, dict[str, str]]
) -> None:
    ids = sorted(graphs)
    with pytest.raises(CompositionalTrainingError, match="sin grafo"):
        run_compositional_fold(
            seed=0,
            fold=0,
            model_name="homo_sage",
            edges_arm="with_inferred",
            train_ids=ids[:12],
            test_ids=["desconocido"],
            graphs=graphs,
            pens=context["pens"],
            diets=context["diets"],
            days=context["days"],
            model_config=load_model_config("configs/models/homo_sage.yaml"),
            metadata=GraphMetadata.from_graphs(list(graphs.values())),
            config=_config(),
            inner_folds=3,
        )
