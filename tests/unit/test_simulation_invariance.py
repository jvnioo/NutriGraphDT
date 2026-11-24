"""Tests de invariancia del módulo nutrigraphdt.simulation (A93-P4, #312).

Verifica que al comparar los escenarios basal e intervenido:

1. Solo cambia la variable intervenida (``crude_protein`` en la dieta).
2. Todos los demás nodos y aristas permanecen idénticos entre escenarios.
3. El runner produce los mismos resultados en dos ejecuciones (determinismo).
4. El ``ConstantPredictor`` devuelve diferencias cero cuando ambos escenarios
   reciben las mismas fracciones.
5. El control de soporte marca «no estimable» cuando corresponde.
6. El catálogo es coherente con los identificadores canónicos de DS-04.

Los datos son **sintéticos**. Los tests validan el comportamiento del módulo,
no efectos biológicos reales.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nutrigraphdt.data.synthetic.nodes import NodeType
from nutrigraphdt.data.synthetic.scenarios import (
    INTERVENTION_BASAL_VALUE,
    INTERVENTION_INTERVENED_VALUE,
    INTERVENTION_VARIABLE,
    SCENARIO_BASAL_GRAPH_ID,
    SCENARIO_INTERVENED_GRAPH_ID,
)
from nutrigraphdt.scenarios import EmpiricalSupport
from nutrigraphdt.simulation import (
    OutcomeStatus,
    ScenarioPair,
    ScenarioResult,
    run_scenario_pair,
)
from nutrigraphdt.simulation.catalog import CatalogError, load_scenario_catalog
from nutrigraphdt.simulation.outcome import SCFA_COMPONENTS, compute_scfa_diff
from nutrigraphdt.simulation.runner import ConstantPredictor, SimulationError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CATALOG_DIR = Path(__file__).parents[3] / "configs" / "scenarios"

_VALID_FRACTIONS: dict[str, float] = {
    "acetate": 0.70,
    "propionate": 0.15,
    "butyrate": 0.15,
}


@pytest.fixture(scope="module")
def pair() -> ScenarioPair:
    """Par de escenarios construido una vez por módulo."""
    return ScenarioPair.default()


@pytest.fixture(scope="module")
def constant_result(pair: ScenarioPair) -> ScenarioResult:
    """Resultado del ConstantPredictor sobre el par por defecto."""
    predictor = ConstantPredictor(_VALID_FRACTIONS)
    return run_scenario_pair(pair, predictor, predictor_name="constant")


# ---------------------------------------------------------------------------
# A93-P4-INV-1: Solo cambia la variable intervenida
# ---------------------------------------------------------------------------


def test_only_crude_protein_changes_between_scenarios(pair: ScenarioPair) -> None:
    """Solo el componente crude_protein de la dieta cambia entre basal e intervenido."""
    basal_diet = [n for n in pair.basal.nodes if n.node_type == NodeType.DIET.value]
    intervened_diet = [n for n in pair.intervened.nodes if n.node_type == NodeType.DIET.value]

    assert len(basal_diet) == len(intervened_diet)
    for b_node, i_node in zip(basal_diet, intervened_diet, strict=True):
        b_comp = {c["component_id"]: c["value"] for c in b_node.attributes["composition"]}
        i_comp = {c["component_id"]: c["value"] for c in i_node.attributes["composition"]}

        # Solo crude_protein debería diferir
        changed = {k for k in b_comp if b_comp[k] != i_comp.get(k)}
        assert changed == {INTERVENTION_VARIABLE}, (
            f"Se esperaba que solo cambiara '{INTERVENTION_VARIABLE}'; cambiaron: {changed}."
        )
        assert b_comp[INTERVENTION_VARIABLE] == INTERVENTION_BASAL_VALUE
        assert i_comp[INTERVENTION_VARIABLE] == INTERVENTION_INTERVENED_VALUE


def test_non_diet_nodes_are_identical_between_scenarios(pair: ScenarioPair) -> None:
    """Los nodos que no son 'diet' son idénticos entre basal e intervenido."""
    non_diet_types = [nt.value for nt in NodeType if nt != NodeType.DIET]

    for node_type in non_diet_types:
        b_nodes = sorted(
            [n for n in pair.basal.nodes if n.node_type == node_type],
            key=lambda n: n.node_id,
        )
        i_nodes = sorted(
            [n for n in pair.intervened.nodes if n.node_type == node_type],
            key=lambda n: n.node_id,
        )
        assert len(b_nodes) == len(i_nodes), (
            f"Tipo '{node_type}': conteo distinto entre escenarios."
        )
        for b_n, i_n in zip(b_nodes, i_nodes, strict=True):
            # Comparar atributos (excepto graph_id que sí difiere por diseño)
            b_attrs = dict(b_n.attributes)
            i_attrs = dict(i_n.attributes)
            assert b_attrs == i_attrs, (
                f"Atributos del nodo '{node_type}/{b_n.node_id}' difieren entre escenarios."
            )


def test_edges_are_identical_except_graph_id(pair: ScenarioPair) -> None:
    """Las aristas son idénticas entre escenarios (salvo graph_id)."""
    assert len(pair.basal.edges) == len(pair.intervened.edges)

    for b_edge, i_edge in zip(pair.basal.edges, pair.intervened.edges, strict=True):
        assert b_edge.edge_type == i_edge.edge_type
        assert b_edge.source_id == i_edge.source_id
        assert b_edge.target_id == i_edge.target_id
        assert b_edge.attributes == i_edge.attributes


# ---------------------------------------------------------------------------
# A93-P4-INV-2: Determinismo del runner
# ---------------------------------------------------------------------------


def test_runner_is_deterministic(pair: ScenarioPair) -> None:
    """Dos ejecuciones del runner con el mismo predictor producen el mismo resultado."""
    predictor = ConstantPredictor(_VALID_FRACTIONS)
    result_a = run_scenario_pair(pair, predictor)
    result_b = run_scenario_pair(pair, predictor)

    assert [o.to_dict() for o in result_a.basal_outcomes] == [
        o.to_dict() for o in result_b.basal_outcomes
    ]
    assert [d.to_dict() for d in result_a.diffs] == [d.to_dict() for d in result_b.diffs]


# ---------------------------------------------------------------------------
# A93-P4-INV-3: ConstantPredictor produce diferencias cero
# ---------------------------------------------------------------------------


def test_constant_predictor_produces_zero_diffs(constant_result: ScenarioResult) -> None:
    """Un predictor constante produce diferencias cero entre basal e intervenido."""
    for diff in constant_result.diffs:
        assert diff.status == OutcomeStatus.ESTIMABLE
        assert diff.diff is not None
        assert abs(diff.diff) < 1e-12, (
            f"Se esperaba diff=0 para '{diff.component}'; obtenido: {diff.diff}."
        )


def test_runner_result_has_all_scfa_components(constant_result: ScenarioResult) -> None:
    """El resultado contiene los tres AGCC canónicos."""
    expected = set(SCFA_COMPONENTS)
    assert {o.component for o in constant_result.basal_outcomes} == expected
    assert {o.component for o in constant_result.intervened_outcomes} == expected
    assert {d.component for d in constant_result.diffs} == expected


# ---------------------------------------------------------------------------
# A93-P4-INV-4: Control de soporte — «no estimable»
# ---------------------------------------------------------------------------


def test_out_of_support_prediction_is_not_estimable(pair: ScenarioPair) -> None:
    """Una predicción fuera de soporte se devuelve como 'no_estimable', sin número."""
    # Soporte estrecho: solo acepta fracciones exactamente [0.70, 0.15, 0.15]
    support = EmpiricalSupport.fit(
        [(0.70, 0.15, 0.15)],
        source="soporte de prueba (mínimo = máximo)",
    )
    # Predictor que devuelve fracciones fuera del soporte
    out_of_support_predictor = ConstantPredictor(
        {"acetate": 0.60, "propionate": 0.20, "butyrate": 0.20}
    )
    result = run_scenario_pair(pair, out_of_support_predictor, support=support)

    for outcome in result.basal_outcomes + result.intervened_outcomes:
        assert outcome.status == OutcomeStatus.NOT_ESTIMABLE
        assert outcome.value is None, (
            f"Una predicción fuera de soporte no debe devolver un número "
            f"(componente: '{outcome.component}')."
        )

    for diff in result.diffs:
        assert diff.status == OutcomeStatus.NOT_ESTIMABLE
        assert diff.diff is None


def test_in_support_prediction_is_estimable(pair: ScenarioPair) -> None:
    """Una predicción dentro del soporte se devuelve como 'estimable' con valor."""
    support = EmpiricalSupport.fit(
        [(0.60, 0.15, 0.25), (0.80, 0.20, 0.00)],
        source="soporte de prueba amplio",
    )
    predictor = ConstantPredictor({"acetate": 0.70, "propionate": 0.17, "butyrate": 0.13})
    result = run_scenario_pair(pair, predictor, support=support)

    for outcome in result.basal_outcomes + result.intervened_outcomes:
        assert outcome.status == OutcomeStatus.ESTIMABLE
        assert outcome.value is not None


# ---------------------------------------------------------------------------
# A93-P4-INV-5: Catálogo versionado
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not CATALOG_DIR.exists(),
    reason="configs/scenarios/ no existe en este entorno.",
)
def test_catalog_loads_and_matches_canonical_ids() -> None:
    """El catálogo se lee y los scenario_id coinciden con los canónicos de DS-04."""
    catalog = load_scenario_catalog(CATALOG_DIR)
    assert catalog.basal.scenario_id == SCENARIO_BASAL_GRAPH_ID
    assert catalog.intervened.scenario_id == SCENARIO_INTERVENED_GRAPH_ID


@pytest.mark.skipif(
    not CATALOG_DIR.exists(),
    reason="configs/scenarios/ no existe en este entorno.",
)
def test_catalog_entries_are_synthetic() -> None:
    """Las entradas del catálogo declaran is_synthetic=true."""
    catalog = load_scenario_catalog(CATALOG_DIR)
    assert catalog.basal.is_synthetic
    assert catalog.intervened.is_synthetic


@pytest.mark.skipif(
    not CATALOG_DIR.exists(),
    reason="configs/scenarios/ no existe en este entorno.",
)
def test_catalog_intervened_has_intervention_values() -> None:
    """El catálogo del escenario intervenido documenta los valores de intervención."""
    catalog = load_scenario_catalog(CATALOG_DIR)
    entry = catalog.intervened
    assert entry.intervention_variable == INTERVENTION_VARIABLE
    assert entry.intervention_basal_value == INTERVENTION_BASAL_VALUE
    assert entry.intervention_intervened_value == INTERVENTION_INTERVENED_VALUE


@pytest.mark.skipif(
    not CATALOG_DIR.exists(),
    reason="configs/scenarios/ no existe en este entorno.",
)
def test_pair_from_catalog_uses_canonical_scenarios() -> None:
    """ScenarioPair.from_catalog() construye el par con los escenarios canónicos."""
    from nutrigraphdt.simulation.runner import ScenarioPair

    pair = ScenarioPair.from_catalog(CATALOG_DIR)
    assert pair.basal.graph_id == SCENARIO_BASAL_GRAPH_ID
    assert pair.intervened.graph_id == SCENARIO_INTERVENED_GRAPH_ID


def test_catalog_error_on_missing_file(tmp_path: Path) -> None:
    """load_scenario_catalog lanza CatalogError si falta un archivo."""
    with pytest.raises(CatalogError, match="no encontrado"):
        load_scenario_catalog(tmp_path)


def test_catalog_error_on_wrong_scenario_id(tmp_path: Path) -> None:
    """load_scenario_catalog lanza CatalogError si el scenario_id es incorrecto."""
    basal_data = {
        "schema_version": "1.0.0",
        "scenario_id": "wrong:id",
        "label": "Basal",
        "description": "Basal",
        "intervention_variable": None,
        "intervention_basal_value": None,
        "intervention_intervened_value": None,
        "intervention_unit": None,
        "is_synthetic": True,
        "synthetic_data_warning": "warning",
        "source": "module",
    }
    intervened_data = {
        **basal_data,
        "scenario_id": SCENARIO_INTERVENED_GRAPH_ID,
        "label": "Intervenido",
    }
    (tmp_path / "basal_v1.json").write_text(json.dumps(basal_data), encoding="utf-8")
    (tmp_path / "intervened_v1.json").write_text(json.dumps(intervened_data), encoding="utf-8")

    with pytest.raises(CatalogError, match="scenario_id"):
        load_scenario_catalog(tmp_path)


# ---------------------------------------------------------------------------
# A93-P4-INV-6: SimulationError cuando el predictor falla
# ---------------------------------------------------------------------------


def test_simulation_error_when_predictor_missing_component(pair: ScenarioPair) -> None:
    """run_scenario_pair lanza SimulationError si el predictor omite un AGCC."""

    class BrokenPredictor:
        def predict(self, scenario: object) -> dict[str, float]:
            return {"acetate": 0.70}  # faltan propionate y butyrate

    with pytest.raises(SimulationError, match="faltan"):
        run_scenario_pair(pair, BrokenPredictor())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A93-P4-INV-7: compute_scfa_diff — alineación de componentes
# ---------------------------------------------------------------------------


def test_compute_scfa_diff_raises_on_misaligned_components() -> None:
    """compute_scfa_diff lanza ValueError si los componentes no coinciden."""
    from nutrigraphdt.simulation.outcome import ScfaOutcome

    basal_outcomes = [ScfaOutcome("acetate", 0.70, "fraccion_molar", OutcomeStatus.ESTIMABLE)]
    interv_outcomes = [ScfaOutcome("propionate", 0.15, "fraccion_molar", OutcomeStatus.ESTIMABLE)]
    with pytest.raises(ValueError, match="desalineado"):
        compute_scfa_diff(basal_outcomes, interv_outcomes)


# ---------------------------------------------------------------------------
# A93-P4-INV-8: ScenarioResult.to_dict incluye advertencia de datos sintéticos
# ---------------------------------------------------------------------------


def test_result_to_dict_contains_synthetic_warning(constant_result: ScenarioResult) -> None:
    """to_dict() incluye la advertencia de datos sintéticos (D-06 §7)."""
    data = constant_result.to_dict()
    assert "synthetic_data_warning" in data
    assert (
        "SINTÉTICOS" in data["synthetic_data_warning"].upper()
        or "SINTETICOS" in data["synthetic_data_warning"].upper()
    )
