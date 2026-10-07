"""Pruebas de la interfaz común, el reporte y la compuerta previa al modelo (VG-07).

Verifican el efecto de cada severidad definido en `docs/graph/graph-integrity-rules.md`: un `ERROR`
retiene su grafo (o todos, si es de nivel dataset); una `ADVERTENCIA` y un `INFO` no bloquean.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from nutrigraphdt.data.synthetic import (
    NodeCountConfig,
    SyntheticNodeConfig,
    generate_scenario_dataset,
    generate_synthetic_dataset,
)
from nutrigraphdt.graph.validation import (
    RULES_VERSION,
    GraphIntegrityError,
    RawDataset,
    Severity,
    ValidationReport,
    prepare_graphs_for_model,
    require_deliverable,
    validate_graph,
)
from nutrigraphdt.graph.validation.pipeline import RECORD_FAMILIES

Builder = Callable[..., tuple[Any, dict[str, Any]]]
RULES = Path(__file__).resolve().parents[2] / "docs" / "graph" / "graph-integrity-rules.md"

BEYOND_CATALOG = NodeCountConfig(
    diet=3, additive=6, substrate=10, taxon=14, function=11, metabolite=8, host=2, phenotype=5
)


def _raw(dataset: Any) -> RawDataset:
    """Registros JSONL mutables de un dataset generado."""
    return RawDataset(
        metadata=copy.deepcopy(dataset.metadata),
        instances=[instance.to_dict() for instance in dataset.instances],
        nodes=copy.deepcopy([node.to_dict() for node in dataset.nodes]),
        edges=copy.deepcopy([edge.to_dict() for edge in dataset.edges]),
        outputs=[output.to_dict() for output in dataset.outputs],
    )


def _graphs(builder: Builder, dataset: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """`HeteroData` de cada instancia y el metadata que declara sus columnas."""
    graphs: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    for instance in dataset.instances:
        graphs[instance.graph_id], metadata = builder(dataset, instance.graph_id)
    return graphs, metadata


def _rules(report: ValidationReport) -> list[str]:
    return [finding.rule_id for finding in report.findings]


# ---------------------------------------------------------------------------
# Interfaz común
# ---------------------------------------------------------------------------


def test_rules_version_matches_the_specification() -> None:
    header = re.search(r"\*\*Versión de las reglas:\*\* `([^`]+)`", RULES.read_text("utf-8"))

    assert header is not None
    assert header.group(1) == RULES_VERSION


def test_valid_dataset_produces_an_empty_valid_report() -> None:
    dataset = generate_synthetic_dataset()

    report = validate_graph(dataset)

    assert report.findings == ()
    assert report.is_valid
    assert report.graph_ids == (dataset.instances[0].graph_id,)
    assert report.deliverable_graph_ids == report.graph_ids
    assert report.evaluated == RECORD_FAMILIES
    assert dict(report.not_evaluated) == {"TEN": "no se entregó HeteroData"}


def test_dataset_objects_and_raw_records_give_the_same_report() -> None:
    dataset = generate_scenario_dataset()

    assert validate_graph(dataset) == validate_graph(_raw(dataset))


def test_every_record_rule_family_runs_through_the_common_interface() -> None:
    records = _raw(generate_scenario_dataset())
    basal, intervention = (instance["graph_id"] for instance in records.instances)
    records.instances[1]["scenario_id"] = "treatment"  # INS-03
    next(n for n in records.nodes if n["graph_id"] == intervention)["source_id"] = ""  # NOD-02
    next(e for e in records.edges if e["graph_id"] == intervention)["evidence_id"] = ""  # EDG-03
    # Una dieta aislada (CON-01) que counts no declara (MET-03).
    records.nodes.append({**copy.deepcopy(records.nodes[0]), "node_id": "synthetic:diet:0099"})
    records.outputs.append({"graph_id": basal})  # OUT-01, OUT-02 y OUT-04

    report = validate_graph(records)

    families = {rule_id.split("-")[0] for rule_id in _rules(report)}
    assert families == set(RECORD_FAMILIES)


def test_does_not_modify_records_or_graphs(heterodata_builder: Builder) -> None:
    dataset = generate_scenario_dataset()
    graphs, _ = _graphs(heterodata_builder, dataset)
    records = _raw(dataset)
    records.edges[0]["evidence_status"] = "observed"
    before = copy.deepcopy(records)
    graph_types = {key: list(data.node_types) for key, data in graphs.items()}

    validate_graph(records, heterodata=graphs)

    assert records == before
    assert {key: list(data.node_types) for key, data in graphs.items()} == graph_types


def test_metadata_rules_are_skipped_without_metadata() -> None:
    records = _raw(generate_synthetic_dataset())
    records = RawDataset(None, records.instances, records.nodes, records.edges, records.outputs)

    report = validate_graph(records)

    assert "MET" not in report.evaluated
    assert report.not_evaluated["MET"] == "no se entregó metadata.json"
    assert report.is_valid


# ---------------------------------------------------------------------------
# Efecto de las severidades
# ---------------------------------------------------------------------------


def test_warnings_do_not_block_delivery() -> None:
    records = _raw(generate_scenario_dataset())
    intervention = records.instances[1]["graph_id"]
    taxon = next(
        node
        for node in records.nodes
        if node["graph_id"] == intervention and node["node_type"] == "taxon"
    )
    taxon["attributes"]["abundance"] += 0.001

    report = validate_graph(records)

    assert report.warnings and set(_rules(report)) == {"INS-06"}
    assert report.is_valid
    assert report.deliverable_graph_ids == report.graph_ids


def test_info_findings_do_not_block_delivery() -> None:
    dataset = generate_synthetic_dataset(SyntheticNodeConfig(counts=BEYOND_CATALOG))

    report = validate_graph(dataset)

    assert [finding.severity for finding in report.findings] == [Severity.INFO]
    assert report.deliverable_graph_ids == report.graph_ids


def test_an_error_blocks_only_its_graph() -> None:
    records = _raw(generate_scenario_dataset())
    basal, intervention = (instance["graph_id"] for instance in records.instances)
    next(edge for edge in records.edges if edge["graph_id"] == basal)["evidence_status"] = (
        "observed"
    )

    report = validate_graph(records)

    assert not report.is_valid
    assert report.blocked_graph_ids == (basal,)
    assert report.deliverable_graph_ids == (intervention,)
    assert [finding.rule_id for finding in report.blocking_findings(basal)] == ["EDG-04"]


def test_a_dataset_level_error_blocks_every_graph() -> None:
    records = _raw(generate_scenario_dataset())
    records.metadata["random_seed"] = "42"

    report = validate_graph(records)

    assert [finding.rule_id for finding in report.dataset_errors] == ["MET-01"]
    assert report.deliverable_graph_ids == ()
    assert report.blocked_graph_ids == report.graph_ids


def test_require_deliverable_raises_only_for_blocked_graphs() -> None:
    records = _raw(generate_scenario_dataset())
    basal, intervention = (instance["graph_id"] for instance in records.instances)
    next(edge for edge in records.edges if edge["graph_id"] == basal)["evidence_id"] = ""
    report = validate_graph(records)

    require_deliverable(report, [intervention])
    with pytest.raises(GraphIntegrityError) as raised:
        require_deliverable(report)

    assert raised.value.graph_ids == (basal,)
    assert raised.value.report is report
    assert "EDG-03" in str(raised.value)


def test_integrity_error_lists_a_dataset_error_once() -> None:
    records = _raw(generate_scenario_dataset())
    records.metadata["schema_version"] = "2.0.0"
    report = validate_graph(records)

    with pytest.raises(GraphIntegrityError) as raised:
        require_deliverable(report)

    assert len(raised.value.graph_ids) == 2
    assert str(raised.value).count("MET-01") == 1


# ---------------------------------------------------------------------------
# Reporte
# ---------------------------------------------------------------------------


def test_report_structure_is_stable_and_json_compatible() -> None:
    records = _raw(generate_scenario_dataset())
    records.metadata["random_seed"] = True
    basal = records.instances[0]["graph_id"]
    next(edge for edge in records.edges if edge["graph_id"] == basal)["evidence_status"] = (
        "observed"
    )

    first = validate_graph(records).to_dict()
    second = validate_graph(copy.deepcopy(records)).to_dict()

    assert first == second
    assert json.loads(json.dumps(first, allow_nan=False)) == first
    assert list(first) == [
        "report_format",
        "rules_version",
        "schema_version",
        "scope",
        "status",
        "summary",
        "dataset_errors",
        "graphs",
        "rules",
        "evaluated",
        "not_evaluated",
        "findings",
    ]
    assert first["status"] == "invalid"
    assert first["dataset_errors"] == 1
    assert first["summary"]["ERROR"] == 2
    assert first["rules"]["EDG-04"] == {"severity": "ERROR", "count": 1}
    assert first["graphs"][basal]["deliverable"] is False
    assert "biológica" in first["scope"]


def test_findings_start_with_dataset_level_errors() -> None:
    records = _raw(generate_scenario_dataset())
    records.metadata["random_seed"] = True

    report = validate_graph(records)

    assert report.findings[0].rule_id == "MET-01"
    graph_ids = [finding.graph_id or "" for finding in report.findings]
    assert graph_ids == sorted(graph_ids)


# ---------------------------------------------------------------------------
# Tensores y compuerta previa al modelo
# ---------------------------------------------------------------------------


def _with_feature_schema(records: RawDataset, metadata: dict[str, Any]) -> RawDataset:
    records.metadata["node_feature_schema"] = metadata["node_feature_schema"]
    records.metadata["edge_feature_schema"] = metadata["edge_feature_schema"]
    return records


def test_valid_graphs_are_all_delivered(heterodata_builder: Builder) -> None:
    dataset = generate_scenario_dataset()
    graphs, metadata = _graphs(heterodata_builder, dataset)
    records = _with_feature_schema(_raw(dataset), metadata)

    delivered, report = prepare_graphs_for_model(records, graphs)

    assert set(delivered) == set(graphs)
    assert all(delivered[key] is graphs[key] for key in graphs)
    assert "TEN" in report.evaluated
    assert report.findings == ()


def test_a_tensor_error_withholds_only_its_graph(heterodata_builder: Builder) -> None:
    dataset = generate_scenario_dataset()
    graphs, metadata = _graphs(heterodata_builder, dataset)
    records = _with_feature_schema(_raw(dataset), metadata)
    basal, intervention = sorted(graphs)
    graphs[intervention]["taxon", "has_capacity", "function"].edge_index[1, 0] = 999

    delivered, report = prepare_graphs_for_model(records, graphs)

    assert set(delivered) == {basal}
    assert [finding.rule_id for finding in report.blocking_findings(intervention)] == ["TEN-04"]


def test_graphs_with_record_errors_are_not_converted(heterodata_builder: Builder) -> None:
    dataset = generate_scenario_dataset()
    graphs, metadata = _graphs(heterodata_builder, dataset)
    records = _with_feature_schema(_raw(dataset), metadata)
    basal, intervention = sorted(graphs)
    next(edge for edge in records.edges if edge["graph_id"] == intervention)["evidence_id"] = ""
    graphs[intervention]["taxon"].x[0, 0] = float("nan")

    delivered, report = prepare_graphs_for_model(records, graphs)

    assert set(delivered) == {basal}
    assert "TEN-10" not in _rules(report)
    assert report.not_evaluated[f"TEN:{intervention}"].startswith("errores de registro")


def test_missing_heterodata_is_reported_as_not_evaluated(heterodata_builder: Builder) -> None:
    dataset = generate_scenario_dataset()
    graphs, metadata = _graphs(heterodata_builder, dataset)
    records = _with_feature_schema(_raw(dataset), metadata)
    basal, intervention = sorted(graphs)
    del graphs[intervention]

    delivered, report = prepare_graphs_for_model(records, graphs)

    assert set(delivered) == {basal}
    assert report.not_evaluated[f"TEN:{intervention}"] == (
        "no se entregó el HeteroData de la instancia"
    )


def test_heterodata_without_instance_is_rejected(heterodata_builder: Builder) -> None:
    dataset = generate_synthetic_dataset()
    graphs, _ = _graphs(heterodata_builder, dataset)
    graphs["synthetic:graph:9999"] = next(iter(graphs.values()))

    with pytest.raises(ValueError, match="synthetic:graph:9999"):
        validate_graph(dataset, heterodata=graphs)


@pytest.mark.parametrize(
    ("output_records", "rule_id"),
    [([{"graph_id": "synthetic:graph:0001"}], "OUT-01"), ("not-a-list", "OUT-01")],
    ids=["invalid-record", "not-a-list"],
)
def test_output_records_of_the_graph_are_validated(
    heterodata_builder: Builder, output_records: Any, rule_id: str
) -> None:
    dataset = generate_synthetic_dataset()
    graphs, metadata = _graphs(heterodata_builder, dataset)
    records = _with_feature_schema(_raw(dataset), metadata)
    next(iter(graphs.values())).output_records = output_records

    report = validate_graph(records, heterodata=graphs)

    output_findings = [f for f in report.findings if f.location.get("source") == "output_records"]
    assert output_findings
    assert output_findings[0].rule_id == rule_id
    assert report.deliverable_graph_ids == ()
