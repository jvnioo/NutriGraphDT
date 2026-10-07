"""Pruebas del validador de nodos, identificadores y atributos obligatorios (VG-02).

Cada regla NOD-01 a NOD-12 e INS-01 a INS-04 de `docs/graph/graph-integrity-rules.md` tiene casos
negativos construidos alterando un solo campo de un grafo sintético válido. Casi todos exigen
exactamente el hallazgo esperado, para detectar también falsos positivos y duplicados. Los
grafos válidos no deben producir ningún hallazgo.

Las pruebas verifican estructura, no validez biológica.
"""

from __future__ import annotations

import copy
import json
import math
from collections.abc import Callable
from dataclasses import dataclass, fields, replace
from typing import Any

import pytest

from nutrigraphdt.data.schema import OBSERVED_SCENARIO_ID
from nutrigraphdt.data.synthetic import (
    AdditiveAttributes,
    DietAttributes,
    FunctionAttributes,
    HostAttributes,
    MetaboliteAttributes,
    NodeCountConfig,
    NodeType,
    PhenotypeAttributes,
    SubstrateAttributes,
    SyntheticEdgeConfig,
    SyntheticNodeConfig,
    TaxonAttributes,
    generate_scenario_dataset,
    generate_synthetic_dataset,
)
from nutrigraphdt.graph.validation import (
    NODE_ATTRIBUTE_CONTRACT,
    Finding,
    Severity,
    find_node_findings,
)

Record = dict[str, Any]

# Clases de atributos del generador (DS-02): fuente independiente para los atributos
# obligatorios, distinta de la tabla transcrita en el validador.
ATTRIBUTE_CLASSES: dict[str, type] = {
    NodeType.DIET.value: DietAttributes,
    NodeType.ADDITIVE.value: AdditiveAttributes,
    NodeType.SUBSTRATE.value: SubstrateAttributes,
    NodeType.TAXON.value: TaxonAttributes,
    NodeType.FUNCTION.value: FunctionAttributes,
    NodeType.METABOLITE.value: MetaboliteAttributes,
    NodeType.HOST.value: HostAttributes,
    NodeType.PHENOTYPE.value: PhenotypeAttributes,
}

REQUIRED_ATTRIBUTES = [
    (node_type, attribute.name)
    for node_type, cls in ATTRIBUTE_CLASSES.items()
    for attribute in fields(cls)
]


@dataclass
class Graph:
    """Copia mutable, con la forma de los registros JSONL, de un grafo sintético válido."""

    instances: list[Record]
    nodes: list[Record]
    metadata: Record

    @property
    def instance(self) -> Record:
        return self.instances[0]

    def node(self, node_type: str, position: int = 0) -> Record:
        return [node for node in self.nodes if node["node_type"] == node_type][position]

    def index(self, node: Record) -> int:
        return next(index for index, candidate in enumerate(self.nodes) if candidate is node)

    def findings(self, *, with_metadata: bool = True) -> list[Finding]:
        metadata = self.metadata if with_metadata else None
        return find_node_findings(self.instances, self.nodes, metadata=metadata)


@pytest.fixture
def graph() -> Graph:
    dataset = generate_synthetic_dataset()
    return Graph(
        instances=[instance.to_dict() for instance in dataset.instances],
        nodes=copy.deepcopy([node.to_dict() for node in dataset.nodes]),
        metadata=copy.deepcopy(dataset.metadata),
    )


def _only(findings: list[Finding], rule_id: str) -> Finding:
    """Exige un único hallazgo, de la regla indicada, y lo devuelve."""
    assert [finding.rule_id for finding in findings] == [rule_id], findings
    return findings[0]


def _set_path(attributes: Record, path: str, value: Any) -> None:
    *parents, leaf = path.split(".")
    for part in parents:
        attributes = attributes[part]
    attributes[leaf] = value


# ---------------------------------------------------------------------------
# Grafos válidos: sin hallazgos
# ---------------------------------------------------------------------------


def test_default_synthetic_graph_has_no_findings(graph: Graph) -> None:
    assert graph.findings() == []
    assert graph.findings(with_metadata=False) == []


def test_scenario_dataset_has_no_findings() -> None:
    dataset = generate_scenario_dataset()

    assert find_node_findings(dataset.instances, dataset.nodes, metadata=dataset.metadata) == []


