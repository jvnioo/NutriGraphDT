"""Modelos GNN: las tres variantes, su estructura y la prueba de sobreajuste."""

from __future__ import annotations

import streamlit as st

from nutrigraphdt.demo import cache, plots, ui

_DESCRIPTIONS = {
    "homo_sage": (
        "GraphSAGE homogénea",
        "Ignora los tipos: convierte el grafo en uno homogéneo y aplica la misma convolución a "
        "todas las relaciones. Es la referencia simple.",
    ),
    "hetero_sage": (
        "GraphSAGE heterogénea",
        "Una convolución distinta por relación (taxón → función no se trata igual que "
        "metabolito → huésped), sumadas por tipo de destino.",
    ),
    "hetero_gat": (
        "GAT heterogénea",
        "Como la anterior, pero con atención: el modelo aprende cuánto pesa cada vecino. Esos "
        "pesos son la base de la interpretación (fase F7).",
    ),
}


def render() -> None:
    ui.hero(
        "Modelos GNN",
        "Tres formas de leer el mismo grafo.",
        "Las tres variantes comparten la entrada, el codificador por tipo de nodo, la conexión "
        "residual, la lectura por grafo y la cabeza que predice los tres AGCC. Solo cambia cómo "
        "se pasan los mensajes entre vecinos.",
    )
    ui.steps(
        [
            (
                "Codificador",
                "Una capa lineal por tipo de nodo lleva sus atributos a 64 dimensiones.",
                "done",
            ),
            ("Mensajes", "2 capas de convolución; cada nodo combina a sus vecinos.", "done"),
            (
                "Lectura",
                "Media por tipo, concatenada por grafo; sin metabolito ni fenotipo, que "
                "son los nodos objetivo.",
                "done",
            ),
            ("Cabeza", "Un perceptrón predice acetato, propionato y butirato.", "done"),
        ]
    )
    st.write("")
    overview = cache.model_overview()
    columns = st.columns(3)
    for column, row in zip(columns, overview, strict=True):
        title, text = _DESCRIPTIONS[row["variant"]]
        column.markdown(
            f'<div class="ng-card"><div class="label">{row["variant"]}</div>'
            f'<div class="value" style="font-size:1.35rem">{title}</div>'
            f'<div class="help">{text}</div>'
            f'<div style="margin-top:.6rem"><b>{row["parameters"]:,}</b> parámetros · '
            f"{len(row['layers'][0])} → {len(row['layers'][-1])} relaciones por capa</div></div>",
            unsafe_allow_html=True,
        )
    st.caption(
        "Parámetros contados sobre la metadata sintética (8 tipos de nodo, 22 relaciones con sus "
        "inversas), con la configuración de configs/models/."
    )
    with st.expander("Relaciones que usa cada capa"):
        variant = st.selectbox("Variante", [row["variant"] for row in overview], index=1)
        row = next(r for r in overview if r["variant"] == variant)
        for layer, relations in enumerate(row["layers"], 1):
            st.markdown(f"**Capa {layer}** · {len(relations)} relaciones")
            st.code("\n".join(relations), language=None)
        ui.note(
            "En la última capa, las heterogéneas no crean convoluciones hacia metabolito y "
            "fenotipo: esos tipos no entran a la lectura, así que esas convoluciones nunca "
            "aprenderían (decisión de #111)."
        )

    st.subheader("Prueba de cordura: ¿puede aprender?")
    results = cache.overfit_results()
    if results is None:
        st.info(
            "Todavía no hay resultados locales. Ejecute `python scripts/overfit_gnn.py` "
            "(unos minutos en CPU) y recargue la página."
        )
        return
    summary = results["summary"]
    st.markdown(
        f"Cada variante se entrena {summary['epochs']} pasos sobre el **mismo lote** de "
        f"{summary['n_graphs']} grafos sintéticos. Si no pudiera llevar la pérdida a casi cero, "
        "habría un defecto de construcción. Pasarla no dice nada de generalización."
    )
    st.plotly_chart(
        config=ui.CHART_CONFIG,
        figure_or_data=plots.curves_figure(
            results["curves"],
            title="Pérdida de entrenamiento (MSE estandarizado, escala log)",
            y_title="MSE",
            log_y=True,
        ),
    )
    st.dataframe(
        [
            {
                "variante": name,
                "inicial": round(item["initial_loss"], 4),
                "final": f"{item['final_loss']:.2e}",
                "sobreajusta": "sí" if item["overfit"] else "no",
            }
            for name, item in summary["variants"].items()
        ],
        hide_index=True,
    )
