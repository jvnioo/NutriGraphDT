"""Pruebas unitarias para la generación de nodos sintéticos (DS-02)."""

import json

import pytest

from nutrigraphdt.data.synthetic.nodes import (
    Node,
    NodeCountConfig,
    NodeType,
    SyntheticNodeConfig,
    SyntheticNodeGenerator,
    generate_synthetic_nodes,
)


def test_generate_all_eight_node_types_by_default() -> None:
    """Verifica que se generen los 8 tipos de nodo del dominio por defecto."""
    generator = SyntheticNodeGenerator()
    nodes = generator.generate_all_nodes()

    present_types = {n.node_type for n in nodes}
    expected_types = {t.value for t in NodeType}

    assert present_types == expected_types
    assert len(expected_types) == 8


def test_node_common_envelope_contract() -> None:
    """Verifica que los campos comunes del contrato de nodo sean conformes."""
    config = SyntheticNodeConfig(
        graph_id="synthetic:graph:test_001",
        source_id="SYNTHETIC_V1",
    )
    generator = SyntheticNodeGenerator(config)
    nodes = generator.generate_all_nodes()

    for node in nodes:
        assert isinstance(node.graph_id, str)
        assert node.graph_id == "synthetic:graph:test_001"
        assert isinstance(node.node_id, str)
        assert node.node_id.startswith(f"synthetic:{node.node_type}:")
        assert node.node_type in [t.value for t in NodeType]
        assert node.source_id == "SYNTHETIC_V1"
        assert isinstance(node.attributes, dict)
        assert isinstance(node.missing_mask, dict)


def test_unique_node_ids_per_type_and_graph() -> None:
    """Verifica que todos los node_id generados sean estrictamente únicos."""
    generator = SyntheticNodeGenerator(
        SyntheticNodeConfig(
            counts=NodeCountConfig(
                diet=3,
                additive=3,
                substrate=10,
                taxon=25,
                function=20,
                metabolite=10,
                host=2,
                phenotype=5,
            )
        )
    )
    nodes = generator.generate_all_nodes()
    node_ids = [n.node_id for n in nodes]

    assert len(node_ids) == len(set(node_ids))


def test_diet_node_attributes_complete() -> None:
    """Verifica que los atributos del nodo Dieta (D) cumplan la especificación."""
    generator = SyntheticNodeGenerator()
    nodes = generator.generate_diet_nodes(count=2)

    assert len(nodes) == 2
    for node in nodes:
        assert node.node_type == NodeType.DIET.value
        attrs = node.attributes
        assert "name" in attrs and isinstance(attrs["name"], str)
        assert "ingredients" in attrs and isinstance(attrs["ingredients"], list)
        assert len(attrs["ingredients"]) > 0
        assert "composition" in attrs and isinstance(attrs["composition"], list)
        assert len(attrs["composition"]) > 0
        for comp in attrs["composition"]:
            assert "component_id" in comp and isinstance(comp["component_id"], str)
            assert "value" in comp and isinstance(comp["value"], (int, float))
            assert "unit" in comp and isinstance(comp["unit"], str)
        assert "source_version" in attrs and isinstance(attrs["source_version"], str)


def test_additive_node_attributes_complete() -> None:
    """Verifica que los atributos del nodo Aditivo (A) cumplan la especificación."""
    generator = SyntheticNodeGenerator()
    nodes = generator.generate_additive_nodes(count=3)

    assert len(nodes) == 3
    for node in nodes:
        assert node.node_type == NodeType.ADDITIVE.value
        attrs = node.attributes
        assert "category" in attrs and isinstance(attrs["category"], str)
        assert "substance" in attrs and isinstance(attrs["substance"], str)
        assert "dose" in attrs and isinstance(attrs["dose"], (int, float))
        assert "dose_unit" in attrs and isinstance(attrs["dose_unit"], str)
        assert "control_label" in attrs and isinstance(attrs["control_label"], str)


