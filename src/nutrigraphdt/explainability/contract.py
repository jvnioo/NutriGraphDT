"""Contrato de salida de las explicaciones (A55-P3, #156).

Define la forma versionada de una explicación de un modelo de NutriGraphDT: la importancia
**calculada** de nodos, atributos y aristas para una salida del modelo, el subgrafo explicativo
top-k y la **evidencia declarada** de cada arista en el grafo, con trazabilidad a la corrida
(`run.json`) que produjo el modelo. La especificación completa está en
`docs/models/explanation-contract.md`; este módulo la hace ejecutable.

`validate_explanation(data)` devuelve la explicación validada o lanza `ExplanationContractError`
con todas las infracciones, cada una con su regla (`EXP-01` a `EXP-09`).

La importancia es una propiedad del modelo entrenado, no del sistema biológico: el contrato
separa `importance` (calculada) de `evidence` (copiada del grafo) y exige las advertencias de
interpretación que lo dicen.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping
from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from nutrigraphdt.data.schema import ALLOWED_EVIDENCE_STATUSES
from nutrigraphdt.graph.schema import ALLOWED_RELATIONS, NODE_TYPES

EXPLANATION_FORMAT: Final = "nutrigraphdt-explanation"
EXPLANATION_FORMAT_VERSION: Final = "1.0.0"

REVERSE_PREFIX: Final = "rev_"
"""Prefijo de las relaciones inversas que agrega la conversión a `HeteroData` para el paso de
mensajes (`host → rev_measured_in → metabolite`)."""

EVIDENCE_METHOD_STATUS: Final[Mapping[str, str]] = {
    "measurement": "observed",
    "database_annotation": "annotated",
    "literature_curation": "annotated",
    "model_prediction": "inferred",
    "statistical_association": "inferred",
    "expert_hypothesis": "hypothetical",
    "synthetic_generator": "synthetic",
}
"""Método de evidencia → estado que respalda: el vocabulario cerrado de EDG-04 (reglas de
integridad) más `synthetic_generator`, el método del generador sintético."""

REQUIRED_WARNINGS: Final[frozenset[str]] = frozenset(
    {"association_not_causation", "importance_is_not_evidence"}
)
"""Advertencias de interpretación que toda explicación declara (EXP-08)."""

SYNTHETIC_WARNING: Final = "synthetic_data"
"""Advertencia obligatoria si la instancia explicada es sintética (EXP-08)."""

ATTENTION_WARNING: Final = "attention_is_not_explanation"
"""Advertencia obligatoria si la importancia proviene de pesos de atención (EXP-08)."""

Text = Annotated[str, Field(min_length=1)]


class ExplanationContractError(ValueError):
    """La explicación no cumple el contrato; `problems` lista cada infracción."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("Explicación inválida:\n- " + "\n- ".join(problems))


class _Strict(BaseModel):
    # `extra="forbid"`: un campo no declarado se rechaza, así no se cuelan datos crudos ni
    # tensores en el artefacto (EXP-01).
    model_config = ConfigDict(extra="forbid", frozen=True)


# ---------------------------------------------------------------------------
# Trazabilidad
# ---------------------------------------------------------------------------


class SplitRef(_Strict):
    version: Text
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class RunRef(_Strict):
    """Corrida que produjo el modelo explicado: los campos de su `run.json`."""

    run_id: Text
    run_json: Text
    """Ruta del `run.json`, relativa a la raíz del repositorio (nunca absoluta)."""
    format_version: Text
    variant: Text
    seed: int
    dataset_id: Text
    split: SplitRef
    git_commit: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")] | None

    @field_validator("run_json")
    @classmethod
    def _relative(cls, value: str) -> str:
        if value.startswith(("/", "\\")) or (len(value) > 1 and value[1] == ":"):
            raise ValueError("debe ser una ruta relativa a la raíz del repositorio.")
        return value


