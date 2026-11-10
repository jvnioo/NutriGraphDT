"""Sintético frente a D1: qué parte del esquema se pudo reconstruir con datos reales."""

from __future__ import annotations

import streamlit as st

from nutrigraphdt.demo import cache, data, graph_comparison, plots, ui


def render() -> None:
    ui.hero(
        "Sintético frente a D1",
        "Qué parte del grafo se reconstruyó con datos reales.",
        "El grafo sintético tiene los ocho tipos de nodo y las once relaciones del esquema v1. "
        "El de D1 se reconstruyó con los datos de HoloFood y las tablas aprobadas por "
        "Investigación; solo tiene las relaciones con respaldo en esos datos.",
        badges=[("Sintético", "synthetic"), ("Datos reales · D1", "real")],
    )
    synthetic = cache.scenarios()
    d1 = cache.d1_records()
    with_targets = {row["graph_id"] for row in cache.d1_agcc()}
    real_ids = [gid for gid in data.graph_ids(d1.records) if gid in with_targets]
    left, right = st.columns(2)
    synthetic_id = left.selectbox(
        "Escenario sintético",
        data.graph_ids(synthetic),
        format_func=lambda gid: "basal" if "basal" in gid else "intervenido",
    )
    real_id = right.selectbox(
        f"Animal de D1 ({len(real_ids)} con los tres AGCC)",
        real_ids,
        format_func=lambda gid: data.instance_info(d1.records, gid)["sample_id"],
    )

    synthetic_nodes, synthetic_edges = graph_comparison.instance_counts(synthetic, synthetic_id)
    real_nodes, real_edges = graph_comparison.instance_counts(d1.records, real_id)
    relations = graph_comparison.relation_rows(synthetic_edges, real_edges)
    ui.metric_cards(
        [
            ("Tipos de nodo", f"{len(synthetic_nodes)} → {len(real_nodes)}", "sintético → D1"),
            (
                "Relaciones",
                f"{sum(1 for r in relations if r['sintético'])} → "
                f"{sum(1 for r in relations if r['D1'])}",
                "sintético → D1",
            ),
            (
                "Nodos",
                f"{sum(synthetic_nodes.values())} → {sum(real_nodes.values())}",
                "por grafo",
            ),
            (
                "Aristas",
                f"{sum(synthetic_edges.values())} → {sum(real_edges.values())}",
                "por grafo",
            ),
        ]
    )
    st.write("")
    left, right = st.columns(2)
    left.markdown("**Grafo sintético**")
    left.plotly_chart(
        plots.schema_figure(graph_comparison.synthetic_view(relations), set(synthetic_nodes)),
        config=ui.CHART_CONFIG,
        key="schema_synthetic",
    )
    right.markdown("**Grafo de D1 (datos reales)**")
    right.plotly_chart(
        plots.schema_figure(relations, set(real_nodes)),
        config=ui.CHART_CONFIG,
        key="schema_d1",
    )
    st.caption(
        "Verde: relación presente; ámbar: limitación declarada; gris punteado: fuera de D1. Los "
        "nodos grises no existen en ese grafo. Pase el cursor sobre el centro de una relación "
        "para ver su nombre y su motivo."
    )
    st.markdown("**Aristas por relación**")
    st.dataframe(relations, hide_index=True)
    st.markdown("**Nodos por tipo**")
    st.dataframe(graph_comparison.node_rows(synthetic_nodes, real_nodes), hide_index=True)
    st.caption(
        "El sintético es un escenario ilustrativo pequeño. En D1, los taxones son los géneros y "
        "los nodos residuales del animal (contrato v2 §6), y las funciones son los KO con "
        "portador entre los géneros enlazados (#175)."
        + ("" if d1.full else " Sin la descarga de D1, se usa el fixture de 6 animales.")
    )
