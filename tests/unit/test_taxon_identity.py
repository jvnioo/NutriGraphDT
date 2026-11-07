"""Identidad de los taxones por linaje, multiplicada por la abundancia (#266, decisión de #239)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")

from torch_geometric.data import HeteroData  # noqa: E402

from nutrigraphdt.graph.builder import add_reverse_edges  # noqa: E402
from nutrigraphdt.graph.heterodata import build_synthetic_graphs  # noqa: E402
from nutrigraphdt.models.baselines import build_synthetic_cohort  # noqa: E402
from nutrigraphdt.models.gnn import load_model_config  # noqa: E402
from nutrigraphdt.models.gnn.base import GraphMetadata  # noqa: E402
from nutrigraphdt.models.gnn.batching import align_graph_types  # noqa: E402
from nutrigraphdt.models.gnn.components import NodeTypeEncoder  # noqa: E402
from nutrigraphdt.models.gnn.factory import build_model  # noqa: E402
from nutrigraphdt.models.gnn.target import add_graph_target  # noqa: E402
from nutrigraphdt.models.training import TrainingConfig  # noqa: E402
from nutrigraphdt.models.training.compositional import run_compositional_fold  # noqa: E402
from nutrigraphdt.models.training.compositional_tracking import (  # noqa: E402
    load_compositional_run,
    predict_compositional,
)
from nutrigraphdt.models.training.taxon_identity import (  # noqa: E402
    OTHER_GROUP,
    TaxonIdentityConfig,
    TaxonLineageEncoder,
    group_profile,
    taxon_groups,
    without_functional_structure,
)

LINEAGES = {
    "g__A": "p__F;c__C;o__O;f__Uno;g__A",
    "g__B": "p__F;c__C;o__O;f__Uno;g__B",
    "g__C": "p__F;c__C;o__O;f__Dos;g__C",
    "g__SinFamilia": "p__F;c__C;o__Orden",
    "f__Dos;g__": "p__F;c__C;o__O;f__Dos",
}


def _graph(abundances: dict[str, float]) -> HeteroData:
    data = HeteroData()
    ids = list(abundances)
    store = data["taxon"]
    store.x = torch.tensor([[abundances[t]] for t in ids], dtype=torch.float32)
    store.missing_mask = torch.zeros((len(ids), 1), dtype=torch.bool)
    store.node_id = ids
    store.raw_attributes = [{"taxonomy_id": LINEAGES.get(t, t)} for t in ids]
    return data


def test_groups_use_the_family_or_the_deepest_rank_above_genus() -> None:
    graph = _graph(dict.fromkeys(LINEAGES, 0.2))

    assert taxon_groups(graph) == ["f__Uno", "f__Uno", "f__Dos", "o__Orden", "f__Dos"]
    assert group_profile(graph)["f__Uno"] == pytest.approx(0.4)


def test_a_taxon_without_lineage_goes_to_the_reserved_column() -> None:
    assert taxon_groups(_graph({"g__Suelto": 1.0})) == [OTHER_GROUP]


def test_vocabulary_applies_prevalence_and_top_k_only_with_train() -> None:
    train = [
        _graph({"g__A": 0.7, "g__C": 0.3, "g__SinFamilia": 0.0}),
        _graph({"g__A": 0.5, "g__C": 0.5, "g__SinFamilia": 0.0}),
        _graph({"g__A": 0.9, "g__C": 0.0, "g__SinFamilia": 0.1}),
    ]
    config = TaxonIdentityConfig(min_prevalence=0.5, top_k=5)

    encoder = TaxonLineageEncoder.fit(train, config)

    # o__Orden solo está en 1 de 3 grafos.
    assert encoder.vocabulary == ("f__Dos", "f__Uno")
    assert encoder.columns == ("f__Dos", "f__Uno", OTHER_GROUP)
    limited = TaxonLineageEncoder.fit(train, TaxonIdentityConfig(min_prevalence=0.0, top_k=1))
    assert limited.vocabulary == ("f__Uno",)


def test_vocabulary_does_not_depend_on_graphs_outside_train() -> None:
    train = [_graph({"g__A": 1.0, "g__C": 0.0})]
    encoder = TaxonLineageEncoder.fit(train, TaxonIdentityConfig(min_prevalence=0.5))
    assert encoder.vocabulary == ("f__Uno",)

    # f__Dos aparece solo en un grafo de test: no agrega columnas y cae en «otras».
    (encoded,) = encoder.transform([_graph({"g__A": 0.25, "g__C": 0.75})])

    assert encoded["taxon"].x.tolist() == [[0.25, 0.0], [0.0, 0.75]]


def test_transform_keeps_the_sum_and_does_not_touch_the_original() -> None:
    graph = _graph({"g__A": 0.5, "g__C": 0.5})
    encoder = TaxonLineageEncoder(("f__Uno", "f__Dos"))

    (encoded,) = encoder.transform([graph])

    assert encoded["taxon"].x.shape == (2, 3)
    assert encoded["taxon"].missing_mask.shape == (2, 3)
    assert float(encoded["taxon"].x.sum()) == pytest.approx(1.0)
    assert graph["taxon"].x.shape == (2, 1)


def test_missing_abundance_stays_masked_in_its_group_column() -> None:
    graph = _graph({"g__A": 0.0, "g__C": 1.0})
    graph["taxon"].missing_mask[0, 0] = True

    (encoded,) = TaxonLineageEncoder(("f__Uno", "f__Dos")).transform([graph])

    assert encoded["taxon"].missing_mask.tolist() == [
        [True, False, False],
        [False, False, False],
    ]


@pytest.mark.parametrize("kwargs", [{"min_prevalence": 1.5}, {"min_abundance": -1.0}, {"top_k": 0}])
def test_invalid_config_is_rejected(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        TaxonIdentityConfig(**kwargs)  # type: ignore[arg-type]


def test_encoder_needs_train_graphs_and_a_single_abundance_column() -> None:
    with pytest.raises(ValueError, match="entrenamiento"):
        TaxonLineageEncoder.fit([])
    graph = _graph({"g__A": 1.0})
    graph["taxon"].x = torch.ones((1, 2))
    with pytest.raises(ValueError, match="una columna"):
        group_profile(graph)


def test_encoder_round_trips_through_its_dictionary() -> None:
    encoder = TaxonLineageEncoder(("f__Uno",), TaxonIdentityConfig(top_k=7))

    restored = TaxonLineageEncoder.from_dict(json.loads(json.dumps(encoder.to_dict())))

    assert restored.vocabulary == encoder.vocabulary
    assert restored.config == encoder.config


def _linear_block(graphs: list[HeteroData], channels: int) -> list[list[float]]:
    """El bloque `taxon` de la lectura con un encoder lineal, antes de cualquier arista."""
    encoder = NodeTypeEncoder({"taxon": channels}, 4)
    blocks = []
    for graph in graphs:
        store = graph["taxon"]
        h = encoder({"taxon": store.x}, {"taxon": store.missing_mask})["taxon"]
        blocks.append(h.mean(0).tolist())
    return blocks


def test_the_taxon_block_of_the_readout_varies_between_animals_only_with_identity() -> None:
    """Criterio de aceptación de #266: deja de valer la premisa de `check_d1_taxon_readout.py`."""
    torch.manual_seed(0)
    first = _graph({"g__A": 0.7, "g__B": 0.1, "g__C": 0.2})
    second = _graph({"g__A": 0.1, "g__B": 0.1, "g__C": 0.8})

    plain = _linear_block([first, second], 1)
    assert plain[0] == pytest.approx(plain[1], abs=1e-6)

    encoder = TaxonLineageEncoder(("f__Uno", "f__Dos"))
    encoded = encoder.transform([first, second])
    with_identity = _linear_block(encoded, len(encoder.columns))
    assert with_identity[0] != pytest.approx(with_identity[1], abs=1e-3)