class ExplainerRef(_Strict):
    """Método que calculó la importancia y su configuración completa."""

    name: Text
    library: Text
    library_version: Text
    algorithm: Text
    explanation_type: Literal["model", "phenomenon"]
    node_mask_type: Literal["object", "attributes", "common_attributes"] | None
    edge_mask_type: Literal["object"] | None
    seed: int
    config: dict[str, Any]
    uses_attention: bool = False
    """`True` si la importancia proviene de pesos de atención (obliga a advertirlo)."""


class TargetRef(_Strict):
    """Salida del modelo que se explica, para una instancia."""

    graph_id: Text
    sample_id: Text | None
    is_synthetic: bool
    output: Text
    """Nombre de la salida: una de `MODEL_OUTPUT_NAMES` (`log_butyrate_acetate`…) o un AGCC."""
    output_index: Annotated[int, Field(ge=0)]
    unit: Text
    model_output: float | None
    """Valor que predijo el modelo para esa salida, en `unit`; `null` si no se registra."""


# ---------------------------------------------------------------------------
# Importancia calculada
# ---------------------------------------------------------------------------


class Scale(_Strict):
    """Escala de los valores de importancia."""

    kind: Literal["normalized", "raw"]
    range: tuple[float, float]
    normalization: Text
    """Cómo se normalizó (`max_abs`, `sum_to_one`…) o `none` si es `raw`."""
    aggregation: Text
    """Cómo se agregó una máscara por elemento a un valor por nodo, atributo o arista."""


class NodeImportance(_Strict):
    node_type: Text
    node_id: Text
    importance: float


class AttributeImportance(_Strict):
    node_type: Text
    node_id: Text
    attribute: Text
    """Nombre de la columna de `x` en `node_feature_schema` (`abundance (relative_abundance)`)."""
    importance: float


class Evidence(_Strict):
    """Evidencia **declarada** de la arista en el grafo; nunca se deriva de la importancia."""

    evidence_status: Text
    evidence_method: Text
    evidence_source: Text | None = None


class EdgeImportance(_Strict):
    source_type: Text
    relation_type: Text
    target_type: Text
    source_id: Text
    target_id: Text
    importance: float
    evidence: Evidence | None
    """`null` solo en una relación inversa (`rev_*`), que no existe en el grafo de registros."""


class Importance(_Strict):
    scale: Scale
    nodes: list[NodeImportance]
    attributes: list[AttributeImportance]
    edges: list[EdgeImportance]


# ---------------------------------------------------------------------------
# Subgrafo top-k
# ---------------------------------------------------------------------------


class NodeRef(_Strict):
    node_type: Text
    node_id: Text


class EdgeRef(_Strict):
    source_type: Text
    relation_type: Text
    target_type: Text
    source_id: Text
    target_id: Text


class Subgraph(_Strict):
    k: Annotated[int, Field(ge=1)]
    selection: Text
    """Regla de selección; en `1.0.0`, `top_k_edges_by_importance`."""
    tie_break: Text
    """Desempate determinista; en `1.0.0`, `lexicographic_edge_key`."""
    nodes: list[NodeRef]
    edges: list[EdgeRef]


class Warning_(_Strict):
    code: Text
    message: Text


class Explanation(_Strict):
    format: Literal["nutrigraphdt-explanation"]
    format_version: Literal["1.0.0"]
    created_at: Text
    run: RunRef
    explainer: ExplainerRef
    target: TargetRef
    importance: Importance
    subgraph: Subgraph
    warnings: list[Warning_]


# ---------------------------------------------------------------------------
# Reglas que cruzan campos
# ---------------------------------------------------------------------------


def _edge_key(edge: EdgeImportance | EdgeRef) -> tuple[str, str, str, str, str]:
    return (edge.source_type, edge.relation_type, edge.target_type, edge.source_id, edge.target_id)


