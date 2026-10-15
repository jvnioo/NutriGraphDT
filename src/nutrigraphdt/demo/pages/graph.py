"""Explorador del grafo: qué es un grafo aquí, el sintético, un animal real y por qué difieren."""

from __future__ import annotations

from typing import Any

import streamlit as st

from nutrigraphdt.demo import cache, data, plots, ui

_TARGETS = ("Acetato", "Propionato", "Butirato")


def render() -> None:
    ui.hero(
        "Explorador del grafo",
        "Cada animal es una red.",
        "En NutriGraphDT un pollo no se describe con una fila de planilla, sino con una red: qué "
        "come, qué bacterias tiene en el intestino, qué hacen esas bacterias y qué compuestos "
        "aparecen en su ciego. Esa red es lo que la GNN aprende a leer para predecir los AGCC.",
    )
    _how_to_read()
    _synthetic()
    _real()
    _why_different()


def _how_to_read() -> None:
    ui.section(1, "Cómo leer el dibujo")
    ui.legend(
        [
            (
                "●",
                "Un <b>nodo</b> es una entidad: una bacteria, un compuesto, el animal. El color y "
                "la columna dicen de qué tipo es.",
            ),
            (
                "—",
                "Una <b>arista</b> es una relación conocida entre dos nodos, por ejemplo "
                "«sustrato alimenta a taxón».",
            ),
            (
                "○",
                "Un <b>círculo vacío</b> es un nodo sin relaciones conocidas: está en el grafo, "
                "pero no se conecta con nada.",
            ),
            (
                "⬤",
                "Un círculo <b>más grande</b> tiene más conexiones. Pase el cursor sobre un nodo "
                "para ver sus datos.",
            ),
        ]
    )
    with st.expander("Los ocho tipos de nodo"):
        st.dataframe(
            [
                {
                    "tipo": data.NODE_TYPE_LABELS[node_type],
                    "qué representa": data.NODE_TYPE_DESCRIPTIONS[node_type],
                }
                for node_type in data.NODE_TYPE_ORDER
            ],
            hide_index=True,
        )


def _synthetic() -> None:
    ui.section(
        2,
        "El grafo sintético: la red completa",
        "Lo genera el código del proyecto para probar todo el flujo con una red <b>completa</b>. "
        "Tiene la ruta que el proyecto quiere modelar: la dieta aporta sustratos, los sustratos "
        "alimentan bacterias, las bacterias realizan funciones y las funciones producen AGCC. "
        + ui.badge("Datos sintéticos", "synthetic"),
    )
    records = cache.scenarios()
    graph_id = data.graph_ids(records)[0]
    view = data.graph_view(records, graph_id, max_per_type=20)
    choice = st.radio(
        "Resaltar todo lo que conduce a…",
        ["nada", *_TARGETS],
        horizontal=True,
        key="synthetic_highlight",
    )
    highlight = None
    if choice != "nada":
        target = next(node for node in view.nodes if node["label"] == choice)
        highlight = data.upstream(view, "metabolite", target["node_id"])
    st.plotly_chart(
        plots.graph_figure(view, highlight=highlight), config=ui.CHART_CONFIG, key="g_syn"
    )
    if highlight:
        nodes, edges = highlight
        st.caption(
            f"{len(nodes) - 1} nodos y {len(edges)} relaciones llegan a {choice.lower()}: es la "
            "información que la GNN puede combinar para predecirlo."
        )
    ui.how_to_read(
        "Se lee de izquierda a derecha, como el camino del alimento: <b>dieta → sustrato → "
        "taxón → función → metabolito</b>, y a la derecha el animal y sus rasgos. Elija un AGCC "
        "arriba para iluminar en rojo los caminos que terminan en él. Todos los nodos tienen "
        "conexiones: no hay círculos vacíos."
    )


