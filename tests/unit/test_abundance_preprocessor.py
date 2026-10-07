"""Tests del preprocesamiento y control de calidad de abundancias (A34-4)."""

from __future__ import annotations

import copy
import json
import logging
import math
import random
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from nutrigraphdt.data.loaders.abundance import AbundanceLoader
from nutrigraphdt.data.loaders.base import IngestionPayload, SourceMetadata
from nutrigraphdt.data.preprocessors import (
    DUPLICATE_RECORD,
    EMPTY_SAMPLE,
    FILTERED_TAXON,
    INVALID_RECORD,
    MISSING_VALUE,
    UNKNOWN_CONTEXT,
    AbundancePreprocessingConfig,
    AbundancePreprocessor,
    DiscardedRecord,
    PreprocessedData,
    clr_transform,
    relative_abundance,
    taxon_prevalence,
)
from nutrigraphdt.data.schema import OBSERVED_SCENARIO_ID
from nutrigraphdt.data.synthetic import (
    SyntheticEdgeConfig,
    SyntheticNodeConfig,
    export_dataset,
    generate_scenario_dataset,
    generate_synthetic_dataset,
)

SOURCE_ID = "test_source"
LOGGER = "nutrigraphdt.data.preprocessors.abundance"

# ---------------------------------------------------------------------------
# Ayudantes
# ---------------------------------------------------------------------------


def _meta(
    *, is_synthetic: bool = False, fmt: str = "tsv", path: str | None = None
) -> SourceMetadata:
    return SourceMetadata(
        source_id=SOURCE_ID,
        name="Test Source",
        species="chicken",
        gut_segment="cecum",
        data_types=("microbiome",),
        format=fmt,
        path_or_url=path,
        is_synthetic=is_synthetic,
    )


def _rec(
    sample_id: Any,
    taxon_id: Any,
    value: Any,
    *,
    graph_id: Any = None,
    unit: Any = "relative_abundance",
) -> dict[str, Any]:
    return {
        "graph_id": graph_id,
        "sample_id": sample_id,
        "taxon_id": taxon_id,
        "taxon_level": "genus",
        "value": value,
        "unit": unit,
        "source_id": SOURCE_ID,
        "species": "chicken",
        "gut_segment": "cecum",
    }


def _payload(
    records: list[Any], *, errors: list[str] | None = None, is_synthetic: bool = False
) -> IngestionPayload:
    return IngestionPayload(
        metadata=_meta(is_synthetic=is_synthetic),
        raw_data=records,
        records_count=len(records),
        extra={"errors": errors or []},
    )


def _table(rows: dict[str, dict[str, float]], unit: str = "relative_abundance") -> list[Any]:
    """Registros de una tabla ``{muestra: {taxón: valor}}``."""
    return [
        _rec(sample, taxon, value, unit=unit)
        for sample, taxa in rows.items()
        for taxon, value in taxa.items()
    ]


def _run(records: list[Any], **config: Any) -> PreprocessedData:
    return AbundancePreprocessor(AbundancePreprocessingConfig(**config)).process(_payload(records))


def _values(data: PreprocessedData) -> dict[tuple[str, str], float]:
    return {(item.graph_id, item.node_id): item.value for item in data.features}


def _reasons(data: PreprocessedData) -> list[tuple[int, str]]:
    return [(item.index, item.reason) for item in data.report.discarded]


def _discarded_content(data: PreprocessedData) -> list[str]:
    """Descartes sin su posición, para comparar entradas en distinto orden."""
    return sorted(
        json.dumps([item.reason, item.detail, item.to_dict()["record"]], sort_keys=True)
        for item in data.report.discarded
    )


def _assert_report_balance(data: PreprocessedData, n_input: int) -> None:
    report = data.report
    assert report.input_records == n_input
    assert report.output_records == len(data.features)
    assert report.input_records == report.output_records + len(report.discarded)


# Tabla de 4 muestras con prevalencias conocidas (abundancia relativa ya cerrada a 1).
FILTER_TABLE: dict[str, dict[str, float]] = {
    "S1": {"common": 0.70, "half": 0.20, "rare": 0.10, "never": 0.0},
    "S2": {"common": 0.60, "half": 0.40, "rare": 0.0, "never": 0.0},
    "S3": {"common": 0.95, "half": 0.0, "rare": 0.05, "never": 0.0},
    "S4": {"common": 1.00, "half": 0.0, "rare": 0.0, "never": 0.0},
}


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------


