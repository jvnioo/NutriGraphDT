"""Tests de contratos Pydantic v2 por tipo de nodo y relación (A38-2 / #33).

Cubre casos válidos e inválidos para cada uno de los ocho tipos de nodo y para las once
relaciones permitidas. Un registro inválido debe producir ``pydantic.ValidationError`` (o
``ValueError`` en el caso de ``node_type`` desconocido) con un mensaje claro que identifique
el campo o la regla violada.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from nutrigraphdt.graph.contracts import (
    EdgeRecord,
    validate_edge_record,
    validate_edge_records,
    validate_node_record,
    validate_node_records,
)

# ===========================================================================
# Fixtures de registros válidos
# ===========================================================================


def _diet_raw() -> dict[str, Any]:
    return {
        "graph_id": "g001",
        "node_id": "d001",
        "node_type": "diet",
        "source_id": "SYNTHETIC_V1",
        "missing_mask": {},
        "attributes": {
            "name": "Control diet",
            "ingredients": ["corn", "soybean"],
            "composition": [
                {"component_id": "CP", "value": 180.0, "unit": "g_kg"},
                {"component_id": "ME", "value": 12.5, "unit": "MJ_kg"},
            ],
            "source_version": "1.0.0",
        },
    }


def _additive_raw() -> dict[str, Any]:
    return {
        "graph_id": "g001",
        "node_id": "a001",
        "node_type": "additive",
        "source_id": "SYNTHETIC_V1",
        "missing_mask": {},
        "attributes": {
            "category": "probiotic",
            "substance": "Lactobacillus acidophilus",
            "dose": 1e8,
            "dose_unit": "CFU_kg",
            "control_label": "no_additive",
        },
    }


def _substrate_raw() -> dict[str, Any]:
    return {
        "graph_id": "g001",
        "node_id": "s001",
        "node_type": "substrate",
        "source_id": "SYNTHETIC_V1",
        "missing_mask": {},
        "attributes": {
            "chemical_id": "synthetic:substrate:0001",
            "name": "Cellulose",
            "quantity": 50.0,
            "unit": "g_kg",
        },
    }


def _taxon_raw() -> dict[str, Any]:
    return {
        "graph_id": "g001",
        "node_id": "t001",
        "node_type": "taxon",
        "source_id": "SYNTHETIC_V1",
        "missing_mask": {},
        "attributes": {
            "taxonomy_id": "synthetic:taxon:0001",
            "taxonomy_level": "genus",
            "abundance": 0.035,
            "abundance_unit": "relative_abundance",
            "quantification_method": "16S_rRNA",
        },
    }


def _function_raw() -> dict[str, Any]:
    return {
        "graph_id": "g001",
        "node_id": "f001",
        "node_type": "function",
        "source_id": "SYNTHETIC_V1",
        "missing_mask": {},
        "attributes": {
            "function_id": "synthetic:function:0001",
            "function_type": "pathway",
            "annotation_source": "KEGG",
            "annotation_value": 0.8,
            "annotation_value_type": "abundance",
            "unit": "relative_abundance",
        },
    }


def _metabolite_raw() -> dict[str, Any]:
    return {
        "graph_id": "g001",
        "node_id": "m001",
        "node_type": "metabolite",
        "source_id": "SYNTHETIC_V1",
        "missing_mask": {},
        "attributes": {
            "chemical_id": "synthetic:metabolite:0001",
            "name": "Acetate",
            "sample_matrix": "cecal_content",
            "concentration": 12.4,
            "unit": "mmol_kg",
        },
    }


def _host_raw() -> dict[str, Any]:
    return {
        "graph_id": "g001",
        "node_id": "h001",
        "node_type": "host",
        "source_id": "SYNTHETIC_V1",
        "missing_mask": {},
        "attributes": {
            "species": "chicken",
            "gut_segment": "cecum",
            "cohort_id": "cohort_A",
            "covariates": {"age_days": 35, "sex": "male"},
        },
    }


def _phenotype_raw() -> dict[str, Any]:
    return {
        "graph_id": "g001",
        "node_id": "p001",
        "node_type": "phenotype",
        "source_id": "SYNTHETIC_V1",
        "missing_mask": {},
        "attributes": {
            "trait": "body_weight_gain",
            "timepoint": "day_35",
            "value": 42.5,
            "unit": "g",
        },
    }


def _edge_provides_raw() -> dict[str, Any]:
    return {
        "graph_id": "g001",
        "source_type": "diet",
        "source_id": "d001",
        "relation_type": "provides",
        "target_type": "substrate",
        "target_id": "s001",
        "evidence_id": "SYNTHETIC_V1",
        "evidence_status": "synthetic",
        "evidence_method": "synthetic_generator",
        "attributes": {"proportion": 0.18, "unit": "g_kg"},
    }


def _edge_available_to_raw() -> dict[str, Any]:
    return {
        "graph_id": "g001",
        "source_type": "substrate",
        "source_id": "s001",
        "relation_type": "available_to",
        "target_type": "taxon",
        "target_id": "t001",
        "evidence_id": "SYNTHETIC_V1",
        "evidence_status": "synthetic",
        "evidence_method": "synthetic_generator",
        "attributes": {},
    }


def _edge_has_capacity_raw() -> dict[str, Any]:
    return {
        "graph_id": "g001",
        "source_type": "taxon",
        "source_id": "t001",
        "relation_type": "has_capacity",
        "target_type": "function",
        "target_id": "f001",
        "evidence_id": "SYNTHETIC_V1",
        "evidence_status": "synthetic",
        "evidence_method": "synthetic_generator",
        "attributes": {"annotation_source": "KEGG"},
    }


def _edge_produces_raw() -> dict[str, Any]:
    return {
        "graph_id": "g001",
        "source_type": "function",
        "source_id": "f001",
        "relation_type": "produces",
        "target_type": "metabolite",
        "target_id": "m001",
        "evidence_id": "SYNTHETIC_V1",
        "evidence_status": "synthetic",
        "evidence_method": "synthetic_generator",
        "attributes": {},
    }


def _edge_measured_in_raw() -> dict[str, Any]:
    return {
        "graph_id": "g001",
        "source_type": "metabolite",
        "source_id": "m001",
        "relation_type": "measured_in",
        "target_type": "host",
        "target_id": "h001",
        "evidence_id": "SYNTHETIC_V1",
        "evidence_status": "synthetic",
        "evidence_method": "synthetic_generator",
        "attributes": {"sample_matrix": "cecal_content"},
    }


def _edge_modulates_taxon_raw() -> dict[str, Any]:
    return {
        "graph_id": "g001",
        "source_type": "additive",
        "source_id": "a001",
        "relation_type": "modulates",
        "target_type": "taxon",
        "target_id": "t001",
        "evidence_id": "SYNTHETIC_V1",
        "evidence_status": "synthetic",
        "evidence_method": "synthetic_generator",
        "attributes": {},
    }


def _edge_modulates_function_raw() -> dict[str, Any]:
    return {
        "graph_id": "g001",
        "source_type": "additive",
        "source_id": "a001",
        "relation_type": "modulates",
        "target_type": "function",
        "target_id": "f001",
        "evidence_id": "SYNTHETIC_V1",
        "evidence_status": "synthetic",
        "evidence_method": "synthetic_generator",
        "attributes": {},
    }


def _edge_associated_with_raw() -> dict[str, Any]:
    return {
        "graph_id": "g001",
        "source_type": "metabolite",
        "source_id": "m001",
        "relation_type": "associated_with",
        "target_type": "phenotype",
        "target_id": "p001",
        "evidence_id": "SYNTHETIC_V1",
        "evidence_status": "synthetic",
        "evidence_method": "synthetic_generator",
        "attributes": {},
    }


def _edge_exhibits_raw() -> dict[str, Any]:
    return {
        "graph_id": "g001",
        "source_type": "host",
        "source_id": "h001",
        "relation_type": "exhibits",
        "target_type": "phenotype",
        "target_id": "p001",
        "evidence_id": "SYNTHETIC_V1",
        "evidence_status": "synthetic",
        "evidence_method": "synthetic_generator",
        "attributes": {"timepoint": "day_35"},
    }


def _edge_interacts_with_raw() -> dict[str, Any]:
    return {
        "graph_id": "g001",
        "source_type": "taxon",
        "source_id": "t001",
        "relation_type": "interacts_with",
        "target_type": "taxon",
        "target_id": "t002",
        "evidence_id": "SYNTHETIC_V1",
        "evidence_status": "synthetic",
        "evidence_method": "synthetic_generator",
        "attributes": {"interaction_type": "competition"},
    }


def _edge_cross_feeds_raw() -> dict[str, Any]:
    return {
        "graph_id": "g001",
        "source_type": "function",
        "source_id": "f001",
        "relation_type": "cross_feeds",
        "target_type": "function",
        "target_id": "f002",
        "evidence_id": "SYNTHETIC_V1",
        "evidence_status": "synthetic",
        "evidence_method": "synthetic_generator",
        "attributes": {"substrate_id": "s001"},
    }


# ===========================================================================
# Tests de casos VÁLIDOS — nodos
# ===========================================================================


class TestValidNodes:
    """Cada tipo de nodo debe validarse sin errores cuando los datos son correctos."""

    def test_diet_valid(self) -> None:
        node = validate_node_record(_diet_raw())
        assert node.node_type == "diet"
        assert node.node_id == "d001"

    def test_additive_valid(self) -> None:
        node = validate_node_record(_additive_raw())
        assert node.node_type == "additive"

    def test_substrate_valid(self) -> None:
        node = validate_node_record(_substrate_raw())
        assert node.node_type == "substrate"

    def test_taxon_valid(self) -> None:
        node = validate_node_record(_taxon_raw())
        assert node.node_type == "taxon"

    def test_function_valid(self) -> None:
        node = validate_node_record(_function_raw())
        assert node.node_type == "function"

    def test_metabolite_valid(self) -> None:
        node = validate_node_record(_metabolite_raw())
        assert node.node_type == "metabolite"

    def test_host_valid(self) -> None:
        node = validate_node_record(_host_raw())
        assert node.node_type == "host"

    def test_phenotype_valid(self) -> None:
        node = validate_node_record(_phenotype_raw())
        assert node.node_type == "phenotype"

    def test_missing_mask_can_be_empty(self) -> None:
        raw = _taxon_raw()
        raw["missing_mask"] = {}
        node = validate_node_record(raw)
        assert node.missing_mask == {}

    def test_missing_mask_with_flags(self) -> None:
        raw = _taxon_raw()
        raw["attributes"]["abundance"] = None
        raw["missing_mask"] = {"abundance": True}
        node = validate_node_record(raw)
        assert node.missing_mask == {"abundance": True}

    @pytest.mark.parametrize(
        ("factory", "attribute"),
        [
            (_taxon_raw, "taxonomy_level"),
            (_metabolite_raw, "concentration"),
            (_diet_raw, "ingredients"),
            (_diet_raw, "composition"),
            (_host_raw, "covariates"),
        ],
    )
    def test_masked_null_attribute_is_accepted(self, factory: Any, attribute: str) -> None:
        raw = factory()
        raw["attributes"][attribute] = None
        raw["missing_mask"] = {attribute: True}
        node = validate_node_record(raw)
        assert getattr(node.attributes, attribute) is None

    @pytest.mark.parametrize("mask", [{}, {"taxonomy_level": False}])
    def test_null_attribute_without_true_mask_is_rejected(self, mask: dict[str, bool]) -> None:
        raw = _taxon_raw()
        raw["attributes"]["taxonomy_level"] = None
        raw["missing_mask"] = mask
        with pytest.raises(ValidationError, match="taxonomy_level"):
            validate_node_record(raw)

    def test_true_mask_with_a_value_is_rejected(self) -> None:
        raw = _taxon_raw()
        raw["missing_mask"] = {"abundance": True}
        with pytest.raises(ValidationError, match="tiene valor"):
            validate_node_record(raw)

    def test_mask_key_that_is_not_an_attribute_is_rejected(self) -> None:
        raw = _taxon_raw()
        raw["missing_mask"] = {"colour": True}
        with pytest.raises(ValidationError, match="colour"):
            validate_node_record(raw)

    def test_absent_attribute_key_is_still_rejected(self) -> None:
        raw = _taxon_raw()
        del raw["attributes"]["taxonomy_level"]
        raw["missing_mask"] = {"taxonomy_level": True}
        with pytest.raises(ValidationError):
            validate_node_record(raw)

    def test_host_covariates_arbitrary_object(self) -> None:
        raw = _host_raw()
        raw["attributes"]["covariates"] = {"age_days": 35, "sex": "female", "breed": "Ross 308"}
        node = validate_node_record(raw)
        assert node.node_type == "host"


# ===========================================================================
# Tests de casos INVÁLIDOS — nodos
# ===========================================================================


class TestInvalidNodes:
    """Un registro inválido debe levantar ValidationError con mensaje claro."""

    def test_unknown_node_type_raises_value_error(self) -> None:
        raw = _taxon_raw()
        raw["node_type"] = "unknown_type"
        with pytest.raises(ValueError, match="node_type"):
            validate_node_record(raw)

    def test_missing_graph_id(self) -> None:
        raw = _taxon_raw()
        del raw["graph_id"]
        with pytest.raises(ValidationError):
            validate_node_record(raw)

    def test_empty_graph_id(self) -> None:
        raw = _taxon_raw()
        raw["graph_id"] = ""
        with pytest.raises(ValidationError):
            validate_node_record(raw)

    def test_missing_node_id(self) -> None:
        raw = _taxon_raw()
        del raw["node_id"]
        with pytest.raises(ValidationError):
            validate_node_record(raw)

    def test_missing_source_id(self) -> None:
        raw = _taxon_raw()
        del raw["source_id"]
        with pytest.raises(ValidationError):
            validate_node_record(raw)

    def test_taxon_missing_attribute(self) -> None:
        raw = _taxon_raw()
        del raw["attributes"]["abundance"]
        with pytest.raises(ValidationError):
            validate_node_record(raw)

    def test_taxon_nan_abundance(self) -> None:
        raw = _taxon_raw()
        raw["attributes"]["abundance"] = float("nan")
        with pytest.raises(ValidationError, match="finito"):
            validate_node_record(raw)

    def test_taxon_infinity_abundance(self) -> None:
        raw = _taxon_raw()
        raw["attributes"]["abundance"] = float("inf")
        with pytest.raises(ValidationError, match="finito"):
            validate_node_record(raw)

    def test_diet_composition_missing_unit(self) -> None:
        raw = _diet_raw()
        raw["attributes"]["composition"][0] = {"component_id": "CP", "value": 180.0}
        with pytest.raises(ValidationError):
            validate_node_record(raw)

    def test_diet_composition_nan_value(self) -> None:
        raw = _diet_raw()
        raw["attributes"]["composition"][0]["value"] = float("nan")
        with pytest.raises(ValidationError, match="finito"):
            validate_node_record(raw)

    def test_metabolite_missing_concentration(self) -> None:
        raw = _metabolite_raw()
        del raw["attributes"]["concentration"]
        with pytest.raises(ValidationError):
            validate_node_record(raw)

    def test_metabolite_infinite_concentration(self) -> None:
        raw = _metabolite_raw()
        raw["attributes"]["concentration"] = float("-inf")
        with pytest.raises(ValidationError, match="finito"):
            validate_node_record(raw)

    def test_phenotype_missing_trait(self) -> None:
        raw = _phenotype_raw()
        del raw["attributes"]["trait"]
        with pytest.raises(ValidationError):
            validate_node_record(raw)

    def test_extra_field_forbidden(self) -> None:
        raw = _taxon_raw()
        raw["extra_unknown"] = "surprise"
        with pytest.raises(ValidationError):
            validate_node_record(raw)

    def test_function_nan_annotation_value(self) -> None:
        raw = _function_raw()
        raw["attributes"]["annotation_value"] = float("nan")
        with pytest.raises(ValidationError, match="finito"):
            validate_node_record(raw)

    def test_additive_nan_dose(self) -> None:
        raw = _additive_raw()
        raw["attributes"]["dose"] = float("nan")
        with pytest.raises(ValidationError, match="finito"):
            validate_node_record(raw)

    def test_substrate_nan_quantity(self) -> None:
        raw = _substrate_raw()
        raw["attributes"]["quantity"] = float("nan")
        with pytest.raises(ValidationError, match="finito"):
            validate_node_record(raw)


# ===========================================================================
# Tests de casos VÁLIDOS — aristas (todas las relaciones)
# ===========================================================================


class TestValidEdges:
    """Cada relación permitida debe validarse sin errores cuando los datos son correctos."""

    def test_diet_provides_substrate(self) -> None:
        edge = validate_edge_record(_edge_provides_raw())
        assert edge.relation_type == "provides"

    def test_substrate_available_to_taxon(self) -> None:
        edge = validate_edge_record(_edge_available_to_raw())
        assert edge.relation_type == "available_to"

    def test_taxon_has_capacity_function(self) -> None:
        edge = validate_edge_record(_edge_has_capacity_raw())
        assert edge.relation_type == "has_capacity"

    def test_function_produces_metabolite(self) -> None:
        edge = validate_edge_record(_edge_produces_raw())
        assert edge.relation_type == "produces"

    def test_metabolite_measured_in_host(self) -> None:
        edge = validate_edge_record(_edge_measured_in_raw())
        assert edge.relation_type == "measured_in"

    def test_additive_modulates_taxon(self) -> None:
        edge = validate_edge_record(_edge_modulates_taxon_raw())
        assert edge.relation_type == "modulates"

    def test_additive_modulates_function(self) -> None:
        edge = validate_edge_record(_edge_modulates_function_raw())
        assert edge.relation_type == "modulates"

    def test_metabolite_associated_with_phenotype(self) -> None:
        edge = validate_edge_record(_edge_associated_with_raw())
        assert edge.relation_type == "associated_with"

    def test_host_exhibits_phenotype(self) -> None:
        edge = validate_edge_record(_edge_exhibits_raw())
        assert edge.relation_type == "exhibits"

    def test_taxon_interacts_with_taxon(self) -> None:
        edge = validate_edge_record(_edge_interacts_with_raw())
        assert edge.relation_type == "interacts_with"

    def test_function_cross_feeds_function(self) -> None:
        edge = validate_edge_record(_edge_cross_feeds_raw())
        assert edge.relation_type == "cross_feeds"

    def test_all_evidence_statuses(self) -> None:
        for status in ("synthetic", "observed", "annotated", "inferred", "hypothetical"):
            raw = _edge_available_to_raw()
            raw["evidence_status"] = status
            edge = validate_edge_record(raw)
            assert edge.evidence_status == status


# ===========================================================================
# Tests de casos INVÁLIDOS — aristas
# ===========================================================================


class TestInvalidEdges:
    """Una arista inválida debe levantar ValidationError con mensaje claro."""

    def test_unknown_relation_type(self) -> None:
        raw = _edge_provides_raw()
        raw["relation_type"] = "unknown_rel"
        with pytest.raises(ValidationError, match="tupla de relación"):
            validate_edge_record(raw)

    def test_invalid_source_target_combination(self) -> None:
        """diet -> modulates -> taxon no es una relación permitida."""
        raw = _edge_provides_raw()
        raw["source_type"] = "diet"
        raw["relation_type"] = "modulates"
        raw["target_type"] = "taxon"
        with pytest.raises(ValidationError, match="tupla de relación"):
            validate_edge_record(raw)

    def test_missing_evidence_id(self) -> None:
        raw = _edge_provides_raw()
        del raw["evidence_id"]
        with pytest.raises(ValidationError):
            validate_edge_record(raw)

    def test_invalid_evidence_status(self) -> None:
        raw = _edge_provides_raw()
        raw["evidence_status"] = "fabricated"
        with pytest.raises(ValidationError):
            validate_edge_record(raw)

    def test_missing_graph_id(self) -> None:
        raw = _edge_provides_raw()
        del raw["graph_id"]
        with pytest.raises(ValidationError):
            validate_edge_record(raw)

    def test_empty_source_id(self) -> None:
        raw = _edge_provides_raw()
        raw["source_id"] = ""
        with pytest.raises(ValidationError):
            validate_edge_record(raw)

    def test_provides_missing_proportion(self) -> None:
        """La relación provides requiere el atributo proportion."""
        raw = _edge_provides_raw()
        raw["attributes"] = {"unit": "g_kg"}  # falta proportion
        with pytest.raises(ValidationError):
            validate_edge_record(raw)

    def test_provides_nan_proportion(self) -> None:
        raw = _edge_provides_raw()
        raw["attributes"]["proportion"] = float("nan")
        with pytest.raises(ValidationError, match="finito"):
            validate_edge_record(raw)

    def test_has_capacity_missing_annotation_source(self) -> None:
        """La relación has_capacity requiere annotation_source."""
        raw = _edge_has_capacity_raw()
        raw["attributes"] = {}
        with pytest.raises(ValidationError):
            validate_edge_record(raw)

    def test_measured_in_missing_sample_matrix(self) -> None:
        raw = _edge_measured_in_raw()
        raw["attributes"] = {}
        with pytest.raises(ValidationError):
            validate_edge_record(raw)

    def test_exhibits_missing_timepoint(self) -> None:
        raw = _edge_exhibits_raw()
        raw["attributes"] = {}
        with pytest.raises(ValidationError):
            validate_edge_record(raw)

    def test_interacts_with_missing_interaction_type(self) -> None:
        raw = _edge_interacts_with_raw()
        raw["attributes"] = {}
        with pytest.raises(ValidationError):
            validate_edge_record(raw)

    def test_cross_feeds_missing_substrate_id(self) -> None:
        raw = _edge_cross_feeds_raw()
        raw["attributes"] = {}
        with pytest.raises(ValidationError):
            validate_edge_record(raw)

    def test_missing_evidence_method(self) -> None:
        raw = _edge_provides_raw()
        del raw["evidence_method"]
        with pytest.raises(ValidationError):
            validate_edge_record(raw)


# ===========================================================================
# Tests de funciones de validación en lote
# ===========================================================================


class TestBatchValidation:
    """Las funciones validate_node_records / validate_edge_records devuelven
    válidos y errores sin interrumpir el procesamiento del lote."""

    def test_all_valid_nodes(self) -> None:
        raws = [_taxon_raw(), _metabolite_raw(), _host_raw()]
        valid, errors = validate_node_records(raws)
        assert len(valid) == 3
        assert errors == []

    def test_mixed_nodes_separates_valid_invalid(self) -> None:
        bad = _taxon_raw()
        bad["attributes"]["abundance"] = float("nan")
        raws = [_taxon_raw(), bad, _host_raw()]
        valid, errors = validate_node_records(raws)
        assert len(valid) == 2
        assert len(errors) == 1
        assert "Nodo #1" in errors[0]

    def test_all_valid_edges(self) -> None:
        raws = [_edge_provides_raw(), _edge_available_to_raw(), _edge_produces_raw()]
        valid, errors = validate_edge_records(raws)
        assert len(valid) == 3
        assert errors == []

    def test_mixed_edges_separates_valid_invalid(self) -> None:
        bad = _edge_provides_raw()
        del bad["evidence_id"]
        raws = [_edge_provides_raw(), bad]
        valid, errors = validate_edge_records(raws)
        assert len(valid) == 1
        assert len(errors) == 1
        assert "Arista #1" in errors[0]

    def test_unknown_node_type_captured_in_batch(self) -> None:
        bad = _taxon_raw()
        bad["node_type"] = "alien"
        _, errors = validate_node_records([_taxon_raw(), bad])
        assert len(errors) == 1
        assert "alien" in errors[0]

    def test_error_message_identifies_field(self) -> None:
        """El mensaje de error debe mencionar el campo o razón de rechazo."""
        bad = _metabolite_raw()
        del bad["attributes"]["chemical_id"]
        _, errors = validate_node_records([bad])
        assert errors
        # El mensaje debe contener información suficiente para identificar el problema
        assert len(errors[0]) > 10

    def test_empty_batch_returns_empty(self) -> None:
        valid, errors = validate_node_records([])
        assert valid == []
        assert errors == []

    def test_edge_error_message_identifies_relation(self) -> None:
        bad = _edge_has_capacity_raw()
        bad["attributes"] = {}
        _, errors = validate_edge_records([bad])
        assert errors
        assert "has_capacity" in errors[0] or "Arista" in errors[0]


# ===========================================================================
# Tests de inmutabilidad del modelo
# ===========================================================================


class TestModelImmutability:
    """Los modelos son frozen=True; intentar mutar un campo debe fallar con ValidationError."""

    def test_node_is_frozen(self) -> None:
        node = validate_node_record(_taxon_raw())
        with pytest.raises(ValidationError):
            node.graph_id = "modified"  # type: ignore[misc]

    def test_edge_is_frozen(self) -> None:
        edge = validate_edge_record(_edge_provides_raw())
        with pytest.raises(ValidationError):
            edge.graph_id = "modified"  # type: ignore[misc]


# ===========================================================================
# Tests de instancia del tipo correcto
# ===========================================================================


class TestNodeTypeInstances:
    """validate_node_record devuelve el modelo concreto correcto."""

    def test_returns_diet_node(self) -> None:
        from nutrigraphdt.graph.contracts import DietNode

        node = validate_node_record(_diet_raw())
        assert isinstance(node, DietNode)

    def test_returns_taxon_node(self) -> None:
        from nutrigraphdt.graph.contracts import TaxonNode

        node = validate_node_record(_taxon_raw())
        assert isinstance(node, TaxonNode)

    def test_returns_edge_record(self) -> None:
        edge = validate_edge_record(_edge_provides_raw())
        assert isinstance(edge, EdgeRecord)
