"""Baselines (actividad 40): resultados sobre la cohorte sintética."""

from __future__ import annotations

import streamlit as st

from nutrigraphdt.demo import cache, data, plots, ui

_METRICS = {"RMSE": "rmse", "MAE": "mae", "R²": "r2"}
_GNN = frozenset({"homo_sage", "hetero_sage", "hetero_gat"})


def render() -> None:
    ui.hero(
        "Baselines",
        "Modelos de referencia (A40).",
        "Cinco modelos tabulares sobre la cohorte sintética, con la partición de A40-1 y "
        "validación cruzada agrupada dentro de entrenamiento.",
        badges=[("Datos sintéticos", "synthetic")],
    )
    report = cache.baseline_report(str(data.REPORTS_DIR / "baselines"))
    run = report["run"]
    sizes = run["subset_sizes"]
    ui.metric_cards(
        [
            ("Animales", f"{sum(sizes.values())}", "cohorte sintética"),
            (
                "Partición",
                f"{sizes['train']} · {sizes['val']} · {sizes['test']}",
                "entrenamiento · validación · prueba",
            ),
            ("Atributos", f"{run['n_features']}", "columnas tabulares"),
            ("Modelos", "5", "media, 2 lineales, 2 de árboles"),
        ]
    )
    st.write("")
    left, right = st.columns(2)
    subset = left.radio(
        "Conjunto",
        ["test", "val"],
        horizontal=True,
        format_func=lambda s: "prueba (test)" if s == "test" else "validación (val)",
    )
    metric = right.radio("Métrica", list(_METRICS), horizontal=True)
    rmse = data.baseline_table(report["rows"], "rmse", subset)
    reference = next(row["promedio"] for row in rmse if row["clave"] == "dummy_mean")
    st.plotly_chart(
        plots.versus_mean_figure(
            rmse,
            value="promedio",
            reference=reference,
            title=f"RMSE promedio de los tres AGCC en {subset} (mmol/kg)",
        ),
        config=ui.CHART_CONFIG,
    )
    rows = data.baseline_table(report["rows"], _METRICS[metric], subset)
    st.markdown(f"**{metric} por AGCC en {subset}**")
    st.dataframe(
        [
            {
                "modelo": row["modelo"],
                "acetato": round(row["acetato"], 3),
                "propionato": round(row["propionato"], 3),
                "butirato": round(row["butirato"], 3),
                "promedio": round(row["promedio"], 3),
            }
            for row in rows
        ],
        hide_index=True,
    )
    st.caption(
        "En el generador sintético los AGCC no dependen de los atributos tabulares: estos "
        "resultados verifican el flujo (partición, validación cruzada y métricas), no capacidad "
        "predictiva."
    )
    _versus_gnn(report["rows"], subset, metric)


def _versus_gnn(baseline_rows: list[dict[str, str]], subset: str, metric: str) -> None:
    gnn_rows = cache.gnn_synthetic_rows()
    if gnn_rows is None:
        return
    st.divider()
    st.subheader("Baselines frente a GNN sobre el grafo sintético")
    st.caption(
        "Mismos animales y misma partición (semilla 42, 30 · 10 · 10). Las GNN reciben el grafo "
        "de cada animal; los baselines, su tabla de atributos. Fuente: reports/gnn/synthetic/."
    )
    rmse = data.baseline_table(baseline_rows, "rmse", subset) + data.baseline_table(
        gnn_rows, "rmse", subset
    )
    reference = next(row["promedio"] for row in rmse if row["clave"] == "dummy_mean")
    st.plotly_chart(
        plots.versus_mean_figure(
            rmse,
            value="promedio",
            reference=reference,
            title=f"RMSE promedio de los tres AGCC en {subset} (mmol/kg)",
            height=380,
        ),
        config=ui.CHART_CONFIG,
        key="versus_gnn",
    )
    rows = data.baseline_table(baseline_rows, _METRICS[metric], subset) + data.baseline_table(
        gnn_rows, _METRICS[metric], subset
    )
    st.markdown(f"**{metric} por AGCC en {subset}: baselines y GNN**")
    st.dataframe(
        [
            {
                "modelo": row["modelo"],
                "tipo": "GNN (grafo)" if row["clave"] in _GNN else "baseline (tabla)",
                "acetato": round(row["acetato"], 3),
                "propionato": round(row["propionato"], 3),
                "butirato": round(row["butirato"], 3),
                "promedio": round(row["promedio"], 3),
            }
            for row in rows
        ],
        hide_index=True,
    )
    st.caption(
        "Como los AGCC sintéticos no dependen de las entradas, las diferencias pequeñas frente a "
        "la media no son interpretables ni permiten afirmar que un modelo supere a otro."
    )
