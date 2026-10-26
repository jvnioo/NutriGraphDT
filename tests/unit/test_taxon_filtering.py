"""Tests unitarios para filtrado de taxones raros con train (A52-P2, #160)."""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from torch_geometric.data import HeteroData  # noqa: E402

from nutrigraphdt.models.training.filtering import (  # noqa: E402
    TaxonFilter,
    TaxonFilterConfig,
)


def _create_graph_with_taxa(
    sample_id: str,
    taxa_abundances: dict[str, float],
    *,
    with_functions: bool = False,
) -> HeteroData:
    """Crea un HeteroData con nodos taxon y opcionalmente aristas a funciones."""
    g = HeteroData()
    g.sample_id = sample_id
    g.graph_id = f"graph_{sample_id}"

    taxa_ids = list(taxa_abundances.keys())
    num_taxa = len(taxa_ids)
    abundances = [taxa_abundances[t] for t in taxa_ids]

    g["taxon"].node_id = taxa_ids
    g["taxon"].x = torch.tensor([[a] for a in abundances], dtype=torch.float32)

    # Nodos host para lectura
    g["host"].node_id = [f"{sample_id}:host"]
    g["host"].x = torch.tensor([[1.0, 2.0]], dtype=torch.float32)

    # Nodos diet aislados
    g["diet"].node_id = [f"{sample_id}:diet"]
    g["diet"].x = torch.tensor([[0.5]], dtype=torch.float32)

    if with_functions and num_taxa > 0:
        g["function"].node_id = ["func_1", "func_2"]
        g["function"].x = torch.ones((2, 1), dtype=torch.float32)

        # Aristas taxon -> function
        # taxón 0 -> func_0, taxón 1 -> func_1 (si existen)
        src_list = []
        dst_list = []
        for i in range(min(num_taxa, 2)):
            src_list.append(i)
            dst_list.append(i)

        edge_index = torch.tensor([src_list, dst_list], dtype=torch.long)
        g["taxon", "has_capacity", "function"].edge_index = edge_index
        g["taxon", "has_capacity", "function"].edge_attr = torch.ones(
            (len(src_list), 1), dtype=torch.float32
        )

    return g


class TestTaxonFilterFittingAndNoLeakage:
    """Prueba fundamental de no fuga: validación y test no intervienen en la selección."""

    def test_validation_and_test_data_do_not_intervene_in_taxon_selection(self) -> None:
        """Criterio de aceptación A52-P2: demuestra formalmente que los datos de val y test

        no intervienen en la selección del vocabulario ni en las estadísticas del filtro.
        """
        # 1. Conjunto de entrenamiento (10 grafos):
        # Taxón A: en 8 de 10 grafos (prevalencia 0.8) -> COMÚN
        # Taxón B: en 5 de 10 grafos (prevalencia 0.5) -> COMÚN
        # Taxón R: en 1 de 10 grafos (prevalencia 0.1) -> RARO
        # Taxón Z: NUNCA aparece en train (prevalencia 0.0) -> AUSENTE
        train_graphs = []
        for i in range(10):
            t_map = {}
            if i < 8:
                t_map["taxon_A"] = 0.5
            if i < 5:
                t_map["taxon_B"] = 0.3
            if i == 0:
                t_map["taxon_R"] = 0.05
            train_graphs.append(_create_graph_with_taxa(f"train_{i}", t_map))

        # 2. Conjunto de validación y prueba:
        # Contienen taxón Z con abundancia gigante (100.0) en el 100% de las muestras.
        # Contienen taxón R en el 100% de las muestras (en train era raro con solo 1 muestra).
        val_graphs = [
            _create_graph_with_taxa(f"val_{i}", {"taxon_Z": 100.0, "taxon_R": 50.0, "taxon_A": 0.2})
            for i in range(5)
        ]
        test_graphs = [
            _create_graph_with_taxa(
                f"test_{i}", {"taxon_Z": 200.0, "taxon_R": 80.0, "taxon_B": 0.1}
            )
            for i in range(5)
        ]

        # 3. Ajustamos TaxonFilter con umbral de prevalencia = 0.3 (30%)
        # Taxón A: 8/10 = 0.8 >= 0.3 -> seleccionado
        # Taxón B: 5/10 = 0.5 >= 0.3 -> seleccionado
        # Taxón R: 1/10 = 0.1 < 0.3 -> RECHAZADO (a pesar de estar al 100% en val/test)
        # Taxón Z: 0/10 = 0.0 < 0.3 -> RECHAZADO (a pesar de estar al 100% en val/test)
        filter_obj = TaxonFilter.fit(train_graphs, min_prevalence=0.3)

        assert filter_obj.is_fitted
        assert filter_obj.selected_taxa == frozenset({"taxon_A", "taxon_B"})
        assert "taxon_Z" not in filter_obj.selected_taxa
        assert "taxon_R" not in filter_obj.selected_taxa

        # Demostración 1: Manipular val o test NO cambia el filtro
        # El filtro ajustado con train permanece estrictamente inmutable
        assert "alien_taxon" not in filter_obj.selected_taxa
        assert filter_obj.selected_taxa == frozenset({"taxon_A", "taxon_B"})

        # Demostración 2: Al transformar val y test, los taxones raros/ausentes son podados
        transformed_val = filter_obj.transform(val_graphs)
        for g_val in transformed_val:
            node_ids = g_val["taxon"].node_id
            # taxon_Z y taxon_R fueron podados; solo taxon_A sobrevive
            assert "taxon_Z" not in node_ids
            assert "taxon_R" not in node_ids
            assert node_ids == ["taxon_A"]
            assert g_val["taxon"].x.shape == (1, 1)

        transformed_test = filter_obj.transform(test_graphs)
        for g_test in transformed_test:
            node_ids = g_test["taxon"].node_id
            # taxon_Z y taxon_R fueron podados; solo taxon_B sobrevive
            assert "taxon_Z" not in node_ids
            assert "taxon_R" not in node_ids
            assert node_ids == ["taxon_B"]
            assert g_test["taxon"].x.shape == (1, 1)


