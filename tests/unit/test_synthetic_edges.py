"""Pruebas unitarias para la generación de aristas sintéticas (DS-03)."""

import dataclasses
import json
import random
from typing import Any

import pytest

from nutrigraphdt.data.synthetic.edges import (
    ADDITIVE_MODULATES_FUNCTION,
    ADDITIVE_MODULATES_TAXON,
    ALLOWED_RELATIONS,
    DIET_PROVIDES_SUBSTRATE,
    FUNCTION_CROSS_FEEDS_FUNCTION,
    HOST_EXHIBITS_PHENOTYPE,
    METABOLITE_MEASURED_IN_HOST,
    TAXON_HAS_CAPACITY_FUNCTION,
    TAXON_INTERACTS_WITH_TAXON,
    Edge,
    EdgeType,
    EdgeValidationError,
    SyntheticEdgeConfig,
    SyntheticEdgeGenerator,
    find_edge_errors,
    generate_synthetic_edges,
    validate_edges,
)
from nutrigraphdt.data.synthetic.nodes import (
    Node,
    NodeCountConfig,
    SyntheticNodeConfig,
    generate_synthetic_nodes,
)

# Tabla "Relaciones permitidas" de docs/synthetic-dataset/synthetic-dataset-spec.md, transcrita a
# mano para detectar cualquier divergencia entre el catálogo del código y la especificación.
SPEC_RELATIONS: dict[EdgeType, dict[str, str]] = {
    ("diet", "provides", "substrate"): {"proportion": "number", "unit": "str"},
    ("substrate", "available_to", "taxon"): {},
    ("taxon", "has_capacity", "function"): {"annotation_source": "str"},
    ("function", "produces", "metabolite"): {},
    ("metabolite", "measured_in", "host"): {"sample_matrix": "str"},
    ("additive", "modulates", "taxon"): {},
    ("additive", "modulates", "function"): {},
    ("metabolite", "associated_with", "phenotype"): {},
    ("host", "exhibits", "phenotype"): {"timepoint": "str"},
    ("taxon", "interacts_with", "taxon"): {"interaction_type": "str"},
    ("function", "cross_feeds", "function"): {"substrate_id": "str"},
}

# Columnas "Semántica" y "Estado estructural" de la misma tabla.
SPEC_SEMANTICS: dict[EdgeType, tuple[str, str]] = {
    ("diet", "provides", "substrate"): ("Composición documentada de dieta.", "approved_structure"),
    ("substrate", "available_to", "taxon"): ("Recurso potencialmente disponible.", "provisional"),
    ("taxon", "has_capacity", "function"): (
        "Capacidad anotada, no actividad demostrada.",
        "provisional",
    ),
    ("function", "produces", "metabolite"): ("Transformación candidata.", "provisional"),
    ("metabolite", "measured_in", "host"): ("Medición o exposición contextual.", "provisional"),
    ("additive", "modulates", "taxon"): ("Hipótesis de modulación.", "hypothetical"),
    ("additive", "modulates", "function"): ("Hipótesis de modulación.", "hypothetical"),
    ("metabolite", "associated_with", "phenotype"): (
        "Asociación, no efecto causal.",
        "hypothetical",
    ),
    ("host", "exhibits", "phenotype"): ("Correspondencia observacional.", "provisional"),
    ("taxon", "interacts_with", "taxon"): ("Interacción ecológica candidata.", "hypothetical"),
    ("function", "cross_feeds", "function"): (
        "Sustrato cruzado candidato entre funciones.",
        "hypothetical",
    ),
}

LARGE_COUNTS = NodeCountConfig(
    diet=2,
    additive=2,
    substrate=6,
    taxon=12,
    function=9,
    metabolite=6,
    host=1,
    phenotype=4,
)

ALL_RELATIONS_ALWAYS = SyntheticEdgeConfig(
    relation_probabilities=dict.fromkeys(ALLOWED_RELATIONS, 1.0)
)


