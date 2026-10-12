"""Pruebas unitarias para la consolidación y comparación de baselines (A40-6, #76).

Verifica:
1. `build_comparison_summary`: extracción y consolidación de filas por modelo y split.
2. `format_comparison_table_markdown`: generación de tabla comparativa en formato Markdown.
3. `format_comparison_table_csv`: generación de tabla comparativa en formato CSV.
4. `train_all_baselines`: entrenamiento conjunto de los 5 baselines y reporte consolidado.
5. Validación de errores (incompatibilidad de cv_folds).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nutrigraphdt.models.baselines import (
    ALL_BASELINE_NAMES,
    LinearBaselineConfig,
    TreeBaselineConfig,
    _default_linear_config_path,
    _default_tree_config_path,
    build_comparison_summary,
    build_synthetic_baseline_dataset,
    format_comparison_table_csv,
    format_comparison_table_markdown,
    train_all_baselines,
)
from nutrigraphdt.models.metrics import (
    EvaluationReport,
    MetricRow,
)


def _sample_report() -> EvaluationReport:
    """Reporte sintético simple para pruebas de formato."""
    rows: list[MetricRow] = []
    for model in ("dummy_mean", "ridge", "random_forest"):
        for split in ("val", "test"):
            rows.append(
                MetricRow(
                    model=model,
                    metric="mae",
                    targets={"acetate": 10.0, "propionate": 6.0, "butyrate": 5.0},
                    average=7.0,
                    split=split,
                )
            )
            rows.append(
                MetricRow(
                    model=model,
                    metric="rmse",
                    targets={"acetate": 12.0, "propionate": 7.0, "butyrate": 6.0},
                    average=8.3333,
                    split=split,
                )
            )
            rows.append(
                MetricRow(
                    model=model,
                    metric="r2",
                    targets={"acetate": -0.05, "propionate": 0.10, "butyrate": -0.02},
                    average=0.01,
                    split=split,
                )
            )
            rows.append(
                MetricRow(
                    model=model,
                    metric="negative_pct",
                    targets={"acetate": 0.0, "propionate": 0.0, "butyrate": 0.0},
                    average=0.0,
                    split=split,
                )
            )
    return EvaluationReport(rows=tuple(rows))


def test_build_comparison_summary() -> None:
    """Verifica que el resumen agrupe correctamente por modelo y split."""
    report = _sample_report()
    summary = build_comparison_summary(report)

    # 3 modelos * 2 splits = 6 filas consolidadas
    assert len(summary) == 6
    first = summary[0]
    assert first.model == "dummy_mean"
    assert first.split == "val"
    assert first.mae == 7.0
    assert first.rmse == 8.3333
    assert first.r2 == 0.01
    assert first.negative_pct == 0.0
    assert first.targets_mae["acetate"] == 10.0
    assert first.targets_rmse["propionate"] == 7.0


def test_format_comparison_table_markdown() -> None:
    """Verifica que la salida Markdown contenga las secciones y cabeceras esperadas."""
    report = _sample_report()
    markdown = format_comparison_table_markdown(report, include_targets=True)

    assert "### Promedio macro de los tres AGCC" in markdown
    assert "| Modelo | Split | MAE | RMSE | R² | % Neg |" in markdown
    assert "`dummy_mean`" in markdown
    assert "`ridge`" in markdown
    assert "`random_forest`" in markdown
    assert "### Detalle por objetivo: Acetate" in markdown
    assert "### Detalle por objetivo: Propionate" in markdown
    assert "### Detalle por objetivo: Butyrate" in markdown


def test_format_comparison_table_csv() -> None:
    """Verifica que la salida CSV tenga las columnas y filas esperadas."""
    report = _sample_report()
    csv_text = format_comparison_table_csv(report)
    lines = csv_text.strip().splitlines()

    # Cabecera + 6 filas
    assert len(lines) == 7
    header = lines[0].split(",")
    assert header[:6] == ["model", "split", "mae", "rmse", "r2", "negative_pct"]
    assert "mae_acetate" in header
    assert "rmse_propionate" in header
    assert "r2_butyrate" in header


def test_format_comparison_empty_report() -> None:
    """Verifica el comportamiento seguro con un reporte vacío."""
    empty_report = EvaluationReport(rows=())
    summary = build_comparison_summary(empty_report)
    assert summary == []
    csv_text = format_comparison_table_csv(empty_report)
    assert csv_text == ""
    md_text = format_comparison_table_markdown(empty_report)
    assert "| Modelo | Split |" in md_text


def test_train_all_baselines_reproducible_cohort() -> None:
    """Verifica train_all_baselines sobre una cohorte sintética pequeña."""
    dataset, groups = build_synthetic_baseline_dataset(n_samples=12, first_seed=1, split_seed=42)

    linear_cfg = LinearBaselineConfig(
        ridge_alphas=(10.0,),
        elasticnet_alphas=(1.0,),
        elasticnet_l1_ratios=(0.5,),
        elasticnet_max_iter=1000,
        cv_folds=2,
        scoring="neg_root_mean_squared_error",
    )
    tree_cfg = TreeBaselineConfig(
        random_forest_n_estimators=(10,),
        random_forest_max_depth=(3,),
        random_forest_min_samples_leaf=(1,),
        hist_gradient_boosting_learning_rate=(0.1,),
        hist_gradient_boosting_max_iter=(10,),
        hist_gradient_boosting_max_depth=(3,),
        hist_gradient_boosting_min_samples_leaf=(2,),
        cv_folds=2,
        scoring="neg_root_mean_squared_error",
        random_state=42,
        permutation_repeats=2,
    )

    result = train_all_baselines(dataset, groups, linear_cfg, tree_cfg)

    # Verifica que los 5 modelos estén presentes en el reporte consolidado
    models_in_report = {row.model for row in result.report.rows}
    assert models_in_report == set(ALL_BASELINE_NAMES)

    # Verifica que los parámetros elegidos cubran lineales y árboles
    assert "ridge" in result.best_params
    assert "elasticnet" in result.best_params
    assert "random_forest" in result.best_params
    assert "hist_gradient_boosting" in result.best_params

    # Verifica que existan importancias de atributos para los árboles
    assert "random_forest" in result.feature_importances
    assert "hist_gradient_boosting" in result.feature_importances


def test_train_all_baselines_cv_folds_mismatch() -> None:
    """Rechaza configuraciones con distinto número de folds entre lineales y árboles."""
    dataset, groups = build_synthetic_baseline_dataset(n_samples=10, first_seed=1, split_seed=42)

    linear_cfg = LinearBaselineConfig(
        ridge_alphas=(10.0,),
        elasticnet_alphas=(1.0,),
        elasticnet_l1_ratios=(0.5,),
        elasticnet_max_iter=1000,
        cv_folds=2,
        scoring="neg_root_mean_squared_error",
    )
    tree_cfg = TreeBaselineConfig(
        random_forest_n_estimators=(10,),
        random_forest_max_depth=(3,),
        random_forest_min_samples_leaf=(1,),
        hist_gradient_boosting_learning_rate=(0.1,),
        hist_gradient_boosting_max_iter=(10,),
        hist_gradient_boosting_max_depth=(3,),
        hist_gradient_boosting_min_samples_leaf=(2,),
        cv_folds=3,  # diferente
        scoring="neg_root_mean_squared_error",
        random_state=42,
        permutation_repeats=2,
    )

    with pytest.raises(ValueError, match="cv_folds debe coincidir"):
        train_all_baselines(dataset, groups, linear_cfg, tree_cfg)


def test_default_config_paths_exist_from_different_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifica que las rutas de configuración por defecto se resuelvan desde la raíz
    del repositorio aun cambiando de directorio de trabajo.
    """
    monkeypatch.chdir(tmp_path)
    lin_path = _default_linear_config_path()
    tree_path = _default_tree_config_path()
    assert lin_path.is_file(), f"Linear config no encontrada en {lin_path}"
    assert tree_path.is_file(), f"Tree config no encontrada en {tree_path}"