@pytest.mark.parametrize("seed", [1, 7, 42, 99])
@pytest.mark.parametrize(
    "counts",
    [
        NodeCountConfig(),
        NodeCountConfig(
            diet=1,
            additive=1,
            substrate=1,
            taxon=1,
            function=1,
            metabolite=1,
            host=1,
            phenotype=1,
        ),
        # Supera los catálogos: sufijos `_NN`, aditivo de control y varios huéspedes.
        NodeCountConfig(
            diet=3,
            additive=6,
            substrate=10,
            taxon=14,
            function=11,
            metabolite=8,
            host=2,
            phenotype=5,
        ),
    ],
    ids=["default", "minimal", "beyond-catalog"],
)
def test_generated_graphs_have_no_findings(seed: int, counts: NodeCountConfig) -> None:
    dataset = generate_synthetic_dataset(
        SyntheticNodeConfig(random_seed=seed, counts=counts),
        SyntheticEdgeConfig(random_seed=seed),
    )

    assert find_node_findings(dataset.instances, dataset.nodes, metadata=dataset.metadata) == []


# ---------------------------------------------------------------------------
# Comportamiento general
# ---------------------------------------------------------------------------


def test_node_objects_and_jsonl_records_give_the_same_findings() -> None:
    dataset = generate_synthetic_dataset()
    nodes = [
        replace(node, node_id="taxon-0001") if node.node_id == "synthetic:taxon:0001" else node
        for node in dataset.nodes
    ]

    from_objects = find_node_findings(dataset.instances, nodes, metadata=dataset.metadata)
    from_records = find_node_findings(
        [instance.to_dict() for instance in dataset.instances],
        [node.to_dict() for node in nodes],
        metadata=dataset.metadata,
    )

    assert from_objects == from_records
    assert [finding.rule_id for finding in from_objects] == ["NOD-04"]


def test_reports_every_finding_not_only_the_first(graph: Graph) -> None:
    graph.instance["scenario_id"] = "treatment"
    graph.node("taxon", 0)["node_type"] = "microbe"
    del graph.node("metabolite")["attributes"]["unit"]
    graph.node("substrate")["attributes"]["quantity"] = -1.0

    rule_ids = sorted(finding.rule_id for finding in graph.findings())

    assert rule_ids == ["INS-03", "NOD-01", "NOD-05", "NOD-10"]


def test_does_not_modify_the_records(graph: Graph) -> None:
    graph.node("taxon")["attributes"]["abundance"] = None
    graph.node("function")["attributes"]["extra"] = "value"
    graph.node("diet")["attributes"]["composition"][0].pop("unit")
    graph.nodes.append(copy.deepcopy(graph.node("host")))
    snapshot = copy.deepcopy((graph.instances, graph.nodes, graph.metadata))

    assert graph.findings()
    assert (graph.instances, graph.nodes, graph.metadata) == snapshot


def test_findings_are_json_serializable(graph: Graph) -> None:
    graph.node("taxon")["attributes"]["abundance"] = math.nan
    graph.node("host")["attributes"]["covariates"]["body_weight_g"] = math.inf
    graph.instance["is_synthetic"] = "yes"

    findings = graph.findings()
    serialized = json.loads(json.dumps([finding.to_dict() for finding in findings]))

    assert {record["rule_id"] for record in serialized} == {"INS-02", "NOD-05"}
    assert {record["severity"] for record in serialized} == {"ERROR"}
    assert {record["observed"] for record in serialized} == {'"yes"', "NaN", "Infinity"}


def test_severities_use_the_values_of_the_specification() -> None:
    assert [severity.value for severity in Severity] == ["ERROR", "ADVERTENCIA", "INFO"]


def test_attribute_contract_matches_the_node_attribute_classes() -> None:
    assert set(NODE_ATTRIBUTE_CONTRACT) == {node_type.value for node_type in NodeType}
    for node_type, cls in ATTRIBUTE_CLASSES.items():
        assert set(NODE_ATTRIBUTE_CONTRACT[node_type]) == {field.name for field in fields(cls)}


# ---------------------------------------------------------------------------
# INS-01 a INS-04
# ---------------------------------------------------------------------------


def test_ins01_detects_repeated_graph_id(graph: Graph) -> None:
    graph.instances.append(dict(graph.instance))

    finding = _only(graph.findings(), "INS-01")

    assert finding.severity is Severity.ERROR
    assert finding.graph_id == graph.instance["graph_id"]
    assert finding.location == {"instance_indices": [0, 1], "field": "graph_id"}


