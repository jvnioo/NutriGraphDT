"""Regresiones DS-04/DS-06: rechazar entradas inválidas antes de exportarlas."""

from copy import deepcopy
from dataclasses import replace
from typing import Any
from unittest.mock import patch

import pytest

from nutrigraphdt.data.synthetic.scenarios import (
    ScenarioInstance,
    build_basal_scenario,
    build_intervened_scenario,
    validate_scenario_contracts,
)


# Campos del contrato DS-01, independientes del mapa usado por el validador.
@pytest.mark.parametrize("builder", [build_basal_scenario, build_intervened_scenario])
@pytest.mark.parametrize(
    "kind,field",
    [
        ("diet", "composition"),
        ("additive", "dose_unit"),
        ("substrate", "quantity"),
        ("taxon", "abundance"),
        ("function", "annotation_source"),
        ("metabolite", "sample_matrix"),
        ("host", "species"),
        ("phenotype", "value"),
    ],
)
def test_rejects_missing_domain_attribute(builder: Any, kind: str, field: str) -> None:
    scenario = builder()
    node = next(n for n in scenario.nodes if n.node_type == kind)
    del node.attributes[field]
    assert any(f"attributes.{field}" in e for e in validate_scenario_contracts(scenario))


def _taxon(scenario: ScenarioInstance) -> Any:
    return next(n for n in scenario.nodes if n.node_type == "taxon")


@pytest.mark.parametrize("invalid", [True, "0.2", float("nan"), float("inf"), -float("inf")])
def test_abundance_requires_finite_json_number(invalid: Any) -> None:
    scenario = build_basal_scenario()
    _taxon(scenario).attributes["abundance"] = invalid
    assert validate_scenario_contracts(scenario)


def test_null_requires_explicit_missing_mask_and_does_not_mutate() -> None:
    scenario = build_basal_scenario()
    node = _taxon(scenario)
    node.attributes["abundance"] = None
    assert validate_scenario_contracts(scenario)
    node.missing_mask["abundance"] = True
    before = deepcopy(scenario)
    assert validate_scenario_contracts(scenario) == []
    assert scenario == before


@pytest.mark.parametrize(
    "mask",
    [{"abundance": 1}, {"abundance": "true"}, {"abundance": True}, {"absent_attribute": True}],
)
def test_rejects_malformed_or_inconsistent_missing_mask(mask: dict[str, Any]) -> None:
    scenario = build_basal_scenario()
    _taxon(scenario).missing_mask.clear()
    _taxon(scenario).missing_mask.update(mask)
    assert validate_scenario_contracts(scenario)


@pytest.mark.parametrize(
    "composition",
    [
        "invalid",
        [42],
        [{"component_id": "synthetic:nutrient", "value": 1.0}],
        [{"component_id": "synthetic:nutrient", "value": True, "unit": "g_kg"}],
        [{"component_id": "synthetic:nutrient", "value": float("nan"), "unit": "g_kg"}],
    ],
)
def test_rejects_invalid_diet_composition(composition: Any) -> None:
    scenario = build_basal_scenario()
    diet = next(n for n in scenario.nodes if n.node_type == "diet")
    diet.attributes["composition"] = composition
    assert validate_scenario_contracts(scenario)


def test_rejects_nonfinite_nested_covariate() -> None:
    scenario = build_basal_scenario()
    host = next(n for n in scenario.nodes if n.node_type == "host")
    host.attributes["covariates"]["test_only"] = {"value": float("inf")}
    assert any("covariates.test_only.value" in e for e in validate_scenario_contracts(scenario))


@pytest.mark.parametrize("container", ["attributes", "missing_mask"])
def test_invalid_containers_are_reported_without_crashing(container: str) -> None:
    scenario = build_basal_scenario()
    nodes = list(scenario.nodes)
    nodes[0] = replace(nodes[0], **{container: []})
    assert validate_scenario_contracts(replace(scenario, nodes=nodes))


def test_builder_rejects_invalid_generated_attributes() -> None:
    valid = build_basal_scenario()
    nodes = deepcopy(valid.nodes)
    next(n for n in nodes if n.node_type == "taxon").attributes["abundance"] = True
    with (
        patch("nutrigraphdt.data.synthetic.scenarios.generate_synthetic_nodes", return_value=nodes),
        pytest.raises(ValueError, match="attributes.abundance"),
    ):
        build_basal_scenario()
