"""Pruebas de las reglas de escenarios comparables y de metadatos (VG-07, VG-08).

INS-05 a INS-07 comparan la instancia `intervention` con la `basal` del mismo `sample_id`. MET-01
a MET-03 comparan `metadata.json` con los registros. Los casos negativos alteran un solo campo de
un dataset válido y exigen el hallazgo esperado.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

import pytest

from nutrigraphdt.data.synthetic import (
    INTERVENTION_VARIABLE,
    generate_scenario_dataset,
    generate_synthetic_dataset,
)
from nutrigraphdt.graph.validation import (
    Finding,
    Severity,
    find_metadata_findings,
    find_scenario_findings,
)
from nutrigraphdt.graph.validation.dataset import METADATA_FIELDS, intervened_variable

Record = dict[str, Any]


@dataclass
class Dataset:
    """Copia mutable, con la forma de los registros JSONL, de un dataset válido."""

    metadata: Record
    instances: list[Record]
    nodes: list[Record]
    edges: list[Record]
    outputs: list[Record]

    def scenario_findings(self) -> list[Finding]:
        return find_scenario_findings(self.instances, self.nodes, self.edges)

    def metadata_findings(self) -> list[Finding]:
        return find_metadata_findings(
            self.metadata, self.instances, self.nodes, self.edges, self.outputs
        )

    def node(self, graph_id: str, node_type: str, position: int = 0) -> Record:
        return [
            node
            for node in self.nodes
            if node["graph_id"] == graph_id and node["node_type"] == node_type
        ][position]


def _copy(dataset: Any) -> Dataset:
    return Dataset(
        metadata=copy.deepcopy(dataset.metadata),
        instances=[instance.to_dict() for instance in dataset.instances],
        nodes=copy.deepcopy([node.to_dict() for node in dataset.nodes]),
        edges=copy.deepcopy([edge.to_dict() for edge in dataset.edges]),
        outputs=[output.to_dict() for output in dataset.outputs],
    )


def _aligned_scenarios() -> Dataset:
    """Escenarios cuya intervención solo cambia la variable declarada (sin INS-06 ni INS-07)."""
    dataset = _copy(generate_scenario_dataset())
    basal, intervention = (instance["graph_id"] for instance in dataset.instances)
    for records in (dataset.nodes, dataset.edges):
        for record in [record for record in records if record["graph_id"] == intervention]:
            records.remove(record)
        for record in [record for record in records if record["graph_id"] == basal]:
            twin = copy.deepcopy(record)
            twin["graph_id"] = intervention
            records.append(twin)
    diet = dataset.node(intervention, "diet")
    for item in diet["attributes"]["composition"]:
        if item["component_id"] == INTERVENTION_VARIABLE:
            item["value"] = 270.0
    return dataset


@pytest.fixture
def scenarios() -> Dataset:
    return _aligned_scenarios()


@pytest.fixture
def dataset() -> Dataset:
    return _copy(generate_scenario_dataset())


def _only(findings: list[Finding], rule_id: str) -> Finding:
    assert [finding.rule_id for finding in findings] == [rule_id], findings
    return findings[0]


def _ids(dataset: Dataset) -> tuple[str, str]:
    return dataset.instances[0]["graph_id"], dataset.instances[1]["graph_id"]


# ---------------------------------------------------------------------------
# INS-05 a INS-07
# ---------------------------------------------------------------------------


def test_scenarios_that_only_change_the_declared_variable_have_no_findings(
    scenarios: Dataset,
) -> None:
    assert scenarios.scenario_findings() == []


def test_generated_scenarios_have_no_unmodeled_differences() -> None:
    """Los escenarios generados no difieren fuera de la intervención declarada."""
    dataset = generate_scenario_dataset()

    findings = find_scenario_findings(dataset.instances, dataset.nodes, dataset.edges)

    assert findings == []


def test_single_instances_are_not_compared() -> None:
    dataset = generate_synthetic_dataset()

    assert find_scenario_findings(dataset.instances, dataset.nodes, dataset.edges) == []


def test_pairs_without_a_single_basal_instance_are_not_compared(scenarios: Dataset) -> None:
    scenarios.instances[1]["scenario_id"] = "basal"
    scenarios.node(_ids(scenarios)[1], "taxon")["node_id"] = "synthetic:taxon:0099"

    assert scenarios.scenario_findings() == []


def test_interventions_with_several_basal_instances_are_not_compared(scenarios: Dataset) -> None:
    basal, intervention = _ids(scenarios)
    twin = {**copy.deepcopy(scenarios.instances[0]), "graph_id": "synthetic:scenario:basal:0002"}
    scenarios.instances.append(twin)
    scenarios.node(intervention, "taxon")["node_id"] = "synthetic:taxon:0099"

    # Con dos instancias basal, no está definido contra cuál comparar.
    assert scenarios.scenario_findings() == []


def test_ins05_detects_different_node_ids(scenarios: Dataset) -> None:
    basal, intervention = _ids(scenarios)
    scenarios.node(intervention, "taxon")["node_id"] = "synthetic:taxon:0099"

    finding = _only(scenarios.scenario_findings(), "INS-05")

    assert finding.severity is Severity.ERROR
    assert finding.graph_id == intervention
    assert finding.location["basal_graph_id"] == basal
    assert finding.location["only_in_basal"] == ["synthetic:taxon:0001"]
    assert finding.location["only_in_intervention"] == ["synthetic:taxon:0099"]


def test_ins05_detects_a_node_type_missing_from_one_scenario(scenarios: Dataset) -> None:
    _, intervention = _ids(scenarios)
    scenarios.nodes = [
        node
        for node in scenarios.nodes
        if not (node["graph_id"] == intervention and node["node_type"] == "phenotype")
    ]

    finding = _only(scenarios.scenario_findings(), "INS-05")

    assert finding.location["node_type"] == "phenotype"
    assert finding.location["only_in_intervention"] == []


def test_ins05_detects_different_attribute_keys(scenarios: Dataset) -> None:
    _, intervention = _ids(scenarios)
    scenarios.node(intervention, "substrate")["attributes"]["extra"] = 1

    finding = _only(scenarios.scenario_findings(), "INS-05")

    assert finding.location["attributes_only_in_intervention"] == ["extra"]
    assert finding.location["attributes_only_in_basal"] == []


def test_ins06_warns_about_a_value_outside_the_declared_variable(scenarios: Dataset) -> None:
    _, intervention = _ids(scenarios)
    scenarios.node(intervention, "metabolite")["attributes"]["concentration"] = 99.0

    finding = _only(scenarios.scenario_findings(), "INS-06")

    assert finding.severity is Severity.WARNING
    assert finding.location["attribute"] == "concentration"
    assert finding.location["declared_variable"] == INTERVENTION_VARIABLE
    assert finding.observed == "intervención: 99.0"


def test_ins06_compares_nested_values(scenarios: Dataset) -> None:
    _, intervention = _ids(scenarios)
    covariates = scenarios.node(intervention, "host")["attributes"]["covariates"]
    covariates[next(iter(covariates))] = "otro valor"

    finding = _only(scenarios.scenario_findings(), "INS-06")

    assert finding.location["attribute"].startswith("covariates.")


def test_ins06_reports_another_diet_component(scenarios: Dataset) -> None:
    _, intervention = _ids(scenarios)
    composition = scenarios.node(intervention, "diet")["attributes"]["composition"]
    other = next(
        position
        for position, item in enumerate(composition)
        if item["component_id"] != INTERVENTION_VARIABLE
    )
    composition[other]["value"] += 1.0

    finding = _only(scenarios.scenario_findings(), "INS-06")

    assert finding.location["attribute"] == f"composition[{other}].value"


def test_ins06_reports_the_variable_when_diet_treatment_does_not_declare_it(
    scenarios: Dataset,
) -> None:
    scenarios.instances[1]["diet_treatment"] = "synthetic_protein_diet"

    finding = _only(scenarios.scenario_findings(), "INS-06")

    assert finding.location["declared_variable"] is None
    assert finding.location["attribute"].startswith("composition[")


def _intervention_edge(dataset: Dataset, relation: str) -> Record:
    intervention = dataset.instances[1]["graph_id"]
    return next(
        edge
        for edge in dataset.edges
        if edge["graph_id"] == intervention and edge["relation_type"] == relation
    )


def test_ins07_warns_about_an_edge_missing_from_the_intervention(scenarios: Dataset) -> None:
    basal, intervention = _ids(scenarios)
    edge = _intervention_edge(scenarios, "produces")
    scenarios.edges.remove(edge)

    finding = _only(scenarios.scenario_findings(), "INS-07")

    assert finding.severity is Severity.WARNING
    assert finding.graph_id == intervention
    assert finding.location["basal_graph_id"] == basal
    assert finding.location["edge_type"] == ["function", "produces", "metabolite"]
    assert finding.location["only_in_basal"] == [[edge["source_id"], edge["target_id"]]]
    assert finding.location["only_in_intervention_count"] == 0


def test_ins07_treats_a_reversed_edge_as_a_different_edge(scenarios: Dataset) -> None:
    edge = _intervention_edge(scenarios, "interacts_with")
    edge["source_id"], edge["target_id"] = edge["target_id"], edge["source_id"]

    finding = _only(scenarios.scenario_findings(), "INS-07")

    assert finding.location["only_in_basal_count"] == 1
    assert finding.location["only_in_intervention"] == [[edge["source_id"], edge["target_id"]]]


def test_ins07_ignores_edge_attributes(scenarios: Dataset) -> None:
    _intervention_edge(scenarios, "interacts_with")["attributes"]["interaction_type"] = "other"

    assert scenarios.scenario_findings() == []


def test_ins07_lists_a_bounded_number_of_edges() -> None:
    dataset = generate_scenario_dataset()

    findings = find_scenario_findings(dataset.instances, dataset.nodes, dataset.edges)

    for finding in (finding for finding in findings if finding.rule_id == "INS-07"):
        location = finding.location
        assert len(location["only_in_basal"]) == min(location["only_in_basal_count"], 10)
        assert len(location["only_in_intervention"]) == min(
            location["only_in_intervention_count"], 10
        )
        assert json.loads(json.dumps(finding.to_dict(), allow_nan=False)) == finding.to_dict()


@pytest.mark.parametrize(
    ("diet_treatment", "variable"),
    [
        ("synthetic_basal_diet:crude_protein=270.0", "crude_protein"),
        ("label:with:colons:fiber=1", "fiber"),
        ("synthetic_basal_diet", None),
        ("crude_protein=270", None),
        (None, None),
    ],
)
def test_intervened_variable_follows_the_exporter_convention(
    diet_treatment: Any, variable: str | None
) -> None:
    assert intervened_variable(diet_treatment) == variable


# ---------------------------------------------------------------------------
# MET-01 a MET-03
# ---------------------------------------------------------------------------


def test_exported_metadata_has_no_findings(dataset: Dataset) -> None:
    assert dataset.metadata_findings() == []
    single = _copy(generate_synthetic_dataset())
    assert single.metadata_findings() == []


def test_metadata_findings_are_dataset_level_errors(dataset: Dataset) -> None:
    dataset.metadata["random_seed"] = "42"
    dataset.metadata["is_synthetic"] = False
    dataset.metadata["counts"][dataset.instances[0]["graph_id"]]["outputs"] += 1

    findings = dataset.metadata_findings()

    assert [finding.rule_id for finding in findings] == ["MET-01", "MET-02", "MET-03"]
    for finding in findings:
        assert finding.severity is Severity.ERROR
        assert finding.graph_id is None
        assert json.loads(json.dumps(finding.to_dict(), allow_nan=False)) == finding.to_dict()


@pytest.mark.parametrize("name", METADATA_FIELDS)
def test_met01_detects_missing_minimal_field(dataset: Dataset, name: str) -> None:
    del dataset.metadata[name]

    finding = _only(dataset.metadata_findings(), "MET-01")

    assert finding.location == {"file": "metadata.json", "field": name}


@pytest.mark.parametrize(
    ("name", "value"),
    [("schema_version", "2.0.0"), ("random_seed", True), ("random_seed", 4.2)],
)
def test_met01_detects_incompatible_version_or_seed(
    dataset: Dataset, name: str, value: Any
) -> None:
    dataset.metadata[name] = value

    finding = _only(dataset.metadata_findings(), "MET-01")

    assert finding.location["field"] == name


def test_met01_admits_a_null_seed_in_a_real_dataset(dataset: Dataset) -> None:
    dataset.metadata["is_synthetic"] = False
    dataset.metadata["random_seed"] = None
    for instance in dataset.instances:
        instance["is_synthetic"] = False

    assert dataset.metadata_findings() == []


def test_met01_still_requires_an_integer_seed_in_a_synthetic_dataset(dataset: Dataset) -> None:
    dataset.metadata["random_seed"] = None

    finding = _only(dataset.metadata_findings(), "MET-01")

    assert finding.location["field"] == "random_seed"


@pytest.mark.parametrize("metadata", [None, [], "metadata"])
def test_met01_detects_metadata_that_is_not_an_object(dataset: Dataset, metadata: Any) -> None:
    dataset.metadata = metadata

    _only(dataset.metadata_findings(), "MET-01")


@pytest.mark.parametrize("value", [False, "true", 1])
def test_met02_detects_origin_different_from_the_instances(dataset: Dataset, value: Any) -> None:
    dataset.metadata["is_synthetic"] = value

    finding = _only(dataset.metadata_findings(), "MET-02")

    assert finding.location["graph_ids"] == sorted(
        instance["graph_id"] for instance in dataset.instances
    )


def test_met02_skips_instances_whose_origin_is_not_boolean(dataset: Dataset) -> None:
    dataset.instances[0]["is_synthetic"] = "yes"

    # INS-02 informa el valor; MET-02 no lo repite.
    assert dataset.metadata_findings() == []


def test_met03_detects_a_node_removed_after_export(dataset: Dataset) -> None:
    graph_id = dataset.instances[0]["graph_id"]
    dataset.nodes.remove(dataset.node(graph_id, "taxon"))

    finding = _only(dataset.metadata_findings(), "MET-03")

    assert finding.location == {
        "file": "metadata.json",
        "field": "counts",
        "graph_id": graph_id,
        "category": "nodes",
        "key": "taxon",
    }
    assert finding.expected.startswith("9 ")
    assert finding.observed.startswith("10 ")


def test_met03_treats_an_undeclared_type_as_zero(dataset: Dataset) -> None:
    graph_id = dataset.instances[0]["graph_id"]
    del dataset.metadata["counts"][graph_id]["nodes"]["taxon"]

    finding = _only(dataset.metadata_findings(), "MET-03")

    assert finding.location["key"] == "taxon"
    assert finding.observed == "0 (declarado en counts)"


def test_met03_detects_an_edge_added_after_export(dataset: Dataset) -> None:
    dataset.edges.append(copy.deepcopy(dataset.edges[0]))

    finding = _only(dataset.metadata_findings(), "MET-03")

    assert finding.location["category"] == "edges"


def test_met03_detects_undeclared_outputs(dataset: Dataset) -> None:
    dataset.outputs.append({"graph_id": dataset.instances[0]["graph_id"]})

    finding = _only(dataset.metadata_findings(), "MET-03")

    assert finding.location["category"] == "outputs"


def test_met03_detects_counts_of_unknown_or_missing_instances(dataset: Dataset) -> None:
    counts = dataset.metadata["counts"]
    first = dataset.instances[0]["graph_id"]
    counts["synthetic:graph:9999"] = counts.pop(first)

    findings = dataset.metadata_findings()

    assert [finding.rule_id for finding in findings] == ["MET-03", "MET-03"]
    assert {finding.location["graph_id"] for finding in findings} == {
        "synthetic:graph:9999",
        first,
    }


def test_met03_detects_counts_that_are_not_an_object(dataset: Dataset) -> None:
    dataset.metadata["counts"] = []

    finding = _only(dataset.metadata_findings(), "MET-03")

    assert finding.location == {"file": "metadata.json", "field": "counts"}
