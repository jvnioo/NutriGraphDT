"""Pruebas de `attach_sample_context` (A39-1, #35): contexto, huésped y targets por muestra."""

from __future__ import annotations

from typing import Any

from nutrigraphdt.data.integration import attach_sample_context, host_node_id
from nutrigraphdt.data.loaders import IngestionPayload, SourceMetadata
from nutrigraphdt.data.schema import (
    NormalizedFeatureRecord,
    NormalizedInstanceRecord,
    NormalizedTabularDataset,
)

SOURCE = SourceMetadata(
    source_id="real",
    name="Fuente real de prueba",
    species="chicken",
    gut_segment="cecum",
    data_types=("microbiome",),
    format="tsv",
)


def _dataset() -> NormalizedTabularDataset:
    instances = [
        NormalizedInstanceRecord(
            graph_id=f"real:{sample}",
            sample_id=sample,
            species="chicken",
            gut_segment="cecum",
            study_id="unknown",
            scenario_id="unknown",
            diet_treatment="unknown",
            source_id="real",
        )
        for sample in ("A1", "A2")
    ]
    features = [
        NormalizedFeatureRecord(
            graph_id="real:A1",
            node_id="Lactobacillus",
            node_type="taxon",
            feature_name="abundance",
            value=1.0,
            unit="relative_abundance",
            source_id="real",
        )
    ]
    return NormalizedTabularDataset(instances=instances, features=features)


def _payload(records: list[dict[str, Any]]) -> IngestionPayload:
    return IngestionPayload(metadata=SOURCE, raw_data=records, records_count=len(records))


def _meta(sample: str, field: str, value: Any, unit: str = "dimensionless") -> dict[str, Any]:
    return {"sample_id": sample, "field": field, "value": value, "unit": unit, "source_id": "m"}


METADATA = _payload(
    [
        _meta("A1", "trial_code", "CA"),
        _meta("A1", "diet_treatment_name", "Probiotic"),
        _meta("A1", "sampling_day", 21.0),
        _meta("A1", "body_weight_g", 920.8, "g"),
        _meta("A2", "body_weight_g", "no numérico", "g"),
        _meta("Z9", "trial_code", "CB"),
    ]
)
METABOLITES = _payload(
    [
        {"sample_id": "A1", "canonical_id": "acetate", "value": 51.5, "unit": "mmol_kg"},
        {"sample_id": "Z9", "canonical_id": "acetate", "value": 1.0, "unit": "mmol_kg"},
    ]
)


def test_context_fills_instances_and_keeps_unknown_when_absent() -> None:
    dataset, report = attach_sample_context(_dataset(), metadata=METADATA)
    first, second = dataset.instances
    assert (first.study_id, first.diet_treatment, first.timepoint) == ("CA", "Probiotic", "21")
    assert (second.study_id, second.diet_treatment, second.timepoint) == (
        "unknown",
        "unknown",
        None,
    )
    assert report.instances_with_context == 1


def test_numeric_host_fields_become_host_features() -> None:
    dataset, report = attach_sample_context(_dataset(), metadata=METADATA)
    host = [feature for feature in dataset.features if feature.node_type == "host"]
    assert len(host) == 1
    assert host[0].node_id == host_node_id("A1") == "A1:host"
    assert (host[0].feature_name, host[0].value, host[0].unit) == ("body_weight_g", 920.8, "g")
    assert report.skipped_metadata_fields == ("body_weight_g",)


def test_metabolites_become_measured_targets_of_existing_instances() -> None:
    dataset, report = attach_sample_context(
        _dataset(), metabolites=METABOLITES, sample_matrix="cecal_content"
    )
    assert [(t.graph_id, t.target_id, t.value) for t in dataset.targets] == [
        ("real:A1", "acetate", 51.5)
    ]
    target = dataset.targets[0]
    assert (target.target_type, target.sample_matrix, target.measured_or_predicted) == (
        "scfa_concentration",
        "cecal_content",
        "measured",
    )
    assert report.unmatched_metabolite_samples == ("Z9",)


def test_unmatched_samples_are_reported_and_input_is_not_modified() -> None:
    original = _dataset()
    _, report = attach_sample_context(original, metadata=METADATA, metabolites=METABOLITES)
    assert report.unmatched_metadata_samples == ("Z9",)
    assert original.instances[0].study_id == "unknown"
    assert not original.targets
