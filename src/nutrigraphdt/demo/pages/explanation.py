"""Página Explicación: subgrafo explicativo e importancias del escenario (A104, #334).

Explica el escenario de la sesión (o el basal del primer animal de test) con GNNExplainer sobre el
modelo congelado de la corrida activa. El resultado se guarda en caché por corrida, escenario,
salida y semilla.
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
import streamlit as st

from nutrigraphdt import api
from nutrigraphdt.demo import cache, plots, state, ui
from nutrigraphdt.demo import explanation as explain
from nutrigraphdt.demo import graph_viewer as viewer
from nutrigraphdt.demo.data import NODE_TYPE_LABELS
from nutrigraphdt.explainability.style import evidence_legend


def _run() -> str:
    return str(state.get(state.ACTIVE_RUN) or cache.active_run())


@st.cache_resource(show_spinner="Ejecutando el explicador (unos segundos)…")
def _cached(run: str, request_json: str, target: str, seed: int) -> explain.ScenarioExplanation:
    request = api.ScenarioRequest.model_validate_json(request_json)
    return explain.explain_scenario(cache.engine(run), request, target=target, seed=seed)


def _request(engine: Any) -> tuple[Any, bool]:
    current = state.scenario()
    if current is not None:
        return current, True
    tests = [s for s in engine.base.sample_ids if engine.split_of(s) == "test"]
    sample_id = tests[0] if tests else engine.base.sample_ids[0]
    return api.ScenarioRequest(contract_version="1.0.0", base_instance=sample_id), False


def render() -> None:
    ui.hero(
        "Explicación",
        "Qué partes del grafo usa el modelo.",
        "GNNExplainer asigna a cada nodo y atributo de la instancia una importancia para una "
        "salida del modelo. Es una asociación que el modelo usa, no una causa.",
        badges=[("Datos sintéticos", "synthetic")],
    )
    run = _run()
    try:
        engine = cache.engine(run)
    except (ImportError, api.ScenarioContractError) as error:
        st.error(f"La corrida no se pudo cargar: {error}")
        return
    request, from_session = _request(engine)
    st.caption(
        ("Escenario de la página Escenario" if from_session else "Sin escenario: basal")
        + f" · animal {request.base_instance} · corrida {api.DEMO_RUNS[run].label}."
    )
    left, right = st.columns([3, 1])
    target = left.selectbox(
        "Salida explicada",
        list(explain.TARGETS),
        index=list(explain.TARGETS).index("log_total"),
        format_func=lambda t: explain.TARGETS[t],
        key="ng_explain_target",
    )
    seed = int(
        right.number_input("Semilla del explicador", 0, 99, 0, step=1, key="ng_explain_seed")
    )
    for text in explain.INTERPRETATION:
        st.warning(text)
    try:
        result = _cached(run, request.model_dump_json(), target, seed)
    except Exception as error:  # noqa: BLE001 - la página no muestra trazas
        st.error(f"No se pudo explicar el escenario: {type(error).__name__}.")
        return

    st.caption(
        f"GNNExplainer, {explain.DEFAULT_EPOCHS} épocas, semilla {seed}: "
        f"{result.elapsed_seconds:.2f} s (en caché por escenario, salida y semilla)."
    )
    st.subheader("Importancia por tipo de nodo")
    rows = result.by_node_type
    figure = go.Figure(
        go.Bar(
            x=[r["importancia total"] for r in rows],
            y=[NODE_TYPE_LABELS.get(r["tipo"], r["tipo"]) for r in rows],
            orientation="h",
            marker_color=[ui.NODE_COLORS.get(r["tipo"], ui.MUTED) for r in rows],
        )
    )
    figure.update_layout(height=300, margin={"l": 10, "r": 10, "t": 10, "b": 10})
    st.plotly_chart(figure, use_container_width=True, config=ui.CHART_CONFIG, key="ng_explain_bars")
    st.caption(
        "Importancia por relación: no disponible con este modelo (homo_sage no admite máscaras "
        "de aristas)."
        if not result.explanation.importance.edges
        else f"{len(result.explanation.importance.edges)} aristas con importancia."
    )

    st.subheader(f"Subgrafo de los {len(result.top_nodes)} nodos más importantes")
    records = viewer.scenario_graph(engine, request)
    sub = viewer.viewer_view(explain.subgraph_records(records, result), max_taxa=len(records.nodes))
    st.plotly_chart(
        plots.graph_figure(sub.view),
        use_container_width=True,
        config=ui.CHART_CONFIG,
        key="ng_explain_subgraph",
    )
    st.caption(
        "Las aristas son las del grafo entre esos nodos, con su trazo de evidencia: "
        + "; ".join(style.label for style in evidence_legend())
        + "."
    )
    st.dataframe(result.top_nodes, hide_index=True, key="ng_explain_top")
    with st.expander("Explicación (JSON del contrato)"):
        st.json(result.explanation.model_dump(mode="json"))


__all__ = ["render"]
