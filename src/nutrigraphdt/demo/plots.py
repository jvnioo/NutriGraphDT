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


def graph_figure(
    view: GraphView,
    *,
    highlight: tuple[set[tuple[str, str]], set[int]] | None = None,
    height: int = 620,
) -> go.Figure:
    """Grafo heterogéneo en columnas por tipo de nodo.

    Los nodos sin aristas se dibujan como círculos vacíos. Con `highlight` (de `upstream`), lo
    que no pertenece a la ruta queda atenuado.
    """
    position = {(n["node_type"], n["node_id"]): (n["x"], n["y"]) for n in view.nodes}
    nodes_on, edges_on = highlight if highlight else (set(), set())
    fig = go.Figure()
    for active in (False, True):
        xs: list[float | None] = []
        ys: list[float | None] = []
        for index, edge in enumerate(view.edges):
            if highlight and (index in edges_on) != active:
                continue
            if not highlight and active:
                continue
            x0, y0 = position[(edge["source_type"], edge["source_id"])]
            x1, y1 = position[(edge["target_type"], edge["target_id"])]
            xs += [x0, x1, None]
            ys += [y0, y1, None]
        dimmed = highlight is not None and not active
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line={
                    "width": 2.2 if active else 1,
                    "color": "rgba(200,85,61,.75)"
                    if active
                    else f"rgba(20,35,46,{0.07 if dimmed else 0.22})",
                },
                hoverinfo="skip",
                showlegend=False,
            )
        )
    for node_type in view.node_types:
        nodes = [n for n in view.nodes if n["node_type"] == node_type]
        color = NODE_COLORS.get(node_type, MUTED)
        opacity = [
            1.0 if not highlight or (n["node_type"], n["node_id"]) in nodes_on else 0.18
            for n in nodes
        ]
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
                    "color": color,
                    "symbol": ["circle" if n["degree"] else "circle-open" for n in nodes],
                    "line": {
                        "width": [1 if n["degree"] else 2 for n in nodes],
                        "color": [("white" if n["degree"] else color) for n in nodes],
                    },
                    "opacity": opacity,
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
        extra = f"<br><span style='font-size:10px'>+{hidden} más</span>" if hidden else ""
        fig.add_annotation(
            x=column,
            y=top,
            text=f"<b>{label}</b>{extra}",
            showarrow=False,
            font={"color": NODE_COLORS.get(node_type, NAVY), "size": 12},
        )
    fig.update_xaxes(visible=False, range=[-0.5, len(view.node_types) - 0.2])
    fig.update_yaxes(visible=False)
    return _layout(fig, height=height)


def _hover(node: Mapping[str, Any]) -> str:
    lines = [f"<b>{node['label']}</b>", f"{NODE_TYPE_LABELS.get(node['node_type'], '')}"]
    lines += [f"{key}: {value}" for key, value in list(node["attributes"].items())[:8]]
    lines.append(f"conexiones: {node['degree']}" if node["degree"] else "sin conexiones")
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


def split_figure(rows: Sequence[Mapping[str, Any]], *, height: int = 210) -> go.Figure:
    """Barras horizontales apiladas: animales por subconjunto, una fila por población."""
    fig = go.Figure()
    colors = {"train": TEAL, "val": "#D9973B", "test": BLUE}
    for subset, color in colors.items():
        fig.add_trace(
            go.Bar(
                y=[row["población"] for row in rows],
                x=[row[subset] for row in rows],
                name=subset,
                orientation="h",
                marker_color=color,
                text=[row[subset] for row in rows],
                textposition="inside",
                insidetextfont={"color": "white"},
            )
        )
    fig.update_layout(barmode="stack", legend={"traceorder": "normal"})
    fig.update_xaxes(title="animales", gridcolor="#E9ECE8")
    return _layout(fig, height=height)


def versus_mean_figure(
    rows: Sequence[Mapping[str, Any]],
    *,
    value: str,
    reference: float,
    title: str,
    height: int = 330,
) -> go.Figure:
    """Barras por modelo con una línea en el valor de "predecir la media" (`reference`)."""
    fig = go.Figure(
        go.Bar(
            x=[row["modelo"] for row in rows],
            y=[row[value] for row in rows],
            marker_color=[
                MUTED
                if row["modelo"] == "dummy_mean"
                else (TEAL if row[value] < reference else CORAL)
                for row in rows
            ],
            text=[f"{row[value]:.2f}" for row in rows],
            textposition="outside",
        )
    )
    fig.add_hline(
        y=reference,
        line={"dash": "dot", "color": MUTED},
        annotation_text="predecir siempre la media",
        annotation_position="top right",
    )
    fig.update_yaxes(title="RMSE (mmol/kg)", gridcolor="#E9ECE8", rangemode="tozero")
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
    "split_figure",
    "versus_mean_figure",
]
