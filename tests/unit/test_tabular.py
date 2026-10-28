"""Tests unitarios del módulo de tablas de atributos tabulares (A40-3).

Verifica la construcción de tablas de atributos para modelos no basados en grafos:
- Extracción de abundancias, dieta, aditivos y variables del huésped.
- Extracción de objetivos: acetato, propionato y butirato.
- Integración exacta de la partición train/val/test de A40-1.
- Auditoría estricta de ausencia de fuga de datos (no target leakage).
- Conversión a matrices numéricas para baselines.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from nutrigraphdt.data.config import load_sources
from nutrigraphdt.data.integration import attach_sample_context
from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader
from nutrigraphdt.data.pipeline import DataPipeline
from nutrigraphdt.data.schema import (
    NormalizedFeatureRecord,
    NormalizedInstanceRecord,
    NormalizedTabularDataset,
    NormalizedTargetRecord,
)
from nutrigraphdt.data.split import DatasetSplit, get_split
from nutrigraphdt.data.synthetic import generate_scenario_dataset
from nutrigraphdt.models.tabular import (
    CANONICAL_TARGETS,
    TabularDataset,
    TabularSample,
    _canonicalize_target_name,
    build_tabular_dataset,
    build_tabular_from_holofood,
    build_tabular_from_synthetic,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "holofood"
SOURCES = load_sources(REPO_ROOT / "configs" / "sources.json")


def _source(source_id: str, file_name: str):  # type: ignore[no-untyped-def]
    return dataclasses.replace(SOURCES[source_id], path_or_url=str(FIXTURES / file_name))


class TestHandCalculatedTabularDataset:
    """Prueba con datos sintéticos mínimos conocidos calculados a mano."""

    def test_minimal_known_values(self) -> None:
        """Verifica una tabla mínima con valores exactos definidos a mano."""
        # 1. Crear dataset normalizado mínimo con 2 animales
        instances = [
            NormalizedInstanceRecord(
                graph_id="inst_01",
                sample_id="SAMPLE_A",
                species="chicken",
                gut_segment="cecum",
                study_id="STUDY_1",
                scenario_id="observed",
                diet_treatment="Diet_X",
                timepoint="35",
            ),
            NormalizedInstanceRecord(
                graph_id="inst_02",
                sample_id="SAMPLE_B",
                species="chicken",
                gut_segment="cecum",
                study_id="STUDY_1",
                scenario_id="observed",
                diet_treatment="Diet_Y",
                timepoint="35",
            ),
        ]

        features = [
            # Abundancias taxonómicas
            NormalizedFeatureRecord(
                graph_id="inst_01",
                node_id="taxon_bacteroides",
                node_type="taxon",
                feature_name="abundance",
                value=0.25,
                unit="relative_abundance",
            ),
            NormalizedFeatureRecord(
                graph_id="inst_02",
                node_id="taxon_bacteroides",
                node_type="taxon",
                feature_name="abundance",
                value=0.40,
                unit="relative_abundance",
            ),
            NormalizedFeatureRecord(
                graph_id="inst_01",
                node_id="taxon_lactobacillus",
                node_type="taxon",
                feature_name="abundance",
                value=0.15,
                unit="relative_abundance",
            ),
            NormalizedFeatureRecord(
                graph_id="inst_02",
                node_id="taxon_lactobacillus",
                node_type="taxon",
                feature_name="abundance",
                value=0.05,
                unit="relative_abundance",
            ),
            # Covariables del huésped
            NormalizedFeatureRecord(
                graph_id="inst_01",
                node_id="SAMPLE_A:host",
                node_type="host",
                feature_name="body_weight_g",
                value=1250.0,
                unit="g",
            ),
            NormalizedFeatureRecord(
                graph_id="inst_02",
                node_id="SAMPLE_B:host",
                node_type="host",
                feature_name="body_weight_g",
                value=1300.0,
                unit="g",
            ),
        ]

        targets = [
            # Muestra A
            NormalizedTargetRecord(
                graph_id="inst_01",
                target_type="scfa_concentration",
                target_id="acetate",
                value=50.0,
                unit="mmol_kg",
                sample_matrix="cecal_content",
                measured_or_predicted="measured",
            ),
            NormalizedTargetRecord(
                graph_id="inst_01",
                target_type="scfa_concentration",
                target_id="propionate",
                value=20.0,
                unit="mmol_kg",
                sample_matrix="cecal_content",
                measured_or_predicted="measured",
            ),
            NormalizedTargetRecord(
                graph_id="inst_01",
                target_type="scfa_concentration",
                target_id="butyrate",
                value=10.0,
                unit="mmol_kg",
                sample_matrix="cecal_content",
                measured_or_predicted="measured",
            ),
            # Muestra B
            NormalizedTargetRecord(
                graph_id="inst_02",
                target_type="scfa_concentration",
                target_id="acetate",
                value=60.0,
                unit="mmol_kg",
                sample_matrix="cecal_content",
                measured_or_predicted="measured",
            ),
            NormalizedTargetRecord(
                graph_id="inst_02",
                target_type="scfa_concentration",
                target_id="propionate",
                value=25.0,
                unit="mmol_kg",
                sample_matrix="cecal_content",
                measured_or_predicted="measured",
            ),
            NormalizedTargetRecord(
                graph_id="inst_02",
                target_type="scfa_concentration",
                target_id="butyrate",
                value=15.0,
                unit="mmol_kg",
                sample_matrix="cecal_content",
                measured_or_predicted="measured",
            ),
        ]

        norm_ds = NormalizedTabularDataset(
            instances=instances,
            features=features,
            targets=targets,
        )

        split = DatasetSplit(
            train=("SAMPLE_A",),
            val=("SAMPLE_B",),
            test=(),
        )

        tab_ds = build_tabular_from_holofood(norm_ds, split=split)

        assert len(tab_ds) == 2
        assert tab_ds.sample_ids == ("SAMPLE_A", "SAMPLE_B")
        assert tab_ds.target_names == CANONICAL_TARGETS

        # Comprobar atributos esperados
        # Contrato v2 §3 (#147): body_weight_g se informa en el host, pero no es entrada.
        expected_features = (
            "diet:treatment",
            "taxon:taxon_bacteroides",
            "taxon:taxon_lactobacillus",
        )
        assert tab_ds.feature_names == expected_features

        # Comprobar muestra A
        sample_a = tab_ds.samples[0]
        assert sample_a.sample_id == "SAMPLE_A"
        assert sample_a.split == "train"
        assert sample_a.features["diet:treatment"] == "Diet_X"
        assert "host:body_weight_g" not in sample_a.features
        assert sample_a.features["taxon:taxon_bacteroides"] == 0.25
        assert sample_a.features["taxon:taxon_lactobacillus"] == 0.15
        assert sample_a.acetate == 50.0
        assert sample_a.propionate == 20.0
        assert sample_a.butyrate == 10.0

        # Comprobar muestra B
        sample_b = tab_ds.samples[1]
        assert sample_b.sample_id == "SAMPLE_B"
        assert sample_b.split == "val"
        assert sample_b.features["diet:treatment"] == "Diet_Y"
        assert "host:body_weight_g" not in sample_b.features
        assert sample_b.features["taxon:taxon_bacteroides"] == 0.40
        assert sample_b.features["taxon:taxon_lactobacillus"] == 0.05
        assert sample_b.acetate == 60.0
        assert sample_b.propionate == 25.0
        assert sample_b.butyrate == 15.0

        # Comprobar matriz numérica con One-Hot Encoding
        cols, X_num = tab_ds.to_numeric_matrix(one_hot=True)
        assert "host:body_weight_g" not in cols
        assert "taxon:taxon_bacteroides" in cols
        assert "diet:treatment=Diet_X" in cols
        assert "diet:treatment=Diet_Y" in cols
        assert len(X_num) == 2

        # Subconjunto train y val disjuntos
        train_ds = tab_ds.train_dataset
        val_ds = tab_ds.val_dataset
        assert len(train_ds) == 1
        assert len(val_ds) == 1
        assert train_ds.sample_ids == ("SAMPLE_A",)
        assert val_ds.sample_ids == ("SAMPLE_B",)


class TestTargetLeakageAudit:
    """Verifica que el detector de fuga de datos rechace cualquier objetivo en los atributos."""

    def test_direct_target_name_in_features_raises(self) -> None:
        sample = TabularSample(
            sample_id="S1",
            graph_id="G1",
            features={"acetate": 50.0, "taxon:bacteroides": 0.2},
            targets={"acetate": 50.0, "propionate": 10.0, "butyrate": 5.0},
        )
        with pytest.raises(ValueError, match="Fuga detectada: columnas objetivo presentes"):
            TabularDataset(
                samples=(sample,),
                feature_names=("acetate", "taxon:bacteroides"),
            )

    def test_derived_target_stem_in_features_raises(self) -> None:
        sample = TabularSample(
            sample_id="S1",
            graph_id="G1",
            features={"metabolite:acetate_level": 50.0, "taxon:bacteroides": 0.2},
            targets={"acetate": 50.0, "propionate": 10.0, "butyrate": 5.0},
        )
        with pytest.raises(ValueError, match="Fuga detectada: el atributo"):
            TabularDataset(
                samples=(sample,),
                feature_names=("metabolite:acetate_level", "taxon:bacteroides"),
            )

    def test_non_taxon_stem_in_features_raises(self) -> None:
        sample = TabularSample(
            sample_id="S1",
            graph_id="G1",
            features={"host:acetate_ratio": 50.0, "taxon:bacteroides": 0.2},
            targets={"acetate": 50.0, "propionate": 10.0, "butyrate": 5.0},
        )
        with pytest.raises(ValueError, match="Fuga potencial detectada: el atributo no taxon"):
            TabularDataset(
                samples=(sample,),
                feature_names=("host:acetate_ratio", "taxon:bacteroides"),
            )

    def test_scfa_stem_in_features_raises(self) -> None:
        sample = TabularSample(
            sample_id="S1",
            graph_id="G1",
            features={"host:scfa_total": 80.0, "taxon:bacteroides": 0.2},
            targets={"acetate": 50.0, "propionate": 10.0, "butyrate": 5.0},
        )
        with pytest.raises(ValueError, match="Fuga potencial detectada"):
            TabularDataset(
                samples=(sample,),
                feature_names=("host:scfa_total", "taxon:bacteroides"),
            )


class TestSyntheticDatasetTabularBuilder:
    """Pruebas con el dataset sintético (DS-04/DS-05)."""

    def test_build_from_synthetic_scenario(self) -> None:
        ds = generate_scenario_dataset()
        tab_ds = build_tabular_from_synthetic(ds)

        assert len(tab_ds) == 2
        # Comprobar presencia de categorías requeridas
        feature_prefixes = {f.split(":")[0] for f in tab_ds.feature_names}
        assert "taxon" in feature_prefixes
        assert "diet" in feature_prefixes
        assert "host" in feature_prefixes
        assert "additive" in feature_prefixes

        # Verificar que no hay nodos metabolite en atributos
        assert "metabolite" not in feature_prefixes

        # Verificar targets canónicos
        for sample in tab_ds.samples:
            assert sample.acetate == pytest.approx(65.07)
            assert sample.propionate == pytest.approx(22.358)
            assert sample.butyrate == pytest.approx(14.649)

        # Matriz y exportación
        records = tab_ds.to_records()
        assert len(records) == 2
        assert "target_acetate" in records[0]
        assert "target_propionate" in records[0]
        assert "target_butyrate" in records[0]

        csv_text = tab_ds.to_csv()
        assert "target_acetate" in csv_text


class TestHoloFoodRealDataTabularBuilder:
    """Pruebas con la primera fuente real (D1 HoloFood)."""

    def test_build_from_holofood_fixtures(self) -> None:
        abundance = _source("D1_holofood", "abundance_ssu_caecum.tsv")
        tables = DataPipeline({"D1_holofood": abundance}).run(["D1_holofood"]).dataset
        tables, _ = attach_sample_context(
            tables,
            metadata=MetadataLoader(_source("D1_holofood_metadata", "metadata.tsv")).load(),
            metabolites=MetaboliteLoader(
                _source("D1_holofood_scfa_content", "scfa_caecum_content.tsv")
            ).load(),
        )

        split = get_split(split_file=FIXTURES / "split.json")
        tab_ds = build_tabular_dataset(tables, split=split)

        assert len(tab_ds) == 6
        assert tab_ds.target_names == CANONICAL_TARGETS

        # 1. Comprobar que todos los animales tienen los 3 AGCC
        for sample in tab_ds.samples:
            assert sample.acetate is not None and sample.acetate > 0.0
            assert sample.propionate is not None and sample.propionate > 0.0
            assert sample.butyrate is not None and sample.butyrate > 0.0

        # 2. Comprobar partición de A40-1
        train_ds = tab_ds.train_dataset
        val_ds = tab_ds.val_dataset
        test_ds = tab_ds.test_dataset

        assert len(train_ds) == len(split.train)
        assert len(val_ds) == len(split.val)
        assert len(test_ds) == len(split.test)
        assert len(train_ds) + len(val_ds) + len(test_ds) == 6

        train_samples = set(train_ds.sample_ids)
        val_samples = set(val_ds.sample_ids)
        test_samples = set(test_ds.sample_ids)

        assert train_samples.isdisjoint(val_samples)
        assert train_samples.isdisjoint(test_samples)
        assert val_samples.isdisjoint(test_samples)

        # 3. Covariables de entrada del huésped (contrato v2 §3, #147) y dieta; el corral y el
        # peso corporal nunca entran.
        for name in ("host:trial_code", "host:sampling_day", "host:sex", "host:breed"):
            assert name in tab_ds.feature_names
        assert "host:pen_code" not in tab_ds.feature_names
        assert "host:body_weight_g" not in tab_ds.feature_names
        assert "diet:treatment" in tab_ds.feature_names

        # 4. Comprobar ausencia de fuga de datos
        tab_ds.verify_no_target_leakage()


def test_canonicalize_target_name_distinguishes_isobutyrate() -> None:
    """Verifica que isobutyrate no se asigne erróneamente a butyrate por coincidencia
    de subcadena.
    """
    assert _canonicalize_target_name("isobutyrate") is None
    assert _canonicalize_target_name("isobutyric_acid") is None
    assert _canonicalize_target_name("sample:isobutyrate") is None
    assert _canonicalize_target_name("butyrate") == "butyrate"
    assert _canonicalize_target_name("butyric_acid") == "butyrate"
    assert _canonicalize_target_name("synthetic:metabolite:butyrate") == "butyrate"


def test_filter_complete_targets_keeps_only_finite_three_agcc_samples() -> None:
    """La cohorte de baselines no admite targets incompletos o no finitos."""
    samples = (
        TabularSample(
            sample_id="complete",
            graph_id="G1",
            features={"host:body_weight_g": 100.0},
            targets={"acetate": 1.0, "propionate": 2.0, "butyrate": 3.0},
            split="train",
        ),
        TabularSample(
            sample_id="missing",
            graph_id="G2",
            features={"host:body_weight_g": 110.0},
            targets={"acetate": 1.0, "propionate": 2.0},
            split="val",
        ),
        TabularSample(
            sample_id="non_finite",
            graph_id="G3",
            features={"host:body_weight_g": 120.0},
            targets={"acetate": 1.0, "propionate": 2.0, "butyrate": float("nan")},
            split="test",
        ),
    )
    dataset = TabularDataset(samples=samples, feature_names=("host:body_weight_g",))

    complete = dataset.filter_complete_targets()

    assert complete.sample_ids == ("complete",)
    assert complete.metadata["num_instances"] == 1
    assert len(dataset) == 3
