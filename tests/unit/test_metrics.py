"""Tests unitarios del módulo de métricas de evaluación (A40-2).

Verifica cálculos con valores conocidos calculados a mano, soporte para AGCC
(acetato, propionato, butirato) y promedio agregado, porcentaje de predicciones
negativas y formato de salida común (una fila por modelo y métrica).
"""

from __future__ import annotations

import math

import pytest

from nutrigraphdt.models.metrics import (
    DEFAULT_SCFA_TARGETS,
    combine_reports,
    evaluate_predictions,
    mean_absolute_error,
    negative_prediction_percentage,
    r2_score,
    root_mean_squared_error,
)


class TestHandCalculatedMetrics:
    """Pruebas con valores de referencia exactos calculados a mano."""

    def test_acetate_hand_calculated(self) -> None:
        """Verifica métricas para el vector de acetato calculado a mano.

        y_true = [10.0, 20.0, 30.0, 40.0]
        y_pred = [12.0, 18.0, 33.0, 35.0]
        Errores: [+2.0, -2.0, +3.0, -5.0]
        MAE: (2 + 2 + 3 + 5) / 4 = 12 / 4 = 3.0
        MSE: (4 + 4 + 9 + 25) / 4 = 42 / 4 = 10.5
        RMSE: sqrt(10.5) ~ 3.2403703492...
        SS_tot: (-15)^2 + (-5)^2 + (+5)^2 + (+15)^2 = 225 + 25 + 25 + 225 = 500.0
        R2: 1 - 42.0 / 500.0 = 1 - 0.084 = 0.916
        Negative pct: 0 / 4 = 0.0%
        """
        y_true = [10.0, 20.0, 30.0, 40.0]
        y_pred = [12.0, 18.0, 33.0, 35.0]

        mae = mean_absolute_error(y_true, y_pred)
        rmse = root_mean_squared_error(y_true, y_pred)
        r2 = r2_score(y_true, y_pred)
        neg_pct = negative_prediction_percentage(y_pred)

        assert mae == pytest.approx(3.0, rel=1e-6)
        assert rmse == pytest.approx(math.sqrt(10.5), rel=1e-6)
        assert r2 == pytest.approx(0.916, rel=1e-6)
        assert neg_pct == pytest.approx(0.0)

    def test_propionate_hand_calculated_with_negative_prediction(self) -> None:
        """Verifica métricas para propionato conteniendo una predicción negativa.

        y_true = [5.0, 10.0, 15.0, 20.0]
        y_pred = [4.0, 12.0, 11.0, -1.0]
        Errores: [-1.0, +2.0, -4.0, -21.0]
        MAE: (1 + 2 + 4 + 21) / 4 = 28 / 4 = 7.0
        MSE: (1 + 4 + 16 + 441) / 4 = 462 / 4 = 115.5
        RMSE: sqrt(115.5) ~ 10.7470926...
        SS_tot: (-7.5)^2 + (-2.5)^2 + (+2.5)^2 + (+7.5)^2 = 56.25 + 6.25 + 6.25 + 56.25 = 125.0
        R2: 1 - 462 / 125 = 1 - 3.696 = -2.696
        Negative pct: 1 / 4 = 25.0%
        """
        y_true = [5.0, 10.0, 15.0, 20.0]
        y_pred = [4.0, 12.0, 11.0, -1.0]

        mae = mean_absolute_error(y_true, y_pred)
        rmse = root_mean_squared_error(y_true, y_pred)
        r2 = r2_score(y_true, y_pred)
        neg_pct = negative_prediction_percentage(y_pred)

        assert mae == pytest.approx(7.0, rel=1e-6)
        assert rmse == pytest.approx(math.sqrt(115.5), rel=1e-6)
        assert r2 == pytest.approx(-2.696, rel=1e-6)
        assert neg_pct == pytest.approx(25.0, rel=1e-6)

    def test_butyrate_hand_calculated(self) -> None:
        """Verifica métricas para butirato.

        y_true = [2.0, 4.0, 6.0, 8.0]
        y_pred = [1.0, 5.0, 7.0, 7.0]
        Errores: [-1.0, +1.0, +1.0, -1.0]
        MAE: 4 / 4 = 1.0
        MSE: 4 / 4 = 1.0
        RMSE: 1.0
        SS_tot: (-3)^2 + (-1)^2 + (+1)^2 + (+3)^2 = 9 + 1 + 1 + 9 = 20.0
        R2: 1 - 4 / 20 = 1 - 0.2 = 0.8
        Negative pct: 0 / 4 = 0.0%
        """
        y_true = [2.0, 4.0, 6.0, 8.0]
        y_pred = [1.0, 5.0, 7.0, 7.0]

        mae = mean_absolute_error(y_true, y_pred)
        rmse = root_mean_squared_error(y_true, y_pred)
        r2 = r2_score(y_true, y_pred)
        neg_pct = negative_prediction_percentage(y_pred)

        assert mae == pytest.approx(1.0, rel=1e-6)
        assert rmse == pytest.approx(1.0, rel=1e-6)
        assert r2 == pytest.approx(0.8, rel=1e-6)
        assert neg_pct == pytest.approx(0.0)

    def test_perfect_prediction(self) -> None:
        """Predicción idéntica debe resultar en MAE=0, RMSE=0, R2=1.0, neg_pct=0."""
        y = [1.0, 2.5, 3.8, 4.2]
        assert mean_absolute_error(y, y) == pytest.approx(0.0)
        assert root_mean_squared_error(y, y) == pytest.approx(0.0)
        assert r2_score(y, y) == pytest.approx(1.0)
        assert negative_prediction_percentage(y) == pytest.approx(0.0)

    def test_dummy_mean_prediction(self) -> None:
        """Predicción constante igual a la media empírica tiene R2=0."""
        y_true = [1.0, 2.0, 3.0, 4.0]  # media = 2.5
        y_pred = [2.5, 2.5, 2.5, 2.5]

        # MAE: (|1-2.5| + |2-2.5| + |3-2.5| + |4-2.5|) / 4 = (1.5 + 0.5 + 0.5 + 1.5)/4 = 1.0
        assert mean_absolute_error(y_true, y_pred) == pytest.approx(1.0)
        # MSE: (2.25 + 0.25 + 0.25 + 2.25) / 4 = 5.0 / 4 = 1.25 -> RMSE = sqrt(1.25)
        assert root_mean_squared_error(y_true, y_pred) == pytest.approx(math.sqrt(1.25))
        assert r2_score(y_true, y_pred) == pytest.approx(0.0)