class TestConfig:
    def test_defaults_do_not_filter_and_use_relative_abundance(self) -> None:
        config = AbundancePreprocessingConfig()
        assert config.normalization == "relative"
        assert config.clr_pseudocount is None
        assert config.min_prevalence == 0.0
        assert config.min_abundance == 0.0
        assert config.missing_strategy == "drop"

    @pytest.mark.parametrize(
        "changes",
        [
            {"normalization": "tss"},
            {"normalization": None},
            {"missing_strategy": "mean"},
            {"missing_strategy": 0},
            {"min_prevalence": -0.1},
            {"min_prevalence": 1.5},
            {"min_abundance": math.nan},
            {"min_abundance": math.inf},
            {"normalization": "clr"},
            {"normalization": "clr", "clr_pseudocount": 0.0},
            {"normalization": "clr", "clr_pseudocount": -1e-6},
            {"normalization": "clr", "clr_pseudocount": math.nan},
        ],
    )
    def test_invalid_values_raise_value_error(self, changes: dict[str, Any]) -> None:
        with pytest.raises(ValueError):
            AbundancePreprocessingConfig(**changes)

    @pytest.mark.parametrize(
        "changes",
        [
            {"min_prevalence": True},
            {"min_abundance": "0.1"},
            {"clr_pseudocount": False},
            {"clr_pseudocount": "1e-6"},
        ],
    )
    def test_non_numeric_values_raise_type_error(self, changes: dict[str, Any]) -> None:
        with pytest.raises(TypeError):
            AbundancePreprocessingConfig(**changes)

    def test_bounds_are_inclusive(self) -> None:
        config = AbundancePreprocessingConfig(min_prevalence=1, min_abundance=0)
        assert config.min_prevalence == 1

    def test_from_mapping_round_trip(self) -> None:
        config = AbundancePreprocessingConfig(
            normalization="clr", clr_pseudocount=1e-6, min_prevalence=0.25, min_abundance=0.001
        )
        assert AbundancePreprocessingConfig.from_mapping(config.to_dict()) == config
        assert json.loads(json.dumps(config.to_dict())) == config.to_dict()

    def test_from_mapping_rejects_unknown_keys(self) -> None:
        with pytest.raises(ValueError, match="min_prevalance"):
            AbundancePreprocessingConfig.from_mapping({"min_prevalance": 0.5})

    def test_from_mapping_rejects_non_mapping(self) -> None:
        with pytest.raises(TypeError):
            AbundancePreprocessingConfig.from_mapping([("min_prevalence", 0.5)])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Funciones de transformación
# ---------------------------------------------------------------------------


class TestRelativeAbundance:
    def test_counts_are_closed_to_one(self) -> None:
        result = relative_abundance([400.0, 100.0, 500.0], "reads_per_million")
        assert result == pytest.approx([0.4, 0.1, 0.5])
        assert math.fsum(result) == pytest.approx(1.0)

    def test_relative_values_with_unassigned_fraction_are_kept(self) -> None:
        # Una suma menor que 1 conserva la fracción no asignada, como AbundanceLoader.
        assert relative_abundance([0.2, 0.3], "relative_abundance") == [0.2, 0.3]

    def test_relative_values_summing_more_than_one_are_closed(self) -> None:
        assert relative_abundance([0.8, 0.8], "relative_abundance") == pytest.approx([0.5, 0.5])

    def test_non_relative_unit_is_always_closed(self) -> None:
        assert relative_abundance([0.2, 0.3], "copies_per_gram") == pytest.approx([0.4, 0.6])

    def test_zero_total_raises(self) -> None:
        with pytest.raises(ValueError):
            relative_abundance([0.0, 0.0], "relative_abundance")


class TestClrTransform:
    def test_known_values(self) -> None:
        # ln(1+1)=ln2 y ln(3+1)=2·ln2; la media es 1.5·ln2.
        result = clr_transform([1.0, 3.0], pseudocount=1.0)
        assert result == pytest.approx([-0.5 * math.log(2), 0.5 * math.log(2)])

    def test_values_sum_to_zero(self) -> None:
        result = clr_transform([0.5, 0.3, 0.2, 0.0], pseudocount=1e-6)
        assert math.fsum(result) == pytest.approx(0.0, abs=1e-12)

    def test_equal_components_are_zero(self) -> None:
        assert clr_transform([0.25] * 4, pseudocount=1e-6) == pytest.approx([0.0] * 4)

    def test_order_is_preserved(self) -> None:
        result = clr_transform([0.1, 0.6, 0.3], pseudocount=1e-6)
        assert result[1] > result[2] > result[0]

    def test_empty_composition_raises(self) -> None:
        with pytest.raises(ValueError):
            clr_transform([], pseudocount=1e-6)

    def test_non_positive_shifted_value_raises(self) -> None:
        with pytest.raises(ValueError):
            clr_transform([0.0, 0.5], pseudocount=0.0)


class TestTaxonPrevalence:
    def test_prevalence_counts_present_samples(self) -> None:
        prevalence = taxon_prevalence(FILTER_TABLE, min_abundance=0.0)
        assert prevalence == {"common": 1.0, "half": 0.5, "never": 0.0, "rare": 0.5}

    def test_min_abundance_defines_presence(self) -> None:
        prevalence = taxon_prevalence(FILTER_TABLE, min_abundance=0.1)
        # "rare" solo alcanza 0.1 en S1; 0.05 en S3 ya no cuenta como presencia.
        assert prevalence["rare"] == 0.25
        assert prevalence["half"] == 0.5

    def test_missing_taxon_counts_as_absent(self) -> None:
        prevalence = taxon_prevalence({"A": {"t1": 1.0}, "B": {"t2": 1.0}}, min_abundance=0.0)
        assert prevalence == {"t1": 0.5, "t2": 0.5}

    def test_empty_input(self) -> None:
        assert taxon_prevalence({}, min_abundance=0.0) == {}


