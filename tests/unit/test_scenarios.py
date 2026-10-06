"""Pruebas unitarias para los escenarios basal e intervenido (DS-05).

Cubre los criterios de aceptacion:
- Existen dos escenarios identificables.
- Los cambios introducidos estan documentados.
- Ambos escenarios cumplen los contratos de entrada (nodo y arista).
- Solo cambia la variable nutricional seleccionada (crude_protein).
- Los efectos sinteticos no se presentan como resultados reales.
"""

from __future__ import annotations

from copy import deepcopy

import pytest

from nutrigraphdt.data.synthetic.nodes import (
    NodeCountConfig,
    NodeType,
    SyntheticNodeConfig,
    generate_synthetic_nodes,
)
from nutrigraphdt.data.synthetic.scenarios import (
    INTERVENTION_BASAL_VALUE,
    INTERVENTION_COMPONENT_UNIT,
    INTERVENTION_INTERVENED_VALUE,
    INTERVENTION_VARIABLE,
    SCENARIO_BASAL_GRAPH_ID,
    SCENARIO_INTERVENED_GRAPH_ID,
    ScenarioInstance,
    build_basal_scenario,
    build_intervened_scenario,
    validate_scenario_contracts,
    validate_scenario_node_contract,
)
from nutrigraphdt.data.synthetic.targets import generate_synthetic_targets

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def basal() -> ScenarioInstance:
    """Escenario basal construido una vez por modulo de tests."""
    return build_basal_scenario()


@pytest.fixture(scope="module")
def intervened() -> ScenarioInstance:
    """Escenario intervenido construido una vez por modulo de tests."""
    return build_intervened_scenario()


# ---------------------------------------------------------------------------
# AC-1: Existen dos escenarios identificables
# ---------------------------------------------------------------------------


def test_two_scenarios_have_distinct_graph_ids(
    basal: ScenarioInstance,
    intervened: ScenarioInstance,
) -> None:
    """Los dos escenarios tienen graph_id distintos y canonicos."""
    assert basal.graph_id == SCENARIO_BASAL_GRAPH_ID
    assert intervened.graph_id == SCENARIO_INTERVENED_GRAPH_ID
    assert basal.graph_id != intervened.graph_id


def test_both_scenarios_have_nodes_and_edges(
    basal: ScenarioInstance,
    intervened: ScenarioInstance,
) -> None:
    """Ambos escenarios contienen nodos y aristas."""
    assert len(basal.nodes) > 0
    assert len(basal.edges) > 0
    assert len(intervened.nodes) > 0
    assert len(intervened.edges) > 0


def test_both_scenarios_have_all_eight_node_types(
    basal: ScenarioInstance,
    intervened: ScenarioInstance,
) -> None:
    """Ambos escenarios generan los 8 tipos de nodo del dominio."""
    expected = {nt.value for nt in NodeType}
    assert {n.node_type for n in basal.nodes} == expected
    assert {n.node_type for n in intervened.nodes} == expected


def test_scenario_node_counts_are_equal(
    basal: ScenarioInstance,
    intervened: ScenarioInstance,
) -> None:
    """Ambos escenarios tienen el mismo numero de nodos por tipo."""
    basal_by_type = {}
    for node in basal.nodes:
        basal_by_type[node.node_type] = basal_by_type.get(node.node_type, 0) + 1

    intervened_by_type = {}
    for node in intervened.nodes:
        intervened_by_type[node.node_type] = intervened_by_type.get(node.node_type, 0) + 1

    assert basal_by_type == intervened_by_type