@pytest.mark.parametrize(
    "field",
    [
        "species",
        "gut_segment",
        "study_id",
        "sample_id",
        "scenario_id",
        "diet_treatment",
        "timepoint",
        "is_synthetic",
        "schema_version",
        "generator_version",
    ],
)
def test_ins01_detects_missing_instance_field(graph: Graph, field: str) -> None:
    del graph.instance[field]

    finding = _only(graph.findings(), "INS-01")

    assert finding.location == {"instance_index": 0, "field": field}
    assert finding.observed == "campo ausente"


def test_ins01_missing_graph_id_leaves_nodes_without_instance(graph: Graph) -> None:
    del graph.instance["graph_id"]

    findings = graph.findings()

    assert findings[0].rule_id == "INS-01"
    assert findings[0].graph_id is None
    assert findings[0].location == {"instance_index": 0, "field": "graph_id"}
    orphan_nodes = [finding for finding in findings[1:] if finding.rule_id == "NOD-02"]
    assert len(orphan_nodes) == len(graph.nodes) == len(findings) - 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("species", None),
        ("study_id", 7),
        ("sample_id", ""),
        ("scenario_id", 3),
        ("diet_treatment", None),
        ("timepoint", 42),
        ("timepoint", ""),
        ("generator_version", ["0.1.0"]),
    ],
)
def test_ins01_detects_wrong_instance_field_type(graph: Graph, field: str, value: Any) -> None:
    graph.instance[field] = value

    finding = _only(graph.findings(), "INS-01")

    assert finding.location == {"instance_index": 0, "field": field}


@pytest.mark.parametrize("timepoint", [None, "day_42"])
def test_ins01_admits_null_or_text_timepoint(graph: Graph, timepoint: str | None) -> None:
    graph.instance["timepoint"] = timepoint

    assert graph.findings() == []


def test_ins01_detects_an_instance_that_is_not_an_object(graph: Graph) -> None:
    graph.instances.append(["synthetic:graph:0002"])  # type: ignore[arg-type]

    finding = _only(graph.findings(), "INS-01")

    assert finding.location == {"instance_index": 1}
    assert finding.observed == "list"


@pytest.mark.parametrize(
    ("field", "value"),
    [("schema_version", "2.0.0"), ("schema_version", 1), ("is_synthetic", "true")],
)
def test_ins02_detects_incompatible_version_or_non_boolean_origin(
    graph: Graph, field: str, value: Any
) -> None:
    graph.instance[field] = value

    finding = _only(graph.findings(), "INS-02")

    assert finding.location == {"instance_index": 0, "field": field}


def _make_real(graph: Graph) -> None:
    """Convierte la instancia en real: desde las reglas 1.2.0, su escenario es `observed`."""
    graph.instance["is_synthetic"] = False
    graph.instance["scenario_id"] = OBSERVED_SCENARIO_ID


def test_ins02_admits_non_synthetic_instances(graph: Graph) -> None:
    _make_real(graph)

    assert graph.findings() == []


@pytest.mark.parametrize("scenario_id", ["basal", "intervention", "unknown"])
def test_ins03_real_instances_are_observations(graph: Graph, scenario_id: str) -> None:
    graph.instance["is_synthetic"] = False
    graph.instance["scenario_id"] = scenario_id

    finding = _only(graph.findings(), "INS-03")

    assert finding.expected == f'uno de ["{OBSERVED_SCENARIO_ID}"]'


def test_ins03_synthetic_instances_cannot_claim_to_be_observed(graph: Graph) -> None:
    graph.instance["scenario_id"] = OBSERVED_SCENARIO_ID

    _only(graph.findings(), "INS-03")


def test_ins03_detects_unknown_scenario(graph: Graph) -> None:
    graph.instance["scenario_id"] = "treatment"

    finding = _only(graph.findings(), "INS-03")

    assert finding.observed == '"treatment"'


@pytest.mark.parametrize(("attribute", "value"), [("species", "pig"), ("gut_segment", "ileum")])
def test_ins04_detects_host_context_different_from_instance(
    graph: Graph, attribute: str, value: str
) -> None:
    host = graph.node("host")
    host["attributes"][attribute] = value

    finding = _only(graph.findings(), "INS-04")

    assert finding.severity is Severity.ERROR
    assert finding.location == {
        "node_index": graph.index(host),
        "node_type": "host",
        "node_id": host["node_id"],
        "attribute": attribute,
    }
    assert finding.expected == json.dumps(graph.instance[attribute])
    assert finding.observed == json.dumps(value)


