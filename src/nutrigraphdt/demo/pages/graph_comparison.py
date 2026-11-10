"""Sintético frente a D1: qué parte del grafo se pudo reconstruir con datos reales."""

from __future__ import annotations

import streamlit as st

from nutrigraphdt.demo import cache, data, plots, ui
from nutrigraphdt.demo import graph_comparison as cmp


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
    report = cache.d1_graph_report()
    d1_graphs = report["graphs"] if report else None

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
        format_func=lambda gid: _animal_label(d1.records, gid),
    )

    synthetic_nodes, synthetic_edges = cmp.instance_counts(synthetic, synthetic_id)
    real_nodes, real_edges = cmp.instance_counts(d1.records, real_id)
    relations = cmp.relation_rows(
        synthetic_edges,
        real_edges,
        synthetic_evidence=cmp.evidence_by_relation(synthetic, synthetic_id),
        real_evidence=cmp.evidence_by_relation(d1.records, real_id),
        d1_graphs=d1_graphs,
    )
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

    st.subheader("Esquema")
    left, right = st.columns(2)
    left.markdown("**Grafo sintético**")
    left.plotly_chart(
        plots.schema_figure(cmp.synthetic_view(relations), set(synthetic_nodes)),
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

    st.subheader("Instancias")
    st.markdown("**Grafo sintético**")
    st.plotly_chart(
        plots.graph_figure(data.graph_view(synthetic, synthetic_id)),
        config=ui.CHART_CONFIG,
        key="instance_synthetic",
    )
    head, control = st.columns([3, 1])
    head.markdown("**Grafo de D1 (datos reales)**")
    max_taxa = control.slider("Taxones mostrados", 5, 40, 15)
    view = data.graph_view(d1.records, real_id, max_per_type=max_taxa)
    st.plotly_chart(plots.graph_figure(view), config=ui.CHART_CONFIG, key="instance_d1")
    st.caption(
        "Columnas: tipos de nodo. El trazo y el color de una arista dicen su evidencia: el "
        "sintético solo tiene aristas generadas; D1 tiene aristas anotadas en bases curadas y "
        "medidas en el animal. Círculo vacío: nodo sin aristas. En D1 se muestran los taxones "
        "con aristas y, entre ellos, los más abundantes"
        + (f"; se ocultan {sum(view.hidden.values())} nodos." if view.hidden else ".")
    )

    st.subheader("Aristas por relación")
    st.dataframe(
        [
            {
                "relación": f"{r['origen']} → {r['relación']} → {r['destino']}",
                **{k: v for k, v in r.items() if k not in ("origen", "relación", "destino")},
            }
            for r in relations
        ],
        hide_index=True,
        height=_height(relations),
    )
    st.caption(
        "«sintético» y «D1»: aristas en las instancias elegidas. "
        + (
            f"«{_cohort(d1_graphs)}»: mínimo y máximo por grafo en toda la cohorte. "
            if d1_graphs
            else ""
        )
        + "Evidencia: estado · método · fuente de las aristas (DS-01)."
    )

    st.subheader("Nodos y atributos por tipo")
    nodes = [
        {"tipo": f"{row.pop('nombre')} ({row.pop('tipo')})", **row}
        for row in cmp.node_rows(
            synthetic_nodes,
            real_nodes,
            synthetic_features=cache.synthetic_features(),
            real_features=d1_graphs["feature_columns"] if d1_graphs else None,
            d1_graphs=d1_graphs,
        )
    ]
    st.dataframe(nodes, hide_index=True, height=_height(nodes))
    st.caption(
        "Atributos: columnas numéricas de x que recibe el modelo, con su unidad. En D1, los "
        "taxones son los géneros y los nodos residuales del animal (contrato v2 §6), las "
        "funciones son los KO con portador entre los géneros enlazados (#175) y el huésped solo "
        "lleva covariables de entrada codificadas (contrato v2 §3)."
    )

    left, right = st.columns(2)
    left.subheader("Instancia")
    left.dataframe(
        cmp.instance_rows(
            data.instance_info(synthetic, synthetic_id), data.instance_info(d1.records, real_id)
        ),
        hide_index=True,
    )
    right.subheader("AGCC objetivo (mmol/kg)")
    right.dataframe(
        cmp.target_rows(
            data.targets_of(synthetic, synthetic_id),
            data.targets_of(d1.records, real_id),
            report["agcc"] if report else None,
        ),
        hide_index=True,
    )
    right.caption(
        "El sintético es un escenario ilustrativo; sus valores no se comparan con D1 como "
        "resultado. D1: AGCC medidos en contenido cecal del animal."
    )
    if not d1.full:
        st.info("Sin la descarga de D1 se usa el fixture de 6 animales de `tests/fixtures/`.")


def _animal_label(records: object, graph_id: str) -> str:
    info = data.instance_info(records, graph_id)
    return f"{info['sample_id']} · {info['diet_treatment']} · día {info['timepoint']}"


def _height(rows: list[dict[str, object]]) -> int:
    return 35 * (len(rows) + 1) + 3


def _cohort(d1_graphs: dict[str, object]) -> str:
    return f"D1 ({d1_graphs.get('instances', '?')} grafos)"