# ---------------------------------------------------------------------------
# Preprocesador: identificadores, instancias y normalización
# ---------------------------------------------------------------------------


class TestIdentifiersAndInstances:
    def test_real_source_gets_graph_id_from_source_and_sample(self) -> None:
        data = _run(_table({"S1": {"a": 0.5, "b": 0.5}, "S2": {"a": 1.0, "b": 0.0}}))
        assert [inst.graph_id for inst in data.instances] == [
            f"{SOURCE_ID}:S1",
            f"{SOURCE_ID}:S2",
        ]
        assert {item.graph_id for item in data.features} == {f"{SOURCE_ID}:S1", f"{SOURCE_ID}:S2"}

    def test_existing_graph_id_is_preserved(self) -> None:
        records = [_rec("S1", "a", 1.0, graph_id="g:basal"), _rec("S1", "a", 1.0, graph_id="g:int")]
        data = _run(records)
        assert [inst.graph_id for inst in data.instances] == ["g:basal", "g:int"]
        assert {inst.sample_id for inst in data.instances} == {"S1"}

    def test_instances_carry_provenance_and_unknown_context(self) -> None:
        data = AbundancePreprocessor().process(
            _payload(_table({"S1": {"a": 1.0}}), is_synthetic=True)
        )
        (instance,) = data.instances
        assert instance.species == "chicken"
        assert instance.gut_segment == "cecum"
        assert instance.source_id == SOURCE_ID
        assert instance.is_synthetic is True
        assert instance.study_id == UNKNOWN_CONTEXT
        assert instance.scenario_id == UNKNOWN_CONTEXT
        assert instance.diet_treatment == UNKNOWN_CONTEXT

    def test_features_carry_the_taxonomy_level_of_the_loader(self) -> None:
        unknown = {**_rec("S1", "b", 1.0), "taxon_level": "unknown"}
        data = _run([_rec("S1", "a", 1.0), unknown])
        levels = {feature.node_id: feature.taxonomy_level for feature in data.features}
        assert levels == {"a": "genus", "b": None}

    def test_real_instances_are_observations(self) -> None:
        (instance,) = (
            AbundancePreprocessor().process(_payload(_table({"S1": {"a": 1.0}}))).instances
        )
        assert instance.is_synthetic is False
        assert instance.scenario_id == OBSERVED_SCENARIO_ID
        assert instance.study_id == UNKNOWN_CONTEXT

    def test_features_follow_the_normalized_schema(self) -> None:
        data = _run(_table({"S1": {"b": 0.25, "a": 0.75}}))
        assert [item.node_id for item in data.features] == ["a", "b"]
        for item in data.features:
            assert item.node_type == "taxon"
            assert item.feature_name == "abundance"
            assert item.unit == "relative_abundance"
            assert item.quality_flag == "valid"
            assert item.source_id == SOURCE_ID

    def test_counts_are_converted_to_relative_abundance(self) -> None:
        data = _run(_table({"S1": {"a": 300.0, "b": 100.0}}, unit="reads_per_million"))
        assert _values(data) == pytest.approx(
            {(f"{SOURCE_ID}:S1", "a"): 0.75, (f"{SOURCE_ID}:S1", "b"): 0.25}
        )
        assert {item.unit for item in data.features} == {"relative_abundance"}


# ---------------------------------------------------------------------------
# Preprocesador: valores faltantes e inválidos
# ---------------------------------------------------------------------------