def _relation_allowed(source: str, relation: str, target: str) -> bool:
    if (source, relation, target) in ALLOWED_RELATIONS:
        return True
    if relation.startswith(REVERSE_PREFIX):
        return (target, relation[len(REVERSE_PREFIX) :], source) in ALLOWED_RELATIONS
    return False


def _cross_field_problems(explanation: Explanation) -> list[str]:
    problems: list[str] = []
    importance = explanation.importance
    low, high = importance.scale.range

    # EXP-02: escala y valores.
    if not (math.isfinite(low) and math.isfinite(high) and low < high):
        problems.append(f"EXP-02: importance.scale.range {[low, high]} no es un intervalo finito.")
    if importance.scale.kind == "normalized" and (low, high) not in {(0.0, 1.0), (-1.0, 1.0)}:
        problems.append("EXP-02: una escala normalized declara range [0, 1] o [-1, 1].")
    values = (
        [(f"nodes[{i}]", item.importance) for i, item in enumerate(importance.nodes)]
        + [(f"attributes[{i}]", item.importance) for i, item in enumerate(importance.attributes)]
        + [(f"edges[{i}]", item.importance) for i, item in enumerate(importance.edges)]
    )
    for where, value in values:
        if not math.isfinite(value) or not (low <= value <= high):
            problems.append(f"EXP-02: importance.{where} = {value} fuera de {[low, high]}.")

    # EXP-03: tipos de nodo y relaciones del esquema.
    for where, node_type in [
        *((f"nodes[{i}]", n.node_type) for i, n in enumerate(importance.nodes)),
        *((f"attributes[{i}]", a.node_type) for i, a in enumerate(importance.attributes)),
    ]:
        if node_type not in NODE_TYPES:
            problems.append(f"EXP-03: importance.{where}.node_type {node_type!r} no existe.")
    for i, edge in enumerate(importance.edges):
        if not _relation_allowed(edge.source_type, edge.relation_type, edge.target_type):
            problems.append(
                f"EXP-03: importance.edges[{i}] ({edge.source_type}, {edge.relation_type}, "
                f"{edge.target_type}) no es una relación del esquema ni su inversa."
            )

    # EXP-04: sin duplicados.
    for name, keys in (
        ("nodes", [(n.node_type, n.node_id) for n in importance.nodes]),
        ("attributes", [(a.node_type, a.node_id, a.attribute) for a in importance.attributes]),
        ("edges", [_edge_key(e) for e in importance.edges]),
    ):
        repeated = sorted(k for k, n in Counter(keys).items() if n > 1)
        if repeated:
            problems.append(f"EXP-04: importance.{name} repite {repeated}.")

    # EXP-05: referencias a nodos con importancia.
    known_nodes = {(n.node_type, n.node_id) for n in importance.nodes}
    if known_nodes:
        for i, attribute in enumerate(importance.attributes):
            if (attribute.node_type, attribute.node_id) not in known_nodes:
                problems.append(f"EXP-05: importance.attributes[{i}] es de un nodo no listado.")
        for i, edge in enumerate(importance.edges):
            for side in ("source", "target"):
                ref = (getattr(edge, f"{side}_type"), getattr(edge, f"{side}_id"))
                if ref not in known_nodes:
                    problems.append(f"EXP-05: importance.edges[{i}].{side} no está en nodes.")

    # EXP-06: evidencia declarada y coherente; separada de la importancia.
    for i, edge in enumerate(importance.edges):
        reverse = edge.relation_type.startswith(REVERSE_PREFIX)
        if edge.evidence is None:
            if not reverse:
                problems.append(f"EXP-06: importance.edges[{i}] no declara su evidencia.")
            continue
        status, method = edge.evidence.evidence_status, edge.evidence.evidence_method
        if status not in ALLOWED_EVIDENCE_STATUSES:
            problems.append(f"EXP-06: importance.edges[{i}] evidence_status {status!r} no existe.")
        elif EVIDENCE_METHOD_STATUS.get(method) != status:
            problems.append(
                f"EXP-06: importance.edges[{i}] evidence_method {method!r} no respalda el estado "
                f"{status!r}."
            )
        if explanation.target.is_synthetic and status != "synthetic":
            problems.append(
                f"EXP-06: importance.edges[{i}] declara {status!r} en una instancia sintética."
            )

    # EXP-07: subgrafo top-k cerrado y contenido en la importancia.
    subgraph = explanation.subgraph
    edge_scores = {_edge_key(e): e.importance for e in importance.edges}
    sub_edges = [_edge_key(e) for e in subgraph.edges]
    sub_nodes = {(n.node_type, n.node_id) for n in subgraph.nodes}
    if len(sub_edges) > subgraph.k:
        problems.append(f"EXP-07: subgraph tiene {len(sub_edges)} aristas; k = {subgraph.k}.")
    if len(set(sub_edges)) != len(sub_edges) or len(sub_nodes) != len(subgraph.nodes):
        problems.append("EXP-07: subgraph repite nodos o aristas.")
    missing = [key for key in sub_edges if key not in edge_scores]
    if missing:
        problems.append(f"EXP-07: subgraph.edges sin importancia calculada: {missing}.")
    endpoints = {(k[0], k[3]) for k in sub_edges} | {(k[2], k[4]) for k in sub_edges}
    if endpoints != sub_nodes:
        problems.append(
            "EXP-07: subgraph.nodes debe ser exactamente el conjunto de extremos de sus aristas."
        )
    if subgraph.selection == "top_k_edges_by_importance" and not missing:
        ranked = sorted(edge_scores, key=lambda key: (-edge_scores[key], key))
        if sub_edges and set(sub_edges) != set(ranked[: len(sub_edges)]):
            problems.append(
                "EXP-07: subgraph.edges no son las de mayor importancia (desempate "
                "lexicográfico por clave de arista)."
            )
        if len(sub_edges) < min(subgraph.k, len(ranked)):
            problems.append("EXP-07: subgraph tiene menos de min(k, aristas) aristas.")

    # EXP-08: advertencias de interpretación.
    codes = {warning.code for warning in explanation.warnings}
    required = set(REQUIRED_WARNINGS)
    if explanation.target.is_synthetic:
        required.add(SYNTHETIC_WARNING)
    if explanation.explainer.uses_attention:
        required.add(ATTENTION_WARNING)
    if required - codes:
        problems.append(f"EXP-08: faltan advertencias {sorted(required - codes)}.")

    # EXP-09: la naturaleza de la instancia es coherente con su identificador (NOD-04).
    if explanation.target.is_synthetic != explanation.target.graph_id.startswith("synthetic:"):
        problems.append(
            "EXP-09: target.is_synthetic no coincide con el prefijo 'synthetic:' del graph_id."
        )
    return problems


def validate_explanation(data: Mapping[str, Any]) -> Explanation:
    """Valida una explicación (el objeto JSON ya leído) contra el contrato `1.0.0`.

    Raises:
        ExplanationContractError: con todas las infracciones (EXP-01 a EXP-09).
    """
    try:
        explanation = Explanation.model_validate(dict(data))
    except ValidationError as error:
        problems = [
            f"EXP-01: {'.'.join(str(p) for p in item['loc']) or '(raíz)'}: {item['msg']}"
            for item in error.errors()
        ]
        raise ExplanationContractError(problems) from error
    problems = _cross_field_problems(explanation)
    if problems:
        raise ExplanationContractError(problems)
    return explanation


__all__ = [
    "ATTENTION_WARNING",
    "EVIDENCE_METHOD_STATUS",
    "EXPLANATION_FORMAT",
    "EXPLANATION_FORMAT_VERSION",
    "REQUIRED_WARNINGS",
    "SYNTHETIC_WARNING",
    "Explanation",
    "ExplanationContractError",
    "validate_explanation",
]
