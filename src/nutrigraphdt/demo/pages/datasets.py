"""Datos: la fuente real D1 HoloFood y la cohorte sintética con sus escenarios."""

from __future__ import annotations

from collections import Counter

import streamlit as st

from nutrigraphdt.demo import cache, data, plots, ui


def render() -> None:
    ui.hero(
        "Datos",
        "Dos fuentes, un mismo contrato.",
        "El proyecto trabaja con datos reales de pollos (D1 HoloFood) y con una cohorte "
        "sintética generada por código. Ambas se convierten al mismo esquema de grafo.",
    )
    real, synthetic = st.tabs(["D1 HoloFood (real)", "Cohorte sintética"])
    with real:
        _real()
    with synthetic:
        _synthetic()


def _real() -> None:
    st.markdown(ui.badge("Datos reales", "real"), unsafe_allow_html=True)
    split = cache.split_summary()
    d1_run = cache.baseline_report(str(data.REPORTS_DIR / "baselines" / "d1"))["run"]
    ui.metric_cards(
        [
            ("Animales", f"{sum(split['counts'].values())}", "con metadatos, en la partición"),
            ("Corrales", f"{sum(split['groups'].values())}", "unidad de agrupación sin fuga"),
            ("Con los tres AGCC", f"{sum(d1_run['subset_sizes'].values())}", "target completo"),
            ("Taxones por grafo", "1315", "descarga completa; 439 en el fixture"),
        ]
    )
    st.markdown(
        """
**HoloFood** (Rogers et al., 2025) es el único conjunto identificado que reúne, para el mismo
animal, microbioma, AGCC, dieta y fenotipo bajo tratamientos dietarios controlados: tres
ensayos de pollos, tratamiento asignado por corral (Control, Probiótico y Fitobiótico) y muestreo
en los días 7, 21 y 35. El repositorio lo descarga de servicios públicos de EMBL-EBI con
`scripts/fetch_holofood.py` y no versiona los datos crudos. De cada animal se usan:

- la **abundancia relativa** de cada taxón (SSU rRNA de MGnify; nodos `taxon`);
- el **peso corporal** (atributo del nodo `host`) y la **dieta** (nodo `diet`);
- los **AGCC medidos** en contenido cecal (nodos `metabolite`), que son el target.

Los 59 animales con metagenoma y AGCC están desbalanceados (37 Control, 15 Probiótico, 7
Fitobiótico): alcanzan para construir y validar grafos reales, no para estimar efectos de la
dieta.
"""
    )
    built, _ = cache.d1_fixture()
    records = built.records
    ids = data.graph_ids(records)
    st.markdown(
        f"En este equipo se muestra el **fixture** de pruebas: {len(ids)} animales reales de D1 "
        "incluidos en `tests/fixtures/holofood/`."
    )
    rows = []
    for graph_id in ids:
        info = data.instance_info(records, graph_id)
        targets = data.targets_of(records, graph_id)
        rows.append(
            {
                "animal": info["sample_id"],
                "dieta": info["diet_treatment"],
                "día": info["timepoint"],
                "acetato": targets.get("acetate"),
                "propionato": targets.get("propionate"),
                "butirato": targets.get("butyrate"),
            }
        )
    st.dataframe(rows, hide_index=True)
    st.caption(
        "AGCC en mmol/kg de contenido cecal. La dieta aparece con el nombre de la API de "
        'HoloFood, que llama "Prebiotic" al tratamiento fitobiótico (extracto de uva).'
    )
    ui.note(
        "El tratamiento dietario de D1 todavía no es un atributo numérico del grafo: el nodo "
        "<code>diet</code> no tiene columnas. Es una limitación conocida (§7 del diseño GNN)."
    )


def _synthetic() -> None:
    st.markdown(ui.badge("Datos sintéticos", "synthetic"), unsafe_allow_html=True)
    st.markdown(
        "El generador produce instancias deterministas a partir de catálogos y semillas. "
        "Sirve para desarrollar y probar el flujo completo, y tiene la ruta mecanística "
        "completa (taxón → función → metabolito) que D1 todavía no tiene."
    )
    dataset = cache.scenarios()
    differences = data.scenario_differences(dataset)
    basal_id, intervened_id = data.graph_ids(dataset)
    st.subheader("Escenario de intervención")
    for row in differences:
        st.markdown(
            f"**{row['tipo']} · {row['nodo']}** — `{row['atributo']}`: "
            f"{row['basal']} → **{row['intervenido']}**"
        )
    basal = data.targets_of(dataset, basal_id)
    intervened = data.targets_of(dataset, intervened_id)
    st.plotly_chart(
        config=ui.CHART_CONFIG,
        figure_or_data=plots.bars_figure(
            [
                {"agcc": name, "basal": basal[name], "intervenido": intervened.get(name)}
                for name in basal
            ],
            category="agcc",
            values=["basal", "intervenido"],
            title="AGCC sintéticos por escenario (mmol/kg)",
        ),
    )
    ui.note(
        "El escenario intervenido es una <b>modificación manual</b> de un valor de entrada; no "
        "simula la respuesta del animal. Los AGCC sintéticos no dependen de los atributos, por "
        "eso ningún modelo puede predecirlos mejor que la media.",
        warn=True,
    )
    st.subheader("Cohorte de entrenamiento")
    cohort = cache.cohort(50)
    by_diet = Counter(instance.diet_treatment for instance in cohort.instances)
    st.markdown(
        f"`build_synthetic_cohort(50, 1)`: **{len(cohort.instances)} instancias**, "
        f"{len(cohort.nodes)} nodos y {len(cohort.edges)} aristas. Es la misma cohorte que usan "
        "los baselines sintéticos y `train_gnn.py --dataset synthetic`."
    )
    st.dataframe(
        [{"tratamiento": diet, "instancias": count} for diet, count in sorted(by_diet.items())],
        hide_index=True,
    )
