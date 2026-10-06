"""Pruebas de consistencia del esquema estructural provisional del grafo."""

from __future__ import annotations

from pathlib import Path

import pytest

from nutrigraphdt.data.schema import ALLOWED_EVIDENCE_STATUSES, ALLOWED_NODE_TYPES
from nutrigraphdt.data.schema import ALLOWED_RELATION_TYPES as TABULAR_RELATION_TYPES
from nutrigraphdt.data.synthetic.edges import ALLOWED_RELATIONS as SYNTHETIC_RELATIONS
from nutrigraphdt.data.synthetic.edges import EVIDENCE_STATUSES as SYNTHETIC_EVIDENCE_STATUSES
from nutrigraphdt.data.synthetic.nodes import NodeType
from nutrigraphdt.graph.schema import (
    ALLOWED_RELATIONS,
    GRAPH_SCHEMA_VERSION,
    NODE_TYPES,
    AttributeSpec,
    RelationSpec,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DOCUMENT = ROOT / "docs" / "graph-schema-v1.md"
DATA_SCHEMA_RELATION_LABELS_WITHOUT_TRIPLETS = {
    "consumes",
    "ferments",
    "affects",
    "targets",
    "participates_in",
}
DATA_SCHEMA_EVIDENCE_STATUSES_WITHOUT_SYNTHETIC_COUNTERPART = {"experimental", "literature"}


def test_graph_schema_version_is_distinctly_provisional() -> None:
    assert GRAPH_SCHEMA_VERSION == "1.0.0-provisional"


def test_node_type_identifiers_are_unique_and_match_existing_definitions() -> None:
    identifiers = [spec.identifier for spec in NODE_TYPES.values()]

    assert len(identifiers) == len(set(identifiers))
    assert set(NODE_TYPES) == set(identifiers)
    assert set(identifiers) == {node_type.value for node_type in NodeType}
    assert set(identifiers) == set(ALLOWED_NODE_TYPES)


def test_each_node_and_attribute_has_source_and_structural_status() -> None:
    allowed_statuses = {"approved_structure", "provisional", "hypothetical"}

    for node in NODE_TYPES.values():
        assert node.source
        assert node.structural_status in allowed_statuses
        assert node.attributes
        for attribute in node.attributes.values():
            assert isinstance(attribute, AttributeSpec)
            assert attribute.source
            assert attribute.structural_status in allowed_statuses


def test_attribute_types_and_measurement_units_are_well_formed() -> None:
    allowed_types = {"str", "number", "object", "list[str]", "list[object]"}

    for node in NODE_TYPES.values():
        for name, attribute in node.attributes.items():
            assert attribute.data_type in allowed_types, (node.identifier, name)
            if attribute.unit_field is None or attribute.unit_field == "composition[].unit":
                continue
            unit_attribute = node.attributes.get(attribute.unit_field)
            assert unit_attribute is not None, (node.identifier, name, attribute.unit_field)
            assert unit_attribute.data_type == "str", (node.identifier, name)

    composition = NODE_TYPES["diet"].attributes["composition"]
    assert composition.data_type == "list[object]"
    assert composition.unit_field == "composition[].unit"
    for relation in ALLOWED_RELATIONS.values():
        for name, attribute in relation.required_attributes.items():
            assert attribute.data_type in allowed_types, (relation.edge_type, name)
            assert attribute.source
            assert attribute.structural_status in {
                "approved_structure",
                "provisional",
                "hypothetical",
            }
            if attribute.unit_field is not None:
                unit_attribute = relation.required_attributes.get(attribute.unit_field)
                assert unit_attribute is not None, (relation.edge_type, name, attribute.unit_field)
                assert unit_attribute.data_type == "str", (relation.edge_type, name)


def test_allowed_relations_are_unique_valid_and_match_synthetic_catalog() -> None:
    edge_types = list(ALLOWED_RELATIONS)
    assert len(edge_types) == len(set(edge_types))

    for edge_type, relation in ALLOWED_RELATIONS.items():
        assert isinstance(relation, RelationSpec)
        assert len(edge_type) == 3
        assert edge_type == relation.edge_type
        assert edge_type[0] in NODE_TYPES
        assert edge_type[2] in NODE_TYPES
        assert edge_type[1]
        assert relation.semantics
        assert relation.source

    assert set(ALLOWED_RELATIONS) == set(SYNTHETIC_RELATIONS)
    for edge_type, relation in ALLOWED_RELATIONS.items():
        existing = SYNTHETIC_RELATIONS[edge_type]
        assert relation.semantics == existing.semantics
        assert relation.structural_status == existing.structural_status
        assert {
            name: attribute.data_type for name, attribute in relation.required_attributes.items()
        } == dict(existing.required_attributes)


def test_generic_tabular_relation_vocabulary_difference_is_documented() -> None:
    graph_relation_labels = {edge_type[1] for edge_type in ALLOWED_RELATIONS}
    assert graph_relation_labels <= TABULAR_RELATION_TYPES
    difference = TABULAR_RELATION_TYPES - graph_relation_labels
    assert difference == DATA_SCHEMA_RELATION_LABELS_WITHOUT_TRIPLETS

    document = SCHEMA_DOCUMENT.read_text(encoding="utf-8")
    for relation_label in difference:
        assert f"`{relation_label}`" in document
    assert "no equivale a una tripleta permitida" in document


def test_evidence_vocabulary_difference_is_documented_not_resolved() -> None:
    assert ALLOWED_EVIDENCE_STATUSES - SYNTHETIC_EVIDENCE_STATUSES == (
        DATA_SCHEMA_EVIDENCE_STATUSES_WITHOUT_SYNTHETIC_COUNTERPART
    )
    assert SYNTHETIC_EVIDENCE_STATUSES <= ALLOWED_EVIDENCE_STATUSES

    document = SCHEMA_DOCUMENT.read_text(encoding="utf-8")
    assert "`experimental`" in document
    assert "`literature`" in document
    assert "pendiente" in document.lower()


def test_unit_notation_difference_is_documented_not_normalized() -> None:
    document = SCHEMA_DOCUMENT.read_text(encoding="utf-8")

    assert "`g_kg`" in document
    assert "`g/kg`" in document
    assert "no se normalizan" in document


def test_schema_mappings_are_read_only() -> None:
    with pytest.raises(TypeError):
        NODE_TYPES["new_type"] = NODE_TYPES["diet"]  # type: ignore[index]
    with pytest.raises(TypeError):
        NODE_TYPES["diet"].attributes["new_attribute"] = NODE_TYPES["diet"].attributes["name"]  # type: ignore[index]
    with pytest.raises(TypeError):
        ALLOWED_RELATIONS[("diet", "new_relation", "substrate")] = next(  # type: ignore[index]
            iter(ALLOWED_RELATIONS.values())
        )
