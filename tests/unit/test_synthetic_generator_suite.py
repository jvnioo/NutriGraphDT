"""Suite transversal del generador sintético (DS-06).

Complementa las pruebas de cada módulo (nodos, aristas, escenarios y exportación) verificando
el generador completo de punta a punta, sobre una matriz de semillas y perfiles de cantidades.
Las reglas se transcriben de `docs/synthetic-dataset-spec.md` para detectar cualquier
divergencia entre la implementación y el contrato DS-01.

Estas pruebas verifican conformidad estructural y etiquetas sintéticas. No validan
plausibilidad biológica, rangos fisiológicos ni relaciones causales: la especificación no los
define.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from typing import Any

import pytest

from nutrigraphdt.data.synthetic import (
    ALLOWED_RELATIONS,
    NodeCountConfig,
    NodeType,
    SyntheticEdgeConfig,
    SyntheticNodeConfig,
    find_edge_errors,
)
from nutrigraphdt.data.synthetic.export import (
    SyntheticDataset,
    find_dataset_errors,
    generate_scenario_dataset,
    generate_synthetic_dataset,
)

# ---------------------------------------------------------------------------
# Contrato transcrito de docs/synthetic-dataset-spec.md
# ---------------------------------------------------------------------------

# Tabla "Tipos de nodo y atributos": atributo -> tipo de intercambio JSON.
REQUIRED_NODE_ATTRIBUTES: dict[str, dict[str, str]] = {
    "diet": {
        "name": "str",
        "ingredients": "list[str]",
        "composition": "list[object]",
        "source_version": "str",
    },
    "additive": {
        "category": "str",
        "substance": "str",
        "dose": "number",
        "dose_unit": "str",
        "control_label": "str",
    },
    "substrate": {"chemical_id": "str", "name": "str", "quantity": "number", "unit": "str"},
    "taxon": {
        "taxonomy_id": "str",
        "taxonomy_level": "str",
        "abundance": "number",
        "abundance_unit": "str",
        "quantification_method": "str",
    },
    "function": {
        "function_id": "str",
        "function_type": "str",
        "annotation_source": "str",
        "annotation_value": "number",
        "annotation_value_type": "str",
        "unit": "str",
    },
    "metabolite": {
        "chemical_id": "str",
        "name": "str",
        "sample_matrix": "str",
        "concentration": "number",
        "unit": "str",
    },
    "host": {"species": "str", "gut_segment": "str", "cohort_id": "str", "covariates": "object"},
    "phenotype": {"trait": "str", "timepoint": "str", "value": "number", "unit": "str"},
}

# Campos de cada elemento de `diet.attributes.composition`.
COMPOSITION_ITEM_FIELDS: dict[str, str] = {"component_id": "str", "value": "number", "unit": "str"}

# Atributos que identifican entidades y deben usar un espacio de nombres sintético
# ("Los identificadores sintéticos deben usar un espacio de nombres reconocible").
NAMESPACED_ATTRIBUTES: dict[str, tuple[str, ...]] = {
    "substrate": ("chemical_id",),
    "taxon": ("taxonomy_id",),
    "function": ("function_id", "annotation_source"),
    "metabolite": ("chemical_id",),
}

# ---------------------------------------------------------------------------
# Matriz de configuraciones
# ---------------------------------------------------------------------------

SEEDS: tuple[int, ...] = (0, 7, 42, 2026)

COUNT_PROFILES: dict[str, NodeCountConfig] = {
    "default": NodeCountConfig(),
    "minimal": NodeCountConfig(
        diet=1, additive=1, substrate=1, taxon=1, function=1, metabolite=1, host=1, phenotype=1
    ),
    "large": NodeCountConfig(
        diet=2, additive=3, substrate=9, taxon=15, function=12, metabolite=7, host=1, phenotype=5
    ),
}

# Perfil con tipos ausentes: la cantidad configurada (cero) también debe respetarse.
SPARSE_PROFILE = NodeCountConfig(
    diet=1, additive=0, substrate=3, taxon=4, function=0, metabolite=2, host=1, phenotype=0
)


def make_dataset(
    seed: int, counts: NodeCountConfig, graph_id: str = "synthetic:graph:0001"
) -> SyntheticDataset:
    """Genera un dataset completo con la misma semilla para nodos y aristas."""
    return generate_synthetic_dataset(
        SyntheticNodeConfig(graph_id=graph_id, counts=counts, random_seed=seed),
        SyntheticEdgeConfig(random_seed=seed),
    )


def dataset_as_records(dataset: SyntheticDataset) -> dict[str, Any]:
    """Representación JSON comparable de todo el contenido del dataset."""
    return {
        "metadata": dataset.metadata,
        "instances": [instance.to_dict() for instance in dataset.instances],
        "nodes": [node.to_dict() for node in dataset.nodes],
        "edges": [edge.to_dict() for edge in dataset.edges],
        "outputs": [output.to_dict() for output in dataset.outputs],
    }


MATRIX = [
    pytest.param(seed, profile, id=f"seed{seed}-{profile}")
    for seed in SEEDS
    for profile in COUNT_PROFILES
]


@pytest.fixture(scope="module")
def datasets() -> dict[tuple[int, str], SyntheticDataset]:
    """Genera una sola vez cada combinación de la matriz para todo el módulo."""
    return {
        (seed, profile): make_dataset(seed, counts)
        for seed in SEEDS
        for profile, counts in COUNT_PROFILES.items()
    }


def _matches(value: Any, kind: str) -> bool:
    if kind == "str":
        return isinstance(value, str) and bool(value)
    if kind == "number":
        return (
            not isinstance(value, bool) and isinstance(value, int | float) and math.isfinite(value)
        )
    if kind == "object":
        return isinstance(value, dict)
    if kind == "list[str]":
        return isinstance(value, list) and all(isinstance(item, str) and item for item in value)
    if kind == "list[object]":
        return isinstance(value, list) and all(isinstance(item, dict) for item in value)
    raise AssertionError(f"Tipo de contrato desconocido en la prueba: {kind}")


# ---------------------------------------------------------------------------
# Generación y cantidades
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_configured_counts_are_generated_exactly(
    datasets: dict[tuple[int, str], SyntheticDataset], seed: int, profile: str
) -> None:
    dataset = datasets[(seed, profile)]
    counts = COUNT_PROFILES[profile]
    produced = Counter(node.node_type for node in dataset.nodes)

    for node_type in NodeType:
        assert produced[node_type.value] == counts.get_count(node_type), node_type.value


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_standard_profiles_contain_all_eight_node_types(
    datasets: dict[tuple[int, str], SyntheticDataset], seed: int, profile: str
) -> None:
    """Regla 2: el perfil estándar incluye los ocho tipos y al menos un nodo de cada uno."""
    present = {node.node_type for node in datasets[(seed, profile)].nodes}

    assert present == {node_type.value for node_type in NodeType}


def test_zero_counts_are_respected_without_inventing_nodes() -> None:
    dataset = make_dataset(42, SPARSE_PROFILE)
    produced = Counter(node.node_type for node in dataset.nodes)

    for node_type in NodeType:
        assert produced[node_type.value] == SPARSE_PROFILE.get_count(node_type)
    assert find_dataset_errors(dataset) == []


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_metadata_counts_match_generated_content(
    datasets: dict[tuple[int, str], SyntheticDataset], seed: int, profile: str
) -> None:
    dataset = datasets[(seed, profile)]
    graph_id = dataset.instances[0].graph_id
    declared = dataset.metadata["counts"][graph_id]
    node_counts = Counter(node.node_type for node in dataset.nodes)
    edge_counts = Counter("|".join(edge.edge_type) for edge in dataset.edges)

    assert declared["nodes"] == {t.value: node_counts[t.value] for t in NodeType}
    assert declared["edges"] == dict(edge_counts)
    assert declared["outputs"] == len(dataset.outputs)


# ---------------------------------------------------------------------------
# Identificadores y atributos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_node_identifiers_are_unique_and_namespaced(
    datasets: dict[tuple[int, str], SyntheticDataset], seed: int, profile: str
) -> None:
    nodes = datasets[(seed, profile)].nodes
    keys = [(node.graph_id, node.node_type, node.node_id) for node in nodes]

    assert len(keys) == len(set(keys))
    for node in nodes:
        assert node.node_id.startswith(f"synthetic:{node.node_type}:"), node.node_id


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_every_node_has_the_contract_attributes_with_correct_types(
    datasets: dict[tuple[int, str], SyntheticDataset], seed: int, profile: str
) -> None:
    for node in datasets[(seed, profile)].nodes:
        required = REQUIRED_NODE_ATTRIBUTES[node.node_type]
        for attribute, kind in required.items():
            assert attribute in node.attributes, f"{node.node_id}: falta {attribute}"
            if node.missing_mask.get(attribute):
                assert node.attributes[attribute] is None
                continue
            assert _matches(node.attributes[attribute], kind), f"{node.node_id}.{attribute}"


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_diet_composition_items_follow_the_contract(
    datasets: dict[tuple[int, str], SyntheticDataset], seed: int, profile: str
) -> None:
    diets = [n for n in datasets[(seed, profile)].nodes if n.node_type == NodeType.DIET.value]

    assert diets
    for diet in diets:
        assert diet.attributes["composition"], diet.node_id
        for item in diet.attributes["composition"]:
            for field_name, kind in COMPOSITION_ITEM_FIELDS.items():
                assert _matches(item.get(field_name), kind), f"{diet.node_id}: {item}"


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_missing_masks_only_reference_existing_attributes(
    datasets: dict[tuple[int, str], SyntheticDataset], seed: int, profile: str
) -> None:
    for node in datasets[(seed, profile)].nodes:
        assert all(isinstance(flag, bool) for flag in node.missing_mask.values())
        assert set(node.missing_mask) <= set(node.attributes), node.node_id


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_all_records_share_the_instance_graph_id(
    datasets: dict[tuple[int, str], SyntheticDataset], seed: int, profile: str
) -> None:
    """Regla 8: una instancia no se mezcla con otra."""
    dataset = datasets[(seed, profile)]
    graph_ids = {instance.graph_id for instance in dataset.instances}

    assert len(graph_ids) == 1
    assert {node.graph_id for node in dataset.nodes} == graph_ids
    assert {edge.graph_id for edge in dataset.edges} <= graph_ids


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_instance_does_not_mix_species_segments_or_timepoints(
    datasets: dict[tuple[int, str], SyntheticDataset], seed: int, profile: str
) -> None:
    dataset = datasets[(seed, profile)]
    instance = dataset.instances[0]
    hosts = [n for n in dataset.nodes if n.node_type == NodeType.HOST.value]
    phenotypes = [n for n in dataset.nodes if n.node_type == NodeType.PHENOTYPE.value]

    assert {h.attributes["species"] for h in hosts} == {instance.species}
    assert {h.attributes["gut_segment"] for h in hosts} == {instance.gut_segment}
    assert len({p.attributes["timepoint"] for p in phenotypes}) <= 1


# ---------------------------------------------------------------------------
# Relaciones
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_relations_are_allowed_and_point_to_existing_nodes(
    datasets: dict[tuple[int, str], SyntheticDataset], seed: int, profile: str
) -> None:
    dataset = datasets[(seed, profile)]
    known = {(n.graph_id, n.node_type, n.node_id) for n in dataset.nodes}

    for edge in dataset.edges:
        assert edge.edge_type in ALLOWED_RELATIONS, edge.edge_type
        assert (edge.graph_id, edge.source_type, edge.source_id) in known
        assert (edge.graph_id, edge.target_type, edge.target_id) in known
        for attribute in ALLOWED_RELATIONS[edge.edge_type].required_attributes:
            assert attribute in edge.attributes, f"{edge.edge_type}: falta {attribute}"
    assert find_edge_errors(dataset.nodes, dataset.edges) == []


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_no_self_loops_or_duplicate_edges(
    datasets: dict[tuple[int, str], SyntheticDataset], seed: int, profile: str
) -> None:
    """Convenciones del generador DS-03: sin autolazos ni aristas repetidas."""
    edges = datasets[(seed, profile)].edges
    keys = [(e.graph_id, e.edge_type, e.source_id, e.target_id) for e in edges]

    assert len(keys) == len(set(keys))
    for edge in edges:
        if edge.source_type == edge.target_type:
            assert edge.source_id != edge.target_id, edge


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_whole_dataset_passes_integrity_validation(
    datasets: dict[tuple[int, str], SyntheticDataset], seed: int, profile: str
) -> None:
    assert find_dataset_errors(datasets[(seed, profile)]) == []


def test_relations_to_absent_node_types_are_not_created() -> None:
    """Sin nodos de un tipo no hay aristas que lo usen: no se inventan extremos."""
    dataset = make_dataset(42, SPARSE_PROFILE)
    absent = {t.value for t in NodeType if SPARSE_PROFILE.get_count(t) == 0}

    for edge in dataset.edges:
        assert edge.source_type not in absent
        assert edge.target_type not in absent


def test_forbidden_taxon_to_metabolite_relation_never_appears() -> None:
    for seed in SEEDS:
        dataset = make_dataset(seed, COUNT_PROFILES["large"])
        assert not any(
            e.source_type == "taxon" and e.target_type == "metabolite" for e in dataset.edges
        )


# ---------------------------------------------------------------------------
# Reproducibilidad
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_same_seed_and_configuration_reproduce_the_dataset(
    datasets: dict[tuple[int, str], SyntheticDataset], seed: int, profile: str
) -> None:
    regenerated = make_dataset(seed, COUNT_PROFILES[profile])

    assert dataset_as_records(regenerated) == dataset_as_records(datasets[(seed, profile)])


@pytest.mark.parametrize("profile", list(COUNT_PROFILES))
def test_different_seeds_change_values_but_not_structure(
    datasets: dict[tuple[int, str], SyntheticDataset], profile: str
) -> None:
    """Diferencia controlada: la semilla cambia valores sintéticos, no identidad ni conteos."""
    first, second = datasets[(0, profile)], datasets[(7, profile)]

    assert [(n.node_type, n.node_id) for n in first.nodes] == [
        (n.node_type, n.node_id) for n in second.nodes
    ]
    assert first.instances == second.instances
    assert dataset_as_records(first)["nodes"] != dataset_as_records(second)["nodes"]
    assert first.metadata["random_seed"] != second.metadata["random_seed"]


def test_metadata_records_the_seed_used() -> None:
    for seed in SEEDS:
        metadata = make_dataset(seed, COUNT_PROFILES["default"]).metadata
        assert metadata["random_seed"] == seed
        assert metadata["configuration"]["nodes"]["random_seed"] == seed
        assert metadata["configuration"]["edges"]["random_seed"] == seed


def test_generation_does_not_depend_on_other_instances() -> None:
    """Generar otra instancia antes no altera el resultado de la siguiente."""
    alone = make_dataset(42, COUNT_PROFILES["default"], graph_id="synthetic:graph:0002")
    make_dataset(7, COUNT_PROFILES["large"], graph_id="synthetic:graph:0001")
    after_other = make_dataset(42, COUNT_PROFILES["default"], graph_id="synthetic:graph:0002")

    assert dataset_as_records(alone) == dataset_as_records(after_other)


# ---------------------------------------------------------------------------
# Invariantes documentales: datos sintéticos y sin afirmaciones reales
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_every_record_is_labelled_as_synthetic(
    datasets: dict[tuple[int, str], SyntheticDataset], seed: int, profile: str
) -> None:
    dataset = datasets[(seed, profile)]

    assert dataset.metadata["is_synthetic"] is True
    assert all(instance.is_synthetic for instance in dataset.instances)
    assert {node.source_id for node in dataset.nodes} == {"SYNTHETIC_V1"}
    for edge in dataset.edges:
        assert (edge.evidence_id, edge.evidence_status, edge.evidence_method) == (
            "SYNTHETIC_V1",
            "synthetic",
            "synthetic_generator",
        )
    assert all(o.measured_or_predicted != "measured" for o in dataset.outputs)


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_entity_identifiers_use_a_synthetic_namespace(
    datasets: dict[tuple[int, str], SyntheticDataset], seed: int, profile: str
) -> None:
    """Ningún identificador de entidad reutiliza accesiones reales sin espacio sintético."""
    dataset = datasets[(seed, profile)]
    for node in dataset.nodes:
        for attribute in NAMESPACED_ATTRIBUTES.get(node.node_type, ()):
            value = node.attributes[attribute]
            assert isinstance(value, str) and value.startswith("synthetic:"), (
                f"{node.node_id}.{attribute} = {value!r}"
            )
    for edge in dataset.edges:
        annotation_source = edge.attributes.get("annotation_source")
        if annotation_source is not None:
            assert annotation_source.startswith("synthetic:")


def test_metadata_contains_no_non_deterministic_or_local_values() -> None:
    """La identidad reproducible no incluye fechas ni rutas locales."""
    metadata = make_dataset(42, COUNT_PROFILES["default"]).metadata
    text = json.dumps(metadata, ensure_ascii=False).lower()

    for key in _all_keys(metadata):
        name = key.lower()
        assert name not in NON_DETERMINISTIC_KEYS, key
        assert not name.endswith(("_at", "_path", "_dir")), key
    assert ":\\" not in text and "/home/" not in text and "/users/" not in text


NON_DETERMINISTIC_KEYS: frozenset[str] = frozenset(
    {"date", "datetime", "time", "timestamp", "created", "path", "output_dir", "input_dir"}
)


def _all_keys(value: Any) -> list[str]:
    if isinstance(value, dict):
        keys = [str(key) for key in value]
        for child in value.values():
            keys.extend(_all_keys(child))
        return keys
    if isinstance(value, list):
        return [key for child in value for key in _all_keys(child)]
    return []


# ---------------------------------------------------------------------------
# Escenarios (DS-04) dentro del dataset exportable
# ---------------------------------------------------------------------------


def test_scenario_dataset_passes_the_same_transversal_checks() -> None:
    dataset = generate_scenario_dataset()
    keys = [(n.graph_id, n.node_type, n.node_id) for n in dataset.nodes]

    assert find_dataset_errors(dataset) == []
    assert len(keys) == len(set(keys))
    assert {i.scenario_id for i in dataset.instances} == {"basal", "intervention"}
    for node in dataset.nodes:
        for attribute, kind in REQUIRED_NODE_ATTRIBUTES[node.node_type].items():
            assert _matches(node.attributes[attribute], kind), f"{node.node_id}.{attribute}"
    assert {e.evidence_status for e in dataset.edges} == {"synthetic"}


# ---------------------------------------------------------------------------
# Configuraciones inválidas y errores esperados
# ---------------------------------------------------------------------------


def test_mismatched_seeds_cannot_identify_a_dataset() -> None:
    with pytest.raises(ValueError, match="semilla"):
        generate_synthetic_dataset(
            SyntheticNodeConfig(random_seed=1), SyntheticEdgeConfig(random_seed=2)
        )


@pytest.mark.parametrize("scenario_id", ["", "baseline", "BASAL", "treatment"])
def test_unknown_scenario_id_is_rejected(scenario_id: str) -> None:
    with pytest.raises(ValueError, match="scenario_id"):
        generate_synthetic_dataset(scenario_id=scenario_id)


@pytest.mark.parametrize(
    "relation_probabilities",
    [
        {("taxon", "produces", "metabolite"): 0.5},
        {("taxon", "has_capacity", "function"): 1.5},
        {("taxon", "has_capacity", "function"): -0.1},
    ],
    ids=["forbidden-relation", "probability-above-one", "negative-probability"],
)
def test_invalid_edge_configuration_is_rejected(
    relation_probabilities: dict[tuple[str, str, str], float],
) -> None:
    with pytest.raises(ValueError):
        SyntheticEdgeConfig(relation_probabilities=relation_probabilities)


def test_empty_graph_id_is_caught_before_export() -> None:
    """Un graph_id vacío produce aristas inválidas y la validación del dataset lo detecta."""
    dataset = make_dataset(42, COUNT_PROFILES["default"], graph_id="")

    assert any("graph_id" in error for error in find_dataset_errors(dataset))
