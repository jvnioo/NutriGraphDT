"""Atributos de entrada DS-01 para escenarios sintéticos; sin rangos biológicos."""

from __future__ import annotations

import math
from typing import Any

from nutrigraphdt.data.synthetic.nodes import Node

# Tipos de intercambio de la tabla DS-01; basis incorpora contrato v2, sección 4.
ATTRIBUTE_TYPES: dict[str, dict[str, str]] = {
    "diet": {
        "name": "str",
        "ingredients": "strings",
        "composition": "composition",
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
        "basis": "str",
    },
    "host": {"species": "str", "gut_segment": "str", "cohort_id": "str", "covariates": "object"},
    "phenotype": {"trait": "str", "timepoint": "str", "value": "number", "unit": "str"},
}


def _matches(value: Any, kind: str) -> bool:
    if kind == "number":
        return (isinstance(value, int) and not isinstance(value, bool)) or (
            isinstance(value, float) and math.isfinite(value)
        )
    if kind == "str":
        return isinstance(value, str)
    if kind == "object":
        return isinstance(value, dict)
    if kind == "strings":
        return isinstance(value, list) and all(isinstance(v, str) for v in value)
    return isinstance(value, list)  # composition; elementos revisados por separado.


def find_node_attribute_errors(node: Node) -> list[str]:
    """Comprueba campos, tipos, composición y máscaras sin modificar el nodo.

    DS-01 permite null solo con máscara true. Las claves obligatorias no se omiten.
    No valida plausibilidad fisiológica ni establece vocabularios nuevos.
    """
    if not isinstance(node.attributes, dict) or not isinstance(node.missing_mask, dict):
        return []  # El envoltorio ya informa ambos errores.
    errors: list[str] = []
    attrs, mask = node.attributes, node.missing_mask
    for field, kind in ATTRIBUTE_TYPES.get(node.node_type, {}).items():
        if field not in attrs:
            errors.append(f"attributes.{field}: falta el atributo obligatorio.")
        elif attrs[field] is not None and not _matches(attrs[field], kind):
            errors.append(f"attributes.{field}: se esperaba {kind}.")
    composition = attrs.get("composition")
    if node.node_type == "diet" and isinstance(composition, list):
        for i, item in enumerate(composition):
            if not isinstance(item, dict):
                errors.append(f"attributes.composition.{i}: se esperaba object.")
                continue
            for field, kind in {"component_id": "str", "value": "number", "unit": "str"}.items():
                if field not in item or (
                    item[field] is not None and not _matches(item[field], kind)
                ):
                    errors.append(f"attributes.composition.{i}.{field}: se esperaba {kind}.")
    leaves: dict[str, Any] = {}

    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if not isinstance(key, str):
                    errors.append(f"attributes.{path}: clave JSON no textual.")
                visit(child, f"{path}.{key}" if path else str(key))
        elif isinstance(value, list):
            for i, child in enumerate(value):
                visit(child, f"{path}.{i}")
        else:
            leaves[path] = value
            if isinstance(value, float) and not math.isfinite(value):
                errors.append(f"attributes.{path}: número no finito.")
            elif value is not None and not isinstance(value, str | int | float | bool):
                errors.append(f"attributes.{path}: valor no compatible con JSON.")
            if value is None and mask.get(path) is not True:
                errors.append(f"attributes.{path}: null requiere missing_mask=true.")

    visit(attrs, "")
    for path, missing in mask.items():
        if not isinstance(path, str) or not isinstance(missing, bool):
            errors.append("missing_mask: se requieren rutas str y valores bool.")
        elif missing and (path not in leaves or leaves[path] is not None):
            errors.append(f"missing_mask.{path}: true requiere un atributo null existente.")
    return errors
