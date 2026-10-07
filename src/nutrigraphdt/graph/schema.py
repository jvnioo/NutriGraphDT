"""Version provisional del esquema estructural del grafo heterogéneo.

El esquema centraliza definiciones documentales sin aprobar ontologías, unidades físicas ni
relaciones científicas pendientes de Investigación. No valida ni transforma registros.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal

GRAPH_SCHEMA_VERSION: Final = "1.0.0-provisional"

StructuralStatus = Literal["approved_structure", "provisional", "hypothetical"]
AttributeType = Literal["str", "number", "object", "list[str]", "list[object]"]
EdgeType = tuple[str, str, str]

_NODE_SOURCE: Final = (
    "Esquema General v3.1, §2.1; "
    "`docs/synthetic-dataset-spec.md`, §Contrato de nodo > Tipos de nodo y atributos."
)
_NODE_ATTRIBUTE_SOURCE: Final = (
    "Esquema General v3.1, §2.1; "
    "`docs/synthetic-dataset-spec.md`, §Contrato de nodo > Tipos de nodo y atributos."
)
_RELATION_SOURCE: Final = (
    "Esquema General v3.1, §2.2; "
    "`docs/synthetic-dataset-spec.md`, §Contrato de arista > Relaciones permitidas."
)


@dataclass(frozen=True)
class AttributeSpec:
    """Definición de un atributo obligatorio y, si corresponde, de su unidad."""

    data_type: AttributeType
    unit_field: str | None
    structural_status: StructuralStatus
    source: str


@dataclass(frozen=True)
class NodeSpec:
    """Definición estructural de un tipo de nodo."""

    identifier: str
    spanish_name: str
    attributes: Mapping[str, AttributeSpec]
    structural_status: StructuralStatus
    source: str


@dataclass(frozen=True)
class RelationSpec:
    """Definición estructural de una tripleta dirigida permitida."""

    edge_type: EdgeType
    semantics: str
    required_attributes: Mapping[str, AttributeSpec]
    structural_status: StructuralStatus
    source: str


def _attribute(
    data_type: AttributeType,
    *,
    unit_field: str | None = None,
    source: str = _NODE_ATTRIBUTE_SOURCE,
) -> AttributeSpec:
    return AttributeSpec(
        data_type=data_type,
        unit_field=unit_field,
        structural_status="provisional",
        source=source,
    )


def _node(
    identifier: str,
    spanish_name: str,
    attributes: Mapping[str, AttributeSpec],
) -> NodeSpec:
    return NodeSpec(
        identifier=identifier,
        spanish_name=spanish_name,
        attributes=MappingProxyType(dict(attributes)),
        structural_status="provisional",
        source=_NODE_SOURCE,
    )


def _relation(
    edge_type: EdgeType,
    semantics: str,
    structural_status: StructuralStatus,
    required_attributes: Mapping[str, AttributeSpec] | None = None,
) -> RelationSpec:
    return RelationSpec(
        edge_type=edge_type,
        semantics=semantics,
        required_attributes=MappingProxyType(dict(required_attributes or {})),
        structural_status=structural_status,
        source=_RELATION_SOURCE,
    )


NODE_TYPES: Final[Mapping[str, NodeSpec]] = MappingProxyType(
    {
        "diet": _node(
            "diet",
            "Dieta",
            {
                "name": _attribute("str"),
                "ingredients": _attribute("list[str]"),
                "composition": _attribute(
                    "list[object]",
                    unit_field="composition[].unit",
                ),
                "source_version": _attribute("str"),
            },
        ),
        "additive": _node(
            "additive",
            "Aditivo",
            {
                "category": _attribute("str"),
                "substance": _attribute("str"),
                "dose": _attribute("number", unit_field="dose_unit"),
                "dose_unit": _attribute("str"),
                "control_label": _attribute("str"),
            },
        ),
        "substrate": _node(
            "substrate",
            "Sustrato",
            {
                "chemical_id": _attribute("str"),
                "name": _attribute("str"),
                "quantity": _attribute("number", unit_field="unit"),
                "unit": _attribute("str"),
            },
        ),
        "taxon": _node(
            "taxon",
            "Taxón / gremio",
            {
                "taxonomy_id": _attribute("str"),
                "taxonomy_level": _attribute("str"),
                "abundance": _attribute("number", unit_field="abundance_unit"),
                "abundance_unit": _attribute("str"),
                "quantification_method": _attribute("str"),
            },
        ),
        "function": _node(
            "function",
            "Función / ruta",
            {
                "function_id": _attribute("str"),
                "function_type": _attribute("str"),
                "annotation_source": _attribute("str"),
                "annotation_value": _attribute("number", unit_field="unit"),
                "annotation_value_type": _attribute("str"),
                "unit": _attribute("str"),
            },
        ),
        "metabolite": _node(
            "metabolite",
            "Metabolito",
            {
                "chemical_id": _attribute("str"),
                "name": _attribute("str"),
                "sample_matrix": _attribute("str"),
                "concentration": _attribute("number", unit_field="unit"),
                "unit": _attribute("str"),
            },
        ),
        "host": _node(
            "host",
            "Huésped",
            {
                "species": _attribute("str"),
                "gut_segment": _attribute("str"),
                "cohort_id": _attribute("str"),
                "covariates": _attribute("object"),
            },
        ),
        "phenotype": _node(
            "phenotype",
            "Fenotipo",
            {
                "trait": _attribute("str"),
                "timepoint": _attribute("str"),
                "value": _attribute("number", unit_field="unit"),
                "unit": _attribute("str"),
            },
        ),
    }
)

ALLOWED_RELATIONS: Final[Mapping[EdgeType, RelationSpec]] = MappingProxyType(
    {
        spec.edge_type: spec
        for spec in (
            _relation(
                ("diet", "provides", "substrate"),
                "Composición documentada de dieta.",
                "approved_structure",
                {
                    "proportion": _attribute(
                        "number",
                        unit_field="unit",
                        source=_RELATION_SOURCE,
                    ),
                    "unit": _attribute("str", source=_RELATION_SOURCE),
                },
            ),
            _relation(
                ("substrate", "available_to", "taxon"),
                "Recurso potencialmente disponible.",
                "provisional",
            ),
            _relation(
                ("taxon", "has_capacity", "function"),
                "Capacidad anotada, no actividad demostrada.",
                "provisional",
                {"annotation_source": _attribute("str", source=_RELATION_SOURCE)},
            ),
            _relation(
                ("function", "produces", "metabolite"),
                "Transformación candidata.",
                "provisional",
            ),
            _relation(
                ("metabolite", "measured_in", "host"),
                "Medición o exposición contextual.",
                "provisional",
                {"sample_matrix": _attribute("str", source=_RELATION_SOURCE)},
            ),
            _relation(
                ("additive", "modulates", "taxon"),
                "Hipótesis de modulación.",
                "hypothetical",
            ),
            _relation(
                ("additive", "modulates", "function"),
                "Hipótesis de modulación.",
                "hypothetical",
            ),
            _relation(
                ("metabolite", "associated_with", "phenotype"),
                "Asociación, no efecto causal.",
                "hypothetical",
            ),
            _relation(
                ("host", "exhibits", "phenotype"),
                "Correspondencia observacional.",
                "provisional",
                {"timepoint": _attribute("str", source=_RELATION_SOURCE)},
            ),
            _relation(
                ("taxon", "interacts_with", "taxon"),
                "Interacción ecológica candidata.",
                "hypothetical",
                {"interaction_type": _attribute("str", source=_RELATION_SOURCE)},
            ),
            _relation(
                ("function", "cross_feeds", "function"),
                "Sustrato cruzado candidato entre funciones.",
                "hypothetical",
                {"substrate_id": _attribute("str", source=_RELATION_SOURCE)},
            ),
        )
    }
)
