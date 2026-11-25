"""Figuras de Plotly de la comparación entre el grafo sintético y el de D1."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import plotly.graph_objects as go

from nutrigraphdt.demo.data import NODE_TYPE_LABELS, GraphView
from nutrigraphdt.demo.ui import AMBER, MUTED, NAVY, NODE_COLORS, TEAL
from nutrigraphdt.explainability.style import evidence_style

LABEL_CHARS = 26


def _layout(fig: go.Figure, *, height: int) -> go.Figure:
    fig.update_layout(
        height=height,
        margin={"l": 10, "r": 10, "t": 10, "b": 30},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": NAVY},
        legend={"orientation": "h", "y": 0, "yanchor": "top"},
    )
    return fig


# ---------------------------------------------------------------------------
# Esquema v1
# ---------------------------------------------------------------------------

_SCHEMA_POSITIONS: dict[str, tuple[float, float]] = {
    "diet": (0.0, 0.0),
    "substrate": (1.0, 0.0),
    "taxon": (2.0, 0.0),
    "function": (3.0, 0.0),
    "metabolite": (4.0, 0.0),
    "host": (5.0, 0.0),
    "additive": (2.5, 1.1),
    "phenotype": (4.5, -1.1),
}
_STATUS_STYLE: dict[str, tuple[str, str, float]] = {
    "Presente": (TEAL, "solid", 4.0),
    "Limitación declarada": (AMBER, "dash", 2.0),
    "Fuera de D1": ("#B8C0C5", "dot", 1.5),
}
_BENT: set[tuple[str, str]] = {("additive", "function"), ("host", "phenotype")}


def schema_figure(
    relation_rows: Sequence[Mapping[str, Any]],
    present_types: set[str],
    *,
    height: int = 360,
) -> go.Figure:
    """Esquema v1 con cada relación según su `estado` y los tipos ausentes en gris.

    El nombre y el motivo de cada relación aparecen al pasar el cursor por su punto medio.
    """
    fig = go.Figure()
    shown: set[str] = set()
    for row in relation_rows:
        color, dash, width = _STATUS_STYLE[row["estado"]]
        source, target = row["origen"], row["destino"]
        x0, y0 = _SCHEMA_POSITIONS[source]
        x1, y1 = _SCHEMA_POSITIONS[target]
        if source == target:
            xs = [x0, x0 - 0.25, x0, x0 + 0.25, x0]
            ys = [y0, y0 + 0.45, y0 + 0.6, y0 + 0.45, y0]
            mid = (x0, y0 + 0.62)
        else:
            bend = 0.18 if (source, target) in _BENT else 0.0
            xs = [x0, (x0 + x1) / 2, x1]
            ys = [y0, (y0 + y1) / 2 + bend, y1]
            mid = ((x0 + x1) / 2, (y0 + y1) / 2 + bend + (0.13 if y0 == y1 else 0.0))
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line={"color": color, "dash": dash, "width": width, "shape": "spline"},
                hoverinfo="skip",
                name=row["estado"],
                legendgroup=row["estado"],
                showlegend=row["estado"] not in shown,
            )
        )
        shown.add(row["estado"])
        fig.add_trace(
            go.Scatter(
                x=[mid[0]],
                y=[mid[1]],
                mode="markers",
                marker={"size": 12, "color": "rgba(0,0,0,0)"},
                hovertext=[
                    f"{source} → {row['relación']} → {target}<br>{row['estado']}: {row['motivo']}"
                ],
                hoverinfo="text",
                showlegend=False,
            )
        )
    for node_type, (x, y) in _SCHEMA_POSITIONS.items():
        present = node_type in present_types
        fig.add_trace(
            go.Scatter(
                x=[x],
                y=[y],
                mode="markers+text",
                marker={
                    "size": 34,
                    "color": NODE_COLORS[node_type] if present else "#E3E6E2",
                    "line": {"width": 2, "color": "white"},
                },
                text=[NODE_TYPE_LABELS.get(node_type, node_type)],
                textposition="bottom center",
                textfont={"color": NAVY if present else MUTED},
                hovertext=[f"{node_type}: {'presente' if present else 'ausente'}"],
                hoverinfo="text",
                showlegend=False,
            )
        )
    fig.update_xaxes(visible=False, range=[-0.5, 5.6])
    fig.update_yaxes(visible=False, range=[-1.6, 1.6])
    _layout(fig, height=height)
    fig.update_layout(legend={"y": -0.05})
    return fig


# ---------------------------------------------------------------------------
# Instancia
# ---------------------------------------------------------------------------


def graph_figure(view: GraphView, *, height: int | None = None) -> go.Figure:
    """Una instancia en columnas por tipo de nodo, con las aristas según su evidencia.

    Cada estado de evidencia (DS-01) tiene su trazo y su color (`evidence_style`). Los nodos sin
    aristas se dibujan como círculos vacíos y el tamaño crece con las conexiones. La altura se
    ajusta a la columna más larga.
    """
    position = {(n["node_type"], n["node_id"]): (n["x"], n["y"]) for n in view.nodes}
    fig = go.Figure()
    by_status: dict[str, list[Mapping[str, Any]]] = {}
    for edge in view.edges:
        by_status.setdefault(edge["evidence_status"], []).append(edge)
    for status, edges in by_status.items():
        style = evidence_style(status)
        xs: list[float | None] = []
        ys: list[float | None] = []
        for item in edges:
            x0, y0 = position[(item["source_type"], item["source_id"])]
            x1, y1 = position[(item["target_type"], item["target_id"])]
            xs += [x0, x1, None]
            ys += [y0, y1, None]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line={"width": 1.2, "color": style.color, "dash": style.dash},
                opacity=0.55,
                hoverinfo="skip",
                name=f"Arista {style.label}",
                meta={"evidence_status": status},
            )
        )

    for node_type in view.node_types:
        nodes = [n for n in view.nodes if n["node_type"] == node_type]
        color = NODE_COLORS.get(node_type, MUTED)
        fig.add_trace(
            go.Scatter(
                x=[n["x"] for n in nodes],
                y=[n["y"] for n in nodes],
                mode="markers+text",
                text=[_short_label(n["label"]) for n in nodes],
                textposition="middle right",
                textfont={"size": 10, "color": MUTED},
                marker={
                    "size": [10 + 2.2 * math.sqrt(n["degree"]) for n in nodes],
                    "color": color,
                    "symbol": ["circle" if n["degree"] else "circle-open" for n in nodes],
                    "line": {
                        "width": [1 if n["degree"] else 2 for n in nodes],
                        "color": ["white" if n["degree"] else color for n in nodes],
                    },
                },
                hovertext=[_hover(n) for n in nodes],
                hoverinfo="text",
                showlegend=False,
            )
        )
    rows = max((sum(n["node_type"] == t for n in view.nodes) for t in view.node_types), default=1)
    top = max((n["y"] for n in view.nodes), default=0.0) + 1.4
    for column, node_type in enumerate(view.node_types):
        hidden = view.hidden.get(node_type)
        extra = f"<br><span style='font-size:10px'>+{hidden} más</span>" if hidden else ""
        fig.add_annotation(
            x=column,
            y=top,
            text=f"<b>{NODE_TYPE_LABELS.get(node_type, node_type)}</b>{extra}",
            showarrow=False,
            font={"color": NODE_COLORS.get(node_type, NAVY), "size": 12},
        )
    fig.update_xaxes(visible=False, range=[-0.4, len(view.node_types) - 0.1])
    fig.update_yaxes(visible=False)
    return _layout(fig, height=height or int(min(760, max(380, 150 + 30 * rows))))


def _short_label(label: str) -> str:
    return label if len(label) <= LABEL_CHARS else label[: LABEL_CHARS - 1] + "…"


def _hover(node: Mapping[str, Any]) -> str:
    lines = [f"<b>{node['label']}</b>", f"{NODE_TYPE_LABELS.get(node['node_type'], '')}"]
    lines += [f"{key}: {value}" for key, value in list(node["attributes"].items())[:8]]
    lines.append(f"conexiones: {node['degree']}" if node["degree"] else "sin conexiones")
    return "<br>".join(lines)


__all__ = ["graph_figure", "schema_figure"]
