"""Página Grafo: el grafo heterogéneo del escenario activo (A97, #320).

Dibuja la instancia derivada del escenario guardado en la sesión (página Escenario) o, si no hay
uno, el basal del primer animal de test de la corrida. Se filtra por tipo de nodo y por relación,
y muestra un número fijo de taxones, elegidos de forma determinista.
"""

from __future__ import annotations

import time
from typing import Any

import streamlit as st

from nutrigraphdt import api
from nutrigraphdt.demo import cache, plots, state, ui
from nutrigraphdt.demo import graph_viewer as viewer
from nutrigraphdt.demo.data import NODE_TYPE_LABELS


def _request(engine: Any) -> tuple[Any, bool]:
    current = state.scenario()
    if current is not None:
        return current, True
    tests = [s for s in engine.base.sample_ids if engine.split_of(s) == "test"]
    sample_id = tests[0] if tests else engine.base.sample_ids[0]
    return (
        api.ScenarioRequest(contract_version=api.API_CONTRACT_VERSION, base_instance=sample_id),
        False,
    )


def render() -> None:
    ui.hero(
        "Grafo",
        "El grafo heterogéneo del escenario.",
        "Cada columna es un tipo de nodo y cada arista se dibuja según su evidencia. Es la "
        "instancia que recibe el modelo: el animal base con las variables del escenario ya "
        "aplicadas.",
        badges=[("Datos sintéticos", "synthetic")],
    )
    try:
        engine = cache.engine(state.get(state.ACTIVE_RUN) or cache.active_run())
    except (ImportError, api.ScenarioContractError) as error:
        st.error(f"La corrida no se pudo cargar: {error}")
        return
    request, from_session = _request(engine)
    declared = ", ".join(f"{i.variable} = {i.value}" for i in request.intervention)
    st.caption(
        (
            "Escenario de la página Escenario"
            if from_session
            else "Sin escenario en la sesión: se muestra el basal"
        )
        + f" · animal {request.base_instance} · intervención: {declared or 'ninguna'}."
    )
    try:
        records = viewer.scenario_graph(engine, request)
    except api.ScenarioContractError as error:
        st.error(
            "El escenario no se pudo construir:\n\n" + "\n".join(f"- {p}" for p in error.problems)
        )
        return

    all_types = viewer.node_types(records)
    all_relations = viewer.relations(records)
    left, middle, right = st.columns([2, 2, 1])
    types = left.multiselect(
        "Tipos de nodo",
        all_types,
        default=all_types,
        format_func=lambda t: NODE_TYPE_LABELS.get(t, t),
        key="ng_graph_types",
    )
    relation_types = middle.multiselect(
        "Relaciones", all_relations, default=all_relations, key="ng_graph_relations"
    )
    max_taxa = right.number_input(
        "Taxones a mostrar",
        min_value=1,
        max_value=200,
        value=viewer.DEFAULT_MAX_TAXA,
        step=1,
        key="ng_graph_max_taxa",
    )
    if not types:
        st.info("Elija al menos un tipo de nodo.")
        return
    start = time.perf_counter()
    result = viewer.viewer_view(
        records, types=types, relation_types=relation_types, max_taxa=int(max_taxa)
    )
    figure = plots.graph_figure(result.view)
    elapsed = time.perf_counter() - start
    if result.total_taxa:
        st.markdown(
            f"**{result.shown_taxa} de {result.total_taxa} taxones** "
            "(los de más aristas y, entre ellos, los más abundantes)."
        )
    st.plotly_chart(figure, use_container_width=True, config=ui.CHART_CONFIG, key="ng_graph_figure")
    st.caption(f"Figura armada en {elapsed * 1000:.0f} ms.")
    st.markdown("**Leyenda de evidencia**")
    st.caption(viewer.SYNTHETIC_LEGEND_NOTE)
    st.dataframe(result.legend, hide_index=True)


__all__ = ["render"]
