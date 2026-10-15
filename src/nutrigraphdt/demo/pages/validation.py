"""Validación: reglas de integridad y compuerta antes de entregar un grafo al modelo."""

from __future__ import annotations

import streamlit as st

from nutrigraphdt.demo import cache, ui


def render() -> None:
    ui.hero(
        "Validación",
        "Ningún grafo llega al modelo sin revisar.",
        "Antes de entrenar, cada grafo pasa por las reglas de integridad del proyecto: "
        "instancia, nodos, aristas, salidas, conectividad y tensores. Un hallazgo ERROR bloquea "
        "el grafo; una ADVERTENCIA se informa y el grafo sigue.",
    )
    catalog = cache.rule_catalog()
    synthetic = cache.synthetic_validation()
    real = cache.d1_validation()
    families: dict[str, int] = {}
    for rule_id in catalog:
        family = rule_id.split("-")[0]
        families[family] = families.get(family, 0) + 1
    ui.metric_cards(
        [
            ("Reglas", f"{len(catalog)}", f"versión {real['rules_version']}"),
            ("Familias", f"{len(families)}", " · ".join(sorted(families))),
            (
                "Sintético",
                f"{synthetic['deliverable']}/{synthetic['graphs']}",
                "grafos entregables, sin hallazgos",
            ),
            ("D1 (fixture)", f"{real['deliverable']}/{real['graphs']}", "grafos entregables"),
        ]
    )
    st.write("")
    source = st.radio(
        "Reporte", ["D1 HoloFood (fixture)", "Sintético (escenarios)"], horizontal=True
    )
    report = real if source.startswith("D1") else synthetic
    summary = report["summary"]
    st.markdown(
        f"**Estado:** `{report['status']}` · ERROR **{summary.get('ERROR', 0)}** · "
        f"ADVERTENCIA **{summary.get('ADVERTENCIA', 0)}** · INFO **{summary.get('INFO', 0)}** · "
        f"{len(report['evaluated'])} reglas evaluadas"
    )
    if report["rules"]:
        st.dataframe(report["rules"], hide_index=True)
    else:
        st.success("Ninguna regla encontró hallazgos.")
    if source.startswith("D1"):
        ui.note(
            "Las advertencias de D1 son esperadas y están documentadas: taxones sin aristas "
            "(CON-01, CON-03), porque falta la anotación taxón → función; atributos ausentes en "
            "la fuente (NOD-08); y tipos de nodo que D1 no tiene, como sustrato o función "
            "(NOD-12, que en datos reales es advertencia). Ninguna bloquea el grafo."
        )
    with st.expander(f"Catálogo completo ({len(catalog)} reglas)"):
        st.dataframe(
            [{"regla": rule_id, **entry} for rule_id, entry in catalog.items()],
            hide_index=True,
        )