def _nodes(graph_id: str = "synthetic:graph:0001", seed: int = 7) -> list[Node]:
    return generate_synthetic_nodes(
        SyntheticNodeConfig(graph_id=graph_id, counts=LARGE_COUNTS, random_seed=seed)
    )


def _node_lookup(nodes: list[Node]) -> dict[tuple[str, str, str], Node]:
    return {(n.graph_id, n.node_type, n.node_id): n for n in nodes}


def _replace_edge(edge: Edge, **changes: Any) -> Edge:
    return dataclasses.replace(edge, **changes)


# --- Catálogo de relaciones -------------------------------------------------------------


def test_catalog_matches_specification_table() -> None:
    """El catálogo contiene exactamente las once tuplas y atributos de la especificación."""
    assert set(ALLOWED_RELATIONS) == set(SPEC_RELATIONS)
    for edge_type, expected_attributes in SPEC_RELATIONS.items():
        assert dict(ALLOWED_RELATIONS[edge_type].required_attributes) == expected_attributes
    for edge_type, (semantics, status) in SPEC_SEMANTICS.items():
        assert ALLOWED_RELATIONS[edge_type].semantics == semantics
        assert ALLOWED_RELATIONS[edge_type].structural_status == status


def test_catalog_excludes_taxon_to_metabolite() -> None:
    """La especificación prohíbe aristas taxon -> metabolite por coocurrencia."""
    assert not any(src == "taxon" and dst == "metabolite" for src, _, dst in ALLOWED_RELATIONS)


# --- Criterio 1: tipos de origen y destino permitidos -----------------------------------


def test_generated_edges_use_only_allowed_relations() -> None:
    edges = generate_synthetic_edges(_nodes(), ALL_RELATIONS_ALWAYS)

    assert edges
    assert {e.edge_type for e in edges} <= set(ALLOWED_RELATIONS)


def test_every_allowed_relation_can_be_generated() -> None:
    """Con densidad 1.0 y todos los tipos de nodo presentes, aparecen las once relaciones."""
    edges = generate_synthetic_edges(_nodes(), ALL_RELATIONS_ALWAYS)

    assert {e.edge_type for e in edges} == set(ALLOWED_RELATIONS)


# --- Criterio 2: extremos existentes ------------------------------------------------------


def test_every_edge_points_to_existing_nodes_of_declared_type() -> None:
    nodes = _nodes()
    lookup = _node_lookup(nodes)
    edges = generate_synthetic_edges(nodes, ALL_RELATIONS_ALWAYS)

    for edge in edges:
        assert (edge.graph_id, edge.source_type, edge.source_id) in lookup
        assert (edge.graph_id, edge.target_type, edge.target_id) in lookup


def test_cross_feeds_substrate_id_references_existing_substrate() -> None:
    nodes = _nodes()
    lookup = _node_lookup(nodes)
    edges = generate_synthetic_edges(nodes, ALL_RELATIONS_ALWAYS)
    cross_feeds = [e for e in edges if e.edge_type == FUNCTION_CROSS_FEEDS_FUNCTION]

    assert cross_feeds
    for edge in cross_feeds:
        assert (edge.graph_id, "substrate", edge.attributes["substrate_id"]) in lookup


def test_cross_feeds_not_generated_without_substrates() -> None:
    counts = dataclasses.replace(LARGE_COUNTS, substrate=0)
    nodes = generate_synthetic_nodes(SyntheticNodeConfig(counts=counts))
    edges = generate_synthetic_edges(nodes, ALL_RELATIONS_ALWAYS)

    assert not [e for e in edges if e.edge_type == FUNCTION_CROSS_FEEDS_FUNCTION]
    validate_edges(nodes, edges)


def test_edges_never_cross_instances() -> None:
    nodes = _nodes("synthetic:graph:0001") + _nodes("synthetic:graph:0002")
    lookup = _node_lookup(nodes)
    edges = generate_synthetic_edges(nodes, ALL_RELATIONS_ALWAYS)

    assert {e.graph_id for e in edges} == {"synthetic:graph:0001", "synthetic:graph:0002"}
    for edge in edges:
        assert lookup[(edge.graph_id, edge.source_type, edge.source_id)].graph_id == edge.graph_id
        assert lookup[(edge.graph_id, edge.target_type, edge.target_id)].graph_id == edge.graph_id


