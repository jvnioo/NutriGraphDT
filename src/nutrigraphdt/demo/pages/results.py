"""Página Resultados: AGCC basal frente a intervenido, métricas del modelo y exportación (A101).

Muestra el último resultado guardado en la sesión (página Escenario). Las cifras del gráfico son
las del JSON de A96; las del panel, las de los archivos registrados de la corrida.
"""

from __future__ import annotations

import streamlit as st

from nutrigraphdt import api
from nutrigraphdt.demo import cache, results, service, state, ui


def render() -> None:
    ui.hero(
        "Resultados",
        "Basal frente a intervenido, por AGCC.",
        "Las dos barras son predicciones del mismo modelo para el mismo animal: su diferencia "
        "describe al modelo, no un efecto de la intervención.",
        badges=[("Datos sintéticos", "synthetic")],
    )
    result = state.result()
    if result is None:
        st.info("Aún no hay resultado: simule un escenario en la página Escenario.")
        return
    comparison = result.comparison
    declared = ", ".join(
        f"{i.variable} = {i.value}" for i in comparison.intervened.request.intervention
    )
    st.caption(
        f"Animal {comparison.intervened.request.base_instance} · intervención: "
        f"{declared or 'ninguna (basal)'} · corrida {api.DEMO_RUNS[result.run].label}."
    )
    st.info(api.CAUSAL_WARNING)
    if comparison.status != api.ESTIMABLE:
        st.warning(
            "No estimable: al menos una de las dos predicciones cae fuera del soporte empírico "
            "de la corrida; no se informan cifras de ese lado.\n\n"
            + "\n".join(f"- {r}" for r in comparison.reasons)
        )

    left, right = st.columns([3, 1])
    left.plotly_chart(
        results.results_figure(result),
        use_container_width=True,
        config=ui.CHART_CONFIG,
        key="ng_results_fractions",
    )
    right.plotly_chart(
        results.results_figure(result, ("log_total",)),
        use_container_width=True,
        config=ui.CHART_CONFIG,
        key="ng_results_total",
    )
    if results.has_intervals(result):
        first = next(r for r in results.chart_rows(result) if r["lower"] is not None)
        note = getattr(cache.engine(result.run), "calibration_note", None)
        st.caption(
            results.interval_caption(first["interval_method"], first["interval_level"], note)
        )
    else:
        st.caption(results.NO_INTERVAL)
    if comparison.differences:
        st.dataframe(
            [
                {
                    "cantidad": results.LABELS[d.quantity],
                    "basal": round(d.basal, 4),
                    "intervenido": round(d.intervened, 4),
                    "diferencia": round(d.difference, 4),
                    "unidad": d.difference_unit,
                }
                for d in comparison.differences
            ],
            hide_index=True,
            key="ng_results_diff",
        )

    _panel(result.run)

    st.subheader("Exportar")
    left, right = st.columns(2)
    left.download_button(
        "Descargar JSON",
        service.to_json(result),
        file_name="nutrigraphdt-resultado.json",
        mime="application/json",
        key="ng_export_json",
    )
    right.download_button(
        "Descargar CSV",
        results.to_csv(result),
        file_name="nutrigraphdt-resultado.csv",
        mime="text/csv",
        key="ng_export_csv",
    )
    st.caption(
        f"Contrato v{result.contract_version} · corrida `{result.run_id}` · commit "
        f"`{(result.commit or 'sin registrar')[:12]}` · {result.data_label}."
    )


def _panel(run: str) -> None:
    run_dir = api.DEMO_RUNS[run].run_dir
    summary = results.training_summary(run_dir)
    st.subheader("Calidad del modelo")
    for warning in results.PANEL_WARNINGS:
        st.warning(warning)
    terms = ", ".join(summary["constraint_terms"]) or "ninguna"
    st.caption(
        f"Corrida `{summary['run_id']}` ({summary['variant']}); restricciones en el "
        f"entrenamiento: {terms}; λ = {summary['constraint_lambda']:g}. Métricas del test del "
        f"fold ({summary['n_test']} animales), leídas de `metrics.csv`."
    )
    st.dataframe(results.metric_rows(run_dir), hide_index=True, key="ng_panel_metrics")
    st.markdown("**Tasa de violación de restricciones D-06 (A73), en las predicciones de test**")
    st.dataframe(results.violation_rows(run_dir), hide_index=True, key="ng_panel_violations")


__all__ = ["render"]
