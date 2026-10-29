"""Extracción y serialización del subgrafo explicativo top-k (A60-P3, #169).

Provee funciones deterministas para:
1. Extraer el subgrafo top-k a partir de la lista de aristas calculadas (`EdgeImportance`),
   con desempate lexicográfico estricto y conservación de extremos (`EXP-07`).
2. Filtrar o incluir relaciones inversas (`rev_*`) según la política de consumo.
3. Generar vistas estructuradas del subgrafo enriquecidas con atributos e importancias para
   reportes y visualización web.
4. Serializar y deserializar artefactos JSON con validación de esquema de ida y vuelta
   conforme al contrato A55-P3 (`nutrigraphdt-explanation 1.0.0`).

Reglas de desempate y relaciones inversas
-----------------------------------------
- **Empates**: ante idéntica importancia, las aristas se ordenan lexicográficamente por su clave
  quíntupla `(source_type, relation_type, target_type, source_id, target_id)`.
- **Relaciones inversas (`rev_*`)**: son artefactos técnicos del paso de mensajes de `HeteroData`
  y no poseen evidencia biológica (`evidence is None`). En la selección por omisión
  (`top_k_edges_by_importance`), compiten por magnitud; si se indica `filter_reverse=True`,
  se descartan previo al ranking bajo la regla `top_k_forward_edges_by_importance`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

from nutrigraphdt.explainability.contract import (
    REVERSE_PREFIX,
    AttributeImportance,
    EdgeImportance,
    EdgeRef,
    Evidence,
    Explanation,
    NodeRef,
    Subgraph,
    TargetRef,
    Warning_,
    validate_explanation,
)

DEFAULT_SELECTION: Final[str] = "top_k_edges_by_importance"
FORWARD_ONLY_SELECTION: Final[str] = "top_k_forward_edges_by_importance"
DEFAULT_TIE_BREAK: Final[str] = "lexicographic_edge_key"


def _edge_sort_key(edge: EdgeImportance) -> tuple[float, tuple[str, str, str, str, str]]:
    """Clave de ordenación para ranking determinista: (-importancia, clave_lexicográfica)."""
    return (
        -edge.importance,
        (
            edge.source_type,
            edge.relation_type,
            edge.target_type,
            edge.source_id,
            edge.target_id,
        ),
    )


# ---------------------------------------------------------------------------
# 1. Extracción del subgrafo top-k (contrato Subgraph)
# ---------------------------------------------------------------------------


def extract_top_k_subgraph(
    edges: Sequence[EdgeImportance],
    k: int,
    *,
    selection: str = DEFAULT_SELECTION,
    tie_break: str = DEFAULT_TIE_BREAK,
    filter_reverse: bool = False,
) -> Subgraph:
    """Extrae el subgrafo top-k de acuerdo con las reglas de EXP-07 del contrato A55-P3.

    Parámetros
    ----------
    edges:
        Lista de aristas con importancia calculada (`EdgeImportance`).
    k:
        Entero mayor o igual a 1.
    selection:
        Nombre de la regla de selección. Por omisión `top_k_edges_by_importance`.
        Si `filter_reverse=True`, se ajusta a `top_k_forward_edges_by_importance` si no se
        especificó una personalizada.
    tie_break:
        Nombre de la regla de desempate. Por omisión `lexicographic_edge_key`.
    filter_reverse:
        Si `True`, se descartan las aristas con prefijo `rev_` antes del ordenamiento.

    Retorna
    -------
    Subgraph
        Subgrafo validado con aristas seleccionadas y exactamente sus nodos extremos.

    Lanza
    -----
    ValueError:
        Si `k < 1` o si la regla de desempate no es válida.
    """
    if not isinstance(k, int) or isinstance(k, bool):
        raise TypeError(f"k debe ser un entero; recibido {type(k).__name__}.")
    if k < 1:
        raise ValueError(f"k debe ser un entero mayor o igual a 1; recibido k={k}.")

    effective_edges = list(edges)
    effective_selection = selection

    if filter_reverse:
        effective_edges = [
            e for e in effective_edges if not e.relation_type.startswith(REVERSE_PREFIX)
        ]
        if selection == DEFAULT_SELECTION:
            effective_selection = FORWARD_ONLY_SELECTION

    # Ordenamiento determinista: importancia descendente, desempate lexicográfico
    ranked_edges = sorted(effective_edges, key=_edge_sort_key)
    selected_edges = ranked_edges[: min(k, len(ranked_edges))]

    sub_edges = [
        EdgeRef(
            source_type=e.source_type,
            relation_type=e.relation_type,
            target_type=e.target_type,
            source_id=e.source_id,
            target_id=e.target_id,
        )
        for e in selected_edges
    ]

    # Conservación exacta de extremos (EXP-07)
    endpoints = sorted(
        {(e.source_type, e.source_id) for e in selected_edges}
        | {(e.target_type, e.target_id) for e in selected_edges}
    )
    sub_nodes = [NodeRef(node_type=t, node_id=i) for t, i in endpoints]

    return Subgraph(
        k=k,
        selection=effective_selection,
        tie_break=tie_break,
        nodes=sub_nodes,
        edges=sub_edges,
    )


# ---------------------------------------------------------------------------
# 2. Vistas enriquecidas para reportes y visualización web
# ---------------------------------------------------------------------------


class SubgraphNodeView(BaseModel):
    """Nodo perteneciente al subgrafo top-k con su importancia y atributos asociados."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: str
    node_id: str
    importance: float
    attributes: list[AttributeImportance] = Field(default_factory=list)