# ---------------------------------------------------------------------------
# NOD-01 a NOD-04: tipos e identificadores
# ---------------------------------------------------------------------------


def test_nod01_detects_unknown_node_type_and_skips_its_attributes(graph: Graph) -> None:
    node = graph.node("taxon")
    node["node_type"] = "microbe"
    node["attributes"] = {"abundance": "not-a-number"}

    finding = _only(graph.findings(), "NOD-01")

    assert finding.severity is Severity.ERROR
    assert finding.location == {
        "node_index": graph.index(node),
        "node_type": "microbe",
        "node_id": node["node_id"],
        "field": "node_type",
    }


@pytest.mark.parametrize("value", [None, "", 3])
def test_nod01_detects_invalid_node_type(graph: Graph, value: Any) -> None:
    graph.node("taxon")["node_type"] = value

    _only(graph.findings(), "NOD-01")


@pytest.mark.parametrize("field", ["graph_id", "node_id", "source_id"])
@pytest.mark.parametrize("value", ["", None, 5, "<absent>"])
def test_nod02_detects_invalid_identifier(graph: Graph, field: str, value: Any) -> None:
    node = graph.node("taxon")
    if value == "<absent>":
        del node[field]
    else:
        node[field] = value

    finding = _only(graph.findings(), "NOD-02")

    assert finding.location["field"] == field
    assert finding.location["node_index"] == graph.index(node)


def test_nod02_detects_graph_id_without_instance(graph: Graph) -> None:
    graph.node("taxon")["graph_id"] = "synthetic:graph:9999"

    finding = _only(graph.findings(), "NOD-02")

    assert finding.graph_id == "synthetic:graph:9999"
    assert finding.expected == "el graph_id de una instancia existente"


def test_nod02_detects_a_node_that_is_not_an_object(graph: Graph) -> None:
    graph.nodes.append("synthetic:taxon:0099")  # type: ignore[arg-type]

    finding = _only(graph.findings(), "NOD-02")

    assert finding.location == {"node_index": len(graph.nodes) - 1}


def test_nod03_detects_repeated_node_id_within_type(graph: Graph) -> None:
    first = graph.node("taxon", 0)
    second = graph.node("taxon", 1)
    second["node_id"] = first["node_id"]

    finding = _only(graph.findings(), "NOD-03")

    assert finding.location == {
        "node_type": "taxon",
        "node_id": first["node_id"],
        "node_indices": [graph.index(first), graph.index(second)],
    }
    assert finding.observed == "2 apariciones"


def test_nod03_admits_the_same_node_id_in_different_types(graph: Graph) -> None:
    graph.node("function")["node_id"] = graph.node("taxon")["node_id"]

    assert graph.findings() == []


def test_nod04_detects_node_id_without_synthetic_prefix(graph: Graph) -> None:
    graph.node("taxon")["node_id"] = "taxon:0001"

    finding = _only(graph.findings(), "NOD-04")

    assert finding.location["field"] == "node_id"


@pytest.mark.parametrize(
    ("node_type", "attribute"),
    [
        ("substrate", "chemical_id"),
        ("taxon", "taxonomy_id"),
        ("function", "function_id"),
        ("metabolite", "chemical_id"),
    ],
)
def test_nod04_detects_domain_id_without_synthetic_prefix(
    graph: Graph, node_type: str, attribute: str
) -> None:
    graph.node(node_type)["attributes"][attribute] = "ACCESSION:0001"

    finding = _only(graph.findings(), "NOD-04")

    assert finding.location["attribute"] == attribute
    assert finding.observed == '"ACCESSION:0001"'


def test_nod04_is_not_evaluated_on_non_synthetic_instances(graph: Graph) -> None:
    _make_real(graph)
    graph.node("taxon")["node_id"] = "taxon:0001"
    graph.node("taxon")["attributes"]["taxonomy_id"] = "ACCESSION:0001"

    assert graph.findings() == []


# ---------------------------------------------------------------------------
# NOD-05 a NOD-07: atributos obligatorios y ausencias
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("node_type", "attribute"), REQUIRED_ATTRIBUTES)
def test_nod05_detects_missing_required_attribute(
    graph: Graph, node_type: str, attribute: str
) -> None:
    node = graph.node(node_type)
    del node["attributes"][attribute]

    finding = _only(graph.findings(), "NOD-05")

    assert finding.severity is Severity.ERROR
    assert finding.graph_id == graph.instance["graph_id"]
    assert finding.location == {
        "node_index": graph.index(node),
        "node_type": node_type,
        "node_id": node["node_id"],
        "attribute": attribute,
    }
    assert finding.observed == "campo ausente"


