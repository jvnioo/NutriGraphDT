"""Explorador del grafo: qué es un grafo aquí, cómo lo lee la GNN y un animal real de D1."""

from __future__ import annotations

from typing import Any

import streamlit as st

from nutrigraphdt.demo import cache, data, plots, ui

_TARGETS = ("Acetato", "Propionato", "Butirato")
_GNN_LAYERS = 2


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
    _gnn_reading()
    graph_id = _real()
    _why_different(graph_id)


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


def _synthetic_view() -> data.GraphView:
    records = cache.scenarios()
    return data.graph_view(records, data.graph_ids(records)[0], max_per_type=20)


def _synthetic() -> None:
    ui.section(
        2,
        "El grafo sintético: la red completa",
        "Lo genera el código del proyecto para probar todo el flujo con una red <b>completa</b>, "
        "con la ruta que el proyecto quiere modelar. " + ui.badge("Datos sintéticos", "synthetic"),
    )
    view = _synthetic_view()
    choice = st.radio(
        "Resaltar todo lo que conduce a…",
        ["nada", *_TARGETS],
        horizontal=True,
        key="synthetic_highlight",
    )
    focus: dict[tuple[str, str], int] = {}
    edges: set[int] = set()
    if choice != "nada":
        target = next(node for node in view.nodes if node["label"] == choice)
        nodes, edges = data.upstream(view, "metabolite", target["node_id"])
        focus = {key: 1 for key in nodes}
    st.plotly_chart(
        plots.graph_figure(view, focus=focus, focus_edges=edges),
        config=ui.CHART_CONFIG,
        key="g_syn",
    )
    if choice == "nada":
        ui.takeaway(
            "Se lee de izquierda a derecha, como el camino del alimento: dieta → sustrato → "
            "bacteria → función → metabolito. Elija un AGCC para ver de dónde viene."
        )
    else:
        ui.takeaway(
            f"{len(focus) - 1} nodos y {len(edges)} relaciones llegan a {choice.lower()}: desde "
            "la dieta, pasando por las bacterias y sus funciones."
        )
    ui.how_to_read(
        "Cada columna es un tipo de nodo, en el orden en que el alimento se transforma: la dieta "
        "aporta sustratos (fibras, almidón), los sustratos alimentan bacterias (taxones), las "
        "bacterias realizan funciones metabólicas y las funciones producen metabolitos como los "
        "AGCC. A la derecha están el animal y sus rasgos productivos. Al elegir un AGCC, los "
        "caminos que terminan en él se iluminan en rojo. Todos los nodos tienen conexiones: no "
        "hay círculos vacíos."
    )


def _gnn_reading() -> None:
    ui.section(
        3,
        "Cómo lee la GNN este grafo",
        "La GNN no mira el grafo completo de una vez. En cada <b>capa</b>, cada nodo combina su "
        "información con la de sus vecinos directos; en la capa siguiente, esos vecinos ya "
        f"traen lo de los suyos. El modelo del proyecto usa {_GNN_LAYERS} capas, así que cada "
        f"nodo reúne información de hasta {_GNN_LAYERS} saltos de distancia.",
    )
    view = _synthetic_view()
    options = {
        f"{data.NODE_TYPE_LABELS[n['node_type']]} · {n['label']}": (n["node_type"], n["node_id"])
        for node_type in ("taxon", "function", "metabolite", "host", "substrate")
        for n in view.nodes
        if n["node_type"] == node_type
    }
    default = next((i for i, label in enumerate(options) if label.endswith("Butirato")), 0)
    left, right = st.columns([3, 2])
    choice = left.selectbox("Mirar desde el nodo…", list(options), index=default)
    layers = right.radio(
        "Capas de la GNN",
        [1, 2],
        index=1,
        horizontal=True,
        format_func=lambda n: f"{n} capa" if n == 1 else f"{n} capas",
    )
    node_type, node_id = options[choice]
    distance, edges = data.neighborhood(view, node_type, node_id, layers)
    st.plotly_chart(
        plots.graph_figure(view, focus=distance, focus_edges=edges),
        config=ui.CHART_CONFIG,
        key="g_hops",
    )
    first = sum(1 for d in distance.values() if d == 1)
    second = sum(1 for d in distance.values() if d == 2)
    detail = f"{first} a un salto" + (f" y {second} a dos saltos" if layers == 2 else "")
    ui.takeaway(
        f"Con {layers} {'capa' if layers == 1 else 'capas'}, «{choice.split(' · ')[1]}» combina "
        f"información de {len(distance) - 1} nodos ({detail}). En un grafo bien conectado, pocas "
        "capas alcanzan casi toda la red."
    )
    ui.how_to_read(
        "El nodo elegido lleva un borde oscuro. Las líneas <b>rojas</b> unen a sus vecinos "
        "directos (lo que aprende en la primera capa) y las <b>naranjas</b> a los vecinos de sus "
        "vecinos (la segunda capa). Lo atenuado no llega a ese nodo. La información viaja en "
        "ambos sentidos de cada relación, porque el modelo agrega una arista inversa por cada "
        "una. Al final, la GNN resume los nodos de cada tipo en un solo vector (salvo "
        "metabolitos y fenotipos, que son lo que se quiere predecir) y con eso predice los "
        "tres AGCC."
    )


