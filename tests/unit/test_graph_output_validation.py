"""Pruebas de las reglas de salidas y targets (VG-07).

Cada regla OUT-01 a OUT-04 se prueba alterando un solo campo de una salida válida, que apunta
a un metabolito de un grafo sintético. Una salida sintética nunca es una medición.
"""

from __future__ import annotations

import copy
import json
import math
from typing import Any

import pytest

from nutrigraphdt.data.synthetic import OutputRecord, generate_synthetic_dataset
from nutrigraphdt.graph.validation import Finding, Severity, find_output_findings

Record = dict[str, Any]

DATASET = generate_synthetic_dataset()
GRAPH_ID = DATASET.instances[0].graph_id
METABOLITE = next(node.node_id for node in DATASET.nodes if node.node_type == "metabolite")


def _output(**changes: Any) -> Record:
    record: Record = {
        "graph_id": GRAPH_ID,
        "target_type": "metabolite",
        "target_id": METABOLITE,
        "value": 12.5,
        "measured_or_predicted": "synthetic",
        "unit": "umol/g",
        "sample_matrix": "cecal_content",
        "model_version": None,
    }
    record.update(changes)
    return record


def _findings(*outputs: Any, instances: Any = None, source: Any = "outputs") -> list[Finding]:
    return find_output_findings(
        list(outputs),
        DATASET.nodes,
        DATASET.instances if instances is None else instances,
        source=source,
    )


def _only(findings: list[Finding], rule_id: str) -> Finding:
    assert [finding.rule_id for finding in findings] == [rule_id], findings
    return findings[0]


# ---------------------------------------------------------------------------
# Salidas válidas
# ---------------------------------------------------------------------------


def test_valid_outputs_have_no_findings() -> None:
    predicted = _output(measured_or_predicted="predicted", model_version="synthetic-gnn-0.1")
    record = OutputRecord.from_dict(_output(target_id=METABOLITE))

    assert _findings(_output(), predicted, record) == []


def test_measured_outputs_are_admitted_in_non_synthetic_instances() -> None:
    instances = [{**DATASET.instances[0].to_dict(), "is_synthetic": False}]

    assert _findings(_output(measured_or_predicted="measured"), instances=instances) == []


def test_does_not_modify_the_outputs() -> None:
    outputs = [_output(value=math.nan), _output(unit="")]
    before = copy.deepcopy(outputs)

    find_output_findings(outputs, DATASET.nodes, DATASET.instances)

    assert json.dumps(outputs) == json.dumps(before)


def test_location_identifies_the_source_and_position() -> None:
    finding = _only(_findings(_output(), _output(unit=""), source="output_records"), "OUT-04")

    assert finding.location == {
        "source": "output_records",
        "output_index": 1,
        "target_type": "metabolite",
        "target_id": METABOLITE,
        "field": "unit",
    }
    assert finding.graph_id == GRAPH_ID
    assert json.loads(json.dumps(finding.to_dict(), allow_nan=False)) == finding.to_dict()


# ---------------------------------------------------------------------------
# OUT-01 a OUT-04
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "changes",
    [
        {"target_id": "synthetic:metabolite:9999"},
        {"target_type": "taxon"},
        {"graph_id": "synthetic:graph:9999"},
    ],
    ids=["missing-node", "wrong-type", "other-instance"],
)
def test_out01_detects_a_target_that_does_not_exist(changes: Record) -> None:
    finding = _only(_findings(_output(**changes)), "OUT-01")

    assert finding.severity is Severity.ERROR
    assert finding.observed == "nodo inexistente"


@pytest.mark.parametrize("field", ["graph_id", "target_type", "target_id"])
@pytest.mark.parametrize("value", ["", None, 3])
def test_out01_detects_an_identifier_that_is_not_text(field: str, value: Any) -> None:
    finding = _only(_findings(_output(**{field: value})), "OUT-01")

    assert finding.location["field"] == field


@pytest.mark.parametrize("value", [None, [], "output"])
def test_out01_detects_an_output_that_is_not_an_object(value: Any) -> None:
    finding = _only(_findings(value), "OUT-01")

    assert finding.location == {"source": "outputs", "output_index": 0}


@pytest.mark.parametrize("kind", ["observed", "", None, ["synthetic"]])
def test_out02_detects_an_unknown_origin(kind: Any) -> None:
    finding = _only(_findings(_output(measured_or_predicted=kind)), "OUT-02")

    assert finding.location["field"] == "measured_or_predicted"


@pytest.mark.parametrize(
    "changes",
    [
        {"measured_or_predicted": "predicted", "model_version": None},
        {"measured_or_predicted": "predicted", "model_version": ""},
        {"model_version": "synthetic-gnn-0.1"},
    ],
    ids=["prediction-without-version", "empty-version", "version-without-prediction"],
)
def test_out02_detects_an_inconsistent_model_version(changes: Record) -> None:
    finding = _only(_findings(_output(**changes)), "OUT-02")

    assert finding.location["field"] == "model_version"


def test_out02_requires_the_model_version_key() -> None:
    record = _output()
    del record["model_version"]

    finding = _only(_findings(record), "OUT-02")

    assert finding.observed == "campo ausente"


def test_out03_detects_a_measured_output_in_a_synthetic_instance() -> None:
    finding = _only(_findings(_output(measured_or_predicted="measured")), "OUT-03")

    assert finding.severity is Severity.ERROR
    assert finding.observed == '"measured"'


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("unit", ""),
        ("unit", None),
        ("sample_matrix", 5),
        ("value", math.nan),
        ("value", math.inf),
        ("value", True),
        ("value", "12.5"),
    ],
)
def test_out04_detects_invalid_unit_matrix_or_value(field: str, value: Any) -> None:
    finding = _only(_findings(_output(**{field: value})), "OUT-04")

    assert finding.location["field"] == field
