"""Figuras de Plotly de la demo."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from nutrigraphdt.demo.data import NODE_TYPE_LABELS, GraphView
from nutrigraphdt.demo.ui import CORAL, MUTED, NAVY, NODE_COLORS, TEAL
from nutrigraphdt.explainability.style import evidence_legend, evidence_style
from nutrigraphdt.explainability.subgraph import ExplanatorySubgraphView

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


SUBGRAPH_TYPE_ORDER: tuple[str, ...] = tuple(NODE_TYPE_LABELS)
"""Columnas del subgrafo explicativo: el orden de los tipos del esquema v1."""


def subgraph_figure(view: ExplanatorySubgraphView, *, height: int | None = None) -> go.Figure:
    """Subgrafo explicativo top-k con el estilo de evidencia de cada arista (C-03, #243).

    El trazo y el color de una arista dependen solo de su estado de evidencia
    (`evidence_style`); el grosor, solo de su |importancia|. Todas las aristas del subgrafo se
    dibujan, también las `hypothetical`. La leyenda muestra los cinco estados de DS-01 aunque el
    subgrafo no los tenga. Los nodos van en columnas por tipo, ordenados por importancia.
    """
    types = [t for t in SUBGRAPH_TYPE_ORDER if any(n.node_type == t for n in view.nodes)]
    types += sorted({n.node_type for n in view.nodes} - set(types))
    position: dict[tuple[str, str], tuple[float, float]] = {}
    for column, node_type in enumerate(types):
        nodes = sorted(
            (n for n in view.nodes if n.node_type == node_type),
            key=lambda n: (-abs(n.importance), n.node_id),
        )
        for row, node in enumerate(nodes):
            position[(node.node_type, node.node_id)] = (float(column), -float(row))
    fig = go.Figure()

    max_abs = max((abs(e.importance) for e in view.edges), default=0.0) or 1.0
    for edge in view.edges:
        style = evidence_style(edge.evidence.evidence_status)
        x0, y0 = position[(edge.source_type, edge.source_id)]
        x1, y1 = position[(edge.target_type, edge.target_id)]
        evidence = f"{style.label}<br>método: {edge.evidence.evidence_method}" + (
            f"<br>fuente: {edge.evidence.evidence_source}" if edge.evidence.evidence_source else ""
        )
        fig.add_trace(
            go.Scatter(
                x=[x0, (x0 + x1) / 2, x1],
                y=[y0, (y0 + y1) / 2, y1],
                mode="lines+markers",
                line={
                    "color": style.color,
                    "dash": style.dash,
                    "width": 1.5 + 5.0 * abs(edge.importance) / max_abs,
                },
                marker={"size": [0, 8, 0], "color": style.color, "opacity": [0, 0.01, 0]},
                hovertext=[
                    "",
                    f"<b>{edge.source_id} → {edge.relation_type} → {edge.target_id}</b><br>"
                    f"importancia: {edge.importance:.3f}<br>evidencia: {evidence}",
                    "",
                ],
                hoverinfo="text",
                legendgroup=style.status,
                showlegend=False,
                meta={"evidence_status": style.status},
            )
        )
    for style in evidence_legend():
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="lines",
                line={"color": style.color, "dash": style.dash, "width": 3},
                name=style.label,
                legendgroup=style.status,
            )
        )

    for node_type in types:
        nodes = [n for n in view.nodes if n.node_type == node_type]
        color = NODE_COLORS.get(node_type, MUTED)
        fig.add_trace(
            go.Scatter(
                x=[position[(n.node_type, n.node_id)][0] for n in nodes],
                y=[position[(n.node_type, n.node_id)][1] for n in nodes],
                mode="markers+text",
                text=[_short_label(n.node_id) for n in nodes],
                textposition="top center",
                textfont={"size": 10, "color": MUTED},
                marker={
                    "size": [10 + 14 * min(1.0, abs(n.importance)) for n in nodes],
                    "color": color,
                    "line": {"width": 1, "color": "white"},
                },
                hovertext=[
                    f"<b>{n.node_id}</b><br>{NODE_TYPE_LABELS.get(n.node_type, n.node_type)}"
                    f"<br>importancia: {n.importance:.3f}"
                    for n in nodes
                ],
                hoverinfo="text",
                showlegend=False,
            )
        )
    rows = max((sum(n.node_type == t for n in view.nodes) for t in types), default=1)
    for column, node_type in enumerate(types):
        fig.add_annotation(
            x=column,
            y=0.75,
            text=f"<b>{NODE_TYPE_LABELS.get(node_type, node_type)}</b>",
            showarrow=False,
            font={"color": NODE_COLORS.get(node_type, NAVY), "size": 12},
        )
    fig.update_xaxes(visible=False, range=[-0.5, max(len(types), 1) - 0.5])
    fig.update_yaxes(visible=False, range=[-(rows - 1) - 0.5, 0.95])
    _layout(fig, height=height or int(min(640, 220 + 70 * rows)))
    # Leyenda vertical a la derecha: las cinco etiquetas no caben en una fila.
    fig.update_layout(
        legend={
            "orientation": "v",
            "x": 1.0,
            "xanchor": "left",
            "y": 1.0,
            "title": {"text": "<b>Evidencia</b>"},
        },
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
    )
    return fig


def _short_label(label: str) -> str:
    return label if len(label) <= LABEL_CHARS else label[: LABEL_CHARS - 1] + "…"


def _hover(node: Mapping[str, Any]) -> str:
    lines = [f"<b>{node['label']}</b>", f"{NODE_TYPE_LABELS.get(node['node_type'], '')}"]
    lines += [f"{key}: {value}" for key, value in list(node["attributes"].items())[:8]]
    lines.append(f"conexiones: {node['degree']}" if node["degree"] else "sin conexiones")
    return "<br>".join(lines)


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
    referencia. Además del color, cada barra dice si es mejor, igual (a dos decimales) o peor
    que la media.
    """
    labels = []
    colors = []
    for row in rows:
        if row["clave"] == "dummy_mean":
            labels.append(f"{row[value]:.2f}")
            colors.append(MUTED)
        elif abs(row[value] - reference) < 0.005:
            labels.append(f"{row[value]:.2f}<br>= igual")
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


def agcc_distribution_figure(
    quantiles: Mapping[str, Mapping[str, float]], *, height: int = 300
) -> go.Figure:
    """Diagrama de caja de cada AGCC desde sus cuantiles (mínimo, Q1, mediana, Q3, máximo)."""
    fig = make_subplots(rows=1, cols=3, subplot_titles=list(TARGET_LABELS.values()))
    for column, target in enumerate(TARGET_LABELS, 1):
        stats = quantiles[target]
        fig.add_trace(
            go.Box(
                q1=[stats["q1"]],
                median=[stats["median"]],
                q3=[stats["q3"]],
                lowerfence=[stats["min"]],
                upperfence=[stats["max"]],
                x=[TARGET_LABELS[target]],
                marker={"color": TEAL},
                line={"color": TEAL},
                fillcolor="rgba(14,153,135,.12)",
                showlegend=False,
            ),
            row=1,
            col=column,
        )
    fig.update_yaxes(title_text="mmol/kg", row=1, col=1)
    fig.update_xaxes(showticklabels=False)
    _layout(fig, height=height)
    fig.update_layout(margin={"t": 30, "b": 10})
    return fig


__all__ = [
    "TARGET_LABELS",
    "agcc_distribution_figure",
    "graph_figure",
    "versus_mean_figure",
]


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
    "Limitación declarada": ("#D9973B", "dash", 2.0),
    "Fuera de D1": ("#B8C0C5", "dot", 1.5),
}


