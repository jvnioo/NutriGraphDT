"""Tests unitarios para FeatureScaler y TargetScaler (A44-2, #96).

Verifica:
1. Las estadísticas se ajustan única y exclusivamente con grafos de `train`: modificar
   `val` o `test` no altera las medias ni desviaciones.
2. `inverse_transform(transform(y))` recupera `y` dentro de la tolerancia numérica.
3. Las celdas ausentes (`missing_mask = True`) no afectan media ni desviación, quedan
   en `0.0` tras la transformación y conservan su `missing_mask`.
4. Manejo robusto de columnas constantes (desviación 0) y tipos con F_t = 0 sin división por cero.
5. Transformación sobre copias sin modificar los grafos originales.
6. Serialización bidireccional a/desde diccionario JSON para trazabilidad (A44-5).
7. Integración con grafos sintéticos heterogéneos bajo el extra `graph`.
"""

from __future__ import annotations

import json
import math

import pytest
import torch
from torch_geometric.data import HeteroData

from nutrigraphdt.data.synthetic import generate_scenario_dataset
from nutrigraphdt.graph.builder import add_reverse_edges
from nutrigraphdt.graph.heterodata import build_synthetic_graphs
from nutrigraphdt.models.gnn.target import add_graph_target
from nutrigraphdt.models.training.scaling import (
    FeatureScaler,
    TargetScaler,
    scalers_from_dict,
    scalers_to_dict,
)


def _make_dummy_graph(
    x_host: torch.Tensor | None = None,
    mask_host: torch.Tensor | None = None,
    x_taxon: torch.Tensor | None = None,
    mask_taxon: torch.Tensor | None = None,
    has_empty_diet: bool = True,
    y_graph: torch.Tensor | None = None,
    y_graph_mask: torch.Tensor | None = None,
) -> HeteroData:
    """Crea un grafo HeteroData mínimo para pruebas de escalado."""
    graph = HeteroData()

    if x_host is not None:
        graph["host"].x = x_host
        if mask_host is not None:
            graph["host"].missing_mask = mask_host

    if x_taxon is not None:
        graph["taxon"].x = x_taxon
        if mask_taxon is not None:
            graph["taxon"].missing_mask = mask_taxon

    if has_empty_diet:
        # F_t = 0 (como en D1)
        graph["diet"].x = torch.zeros((1, 0), dtype=torch.float32)

    if y_graph is not None:
        graph.y_graph = y_graph
        graph.y_graph_mask = (
            y_graph_mask if y_graph_mask is not None else torch.ones_like(y_graph, dtype=torch.bool)
        )

    return graph


