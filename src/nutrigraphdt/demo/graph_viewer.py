"""Visualizador del grafo heterogéneo del escenario activo (A97, #320), sin Streamlit.

`scenario_graph` arma, en memoria, la instancia derivada del escenario con el motor de la corrida
(`ScenarioBase.derive`, sin escribir en disco). `viewer_view` la filtra por tipo de nodo y por
relación, muestrea los taxones de forma determinista y devuelve la `GraphView` que dibuja
`nutrigraphdt.demo.plots.graph_figure`, con el color por tipo de nodo de `ui.NODE_COLORS` y el
trazo por evidencia de `nutrigraphdt.explainability.style`: no hay una segunda definición de
estilos.

**Evidencia y estado estructural.** En el grafo sintético todas las aristas tienen
`evidence_status: synthetic`. El estado estructural de cada relación (aprobada, provisional o
hipotética) está en el esquema (`ALLOWED_RELATIONS`). Una relación hipotética, como
`additive → modulates → taxon`, se dibuja con el estilo `hypothetical` y la leyenda «hipotética»
(C-03, #243), aunque su arista sea sintética: así no parece respaldada.

**Muestreo de taxones.** Con muchos taxones la figura se vuelve ilegible y lenta. Se muestran los
`max_taxa` con más aristas en la vista filtrada y, entre ellos, los más abundantes; el empate se
rompe por `node_id`. La misma entrada da siempre la misma figura.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any, Final

from nutrigraphdt.demo.data import NODE_TYPE_ORDER, GraphView, graph_view
from nutrigraphdt.explainability.style import HYPOTHETICAL_LABEL, evidence_style
from nutrigraphdt.graph.schema import ALLOWED_RELATIONS

DEFAULT_MAX_TAXA: Final[int] = 12
HYPOTHETICAL: Final[str] = "hypothetical"
STRUCTURAL_LABELS: Final[dict[str, str]] = {
    "approved_structure": "aprobada",
    "provisional": "provisional",
    "hypothetical": "hipotética",
}
SYNTHETIC_LEGEND_NOTE: Final[str] = (
    "Datos sintéticos: todas las aristas son del dataset generado (evidencia «sintética»). El "
    "estado estructural dice cómo está la relación en el esquema; una relación hipotética no "
    "tiene respaldo empírico y se dibuja con su propio trazo."
)


@dataclass(frozen=True)
class Records:
    """Nodos y aristas de una instancia, como los que lee `graph_view`."""

    graph_id: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


@dataclass(frozen=True)
class ViewerView:
    """Vista filtrada y muestreada, con lo que la página debe informar."""

    view: GraphView
    shown_taxa: int
    total_taxa: int
    legend: list[dict[str, Any]]


def scenario_graph(engine: Any, request: Any) -> Records:
    """Instancia derivada del escenario, en memoria (no escribe en disco)."""
    instance, nodes, edges = engine.base.derive(request)
    return Records(graph_id=str(instance["graph_id"]), nodes=nodes, edges=edges)


def structural_status(edge: Mapping[str, Any]) -> str:
    """Estado estructural de la relación de la arista en el esquema."""
    key = (str(edge["source_type"]), str(edge["relation_type"]), str(edge["target_type"]))
    spec = ALLOWED_RELATIONS.get(key)
    return spec.structural_status if spec is not None else HYPOTHETICAL


def style_status(edge: Mapping[str, Any]) -> str:
    """Trazo de la arista: `hypothetical` si su relación lo es; si no, su evidencia."""
    if structural_status(edge) == HYPOTHETICAL:
        return HYPOTHETICAL
    return str(edge["evidence_status"])


def node_types(records: Records) -> list[str]:
    present = {str(n["node_type"]) for n in records.nodes}
    return [t for t in NODE_TYPE_ORDER if t in present]


def relations(records: Records) -> list[str]:
    return sorted({str(e["relation_type"]) for e in records.edges})


def _abundance(node: Mapping[str, Any]) -> float:
    value = (node.get("attributes") or {}).get("abundance")
    return float(value) if isinstance(value, int | float) and math.isfinite(value) else 0.0


def sample_taxa(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]], max_taxa: int
) -> list[dict[str, Any]]:
    """Los `max_taxa` taxones con más aristas y, entre ellos, más abundantes (orden por id)."""
    degree: Counter[str] = Counter()
    for edge in edges:
        for side in ("source", "target"):
            if edge[f"{side}_type"] == "taxon":
                degree[str(edge[f"{side}_id"])] += 1
    taxa = [n for n in nodes if n["node_type"] == "taxon"]
    ranked = sorted(taxa, key=lambda n: (-degree[str(n["node_id"])], -_abundance(n), n["node_id"]))
    return ranked[: max(max_taxa, 0)]


def viewer_view(
    records: Records,
    *,
    types: Collection[str] | None = None,
    relation_types: Collection[str] | None = None,
    max_taxa: int = DEFAULT_MAX_TAXA,
) -> ViewerView:
    """Vista filtrada por tipo de nodo y relación, con los taxones muestreados.

    Raises:
        KeyError: si el filtro deja la instancia sin nodos.
    """
    wanted_types = set(types) if types is not None else set(node_types(records))
    wanted_relations = (
        set(relation_types) if relation_types is not None else set(relations(records))
    )
    nodes = [n for n in records.nodes if n["node_type"] in wanted_types]
    edges = [
        e
        for e in records.edges
        if e["relation_type"] in wanted_relations
        and e["source_type"] in wanted_types
        and e["target_type"] in wanted_types
    ]
    taxa = [n for n in nodes if n["node_type"] == "taxon"]
    kept = {str(n["node_id"]) for n in sample_taxa(nodes, edges, max_taxa)}
    nodes = [n for n in nodes if n["node_type"] != "taxon" or str(n["node_id"]) in kept]
    keys = {(n["node_type"], str(n["node_id"])) for n in nodes}
    edges = [
        e
        for e in edges
        if (e["source_type"], str(e["source_id"])) in keys
        and (e["target_type"], str(e["target_id"])) in keys
    ]
    view = graph_view(
        Records(records.graph_id, nodes, edges), records.graph_id, max_per_type=len(nodes) + 1
    )
    by_key = {
        (
            e["source_type"],
            str(e["source_id"]),
            e["relation_type"],
            e["target_type"],
            str(e["target_id"]),
        ): e
        for e in edges
    }
    for edge in view.edges:
        original = by_key[
            (
                edge["source_type"],
                edge["source_id"],
                edge["relation"],
                edge["target_type"],
                edge["target_id"],
            )
        ]
        edge["style_status"] = style_status(original)
    return ViewerView(
        view=view,
        shown_taxa=len(kept),
        total_taxa=len(taxa),
        legend=legend(edges),
    )


def legend(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Una fila por relación: aristas, evidencia, estado estructural y cómo se dibuja."""
    rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    for edge in edges:
        key = (str(edge["source_type"]), str(edge["relation_type"]), str(edge["target_type"]))
        row = rows.setdefault(
            key,
            {
                "relación": " → ".join(key),
                "aristas": 0,
                "evidencia": set(),
                "estado estructural": STRUCTURAL_LABELS.get(
                    structural_status(edge), structural_status(edge)
                ),
                "trazo": evidence_style(style_status(edge)).label,
            },
        )
        row["aristas"] += 1
        row["evidencia"].add(evidence_style(str(edge["evidence_status"])).label)
    return [
        {**row, "evidencia": ", ".join(sorted(row["evidencia"]))} for _, row in sorted(rows.items())
    ]


__all__ = [
    "DEFAULT_MAX_TAXA",
    "HYPOTHETICAL_LABEL",
    "STRUCTURAL_LABELS",
    "SYNTHETIC_LEGEND_NOTE",
    "Records",
    "ViewerView",
    "legend",
    "node_types",
    "relations",
    "sample_taxa",
    "scenario_graph",
    "structural_status",
    "style_status",
    "viewer_view",
]
