"""Inicio de la Web App: qué es, qué datos usa y qué corrida está activa (A88)."""

from __future__ import annotations

import streamlit as st

from nutrigraphdt.demo import cache, ui

PAGES_TABLE = [
    {
        "página": "Escenario",
        "qué hace": "Define el animal, la dieta y el aditivo",
        "actividad": "A90, A96",
    },
    {
        "página": "Resultados",
        "qué hace": "Basal frente a intervenido por AGCC",
        "actividad": "A101",
    },
    {"página": "Grafo", "qué hace": "El grafo heterogéneo de la instancia", "actividad": "A97"},
    {
        "página": "Explicación",
        "qué hace": "Subgrafo explicativo e importancias",
        "actividad": "A104",
    },
    {
        "página": "Sintético frente a D1",
        "qué hace": "Por qué la plataforma usa datos sintéticos",
        "actividad": "#296",
    },
]


def render() -> None:
    ui.hero(
        "NutriGraphDT",
        "Gemelo digital nutricional basado en grafos.",
        "Prototipo académico que predice la composición de los ácidos grasos de cadena corta "
        "(AGCC) del ciego a partir de un grafo heterogéneo de dieta, aditivo, microbioma y "
        "huésped, y compara un escenario intervenido con su basal. La plataforma trabaja con la "
        "cohorte sintética: demuestra que el flujo funciona de punta a punta, no efectos "
        "biológicos.",
        badges=[("Datos sintéticos", "synthetic")],
    )
    run = cache.active_run()
    metadata = cache.run_metadata(run)
    st.subheader("Corrida activa")
    split = metadata["n_animals"]
    ui.metric_cards(
        [
            ("Variante", str(metadata["variant"]), str(metadata["edges_arm"])),
            ("Conjunto", str(metadata["dataset_id"]), "cohorte sintética"),
            (
                "Animales",
                str(sum(split.values())),
                " · ".join(f"{k} {v}" for k, v in split.items()),
            ),
        ]
    )
    st.caption(
        f"{metadata['label']}. {metadata['description']} Se elige en `configs/platform.json` "
        "o con la variable de entorno `NUTRIGRAPHDT_RUN`. Es una corrida de demostración: sus "
        "predicciones no tienen valor científico."
    )
    st.subheader("Páginas")
    st.dataframe(PAGES_TABLE, hide_index=True)


__all__ = ["render"]