class TestTaxonFilterEdgeReindexing:
    """Verifica que las aristas conectadas a taxones podados se filtren y reindexen."""

    def test_pruning_taxa_updates_edge_indices(self) -> None:
        """Si un taxón tiene aristas y es podado, las aristas desaparecen y se remapean."""
        # Grafo con 3 taxones: T0, T1, T2
        # Aristas:
        # T0 (idx 0) -> func_1 (idx 0)
        # T1 (idx 1) -> func_2 (idx 1)
        g = _create_graph_with_taxa(
            "sample_1", {"T0": 1.0, "T1": 1.0, "T2": 1.0}, with_functions=True
        )

        # Filtro que solo conserva T1 (idx original 1 pasa a ser idx 0)
        filter_obj = TaxonFilter(selected_taxa=frozenset({"T1"}))

        g_transformed = filter_obj.transform_graph(g)

        assert g_transformed["taxon"].node_id == ["T1"]
        assert g_transformed["taxon"].x.shape == (1, 1)

        # La arista desde T0 desapareció; la arista desde T1 debe apuntar al nuevo índice 0 de T1
        edge_index = g_transformed["taxon", "has_capacity", "function"].edge_index
        assert edge_index.shape == (2, 1)
        assert edge_index[0, 0].item() == 0  # nuevo índice de T1
        assert edge_index[1, 0].item() == 1  # destino func_2 permanece en idx 1

    def test_empty_retention_leaves_empty_edges(self) -> None:
        """Si ningún taxón es retenido, las aristas quedan con dimensión 0."""
        g = _create_graph_with_taxa("sample_1", {"T0": 1.0, "T1": 1.0}, with_functions=True)
        filter_obj = TaxonFilter(selected_taxa=frozenset())

        g_transformed = filter_obj.transform_graph(g)
        assert g_transformed["taxon"].node_id == []
        assert g_transformed["taxon"].x.shape == (0, 1)
        edge_index = g_transformed["taxon", "has_capacity", "function"].edge_index
        assert edge_index.shape == (2, 0)


class TestTaxonFilterConfigAndOptions:
    """Prueba parámetros top_k, min_abundance y validación de argumentos."""

    def test_top_k_limits_selection(self) -> None:
        train_graphs = [
            _create_graph_with_taxa("s1", {"T1": 10.0, "T2": 5.0, "T3": 1.0}),
            _create_graph_with_taxa("s2", {"T1": 10.0, "T2": 5.0, "T3": 1.0}),
        ]
        # Con top_k=2, solo los 2 más abundantes deben quedar
        f = TaxonFilter.fit(train_graphs, min_prevalence=0.0, top_k=2)
        assert f.selected_taxa == frozenset({"T1", "T2"})

    def test_min_abundance_threshold(self) -> None:
        # T1 tiene abundancia 0.05, T2 tiene 0.2
        train_graphs = [
            _create_graph_with_taxa("s1", {"T1": 0.05, "T2": 0.2}),
        ]
        # Con min_abundance=0.1, T1 no cuenta como presente
        f = TaxonFilter.fit(train_graphs, min_prevalence=0.5, min_abundance=0.1)
        assert f.selected_taxa == frozenset({"T2"})

    def test_invalid_parameters_raise_value_error(self) -> None:
        with pytest.raises(ValueError, match="min_prevalence"):
            TaxonFilterConfig(min_prevalence=1.5)

        with pytest.raises(ValueError, match="min_abundance"):
            TaxonFilterConfig(min_abundance=-0.1)

        with pytest.raises(ValueError, match="top_k"):
            TaxonFilterConfig(top_k=0)

        with pytest.raises(ValueError, match="colección vacía"):
            TaxonFilter.fit([])


class TestTaxonFilterSerialization:
    """Prueba serialización a dict y deserialización desde dict."""

    def test_roundtrip_dict(self) -> None:
        train_graphs = [
            _create_graph_with_taxa("s1", {"T1": 1.0, "T2": 0.5}),
            _create_graph_with_taxa("s2", {"T1": 1.0}),
        ]
        f1 = TaxonFilter.fit(train_graphs, min_prevalence=0.5, top_k=5)
        d = f1.to_dict()

        f2 = TaxonFilter.from_dict(d)
        assert f2.is_fitted
        assert f2.selected_taxa == f1.selected_taxa
        assert f2.config == f1.config
        assert f2.train_num_graphs == f1.train_num_graphs
        assert set(f2.taxon_stats.keys()) == set(f1.taxon_stats.keys())