class TestMissingValues:
    def test_missing_values_are_dropped_and_reported(self) -> None:
        records = [
            _rec("S1", "a", 0.6),
            _rec("S1", "b", None),
            _rec("S1", "c", math.nan),
            _rec("S1", "d", 0.4),
        ]
        data = _run(records)
        assert _reasons(data) == [(1, MISSING_VALUE), (2, MISSING_VALUE)]
        assert data.report.discarded[0].record["taxon_id"] == "b"
        assert sorted(node for _, node in _values(data)) == ["a", "d"]
        _assert_report_balance(data, 4)

    def test_absent_value_key_is_missing(self) -> None:
        record = _rec("S1", "a", 1.0)
        del record["value"]
        data = _run([record, _rec("S1", "b", 1.0)])
        assert _reasons(data) == [(0, MISSING_VALUE)]

    def test_zero_strategy_imputes_and_flags(self) -> None:
        records = [_rec("S1", "a", 0.6), _rec("S1", "b", None), _rec("S1", "c", 0.4)]
        data = _run(records, missing_strategy="zero")
        flags = {item.node_id: (item.value, item.quality_flag) for item in data.features}
        assert flags["b"] == (0.0, "imputed")
        assert flags["a"] == (0.6, "valid")
        assert data.report.imputed_records == 1
        assert data.report.discarded == []
        _assert_report_balance(data, 3)

    @pytest.mark.parametrize(
        "record",
        [
            _rec(None, "a", 0.5),
            _rec("", "a", 0.5),
            _rec("   ", "a", 0.5),
            _rec("S1", None, 0.5),
            _rec("S1", "", 0.5),
            _rec("S1", "a", 0.5, graph_id=""),
            _rec("S1", "a", 0.5, graph_id=7),
            _rec("S1", "a", 0.5, unit="mmol_kg"),
            _rec("S1", "a", 0.5, unit="presence_absence"),
            _rec("S1", "a", 0.5, unit=None),
            _rec("S1", "a", "0.5"),
            _rec("S1", "a", True),
            _rec("S1", "a", math.inf),
            _rec("S1", "a", -0.1),
        ],
    )
    def test_invalid_records_are_discarded(self, record: dict[str, Any]) -> None:
        data = _run([record, _rec("S9", "z", 1.0)])
        assert _reasons(data) == [(0, INVALID_RECORD)]
        assert [inst.sample_id for inst in data.instances] == ["S9"]
        _assert_report_balance(data, 2)

    def test_non_mapping_record_is_discarded(self) -> None:
        data = _run(["not a record", _rec("S1", "a", 1.0)])
        assert _reasons(data) == [(0, INVALID_RECORD)]
        assert data.report.discarded[0].record == {"record": "'not a record'"}

    def test_duplicate_taxon_in_sample_discards_every_value(self) -> None:
        records = [_rec("S1", "a", 0.3), _rec("S1", "b", 0.7), _rec("S1", "a", 0.9)]
        data = _run(records)
        assert _reasons(data) == [(0, DUPLICATE_RECORD), (2, DUPLICATE_RECORD)]
        assert _values(data) == {(f"{SOURCE_ID}:S1", "b"): 0.7}
        assert "2 valores" in data.report.discarded[0].detail
        _assert_report_balance(data, 3)

    def test_duplicate_with_missing_value_keeps_the_measured_one(self) -> None:
        # Con "drop" el faltante se descarta antes de buscar duplicados, en cualquier orden.
        for records in (
            [_rec("S1", "a", None), _rec("S1", "a", 0.4)],
            [_rec("S1", "a", 0.4), _rec("S1", "a", None)],
        ):
            data = _run(records)
            assert _values(data) == {(f"{SOURCE_ID}:S1", "a"): 0.4}
            assert [item.reason for item in data.report.discarded] == [MISSING_VALUE]

    def test_imputed_value_yields_to_a_measured_one(self) -> None:
        for records in (
            [_rec("S1", "a", None), _rec("S1", "a", 0.4), _rec("S1", "b", 0.6)],
            [_rec("S1", "a", 0.4), _rec("S1", "b", 0.6), _rec("S1", "a", None)],
        ):
            data = _run(records, missing_strategy="zero")
            assert _values(data) == {
                (f"{SOURCE_ID}:S1", "a"): 0.4,
                (f"{SOURCE_ID}:S1", "b"): 0.6,
            }
            assert [item.reason for item in data.report.discarded] == [MISSING_VALUE]
            assert data.report.imputed_records == 0

    def test_two_imputed_values_for_one_taxon_are_duplicates(self) -> None:
        records = [_rec("S1", "a", None), _rec("S1", "a", math.nan), _rec("S1", "b", 1.0)]
        data = _run(records, missing_strategy="zero")
        assert _reasons(data) == [(0, DUPLICATE_RECORD), (1, DUPLICATE_RECORD)]

    def test_graph_id_with_two_samples_discards_all_its_records(self) -> None:
        records = [
            _rec("S1", "a", 1.0, graph_id="g1"),
            _rec("S2", "b", 1.0, graph_id="g1"),
            _rec("S3", "a", 1.0, graph_id="g2"),
        ]
        data = _run(records)
        assert _reasons(data) == [(0, INVALID_RECORD), (1, INVALID_RECORD)]
        assert "['S1', 'S2']" in data.report.discarded[0].detail
        assert [inst.graph_id for inst in data.instances] == ["g2"]

    def test_ambiguous_graph_is_detected_with_discarded_records(self) -> None:
        # El registro de S2 se descarta por faltante, pero declara el mismo graph_id que S1.
        records = [_rec("S1", "a", 1.0, graph_id="g1"), _rec("S2", "a", None, graph_id="g1")]
        data = _run(records)
        assert _reasons(data) == [(0, INVALID_RECORD), (1, MISSING_VALUE)]
        assert data.instances == []

    def test_values_too_large_for_float_are_invalid(self) -> None:
        records = [_rec("S1", "a", 10**400), _rec("S2", "a", 1.0)]
        data = _run(records)
        assert _reasons(data) == [(0, INVALID_RECORD)]
        assert "representable" in data.report.discarded[0].detail

    def test_sample_whose_sum_overflows_is_invalid(self) -> None:
        rows = {"S1": {"a": 1e308, "b": 1e308}, "S2": {"a": 1.0}}
        data = _run(_table(rows, unit="reads_per_million"))
        assert _reasons(data) == [(0, INVALID_RECORD), (1, INVALID_RECORD)]
        assert [inst.sample_id for inst in data.instances] == ["S2"]

    def test_any_real_number_type_is_accepted(self) -> None:
        records = [
            _rec("S1", "a", Fraction(1, 4)),
            _rec("S1", "b", 0.75),
            _rec("S2", "a", 2, unit="reads_per_million"),
        ]
        data = _run(records)
        assert _values(data) == {
            (f"{SOURCE_ID}:S1", "a"): 0.25,
            (f"{SOURCE_ID}:S1", "b"): 0.75,
            (f"{SOURCE_ID}:S2", "a"): 1.0,
        }
        assert all(type(item.value) is float for item in data.features)

    def test_sample_mixing_units_is_discarded(self) -> None:
        records = [
            _rec("S1", "a", 0.5),
            _rec("S1", "b", 10.0, unit="reads_per_million"),
            _rec("S2", "a", 1.0),
        ]
        data = _run(records)
        assert _reasons(data) == [(0, INVALID_RECORD), (1, INVALID_RECORD)]
        assert [inst.sample_id for inst in data.instances] == ["S2"]

    def test_all_zero_sample_is_discarded(self) -> None:
        records = [_rec("S1", "a", 0.0), _rec("S1", "b", 0.0), _rec("S2", "a", 1.0)]
        data = _run(records)
        assert _reasons(data) == [(0, EMPTY_SAMPLE), (1, EMPTY_SAMPLE)]
        assert [inst.sample_id for inst in data.instances] == ["S2"]
        _assert_report_balance(data, 3)

    def test_sample_with_only_imputed_zeros_is_empty(self) -> None:
        data = _run([_rec("S1", "a", None), _rec("S2", "a", 1.0)], missing_strategy="zero")
        assert _reasons(data) == [(0, EMPTY_SAMPLE)]

    def test_raw_data_must_be_a_list(self) -> None:
        payload = IngestionPayload(metadata=_meta(), raw_data={"a": 1}, records_count=1)
        with pytest.raises(TypeError, match="raw_data"):
            AbundancePreprocessor().process(payload)

    def test_empty_payload(self) -> None:
        data = _run([])
        assert data.features == []
        assert data.instances == []
        _assert_report_balance(data, 0)