def test_no_self_loops_in_same_type_relations() -> None:
    edges = generate_synthetic_edges(_nodes(), ALL_RELATIONS_ALWAYS)

    for edge in edges:
        if edge.source_type == edge.target_type:
            assert edge.source_id != edge.target_id


# --- Criterio 3: atributos obligatorios ---------------------------------------------------


def test_common_edge_fields_are_complete_and_synthetic() -> None:
    edges = generate_synthetic_edges(_nodes(), ALL_RELATIONS_ALWAYS)

    for edge in edges:
        record = edge.to_dict()
        for field_name in (
            "graph_id",
            "source_type",
            "source_id",
            "relation_type",
            "target_type",
            "target_id",
            "evidence_id",
            "evidence_status",
            "evidence_method",
        ):
            assert isinstance(record[field_name], str) and record[field_name]
        assert isinstance(record["attributes"], dict)
        assert edge.evidence_id == "SYNTHETIC_V1"
        assert edge.evidence_status == "synthetic"
        assert edge.evidence_method == "synthetic_generator"


def test_relation_specific_attributes_are_present_with_correct_type() -> None:
    edges = generate_synthetic_edges(_nodes(), ALL_RELATIONS_ALWAYS)

    for edge in edges:
        for attribute, kind in SPEC_RELATIONS[edge.edge_type].items():
            value = edge.attributes[attribute]
            if kind == "str":
                assert isinstance(value, str) and value
            else:
                assert isinstance(value, float) and not isinstance(value, bool)


def test_attributes_copied_from_nodes_are_consistent() -> None:
    """Los atributos derivados coinciden con el nodo del que provienen."""
    nodes = _nodes()
    lookup = _node_lookup(nodes)
    edges = generate_synthetic_edges(nodes, ALL_RELATIONS_ALWAYS)

    def source(e: Edge) -> Node:
        return lookup[(e.graph_id, e.source_type, e.source_id)]

    def target(e: Edge) -> Node:
        return lookup[(e.graph_id, e.target_type, e.target_id)]

    for edge in edges:
        if edge.edge_type == DIET_PROVIDES_SUBSTRATE:
            assert edge.attributes["proportion"] == target(edge).attributes["quantity"]
            assert edge.attributes["unit"] == target(edge).attributes["unit"]
        elif edge.edge_type == TAXON_HAS_CAPACITY_FUNCTION:
            expected = target(edge).attributes["annotation_source"]
            assert edge.attributes["annotation_source"] == expected
        elif edge.edge_type == METABOLITE_MEASURED_IN_HOST:
            assert edge.attributes["sample_matrix"] == source(edge).attributes["sample_matrix"]
        elif edge.edge_type == HOST_EXHIBITS_PHENOTYPE:
            assert edge.attributes["timepoint"] == target(edge).attributes["timepoint"]


def test_interaction_type_uses_configured_vocabulary() -> None:
    config = dataclasses.replace(ALL_RELATIONS_ALWAYS, interaction_types=("synthetic_a",))
    edges = generate_synthetic_edges(_nodes(), config)
    interactions = [e for e in edges if e.edge_type == TAXON_INTERACTS_WITH_TAXON]

    assert interactions
    assert {e.attributes["interaction_type"] for e in interactions} == {"synthetic_a"}


def test_edge_skipped_when_source_attribute_is_missing() -> None:
    """Si el nodo no tiene la magnitud requerida, no se inventa: la arista se omite."""
    nodes = _nodes()
    masked = [
        dataclasses.replace(
            n,
            attributes={**n.attributes, "sample_matrix": None},
            missing_mask={**n.missing_mask, "sample_matrix": True},
        )
        if n.node_type == "metabolite"
        else n
        for n in nodes
    ]
    edges = generate_synthetic_edges(masked, ALL_RELATIONS_ALWAYS)

    assert not [e for e in edges if e.edge_type == METABOLITE_MEASURED_IN_HOST]
    validate_edges(masked, edges)


