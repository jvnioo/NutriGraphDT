"""Figuras de Plotly de la demo."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

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


FOCUS_EDGE_COLORS: dict[int, str] = {1: "rgba(200,85,61,.85)", 2: "rgba(217,151,59,.9)"}
LABEL_CHARS = 26


def graph_figure(
    view: GraphView,
    *,
    focus: Mapping[tuple[str, str], int] | None = None,
    focus_edges: set[int] | None = None,
    height: int | None = None,
) -> go.Figure:
    """Grafo heterogéneo en columnas por tipo de nodo.

    Los nodos sin aristas se dibujan como círculos vacíos. `focus` asigna un nivel a los nodos
    resaltados (0 para el nodo elegido, 1 y 2 para sus vecinos a uno y dos saltos, o 1 para todo
    un camino) y `focus_edges` dice qué aristas resaltar; el resto queda atenuado. La altura se
    ajusta a la columna más larga.
    """
    focus = dict(focus or {})
    focus_edges = set(focus_edges or set())
    position = {(n["node_type"], n["node_id"]): (n["x"], n["y"]) for n in view.nodes}
    fig = go.Figure()

    def add_edges(indices: list[int], color: str, width: float) -> None:
        xs: list[float | None] = []
        ys: list[float | None] = []
        for index in indices:
            edge = view.edges[index]
            x0, y0 = position[(edge["source_type"], edge["source_id"])]
            x1, y1 = position[(edge["target_type"], edge["target_id"])]
            xs += [x0, x1, None]
            ys += [y0, y1, None]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line={"width": width, "color": color},
                hoverinfo="skip",
                showlegend=False,
            )
        )

    background = [i for i in range(len(view.edges)) if i not in focus_edges]
    add_edges(background, f"rgba(20,35,46,{0.07 if focus else 0.22})", 1)
    by_level: dict[int, list[int]] = {}
    for index in focus_edges:
        edge = view.edges[index]
        level = max(
            focus.get((edge["source_type"], edge["source_id"]), 1),
            focus.get((edge["target_type"], edge["target_id"]), 1),
        )
        by_level.setdefault(level, []).append(index)
    for level in sorted(by_level):
        add_edges(by_level[level], FOCUS_EDGE_COLORS.get(level, FOCUS_EDGE_COLORS[2]), 2.4)

    for node_type in view.node_types:
        nodes = [n for n in view.nodes if n["node_type"] == node_type]
        color = NODE_COLORS.get(node_type, MUTED)
        keys = [(n["node_type"], n["node_id"]) for n in nodes]
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
                        "width": [
                            3 if focus.get(key) == 0 else (1 if n["degree"] else 2)
                            for key, n in zip(keys, nodes, strict=True)
                        ],
                        "color": [
                            NAVY if focus.get(key) == 0 else ("white" if n["degree"] else color)
                            for key, n in zip(keys, nodes, strict=True)
                        ],
                    },
                    "opacity": [1.0 if not focus or key in focus else 0.15 for key in keys],
                },
                hovertext=[_hover(n) for n in nodes],
                hoverinfo="text",
                showlegend=False,
            )
        )
        # Entrada de leyenda aparte, para que no herede la atenuación de los nodos.
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker={"size": 10, "color": color},
                name=NODE_TYPE_LABELS.get(node_type, node_type),
            )
        )
    rows = max((sum(n["node_type"] == t for n in view.nodes) for t in view.node_types), default=1)
    top = max((n["y"] for n in view.nodes), default=0.0) + 1.4
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
    fig.update_xaxes(visible=False, range=[-0.4, len(view.node_types) - 0.1])
    fig.update_yaxes(visible=False)
    _layout(fig, height=height or int(min(760, max(380, 150 + 30 * rows))))
    fig.update_layout(
        legend={"orientation": "h", "y": 0, "yanchor": "top"},
        margin={"l": 10, "r": 10, "t": 10, "b": 30},
    )
    return fig


def _short_label(label: str) -> str:
    return label if len(label) <= LABEL_CHARS else label[: LABEL_CHARS - 1] + "…"


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
    height: int = 340,
) -> go.Figure:
    """Barras por modelo con una línea en el valor de "predecir la media" (`reference`).

    Cada fila trae `modelo` (nombre para mostrar) y `clave`; la de `dummy_mean` es la
    referencia. Además del color, cada barra dice "mejor" o "peor" que la media.
    """
    labels = []
    colors = []
    for row in rows:
        if row["clave"] == "dummy_mean":
            labels.append(f"{row[value]:.2f}")
            colors.append(MUTED)
        elif row[value] < reference:
            labels.append(f"{row[value]:.2f}<br>▼ mejor")
            colors.append(TEAL)
        else:
            labels.append(f"{row[value]:.2f}<br>▲ peor")
            colors.append(CORAL)
    fig = go.Figure(
        go.Bar(
            x=[row["modelo"] for row in rows],
            y=[row[value] for row in rows],
            marker_color=colors,
            text=labels,
            textposition="outside",
            cliponaxis=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[rows[0]["modelo"], rows[-1]["modelo"]],
            y=[reference, reference],
            mode="lines",
            line={"dash": "dot", "color": MUTED},
            name="predecir siempre la media",
            hoverinfo="skip",
        )
    )
    fig.update_traces(showlegend=False, selector={"type": "bar"})
    top = max(row[value] for row in rows)
    fig.update_yaxes(title="RMSE (mmol/kg)", gridcolor="#E9ECE8", range=[0, top * 1.25])
    return _layout(fig, height=height, title=title)


def animal_vs_cohort_figure(
    rows: Sequence[Mapping[str, Any]], *, selected: str, height: int = 300
) -> go.Figure:
    """Los tres AGCC de cada animal (puntos) con el animal `selected` (`graph_id`) resaltado."""
    fig = make_subplots(rows=1, cols=3, subplot_titles=list(TARGET_LABELS.values()))
    for column, target in enumerate(TARGET_LABELS, 1):
        others = [row for row in rows if row["graph_id"] != selected]
        mine = [row for row in rows if row["graph_id"] == selected]
        fig.add_trace(
            go.Box(
                y=[row[target] for row in others],
                boxpoints="all",
                jitter=0.6,
                pointpos=0,
                marker={"color": TEAL, "size": 6, "opacity": 0.55},
                line={"color": "rgba(14,153,135,.4)"},
                fillcolor="rgba(14,153,135,.06)",
                name="otros animales",
                showlegend=column == 1,
                hoverinfo="y",
            ),
            row=1,
            col=column,
        )
        if mine:
            fig.add_trace(
                go.Scatter(
                    x=["otros animales"],
                    y=[mine[0][target]],
                    mode="markers",
                    marker={"color": CORAL, "size": 15, "line": {"color": "white", "width": 2}},
                    name="este animal",
                    showlegend=column == 1,
                ),
                row=1,
                col=column,
            )
        fig.update_yaxes(title_text="mmol/kg" if column == 1 else None, row=1, col=column)
    fig.update_xaxes(showticklabels=False)
    _layout(fig, height=height)
    fig.update_layout(legend={"orientation": "h", "y": -0.08}, margin={"t": 30, "b": 30})
    return fig


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
    "animal_vs_cohort_figure",
    "bars_figure",
    "curves_figure",
    "graph_figure",
    "predicted_vs_measured",
    "split_figure",
    "versus_mean_figure",
]