# ---------------------------------------------------------------------------
# Preprocesador: filtro por prevalencia y abundancia mínima
# ---------------------------------------------------------------------------


class TestFilter:
    def test_default_configuration_keeps_every_taxon(self) -> None:
        data = _run(_table(FILTER_TABLE))
        assert len(data.features) == 16
        assert data.report.removed_taxa == {}

    def test_prevalence_filter_removes_taxa_below_threshold(self) -> None:
        data = _run(_table(FILTER_TABLE), min_prevalence=0.75)
        assert data.report.removed_taxa == {"half": 0.5, "never": 0.0, "rare": 0.5}
        assert {node for _, node in _values(data)} == {"common"}
        assert {item.reason for item in data.report.discarded} == {FILTERED_TAXON}
        assert len(data.report.discarded) == 12
        _assert_report_balance(data, 16)

    def test_prevalence_equal_to_threshold_is_kept(self) -> None:
        data = _run(_table(FILTER_TABLE), min_prevalence=0.5)
        assert set(data.report.removed_taxa) == {"never"}

    def test_min_abundance_changes_presence(self) -> None:
        data = _run(_table(FILTER_TABLE), min_prevalence=0.5, min_abundance=0.1)
        # "rare" solo supera 0.1 en S1 (prevalencia 0.25); "half" la mantiene (0.5).
        assert set(data.report.removed_taxa) == {"never", "rare"}
        assert data.report.removed_taxa["rare"] == 0.25

    def test_filter_uses_relative_abundance_not_raw_counts(self) -> None:
        # En valores crudos "b" supera 5, pero su abundancia relativa es 0.05 y 0.04.
        rows = {"S1": {"a": 95.0, "b": 5.0}, "S2": {"a": 96.0, "b": 4.0}}
        data = _run(_table(rows, unit="reads_per_million"), min_prevalence=1.0, min_abundance=0.1)
        assert set(data.report.removed_taxa) == {"b"}

    def test_filtered_values_are_not_renormalized(self) -> None:
        data = _run(_table(FILTER_TABLE), min_prevalence=0.75)
        assert _values(data)[(f"{SOURCE_ID}:S1", "common")] == 0.70

    def test_sample_without_retained_taxa_has_no_instance(self) -> None:
        rows = {"S1": {"a": 1.0}, "S2": {"a": 1.0}, "S3": {"b": 1.0}}
        data = _run(_table(rows), min_prevalence=0.5)
        assert [inst.sample_id for inst in data.instances] == ["S1", "S2"]
        assert _reasons(data) == [(2, FILTERED_TAXON)]

    def test_filtered_record_detail_explains_threshold(self) -> None:
        data = _run(_table(FILTER_TABLE), min_prevalence=0.75)
        detail = data.report.discarded[0].detail
        assert "0.5" in detail
        assert "0.75" in detail

    def test_imputed_zero_counts_as_absent(self) -> None:
        records = [_rec("S1", "a", 1.0), _rec("S2", "a", None), _rec("S2", "b", 1.0)]
        data = _run(records, missing_strategy="zero", min_prevalence=1.0)
        assert set(data.report.removed_taxa) == {"a", "b"}


# ---------------------------------------------------------------------------
# Preprocesador: transformación CLR
# ---------------------------------------------------------------------------