class TestFeatureScaler:
    """Pruebas unitarias para FeatureScaler."""

    def test_fit_calculates_correct_mean_and_std_ignoring_missing_cells(self) -> None:
        # Grafo 1: host tiene 2 nodos, 2 features
        # fila 0: [10.0, 100.0] (ambos observados)
        # fila 1: [20.0, -999.0] (columna 1 ausente)
        x1 = torch.tensor([[10.0, 100.0], [20.0, -999.0]], dtype=torch.float32)
        m1 = torch.tensor([[False, False], [False, True]], dtype=torch.bool)
        g1 = _make_dummy_graph(x_host=x1, mask_host=m1)

        # Grafo 2: host tiene 1 nodo
        # fila 0: [30.0, 200.0] (ambos observados)
        x2 = torch.tensor([[30.0, 200.0]], dtype=torch.float32)
        m2 = torch.tensor([[False, False]], dtype=torch.bool)
        g2 = _make_dummy_graph(x_host=x2, mask_host=m2)

        scaler = FeatureScaler.fit([g1, g2])
        assert scaler.is_fitted
        stats = scaler.stats["host"]

        # Columna 0: valores observados [10.0, 20.0, 30.0] -> media = 20.0
        # varianza = ((10-20)^2 + (20-20)^2 + (30-20)^2) / 3 = 200 / 3 ≈ 66.6667
        # std = sqrt(200 / 3) ≈ 8.1649658
        assert stats.mean[0] == pytest.approx(20.0)
        assert stats.std[0] == pytest.approx(math.sqrt(200.0 / 3.0))
        assert stats.observed_count[0] == 3

        # Columna 1: valor -999.0 ignorado por missing_mask=True.
        # Observados: [100.0, 200.0] -> media = 150.0
        # varianza = ((100-150)^2 + (200-150)^2) / 2 = 5000 / 2 = 2500 -> std = 50.0
        assert stats.mean[1] == pytest.approx(150.0)
        assert stats.std[1] == pytest.approx(50.0)
        assert stats.observed_count[1] == 2

    def test_missing_cells_with_extreme_values_do_not_affect_statistics(self) -> None:
        """Criterio de aceptación: Las celdas ausentes no afectan media ni desviación."""
        x_base = torch.tensor([[1.0, 2.0], [3.0, 4.0]], dtype=torch.float32)
        m_base = torch.tensor([[False, False], [False, False]], dtype=torch.bool)
        g_base = _make_dummy_graph(x_host=x_base, mask_host=m_base)

        scaler_base = FeatureScaler.fit([g_base])

        # Ahora agregamos un nodo con celdas ausentes conteniendo valores extremos y NaN
        x_with_missing = torch.tensor(
            [[1.0, 2.0], [3.0, 4.0], [1e12, float("nan")]], dtype=torch.float32
        )
        m_with_missing = torch.tensor(
            [[False, False], [False, False], [True, True]], dtype=torch.bool
        )
        g_with_missing = _make_dummy_graph(x_host=x_with_missing, mask_host=m_with_missing)

        scaler_with_missing = FeatureScaler.fit([g_with_missing])

        assert scaler_base.stats["host"].mean == pytest.approx(
            scaler_with_missing.stats["host"].mean
        )
        assert scaler_base.stats["host"].std == pytest.approx(scaler_with_missing.stats["host"].std)

    def test_transform_zeros_out_missing_cells_and_preserves_missing_mask(self) -> None:
        """Celdas ausentes quedan en 0.0 tras escalar y conservan missing_mask."""
        x_train = torch.tensor([[10.0, 20.0], [20.0, 40.0]], dtype=torch.float32)
        m_train = torch.tensor([[False, False], [False, False]], dtype=torch.bool)
        train_graph = _make_dummy_graph(x_host=x_train, mask_host=m_train)

        scaler = FeatureScaler.fit([train_graph])

        # Grafo con una celda ausente
        x_val = torch.tensor([[15.0, 30.0], [9999.0, 30.0]], dtype=torch.float32)
        m_val = torch.tensor([[False, False], [True, False]], dtype=torch.bool)
        val_graph = _make_dummy_graph(x_host=x_val, mask_host=m_val)

        transformed = scaler.transform_graph(val_graph, inplace=False)

        # Celda ausente en fila 1, col 0 debe ser exactamente 0.0
        assert float(transformed["host"].x[1, 0]) == 0.0
        # La máscara debe conservarse
        assert transformed["host"].missing_mask.tolist() == [[False, False], [True, False]]

        # Celda observada [0, 0] = 15.0 (media train es 15.0 -> (15-15)/std = 0.0)
        assert float(transformed["host"].x[0, 0]) == pytest.approx(0.0)
        # Celda observada [0, 1] = 30.0 (media train es 30.0 -> (30-30)/std = 0.0)
        assert float(transformed["host"].x[0, 1]) == pytest.approx(0.0)

    def test_transform_does_not_mutate_original_graphs(self) -> None:
        """Se aplica sobre una copia, sin modificar los grafos originales."""
        x_orig = torch.tensor([[10.0, 20.0]], dtype=torch.float32)
        g_orig = _make_dummy_graph(x_host=x_orig)
        x_clone_before = g_orig["host"].x.clone()

        scaler = FeatureScaler.fit([g_orig])
        g_transformed = scaler.transform_graph(g_orig, inplace=False)

        assert not torch.allclose(g_transformed["host"].x, g_orig["host"].x)
        assert torch.allclose(g_orig["host"].x, x_clone_before)

    def test_changing_val_or_test_does_not_change_train_statistics(self) -> None:
        """Criterio de aceptación: Cambiar los valores de val o test no cambia las estadísticas."""
        x_train = torch.tensor([[10.0], [20.0]], dtype=torch.float32)
        g_train = _make_dummy_graph(x_host=x_train)

        x_val_1 = torch.tensor([[100.0]], dtype=torch.float32)
        x_val_2 = torch.tensor([[99999.0]], dtype=torch.float32)
        g_val_1 = _make_dummy_graph(x_host=x_val_1)
        g_val_2 = _make_dummy_graph(x_host=x_val_2)

        scaler_1 = FeatureScaler.fit([g_train])
        _ = scaler_1.transform([g_val_1])
        stats_1 = scaler_1.stats["host"]

        scaler_2 = FeatureScaler.fit([g_train])
        _ = scaler_2.transform([g_val_2])
        stats_2 = scaler_2.stats["host"]

        assert stats_1.mean == stats_2.mean
        assert stats_1.std == stats_2.std

    def test_constant_columns_and_zero_feature_types_handled_without_zero_division(
        self,
    ) -> None:
        """Maneja columnas constantes (desviación 0) y tipos con F_t = 0 sin división por cero."""
        # Columna constante (valores idénticos 5.0)
        x_const = torch.tensor([[5.0], [5.0], [5.0]], dtype=torch.float32)
        g = _make_dummy_graph(x_host=x_const, has_empty_diet=True)

        scaler = FeatureScaler.fit([g])
        host_stats = scaler.stats["host"]
        diet_stats = scaler.stats["diet"]

        # std de host no debe ser 0.0 sino 1.0 (para evitar división por cero)
        assert host_stats.mean[0] == 5.0
        assert host_stats.std[0] == 1.0

        # F_t = 0 para diet
        assert diet_stats.num_features == 0
        assert diet_stats.mean == ()
        assert diet_stats.std == ()

        # Transformar no lanza error ni produce NaN/Inf
        transformed = scaler.transform_graph(g)
        assert not torch.isnan(transformed["host"].x).any()
        assert not torch.isinf(transformed["host"].x).any()
        # (5.0 - 5.0) / 1.0 = 0.0
        assert (transformed["host"].x == 0.0).all()
        assert transformed["diet"].x.shape == (1, 0)

    def test_json_serialization_roundtrip(self) -> None:
        """Serializar a un diccionario JSON y reconstruir fielmente."""
        x = torch.tensor([[10.0, 20.0], [30.0, 40.0]], dtype=torch.float32)
        g = _make_dummy_graph(x_host=x, has_empty_diet=True)

        scaler = FeatureScaler.fit([g])
        dict_data = scaler.to_dict()

        # Debe ser serializable con json.dumps
        json_str = json.dumps(dict_data)
        assert isinstance(json_str, str)

        reconstructed = FeatureScaler.from_dict(dict_data)
        assert reconstructed.is_fitted
        assert reconstructed.stats.keys() == scaler.stats.keys()
        for k in scaler.stats:
            assert reconstructed.stats[k].mean == scaler.stats[k].mean
            assert reconstructed.stats[k].std == scaler.stats[k].std
            assert reconstructed.stats[k].num_features == scaler.stats[k].num_features

        # Reconstrucción desde cadena JSON
        from_json_scaler = FeatureScaler.from_json(json_str)
        assert from_json_scaler.stats["host"].mean == scaler.stats["host"].mean

    def test_transform_subsets_convenience(self) -> None:
        g_train = _make_dummy_graph(x_host=torch.tensor([[10.0]], dtype=torch.float32))
        g_val = _make_dummy_graph(x_host=torch.tensor([[20.0]], dtype=torch.float32))
        g_test = _make_dummy_graph(x_host=torch.tensor([[30.0]], dtype=torch.float32))

        scaler = FeatureScaler.fit([g_train])
        subsets = scaler.transform_subsets({"train": [g_train], "val": [g_val], "test": [g_test]})

        assert set(subsets.keys()) == {"train", "val", "test"}
        assert len(subsets["train"]) == 1
        assert len(subsets["val"]) == 1
        assert len(subsets["test"]) == 1


