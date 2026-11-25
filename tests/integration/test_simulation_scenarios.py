"""Escenarios de referencia contra la corrida sintética congelada (A93-P1 y A93-P4, #309 y #312).

Recorre todo el catálogo de `configs/scenarios/`: cada escenario da el estado esperado, las dos
predicciones de una comparación salen del mismo checkpoint, el escenario difiere de su basal solo
en las variables declaradas y una intervención nula da diferencia cero exacta. Requiere los extras
`graph` y `baselines`.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")

from nutrigraphdt import api  # noqa: E402
from nutrigraphdt.data.derived import DerivedVariable  # noqa: E402
from nutrigraphdt.simulation import (  # noqa: E402
    CatalogScenario,
    compare_scenario,
    load_catalog,
)

CATALOG = load_catalog()
IDS = [s.id for s in CATALOG]


@pytest.fixture(scope="module")
def engine() -> Any:
    return api.DEMO_RUNS["synthetic"].engine()


@pytest.mark.parametrize("scenario", CATALOG, ids=IDS)
def test_scenario_gives_the_expected_status(engine: Any, scenario: CatalogScenario) -> None:
    comparison = compare_scenario(engine, scenario.request())

    assert comparison.intervened.status == scenario.expected_status
    assert comparison.status == scenario.expected_status
    assert comparison.is_synthetic
    assert api.SYNTHETIC_WARNING in comparison.warnings
    if scenario.expected_status == api.NOT_ESTIMABLE:
        assert comparison.differences == ()
        assert comparison.intervened.fractions is None
        assert all(r.startswith("intervenido:") for r in comparison.reasons)


def test_both_predictions_use_the_same_frozen_checkpoint(engine: Any) -> None:
    run_dir = api.DEMO_RUNS["synthetic"].run_dir
    expected = hashlib.sha256((run_dir / "checkpoint.pt").read_bytes()).hexdigest()
    for scenario in CATALOG:
        comparison = compare_scenario(engine, scenario.request())
        assert comparison.basal.model == comparison.intervened.model == engine.model_ref
        assert comparison.checkpoint_sha256 == expected


def test_comparison_does_not_train(engine: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    import nutrigraphdt.models.training.compositional as compositional

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("la comparación no debe entrenar")

    monkeypatch.setattr(compositional, "run_compositional_fold", forbidden, raising=False)
    compare_scenario(engine, CATALOG[0].request())


@pytest.mark.parametrize("scenario", [s for s in CATALOG if s.null_intervention], ids=str)
def test_null_intervention_gives_exactly_the_basal(engine: Any, scenario: CatalogScenario) -> None:
    comparison = compare_scenario(engine, scenario.request())

    assert comparison.status == api.ESTIMABLE
    assert comparison.intervened.fractions == comparison.basal.fractions
    assert comparison.intervened.log_total == comparison.basal.log_total
    assert all(d.difference == 0.0 for d in comparison.differences)


def _strip(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in r.items() if k != "graph_id"} for r in records]


def _without(node: dict[str, Any], derived: DerivedVariable) -> dict[str, Any]:
    """El nodo sin el atributo intervenido ni su máscara."""
    node = copy.deepcopy(node)
    attributes = node.get("attributes") or {}
    mask = node.get("missing_mask") or {}
    if derived.component_id is not None:
        attributes["composition"] = [
            item
            for item in attributes.get("composition") or []
            if item.get("component_id") != derived.component_id
        ]
        mask.pop("composition", None)
    else:
        attributes.pop(derived.path.split(".")[0], None)
        mask.pop(derived.path, None)
    return node


@pytest.mark.parametrize("scenario", [s for s in CATALOG if not s.is_basal], ids=str)
def test_only_the_declared_variables_change(engine: Any, scenario: CatalogScenario) -> None:
    _, basal_nodes, basal_edges = engine.base.derive(scenario.basal_request())
    instance, nodes, edges = engine.base.derive(scenario.request())

    # Aristas y evidencias idénticas.
    assert _strip(edges) == _strip(basal_edges)
    # Mismos nodos, en el mismo orden; solo cambia el atributo declarado de su tipo.
    assert [(n["node_type"], n["node_id"]) for n in nodes] == [
        (n["node_type"], n["node_id"]) for n in basal_nodes
    ]
    declared = [DerivedVariable.parse(item.variable) for item in scenario.intervention]
    touched = {d.node_type for d in declared}
    for node, basal in zip(_strip(nodes), _strip(basal_nodes), strict=True):
        if node["node_type"] not in touched:
            assert node == basal
            continue
        stripped, stripped_basal = node, basal
        for derived in declared:
            if derived.node_type == node["node_type"]:
                stripped = _without(stripped, derived)
                stripped_basal = _without(stripped_basal, derived)
        assert stripped == stripped_basal
    # La instancia declara la intervención con sus valores.
    assert instance["is_synthetic"] is True
    assert instance["derived_from"] == scenario.base_instance
    assert [(i["variable"], i["value"]) for i in instance["intervention"]] == [
        (i.variable, i.value) for i in scenario.intervention
    ]
    # El valor declarado es el que quedó en el grafo.
    for item in scenario.intervention:
        derived = DerivedVariable.parse(item.variable)
        for node in nodes:
            if node["node_type"] != derived.node_type:
                continue
            attributes = node["attributes"]
            if derived.component_id is not None:
                found = [
                    c["value"]
                    for c in attributes["composition"]
                    if c["component_id"] == derived.component_id
                ]
                assert found == [item.value]
            else:
                assert attributes[derived.path] == item.value