class TestClrOutput:
    def test_clr_features_sum_to_zero_per_sample(self) -> None:
        data = _run(_table(FILTER_TABLE), normalization="clr", clr_pseudocount=1e-6)
        assert {(item.feature_name, item.unit) for item in data.features} == {
            ("abundance_clr", "dimensionless")
        }
        for instance in data.instances:
            values = [item.value for item in data.features if item.graph_id == instance.graph_id]
            assert math.fsum(values) == pytest.approx(0.0, abs=1e-9)

    def test_clr_matches_definition_on_retained_taxa(self) -> None:
        pseudocount = 0.01
        data = _run(
            _table(FILTER_TABLE),
            normalization="clr",
            clr_pseudocount=pseudocount,
            min_prevalence=0.5,
        )
        retained = ["common", "half", "rare"]
        for sample, taxa in FILTER_TABLE.items():
            logs = {taxon: math.log(taxa[taxon] + pseudocount) for taxon in retained}
            mean = sum(logs.values()) / len(logs)
            for taxon in retained:
                assert _values(data)[(f"{SOURCE_ID}:{sample}", taxon)] == pytest.approx(
                    logs[taxon] - mean
                )

    def test_clr_uses_the_shared_taxon_set_of_the_source(self) -> None:
        # S1 no informa "c"; cuenta como 0 y "a" tiene el mismo CLR que en S2.
        rows = {"S1": {"a": 0.5, "b": 0.5}, "S2": {"a": 0.5, "b": 0.5, "c": 0.0}}
        data = _run(_table(rows), normalization="clr", clr_pseudocount=1e-6)
        values = _values(data)
        assert values[(f"{SOURCE_ID}:S1", "a")] == pytest.approx(values[(f"{SOURCE_ID}:S2", "a")])
        assert (f"{SOURCE_ID}:S1", "c") not in values

    def test_dropped_missing_value_counts_as_zero_in_clr(self) -> None:
        pseudocount = 1e-3
        records = [
            _rec("S1", "a", 0.5),
            _rec("S1", "b", None),
            _rec("S1", "c", 0.5),
            _rec("S2", "a", 0.2),
            _rec("S2", "b", 0.3),
            _rec("S2", "c", 0.5),
        ]
        data = _run(records, normalization="clr", clr_pseudocount=pseudocount)
        logs = [math.log(0.5 + pseudocount), math.log(pseudocount), math.log(0.5 + pseudocount)]
        expected = logs[0] - sum(logs) / 3
        assert _values(data)[(f"{SOURCE_ID}:S1", "a")] == pytest.approx(expected)

    def test_clr_with_a_single_taxon_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        rows = {"S1": {"a": 0.5, "b": 0.5}, "S2": {"a": 1.0}, "S3": {"c": 1.0}}
        with caplog.at_level(logging.WARNING, logger=LOGGER):
            data = _run(_table(rows), normalization="clr", clr_pseudocount=1e-6, min_prevalence=0.5)
        assert {item.value for item in data.features} == {0.0}
        assert any("un solo taxón" in record.getMessage() for record in caplog.records)

    def test_clr_keeps_imputed_flag(self) -> None:
        records = [_rec("S1", "a", 1.0), _rec("S1", "b", None)]
        data = _run(records, normalization="clr", clr_pseudocount=1e-6, missing_strategy="zero")
        flags = {item.node_id: item.quality_flag for item in data.features}
        assert flags == {"a": "valid", "b": "imputed"}


# ---------------------------------------------------------------------------
# Reproducibilidad, informe y log
# ---------------------------------------------------------------------------


MIXED_RECORDS: list[Any] = [
    *_table(FILTER_TABLE),
    _rec("S5", "common", None),
    _rec("S5", "half", 0.3),
    _rec("S6", "common", -1.0),
    _rec("S1", "common", 0.5),
]