def test_substrate_node_attributes_complete() -> None:
    """Verifica que los atributos del nodo Sustrato (S) cumplan la especificación."""
    generator = SyntheticNodeGenerator()
    nodes = generator.generate_substrate_nodes(count=4)

    assert len(nodes) == 4
    for node in nodes:
        assert node.node_type == NodeType.SUBSTRATE.value
        attrs = node.attributes
        assert "chemical_id" in attrs and isinstance(attrs["chemical_id"], str)
        assert "name" in attrs and isinstance(attrs["name"], str)
        assert "quantity" in attrs and isinstance(attrs["quantity"], (int, float))
        assert attrs["quantity"] > 0
        assert "unit" in attrs and isinstance(attrs["unit"], str)


def test_taxon_node_attributes_complete_and_normalized() -> None:
    """Verifica que los atributos del nodo Taxón (T) cumplan la especificación y sumen ~1.0."""
    generator = SyntheticNodeGenerator()
    nodes = generator.generate_taxon_nodes(count=10)

    assert len(nodes) == 10
    total_abundance = sum(n.attributes["abundance"] for n in nodes)
    assert pytest.approx(total_abundance, rel=1e-3) == 1.0

    for node in nodes:
        assert node.node_type == NodeType.TAXON.value
        attrs = node.attributes
        assert "taxonomy_id" in attrs and isinstance(attrs["taxonomy_id"], str)
        assert "taxonomy_level" in attrs and isinstance(attrs["taxonomy_level"], str)
        assert "abundance" in attrs and isinstance(attrs["abundance"], (int, float))
        assert "abundance_unit" in attrs and isinstance(attrs["abundance_unit"], str)
        assert "quantification_method" in attrs and isinstance(attrs["quantification_method"], str)


def test_function_node_attributes_complete() -> None:
    """Verifica que los atributos del nodo Función (F) cumplan la especificación."""
    generator = SyntheticNodeGenerator()
    nodes = generator.generate_function_nodes(count=5)

    assert len(nodes) == 5
    for node in nodes:
        assert node.node_type == NodeType.FUNCTION.value
        attrs = node.attributes
        assert "function_id" in attrs and isinstance(attrs["function_id"], str)
        assert "function_type" in attrs and isinstance(attrs["function_type"], str)
        assert "annotation_source" in attrs and isinstance(attrs["annotation_source"], str)
        assert "annotation_value" in attrs and isinstance(attrs["annotation_value"], (int, float))
        assert "annotation_value_type" in attrs and isinstance(attrs["annotation_value_type"], str)
        assert "unit" in attrs and isinstance(attrs["unit"], str)


def test_metabolite_node_attributes_complete() -> None:
    """Verifica que los atributos del nodo Metabolito (M) cumplan la especificación."""
    generator = SyntheticNodeGenerator()
    nodes = generator.generate_metabolite_nodes(count=6)

    assert len(nodes) == 6
    for node in nodes:
        assert node.node_type == NodeType.METABOLITE.value
        attrs = node.attributes
        assert "chemical_id" in attrs and isinstance(attrs["chemical_id"], str)
        assert "name" in attrs and isinstance(attrs["name"], str)
        assert "sample_matrix" in attrs and isinstance(attrs["sample_matrix"], str)
        assert "concentration" in attrs and isinstance(attrs["concentration"], (int, float))
        assert "unit" in attrs and isinstance(attrs["unit"], str)


def test_host_node_attributes_complete() -> None:
    """Verifica que los atributos del nodo Huésped (H) cumplan la especificación."""
    config = SyntheticNodeConfig(species="chicken", gut_segment="cecum")
    generator = SyntheticNodeGenerator(config)
    nodes = generator.generate_host_nodes(count=1)

    assert len(nodes) == 1
    node = nodes[0]
    assert node.node_type == NodeType.HOST.value
    attrs = node.attributes
    assert attrs["species"] == "chicken"
    assert attrs["gut_segment"] == "cecum"
    assert "cohort_id" in attrs and isinstance(attrs["cohort_id"], str)
    assert "covariates" in attrs and isinstance(attrs["covariates"], dict)
    assert "age_days" in attrs["covariates"]
    assert "sex" in attrs["covariates"]
    assert "body_weight_g" in attrs["covariates"]


