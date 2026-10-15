"""Resumen: qué es NutriGraphDT, qué está hecho y qué falta."""

from __future__ import annotations

import streamlit as st

from nutrigraphdt.demo import cache, data, ui


def render() -> None:
    ui.hero(
        "NutriGraphDT · Avance del proyecto",
        "Un gemelo digital nutricional sobre grafos.",
        "Cada animal es un grafo heterogéneo que une dieta, aditivos, sustratos, microbiota, "
        "funciones, metabolitos, huésped y fenotipo. Una red neuronal de grafos (GNN) aprende "
        "a predecir los ácidos grasos de cadena corta (AGCC: acetato, propionato y butirato) "
        "del contenido cecal. Esta demo recorre lo construido usando el código y los "
        "artefactos reales del repositorio.",
        badges=[("Prototipo académico", "synthetic"), ("Datos reales: D1 HoloFood", "real")],
    )

    split = cache.split_summary()
    d1_baselines = cache.baseline_report(str(data.REPORTS_DIR / "baselines" / "d1"))
    with_targets = sum(d1_baselines["run"]["subset_sizes"].values())
    snapshot = data.progress_snapshot()
    issues = snapshot["issues"] if snapshot else []
    closed = sum(issue["state"] == "closed" for issue in issues)
    ui.metric_cards(
        [
            ("Animales en D1", f"{sum(split['counts'].values())}", "partición canónica 2.0.0"),
            ("Con los tres AGCC", f"{with_targets}", "muestras con target completo"),
            ("Tipos de nodo", f"{len(data.NODE_TYPE_ORDER)}", "11 relaciones en el esquema v1"),
            ("Variantes GNN", "3", "homo_sage · hetero_sage · hetero_gat"),
        ]
    )
    st.write("")
    if snapshot:
        ui.metric_cards(
            [
                ("Tareas cerradas", f"{closed} / {len(issues)}", "Issues del tablero Scrumban"),
                ("PR fusionados", f"{snapshot['merged_pull_requests']}", "integrados a main"),
                ("Tests", f"{snapshot['tests_collected']}", "checks locales, sin CI de pago"),
                ("Costo", "$0", "solo herramientas libres"),
            ]
        )

    st.subheader("El flujo, de punta a punta")
    ui.steps(
        [
            ("Datos", "D1 HoloFood real y cohorte sintética con escenarios.", "done"),
            ("Grafo", "Un grafo heterogéneo por animal (esquema v1).", "done"),
            ("Validación", "56 reglas de integridad y compuerta de entrega.", "done"),
            ("Partición", "Sin fuga: por corral en D1, train/val/test.", "done"),
            ("Baselines", "5 modelos tabulares como piso de comparación.", "done"),
            ("GNN", "3 variantes con interfaz común y fábrica.", "done"),
            ("Entrenamiento", "Bucle, escalado, trazabilidad y script único.", "done"),
            ("Evaluación", "GNN en D1 y comparación con baselines (A45).", "pending"),
        ]
    )

    st.subheader("Qué muestra cada página")
    st.markdown(
        """
- **Datos**: la fuente real D1 HoloFood y la cohorte sintética, con su escenario de intervención.
- **Explorador del grafo**: una instancia como grafo heterogéneo, nodo por nodo.
- **Validación**: las reglas de integridad aplicadas a los grafos sintéticos y reales.
- **Partición y baselines**: la partición sin fuga y el piso de comparación en D1.
- **Modelos GNN**: las tres variantes, su estructura y la prueba de sobreajuste.
- **Entrenamiento**: corridas registradas y un entrenamiento en vivo (CPU o GPU).
- **Proceso**: tareas por actividad, revisiones y política de costo cero.
"""
    )
    ui.note(
        "<b>Qué no muestra esta demo.</b> Todavía no hay resultados de la GNN en D1 ni una tabla "
        "GNN vs. baselines (A45-3 a A45-8, en curso). Los números de la cohorte sintética "
        "verifican que el flujo funciona, no capacidad predictiva, y nada de lo mostrado es una "
        "conclusión biológica.",
        warn=True,
    )