def _real() -> str:
    source = cache.d1_records()
    records = source.records
    agcc = cache.d1_agcc()
    with_targets = {row["graph_id"] for row in agcc}
    animals = [gid for gid in data.graph_ids(records) if gid in with_targets] or data.graph_ids(
        records
    )
    origin = (
        f"Descarga completa de HoloFood: {len(data.graph_ids(records))} animales con microbiota, "
        f"{len(with_targets)} de ellos con los tres AGCC medidos (los que se muestran)."
        if source.full
        else f"Muestra de prueba de {len(animals)} animales reales incluida en el repositorio "
        "(la descarga completa no está en este equipo; ver scripts/fetch_holofood.py)."
    )
    ui.section(
        4,
        "Un animal real (D1 HoloFood)",
        "Ahora, un pollo real del estudio HoloFood. De cada animal se midió cuánto hay de cada "
        "bacteria, los AGCC del ciego, su peso y su dieta. "
        + ui.badge("Datos reales · D1", "real"),
    )
    st.caption(origin)
    left, right = st.columns([2, 1])
    graph_id = left.selectbox(
        "Animal", animals, format_func=lambda gid: _animal_label(records, gid)
    )
    taxa = right.slider("Taxones a mostrar (los más abundantes)", 5, 40, 15)
    view = data.graph_view(records, graph_id, max_per_type=taxa)
    show_gnn = st.toggle("Ver qué ve la GNN desde el taxón más abundante", value=False)
    focus: dict[tuple[str, str], int] = {}
    edges: set[int] = set()
    if show_gnn:
        top = next(n for n in view.nodes if n["node_type"] == "taxon")
        focus, edges = data.neighborhood(view, "taxon", top["node_id"], _GNN_LAYERS)
    st.plotly_chart(
        plots.graph_figure(view, focus=focus, focus_edges=edges),
        config=ui.CHART_CONFIG,
        key="g_d1",
    )
    nodes, _ = data.type_counts(records, graph_id)
    if show_gnn:
        ui.takeaway(
            "Desde un taxón, la GNN no ve a nadie: sin aristas, con 1 o con 10 capas, cada "
            "bacteria solo aporta su propia abundancia."
        )
    else:
        ui.takeaway(
            f"Casi todo son círculos vacíos: este animal tiene {nodes.get('taxon', 0)} "
            "taxones y ninguno se conecta con otro nodo."
        )
    ui.how_to_read(
        "Las únicas líneas unen cada metabolito medido con el animal; la dieta y todas las "
        "bacterias quedan sueltas. Se dibujan los taxones más abundantes; el resto está en el "
        "grafo, igual de desconectado. La sección siguiente explica por qué."
    )
    if graph_id in with_targets and len(agcc) > 1:
        st.markdown("**Sus AGCC frente a los demás animales**")
        st.plotly_chart(
            plots.animal_vs_cohort_figure(agcc, selected=graph_id),
            config=ui.CHART_CONFIG,
            key="g_agcc",
        )
        ui.takeaway(
            f"Esto es lo que la GNN tiene que predecir. Entre los {len(agcc)} animales, los "
            "AGCC varían mucho, y el acetato está en una escala mayor que los otros dos."
        )
    return graph_id


def _why_different(graph_id: str) -> None:
    ui.section(
        5,
        "¿Por qué son tan distintos?",
        "Los dos grafos siguen el mismo esquema, pero no contienen la misma información.",
    )
    synthetic = cache.scenarios()
    records = cache.d1_records().records
    comparison = data.compare_graphs(synthetic, data.graph_ids(synthetic)[0], records, graph_id)
    totals = {
        source: sum(row[source] for row in comparison["relations"])
        for source in ("sintético", "D1")
    }
    taxa = next(row for row in comparison["nodes"] if row["tipo"] == "Taxón")
    ui.takeaway(
        f"HoloFood midió <b>cuánto</b> hay de cada bacteria, pero no <b>qué hace</b> cada una: "
        f"por eso este animal tiene {taxa['D1 conectados']} de {taxa['D1']} taxones conectados "
        f"y {totals['D1']} relaciones, frente a {totals['sintético']} del sintético."
    )
    left, right = st.columns(2)
    left.markdown("**Nodos por tipo**: con alguna conexión, de cuántos hay")
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
    with st.expander("Qué significa esto para el proyecto", expanded=True):
        st.markdown(
            """
- **De dónde vendrían las relaciones.** Qué hace cada bacteria se obtiene de bases de anotación
  funcional; incorporarla (taxón → función, tarea S-03) está pendiente con Investigación.
- **Para qué sirve el sintético.** Inventa relaciones con una estructura razonable para probar
  todo el flujo de punta a punta. No describe biología real.
- **Qué significa para la GNN.** Como se vio en la sección 3, la GNN aprende pasando información
  entre vecinos. En D1 las bacterias no tienen vecinos, así que la GNN las ve casi como una
  lista, igual que un modelo de tabla. La ventaja de leer la red solo se puede medir en el
  sintético, o en D1 cuando exista la anotación.
"""
        )


def _animal_label(records: Any, graph_id: str) -> str:
    info = data.instance_info(records, graph_id)
    return f"{info['sample_id']} · dieta {info['diet_treatment']} · día {info['timepoint']}"