def _real() -> None:
    ui.section(
        3,
        "Un animal real (D1 HoloFood)",
        "Ahora, un pollo real del estudio HoloFood. De cada animal se midió cuánto hay de cada "
        "bacteria, los AGCC del ciego, su peso y su dieta. "
        + ui.badge("Datos reales · D1", "real"),
    )
    built, _ = cache.d1_fixture()
    records = built.records
    left, right = st.columns([2, 1])
    graph_id = left.selectbox(
        "Animal (6 animales reales incluidos en el repositorio)",
        data.graph_ids(records),
        format_func=lambda gid: _animal_label(records, gid),
    )
    taxa = right.slider("Taxones a mostrar (los más abundantes)", 5, 40, 15)
    view = data.graph_view(records, graph_id, max_per_type=taxa)
    st.plotly_chart(plots.graph_figure(view, height=560), config=ui.CHART_CONFIG, key="g_d1")
    nodes, _ = data.type_counts(records, graph_id)
    ui.how_to_read(
        f"Casi todo son <b>círculos vacíos</b>: este animal tiene {nodes.get('taxon', 0)} "
        "taxones y ninguno se conecta con otro nodo. Las únicas líneas unen cada metabolito "
        "medido con el animal, y la dieta también queda suelta. Se dibujan los taxones más "
        "abundantes; el resto está en el grafo, igual de desconectado."
    )
    targets = data.targets_of(records, graph_id)
    with st.expander("AGCC medidos en este animal"):
        st.dataframe(
            [
                {"metabolito": name, "mmol/kg": value}
                for name, value in targets.items()
                if name in ("acetate", "propionate", "butyrate")
            ],
            hide_index=True,
        )


def _why_different() -> None:
    ui.section(
        4,
        "¿Por qué son tan distintos?",
        "Los dos grafos siguen el mismo esquema, pero no contienen la misma información.",
    )
    synthetic = cache.scenarios()
    built, _ = cache.d1_fixture()
    comparison = data.compare_graphs(
        synthetic, data.graph_ids(synthetic)[0], built.records, data.graph_ids(built.records)[0]
    )
    left, right = st.columns(2)
    left.markdown("**Nodos por tipo**: cuántos tienen alguna conexión, de cuántos hay")
    left.dataframe(
        [
            {
                "tipo": row["tipo"],
                "sintético": f"{row['sintético conectados']} de {row['sintético']}",
                "D1": f"{row['D1 conectados']} de {row['D1']}",
            }
            for row in comparison["nodes"]
        ],
        hide_index=True,
    )
    right.markdown("**Relaciones**: aristas de cada tipo")
    right.dataframe(comparison["relations"], hide_index=True)
    totals = {
        source: sum(row[source] for row in comparison["relations"])
        for source in ("sintético", "D1")
    }
    st.markdown(
        f"""
- **Lo que se mide no es lo que se sabe.** HoloFood mide *cuánto* hay de cada bacteria y de cada
  AGCC, pero no *qué hace* cada bacteria ni *de qué se alimenta*. Esas relaciones vienen de bases
  de anotación funcional, y su incorporación (taxón → función, tarea S-03) está pendiente con
  Investigación. Por eso este animal de D1 tiene {totals["D1"]} relaciones y el sintético
  {totals["sintético"]}.
- **Para qué sirve el sintético.** Inventa relaciones con una estructura razonable para probar
  todo el flujo de punta a punta. No describe biología real.
- **Qué significa para la GNN.** Una GNN aprende pasando información entre vecinos. En D1 las
  bacterias no tienen vecinos, así que la GNN las ve casi como una lista, igual que un modelo de
  tabla. La ventaja de leer la red solo se puede medir en el sintético, o en D1 cuando exista la
  anotación.
- **Escala.** Un animal de D1 tiene muchos más taxones (1315 en la descarga completa, 439 en esta
  muestra) y muchas menos relaciones.
"""
    )
    ui.note(
        "En resumen: el <b>sintético</b> muestra lo que el modelo podría aprovechar con una red "
        "completa; <b>D1</b> muestra los datos reales que hay hoy. Cerrar esa brecha depende de "
        "la anotación taxón → función."
    )


def _animal_label(records: Any, graph_id: str) -> str:
    info = data.instance_info(records, graph_id)
    return f"{info['sample_id']} · dieta {info['diet_treatment']} · día {info['timepoint']}"