@pytest.mark.parametrize(
    ("node_type", "attribute", "value"),
    [
        ("taxon", "abundance", "0.3"),
        ("taxon", "abundance", True),
        ("taxon", "abundance", math.nan),
        ("metabolite", "concentration", math.inf),
        ("substrate", "unit", ""),
        ("phenotype", "trait", 7),
        ("host", "covariates", []),
        ("diet", "ingredients", ["corn", 3]),
        ("diet", "composition", {}),
    ],
)
def test_nod05_detects_attribute_with_wrong_type(
    graph: Graph, node_type: str, attribute: str, value: Any
) -> None:
    graph.node(node_type)["attributes"][attribute] = value

    finding = _only(graph.findings(), "NOD-05")

    assert finding.location["attribute"] == attribute


def test_nod05_detects_non_finite_number_inside_an_object(graph: Graph) -> None:
    graph.node("host")["attributes"]["covariates"]["body_weight_g"] = -math.inf

    finding = _only(graph.findings(), "NOD-05")

    assert finding.location["attribute"] == "covariates.body_weight_g"
    assert finding.observed == "-Infinity"


@pytest.mark.parametrize("value", [None, [], "attributes", "<absent>"])
def test_nod05_detects_attributes_that_are_not_an_object(graph: Graph, value: Any) -> None:
    node = graph.node("taxon")
    if value == "<absent>":
        del node["attributes"]
    else:
        node["attributes"] = value

    finding = _only(graph.findings(), "NOD-05")

    assert finding.location["field"] == "attributes"


def test_nod05_admits_null_value_marked_as_missing(graph: Graph) -> None:
    node = graph.node("taxon")
    node["attributes"]["abundance"] = None
    node["missing_mask"] = {"abundance": True}

    finding = _only(graph.findings(), "NOD-08")

    assert finding.severity is Severity.WARNING


MutateComposition = Callable[[list[Any]], object]


@pytest.mark.parametrize(
    ("mutate", "path"),
    [
        (lambda composition: composition[0].pop("unit"), "composition[0].unit"),
        (lambda composition: composition[1].update(unit=""), "composition[1].unit"),
        (lambda composition: composition[0].update(value=math.nan), "composition[0].value"),
        (lambda composition: composition[0].update(value=None), "composition[0].value"),
        (lambda composition: composition[0].update(value=False), "composition[0].value"),
        (lambda composition: composition[2].update(component_id=5), "composition[2].component_id"),
        (lambda composition: composition.__setitem__(0, "crude_protein"), "composition[0]"),
    ],
)
def test_nod06_detects_invalid_composition_item(
    graph: Graph, mutate: MutateComposition, path: str
) -> None:
    mutate(graph.node("diet")["attributes"]["composition"])

    finding = _only(graph.findings(), "NOD-06")

    assert finding.severity is Severity.ERROR
    assert finding.location["attribute"] == path


@pytest.mark.parametrize("mask", [{}, {"abundance": False}])
def test_nod07_detects_null_value_without_mask(graph: Graph, mask: dict[str, bool]) -> None:
    node = graph.node("taxon")
    node["attributes"]["abundance"] = None
    node["missing_mask"] = mask

    finding = _only(graph.findings(), "NOD-07")

    assert finding.location["attribute"] == "abundance"


def test_nod07_detects_mask_true_on_a_present_value(graph: Graph) -> None:
    graph.node("taxon")["missing_mask"] = {"abundance": True}

    findings = graph.findings()

    assert [finding.rule_id for finding in findings] == ["NOD-07", "NOD-08"]
    assert findings[0].expected == "valor null cuando la máscara es true"


def test_nod07_detects_mask_key_without_attribute(graph: Graph) -> None:
    graph.node("taxon")["missing_mask"] = {"abundancia": False}

    finding = _only(graph.findings(), "NOD-07")

    assert finding.location["attribute"] == "abundancia"