def test_independent_graph_ids_still_produce_distinct_synthetic_nodes() -> None:
    """El graph_id sigue diferenciando muestras fuera del par de escenarios."""
    first = generate_synthetic_nodes(
        SyntheticNodeConfig(
            graph_id="synthetic:sample:first",
            counts=NodeCountConfig(taxon=10),
            random_seed=42,
        )
    )
    second = generate_synthetic_nodes(
        SyntheticNodeConfig(
            graph_id="synthetic:sample:second",
            counts=NodeCountConfig(taxon=10),
            random_seed=42,
        )
    )

    first_taxa = [deepcopy(node.to_dict()) for node in first if node.node_type == "taxon"]
    second_taxa = [deepcopy(node.to_dict()) for node in second if node.node_type == "taxon"]
    for node in first_taxa + second_taxa:
        node.pop("graph_id")

    assert first_taxa != second_taxa


# ---------------------------------------------------------------------------
# AC-2: Los cambios introducidos estan documentados
# ---------------------------------------------------------------------------


def test_intervention_constants_are_documented() -> None:
    """Las constantes de intervencion existen y tienen tipos correctos."""
    assert isinstance(INTERVENTION_VARIABLE, str) and INTERVENTION_VARIABLE
    assert isinstance(INTERVENTION_COMPONENT_UNIT, str) and INTERVENTION_COMPONENT_UNIT
    assert isinstance(INTERVENTION_BASAL_VALUE, float)
    assert isinstance(INTERVENTION_INTERVENED_VALUE, float)
    assert INTERVENTION_BASAL_VALUE != INTERVENTION_INTERVENED_VALUE


def test_basal_scenario_has_no_intervention(basal: ScenarioInstance) -> None:
    """El escenario basal declara etiqueta 'none' y sin variable de intervencion."""
    assert basal.intervention_label == "none"
    assert basal.intervention_variable is None
    assert basal.intervention_value is None


def test_intervened_scenario_documents_intervention(intervened: ScenarioInstance) -> None:
    """El escenario intervenido registra la variable y el valor modificados."""
    assert intervened.intervention_variable == INTERVENTION_VARIABLE
    assert intervened.intervention_value == INTERVENTION_INTERVENED_VALUE
    assert INTERVENTION_VARIABLE in intervened.intervention_label
    assert str(INTERVENTION_BASAL_VALUE) in intervened.intervention_label
    assert str(INTERVENTION_INTERVENED_VALUE) in intervened.intervention_label
    assert "[synthetic]" in intervened.intervention_label


# ---------------------------------------------------------------------------
# AC-3: Ambos escenarios cumplen los contratos de entrada
# ---------------------------------------------------------------------------


def test_basal_passes_node_contract(basal: ScenarioInstance) -> None:
    """El escenario basal cumple el contrato de nodo de DS-01."""
    errors = validate_scenario_node_contract(basal)
    assert errors == [], "Incumplimientos del contrato de nodo:\n" + "\n".join(errors)


def test_intervened_passes_node_contract(intervened: ScenarioInstance) -> None:
    """El escenario intervenido cumple el contrato de nodo de DS-01."""
    errors = validate_scenario_node_contract(intervened)
    assert errors == [], "Incumplimientos del contrato de nodo:\n" + "\n".join(errors)


def test_basal_passes_full_contracts(basal: ScenarioInstance) -> None:
    """El escenario basal cumple el contrato de nodo y de arista."""
    errors = validate_scenario_contracts(basal)
    assert errors == [], "Incumplimientos del contrato:\n" + "\n".join(errors)


def test_intervened_passes_full_contracts(intervened: ScenarioInstance) -> None:
    """El escenario intervenido cumple el contrato de nodo y de arista."""
    errors = validate_scenario_contracts(intervened)
    assert errors == [], "Incumplimientos del contrato:\n" + "\n".join(errors)


def test_basal_graph_ids_are_consistent(basal: ScenarioInstance) -> None:
    """Todos los nodos del basal tienen el graph_id del escenario."""
    for node in basal.nodes:
        assert node.graph_id == SCENARIO_BASAL_GRAPH_ID
    for edge in basal.edges:
        assert edge.graph_id == SCENARIO_BASAL_GRAPH_ID


