"""Pruebas de integración del pipeline tabular (A40-3).

Verifica que el flujo completo de construcción tabular interopere con:
1. El pipeline de datos preprocesados de D1 HoloFood (`attach_sample_context`).
2. La partición canónica train/val/test sin fuga de datos (`get_split()`).
3. La generación de matrices de entrenamiento y validación listas para baselines (A40-4, A40-5).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from nutrigraphdt.data.config import load_sources
from nutrigraphdt.data.integration import attach_sample_context
from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader
from nutrigraphdt.data.pipeline import DataPipeline
from nutrigraphdt.data.split import get_split
from nutrigraphdt.data.synthetic import generate_scenario_dataset
from nutrigraphdt.models.tabular import (
    CANONICAL_TARGETS,
    build_tabular_dataset,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "holofood"
SOURCES = load_sources(REPO_ROOT / "configs" / "sources.json")


def _source(source_id: str, file_name: str):  # type: ignore[no-untyped-def]
    return dataclasses.replace(SOURCES[source_id], path_or_url=str(FIXTURES / file_name))


def test_tabular_pipeline_integration_holofood_and_split() -> None:
    """Valida la integración integral de D1 HoloFood con la partición A40-1."""
    # 1. Pipeline de ingesta y contexto
    abundance = _source("D1_holofood", "abundance_ssu_caecum.tsv")
    tables = DataPipeline({"D1_holofood": abundance}).run(["D1_holofood"]).dataset
    tables, report = attach_sample_context(
        tables,
        metadata=MetadataLoader(_source("D1_holofood_metadata", "metadata.tsv")).load(),
        metabolites=MetaboliteLoader(
            _source("D1_holofood_scfa_content", "scfa_caecum_content.tsv")
        ).load(),
    )
    assert report.instances_with_context == 6

    # 2. Construcción tabular con partición versionada
    split = get_split()
    dataset = build_tabular_dataset(tables, split=split)

    assert len(dataset) == 6
    assert dataset.target_names == ("acetate", "propionate", "butyrate")

    # 3. Obtención de matrices numéricas por partición
    X_train, y_train = dataset.get_split_matrices("train", numeric=True, one_hot=True)
    X_val, y_val = dataset.get_split_matrices("val", numeric=True, one_hot=True)
    X_test, y_test = dataset.get_split_matrices("test", numeric=True, one_hot=True)

    # Dimensiones esperadas
    assert len(X_train) == 3
    assert len(y_train) == 3
    assert len(X_val) == 2
    assert len(y_val) == 2
    assert len(X_test) == 1
    assert len(y_test) == 1

    # Cada fila de y tiene exactamente 3 componentes (acetato, propionato, butirato)
    for y_row in y_train + y_val + y_test:
        assert len(y_row) == 3
        assert all(val > 0.0 for val in y_row)

    # Cada fila de X tiene idéntica dimensión de atributos y valores finitos
    feature_dim = len(X_train[0])
    for x_row in X_train + X_val + X_test:
        assert len(x_row) == feature_dim
        assert all(isinstance(v, (int, float)) for v in x_row)


def test_tabular_pipeline_integration_synthetic() -> None:
    """Valida la integración con el dataset sintético multiescenario."""
    synthetic_ds = generate_scenario_dataset()
    tab_ds = build_tabular_dataset(synthetic_ds)

    assert len(tab_ds) == 2
    cols, X_mat = tab_ds.to_numeric_matrix(one_hot=True)

    assert len(X_mat) == 2
    assert len(cols) == len(X_mat[0])
    assert tab_ds.target_names == CANONICAL_TARGETS

    # Comprobar que los targets coinciden con los valores fijados en el escenario
    y = tab_ds.y
    assert len(y) == 2
    for y_row in y:
        assert y_row[0] == 65.07  # acetato
        assert y_row[1] == 22.358  # propionato
        assert y_row[2] == 14.649  # butirato