class TestTargetScaler:
    """Pruebas unitarias para TargetScaler."""

    def test_fit_and_inverse_transform_recovers_original_within_tolerance(self) -> None:
        """inverse_transform(transform(y)) recupera y dentro de la tolerancia."""
        # 3 AGCC: acetate, propionate, butyrate
        y = torch.tensor(
            [
                [35.0, 15.0, 8.0],
                [45.0, 25.0, 12.0],
                [55.0, 35.0, 16.0],
            ],
            dtype=torch.float32,
        )
        scaler = TargetScaler.fit(y)
        assert scaler.is_fitted

        # Medias calculadas: [45.0, 25.0, 12.0]
        assert scaler.mean_tuple == pytest.approx((45.0, 25.0, 12.0))

        scaled = scaler.transform(y)
        recovered = scaler.inverse_transform(scaled)

        assert torch.allclose(recovered, y, atol=1e-5)

    def test_unmeasured_targets_are_ignored_in_fitting_and_zeroed_in_transform(self) -> None:
        """Las muestras no medidas (y_graph_mask = False) no afectan las estadísticas."""
        # Muestra 0: los tres medidos
        # Muestra 1: propionato ausente con valor basura 99999.0
        y = torch.tensor(
            [
                [10.0, 20.0, 30.0],
                [20.0, 99999.0, 40.0],
            ],
            dtype=torch.float32,
        )
        mask = torch.tensor(
            [
                [True, True, True],
                [True, False, True],
            ],
            dtype=torch.bool,
        )

        scaler = TargetScaler.fit(y, mask=mask)
        # Para propionato (col 1), solo se observó 20.0
        assert scaler.mean_tuple[1] == 20.0
        assert scaler.std_tuple[1] == 1.0  # std 0 manejada como 1.0
        assert scaler.observed_count[1] == 1

        # Transformar con máscara
        transformed = scaler.transform(y, mask=mask)
        # La celda ausente debe ser 0.0
        assert float(transformed[1, 1]) == 0.0

    def test_constant_target_column_without_zero_division(self) -> None:
        """Columna con desviación 0 no divide por cero y recupera el valor en inverse_transform."""
        y_const = torch.tensor([[10.0, 5.0, 1.0], [20.0, 5.0, 2.0]], dtype=torch.float32)
        scaler = TargetScaler.fit(y_const)

        assert scaler.std_tuple[1] == 1.0  # columna constante de propionato

        scaled = scaler.transform(y_const)
        assert not torch.isnan(scaled).any()
        assert not torch.isinf(scaled).any()

        recovered = scaler.inverse_transform(scaled)
        assert torch.allclose(recovered, y_const, atol=1e-5)

    def test_changing_val_or_test_targets_does_not_change_train_statistics(self) -> None:
        """Criterio de aceptación: Cambiar los valores de val o test no cambia las estadísticas."""
        y_train = torch.tensor([[10.0, 20.0, 30.0], [20.0, 30.0, 40.0]], dtype=torch.float32)
        scaler = TargetScaler.fit(y_train)

        stats_mean_before = scaler.mean_tuple
        stats_std_before = scaler.std_tuple

        # Transformar lotes de val con valores extremos
        y_val_extreme = torch.tensor([[1e6, -1e6, 1e7]], dtype=torch.float32)
        _ = scaler.transform(y_val_extreme)

        assert scaler.mean_tuple == stats_mean_before
        assert scaler.std_tuple == stats_std_before

    def test_fit_from_heterodata_graphs(self) -> None:
        """TargetScaler puede ajustarse directamente desde una lista de HeteroData."""
        g1 = _make_dummy_graph(
            y_graph=torch.tensor([[10.0, 20.0, 30.0]], dtype=torch.float32),
            y_graph_mask=torch.tensor([[True, True, True]], dtype=torch.bool),
        )
        g2 = _make_dummy_graph(
            y_graph=torch.tensor([[20.0, 40.0, 50.0]], dtype=torch.float32),
            y_graph_mask=torch.tensor([[True, True, True]], dtype=torch.bool),
        )

        scaler = TargetScaler.fit([g1, g2])
        assert scaler.mean_tuple == pytest.approx((15.0, 30.0, 40.0))

        # transform_graph
        g_scaled = scaler.transform_graph(g1, inplace=False)
        assert not torch.allclose(g_scaled.y_graph, g1.y_graph)
        assert torch.allclose(g1.y_graph, torch.tensor([[10.0, 20.0, 30.0]]))

    def test_json_serialization_roundtrip(self) -> None:
        """Serialización bidireccional a diccionario JSON."""
        y = torch.tensor([[10.0, 20.0, 30.0], [20.0, 30.0, 40.0]], dtype=torch.float32)
        scaler = TargetScaler.fit(y)

        dict_data = scaler.to_dict()
        json_str = json.dumps(dict_data)
        assert isinstance(json_str, str)

        reconstructed = TargetScaler.from_dict(dict_data)
        assert reconstructed.targets == scaler.targets
        assert reconstructed.mean_tuple == scaler.mean_tuple
        assert reconstructed.std_tuple == scaler.std_tuple

        from_json_scaler = TargetScaler.from_json(json_str)
        assert from_json_scaler.mean_tuple == scaler.mean_tuple

    def test_scalers_pair_serialization(self) -> None:
        """serializar ambos a un diccionario JSON para guardarlos en la corrida (A44-5)."""
        x = torch.tensor([[1.0, 2.0], [3.0, 4.0]], dtype=torch.float32)
        g = _make_dummy_graph(
            x_host=x,
            y_graph=torch.tensor([[10.0, 20.0, 30.0]], dtype=torch.float32),
            y_graph_mask=torch.tensor([[True, True, True]], dtype=torch.bool),
        )

        f_scaler = FeatureScaler.fit([g])
        t_scaler = TargetScaler.fit([g])

        run_dict = scalers_to_dict(f_scaler, t_scaler)
        json_blob = json.dumps(run_dict)
        assert "feature_scaler" in run_dict
        assert "target_scaler" in run_dict

        reloaded_f, reloaded_t = scalers_from_dict(json.loads(json_blob))
        assert reloaded_f.is_fitted
        assert reloaded_t.is_fitted
        assert reloaded_t.mean_tuple == t_scaler.mean_tuple