class TestReproducibility:
    @pytest.mark.parametrize(
        "config",
        [
            {},
            {"min_prevalence": 0.5, "min_abundance": 0.05},
            {"normalization": "clr", "clr_pseudocount": 1e-6, "missing_strategy": "zero"},
        ],
    )
    def test_same_input_gives_same_output(self, config: dict[str, Any]) -> None:
        first = _run(copy.deepcopy(MIXED_RECORDS), **config)
        second = _run(copy.deepcopy(MIXED_RECORDS), **config)
        assert first.features == second.features
        assert first.instances == second.instances
        assert first.report.to_dict() == second.report.to_dict()

    @pytest.mark.parametrize("seed", [0, 1, 2])
    @pytest.mark.parametrize(
        "config",
        [
            {"normalization": "clr", "clr_pseudocount": 1e-6, "min_prevalence": 0.5},
            {"missing_strategy": "zero", "min_prevalence": 0.5, "min_abundance": 0.05},
        ],
    )
    def test_output_does_not_depend_on_record_order(
        self, seed: int, config: dict[str, Any]
    ) -> None:
        # Incluye faltantes, duplicados y un graph_id con dos muestras.
        records = [
            *copy.deepcopy(MIXED_RECORDS),
            _rec("S7", "common", 0.4, graph_id="shared"),
            _rec("S8", "half", 0.6, graph_id="shared"),
        ]
        shuffled = records[:]
        random.Random(seed).shuffle(shuffled)
        expected = _run(records, **config)
        result = _run(shuffled, **config)
        assert result.features == expected.features
        assert result.instances == expected.instances
        assert result.report.removed_taxa == expected.report.removed_taxa
        assert _discarded_content(result) == _discarded_content(expected)

    @pytest.mark.parametrize("seed", range(20))
    def test_random_payloads_are_order_independent(self, seed: int) -> None:
        rng = random.Random(seed)
        values: list[Any] = [None, math.nan, 0.0, 0.0, 0.1, 0.25, 0.5, 3.0, 10.0]
        records = [
            _rec(
                f"S{rng.randint(1, 4)}",
                f"t{rng.randint(1, 5)}",
                rng.choice(values),
                unit=rng.choice(["reads_per_million", "reads_per_million", "relative_abundance"]),
            )
            for _ in range(rng.randint(5, 30))
        ]
        config = {
            "normalization": rng.choice(["relative", "clr"]),
            "clr_pseudocount": 1e-6,
            "missing_strategy": rng.choice(["drop", "zero"]),
            "min_prevalence": rng.choice([0.0, 0.5, 1.0]),
            "min_abundance": rng.choice([0.0, 0.1]),
        }
        shuffled = records[:]
        rng.shuffle(shuffled)
        expected = _run(copy.deepcopy(records), **config)
        result = _run(copy.deepcopy(shuffled), **config)
        assert result.features == expected.features
        assert result.instances == expected.instances
        assert _discarded_content(result) == _discarded_content(expected)
        _assert_report_balance(result, len(records))

    def test_payload_is_not_modified(self) -> None:
        records = copy.deepcopy(MIXED_RECORDS)
        payload = _payload(records)
        snapshot = copy.deepcopy(records)
        AbundancePreprocessor(AbundancePreprocessingConfig(missing_strategy="zero")).process(
            payload
        )
        assert payload.raw_data == snapshot


class TestReport:
    def test_report_balances_and_counts_by_reason(self) -> None:
        data = _run(copy.deepcopy(MIXED_RECORDS), min_prevalence=0.75)
        _assert_report_balance(data, len(MIXED_RECORDS))
        counts = data.report.discarded_counts()
        assert list(counts) == sorted(counts)
        assert counts[MISSING_VALUE] == 1
        assert counts[INVALID_RECORD] == 1
        assert counts[DUPLICATE_RECORD] == 2
        assert sum(counts.values()) == len(data.report.discarded)
        assert [item.index for item in data.report.discarded] == sorted(
            item.index for item in data.report.discarded
        )

    def test_report_is_strict_json(self) -> None:
        data = _run([_rec("S1", "a", math.nan), _rec("S1", "b", 1.0)])
        document = json.dumps(data.report.to_dict(), allow_nan=False)
        restored = json.loads(document)
        assert restored["discarded"][0]["record"]["value"] == "nan"
        assert restored["parameters"] == AbundancePreprocessingConfig().to_dict()

    def test_summary_has_no_row_detail(self) -> None:
        data = _run(copy.deepcopy(MIXED_RECORDS), min_prevalence=0.75)
        summary = data.report.summary()
        assert summary["discarded_records"] == len(data.report.discarded)
        assert summary["removed_taxa_count"] == len(data.report.removed_taxa) > 0
        assert "discarded" not in summary

    def test_filtered_records_keep_only_identifying_fields(self) -> None:
        data = _run(_table(FILTER_TABLE), min_prevalence=0.75)
        for item in data.report.discarded:
            assert set(item.record) == {"graph_id", "sample_id", "taxon_id", "value", "unit"}

    def test_loader_errors_are_kept(self) -> None:
        payload = _payload([_rec("S1", "a", 1.0)], errors=["fila 3: valor no numérico"])
        data = AbundancePreprocessor().process(payload)
        assert data.report.loader_errors == ["fila 3: valor no numérico"]

    def test_discarded_record_rejects_unknown_reason(self) -> None:
        with pytest.raises(ValueError):
            DiscardedRecord(index=0, reason="other", detail="", record={})

    def test_discarded_rows_are_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger=LOGGER):
            _run(_table(FILTER_TABLE) + [_rec("S1", "x", None)], min_prevalence=0.75)
        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        infos = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
        assert any("missing_value" in message for message in warnings)
        assert any("'rare' eliminado" in message for message in infos)
        assert any("preprocesamiento" in message for message in infos)


# ---------------------------------------------------------------------------
# Dataset sintético de la actividad 26
# ---------------------------------------------------------------------------


def _synthetic_payload(tmp_path: Path, seeds: tuple[int, ...]) -> IngestionPayload:
    """Exporta un dataset sintético por semilla y reúne lo que lee `AbundanceLoader`."""
    records: list[Any] = []
    for seed in seeds:
        dataset = generate_synthetic_dataset(
            SyntheticNodeConfig(random_seed=seed, graph_id=f"synthetic:graph:{seed:04d}"),
            SyntheticEdgeConfig(random_seed=seed),
        )
        directory = tmp_path / f"seed_{seed}"
        export_dataset(dataset, directory)
        payload = AbundanceLoader(_meta(is_synthetic=True, fmt="jsonl", path=str(directory))).load()
        assert payload.extra["errors"] == []
        records.extend(payload.raw_data)
    return IngestionPayload(
        metadata=_meta(is_synthetic=True, fmt="jsonl"),
        raw_data=records,
        records_count=len(records),
        extra={"errors": []},
    )


