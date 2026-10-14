"""Tests unitarios para la preparación de grafos y DataLoaders (A44-1, #95).

Requiere el extra `graph`.
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from torch_geometric.data import HeteroData  # noqa: E402

from nutrigraphdt.data.split import DatasetSplit, create_split  # noqa: E402
from nutrigraphdt.data.synthetic import generate_scenario_dataset  # noqa: E402
from nutrigraphdt.graph.heterodata import (  # noqa: E402
    build_heterodata,
    build_synthetic_graphs,
    derive_schema,
)
from nutrigraphdt.models.baselines import build_synthetic_cohort  # noqa: E402
from nutrigraphdt.models.training import (  # noqa: E402
    PreparedDataLoaders,
    SubsetSummary,
    prepare_training_graphs,
)


def _make_dummy_graph(
    sample_id: str,
    graph_id: str,
    *,
    has_scfa: bool = True,
    all_scfa: bool = True,
) -> HeteroData:
    """Crea un grafo sintético mínimo para pruebas rápidas."""
    g = HeteroData()
    g.graph_id = graph_id
    g.sample_id = sample_id
    g["host"].x = torch.randn(1, 2)
    g["host"].node_id = [f"{sample_id}:host"]

    if has_scfa:
        g["metabolite"].x = torch.randn(3 if all_scfa else 1, 2)
        if all_scfa:
            g["metabolite"].y = torch.tensor([[10.0], [20.0], [30.0]])
            g["metabolite"].y_mask = torch.tensor([[True], [True], [True]])
            g["metabolite"].node_id = ["acetate", "propionate", "butyrate"]
            g["metabolite", "measured_in", "host"].edge_index = torch.tensor([[0, 1, 2], [0, 0, 0]])
        else:
            g["metabolite"].y = torch.tensor([[10.0]])
            g["metabolite"].y_mask = torch.tensor([[True]])
            g["metabolite"].node_id = ["acetate"]
            g["metabolite", "measured_in", "host"].edge_index = torch.tensor([[0], [0]])
    else:
        g["metabolite"].x = torch.randn(1, 2)
        g["metabolite"].y = torch.tensor([[0.0]])
        g["metabolite"].y_mask = torch.tensor([[False]])
        g["metabolite"].node_id = ["lactate"]
        g["metabolite", "measured_in", "host"].edge_index = torch.tensor([[0], [0]])

    return g


class TestPrepareTrainingGraphs:
    """Conjunto de pruebas para `prepare_training_graphs`."""

    def test_synthetic_cohort_counts_match_partition(self) -> None:
        """Con la cohorte sintética, el resumen de conteos coincide con la partición."""
        n_samples = 20
        cohort = build_synthetic_cohort(n_samples, first_seed=1)
        split = create_split(
            [
                {"sample_id": inst.sample_id, "diet_treatment": inst.diet_treatment}
                for inst in cohort.instances
            ],
            group_key=None,
            stratify_key="diet_treatment",
            seed=42,
        )

        built = build_synthetic_graphs(cohort)
        prepared = prepare_training_graphs(
            built.dataset,
            built.graphs,
            split,
            batch_size=4,
            seed=42,
        )

        assert isinstance(prepared, PreparedDataLoaders)
        summary = prepared.summary

        for subset in ("train", "val", "test"):
            expected = len(split[subset])
            sub_sum = summary[subset]
            assert isinstance(sub_sum, SubsetSummary)
            assert sub_sum.received == expected
            assert sub_sum.deliverable == expected
            assert sub_sum.with_any_scfa == expected
            assert sub_sum.with_all_scfa == expected

            # Prueba de acceso por propiedades en español
            assert sub_sum.recibidos == expected
            assert sub_sum.entregables == expected
            assert sub_sum.con_algun_agcc == expected
            assert sub_sum.con_los_tres_agcc == expected

            # Prueba de acceso por indexación
            assert sub_sum["received"] == expected
            assert sub_sum["recibidos"] == expected
            assert sub_sum["with_all_scfa"] == expected

    def test_no_sample_id_appears_in_more_than_one_dataloader(self) -> None:
        """Ningún sample_id aparece en más de un DataLoader."""
        n_samples = 24
        cohort = build_synthetic_cohort(n_samples, first_seed=1)
        split = create_split(
            [
                {"sample_id": inst.sample_id, "diet_treatment": inst.diet_treatment}
                for inst in cohort.instances
            ],
            group_key=None,
            stratify_key="diet_treatment",
            seed=42,
        )
        built = build_synthetic_graphs(cohort)
        prepared = prepare_training_graphs(built.dataset, built.graphs, split, batch_size=4)

        train_samples: set[str] = set()
        for batch in prepared.train:
            sids = batch.sample_id if isinstance(batch.sample_id, list) else [batch.sample_id]
            train_samples.update(sids)

        val_samples: set[str] = set()
        for batch in prepared.val:
            sids = batch.sample_id if isinstance(batch.sample_id, list) else [batch.sample_id]
            val_samples.update(sids)

        test_samples: set[str] = set()
        for batch in prepared.test:
            sids = batch.sample_id if isinstance(batch.sample_id, list) else [batch.sample_id]
            test_samples.update(sids)

        assert not (train_samples & val_samples)
        assert not (train_samples & test_samples)
        assert not (val_samples & test_samples)

        assert train_samples == set(split.train)
        assert val_samples == set(split.val)
        assert test_samples == set(split.test)

    def test_unpartitioned_sample_id_raises_explicit_error(self) -> None:
        """Un grafo cuyo sample_id no está en la partición produce un error explícito."""
        split = DatasetSplit(train=("S1", "S2"), val=("S3",), test=("S4",))
        g1 = _make_dummy_graph("S1", "G1")
        g_unknown = _make_dummy_graph("S999", "G_UNKNOWN")

        with pytest.raises(ValueError, match="S999"):
            prepare_training_graphs([g1, g_unknown], split)

    def test_missing_sample_id_raises_explicit_error(self) -> None:
        """Un grafo sin atributo sample_id produce un error explícito."""
        split = DatasetSplit(train=("S1",), val=(), test=())
        g = _make_dummy_graph("S1", "G1")
        delattr(g, "sample_id")

        with pytest.raises(ValueError, match="sample_id"):
            prepare_training_graphs([g], split)

    def test_paired_basal_and_intervention_stay_together(self) -> None:
        """El grafo basal y el intervenido de una misma muestra quedan juntos en el subconjunto."""
        dataset = generate_scenario_dataset()
        schema = derive_schema(dataset.nodes, dataset.edges, dataset.outputs)
        graphs = {
            inst.graph_id: build_heterodata(dataset, inst.graph_id, schema)
            for inst in dataset.instances
        }

        sample_id = dataset.instances[0].sample_id
        split = DatasetSplit(train=(sample_id,), val=(), test=())

        prepared = prepare_training_graphs(graphs, split, batch_size=4)

        assert prepared.summary["train"].received == 2
        assert prepared.summary["train"].deliverable == 2
        assert prepared.summary["train"].with_any_scfa == 2

        # Ambos grafos deben estar en train
        train_graph_ids = {g.graph_id for g in prepared.graphs["train"]}
        assert train_graph_ids == {dataset.instances[0].graph_id, dataset.instances[1].graph_id}

    def test_exclude_graphs_without_any_scfa(self) -> None:
        """Excluye los grafos sin ningún AGCC (y_graph_mask todo en False)."""
        split = DatasetSplit(train=("S1", "S2"), val=(), test=())
        g_with_scfa = _make_dummy_graph("S1", "G1", has_scfa=True, all_scfa=False)
        g_without_scfa = _make_dummy_graph("S2", "G2", has_scfa=False)

        prepared = prepare_training_graphs([g_with_scfa, g_without_scfa], split, batch_size=2)

        summary_train = prepared.summary["train"]
        assert summary_train.received == 2
        assert summary_train.deliverable == 2
        assert summary_train.with_any_scfa == 1
        assert summary_train.with_all_scfa == 0

        # Solo el grafo con algún AGCC entra al DataLoader
        assert len(prepared.train.dataset) == 1
        assert prepared.graphs["train"][0].graph_id == "G1"

    def test_graph_metadata_includes_reverse_edges_and_all_deliverable(self) -> None:
        """GraphMetadata se construye con todos los grafos entregables."""
        split = DatasetSplit(train=("S1",), val=("S2",), test=())
        g1 = _make_dummy_graph("S1", "G1", has_scfa=True, all_scfa=True)
        g2 = _make_dummy_graph("S2", "G2", has_scfa=True, all_scfa=False)

        prepared = prepare_training_graphs([g1, g2], split)
        metadata = prepared.metadata

        # Arista directa y su inversa
        assert ("metabolite", "measured_in", "host") in metadata.edge_types
        assert ("host", "rev_measured_in", "metabolite") in metadata.edge_types

    def test_train_shuffling_determinism_with_seed(self) -> None:
        """El generador sembrado produce el mismo orden de lotes en train."""
        n_samples = 12
        cohort = build_synthetic_cohort(n_samples, first_seed=1)
        split = create_split(
            [
                {"sample_id": inst.sample_id, "diet_treatment": inst.diet_treatment}
                for inst in cohort.instances
            ],
            group_key=None,
            stratify_key="diet_treatment",
            seed=42,
        )
        built = build_synthetic_graphs(cohort)

        prep1 = prepare_training_graphs(built.graphs, split, batch_size=2, seed=123)
        prep2 = prepare_training_graphs(built.graphs, split, batch_size=2, seed=123)

        batches1 = [list(batch.sample_id) for batch in prep1.train]
        batches2 = [list(batch.sample_id) for batch in prep2.train]
        assert batches1 == batches2

    def test_val_and_test_are_not_shuffled(self) -> None:
        """val y test no se barajan: el orden coincide con la secuencia entregada."""
        split = DatasetSplit(train=(), val=("S1", "S2"), test=("S3", "S4"))
        g1 = _make_dummy_graph("S1", "G1")
        g2 = _make_dummy_graph("S2", "G2")
        g3 = _make_dummy_graph("S3", "G3")
        g4 = _make_dummy_graph("S4", "G4")

        prepared = prepare_training_graphs([g1, g2, g3, g4], split, batch_size=2)

        val_batches = [list(batch.sample_id) for batch in prepared.val]
        assert val_batches == [["S1", "S2"]]

        test_batches = [list(batch.sample_id) for batch in prepared.test]
        assert test_batches == [["S3", "S4"]]

    def test_container_unpacking_and_indexing(self) -> None:
        """PreparedDataLoaders se puede desempaquetar e indexar."""
        split = DatasetSplit(train=("S1",), val=(), test=())
        g1 = _make_dummy_graph("S1", "G1")
        prepared = prepare_training_graphs([g1], split)

        # Desempaquetado tipo tupla: train, val, test
        train_l, val_l, test_l = prepared
        assert train_l is prepared.train
        assert val_l is prepared.val
        assert test_l is prepared.test

        # Indexación
        assert prepared["train"] is prepared.train
        assert prepared["val"] is prepared.val
        assert prepared["test"] is prepared.test

        with pytest.raises(KeyError):
            _ = prepared["invalid"]

    def test_invalid_batch_size_raises_error(self) -> None:
        """batch_size < 1 produce ValueError."""
        split = DatasetSplit(train=("S1",), val=(), test=())
        g1 = _make_dummy_graph("S1", "G1")
        with pytest.raises(ValueError, match="batch_size"):
            prepare_training_graphs([g1], split, batch_size=0)

    def test_empty_deliverable_graphs_raises_error(self) -> None:
        """Si no hay grafos entregables se produce ValueError."""
        split = DatasetSplit(train=(), val=(), test=())
        with pytest.raises(ValueError, match="entregable"):
            prepare_training_graphs([], split)