class TestScalingWithSyntheticGraphs:
    """Pruebas de integración con el extra `graph` sobre la cohorte sintética."""

    def test_synthetic_cohort_scaling_pipeline(self) -> None:
        # Generar grafos sintéticos con aristas inversas y targets
        dataset = generate_scenario_dataset()
        graphs_dict = build_synthetic_graphs(dataset).graphs
        graph_ids = sorted(graphs_dict.keys())

        prepared_graphs = [
            add_graph_target(add_reverse_edges(graphs_dict[gid])) for gid in graph_ids
        ]

        # Simular partición 60/20/20
        n_train = int(len(prepared_graphs) * 0.6)
        n_val = int(len(prepared_graphs) * 0.2)
        train_graphs = prepared_graphs[:n_train]
        val_graphs = prepared_graphs[n_train : n_train + n_val]
        test_graphs = prepared_graphs[n_train + n_val :]

        # 1. Ajustar FeatureScaler solo con train
        f_scaler = FeatureScaler.fit(train_graphs)
        assert f_scaler.is_fitted

        # Verificar que se descubrieron los tipos de nodo sintéticos
        stats = f_scaler.stats
        assert "taxon" in stats
        assert "host" in stats

        # 2. Ajustar TargetScaler solo con train
        t_scaler = TargetScaler.fit(train_graphs)
        assert t_scaler.is_fitted
        assert len(t_scaler.mean_tuple) == 3

        # 3. Transformar los 3 subconjuntos
        scaled_subsets = f_scaler.transform_subsets(
            {"train": train_graphs, "val": val_graphs, "test": test_graphs}
        )

        train_scaled = scaled_subsets["train"]
        val_scaled = scaled_subsets["val"]
        test_scaled = scaled_subsets["test"]
        assert len(test_scaled) == len(test_graphs)

        # 4. Verificar que en train_scaled las celdas observadas tienen media cercana a 0
        taxon_train_x = torch.cat([g["taxon"].x for g in train_scaled], dim=0)
        taxon_train_mask = torch.cat([g["taxon"].missing_mask for g in train_scaled], dim=0)
        taxon_obs = ~taxon_train_mask

        for col in range(taxon_train_x.size(1)):
            col_obs = taxon_obs[:, col]
            if col_obs.any():
                col_vals = taxon_train_x[col_obs, col]
                # En train la media estandarizada debe ser ~0.0
                assert float(col_vals.mean().item()) == pytest.approx(0.0, abs=1e-4)

        # 5. Transformar y revertir targets de val
        for g_val in val_scaled:
            y_orig = g_val.y_graph.clone()
            g_scaled_val = t_scaler.transform_graph(g_val, inplace=False)
            recovered = t_scaler.inverse_transform(
                g_scaled_val.y_graph, mask=g_scaled_val.y_graph_mask
            )
            assert torch.allclose(recovered, y_orig, atol=1e-5)

    def test_feature_scaler_nan_in_observed_cell_raises_error(self) -> None:
        """Un valor NaN en una celda no enmascarada (missing_mask=False) produce ValueError."""
        x = torch.tensor([[1.0, float("nan")], [3.0, 4.0]])
        mask = torch.tensor([[False, False], [False, False]])
        g = _make_dummy_graph(x_host=x, mask_host=mask)

        with pytest.raises(ValueError, match="no finito.*host"):
            FeatureScaler.fit([g])

    def test_target_scaler_nan_in_observed_target_raises_error(self) -> None:
        """Un valor NaN en un target medido (y_graph_mask=True) produce ValueError."""
        y = torch.tensor([[10.0, float("nan"), 30.0]])
        mask = torch.tensor([[True, True, True]])

        with pytest.raises(ValueError, match="no finito.*target"):
            TargetScaler.fit(y, mask=mask)

    def test_empty_feature_scaler_warns_on_transform(self) -> None:
        """FeatureScaler ajustado con stats vacías emite UserWarning al transformar."""
        scaler = FeatureScaler(stats={})
        assert scaler.is_fitted
        g = _make_dummy_graph(x_host=torch.tensor([[1.0, 2.0]]))

        with pytest.warns(UserWarning, match="no contiene estadísticas"):
            scaler.transform_graph(g)

    def test_unseen_node_type_with_features_warns_on_transform(self) -> None:
        """Un tipo de nodo con features ausente en train emite UserWarning al transformar."""
        g_train = _make_dummy_graph(x_host=torch.tensor([[1.0, 2.0]]))
        scaler = FeatureScaler.fit([g_train])

        g_val = _make_dummy_graph(
            x_host=torch.tensor([[1.0, 2.0]]),
            x_taxon=torch.tensor([[10.0, 20.0]]),
        )

        with pytest.warns(UserWarning, match="taxon.*no fue observado"):
            scaler.transform_graph(g_val)


