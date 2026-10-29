"""Extracción y serialización del subgrafo explicativo top-k (A60-P3, #169).

Provee funciones deterministas para:
1. Extraer el subgrafo top-k a partir de la lista de aristas calculadas (`EdgeImportance`),
   con desempate lexicográfico estricto y conservación de extremos (`EXP-07`).
2. Generar una vista autocontenida del subgrafo, enriquecida con importancias, atributos y
   evidencia, para reportes y visualización web.
3. Serializar y deserializar artefactos JSON con validación de ida y vuelta conforme al
   contrato A55-P3 (`nutrigraphdt-explanation 1.0.0`).

Reglas de desempate y relaciones inversas
-----------------------------------------
- **Empates**: ante idéntica importancia, gana la clave quíntupla
  `(source_type, relation_type, target_type, source_id, target_id)` menor
  (`lexicographic_edge_key`).
- **Relaciones inversas (`rev_*`)**: son aristas técnicas del paso de mensajes de `HeteroData`,
  sin evidencia en los registros (`evidence is None`). En `1.0.0` compiten por importancia como
  cualquier otra arista (`top_k_edges_by_importance`) y se conservan en el subgrafo y en la vista;
  quien las consuma las reconoce por el prefijo `rev_` y por su evidencia nula. Excluirlas de la
  selección cambiaría la regla del subgrafo, lo que según el contrato sube la versión mayor.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from nutrigraphdt.explainability.contract import (
    AttributeImportance,
    EdgeImportance,
    EdgeRef,
    Evidence,
    ExplainerRef,
    Explanation,
    NodeRef,
    RunRef,
    Scale,
    Subgraph,
    TargetRef,
    Warning_,
    validate_explanation,
)

DEFAULT_SELECTION: Final[str] = "top_k_edges_by_importance"
DEFAULT_TIE_BREAK: Final[str] = "lexicographic_edge_key"

EdgeKey = tuple[str, str, str, str, str]
NodeKey = tuple[str, str]


def _edge_key(edge: EdgeImportance | EdgeRef | SubgraphEdgeView) -> EdgeKey:
    return (edge.source_type, edge.relation_type, edge.target_type, edge.source_id, edge.target_id)


def _endpoints(keys: Collection[EdgeKey]) -> set[NodeKey]:
    return {(key[0], key[3]) for key in keys} | {(key[2], key[4]) for key in keys}


# ---------------------------------------------------------------------------
# 1. Extracción del subgrafo top-k (contrato Subgraph)
# ---------------------------------------------------------------------------


def extract_top_k_subgraph(edges: Sequence[EdgeImportance], k: int) -> Subgraph:
    """Extrae el subgrafo top-k de acuerdo con la regla EXP-07 del contrato A55-P3.

    Selecciona las `min(k, len(edges))` aristas de mayor importancia, desempata por la clave
    lexicográfica de arista y devuelve como nodos exactamente sus extremos. Las relaciones
    inversas (`rev_*`) participan en el ranking como cualquier otra arista.

    Raises:
        TypeError: si `k` no es un entero (`bool` no cuenta como entero).
        ValueError: si `k < 1` o si `edges` repite una arista.
    """
    if not isinstance(k, int) or isinstance(k, bool):
        raise TypeError(f"k debe ser un entero; recibido {type(k).__name__}.")
    if k < 1:
        raise ValueError(f"k debe ser un entero mayor o igual a 1; recibido k={k}.")

    scores = {_edge_key(e): e.importance for e in edges}
    if len(scores) != len(edges):
        raise ValueError("edges repite aristas; cada clave de arista debe aparecer una vez.")

    ranked = sorted(scores, key=lambda key: (-scores[key], key))
    selected = ranked[:k]

    return Subgraph(
        k=k,
        selection=DEFAULT_SELECTION,
        tie_break=DEFAULT_TIE_BREAK,
        nodes=[NodeRef(node_type=t, node_id=i) for t, i in sorted(_endpoints(selected))],
        edges=[
            EdgeRef(
                source_type=key[0],
                relation_type=key[1],
                target_type=key[2],
                source_id=key[3],
                target_id=key[4],
            )
            for key in selected
        ],
    )


# ---------------------------------------------------------------------------
# 2. Vista autocontenida para reportes y visualización web
# ---------------------------------------------------------------------------


class SubgraphNodeView(BaseModel):
    """Nodo del subgrafo top-k con su importancia y la de sus atributos."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: str
    node_id: str
    importance: float
    attributes: list[AttributeImportance] = Field(default_factory=list)


class SubgraphEdgeView(BaseModel):
    """Arista del subgrafo top-k con su importancia y evidencia declarada."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_type: str
    relation_type: str
    target_type: str
    source_id: str
    target_id: str
    importance: float
    evidence: Evidence | None
    """`null` solo en una relación inversa (`rev_*`), como en el contrato."""


class ExplanatorySubgraphView(BaseModel):
    """Vista autocontenida del subgrafo explicativo para interfaces web y reportes.

    Agrupa los nodos y aristas del top-k con sus importancias, atributos y evidencia, más la
    trazabilidad necesaria para interpretarlos: corrida, explicador, instancia, escala de la
    importancia y advertencias. No incluye datos crudos ni tensores.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    k: int = Field(ge=1)
    selection: str
    tie_break: str
    run: RunRef
    explainer: ExplainerRef
    target: TargetRef
    scale: Scale
    nodes: list[SubgraphNodeView]
    edges: list[SubgraphEdgeView]
    warnings: list[Warning_]

    @model_validator(mode="after")
    def _closed_subgraph(self) -> Self:
        edge_keys = [_edge_key(e) for e in self.edges]
        node_keys = [(n.node_type, n.node_id) for n in self.nodes]
        if len(edge_keys) > self.k:
            raise ValueError(f"la vista tiene {len(edge_keys)} aristas; k = {self.k}.")
        if len(set(edge_keys)) != len(edge_keys) or len(set(node_keys)) != len(node_keys):
            raise ValueError("la vista repite nodos o aristas.")
        if _endpoints(edge_keys) != set(node_keys):
            raise ValueError("los nodos de la vista deben ser los extremos de sus aristas.")
        return self