class TestNegativePredictionPercentage:
    """Pruebas específicas para la métrica de violación de no-negatividad."""

    def test_all_negative(self) -> None:
        y_pred = [-1.0, -0.5, -100.0]
        assert negative_prediction_percentage(y_pred) == pytest.approx(100.0)

    def test_none_negative(self) -> None:
        # Cero exacto no es negativo biológicamente
        y_pred = [0.0, 1.2, 5.0]
        assert negative_prediction_percentage(y_pred) == pytest.approx(0.0)

    def test_half_negative(self) -> None:
        y_pred = [1.0, -1.0, 2.0, -2.0]
        assert negative_prediction_percentage(y_pred) == pytest.approx(50.0)

    def test_empty_vector_raises(self) -> None:
        with pytest.raises(ValueError, match="no puede estar vacío"):
            negative_prediction_percentage([])


class TestEdgeCasesAndValidation:
    """Pruebas de casos borde y validación de tipos y tamaños."""

    def test_constant_y_true(self) -> None:
        """Si y_true es constante, SS_tot == 0.

        Si y_pred coincide exactamente, R2 = 1.0; en caso contrario, R2 = 0.0.
        """
        assert r2_score([5.0, 5.0, 5.0], [5.0, 5.0, 5.0]) == pytest.approx(1.0)
        assert r2_score([5.0, 5.0, 5.0], [6.0, 6.0, 6.0]) == pytest.approx(0.0)

    def test_single_sample(self) -> None:
        """Con N=1, MAE y RMSE son el error absoluto; R2 es 1.0 si coincide, 0.0 si no."""
        assert mean_absolute_error([10.0], [12.0]) == pytest.approx(2.0)
        assert root_mean_squared_error([10.0], [12.0]) == pytest.approx(2.0)
        assert r2_score([10.0], [10.0]) == pytest.approx(1.0)
        assert r2_score([10.0], [12.0]) == pytest.approx(0.0)

    def test_length_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="Longitud incompatible"):
            mean_absolute_error([1.0, 2.0], [1.0])

    def test_empty_vectors_raise(self) -> None:
        with pytest.raises(ValueError, match="no pueden estar vacíos"):
            mean_absolute_error([], [])

    def test_non_finite_values_raise(self) -> None:
        with pytest.raises(ValueError, match="no finito"):
            mean_absolute_error([1.0, float("nan")], [1.0, 2.0])

        with pytest.raises(ValueError, match="no finito"):
            root_mean_squared_error([1.0, 2.0], [float("inf"), 2.0])