# --- Configuración ------------------------------------------------------------------------


def test_default_configuration_produces_valid_edges() -> None:
    nodes = generate_synthetic_nodes()
    edges = generate_synthetic_edges(nodes)

    assert edges
    validate_edges(nodes, edges)


def test_full_probability_connects_every_candidate_pair() -> None:
    nodes = _nodes()
    config = SyntheticEdgeConfig(relation_probabilities={TAXON_HAS_CAPACITY_FUNCTION: 1.0})
    edges = generate_synthetic_edges(nodes, config)

    assert len(edges) == LARGE_COUNTS.taxon * LARGE_COUNTS.function
    assert {e.edge_type for e in edges} == {TAXON_HAS_CAPACITY_FUNCTION}


def test_relations_absent_from_configuration_are_not_generated() -> None:
    config = SyntheticEdgeConfig(relation_probabilities={})

    assert generate_synthetic_edges(_nodes(), config) == []


def test_control_additive_does_not_modulate() -> None:
    """Un aditivo de control (dosis cero) no recibe hipótesis de modulación."""
    nodes = [
        dataclasses.replace(
            n, attributes={**n.attributes, "control_label": "control_basal", "dose": 0.0}
        )
        if n.node_type == "additive"
        else n
        for n in _nodes()
    ]
    edges = generate_synthetic_edges(nodes, ALL_RELATIONS_ALWAYS)

    assert not [
        e for e in edges if e.edge_type in {ADDITIVE_MODULATES_TAXON, ADDITIVE_MODULATES_FUNCTION}
    ]


@pytest.mark.parametrize("probability", [-0.1, 1.5, float("nan"), True])
def test_invalid_probability_is_rejected(probability: float) -> None:
    with pytest.raises(ValueError, match="probabilidad"):
        SyntheticEdgeConfig(relation_probabilities={TAXON_HAS_CAPACITY_FUNCTION: probability})


def test_relation_outside_catalog_is_rejected_in_configuration() -> None:
    with pytest.raises(ValueError, match="no permitida"):
        SyntheticEdgeConfig(relation_probabilities={("taxon", "produces", "metabolite"): 0.5})


def test_empty_interaction_vocabulary_is_rejected() -> None:
    with pytest.raises(ValueError, match="interaction_types"):
        SyntheticEdgeConfig(interaction_types=())


def test_duplicate_node_ids_are_rejected() -> None:
    nodes = _nodes()
    with pytest.raises(ValueError, match="repetido"):
        generate_synthetic_edges([*nodes, nodes[0]])


def test_unknown_node_type_is_rejected() -> None:
    nodes = [*_nodes(), dataclasses.replace(_nodes()[0], node_type="enzyme")]
    with pytest.raises(ValueError, match="desconocido"):
        generate_synthetic_edges(nodes)


# --- Determinismo -------------------------------------------------------------------------


def test_same_seed_produces_identical_edges() -> None:
    nodes = _nodes()
    first = generate_synthetic_edges(nodes, SyntheticEdgeConfig(random_seed=123))
    second = generate_synthetic_edges(nodes, SyntheticEdgeConfig(random_seed=123))

    assert [e.to_dict() for e in first] == [e.to_dict() for e in second]


def test_repeated_calls_on_same_generator_are_identical() -> None:
    nodes = _nodes()
    generator = SyntheticEdgeGenerator()

    assert generator.generate_edges(nodes) == generator.generate_edges(nodes)


def test_node_input_order_does_not_change_result() -> None:
    nodes = _nodes()
    shuffled = list(nodes)
    random.Random(0).shuffle(shuffled)

    assert generate_synthetic_edges(nodes) == generate_synthetic_edges(shuffled)