def test_intervened_graph_ids_are_consistent(intervened: ScenarioInstance) -> None:
    """Todos los nodos del intervenido tienen el graph_id del escenario."""
    for node in intervened.nodes:
        assert node.graph_id == SCENARIO_INTERVENED_GRAPH_ID
    for edge in intervened.edges:
        assert edge.graph_id == SCENARIO_INTERVENED_GRAPH_ID


# ---------------------------------------------------------------------------
# AC-4: Solo cambia la variable nutricional seleccionada
# ---------------------------------------------------------------------------


def test_only_crude_protein_differs_in_diet_composition(
    basal: ScenarioInstance,
    intervened: ScenarioInstance,
) -> None:
    """En la composicion de la dieta, solo crude_protein tiene un valor diferente."""
    basal_diet_nodes = [n for n in basal.nodes if n.node_type == NodeType.DIET.value]
    intervened_diet_nodes = [n for n in intervened.nodes if n.node_type == NodeType.DIET.value]

    assert len(basal_diet_nodes) == len(intervened_diet_nodes)

    for b_node, i_node in zip(basal_diet_nodes, intervened_diet_nodes, strict=True):
        b_comp = {item["component_id"]: item for item in b_node.attributes["composition"]}
        i_comp = {item["component_id"]: item for item in i_node.attributes["composition"]}

        assert set(b_comp.keys()) == set(i_comp.keys()), (
            "Los componentes de la composicion deben ser los mismos en ambos escenarios."
        )

        for component_id in b_comp:
            if component_id == INTERVENTION_VARIABLE:
                # Esta variable SI debe cambiar
                assert b_comp[component_id]["value"] != i_comp[component_id]["value"], (
                    f"Se esperaba que {INTERVENTION_VARIABLE!r} tuviera valores distintos."
                )
                assert b_comp[component_id]["value"] == INTERVENTION_BASAL_VALUE
                assert i_comp[component_id]["value"] == INTERVENTION_INTERVENED_VALUE
            else:
                # Todas las demas variables deben ser identicas
                assert b_comp[component_id]["value"] == i_comp[component_id]["value"], (
                    f"El componente {component_id!r} no debe cambiar entre escenarios."
                )
                assert b_comp[component_id]["unit"] == i_comp[component_id]["unit"]


def test_non_diet_nodes_have_same_structure_between_scenarios(
    basal: ScenarioInstance,
    intervened: ScenarioInstance,
) -> None:
    """Todos los atributos no-dieta, incluidos sus valores, son idénticos."""
    non_diet_types = [t.value for t in NodeType if t != NodeType.DIET]

    for node_type in non_diet_types:
        b_nodes = sorted(
            [n for n in basal.nodes if n.node_type == node_type],
            key=lambda n: n.node_id,
        )
        i_nodes = sorted(
            [n for n in intervened.nodes if n.node_type == node_type],
            key=lambda n: n.node_id,
        )
        assert len(b_nodes) == len(i_nodes), (
            f"El numero de nodos de tipo {node_type!r} debe ser igual en ambos escenarios."
        )
        for b_node, i_node in zip(b_nodes, i_nodes, strict=True):
            basal_data = b_node.to_dict()
            intervened_data = i_node.to_dict()
            basal_data.pop("graph_id")
            intervened_data.pop("graph_id")
            assert basal_data == intervened_data, (
                f"El nodo {b_node.node_id!r} debe ser idéntico salvo por graph_id."
            )


def test_all_nodes_match_except_crude_protein_value(
    basal: ScenarioInstance,
    intervened: ScenarioInstance,
) -> None:
    """Solo difiere crude_protein entre los registros de nodos del par."""
    basal_nodes = {(node.node_type, node.node_id): node for node in basal.nodes}
    intervened_nodes = {(node.node_type, node.node_id): node for node in intervened.nodes}
    assert basal_nodes.keys() == intervened_nodes.keys()

    for key, basal_node in basal_nodes.items():
        basal_data = deepcopy(basal_node.to_dict())
        intervened_data = deepcopy(intervened_nodes[key].to_dict())
        basal_data.pop("graph_id")
        intervened_data.pop("graph_id")
        if basal_node.node_type == NodeType.DIET.value:
            basal_component = next(
                item
                for item in basal_data["attributes"]["composition"]
                if item["component_id"] == INTERVENTION_VARIABLE
            )
            intervened_component = next(
                item
                for item in intervened_data["attributes"]["composition"]
                if item["component_id"] == INTERVENTION_VARIABLE
            )
            intervened_component["value"] = basal_component["value"]
        assert basal_data == intervened_data


