"""Partición sin fuga y baselines tabulares: el piso que la GNN tiene que superar."""

from __future__ import annotations

import streamlit as st

from nutrigraphdt.demo import cache, data, plots, ui

_METRICS = {"RMSE": "rmse", "MAE": "mae", "R²": "r2"}


def render() -> None:
    ui.hero(
        "Partición y baselines",
        "Primero, un piso honesto.",
        "Para saber si la GNN aporta algo, se compara con cinco modelos tabulares entrenados "
        "sobre la misma partición y el mismo target. Todo lo que se ajusta a los datos se ajusta "
        "solo con train.",
    )
    split = cache.split_summary()
    st.subheader("Partición de D1 (A45-1)")
    ui.metric_cards(
        [
            (name, f"{split['counts'][name]}", f"{split['groups'][name]} corrales")
            for name in ("train", "val", "test")
        ]
        + [("Semilla", f"{split['seed']}", f"versión {split['version']}")]
    )
    ui.note(
        f"La partición agrupa por <b>{split['group_key']}</b> (corral) y estratifica por "
        f"<b>{split['stratify_key']}</b>: los animales de un mismo corral comparten ambiente, así "
        "que nunca quedan repartidos entre train y test. <code>test</code> no se usa para "
        "elegir hiperparámetros ni para detener el entrenamiento."
    )

    st.subheader("Baselines")
    left, middle, right = st.columns(3)
    dataset = left.radio("Datos", ["D1 HoloFood", "Sintético"], horizontal=True)
    metric_label = middle.radio("Métrica", list(_METRICS), horizontal=True)
    subset = right.radio("Subconjunto", ["test", "val"], horizontal=True)
    directory = data.REPORTS_DIR / "baselines" / ("d1" if dataset == "D1 HoloFood" else "")
    report = cache.baseline_report(str(directory))
    rows = data.baseline_table(report["rows"], _METRICS[metric_label], subset)
    st.markdown(
        ui.badge("Real · D1", "real")
        if dataset == "D1 HoloFood"
        else ui.badge("Sintético", "synthetic"),
        unsafe_allow_html=True,
    )
    st.plotly_chart(
        config=ui.CHART_CONFIG,
        figure_or_data=plots.bars_figure(
            rows,
            category="modelo",
            values=["acetato", "propionato", "butirato", "promedio"],
            title=f"{metric_label} en {subset} por AGCC",
        ),
    )
    st.dataframe(rows, hide_index=True)

    run = report["run"]
    sizes = run["subset_sizes"]
    st.markdown(
        f"**Muestras:** {sizes['train']} train · {sizes['val']} val · {sizes['test']} test · "
        f"**validación cruzada:** {run.get('cv_folds', '—')} folds agrupados sobre train · "
        f"**atributos:** {run['n_features']}"
    )
    with st.expander("Hiperparámetros elegidos por validación cruzada"):
        st.json(run["best_params"])
    if dataset == "D1 HoloFood":
        verification = run.get("target_verification", {})
        ui.note(
            f"Las {verification.get('verified_samples', '?')} muestras y sus valores de AGCC "
            "coinciden con el target de la GNN (<code>add_graph_target</code>), así que la "
            "comparación futura usa exactamente el mismo problema."
        )
        ui.note(
            "<b>Cautela.</b> <code>val</code> tiene 7 animales en 5 corrales: sus métricas "
            "varían mucho, y el R² promedio de <code>val</code> es negativo en todos los modelos. "
            f"<code>ridge</code> elige <code>alpha = 1000</code>, el borde de su grilla. Con "
            f"{run['n_features']} atributos y {sizes['train']} animales de train, ningún "
            "baseline explica bien los AGCC: es un piso bajo, no una referencia fuerte.",
            warn=True,
        )
    else:
        ui.note(
            "En el sintético los AGCC no dependen de los atributos: ningún modelo supera a la "
            "media. Esta tabla verifica el flujo, no mide capacidad predictiva.",
            warn=True,
        )