def schema_figure(
    relation_rows: Sequence[Mapping[str, Any]],
    present_types: set[str],
    *,
    height: int = 360,
) -> go.Figure:
    """Esquema v1 con cada relación coloreada según `estado` (`Presente`, limitación o fuera)."""
    fig = go.Figure()
    in_d1 = present_types
    shown: set[str] = set()
    for row in relation_rows:
        color, dash, width = _STATUS_STYLE[row["estado"]]
        source, target = row["origen"], row["destino"]
        x0, y0 = _SCHEMA_POSITIONS[source]
        x1, y1 = _SCHEMA_POSITIONS[target]
        label = f"{source} → {row['relación']} → {target}<br>{row['estado']}: {row['motivo']}"
        if source == target:
            xs = [x0, x0 - 0.25, x0, x0 + 0.25, x0]
            ys = [y0, y0 + 0.45, y0 + 0.6, y0 + 0.45, y0]
            mid = (x0, y0 + 0.62)
        else:
            bend = (
                0.18
                if (source, target) in {("additive", "function"), ("host", "phenotype")}
                else 0.0
            )
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
        hidden = True  # el nombre aparece al pasar el cursor y en la tabla
        fig.add_trace(
            go.Scatter(
                x=[mid[0]],
                y=[mid[1]],
                mode="markers" if hidden else "text",
                marker={"size": 10, "color": "rgba(0,0,0,0)"},
                text=[row["relación"]],
                textfont={"size": 10, "color": color if row["estado"] == "Presente" else MUTED},
                hovertext=[label],
                hoverinfo="text",
                showlegend=False,
            )
        )
    for node_type, (x, y) in _SCHEMA_POSITIONS.items():
        present = node_type in in_d1
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
    fig.update_layout(legend={"orientation": "h", "y": -0.05})
    return _layout(fig, height=height)