def test_edges_are_identical_except_for_graph_id(
    basal: ScenarioInstance,
    intervened: ScenarioInstance,
) -> None:
    """La topología, evidencias y atributos de arista son iguales."""

    def normalized_edges(instance: ScenarioInstance) -> list[dict[str, object]]:
        edges = [deepcopy(edge.to_dict()) for edge in instance.edges]
        for edge in edges:
            edge.pop("graph_id")
        return sorted(
            edges,
            key=lambda edge: (
                str(edge["source_type"]),
                str(edge["source_id"]),
                str(edge["relation_type"]),
                str(edge["target_type"]),
                str(edge["target_id"]),
            ),
        )

    assert normalized_edges(basal) == normalized_edges(intervened)


def test_synthetic_targets_are_identical_between_scenarios(
    basal: ScenarioInstance,
    intervened: ScenarioInstance,
) -> None:
    """Los targets AGCC coinciden porque no se modela efecto de la intervención."""
    basal_targets = generate_synthetic_targets(basal.nodes)
    intervened_targets = generate_synthetic_targets(intervened.nodes)
    basal_values = {
        (target.target_type, target.target_id): (
            target.value,
            target.measured_or_predicted,
            target.unit,
            target.sample_matrix,
        )
        for target in basal_targets
    }
    intervened_values = {
        (target.target_type, target.target_id): (
            target.value,
            target.measured_or_predicted,
            target.unit,
            target.sample_matrix,
        )
        for target in intervened_targets
    }

    assert basal_values
    assert basal_values == intervened_values


def _mutable_object_ids(value: object) -> set[int]:
    if isinstance(value, dict):
        result = {id(value)}
        for key, nested_value in value.items():
            result.update(_mutable_object_ids(key))
            result.update(_mutable_object_ids(nested_value))
        return result
    if isinstance(value, list | set):
        result = {id(value)}
        for item in value:
            result.update(_mutable_object_ids(item))
        return result
    if isinstance(value, tuple):
        result: set[int] = set()
        for item in value:
            result.update(_mutable_object_ids(item))
        return result
    return set()


def test_scenario_copies_share_no_mutable_node_or_edge_data() -> None:
    """Ningún objeto mutable de nodos o aristas se comparte entre escenarios."""
    basal = build_basal_scenario()
    intervened = build_intervened_scenario()

    for basal_node, intervened_node in zip(basal.nodes, intervened.nodes, strict=True):
        for basal_data, intervened_data in (
            (basal_node.attributes, intervened_node.attributes),
            (basal_node.missing_mask, intervened_node.missing_mask),
        ):
            assert not _mutable_object_ids(basal_data) & _mutable_object_ids(intervened_data)
    for basal_edge, intervened_edge in zip(basal.edges, intervened.edges, strict=True):
        assert not _mutable_object_ids(basal_edge.attributes) & _mutable_object_ids(
            intervened_edge.attributes
        )


def test_diet_non_composition_attributes_unchanged(
    basal: ScenarioInstance,
    intervened: ScenarioInstance,
) -> None:
    """Los atributos de dieta fuera de 'composition' no cambian entre escenarios."""
    basal_diet = [n for n in basal.nodes if n.node_type == NodeType.DIET.value]
    intervened_diet = [n for n in intervened.nodes if n.node_type == NodeType.DIET.value]

    for b_node, i_node in zip(basal_diet, intervened_diet, strict=True):
        for attr_key in ("name", "ingredients", "source_version"):
            assert b_node.attributes[attr_key] == i_node.attributes[attr_key], (
                f"El atributo {attr_key!r} del nodo de dieta no debe cambiar."
            )