def test_different_seeds_produce_different_edges() -> None:
    nodes = _nodes()
    first = generate_synthetic_edges(nodes, SyntheticEdgeConfig(random_seed=1))
    second = generate_synthetic_edges(nodes, SyntheticEdgeConfig(random_seed=2))

    assert first != second


def test_edges_follow_specification_export_order() -> None:
    edges = generate_synthetic_edges(_nodes(), ALL_RELATIONS_ALWAYS)
    keys = [
        (e.graph_id, e.source_type, e.relation_type, e.target_type, e.source_id, e.target_id)
        for e in edges
    ]

    assert keys == sorted(keys)


def _edges_of(edges: list[Edge], graph_id: str) -> list[Edge]:
    return [e for e in edges if e.graph_id == graph_id]


def test_instance_edges_do_not_depend_on_other_instances() -> None:
    """Una instancia produce las mismas aristas generada sola o junto con otras."""
    alone = generate_synthetic_edges(_nodes("synthetic:graph:0002"))
    together = generate_synthetic_edges(
        _nodes("synthetic:graph:0001") + _nodes("synthetic:graph:0002")
    )

    assert alone == _edges_of(together, "synthetic:graph:0002")


def test_disabling_a_relation_does_not_change_other_relations() -> None:
    nodes = _nodes()
    full = SyntheticEdgeConfig()
    reduced_probabilities = dict(full.relation_probabilities)
    del reduced_probabilities[TAXON_INTERACTS_WITH_TAXON]
    reduced = SyntheticEdgeConfig(relation_probabilities=reduced_probabilities)

    full_edges = generate_synthetic_edges(nodes, full)
    reduced_edges = generate_synthetic_edges(nodes, reduced)

    assert [e for e in full_edges if e.edge_type != TAXON_INTERACTS_WITH_TAXON] == reduced_edges


def test_changing_additive_only_affects_modulates_edges() -> None:
    """Cambiar el aditivo (escenario de intervención) no altera relaciones ajenas a él."""
    nodes = _nodes()
    as_control = [
        dataclasses.replace(n, attributes={**n.attributes, "control_label": "control_basal"})
        if n.node_type == "additive"
        else n
        for n in nodes
    ]
    modulates = {ADDITIVE_MODULATES_TAXON, ADDITIVE_MODULATES_FUNCTION}

    supplemented_edges = generate_synthetic_edges(nodes)
    control_edges = generate_synthetic_edges(as_control)

    assert [e for e in supplemented_edges if e.edge_type not in modulates] == [
        e for e in control_edges if e.edge_type not in modulates
    ]


# --- Serialización ------------------------------------------------------------------------


def test_edge_json_round_trip() -> None:
    edges = generate_synthetic_edges(_nodes(), ALL_RELATIONS_ALWAYS)

    for edge in edges:
        restored = Edge.from_dict(json.loads(json.dumps(edge.to_dict())))
        assert restored == edge


@pytest.mark.parametrize("field_name", ["evidence_id", "graph_id", "target_id"])
def test_from_dict_rejects_null_text_fields(field_name: str) -> None:
    """Un null no se convierte en el texto "None"."""
    record = generate_synthetic_edges(_nodes())[0].to_dict()
    record[field_name] = None

    with pytest.raises(ValueError, match=field_name):
        Edge.from_dict(record)


def test_from_dict_rejects_non_object_attributes() -> None:
    record = generate_synthetic_edges(_nodes())[0].to_dict()
    record["attributes"] = None

    with pytest.raises(ValueError, match="attributes"):
        Edge.from_dict(record)


# --- Validador ----------------------------------------------------------------------------


@pytest.fixture
def valid_graph() -> tuple[list[Node], list[Edge]]:
    nodes = _nodes()
    return nodes, generate_synthetic_edges(nodes, ALL_RELATIONS_ALWAYS)


def _first(edges: list[Edge], edge_type: EdgeType) -> Edge:
    return next(e for e in edges if e.edge_type == edge_type)


def test_validator_accepts_generated_graph(valid_graph: tuple[list[Node], list[Edge]]) -> None:
    nodes, edges = valid_graph

    assert find_edge_errors(nodes, edges) == []