def extract_subgraph_view(explanation: Explanation) -> ExplanatorySubgraphView:
    """Construye la vista del subgrafo de una `Explanation` validada.

    Raises:
        ValueError: si un nodo o arista del subgrafo no tiene importancia calculada (la
            explicación no cumple EXP-05/EXP-07); nunca se rellena con un valor inventado.
    """
    importance = explanation.importance
    node_scores = {(n.node_type, n.node_id): n.importance for n in importance.nodes}
    edges_by_key = {_edge_key(e): e for e in importance.edges}

    attrs_by_node: dict[NodeKey, list[AttributeImportance]] = {}
    for attr in importance.attributes:
        attrs_by_node.setdefault((attr.node_type, attr.node_id), []).append(attr)

    node_views = []
    for node in explanation.subgraph.nodes:
        node_key = (node.node_type, node.node_id)
        if node_key not in node_scores:
            raise ValueError(f"el nodo {node_key} del subgrafo no tiene importancia calculada.")
        node_views.append(
            SubgraphNodeView(
                node_type=node.node_type,
                node_id=node.node_id,
                importance=node_scores[node_key],
                attributes=attrs_by_node.get(node_key, []),
            )
        )

    edge_views = []
    for ref in explanation.subgraph.edges:
        edge_key = _edge_key(ref)
        if edge_key not in edges_by_key:
            raise ValueError(f"la arista {edge_key} del subgrafo no tiene importancia calculada.")
        edge = edges_by_key[edge_key]
        edge_views.append(
            SubgraphEdgeView(
                source_type=edge.source_type,
                relation_type=edge.relation_type,
                target_type=edge.target_type,
                source_id=edge.source_id,
                target_id=edge.target_id,
                importance=edge.importance,
                evidence=edge.evidence,
            )
        )

    return ExplanatorySubgraphView(
        k=explanation.subgraph.k,
        selection=explanation.subgraph.selection,
        tie_break=explanation.subgraph.tie_break,
        run=explanation.run,
        explainer=explanation.explainer,
        target=explanation.target,
        scale=importance.scale,
        nodes=node_views,
        edges=edge_views,
        warnings=explanation.warnings,
    )


# ---------------------------------------------------------------------------
# 3. Serialización y deserialización JSON
# ---------------------------------------------------------------------------


def _dump(model: BaseModel, path: Path | str | None, indent: int) -> str:
    text = json.dumps(model.model_dump(mode="json"), indent=indent, ensure_ascii=False) + "\n"
    if path is not None:
        target_path = Path(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(text, encoding="utf-8")
    return text


def _read(source: str | Path | Mapping[str, Any]) -> Mapping[str, Any]:
    """Un `Mapping` se usa tal cual; un `Path`, o un `str` que no empieza por `{`, es una ruta."""
    if isinstance(source, Mapping):
        return source
    if isinstance(source, Path) or not source.lstrip().startswith("{"):
        source = Path(source).read_text(encoding="utf-8")
    data = json.loads(source)
    if not isinstance(data, Mapping):
        raise ValueError("el JSON debe ser un objeto.")
    return data


def serialize_explanation(
    explanation: Explanation, path: Path | str | None = None, *, indent: int = 2
) -> str:
    """Serializa una `Explanation` a JSON determinista; si se da `path`, lo escribe en disco."""
    return _dump(explanation, path, indent)


def load_explanation(source: str | Path | Mapping[str, Any]) -> Explanation:
    """Lee una explicación (JSON, ruta o diccionario) y la valida contra el contrato `1.0.0`."""
    return validate_explanation(_read(source))


def serialize_subgraph_view(
    view: ExplanatorySubgraphView, path: Path | str | None = None, *, indent: int = 2
) -> str:
    """Serializa una `ExplanatorySubgraphView` a JSON; si se da `path`, lo escribe en disco."""
    return _dump(view, path, indent)


def load_subgraph_view(source: str | Path | Mapping[str, Any]) -> ExplanatorySubgraphView:
    """Lee y valida una `ExplanatorySubgraphView` desde JSON, ruta o diccionario."""
    return ExplanatorySubgraphView.model_validate(dict(_read(source)))


__all__ = [
    "DEFAULT_SELECTION",
    "DEFAULT_TIE_BREAK",
    "ExplanatorySubgraphView",
    "SubgraphEdgeView",
    "SubgraphNodeView",
    "extract_subgraph_view",
    "extract_top_k_subgraph",
    "load_explanation",
    "load_subgraph_view",
    "serialize_explanation",
    "serialize_subgraph_view",
]
