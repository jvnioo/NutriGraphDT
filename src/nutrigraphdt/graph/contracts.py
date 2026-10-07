"""Contratos Pydantic v2 para nodos, aristas, instancias y salidas del grafo (A38-2 / #33).

Cada modelo representa el esquema de validación **de entrada al grafo** tal como lo define
``docs/synthetic-dataset-spec.md`` (schema_version 1.0.0) y el esquema estructural del grafo
en ``src/nutrigraphdt/graph/schema.py``.

Uso:
    >>> from nutrigraphdt.graph.contracts import validate_node_record, validate_edge_record
    >>> node = validate_node_record(raw_dict)      # lanza ValidationError si es inválido
    >>> edge = validate_edge_record(raw_dict)

Las funciones ``validate_node_record`` y ``validate_edge_record`` son la interfaz preferida.
Los modelos concretos (``DietNode``, ``TaxonNode``, etc.) se pueden importar directamente
cuando se requiere tipado preciso.

Datos ausentes
--------------
Un atributo puede ser ``None`` solo si su ``missing_mask`` es ``True`` (y viceversa), igual que
en DS-01 y la regla NOD-07. Así los contratos aceptan los nodos reales con atributos que la
fuente no informa, sin aceptar un valor vacío no declarado.

Limitaciones provisionales
--------------------------
- Los rangos numéricos (abundancias, dosis, concentraciones) no están fijados por Investigación
  y por tanto NO se validan en esta versión.  Solo se verifica finitud y tipo.
- Los vocabularios de ``taxonomy_level``, ``function_type``, ``annotation_value_type`` y
  ``sample_matrix`` son abiertos («str») hasta que Investigación confirme las ontologías.
- Los ``evidence_status`` válidos incluyen el conjunto del contrato de arista de DS-01.
"""

from __future__ import annotations

import math
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Constantes de dominio (refleja data/schema.py y graph/schema.py)
# ---------------------------------------------------------------------------

_ALLOWED_NODE_TYPES: frozenset[str] = frozenset(
    {"diet", "additive", "substrate", "taxon", "function", "metabolite", "host", "phenotype"}
)

_ALLOWED_RELATION_TYPES: frozenset[tuple[str, str, str]] = frozenset(
    {
        ("diet", "provides", "substrate"),
        ("substrate", "available_to", "taxon"),
        ("taxon", "has_capacity", "function"),
        ("function", "produces", "metabolite"),
        ("metabolite", "measured_in", "host"),
        ("additive", "modulates", "taxon"),
        ("additive", "modulates", "function"),
        ("metabolite", "associated_with", "phenotype"),
        ("host", "exhibits", "phenotype"),
        ("taxon", "interacts_with", "taxon"),
        ("function", "cross_feeds", "function"),
    }
)

_ALLOWED_EVIDENCE_STATUSES: frozenset[str] = frozenset(
    {"synthetic", "observed", "annotated", "inferred", "hypothetical"}
)

# ---------------------------------------------------------------------------
# Validador reutilizable de número finito
# ---------------------------------------------------------------------------

FiniteFloat = Annotated[float, Field(description="Número finito (no NaN ni Infinity)")]


def _assert_finite(v: float | None) -> float | None:
    if v is not None and not math.isfinite(v):
        raise ValueError(f"El valor debe ser un número finito, recibido: {v!r}")
    return v


# ---------------------------------------------------------------------------
# Configuración base de todos los modelos
# ---------------------------------------------------------------------------


