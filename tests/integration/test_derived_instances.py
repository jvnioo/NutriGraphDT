"""Instancias derivadas de un animal real: `derived_from` e `intervention` (contrato v2 §7, #151).

Construye los registros reales del fixture de D1 (`tests/fixtures/holofood/`) y, a partir de la
observación de un animal, una instancia derivada **ficticia** que copia sus nodos y aristas
(como lo haría un simulador en F5). Comprueba que:

- una instancia real con `derived_from` se rechaza (INS-08);
- una derivada que cambia una variable no declarada se informa (INS-06), igual que una que no
  tiene el valor que declara;
- el escenario basal derivado de un animal Control sin cambios reproduce su observación (control
  de calidad del simulador): ningún hallazgo de comparación.
"""

from __future__ import annotations

import copy
import csv
import dataclasses
from pathlib import Path
from typing import Any

import pytest

from nutrigraphdt.data.config import load_sources
from nutrigraphdt.data.derived import DerivedVariable, intervention_problems
from nutrigraphdt.data.integration import attach_sample_context
from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader
from nutrigraphdt.data.pipeline import DataPipeline
from nutrigraphdt.data.schema import NormalizedInstanceRecord, NormalizedTabularDataset
from nutrigraphdt.data.synthetic.export import InstanceRecord
from nutrigraphdt.graph.builder import GraphRecords, records_from_tables
from nutrigraphdt.graph.validation import find_node_findings, find_scenario_findings

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "holofood"
SOURCES = load_sources(REPO_ROOT / "configs" / "sources.json")
CONTROL = "SAMEA112904772"  # tratamiento CC (Control) en tests/fixtures/holofood/metadata.tsv
Record = dict[str, Any]


def _source(source_id: str, file_name: str):  # type: ignore[no-untyped-def]
    return dataclasses.replace(SOURCES[source_id], path_or_url=str(FIXTURES / file_name))


@pytest.fixture(scope="module")
def tables() -> NormalizedTabularDataset:
    abundance = _source("D1_holofood", "abundance_ssu_caecum.tsv")
    base = DataPipeline({"D1_holofood": abundance}).run(["D1_holofood"]).dataset
    integrated, _ = attach_sample_context(
        base,
        metadata=MetadataLoader(_source("D1_holofood_metadata", "metadata.tsv")).load(),
        metabolites=MetaboliteLoader(
            _source("D1_holofood_scfa_content", "scfa_caecum_content.tsv")
        ).load(),
    )
    return integrated


@pytest.fixture(scope="module")
def real(tables: NormalizedTabularDataset) -> GraphRecords:
    return records_from_tables(tables)


def _derive(
    real: GraphRecords,
    sample_id: str = CONTROL,
    *,
    intervention: list[Record] | None = None,
    scenario_id: str = "basal",
) -> tuple[list[Record], list[Record], list[Record]]:
    """Registros reales + una instancia derivada que copia la observación de `sample_id`."""
    origin = next(i for i in real.instances if i["sample_id"] == sample_id)
    graph_id = f"synthetic:derived:{sample_id}:{scenario_id}"
    derived = {
        **origin,
        "graph_id": graph_id,
        "is_synthetic": True,
        "scenario_id": scenario_id,
        "derived_from": sample_id,
        "intervention": [] if intervention is None else intervention,
    }
    nodes = [
        {**copy.deepcopy(n), "graph_id": graph_id}
        for n in real.nodes
        if n["graph_id"] == origin["graph_id"]
    ]
    edges = [
        {**copy.deepcopy(e), "graph_id": graph_id}
        for e in real.edges
        if e["graph_id"] == origin["graph_id"]
    ]
    return (
        [*copy.deepcopy(real.instances), derived],
        [*copy.deepcopy(real.nodes), *nodes],
        [*copy.deepcopy(real.edges), *edges],
    )


def _node(nodes: list[Record], graph_id: str, node_type: str) -> Record:
    return next(n for n in nodes if n["graph_id"] == graph_id and n["node_type"] == node_type)


def _rules(findings: list[Any]) -> list[str]:
    return [f.rule_id for f in findings]


# ---------------------------------------------------------------------------
# Control de calidad: basal derivado de un animal Control
# ---------------------------------------------------------------------------