class TestEvaluatePredictionsCommonFormat:
    """Pruebas del formato común de salida y agregación (A40-2)."""

    def test_evaluate_predictions_dict_input(self) -> None:
        """Evalúa un diccionario por target y comprueba las filas y macro-promedios."""
        y_true = {
            "acetate": [10.0, 20.0, 30.0, 40.0],
            "propionate": [5.0, 10.0, 15.0, 20.0],
            "butyrate": [2.0, 4.0, 6.0, 8.0],
        }
        y_pred = {
            "acetate": [12.0, 18.0, 33.0, 35.0],
            "propionate": [4.0, 12.0, 11.0, -1.0],
            "butyrate": [1.0, 5.0, 7.0, 7.0],
        }

        report = evaluate_predictions(
            y_true=y_true,
            y_pred=y_pred,
            model_name="Ridge",
            split="test",
        )

        assert len(report.rows) == 4
        # Comprobar nombres de métricas requeridas
        metric_names = [r.metric for r in report.rows]
        assert metric_names == ["mae", "rmse", "r2", "negative_pct"]

        # 1. MAE
        row_mae = report.get_row("mae")
        assert row_mae is not None
        assert row_mae.model == "Ridge"
        assert row_mae.split == "test"
        assert row_mae.acetate == pytest.approx(3.0)
        assert row_mae.propionate == pytest.approx(7.0)
        assert row_mae.butyrate == pytest.approx(1.0)
        assert row_mae.average == pytest.approx((3.0 + 7.0 + 1.0) / 3.0)

        # 2. RMSE
        row_rmse = report.get_row("rmse")
        assert row_rmse is not None
        assert row_rmse.acetate == pytest.approx(math.sqrt(10.5))
        assert row_rmse.propionate == pytest.approx(math.sqrt(115.5))
        assert row_rmse.butyrate == pytest.approx(1.0)
        expected_rmse_avg = (math.sqrt(10.5) + math.sqrt(115.5) + 1.0) / 3.0
        assert row_rmse.average == pytest.approx(expected_rmse_avg)

        # 3. R2
        row_r2 = report.get_row("r2")
        assert row_r2 is not None
        assert row_r2.acetate == pytest.approx(0.916)
        assert row_r2.propionate == pytest.approx(-2.696)
        assert row_r2.butyrate == pytest.approx(0.8)
        assert row_r2.average == pytest.approx((0.916 - 2.696 + 0.8) / 3.0)

        # 4. Negative prediction percentage
        row_neg = report.get_row("negative_pct")
        assert row_neg is not None
        assert row_neg.acetate == pytest.approx(0.0)
        assert row_neg.propionate == pytest.approx(25.0)
        assert row_neg.butyrate == pytest.approx(0.0)
        assert row_neg.average == pytest.approx(25.0 / 3.0)

    def test_evaluate_predictions_2d_matrix_input(self) -> None:
        """Verifica que entradas matriciales 2D (N, 3) produzcan el mismo resultado."""
        y_true_mat = [
            [10.0, 5.0, 2.0],
            [20.0, 10.0, 4.0],
            [30.0, 15.0, 6.0],
            [40.0, 20.0, 8.0],
        ]
        y_pred_mat = [
            [12.0, 4.0, 1.0],
            [18.0, 12.0, 5.0],
            [33.0, 11.0, 7.0],
            [35.0, -1.0, 7.0],
        ]

        report = evaluate_predictions(
            y_true=y_true_mat,
            y_pred=y_pred_mat,
            model_name="GNN_Hetero",
            targets=DEFAULT_SCFA_TARGETS,
        )

        row_mae = report.get_row("mae")
        assert row_mae is not None
        assert row_mae.acetate == pytest.approx(3.0)
        assert row_mae.propionate == pytest.approx(7.0)
        assert row_mae.butyrate == pytest.approx(1.0)
        assert row_mae.average == pytest.approx((3.0 + 7.0 + 1.0) / 3.0)

    def test_to_records_one_row_per_model_and_metric(self) -> None:
        """Verifica el formato tabular plano: una fila por modelo y métrica."""
        report = evaluate_predictions(
            y_true={"acetate": [10.0, 20.0], "propionate": [5.0, 10.0], "butyrate": [2.0, 4.0]},
            y_pred={"acetate": [10.0, 20.0], "propionate": [5.0, 10.0], "butyrate": [2.0, 4.0]},
            model_name="BaselineDummy",
            split="val",
        )

        records = report.to_records()
        assert len(records) == 4
        first_row = records[0]
        assert first_row["model"] == "BaselineDummy"
        assert first_row["split"] == "val"
        assert first_row["metric"] == "mae"
        assert first_row["acetate"] == 0.0
        assert first_row["propionate"] == 0.0
        assert first_row["butyrate"] == 0.0
        assert first_row["average"] == 0.0

    def test_markdown_and_csv_export(self) -> None:
        """Verifica la exportación a Markdown y CSV del reporte."""
        report = evaluate_predictions(
            y_true={"acetate": [10.0], "propionate": [5.0], "butyrate": [2.0]},
            y_pred={"acetate": [12.0], "propionate": [4.0], "butyrate": [1.0]},
            model_name="ElasticNet",
            split="test",
        )

        md = report.to_markdown()
        assert "| model | split | metric | acetate | propionate | butyrate | average |" in md
        assert "ElasticNet" in md
        assert "mae" in md

        csv_text = report.to_csv()
        assert "model,split,metric,acetate,propionate,butyrate,average" in csv_text
        assert "ElasticNet,test,mae" in csv_text

    def test_combine_reports(self) -> None:
        """Verifica la consolidación de reportes de múltiples modelos."""
        y_true = {"acetate": [10.0], "propionate": [5.0], "butyrate": [2.0]}
        y_dummy = {"acetate": [10.0], "propionate": [5.0], "butyrate": [2.0]}
        y_ridge = {"acetate": [11.0], "propionate": [6.0], "butyrate": [3.0]}

        rep1 = evaluate_predictions(y_true, y_dummy, model_name="Dummy")
        rep2 = evaluate_predictions(y_true, y_ridge, model_name="Ridge")

        combined = combine_reports([rep1, rep2])
        assert len(combined.rows) == 8

        row_dummy_mae = combined.get_row("mae", model="Dummy")
        row_ridge_mae = combined.get_row("mae", model="Ridge")
        assert row_dummy_mae is not None and row_dummy_mae.average == pytest.approx(0.0)
        assert row_ridge_mae is not None and row_ridge_mae.average == pytest.approx(1.0)

    def test_missing_target_key_raises(self) -> None:
        with pytest.raises(KeyError, match="El target 'butyrate' no se encuentra"):
            evaluate_predictions(
                y_true={"acetate": [1.0], "propionate": [2.0]},
                y_pred={"acetate": [1.0], "propionate": [2.0], "butyrate": [3.0]},
                model_name="Model",
            )