# ---------------------------------------------------------------------------
# AC-5: Los efectos sinteticos no se presentan como resultados reales
# ---------------------------------------------------------------------------


def test_evidence_status_is_synthetic_for_all_edges(
    basal: ScenarioInstance,
    intervened: ScenarioInstance,
) -> None:
    """Todas las aristas de ambos escenarios tienen evidence_status='synthetic'."""
    for edge in basal.edges:
        assert edge.evidence_status == "synthetic", (
            f"Arista {edge.source_id}->{edge.target_id} tiene status {edge.evidence_status!r}."
        )
    for edge in intervened.edges:
        assert edge.evidence_status == "synthetic", (
            f"Arista {edge.source_id}->{edge.target_id} tiene status {edge.evidence_status!r}."
        )


def test_intervention_label_includes_synthetic_disclaimer(
    intervened: ScenarioInstance,
) -> None:
    """La etiqueta de intervencion incluye el marcador '[synthetic]'."""
    assert "[synthetic]" in intervened.intervention_label


def test_source_ids_are_synthetic_v1(
    basal: ScenarioInstance,
    intervened: ScenarioInstance,
) -> None:
    """Todos los nodos declaran source_id='SYNTHETIC_V1'."""
    for node in basal.nodes:
        assert node.source_id == "SYNTHETIC_V1"
    for node in intervened.nodes:
        assert node.source_id == "SYNTHETIC_V1"


# ---------------------------------------------------------------------------
# Determinismo
# ---------------------------------------------------------------------------


def test_scenarios_are_deterministic() -> None:
    """Construir los escenarios dos veces produce resultados identicos."""
    basal_a = build_basal_scenario()
    basal_b = build_basal_scenario()
    assert [n.to_dict() for n in basal_a.nodes] == [n.to_dict() for n in basal_b.nodes]
    assert [e.to_dict() for e in basal_a.edges] == [e.to_dict() for e in basal_b.edges]

    intervened_a = build_intervened_scenario()
    intervened_b = build_intervened_scenario()
    assert [n.to_dict() for n in intervened_a.nodes] == [n.to_dict() for n in intervened_b.nodes]
    assert [e.to_dict() for e in intervened_a.edges] == [e.to_dict() for e in intervened_b.edges]


def test_intervention_value_present_in_intervened_diet_composition(
    intervened: ScenarioInstance,
) -> None:
    """El valor intervenido de crude_protein se encuentra en la composicion."""
    diet_nodes = [n for n in intervened.nodes if n.node_type == NodeType.DIET.value]
    assert len(diet_nodes) >= 1
    for node in diet_nodes:
        composition = node.attributes["composition"]
        protein_items = [
            item for item in composition if item.get("component_id") == INTERVENTION_VARIABLE
        ]
        assert len(protein_items) == 1
        assert protein_items[0]["value"] == INTERVENTION_INTERVENED_VALUE
        assert protein_items[0]["unit"] == INTERVENTION_COMPONENT_UNIT


def test_basal_value_present_in_basal_diet_composition(basal: ScenarioInstance) -> None:
    """El valor basal de crude_protein se encuentra en la composicion."""
    diet_nodes = [n for n in basal.nodes if n.node_type == NodeType.DIET.value]
    assert len(diet_nodes) >= 1
    for node in diet_nodes:
        composition = node.attributes["composition"]
        protein_items = [
            item for item in composition if item.get("component_id") == INTERVENTION_VARIABLE
        ]
        assert len(protein_items) == 1
        assert protein_items[0]["value"] == INTERVENTION_BASAL_VALUE
        assert protein_items[0]["unit"] == INTERVENTION_COMPONENT_UNIT