class _StrictBase(BaseModel):
    """Base con configuración estricta y prohibición de campos extra."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


# ---------------------------------------------------------------------------
# Modelos de atributos por tipo de nodo
# ---------------------------------------------------------------------------


class CompositionItem(_StrictBase):
    """Elemento de la lista ``composition`` de un nodo ``diet``."""

    component_id: str = Field(..., min_length=1)
    value: float
    unit: str = Field(..., min_length=1)

    @field_validator("value")
    @classmethod
    def _value_finite(cls, v: float) -> float:
        _assert_finite(v)
        return v


class DietAttributes(_StrictBase):
    """Atributos obligatorios del nodo ``diet`` (DS-01, §Tipos de nodo y atributos)."""

    name: str | None = Field(..., min_length=1)
    ingredients: list[str] | None
    composition: list[CompositionItem] | None
    source_version: str | None = Field(..., min_length=1)


class AdditiveAttributes(_StrictBase):
    """Atributos obligatorios del nodo ``additive``."""

    category: str | None = Field(..., min_length=1)
    substance: str | None = Field(..., min_length=1)
    dose: float | None
    dose_unit: str | None = Field(..., min_length=1)
    control_label: str | None = Field(..., min_length=1)

    @field_validator("dose")
    @classmethod
    def _dose_finite(cls, v: float | None) -> float | None:
        return _assert_finite(v)


class SubstrateAttributes(_StrictBase):
    """Atributos obligatorios del nodo ``substrate``."""

    chemical_id: str | None = Field(..., min_length=1)
    name: str | None = Field(..., min_length=1)
    quantity: float | None
    unit: str | None = Field(..., min_length=1)

    @field_validator("quantity")
    @classmethod
    def _quantity_finite(cls, v: float | None) -> float | None:
        return _assert_finite(v)


class TaxonAttributes(_StrictBase):
    """Atributos obligatorios del nodo ``taxon``."""

    taxonomy_id: str | None = Field(..., min_length=1)
    taxonomy_level: str | None = Field(..., min_length=1)
    abundance: float | None
    abundance_unit: str | None = Field(..., min_length=1)
    quantification_method: str | None = Field(..., min_length=1)

    @field_validator("abundance")
    @classmethod
    def _abundance_finite(cls, v: float | None) -> float | None:
        return _assert_finite(v)


class FunctionAttributes(_StrictBase):
    """Atributos obligatorios del nodo ``function``."""

    function_id: str | None = Field(..., min_length=1)
    function_type: str | None = Field(..., min_length=1)
    annotation_source: str | None = Field(..., min_length=1)
    annotation_value: float | None
    annotation_value_type: str | None = Field(..., min_length=1)
    unit: str | None = Field(..., min_length=1)

    @field_validator("annotation_value")
    @classmethod
    def _annotation_value_finite(cls, v: float | None) -> float | None:
        return _assert_finite(v)


class MetaboliteAttributes(_StrictBase):
    """Atributos obligatorios del nodo ``metabolite``."""

    chemical_id: str | None = Field(..., min_length=1)
    name: str | None = Field(..., min_length=1)
    sample_matrix: str | None = Field(..., min_length=1)
    concentration: float | None
    unit: str | None = Field(..., min_length=1)

    @field_validator("concentration")
    @classmethod
    def _concentration_finite(cls, v: float | None) -> float | None:
        return _assert_finite(v)


class HostAttributes(_StrictBase):
    """Atributos obligatorios del nodo ``host``."""

    species: str | None = Field(..., min_length=1)
    gut_segment: str | None = Field(..., min_length=1)
    cohort_id: str | None = Field(..., min_length=1)
    covariates: dict[str, Any] | None


class PhenotypeAttributes(_StrictBase):
    """Atributos obligatorios del nodo ``phenotype``."""

    trait: str | None = Field(..., min_length=1)
    timepoint: str | None = Field(..., min_length=1)
    value: float | None
    unit: str | None = Field(..., min_length=1)

    @field_validator("value")
    @classmethod
    def _value_finite(cls, v: float | None) -> float | None:
        return _assert_finite(v)


# ---------------------------------------------------------------------------
# Modelos de nodo por tipo (envelope completo)
# ---------------------------------------------------------------------------

_NodeType = Literal[
    "diet", "additive", "substrate", "taxon", "function", "metabolite", "host", "phenotype"
]


class _BaseNodeRecord(_StrictBase):
    """Campos comunes a todos los nodos del contrato DS-01.

    Todo atributo del tipo debe estar presente. Puede ser ``None`` solo si
    ``missing_mask[atributo]`` es ``True``, y una máscara ``True`` exige ``None`` (DS-01,
    ausencia de datos; regla NOD-07). Las claves de ``missing_mask`` son atributos del tipo.
    """

    graph_id: str = Field(..., min_length=1)
    node_id: str = Field(..., min_length=1)
    node_type: _NodeType
    source_id: str = Field(..., min_length=1)
    missing_mask: dict[str, bool]

    @model_validator(mode="after")
    def _missing_mask_matches_attributes(self) -> _BaseNodeRecord:
        attributes = getattr(self, "attributes", None)
        if not isinstance(attributes, BaseModel):
            return self
        names = type(attributes).model_fields
        unknown = sorted(set(self.missing_mask) - set(names))
        if unknown:
            raise ValueError(f"missing_mask declara claves que no son atributos: {unknown}")
        for name in names:
            value = getattr(attributes, name)
            masked = self.missing_mask.get(name, False)
            if value is None and not masked:
                raise ValueError(f"'{name}' es null pero missing_mask['{name}'] no es true.")
            if value is not None and masked:
                raise ValueError(f"missing_mask['{name}'] es true pero '{name}' tiene valor.")
        return self


class DietNode(_BaseNodeRecord):
    """Nodo de tipo ``diet``."""

    node_type: Literal["diet"] = "diet"
    attributes: DietAttributes


class AdditiveNode(_BaseNodeRecord):
    """Nodo de tipo ``additive``."""

    node_type: Literal["additive"] = "additive"
    attributes: AdditiveAttributes


class SubstrateNode(_BaseNodeRecord):
    """Nodo de tipo ``substrate``."""

    node_type: Literal["substrate"] = "substrate"
    attributes: SubstrateAttributes


class TaxonNode(_BaseNodeRecord):
    """Nodo de tipo ``taxon``."""

    node_type: Literal["taxon"] = "taxon"
    attributes: TaxonAttributes


class FunctionNode(_BaseNodeRecord):
    """Nodo de tipo ``function``."""

    node_type: Literal["function"] = "function"
    attributes: FunctionAttributes


class MetaboliteNode(_BaseNodeRecord):
    """Nodo de tipo ``metabolite``."""

    node_type: Literal["metabolite"] = "metabolite"
    attributes: MetaboliteAttributes


class HostNode(_BaseNodeRecord):
    """Nodo de tipo ``host``."""

    node_type: Literal["host"] = "host"
    attributes: HostAttributes


class PhenotypeNode(_BaseNodeRecord):
    """Nodo de tipo ``phenotype``."""

    node_type: Literal["phenotype"] = "phenotype"
    attributes: PhenotypeAttributes


# Unión discriminada de todos los tipos de nodo
AnyNodeRecord = (
    DietNode
    | AdditiveNode
    | SubstrateNode
    | TaxonNode
    | FunctionNode
    | MetaboliteNode
    | HostNode
    | PhenotypeNode
)

_NODE_MODEL_MAP: dict[str, type[_BaseNodeRecord]] = {
    "diet": DietNode,
    "additive": AdditiveNode,
    "substrate": SubstrateNode,
    "taxon": TaxonNode,
    "function": FunctionNode,
    "metabolite": MetaboliteNode,
    "host": HostNode,
    "phenotype": PhenotypeNode,
}

# ---------------------------------------------------------------------------
# Modelos de atributos de arista por tipo de relación
# ---------------------------------------------------------------------------


class ProvidesEdgeAttributes(_StrictBase):
    """Atributos de la relación ``diet → provides → substrate``."""

    proportion: float
    unit: str = Field(..., min_length=1)

    @field_validator("proportion")
    @classmethod
    def _proportion_finite(cls, v: float | None) -> float | None:
        return _assert_finite(v)


class HasCapacityEdgeAttributes(_StrictBase):
    """Atributos de la relación ``taxon → has_capacity → function``."""

    annotation_source: str = Field(..., min_length=1)


class MeasuredInEdgeAttributes(_StrictBase):
    """Atributos de la relación ``metabolite → measured_in → host``."""

    sample_matrix: str = Field(..., min_length=1)


class ExhibitsEdgeAttributes(_StrictBase):
    """Atributos de la relación ``host → exhibits → phenotype``."""

    timepoint: str = Field(..., min_length=1)


class InteractsWithEdgeAttributes(_StrictBase):
    """Atributos de la relación ``taxon → interacts_with → taxon``."""

    interaction_type: str = Field(..., min_length=1)


class CrossFeedsEdgeAttributes(_StrictBase):
    """Atributos de la relación ``function → cross_feeds → function``."""

    substrate_id: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Modelo de arista genérico
# ---------------------------------------------------------------------------

_EDGE_ATTRIBUTE_MODELS: dict[
    tuple[str, str, str],
    type[_StrictBase] | None,
] = {
    ("diet", "provides", "substrate"): ProvidesEdgeAttributes,
    ("substrate", "available_to", "taxon"): None,
    ("taxon", "has_capacity", "function"): HasCapacityEdgeAttributes,
    ("function", "produces", "metabolite"): None,
    ("metabolite", "measured_in", "host"): MeasuredInEdgeAttributes,
    ("additive", "modulates", "taxon"): None,
    ("additive", "modulates", "function"): None,
    ("metabolite", "associated_with", "phenotype"): None,
    ("host", "exhibits", "phenotype"): ExhibitsEdgeAttributes,
    ("taxon", "interacts_with", "taxon"): InteractsWithEdgeAttributes,
    ("function", "cross_feeds", "function"): CrossFeedsEdgeAttributes,
}

_EvidenceStatus = Literal["synthetic", "observed", "annotated", "inferred", "hypothetical"]


class EdgeRecord(_StrictBase):
    """Registro de arista del contrato DS-01.

    Valida la tupla ``(source_type, relation_type, target_type)`` contra las relaciones
    permitidas, el ``evidence_status`` contra el vocabulario del contrato y, cuando la
    relación requiere atributos específicos, que ``attributes`` los contenga.
    """

    graph_id: str = Field(..., min_length=1)
    source_type: str = Field(..., min_length=1)
    source_id: str = Field(..., min_length=1)
    relation_type: str = Field(..., min_length=1)
    target_type: str = Field(..., min_length=1)
    target_id: str = Field(..., min_length=1)
    evidence_id: str = Field(..., min_length=1)
    evidence_status: _EvidenceStatus
    evidence_method: str = Field(..., min_length=1)
    attributes: dict[str, Any]

    @model_validator(mode="after")
    def _validate_relation_and_attributes(self) -> EdgeRecord:
        key = (self.source_type, self.relation_type, self.target_type)
        if key not in _ALLOWED_RELATION_TYPES:
            raise ValueError(
                f"La tupla de relación {key!r} no está permitida. "
                f"Relaciones válidas: {sorted(_ALLOWED_RELATION_TYPES)}"
            )
        attr_model = _EDGE_ATTRIBUTE_MODELS.get(key)
        if attr_model is not None:
            # Valida el subconjunto de atributos requeridos
            attr_model.model_validate(self.attributes)
        return self


# ---------------------------------------------------------------------------
# Funciones de validación de entrada al grafo
# ---------------------------------------------------------------------------


def validate_node_record(raw: dict[str, Any]) -> _BaseNodeRecord:
    """Valida un diccionario de nodo contra el contrato DS-01 schema v1.

    Parameters
    ----------
    raw:
        Diccionario con los campos del nodo tal como llegan del preprocesamiento.

    Returns
    -------
    _BaseNodeRecord
        Instancia del modelo concreto correspondiente al ``node_type`` indicado.

    Raises
    ------
    pydantic.ValidationError
        Si algún campo falta, tiene tipo incorrecto, contiene NaN/Infinity o
        el ``node_type`` no es uno de los ocho permitidos.
    ValueError
        Si ``node_type`` no está presente en el diccionario o no es reconocido.
    """
    node_type = raw.get("node_type")
    if node_type not in _NODE_MODEL_MAP:
        raise ValueError(
            f"node_type {node_type!r} no reconocido. Tipos permitidos: {sorted(_NODE_MODEL_MAP)}"
        )
    return _NODE_MODEL_MAP[node_type].model_validate(raw)


def validate_edge_record(raw: dict[str, Any]) -> EdgeRecord:
    """Valida un diccionario de arista contra el contrato DS-01 schema v1.

    Parameters
    ----------
    raw:
        Diccionario con los campos de la arista tal como llegan del preprocesamiento.

    Returns
    -------
    EdgeRecord
        Instancia validada.

    Raises
    ------
    pydantic.ValidationError
        Si algún campo falta, tiene tipo incorrecto o la tupla de relación no está
        en el catálogo de relaciones permitidas.
    """
    return EdgeRecord.model_validate(raw)


def validate_node_records(
    records: list[dict[str, Any]],
) -> tuple[list[_BaseNodeRecord], list[str]]:
    """Valida una lista de registros de nodo y devuelve válidos y mensajes de error.

    Parameters
    ----------
    records:
        Lista de diccionarios de nodo tal como salen del preprocesamiento.

    Returns
    -------
    valid:
        Registros que pasaron la validación.
    errors:
        Mensajes de error para cada registro inválido, con índice e identificador.
    """
    from pydantic import ValidationError

    valid: list[_BaseNodeRecord] = []
    errors: list[str] = []
    for i, raw in enumerate(records):
        node_id = raw.get("node_id", "<sin_id>")
        node_type = raw.get("node_type", "<sin_tipo>")
        try:
            valid.append(validate_node_record(raw))
        except (ValueError, ValidationError) as exc:
            errors.append(f"Nodo #{i} ({node_type}/{node_id}): {exc}")
    return valid, errors


def validate_edge_records(
    records: list[dict[str, Any]],
) -> tuple[list[EdgeRecord], list[str]]:
    """Valida una lista de registros de arista y devuelve válidos y mensajes de error.

    Parameters
    ----------
    records:
        Lista de diccionarios de arista tal como salen del preprocesamiento.

    Returns
    -------
    valid:
        Registros que pasaron la validación.
    errors:
        Mensajes de error para cada registro inválido, con índice e identificador.
    """
    from pydantic import ValidationError

    valid: list[EdgeRecord] = []
    errors: list[str] = []
    for i, raw in enumerate(records):
        src = raw.get("source_id", "<sin_id>")
        rel = raw.get("relation_type", "<sin_relacion>")
        dst = raw.get("target_id", "<sin_id>")
        try:
            valid.append(validate_edge_record(raw))
        except (ValueError, ValidationError) as exc:
            errors.append(f"Arista #{i} ({src} -{rel}-> {dst}): {exc}")
    return valid, errors