def test_basal_derived_from_a_control_reproduces_its_observation(real: GraphRecords) -> None:
    instances, nodes, edges = _derive(real)
    derived_id = f"synthetic:derived:{CONTROL}:basal"

    scenario = find_scenario_findings(instances, nodes, edges)
    assert scenario == []
    node_findings = find_node_findings(instances, nodes, metadata=real.metadata)
    derived = [f for f in node_findings if f.graph_id == derived_id]
    # Reutiliza los IDs reales (sin NOD-04) y se evalúa como una instancia real en NOD-12.
    assert not {"NOD-04", "INS-08"} & set(_rules(derived))
    origin = next(i for i in real.instances if i["sample_id"] == CONTROL)["graph_id"]
    origin_findings = [f for f in node_findings if f.graph_id == origin]
    assert sorted(_rules(derived)) == sorted(_rules(origin_findings))


def test_basal_that_differs_from_its_observation_is_reported(real: GraphRecords) -> None:
    instances, nodes, edges = _derive(real)
    derived_id = f"synthetic:derived:{CONTROL}:basal"
    _node(nodes, derived_id, "host")["attributes"]["covariates"]["body_weight_g"] = 9999.0

    (finding,) = find_scenario_findings(instances, nodes, edges)
    assert finding.rule_id == "INS-06"
    assert finding.location["attribute"] == "covariates.body_weight_g"
    assert finding.location["origin_graph_id"].endswith(CONTROL)
    assert finding.location["derived_graph_id"] == derived_id
    assert "no es una variable declarada en intervention" in finding.message


# ---------------------------------------------------------------------------
# Variables declaradas
# ---------------------------------------------------------------------------


def test_declared_change_is_not_reported(real: GraphRecords) -> None:
    change = [{"variable": "host.covariates.body_weight_g", "value": 2500.0}]
    instances, nodes, edges = _derive(real, intervention=change, scenario_id="intervention")
    derived_id = f"synthetic:derived:{CONTROL}:intervention"
    _node(nodes, derived_id, "host")["attributes"]["covariates"]["body_weight_g"] = 2500.0

    assert find_scenario_findings(instances, nodes, edges) == []


def test_undeclared_change_is_reported_next_to_a_declared_one(real: GraphRecords) -> None:
    change = [{"variable": "host.covariates.body_weight_g", "value": 2500.0}]
    instances, nodes, edges = _derive(real, intervention=change, scenario_id="intervention")
    derived_id = f"synthetic:derived:{CONTROL}:intervention"
    host = _node(nodes, derived_id, "host")
    host["attributes"]["covariates"]["body_weight_g"] = 2500.0
    host["attributes"]["covariates"]["breed"] = (
        "Ross" if (host["attributes"]["covariates"]["breed"] == "Cobb") else "Cobb"
    )

    (finding,) = find_scenario_findings(instances, nodes, edges)
    assert (finding.rule_id, finding.location["attribute"]) == ("INS-06", "covariates.breed")
    assert finding.location["declared_variable"] == ["covariates.body_weight_g"]


def test_derived_value_must_match_the_declared_value(real: GraphRecords) -> None:
    change = [{"variable": "host.covariates.body_weight_g", "value": 2500.0}]
    instances, nodes, edges = _derive(real, intervention=change, scenario_id="intervention")

    (finding,) = find_scenario_findings(instances, nodes, edges)
    assert finding.rule_id == "INS-06"
    assert finding.location["declared_value"] == 2500.0
    assert "valor que declara intervention" in finding.message


def test_derived_edges_are_compared_with_the_origin(real: GraphRecords) -> None:
    instances, nodes, edges = _derive(real)
    derived_id = f"synthetic:derived:{CONTROL}:basal"
    edges = [e for e in edges if e["graph_id"] != derived_id]

    findings = find_scenario_findings(instances, nodes, edges)
    assert findings and set(_rules(findings)) == {"INS-07"}
    assert findings[0].location["only_in_origin_count"] >= 1
    assert findings[0].location["only_in_derived_count"] == 0


def test_derived_without_its_origin_in_the_dataset_is_not_compared(
    real: GraphRecords,
) -> None:
    instances, nodes, edges = _derive(real)
    derived_id = f"synthetic:derived:{CONTROL}:basal"
    _node(nodes, derived_id, "host")["attributes"]["covariates"]["body_weight_g"] = 9999.0
    origin_id = next(i for i in real.instances if i["sample_id"] == CONTROL)["graph_id"]
    instances = [i for i in instances if i["graph_id"] != origin_id]

    assert find_scenario_findings(instances, nodes, edges) == []


