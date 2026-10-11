"""Pruebas unitarias para la partición train/val/test sin fuga de datos (A40-1, #71)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest

from nutrigraphdt.data.schema import NormalizedInstanceRecord, NormalizedTabularDataset
from nutrigraphdt.data.split import (
    DEFAULT_DATASET_ID,
    DatasetSplit,
    create_split,
    get_split,
    load_split,
    save_split,
)
from nutrigraphdt.models.split import get_split as models_get_split

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "holofood"
METADATA_FIXTURE = FIXTURES / "metadata.tsv"


def test_get_split_returns_identical_partition_across_executions() -> None:
    """Criterio de aceptación: La partición es idéntica entre ejecuciones."""
    split1 = get_split()
    split2 = get_split()
    models_split = models_get_split()

    assert split1.train == split2.train
    assert split1.val == split2.val
    assert split1.test == split2.test
    assert split1.groups == split2.groups
    assert split1.seed == split2.seed

    # La versión expuesta a través de nutrigraphdt.models debe ser exactamente idéntica
    assert split1.train == models_split.train
    assert split1.val == models_split.val
    assert split1.test == models_split.test


def test_subsets_are_mutually_disjoint() -> None:
    """Criterio de aceptación: Ningún animal o muestra aparece en más de un subconjunto."""
    split = get_split()

    train_set = set(split.train)
    val_set = set(split.val)
    test_set = set(split.test)

    assert train_set.isdisjoint(val_set), f"Intersección train-val: {train_set & val_set}"
    assert train_set.isdisjoint(test_set), f"Intersección train-test: {train_set & test_set}"
    assert val_set.isdisjoint(test_set), f"Intersección val-test: {val_set & test_set}"

    # Verificación de que no estén vacíos
    assert len(split.train) > 0
    assert len(split.val) > 0
    assert len(split.test) > 0


def test_no_group_or_pen_leakage() -> None:
    """Verifica que ningún corral (pen_code) esté repartido en más de un subconjunto."""
    split = get_split()

    g_train = set(split.groups.get("train", ()))
    g_val = set(split.groups.get("val", ()))
    g_test = set(split.groups.get("test", ()))

    assert len(g_train) > 0
    assert len(g_val) > 0
    assert len(g_test) > 0

    assert g_train.isdisjoint(g_val), f"Corrales compartidos train-val: {g_train & g_val}"
    assert g_train.isdisjoint(g_test), f"Corrales compartidos train-test: {g_train & g_test}"
    assert g_val.isdisjoint(g_test), f"Corrales compartidos val-test: {g_val & g_test}"


def test_all_samples_from_source_are_accounted_for() -> None:
    """Verifica que todas las muestras del archivo de metadatos estén en la partición."""
    with METADATA_FIXTURE.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        expected_samples = {row["sample_id"] for row in reader}

    split = get_split()
    all_split_samples = set(split.train) | set(split.val) | set(split.test)

    assert all_split_samples == expected_samples
    assert len(split) == len(expected_samples)
    assert set(split.all_samples) == expected_samples


def test_stratification_preserves_diet_treatments() -> None:
    """Verifica que los tratamientos presentes en D1 HoloFood se conserven en train."""
    with METADATA_FIXTURE.open(encoding="utf-8") as handle:
        rows = {
            row["sample_id"]: row["diet_treatment_code"]
            for row in csv.DictReader(handle, delimiter="\t")
        }

    split = get_split()
    train_treatments = {rows[s] for s in split.train}

    # Los tres tratamientos del fixture (CC: Control, CO: Probiotic, CE: Prebiotic)
    assert {"CC", "CO", "CE"} <= train_treatments


def test_tolerance_to_small_groups_and_singletons() -> None:
    """Verifica que la estratificación tolere grupos pequeños (1, 2 o 3 corrales) sin fallar."""
    synthetic_records: list[dict[str, Any]] = [
        # Estrato A: 1 solo corral
        {"sample_id": "S1", "pen_code": "P1", "diet_treatment_code": "T_SINGLE"},
        # Estrato B: 2 corrales
        {"sample_id": "S2", "pen_code": "P2", "diet_treatment_code": "T_PAIR"},
        {"sample_id": "S3", "pen_code": "P3", "diet_treatment_code": "T_PAIR"},
        # Estrato C: 3 corrales
        {"sample_id": "S4", "pen_code": "P4", "diet_treatment_code": "T_TRIO"},
        {"sample_id": "S5", "pen_code": "P5", "diet_treatment_code": "T_TRIO"},
        {"sample_id": "S6", "pen_code": "P6", "diet_treatment_code": "T_TRIO"},
        # Estrato D: 5 corrales con varias muestras por corral
        {"sample_id": "S7", "pen_code": "P7", "diet_treatment_code": "T_MULTI"},
        {"sample_id": "S8", "pen_code": "P7", "diet_treatment_code": "T_MULTI"},
        {"sample_id": "S9", "pen_code": "P8", "diet_treatment_code": "T_MULTI"},
        {"sample_id": "S10", "pen_code": "P9", "diet_treatment_code": "T_MULTI"},
        {"sample_id": "S11", "pen_code": "P10", "diet_treatment_code": "T_MULTI"},
        {"sample_id": "S12", "pen_code": "P11", "diet_treatment_code": "T_MULTI"},
    ]

    split = create_split(synthetic_records, seed=123)

    # Debe ser completamente válido y sin fugas
    split.validate()
    assert set(split.train).isdisjoint(set(split.val))
    assert set(split.train).isdisjoint(set(split.test))
    assert set(split.val).isdisjoint(set(split.test))
    assert len(split) == 12

    # El corral P7 tiene 2 muestras (S7 y S8): ambas deben estar en el mismo subconjunto
    s7_sub = split.subset_of("S7")
    s8_sub = split.subset_of("S8")
    assert s7_sub is not None
    assert s7_sub == s8_sub


def test_fixed_seed_reproducibility() -> None:
    """Verifica reproducibilidad estricta con la misma semilla y variación con distinta."""
    records = [
        {"sample_id": f"S{i}", "pen_code": f"P{i // 2}", "diet_treatment_code": f"T{i % 3}"}
        for i in range(30)
    ]

    split_a = create_split(records, seed=42)
    split_b = create_split(records, seed=42)
    split_c = create_split(records, seed=999)

    assert split_a.train == split_b.train
    assert split_a.val == split_b.val
    assert split_a.test == split_b.test

    # Con 30 registros, una semilla diferente debe producir un orden distinto
    assert split_a.train != split_c.train or split_a.test != split_c.test


def test_dataset_split_ergonomics() -> None:
    """Prueba la interfaz ergonómica: desempaquetado, indexación, máscaras y filtros."""
    split = get_split()

    # 1. Desempaquetado como tupla
    train_tuple, val_tuple, test_tuple = split
    assert train_tuple == split.train
    assert val_tuple == split.val
    assert test_tuple == split.test

    # 2. Acceso por clave
    assert split["train"] == split.train
    assert split["val"] == split.val
    assert split["test"] == split.test
    with pytest.raises(KeyError):
        _ = split["unknown_split"]

    # 3. subset_of
    first_train = split.train[0]
    assert split.subset_of(first_train) == "train"
    assert split.subset_of("NONEXISTENT_SAMPLE") is None

    # 4. Máscaras booleanas
    sample_list = [split.train[0], split.val[0], split.test[0]]
    masks = split.mask(sample_list)
    assert masks["train"] == [True, False, False]
    assert masks["val"] == [False, True, False]
    assert masks["test"] == [False, False, True]

    # 5. Filtrado de mapeo con prefijos de grafo (ej. 'D1_holofood:SAMEA...')
    mapping_data = {f"D1_holofood:{s}": f"data_{s}" for s in split.all_samples}
    tr_map, va_map, te_map = split.filter(mapping_data)
    assert isinstance(tr_map, dict)
    assert len(tr_map) == len(split.train)
    assert len(va_map) == len(split.val)
    assert len(te_map) == len(split.test)

    # 6. Filtrado de secuencias con key_fn
    class Item:
        def __init__(self, sid: str) -> None:
            self.sid = sid

    items = [Item(s) for s in split.all_samples]
    tr_items, va_items, te_items = split.filter(items, key_fn=lambda x: x.sid)
    assert isinstance(tr_items, list)
    assert len(tr_items) == len(split.train)


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    """Verifica que serializar y deserializar conserve la partición exacta."""
    original = get_split()
    target_path = tmp_path / "custom_split.json"

    saved_path = save_split(original, target_path)
    assert saved_path == target_path
    assert target_path.exists()

    loaded = load_split(target_path)
    assert loaded.train == original.train
    assert loaded.val == original.val
    assert loaded.test == original.test
    assert loaded.groups == original.groups
    assert loaded.dataset_id == original.dataset_id
    assert loaded.seed == original.seed
    assert loaded.ratios == original.ratios
    assert loaded.metadata == original.metadata


def test_validation_detects_data_leakage() -> None:
    """Verifica que `validate()` lance ValueError si hay fugas simuladas."""
    # Fuga de muestras
    with pytest.raises(ValueError, match="Fuga detectada.*compartidas entre train y val"):
        DatasetSplit(
            train=("SAMEA1", "SAMEA2"),
            val=("SAMEA2", "SAMEA3"),
            test=("SAMEA4",),
        )

    # Fuga de corrales/grupos
    with pytest.raises(ValueError, match="Fuga de grupos detectada"):
        DatasetSplit(
            train=("SAMEA1",),
            val=("SAMEA2",),
            test=("SAMEA3",),
            groups={"train": ("PEN1",), "val": ("PEN1",), "test": ("PEN2",)},
        )


def test_invalid_ratios_and_inputs() -> None:
    """Verifica validación de parámetros de entrada."""
    with pytest.raises(ValueError, match="Los ratios deben sumar 1.0"):
        create_split([{"sample_id": "S1"}], ratios=(0.5, 0.2, 0.2))

    with pytest.raises(ValueError, match="Los ratios no pueden ser negativos"):
        create_split([{"sample_id": "S1"}], ratios=(1.2, -0.1, -0.1))

    with pytest.raises(ValueError, match="No se proporcionaron registros"):
        create_split([])


def test_extract_records_from_normalized_tabular_dataset() -> None:
    """Verifica que create_split acepte directamente un NormalizedTabularDataset."""
    dataset = NormalizedTabularDataset(
        metadata={"dataset_id": DEFAULT_DATASET_ID},
        instances=[
            NormalizedInstanceRecord(
                graph_id=f"g:{i}",
                sample_id=f"SAMEA_{i}",
                species="chicken",
                gut_segment="cecum",
                study_id="CA",
                scenario_id="observed",
                timepoint=str(i),
                diet_treatment="CC" if i % 2 == 0 else "CO",
            )
            for i in range(10)
        ],
    )
    split = create_split(dataset, group_key=None, stratify_key="diet_treatment", seed=42)
    assert len(split) == 10
    split.validate()
