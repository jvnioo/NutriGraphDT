"""Agregación y serialización de importancias de atributos y aristas por tipo (A60-P2, #171).

Provee funciones puras y deterministas para calcular las importancias de nodos, atributos y
aristas a partir de las máscaras brutas que produce un explicador de PyG.  Las funciones son
independientes del wrapper `HeteroExplainer` para facilitar el test unitario con tensores
pequeños.

Convención de valores
---------------------
Todos los valores de importancia que devuelven estas funciones son:

* **Absolutos**: se toma `abs()` de la máscara, que puede ser firmada internamente según el
  algoritmo (p.ej. GNNExplainer con gradientes); la firma se descarta en el contrato.
* **Normalizados en [0, 1]** mediante división por `norm_factor` (máximo absoluto global de
  todas las máscaras del grafo) y `.clamp(0.0, 1.0)`.  El factor se calcula una vez por grafo
  para mantener una escala coherente entre tipos, pero **nunca** se comparten factores entre
  grafos distintos.
* **No comparables entre métodos**: `GNNExplainer`, `AttentionExplainer` y `CaptumExplainer`
  producen magnitudes con significados distintos; el campo `Scale.normalization` del contrato
  documenta el método de normalización.

Trazabilidad
------------
Cada función devuelve objetos del contrato `A55-P3` (`NodeImportance`, `AttributeImportance`,
`EdgeImportance`) que incluyen `node_type`/`relation_type`, identificador original del nodo o
arista, e importancia normalizada.  La trazabilidad a muestra (`sample_id`), corrida (`RunRef`)
y objetivo (`output_index`) la aporta el caller (`_build_contract_explanation` en `wrapper.py`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import torch
from torch import Tensor
from torch_geometric.data import HeteroData

from nutrigraphdt.explainability.contract import (
    AttributeImportance,
    EdgeImportance,
    Evidence,
    NodeImportance,
)
from nutrigraphdt.models.gnn.base import EdgeType

# ---------------------------------------------------------------------------
# Factor de normalización global
# ---------------------------------------------------------------------------


def compute_norm_factor(
    node_masks: Mapping[str, Tensor],
    edge_masks: Mapping[EdgeType, Tensor],
) -> float:
    """Calcula el factor de normalización `max_abs` global para un grafo.

    El factor se obtiene como el máximo de todos los valores absolutos de las máscaras de nodos
    y de aristas producidas para un mismo grafo.  Usar un factor global garantiza que las
    importancias de diferentes tipos de nodo y de relación son comparables dentro del mismo grafo.
    Devuelve ``1.0`` cuando no hay máscaras (sin máscara → importancia cero).

    Parámetros
    ----------
    node_masks:
        Mapa ``node_type → Tensor[num_nodes, num_features]`` (o ``[num_nodes]``).
    edge_masks:
        Mapa ``(src, rel, dst) → Tensor[num_edges]`` de máscara de aristas.

    Retorna
    -------
    float
        Factor de normalización; siempre ``> 0``.
    """
    raw: list[float] = []
    for nm in node_masks.values():
        raw.extend(nm.abs().reshape(-1).tolist())
    for em in edge_masks.values():
        raw.extend(em.abs().reshape(-1).tolist())
    if not raw:
        return 1.0
    max_val = max(raw)
    return max_val if max_val > 0.0 else 1.0


# ---------------------------------------------------------------------------
# Importancia de nodos
# ---------------------------------------------------------------------------


def compute_node_importance(
    data: HeteroData,
    node_masks: Mapping[str, Tensor],
    norm_factor: float,
    *,
    node_mask_type: str | None,
    is_synthetic: bool = False,
) -> list[NodeImportance]:
    """Calcula la importancia agregada de cada nodo por tipo.

    Método de agregación
    --------------------
    * ``node_mask_type == "attributes"`` (máscara por atributo, forma ``[N, F]``):
      ``importance_node_i = sum(abs(mask[i])) / (norm_factor * F)``
      Se normaliza por el número de columnas para que la escala no crezca con la anchura del
      tensor.  El resultado se fija en ``[0, 1]`` con ``.clamp``.

    * ``node_mask_type == "object"`` o ``None`` (máscara por nodo, forma ``[N]`` o ``[N, 1]``):
      ``importance_node_i = mean(abs(mask[i])) / norm_factor``.

    Los nodos sin máscara aparecen con ``importance=0.0`` (EXP-05 del contrato).

    Parámetros
    ----------
    data:
        Grafo fuente del que se extraen los ``node_id`` y los tamaños de tensor.
    node_masks:
        Mapa ``node_type → Tensor`` de máscaras producidas por el explicador.
    norm_factor:
        Factor de normalización global del grafo (devuelto por `compute_norm_factor`).
    node_mask_type:
        ``"attributes"`` si la máscara tiene dimensión de características; ``"object"`` u
        ``None`` si la máscara es escalar por nodo.
    is_synthetic:
        Si ``True``, los IDs generados automáticamente llevan el prefijo ``"synthetic:"``.

    Retorna
    -------
    list[NodeImportance]
        Un elemento por nodo, con ``node_type``, ``node_id`` e ``importance``.  El orden es
        determinista: primero los tipos en el orden de ``data.node_types``, luego los nodos en
        el orden de sus IDs originales.
    """
    nodes_dict: dict[tuple[str, str], float] = {}

    # Inicializar todos los nodos del grafo con importancia cero (EXP-05)
    for node_type in data.node_types:
        store = data[node_type]
        node_ids = _extract_node_ids(store, node_type, is_synthetic)
        for nid in node_ids:
            nodes_dict[(node_type, str(nid))] = 0.0

    for node_type, mask in node_masks.items():
        store = data[node_type]
        node_ids = _extract_node_ids(store, node_type, is_synthetic, fallback_size=mask.shape[0])

        for i, nid in enumerate(node_ids):
            row_mask = mask[i]
            if node_mask_type == "attributes" and mask.ndim > 1:
                row_abs = row_mask.abs()
                importance = float(
                    (row_abs.sum() / (norm_factor * mask.shape[1])).clamp(0.0, 1.0).item()
                )
            else:
                importance = float((row_mask.abs().mean() / norm_factor).clamp(0.0, 1.0).item())
            nodes_dict[(node_type, str(nid))] = round(importance, 6)

    return [
        NodeImportance(node_type=nt, node_id=nid, importance=imp)
        for (nt, nid), imp in nodes_dict.items()
    ]


# ---------------------------------------------------------------------------
# Importancia de atributos
# ---------------------------------------------------------------------------


def compute_attribute_importance(
    data: HeteroData,
    node_masks: Mapping[str, Tensor],
    norm_factor: float,
    feature_names_map: Mapping[str, Sequence[str]] | None = None,
    *,
    is_synthetic: bool = False,
) -> list[AttributeImportance]:
    """Calcula la importancia por atributo para cada nodo de cada tipo.

    Solo se produce salida cuando ``node_mask_type == "attributes"`` y la máscara tiene
    dimensión de características (``mask.ndim > 1``).

    Método de agregación
    --------------------
    ``importance_attr_col_j = abs(mask[i, j]) / norm_factor``

    El valor es el valor absoluto individual de la columna ``j`` para el nodo ``i``, dividido
    por el factor de normalización global del grafo.  Los valores son **absolutos** y
    **normalizados en [0, 1]**; no se comparar entre diferentes métodos de explicación.

    Parámetros
    ----------
    data:
        Grafo fuente del que se extraen ``node_id`` y el esquema de características.
    node_masks:
        Mapa ``node_type → Tensor[N, F]`` de máscaras producidas por el explicador.
    norm_factor:
        Factor de normalización global del grafo.
    feature_names_map:
        Mapa opcional ``node_type → [col_0, col_1, …]`` con nombres de columnas.  Si es
        ``None`` o el tipo no aparece, se generan nombres automáticos ``{node_type}_col_{j}``.
    is_synthetic:
        Si ``True``, los IDs generados llevan el prefijo ``"synthetic:"``.

    Retorna
    -------
    list[AttributeImportance]
        Un elemento por (nodo, atributo).  El orden es determinista: primero los tipos en
        el orden de ``node_masks``, dentro de cada tipo nodos en orden de ID y luego columnas
        en orden creciente de índice.
    """
    attributes: list[AttributeImportance] = []

    for node_type, mask in node_masks.items():
        if mask.ndim <= 1:
            # Máscara de objeto escalar por nodo: no hay importancias de atributo
            continue

        store = data[node_type]
        node_ids = _extract_node_ids(store, node_type, is_synthetic, fallback_size=mask.shape[0])
        names = _resolve_feature_names(
            data, node_type, mask.shape[1], feature_names_map=feature_names_map
        )

        for i, nid in enumerate(node_ids):
            row_abs = mask[i].abs()
            for col_idx, col_name in enumerate(names):
                attr_imp = float((row_abs[col_idx] / norm_factor).clamp(0.0, 1.0).item())
                attributes.append(
                    AttributeImportance(
                        node_type=node_type,
                        node_id=str(nid),
                        attribute=col_name,
                        importance=round(attr_imp, 6),
                    )
                )

    return attributes


# ---------------------------------------------------------------------------
# Importancia de aristas
# ---------------------------------------------------------------------------


def compute_edge_importance(
    data: HeteroData,
    node_importance_list: Sequence[NodeImportance],
    edge_masks: Mapping[EdgeType, Tensor],
    norm_factor: float,
    *,
    is_synthetic: bool = False,
) -> list[EdgeImportance]:
    """Calcula la importancia individual de cada arista, por tipo de relación.

    Las aristas se procesan tipo a tipo y conservan su ``relation_type``. Todas se dividen por el
    mismo ``norm_factor`` del grafo, que también normaliza nodos y atributos: los valores son
    comparables dentro de una explicación, pero no entre grafos ni entre métodos.

    Método de agregación
    --------------------
    ``importance_edge_e = abs(edge_mask[e]) / norm_factor``

    El valor es el valor absoluto de la máscara de arista, dividido por el factor global.
    Los valores son **absolutos** y **normalizados en [0, 1]**; la firma de la máscara se
    descarta.  Los tipos de relación sin máscara aparecen con ``importance=0.0``.

    Trazabilidad de evidencia
    -------------------------
    La evidencia de cada arista se copia del grafo (``evidence_status``, ``evidence_method`` y,
    si existe, ``evidence_source``); no se altera con la explicación ni se completa con valores
    por omisión. Las relaciones inversas (prefijo ``"rev_"``) no llevan evidencia propia: la
    conversión a ``HeteroData`` las agrega para el paso de mensajes.

    Parámetros
    ----------
    data:
        Grafo fuente con ``edge_index`` y metadatos de evidencia (``evidence_status``,
        ``evidence_method``, ``evidence_source``).
    node_importance_list:
        Lista de `NodeImportance` del mismo grafo (para resolver IDs de nodos origen/destino).
    edge_masks:
        Mapa ``(src, rel, dst) → Tensor[num_edges]`` de máscaras de aristas.
    norm_factor:
        Factor de normalización global del grafo.
    is_synthetic:
        Se conserva por compatibilidad de la firma; la evidencia nunca se infiere de este valor.

    Retorna
    -------
    list[EdgeImportance]
        Un elemento por arista de cada tipo de relación en ``data.edge_types``.  El orden es
        determinista: tipos en el orden de ``data.edge_types``, aristas en el orden de
        ``edge_index``.

    Raises
    ------
    ValueError
        Si un índice de ``edge_index`` no corresponde a ningún nodo, o si una arista no inversa
        no declara su evidencia en el grafo.
    """
    # Índice rápido node_type → [node_id] en orden del tensor
    node_id_index: dict[str, list[str]] = {}
    for ni in node_importance_list:
        node_id_index.setdefault(ni.node_type, []).append(ni.node_id)

    result: list[EdgeImportance] = []

    for edge_type in data.edge_types:
        source_type, relation_type, target_type = edge_type
        store = data[edge_type]
        if "edge_index" not in store:
            continue
        edge_index: Tensor = store.edge_index
        num_edges = edge_index.shape[1]
        mask_for_type = edge_masks.get(edge_type)
        is_reverse = relation_type.startswith("rev_")

        src_nodes = node_id_index.get(source_type, [])
        tgt_nodes = node_id_index.get(target_type, [])

        for e in range(num_edges):
            src_idx = int(edge_index[0, e].item())
            tgt_idx = int(edge_index[1, e].item())
            if not (0 <= src_idx < len(src_nodes) and 0 <= tgt_idx < len(tgt_nodes)):
                raise ValueError(
                    f"La arista {e} de {edge_type} apunta a nodos inexistentes "
                    f"({src_idx} -> {tgt_idx})."
                )
            source_id = src_nodes[src_idx]
            target_id = tgt_nodes[tgt_idx]

            if mask_for_type is not None:
                raw_imp = float(mask_for_type[e].abs().item())
                edge_imp = round(
                    float(torch.tensor(raw_imp / norm_factor).clamp(0.0, 1.0).item()), 6
                )
            else:
                edge_imp = 0.0

            evidence: Evidence | None
            if is_reverse:
                evidence = None
            else:
                if not all(
                    name in store and e < len(store[name])
                    for name in ("evidence_status", "evidence_method")
                ):
                    raise ValueError(
                        f"La arista {e} de {edge_type} no declara evidence_status y "
                        "evidence_method en el grafo; la evidencia no se infiere."
                    )
                ev_status = store.evidence_status[e]
                ev_method = store.evidence_method[e]
                ev_source = (
                    store.evidence_source[e]
                    if "evidence_source" in store and e < len(store.evidence_source)
                    else None
                )
                evidence = Evidence(
                    evidence_status=str(ev_status),
                    evidence_method=str(ev_method),
                    evidence_source=str(ev_source) if ev_source else None,
                )

            result.append(
                EdgeImportance(
                    source_type=source_type,
                    relation_type=relation_type,
                    target_type=target_type,
                    source_id=source_id,
                    target_id=target_id,
                    importance=edge_imp,
                    evidence=evidence,
                )
            )

    return result


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------


def _extract_node_ids(
    store: object,
    node_type: str,
    is_synthetic: bool,
    fallback_size: int | None = None,
) -> list[str]:
    """Extrae los ``node_id`` del store o genera IDs sintéticos si no existen."""
    node_ids = list(getattr(store, "node_id", []))
    if node_ids:
        return [str(nid) for nid in node_ids]
    # Fallback: usar índice de tensor o tamaño declarado
    size = fallback_size
    if size is None:
        x = getattr(store, "x", None)
        size = x.shape[0] if x is not None else 0
    prefix = "synthetic:" if is_synthetic else ""
    return [f"{prefix}{node_type}:{i:04d}" for i in range(size)]


def _resolve_feature_names(
    data: HeteroData,
    node_type: str,
    count: int,
    feature_names_map: Mapping[str, Sequence[str]] | None,
) -> list[str]:
    """Resuelve los nombres de columnas para un tipo de nodo dado."""
    if feature_names_map is not None and node_type in feature_names_map:
        names = list(feature_names_map[node_type])
        if len(names) >= count:
            return names[:count]

    schema = getattr(data, "node_feature_schema", None)
    if isinstance(schema, Mapping) and node_type in schema:
        cols = schema[node_type]
        names = [col.get("name", str(col)) if isinstance(col, dict) else str(col) for col in cols]
        if len(names) >= count:
            return names[:count]

    return [f"{node_type}_col_{i}" for i in range(count)]


__all__ = [
    "compute_attribute_importance",
    "compute_edge_importance",
    "compute_node_importance",
    "compute_norm_factor",
]