def test_validator_rejects_disallowed_relation(
    valid_graph: tuple[list[Node], list[Edge]],
) -> None:
    nodes, edges = valid_graph
    edge = _first(edges, TAXON_HAS_CAPACITY_FUNCTION)
    bad = _replace_edge(edge, relation_type="produces", target_type="metabolite")

    errors = find_edge_errors(nodes, [bad])
    assert any("no es una relación permitida" in e for e in errors)


def test_validator_rejects_missing_endpoint(valid_graph: tuple[list[Node], list[Edge]]) -> None:
    nodes, edges = valid_graph
    bad = _replace_edge(edges[0], target_id="synthetic:missing:9999")

    errors = find_edge_errors(nodes, [bad])
    assert any("destino no existe" in e for e in errors)


def test_validator_rejects_endpoint_from_other_instance(
    valid_graph: tuple[list[Node], list[Edge]],
) -> None:
    nodes, edges = valid_graph
    bad = _replace_edge(edges[0], graph_id="synthetic:graph:9999")

    errors = find_edge_errors(nodes, [bad])
    assert any("origen no existe" in e for e in errors)


def test_validator_rejects_missing_required_attribute(
    valid_graph: tuple[list[Node], list[Edge]],
) -> None:
    nodes, edges = valid_graph
    bad = _replace_edge(_first(edges, DIET_PROVIDES_SUBSTRATE), attributes={"unit": "g/kg"})

    errors = find_edge_errors(nodes, [bad])
    assert any("falta el atributo obligatorio 'proportion'" in e for e in errors)


def test_validator_rejects_wrong_attribute_type(
    valid_graph: tuple[list[Node], list[Edge]],
) -> None:
    nodes, edges = valid_graph
    edge = _first(edges, DIET_PROVIDES_SUBSTRATE)
    bad = _replace_edge(edge, attributes={**edge.attributes, "proportion": "alto"})

    errors = find_edge_errors(nodes, [bad])
    assert any("'proportion' debe ser de tipo number" in e for e in errors)


def test_validator_rejects_unknown_cross_feeds_substrate(
    valid_graph: tuple[list[Node], list[Edge]],
) -> None:
    nodes, edges = valid_graph
    edge = _first(edges, FUNCTION_CROSS_FEEDS_FUNCTION)
    bad = _replace_edge(edge, attributes={"substrate_id": "synthetic:substrate:9999"})

    errors = find_edge_errors(nodes, [bad])
    assert any("substrate_id" in e for e in errors)


def test_validator_rejects_invalid_evidence_status(
    valid_graph: tuple[list[Node], list[Edge]],
) -> None:
    nodes, edges = valid_graph
    bad = _replace_edge(edges[0], evidence_status="proven")

    errors = find_edge_errors(nodes, [bad])
    assert any("evidence_status" in e for e in errors)


@pytest.mark.parametrize("status", ["observed", "annotated", "inferred", "hypothetical"])
def test_validator_requires_synthetic_evidence_by_default(
    valid_graph: tuple[list[Node], list[Edge]], status: str
) -> None:
    """Regla 6: sin criterio de evidencia aprobado, solo se admite evidencia sintética."""
    nodes, edges = valid_graph
    edge = _replace_edge(edges[0], evidence_status=status)

    assert any("debe ser 'synthetic'" in e for e in find_edge_errors(nodes, [edge]))
    assert find_edge_errors(nodes, [edge], require_synthetic=False) == []


def test_validate_edges_raises_with_all_errors(
    valid_graph: tuple[list[Node], list[Edge]],
) -> None:
    nodes, edges = valid_graph
    bad = [
        _replace_edge(edges[0], target_id="synthetic:missing:0001"),
        _replace_edge(edges[1], evidence_status="proven"),
    ]

    with pytest.raises(EdgeValidationError) as excinfo:
        validate_edges(nodes, bad)
    assert "destino no existe" in str(excinfo.value)
    assert "evidence_status" in str(excinfo.value)
