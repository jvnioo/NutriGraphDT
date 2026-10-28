"""Resultado de los grafos de D1: construcción, integración, validación y contratos (A39)."""

from __future__ import annotations

import streamlit as st

from nutrigraphdt.demo import cache, data, plots, ui


def render() -> None:
    ui.hero(
        "Grafos de D1",
        "Resultado de construir y validar los grafos reales.",
        "Resumen de scripts/build_graph.py sobre la descarga completa de D1 HoloFood: un grafo "
        "por animal con metagenoma cecal, validado con las reglas de integridad y los contratos "
        "de nodos y aristas.",
        badges=[("Datos reales · D1", "real")],
    )
    report = cache.d1_graph_report()
    if report is None:
        st.info(
            "No hay resumen de D1. Genérelo con `python scripts/fetch_holofood.py`, "
            "`python scripts/build_graph.py` y `python scripts/summarize_d1_graphs.py`."
        )
        return
    graphs = report["graphs"]
    summary = report["summary"]
    contracts = report["contracts"]
    ui.metric_cards(
        [
            ("Grafos construidos", f"{graphs['instances']}", "un grafo por animal"),
            ("Entregables", f"{report['deliverable']}", "sin hallazgos ERROR"),
            (
                "Hallazgos",
                f"{summary.get('ERROR', 0)} · {summary.get('ADVERTENCIA', 0)}",
                "ERROR · ADVERTENCIA",
            ),
            (
                "Contratos",
                f"{contracts['invalid_nodes'] + contracts['invalid_edges']} inválidos",
                f"{contracts['checked_nodes']:,} nodos y {contracts['checked_edges']} aristas",
            ),
        ]
    )
    st.write("")
    left, right = st.columns(2)
    left.markdown("**Nodos por tipo** (por grafo y total)")
    left.dataframe(
        [
            {
                "tipo": data.NODE_TYPE_LABELS.get(node_type, node_type),
                "mín": entry["min"],
                "máx": entry["max"],
                "total": entry["total"],
            }
            for node_type, entry in graphs["nodes_per_type"].items()
        ],
        hide_index=True,
    )
    right.markdown("**Aristas por relación** (por grafo y total)")
    right.dataframe(
        [
            {
                "relación": data.relation_text(*key.split("|")),
                "mín": entry["min"],
                "máx": entry["max"],
                "total": entry["total"],
            }
            for key, entry in graphs["edges_per_relation"].items()
        ],
        hide_index=True,
    )
    integration = report["integration"]
    right.markdown("**Integración de fuentes**")
    right.dataframe(
        [
            {
                "concepto": "Animales con contexto (metadatos)",
                "valor": str(integration["instances_with_context"]),
            },
            {"concepto": "AGCC con valor asignados", "valor": str(integration["targets"])},
            {
                "concepto": "Columnas de atributos",
                "valor": ", ".join(
                    f"{data.NODE_TYPE_LABELS.get(t, t)}: {', '.join(c)}"
                    for t, c in graphs["feature_columns"].items()
                    if c
                ),
            },
        ],
        hide_index=True,
    )

    st.markdown(
        f"**Validación** (reglas {report['rules_version']}, {report['evaluated']} evaluadas)"
    )
    st.dataframe(report["rules"], hide_index=True)

    agcc = report.get("agcc")
    if agcc:
        count = agcc["acetate"]["n"]
        st.markdown(f"**AGCC medidos** ({count} animales con acetato, propionato y butirato)")
        st.plotly_chart(plots.agcc_distribution_figure(agcc), config=ui.CHART_CONFIG, key="d1_agcc")