class SubgraphEdgeView(BaseModel):
    """Arista perteneciente al subgrafo top-k con su importancia y evidencia."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_type: str
    relation_type: str
    target_type: str
    source_id: str
    target_id: str
    importance: float
    evidence: Evidence | None = None


class ExplanatorySubgraphView(BaseModel):
    """Vista autocontenida del subgrafo explicativo para interfaces web y reportes.

    Agrupa únicamente los nodos y aristas seleccionados en el top-k, enriquecidos con sus
    importancias calculadas, atributos explicativos y evidencia del grafo de conocimiento.
    No incluye datos crudos de entrenamiento ni tensores internos.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    k: int
    selection: str
    tie_break: str
    target: TargetRef
    nodes: list[SubgraphNodeView]
    edges: list[SubgraphEdgeView]
    warnings: list[Warning_] = Field(default_factory=list)


def extract_subgraph_view(explanation: Explanation) -> ExplanatorySubgraphView:
    """Construye una vista autocontenida del subgrafo a partir de una `Explanation` validada."""
    subgraph = explanation.subgraph
    sub_node_keys = {(n.node_type, n.node_id) for n in subgraph.nodes}

    # Mapeo de importancia de nodos
    node_imp_map = {(n.node_type, n.node_id): n.importance for n in explanation.importance.nodes}

    # Atributos asociados a cada nodo del subgrafo
    attrs_by_node: dict[tuple[str, str], list[AttributeImportance]] = {}
    for attr in explanation.importance.attributes:
        key = (attr.node_type, attr.node_id)
        if key in sub_node_keys:
            attrs_by_node.setdefault(key, []).append(attr)

    node_views = [
        SubgraphNodeView(
            node_type=n.node_type,
            node_id=n.node_id,
            importance=node_imp_map.get((n.node_type, n.node_id), 0.0),
            attributes=attrs_by_node.get((n.node_type, n.node_id), []),
        )
        for n in subgraph.nodes
    ]

    # Mapeo de aristas
    edge_map = {
        (e.source_type, e.relation_type, e.target_type, e.source_id, e.target_id): e
        for e in explanation.importance.edges
    }

    edge_views: list[SubgraphEdgeView] = []
    for ref in subgraph.edges:
        key = (ref.source_type, ref.relation_type, ref.target_type, ref.source_id, ref.target_id)
        full_edge = edge_map.get(key)
        if full_edge is not None:
            edge_views.append(
                SubgraphEdgeView(
                    source_type=ref.source_type,
                    relation_type=ref.relation_type,
                    target_type=ref.target_type,
                    source_id=ref.source_id,
                    target_id=ref.target_id,
                    importance=full_edge.importance,
                    evidence=full_edge.evidence,
                )
            )

    return ExplanatorySubgraphView(
        k=subgraph.k,
        selection=subgraph.selection,
        tie_break=subgraph.tie_break,
        target=explanation.target,
        nodes=node_views,
        edges=edge_views,
        warnings=explanation.warnings,
    )


# ---------------------------------------------------------------------------
# 3. Serialización y deserialización JSON
# ---------------------------------------------------------------------------


def serialize_explanation(
    explanation: Explanation,
    path: Path | str | None = None,
    *,
    indent: int = 2,
) -> str:
    """Serializa una `Explanation` a formato JSON determinista.

    Si `path` se suministra, guarda el archivo en disco.
    """
    payload = explanation.model_dump(mode="json")
    text = json.dumps(payload, indent=indent, ensure_ascii=False) + "\n"
    if path is not None:
        target_path = Path(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(text, encoding="utf-8")
    return text


def load_explanation(source: str | Path | Mapping[str, Any]) -> Explanation:
    """Lee y valida una explicación desde una cadena JSON, ruta o diccionario."""
    if isinstance(source, Mapping):
        return validate_explanation(source)
    if isinstance(source, Path) or (isinstance(source, str) and not source.strip().startswith("{")):
        path = Path(source)
        data = json.loads(path.read_text(encoding="utf-8"))
        return validate_explanation(data)
    if isinstance(source, str):
        data = json.loads(source)
        return validate_explanation(data)
    raise TypeError(f"Fuente no soportada para load_explanation: {type(source)!r}")


def serialize_subgraph_view(
    view: ExplanatorySubgraphView,
    path: Path | str | None = None,
    *,
    indent: int = 2,
) -> str:
    """Serializa una `ExplanatorySubgraphView` a JSON."""
    payload = view.model_dump(mode="json")
    text = json.dumps(payload, indent=indent, ensure_ascii=False) + "\n"
    if path is not None:
        target_path = Path(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(text, encoding="utf-8")
    return text


def load_subgraph_view(source: str | Path | Mapping[str, Any]) -> ExplanatorySubgraphView:
    """Lee y valida una `ExplanatorySubgraphView` desde JSON, archivo o diccionario."""
    if isinstance(source, Mapping):
        return ExplanatorySubgraphView.model_validate(dict(source))
    if isinstance(source, Path) or (isinstance(source, str) and not source.strip().startswith("{")):
        path = Path(source)
        data = json.loads(path.read_text(encoding="utf-8"))
        return ExplanatorySubgraphView.model_validate(data)
    if isinstance(source, str):
        data = json.loads(source)
        return ExplanatorySubgraphView.model_validate(data)
    raise TypeError(f"Fuente no soportada para load_subgraph_view: {type(source)!r}")


__all__ = [
    "DEFAULT_SELECTION",
    "DEFAULT_TIE_BREAK",
    "ExplanatorySubgraphView",
    "FORWARD_ONLY_SELECTION",
    "SubgraphEdgeView",
    "SubgraphNodeView",
    "extract_subgraph_view",
    "extract_top_k_subgraph",
    "load_explanation",
    "load_subgraph_view",
    "serialize_explanation",
    "serialize_subgraph_view",
]