def test_a_nonlinear_encoder_varies_between_animals_without_identity() -> None:
    torch.manual_seed(0)
    encoder = NodeTypeEncoder({"taxon": 1}, 4, nonlinear_types=("taxon",))
    blocks = []
    for graph in (_graph({"g__A": 0.9, "g__C": 0.1}), _graph({"g__A": 0.5, "g__C": 0.5})):
        store = graph["taxon"]
        h = encoder({"taxon": store.x}, {"taxon": store.missing_mask})["taxon"]
        blocks.append(h.mean(0).tolist())
    assert blocks[0] != pytest.approx(blocks[1], abs=1e-6)


def test_functional_structure_can_be_removed_for_the_control_arms() -> None:
    built = build_synthetic_graphs(build_synthetic_cohort(2, first_seed=1))
    graph = add_reverse_edges(next(iter(built.graphs.values())))
    assert "function" in graph.node_types

    stripped = without_functional_structure(graph)

    assert "function" not in stripped.node_types
    assert not [e for e in stripped.edge_types if "function" in (e[0], e[2])]
    assert "function" in graph.node_types


@pytest.fixture(scope="module")
def graphs() -> dict[str, HeteroData]:
    built = build_synthetic_graphs(build_synthetic_cohort(16, first_seed=1))
    prepared: dict[str, HeteroData] = {}
    for graph_id, graph in built.graphs.items():
        with_target = add_graph_target(add_reverse_edges(graph))
        with_target.graph_id = graph_id
        families = ["f__Uno", "f__Dos", "f__Tres"]
        with_target["taxon"].raw_attributes = [
            {**attributes, "taxonomy_id": f"p__F;{families[i % 3]};g__G{i}"}
            for i, attributes in enumerate(with_target["taxon"].raw_attributes)
        ]
        prepared[str(with_target.sample_id)] = with_target
    align_graph_types(list(prepared.values()), inplace=True)
    return prepared


