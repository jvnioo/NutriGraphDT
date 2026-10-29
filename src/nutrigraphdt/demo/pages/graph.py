"""Grafos: una instancia sintética o de D1, con su estructura y sus AGCC."""

from __future__ import annotations

from typing import Any

import streamlit as st

from nutrigraphdt.demo import cache, data, plots, ui

_SCFA = ("acetate", "propionate", "butyrate", "Acetato", "Propionato", "Butirato")


def render() -> None:
    ui.hero(
        "Grafos",
        "Grafo heterogéneo por animal.",
        "Esquema v1: ocho tipos de nodo y once relaciones. Cada instancia (un animal o un "
        "escenario sintético) es un grafo.",
    )
    source = st.radio(
        "Fuente", ["Sintético", "D1 HoloFood (real)"], horizontal=True, key="graph_source"
    )
    if source == "Sintético":
        records = cache.scenarios()
        ids = data.graph_ids(records)
        graph_id = st.selectbox(
            "Escenario", ids, format_func=lambda gid: "basal" if "basal" in gid else "intervenido"
        )
        max_per_type = 20
    else:
        d1 = cache.d1_records()
        records = d1.records
        with_targets = {row["graph_id"] for row in cache.d1_agcc()}
        ids = [gid for gid in data.graph_ids(records) if gid in with_targets]
        left, right = st.columns([2, 1])
        graph_id = left.selectbox(
            f"Animal ({len(ids)} con los tres AGCC"
            + (f" de {len(data.graph_ids(records))} grafos)" if d1.full else ", fixture)"),
            ids,
            format_func=lambda gid: _animal_label(records, gid),
        )
        max_per_type = right.slider("Taxones mostrados (más abundantes)", 5, 40, 15)

    view = data.graph_view(records, graph_id, max_per_type=max_per_type)
    st.plotly_chart(plots.graph_figure(view), config=ui.CHART_CONFIG, key="graph")
    st.caption(
        "Columnas: tipos de nodo. Líneas: aristas. Círculo vacío: nodo sin aristas. Tamaño: "
        "número de conexiones."
        + (
            f" Se ocultan {sum(view.hidden.values())} nodos de menor abundancia."
            if view.hidden
            else ""
        )
    )
    nodes, edges = data.type_counts(records, graph_id)
    targets = data.targets_of(records, graph_id)
    left, middle, right = st.columns([1, 2, 1])
    left.markdown("**Nodos por tipo**")
    left.dataframe(
        [{"tipo": data.NODE_TYPE_LABELS.get(t, t), "nodos": n} for t, n in nodes.items()],
        hide_index=True,
    )
    middle.markdown("**Aristas por relación**")
    middle.dataframe(
        [{"relación": name, "aristas": count} for name, count in edges.items()],
        hide_index=True,
    )
    right.markdown("**AGCC (mmol/kg)**")
    right.dataframe(
        [{"metabolito": name, "valor": value} for name, value in targets.items() if name in _SCFA],
        hide_index=True,
    )


def _animal_label(records: Any, graph_id: str) -> str:
    info = data.instance_info(records, graph_id)
    return f"{info['sample_id']} · {info['diet_treatment']} · día {info['timepoint']}"