def test_phenotype_node_attributes_complete() -> None:
    """Verifica que los atributos del nodo Fenotipo (P) cumplan la especificación."""
    generator = SyntheticNodeGenerator()
    nodes = generator.generate_phenotype_nodes(count=2)

    assert len(nodes) == 2
    for node in nodes:
        assert node.node_type == NodeType.PHENOTYPE.value
        attrs = node.attributes
        assert "trait" in attrs and isinstance(attrs["trait"], str)
        assert "timepoint" in attrs and isinstance(attrs["timepoint"], str)
        assert "value" in attrs and isinstance(attrs["value"], (int, float))
        assert "unit" in attrs and isinstance(attrs["unit"], str)


def test_configurable_node_counts() -> None:
    """Verifica la generación de nodos con cantidades personalizadas por tipo."""
    counts = NodeCountConfig(
        diet=2,
        additive=0,
        substrate=5,
        taxon=8,
        function=3,
        metabolite=4,
        host=1,
        phenotype=0,
    )
    config = SyntheticNodeConfig(counts=counts)
    nodes = generate_synthetic_nodes(config)

    grouped = SyntheticNodeGenerator(config).generate_nodes_by_type()
    assert len(grouped[NodeType.DIET.value]) == 2
    assert len(grouped[NodeType.ADDITIVE.value]) == 0
    assert len(grouped[NodeType.SUBSTRATE.value]) == 5
    assert len(grouped[NodeType.TAXON.value]) == 8
    assert len(grouped[NodeType.FUNCTION.value]) == 3
    assert len(grouped[NodeType.METABOLITE.value]) == 4
    assert len(grouped[NodeType.HOST.value]) == 1
    assert len(grouped[NodeType.PHENOTYPE.value]) == 0

    assert len(nodes) == 2 + 0 + 5 + 8 + 3 + 4 + 1 + 0


def test_determinism_with_seed() -> None:
    """Verifica que semillas aleatorias idénticas produzcan nodos idénticos."""
    config1 = SyntheticNodeConfig(random_seed=12345)
    config2 = SyntheticNodeConfig(random_seed=12345)

    nodes1 = generate_synthetic_nodes(config1)
    nodes2 = generate_synthetic_nodes(config2)

    assert len(nodes1) == len(nodes2)
    for n1, n2 in zip(nodes1, nodes2, strict=True):
        assert n1.to_dict() == n2.to_dict()


def test_different_seeds_produce_different_values() -> None:
    """Verifica que diferentes semillas aleatorias produzcan atributos estocásticos distintos."""
    config1 = SyntheticNodeConfig(random_seed=1)
    config2 = SyntheticNodeConfig(random_seed=2)

    nodes1 = generate_synthetic_nodes(config1)
    nodes2 = generate_synthetic_nodes(config2)

    taxa1 = [n.attributes["abundance"] for n in nodes1 if n.node_type == NodeType.TAXON.value]
    taxa2 = [n.attributes["abundance"] for n in nodes2 if n.node_type == NodeType.TAXON.value]

    assert taxa1 != taxa2


def test_serialization_and_json_compatibility() -> None:
    """Verifica la serialización a/desde diccionario y la validez JSON."""
    generator = SyntheticNodeGenerator()
    nodes = generator.generate_all_nodes()

    for node in nodes:
        node_dict = node.to_dict()
        # Asegura compatibilidad de serialización JSON
        json_str = json.dumps(node_dict)
        deserialized_dict = json.loads(json_str)
        reconstructed = Node.from_dict(deserialized_dict)

        assert reconstructed == node
        assert reconstructed.node_id == node.node_id
        assert reconstructed.attributes == node.attributes
