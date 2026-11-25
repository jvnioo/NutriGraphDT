"""Catálogo de escenarios de referencia (A93-P2, #310): esquema, valores y cobertura."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nutrigraphdt.data.synthetic.scenarios import (
    INTERVENTION_BASAL_VALUE,
    INTERVENTION_INTERVENED_VALUE,
)
from nutrigraphdt.simulation import CATALOG_DIR, CatalogError, load_catalog, load_scenario

CATALOG = load_catalog()


def _write(directory: Path, data: dict[str, object]) -> Path:
    path = directory / f"{data['id']}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _valid() -> dict[str, object]:
    return json.loads((CATALOG_DIR / "basal.json").read_text(encoding="utf-8"))


def test_the_whole_catalog_is_valid_and_synthetic() -> None:
    assert len(CATALOG) >= 4
    assert len({s.id for s in CATALOG}) == len(CATALOG)
    for scenario in CATALOG:
        assert scenario.is_synthetic is True
        assert scenario.run == "synthetic"
        assert scenario.base_instance.startswith("synthetic:sample:")
        assert scenario.request().base_instance == scenario.base_instance
        assert scenario.basal_request().intervention == ()


def test_catalog_covers_the_required_cases() -> None:
    by_id = {s.id: s for s in CATALOG}
    assert by_id["basal"].is_basal
    assert any(s.expected_status == "no_estimable" for s in CATALOG)
    assert any(s.null_intervention for s in CATALOG)
    variables = {item.variable for s in CATALOG for item in s.intervention}
    assert "diet.composition.crude_protein" in variables
    assert "additive.dose" in variables


def test_protein_scenario_uses_the_ds04_values() -> None:
    by_id = {s.id: s for s in CATALOG}
    protein = by_id["crude-protein-270"].intervention[0]
    assert protein.variable == "diet.composition.crude_protein"
    assert protein.value == INTERVENTION_INTERVENED_VALUE
    null = by_id["crude-protein-null"].intervention[0]
    assert null.value == INTERVENTION_BASAL_VALUE


def test_additive_doses_come_from_the_synthetic_dictionary() -> None:
    from nutrigraphdt.data.synthetic.nodes import _ADDITIVE_CATALOG

    doses = {float(entry["dose"]) for entry in _ADDITIVE_CATALOG}
    for scenario in CATALOG:
        for item in scenario.intervention:
            if item.variable == "additive.dose":
                assert float(item.value) in doses


def test_every_intervention_declares_its_source() -> None:
    for scenario in CATALOG:
        assert {s.variable for s in scenario.value_sources} == {
            i.variable for i in scenario.intervention
        }


def test_unknown_fields_are_rejected(tmp_path: Path) -> None:
    data = {**_valid(), "extra": 1}
    with pytest.raises(CatalogError, match="extra"):
        load_scenario(_write(tmp_path, data))


def test_file_name_must_match_the_id(tmp_path: Path) -> None:
    path = tmp_path / "otro.json"
    path.write_text(json.dumps(_valid()), encoding="utf-8")
    with pytest.raises(CatalogError, match=r"basal\.json"):
        load_scenario(path)


def test_intervention_without_source_is_rejected(tmp_path: Path) -> None:
    data = {
        **_valid(),
        "intervention": [{"variable": "additive.dose", "value": 0.0}],
        "value_sources": [],
    }
    with pytest.raises(CatalogError, match="value_sources"):
        load_scenario(_write(tmp_path, data))


def test_non_synthetic_scenarios_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(CatalogError, match="is_synthetic"):
        load_scenario(_write(tmp_path, {**_valid(), "is_synthetic": False}))


def test_null_intervention_needs_variables(tmp_path: Path) -> None:
    with pytest.raises(CatalogError, match="nula"):
        load_scenario(_write(tmp_path, {**_valid(), "null_intervention": True}))


def test_empty_directory_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(CatalogError, match="no tiene escenarios"):
        load_catalog(tmp_path)


def test_invalid_json_is_reported(tmp_path: Path) -> None:
    (tmp_path / "roto.json").write_text("{", encoding="utf-8")
    with pytest.raises(CatalogError, match="roto.json"):
        load_catalog(tmp_path)