@pytest.mark.parametrize("abundance", [0.25, None])
def test_nod07_detects_non_boolean_mask_once(graph: Graph, abundance: float | None) -> None:
    node = graph.node("taxon")
    node["attributes"]["abundance"] = abundance
    node["missing_mask"] = {"abundance": "yes"}

    finding = _only(graph.findings(), "NOD-07")

    assert finding.expected == "un booleano"


@pytest.mark.parametrize("value", [None, [], "<absent>"])
def test_nod07_detects_missing_mask_that_is_not_an_object(graph: Graph, value: Any) -> None:
    node = graph.node("taxon")
    if value == "<absent>":
        del node["missing_mask"]
    else:
        node["missing_mask"] = value

    finding = _only(graph.findings(), "NOD-07")

    assert finding.location["field"] == "missing_mask"


def test_nod07_resolves_nested_mask_paths(graph: Graph) -> None:
    host = graph.node("host")
    host["attributes"]["covariates"]["sex"] = None

    assert _only(graph.findings(), "NOD-07").location["attribute"] == "covariates.sex"

    host["missing_mask"] = {"covariates.sex": True}

    assert _only(graph.findings(), "NOD-08").location["attribute"] == "covariates.sex"


# ---------------------------------------------------------------------------
# NOD-08 a NOD-12: advertencias y cobertura de tipos
# ---------------------------------------------------------------------------


def test_nod08_counts_missing_values_by_type_and_attribute(graph: Graph) -> None:
    missing = [graph.node("taxon", 0), graph.node("taxon", 3)]
    for node in missing:
        node["attributes"]["abundance"] = None
        node["missing_mask"] = {"abundance": True}

    finding = _only(graph.findings(), "NOD-08")

    assert finding.severity is Severity.WARNING
    assert finding.location == {
        "node_type": "taxon",
        "attribute": "abundance",
        "node_ids": [node["node_id"] for node in missing],
    }
    assert finding.observed.startswith("2 nodo(s)")


def test_nod09_warns_about_attributes_outside_the_contract(graph: Graph) -> None:
    graph.node("taxon")["attributes"].update(colour="red", alias="t1")

    finding = _only(graph.findings(), "NOD-09")

    assert finding.severity is Severity.WARNING
    assert finding.location["attributes"] == ["alias", "colour"]


@pytest.mark.parametrize(
    ("node_type", "path"),
    [
        ("additive", "dose"),
        ("substrate", "quantity"),
        ("taxon", "abundance"),
        ("function", "annotation_value"),
        ("metabolite", "concentration"),
        ("host", "covariates.body_weight_g"),
    ],
)
def test_nod10_warns_about_negative_magnitudes(graph: Graph, node_type: str, path: str) -> None:
    _set_path(graph.node(node_type)["attributes"], path, -0.5)

    finding = _only(graph.findings(), "NOD-10")

    assert finding.severity is Severity.WARNING
    assert finding.location["attribute"] == path


def test_nod10_admits_zero_and_ignores_magnitudes_outside_the_rule(graph: Graph) -> None:
    graph.node("additive")["attributes"]["dose"] = 0.0
    graph.node("phenotype")["attributes"]["value"] = -1.0

    assert graph.findings() == []


def test_nod11_warns_about_values_outside_declared_vocabularies(graph: Graph) -> None:
    graph.node("function")["attributes"]["function_type"] = "operon"

    finding = _only(graph.findings(), "NOD-11")

    assert finding.severity is Severity.WARNING
    assert finding.location["attribute"] == "function_type"
    assert graph.findings(with_metadata=False) == []


def test_nod11_treats_undeclared_vocabularies_as_empty(graph: Graph) -> None:
    del graph.metadata["vocabularies"]
    function_nodes = [node for node in graph.nodes if node["node_type"] == "function"]

    findings = graph.findings()

    assert {finding.rule_id for finding in findings} == {"NOD-11"}
    assert len(findings) == 2 * len(function_nodes)


@pytest.mark.parametrize(
    ("is_synthetic", "severity"), [(True, Severity.ERROR), (False, Severity.WARNING)]
)
def test_nod12_detects_missing_node_types(
    graph: Graph, is_synthetic: bool, severity: Severity
) -> None:
    if is_synthetic:
        graph.instance["is_synthetic"] = True
    else:
        _make_real(graph)
    graph.nodes = [node for node in graph.nodes if node["node_type"] not in {"host", "diet"}]

    finding = _only(graph.findings(), "NOD-12")

    assert finding.severity is severity
    assert finding.location == {"instance_index": 0, "node_types": ["diet", "host"]}