class TestSyntheticDataset:
    def test_scenario_dataset_passes_unchanged_with_defaults(self) -> None:
        loader_meta = _meta(is_synthetic=True, fmt="jsonl", path="does-not-exist")
        loader_meta.options["generate_if_missing"] = True
        payload = AbundanceLoader(loader_meta).load()
        data = AbundancePreprocessor().process(payload)

        dataset = generate_scenario_dataset()
        assert [inst.graph_id for inst in data.instances] == sorted(
            inst.graph_id for inst in dataset.instances
        )
        assert data.report.discarded == []
        expected = {(r["graph_id"], r["taxon_id"]): r["value"] for r in payload.raw_data}
        assert _values(data) == expected
        assert all(inst.is_synthetic for inst in data.instances)

    def test_filter_on_several_synthetic_graphs(self, tmp_path: Path) -> None:
        payload = _synthetic_payload(tmp_path, seeds=(0, 7, 42, 2026))
        min_abundance, min_prevalence = 0.05, 0.75
        data = AbundancePreprocessor(
            AbundancePreprocessingConfig(min_prevalence=min_prevalence, min_abundance=min_abundance)
        ).process(payload)

        # Expectativa calculada directamente desde los registros del loader.
        graphs = {r["graph_id"] for r in payload.raw_data}
        present: dict[str, int] = {}
        for r in payload.raw_data:
            hit = r["value"] > 0 and r["value"] >= min_abundance
            present[r["taxon_id"]] = present.get(r["taxon_id"], 0) + int(hit)
        expected_removed = {t for t, n in present.items() if n / len(graphs) < min_prevalence}

        assert expected_removed, "la configuración debe eliminar algún taxón sintético"
        assert set(data.report.removed_taxa) == expected_removed
        assert {node for _, node in _values(data)} == set(present) - expected_removed
        assert len(data.instances) == 4
        _assert_report_balance(data, len(payload.raw_data))

    def test_clr_on_synthetic_graphs_is_reproducible(self, tmp_path: Path) -> None:
        payload = _synthetic_payload(tmp_path, seeds=(0, 7, 42))
        config = AbundancePreprocessingConfig(normalization="clr", clr_pseudocount=1e-6)
        first = AbundancePreprocessor(config).process(payload)
        second = AbundancePreprocessor(config).process(copy.deepcopy(payload))
        assert first.features == second.features
        for instance in first.instances:
            values = [f.value for f in first.features if f.graph_id == instance.graph_id]
            assert math.fsum(values) == pytest.approx(0.0, abs=1e-9)

    def test_missing_values_in_synthetic_payload(self, tmp_path: Path) -> None:
        payload = _synthetic_payload(tmp_path, seeds=(0, 7))
        records = copy.deepcopy(payload.raw_data)
        records[0]["value"] = None
        records[11]["value"] = math.nan
        damaged = IngestionPayload(
            metadata=payload.metadata,
            raw_data=records,
            records_count=len(records),
            extra={"errors": []},
        )

        dropped = AbundancePreprocessor().process(damaged)
        assert _reasons(dropped) == [(0, MISSING_VALUE), (11, MISSING_VALUE)]
        assert len(dropped.features) == len(records) - 2

        imputed = AbundancePreprocessor(
            AbundancePreprocessingConfig(missing_strategy="zero")
        ).process(damaged)
        flags = {(f.graph_id, f.node_id): (f.value, f.quality_flag) for f in imputed.features}
        assert flags[(records[0]["graph_id"], records[0]["taxon_id"])] == (0.0, "imputed")
        assert flags[(records[11]["graph_id"], records[11]["taxon_id"])] == (0.0, "imputed")
        assert imputed.report.imputed_records == 2


class TestLoaderCells:
    def test_loader_cell_handling_reaches_the_report(self, tmp_path: Path) -> None:
        # AbundanceLoader (A34-2) lee una celda vacía como 0 y omite "NA" con un error de
        # lectura: el preprocesador recibe un 0 medido y no ve ese faltante. El informe conserva
        # el error del loader para que la fila omitida no se pierda sin rastro.
        table = tmp_path / "cells.tsv"
        table.write_text("taxon_id\tS1\tS2\nA\t10\t\nB\tNA\t5\n", encoding="utf-8")
        payload = AbundanceLoader(_meta(path=str(table))).load()
        data = AbundancePreprocessor(AbundancePreprocessingConfig(missing_strategy="zero")).process(
            payload
        )

        flags = {(f.graph_id, f.node_id): (f.value, f.quality_flag) for f in data.features}
        assert flags[(f"{SOURCE_ID}:S2", "A")] == (0.0, "valid")
        assert (f"{SOURCE_ID}:S1", "B") not in flags
        assert data.report.imputed_records == 0
        assert any("'NA'" in error for error in data.report.loader_errors)
