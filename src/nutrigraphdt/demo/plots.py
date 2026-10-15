"""Figuras de Plotly de la demo."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import plotly.graph_objects as go

from nutrigraphdt.demo.data import NODE_TYPE_LABELS, GraphView
from nutrigraphdt.demo.ui import BLUE, CORAL, MUTED, NAVY, NODE_COLORS, TEAL, TEAL_LIGHT

SERIES_COLORS: tuple[str, ...] = (TEAL, CORAL, BLUE, "#D9973B", "#8E6C8A", TEAL_LIGHT)
TARGET_LABELS: dict[str, str] = {
    "acetate": "Acetato",
    "propionate": "Propionato",
    "butyrate": "Butirato",
}


def _layout(fig: go.Figure, *, height: int, title: str | None = None) -> go.Figure:
    fig.update_layout(
        height=height,
        title={"text": title, "font": {"size": 15, "color": NAVY}} if title else None,
        margin={"l": 10, "r": 10, "t": 40 if title else 10, "b": 60},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": NAVY},
        legend={"orientation": "h", "y": -0.28},
    )
    return fig


def graph_figure(view: GraphView, *, height: int = 620) -> go.Figure:
    """Grafo heterogéneo en columnas por tipo de nodo; las aristas se colorean por relación."""
    position = {(n["node_type"], n["node_id"]): (n["x"], n["y"]) for n in view.nodes}
    fig = go.Figure()
    relations = sorted({edge["relation"] for edge in view.edges})
    for relation in relations:
        xs: list[float | None] = []
        ys: list[float | None] = []
        for edge in view.edges:
            if edge["relation"] != relation:
                continue
            x0, y0 = position[(edge["source_type"], edge["source_id"])]
            x1, y1 = position[(edge["target_type"], edge["target_id"])]
            xs += [x0, x1, None]
            ys += [y0, y1, None]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line={"width": 1, "color": "rgba(20,35,46,.22)"},
                hoverinfo="skip",
                name=relation,
                showlegend=False,
            )
        )
    for node_type in view.node_types:
        nodes = [n for n in view.nodes if n["node_type"] == node_type]
        fig.add_trace(
            go.Scatter(
                x=[n["x"] for n in nodes],
                y=[n["y"] for n in nodes],
                mode="markers+text",
                text=[n["label"][:18] for n in nodes],
                textposition="middle right",
                textfont={"size": 10, "color": MUTED},
                marker={
                    "size": [10 + 2.2 * math.sqrt(n["degree"]) for n in nodes],
                    "color": NODE_COLORS.get(node_type, MUTED),
                    "line": {"width": 1, "color": "white"},
                },
                hovertext=[_hover(n) for n in nodes],
                hoverinfo="text",
                name=NODE_TYPE_LABELS.get(node_type, node_type),
            )
        )
    top = max((n["y"] for n in view.nodes), default=0.0) + 1.6
    for column, node_type in enumerate(view.node_types):
        hidden = view.hidden.get(node_type)
        label = NODE_TYPE_LABELS.get(node_type, node_type)
        fig.add_annotation(
            x=column,
            y=top,
            text=f"<b>{label}</b>"
            + (f"<br><span style='font-size:10px'>+{hidden} ocultos</span>" if hidden else ""),
            showarrow=False,
            font={"color": NODE_COLORS.get(node_type, NAVY), "size": 12},
        )
    fig.update_xaxes(visible=False, range=[-0.5, len(view.node_types) - 0.2])
    fig.update_yaxes(visible=False)
    return _layout(fig, height=height)


def _hover(node: Mapping[str, Any]) -> str:
    lines = [f"<b>{node['label']}</b>", f"{NODE_TYPE_LABELS.get(node['node_type'], '')}"]
    lines += [f"{key}: {value}" for key, value in list(node["attributes"].items())[:8]]
    lines.append(f"aristas: {node['degree']}")
    return "<br>".join(lines)


def curves_figure(
    series: Mapping[str, Sequence[float | None]],
    *,
    title: str,
    y_title: str,
    log_y: bool = False,
    marker_x: int | None = None,
    height: int = 340,
) -> go.Figure:
    """Curvas por época; `marker_x` marca una época (por ejemplo, la mejor)."""
    fig = go.Figure()
    for color, (name, values) in zip(SERIES_COLORS * 3, series.items(), strict=False):
        fig.add_trace(
            go.Scatter(
                x=list(range(1, len(values) + 1)),
                y=list(values),
                mode="lines",
                name=name,
                line={"color": color, "width": 2},
            )
        )
    if marker_x is not None:
        fig.add_vline(x=marker_x, line={"dash": "dot", "color": MUTED})
    fig.update_xaxes(title="época", gridcolor="#E9ECE8")
    fig.update_yaxes(
        title=y_title,
        type="log" if log_y else "linear",
        exponentformat="power",
        gridcolor="#E9ECE8",
    )
    return _layout(fig, height=height, title=title)


def bars_figure(
    rows: Sequence[Mapping[str, Any]],
    *,
    category: str,
    values: Sequence[str],
    title: str,
    height: int = 340,
) -> go.Figure:
    """Barras agrupadas: una serie por columna de `values`, una categoría por fila."""
    fig = go.Figure()
    for color, column in zip(SERIES_COLORS * 3, values, strict=False):
        fig.add_trace(
            go.Bar(
                x=[row[category] for row in rows],
                y=[row[column] for row in rows],
                name=column,
                marker_color=color,
            )
        )
    fig.update_layout(barmode="group")
    fig.update_yaxes(gridcolor="#E9ECE8")
    return _layout(fig, height=height, title=title)


def predicted_vs_measured(
    rows: Sequence[Mapping[str, str]], *, subset: str, height: int = 340
) -> go.Figure:
    """Medido frente a predicho por AGCC en `subset`, con la diagonal de predicción perfecta."""
    fig = go.Figure()
    limits: list[float] = []
    for color, (target, label) in zip(SERIES_COLORS, TARGET_LABELS.items(), strict=False):
        points = [
            (float(row[f"measured_{target}"]), float(row[f"predicted_{target}"]))
            for row in rows
            if row.get("subset") == subset and row.get(f"measured_{target}")
        ]
        if not points:
            continue
        limits += [value for point in points for value in point]
        fig.add_trace(
            go.Scatter(
                x=[p[0] for p in points],
                y=[p[1] for p in points],
                mode="markers",
                name=label,
                marker={"color": color, "size": 8, "opacity": 0.8},
            )
        )
    if limits:
        low, high = min(limits), max(limits)
        fig.add_trace(
            go.Scatter(
                x=[low, high],
                y=[low, high],
                mode="lines",
                line={"dash": "dot", "color": MUTED},
                name="predicción perfecta",
            )
        )
    fig.update_xaxes(title="medido (mmol/kg)", gridcolor="#E9ECE8")
    fig.update_yaxes(title="predicho (mmol/kg)", gridcolor="#E9ECE8")
    return _layout(fig, height=height, title=f"Medido vs. predicho · {subset}")


__all__ = [
    "TARGET_LABELS",
    "bars_figure",
    "curves_figure",
    "graph_figure",
    "predicted_vs_measured",
]