class TestScalingContracts:
    """Entradas inválidas y casos borde del escalado (A52-P3, #154)."""

    def test_feature_scaler_rejects_empty_train(self) -> None:
        with pytest.raises(ValueError, match="no puede estar vacío"):
            FeatureScaler.fit([])

    def test_feature_scaler_rejects_inconsistent_widths_across_train_graphs(self) -> None:
        g1 = _make_dummy_graph(x_host=torch.tensor([[1.0, 2.0]]))
        g2 = _make_dummy_graph(x_host=torch.tensor([[1.0, 2.0, 3.0]]))
        with pytest.raises(ValueError, match="Dimensión inconsistente.*host"):
            FeatureScaler.fit([g1, g2])

    def test_feature_scaler_rejects_mask_with_another_shape(self) -> None:
        g = _make_dummy_graph(
            x_host=torch.tensor([[1.0, 2.0]]), mask_host=torch.tensor([[False, False, False]])
        )
        with pytest.raises(ValueError, match="missing_mask de 'host'"):
            FeatureScaler.fit([g])

    def test_column_never_observed_in_train_is_neutral(self) -> None:
        """Una columna ausente en todo `train` se escala con media 0 y desviación 1."""
        x = torch.tensor([[1.0, 99.0], [3.0, -99.0]])
        mask = torch.tensor([[False, True], [False, True]])
        scaler = FeatureScaler.fit([_make_dummy_graph(x_host=x, mask_host=mask)])

        stats = scaler.stats["host"]
        assert stats.observed_count == (2, 0)
        assert (stats.mean[1], stats.std[1]) == (0.0, 1.0)
        # En val la columna sí trae un valor: queda sin desplazar ni reescalar.
        val = _make_dummy_graph(x_host=torch.tensor([[2.0, 7.0]]))
        assert scaler.transform_graph(val)["host"].x[0, 1].item() == 7.0

    def test_feature_scaler_must_be_fitted_before_transform(self) -> None:
        with pytest.raises(RuntimeError, match="ajustarse con fit"):
            FeatureScaler().transform_graph(_make_dummy_graph(x_host=torch.tensor([[1.0]])))

    def test_feature_scaler_rejects_graph_with_another_width(self) -> None:
        scaler = FeatureScaler.fit([_make_dummy_graph(x_host=torch.tensor([[1.0, 2.0]]))])
        with pytest.raises(ValueError, match="se esperaban 2 columnas"):
            scaler.transform_graph(_make_dummy_graph(x_host=torch.tensor([[1.0, 2.0, 3.0]])))

    def test_target_scaler_requires_targets_and_matching_statistics(self) -> None:
        with pytest.raises(ValueError, match="targets no puede"):
            TargetScaler(targets=())
        with pytest.raises(ValueError, match="misma longitud"):
            TargetScaler(mean=[1.0, 2.0], std=[1.0, 1.0, 1.0])

    def test_unfitted_target_scaler_raises_instead_of_returning_defaults(self) -> None:
        scaler = TargetScaler()
        assert not scaler.is_fitted
        y = torch.ones((1, 3))
        for call in (
            lambda: scaler.mean,
            lambda: scaler.std,
            lambda: scaler.transform(y),
            lambda: scaler.inverse_transform(y),
        ):
            with pytest.raises(RuntimeError, match="ajusta"):
                call()

    def test_target_scaler_rejects_wrong_width_or_mask_shape(self) -> None:
        with pytest.raises(ValueError, match="se esperaban 3 columnas"):
            TargetScaler.fit(torch.ones((2, 2)))
        with pytest.raises(ValueError, match="Forma de mask"):
            TargetScaler.fit(torch.ones((2, 3)), mask=torch.ones((1, 3), dtype=torch.bool))
        with pytest.raises(ValueError, match="no puede estar vacío"):
            TargetScaler.fit([])

    def test_target_never_measured_in_train_is_neutral(self) -> None:
        y = torch.tensor([[10.0, 1.0, 5.0], [20.0, 2.0, 7.0]])
        mask = torch.tensor([[True, True, False], [True, True, False]])
        scaler = TargetScaler.fit(y, mask=mask)

        assert scaler.observed_count == (2, 2, 0)
        assert (scaler.mean_tuple[2], scaler.std_tuple[2]) == (0.0, 1.0)

    def test_inverse_transform_zeroes_unmeasured_cells(self) -> None:
        """Con máscara, la inversa no inventa una concentración donde no hubo medición."""
        scaler = TargetScaler.fit(torch.tensor([[10.0, 1.0, 5.0], [20.0, 3.0, 9.0]]))
        mask = torch.tensor([[True, False, True]])
        recovered = scaler.inverse_transform(torch.zeros((1, 3)), mask=mask)

        assert recovered[0, 1].item() == 0.0
        assert recovered[0, 0].item() == pytest.approx(15.0)
        assert recovered[0, 2].item() == pytest.approx(7.0)

    def test_scaler_json_strings_round_trip_exactly(self) -> None:
        g = _make_dummy_graph(
            x_host=torch.tensor([[1.0, 2.0], [4.0, 8.0]]),
            y_graph=torch.tensor([[10.0, 1.0, 5.0]]),
        )
        g2 = _make_dummy_graph(
            x_host=torch.tensor([[3.0, 3.0]]), y_graph=torch.tensor([[12.0, 2.0, 6.0]])
        )
        features = FeatureScaler.fit([g, g2])
        targets = TargetScaler.fit([g, g2])

        assert FeatureScaler.from_json(features.to_json()).stats == features.stats
        restored = TargetScaler.from_json(targets.to_json())
        assert restored.mean_tuple == targets.mean_tuple
        assert restored.std_tuple == targets.std_tuple
        assert restored.observed_count == targets.observed_count