# ---------------------------------------------------------------------------
# INS-08: campos de la derivación
# ---------------------------------------------------------------------------


def test_real_instance_with_derived_from_is_rejected(real: GraphRecords) -> None:
    instances = copy.deepcopy(real.instances)
    instances[0]["derived_from"] = CONTROL
    findings = [
        f
        for f in find_node_findings(instances, real.nodes, metadata=real.metadata)
        if f.rule_id == "INS-08"
    ]
    assert len(findings) == 1
    assert findings[0].severity.name == "ERROR"
    assert findings[0].graph_id == instances[0]["graph_id"]
    assert "instancia real" in findings[0].message

    with pytest.raises(ValueError, match="instancia real"):
        NormalizedInstanceRecord(
            graph_id="g",
            sample_id="s",
            species="chicken",
            gut_segment="cecum",
            study_id="CA",
            scenario_id="observed",
            diet_treatment="Control",
            derived_from="SAMEA1",
        )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"intervention": None}, "no intervention"),
        ({"derived_from": None}, "no derived_from"),
        ({"intervention": [{"variable": "host", "value": 1}]}, "<tipo de nodo>.<ruta"),
        ({"intervention": [{"variable": "host.covariates.sex"}]}, "falta el nuevo valor"),
        (
            {
                "intervention": [
                    {"variable": "additive.dose", "value": 1},
                    {"variable": "additive.dose", "value": 2},
                ]
            },
            "más de una vez",
        ),
        ({"intervention": {"variable": "additive.dose", "value": 1}}, "debe ser una lista"),
    ],
    ids=["no-intervention", "no-derived-from", "bad-path", "no-value", "repeated", "not-a-list"],
)
def test_malformed_derivation_is_reported(
    real: GraphRecords, changes: Record, message: str
) -> None:
    instances, nodes, _ = _derive(real)
    instances[-1].update(changes)
    findings = [
        f
        for f in find_node_findings(instances, nodes, metadata=real.metadata)
        if f.rule_id == "INS-08"
    ]
    assert findings
    assert any(message in f.message for f in findings)


# ---------------------------------------------------------------------------
# Registros y formato de las variables
# ---------------------------------------------------------------------------


def test_variable_paths() -> None:
    assert DerivedVariable.parse("diet.composition.crude_protein") == DerivedVariable(
        "diet", "composition.crude_protein", "crude_protein"
    )
    assert DerivedVariable.parse("host.covariates.body_weight_g").path == (
        "covariates.body_weight_g"
    )
    for bad in ("host", "host.", ".dose", "diet.composition.a.b", ""):
        with pytest.raises(ValueError):
            DerivedVariable.parse(bad)
    assert intervention_problems([]) == []


def test_instance_record_omits_unset_derivation_fields() -> None:
    plain = InstanceRecord("g", "chicken", "cecum", "s", "s1", "basal", "d")
    assert "derived_from" not in plain.to_dict()
    derived = dataclasses.replace(plain, derived_from="SAMEA1", intervention=[])
    assert derived.to_dict()["derived_from"] == "SAMEA1"
    assert InstanceRecord.from_dict(derived.to_dict()) == derived
    assert InstanceRecord.from_dict(plain.to_dict()) == plain


def test_tabular_instance_round_trips_its_intervention(tmp_path: Path) -> None:
    record = NormalizedInstanceRecord(
        graph_id="synthetic:derived:s:intervention",
        sample_id="synthetic:sample:s",
        species="chicken",
        gut_segment="cecum",
        study_id="CA",
        scenario_id="intervention",
        diet_treatment="Control",
        is_synthetic=True,
        derived_from="SAMEA1",
        intervention=[{"variable": "diet.composition.crude_protein", "value": 270.0}],
    )
    paths = NormalizedTabularDataset(instances=[record]).export_tables(tmp_path)
    with paths["instances"].open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle, delimiter="\t"))
    restored = NormalizedInstanceRecord.from_dict({**row, "is_synthetic": True})
    assert restored.intervention == record.intervention
    assert restored.derived_from == "SAMEA1"
