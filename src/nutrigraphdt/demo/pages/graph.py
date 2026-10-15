"""Explorador del grafo: una instancia sintética o real, nodo por nodo."""

from __future__ import annotations

import streamlit as st

from nutrigraphdt.demo import cache, data, plots, ui

_SOURCES = {
    "Sintético · escenario basal": ("synthetic", 0),
    "Sintético · escenario intervenido": ("synthetic", 1),
    "D1 HoloFood · animal real (fixture)": ("d1", None),
}


def render() -> None:
    ui.hero(
        "Explorador del grafo",
        "Un animal, un grafo.",
        "Cada instancia es un grafo heterogéneo: los nodos tienen tipo y atributos propios, y "
        "las aristas dicen qué relación une a dos entidades. Pase el cursor sobre un nodo para "
        "ver sus atributos.",
    )
    left, middle, right = st.columns([2, 2, 1])
    choice = left.selectbox("Instancia", list(_SOURCES))
    kind, index = _SOURCES[choice]
    if kind == "synthetic":
        records = cache.scenarios()
        graph_id = data.graph_ids(records)[int(index or 0)]
        badge = ui.badge("Sintético", "synthetic")
    else:
        built, _ = cache.d1_fixture()
        records = built.records
        graph_id = middle.selectbox("Animal", data.graph_ids(records))
        badge = ui.badge("Real · D1", "real")
    max_per_type = right.slider("Nodos por tipo", 5, 40, 15 if kind == "d1" else 20)

    view = data.graph_view(records, graph_id, max_per_type=max_per_type)
    info = data.instance_info(records, graph_id)
    st.markdown(
        f"{badge} `{graph_id}` · especie **{info['species']}** · segmento **{info['gut_segment']}**"
        f" · escenario **{info['scenario_id']}** · dieta **{info['diet_treatment']}**",
        unsafe_allow_html=True,
    )
    st.plotly_chart(config=ui.CHART_CONFIG, figure_or_data=plots.graph_figure(view))
    if view.hidden:
        hidden = ", ".join(
            f"{count} {data.NODE_TYPE_LABELS.get(t, t).lower()}" for t, count in view.hidden.items()
        )
        st.caption(
            f"Se ocultan {hidden}: por tipo se muestran primero los nodos con aristas y, entre los "
            "taxones, los más abundantes."
        )

    nodes, edges = data.type_counts(records, graph_id)
    col_nodes, col_edges, col_targets = st.columns([1, 2, 1])
    col_nodes.markdown("**Nodos por tipo**")
    col_nodes.dataframe(
        [{"tipo": data.NODE_TYPE_LABELS.get(t, t), "nodos": n} for t, n in nodes.items()],
        hide_index=True,
    )
    col_edges.markdown("**Aristas por relación**")
    col_edges.dataframe(
        [{"relación": r, "aristas": n} for r, n in edges.items()],
        hide_index=True,
    )
    col_targets.markdown("**Target (AGCC)**")
    targets = data.targets_of(records, graph_id)
    col_targets.dataframe(
        [{"metabolito": name, "mmol/kg": value} for name, value in targets.items()],
        hide_index=True,
    )
    if kind == "d1":
        ui.note(
            "En D1 los taxones están <b>aislados</b>: todavía no hay anotación taxón → función "
            "(S-03), así que la única relación es metabolito → medido en → huésped. Por eso la "
            "estructura del grafo solo se ejercita por completo en el sintético."
        )
    else:
        ui.note(
            "La ruta mecanística completa es dieta → sustrato → taxón → función → metabolito. "
            "El modelo agrega, además, una arista inversa por cada relación antes de entrenar."
        )