def test_fold_fits_the_vocabulary_trains_and_reloads(
    graphs: dict[str, HeteroData], tmp_path: Path
) -> None:
    ids = sorted(graphs)
    metadata = GraphMetadata.from_graphs(list(graphs.values()))
    config = TrainingConfig.model_validate(
        {
            "lr": 1e-2,
            "weight_decay": 1e-4,
            "batch_size": 4,
            "max_epochs": 2,
            "patience": 2,
            "seed": 7,
            "dataset_id": "synthetic_cohort",
            "split_file": "configs/splits/d1_holofood.json",
        }
    )
    evaluation = run_compositional_fold(
        seed=1,
        fold=0,
        model_name="hetero_sage",
        edges_arm="with_identity",
        train_ids=ids[:12],
        test_ids=ids[12:],
        graphs=graphs,
        pens={s: f"pen{i // 2}" for i, s in enumerate(ids)},
        diets={s: f"dieta{i % 2}" for i, s in enumerate(ids)},
        days={s: "7" for s in ids},
        model_config=load_model_config("configs/models/hetero_sage.yaml"),
        metadata=metadata,
        config=config,
        inner_folds=3,
        taxon_identity=TaxonIdentityConfig(min_prevalence=0.0),
        runs_dir=tmp_path,
        run_context={
            "dataset_id": "synthetic_cohort",
            "plan": {"file": "plan.json", "sha256": "abc", "version": "1.0.0", "k": 2},
            "cohort": {"size": 16},
        },
    )

    assert evaluation.taxon_vocabulary == ("f__Dos", "f__Tres", "f__Uno")
    assert graphs[ids[0]]["taxon"].x.shape[1] == metadata.node_channels["taxon"]
    assert evaluation.run_dir is not None
    info = json.loads((evaluation.run_dir / "run.json").read_text(encoding="utf-8"))
    assert info["taxon_identity"]["vocabulary"] == ["f__Dos", "f__Tres", "f__Uno"]
    assert info["metadata"]["node_channels"]["taxon"] == 4

    loaded = load_compositional_run(evaluation.run_dir)
    assert loaded.taxon_encoder is not None
    samples, predicted = predict_compositional(loaded, [graphs[s] for s in ids[12:]])
    original = {p["sample_id"]: p for p in evaluation.predictions}
    for row, sample in enumerate(samples):
        assert float(predicted[row, 0]) == pytest.approx(original[sample]["z1"], abs=1e-4)


def test_model_config_builds_a_nonlinear_taxon_encoder(graphs: dict[str, HeteroData]) -> None:
    metadata = GraphMetadata.from_graphs(list(graphs.values()))
    base = load_model_config("configs/models/hetero_sage.yaml")

    linear = build_model(base, metadata)
    nonlinear = build_model(base.model_copy(update={"nonlinear_taxon_encoder": True}), metadata)

    assert isinstance(linear.encoder.projections["taxon"], torch.nn.Linear)
    assert isinstance(nonlinear.encoder.projections["taxon"], torch.nn.Sequential)
