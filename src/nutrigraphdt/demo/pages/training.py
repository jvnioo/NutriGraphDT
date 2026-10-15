"""Entrenamiento: cómo aprende la GNN, entrenar en vivo y leer el resultado paso a paso."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from nutrigraphdt.demo import cache, data, plots, ui

_VARIANTS = {
    "homo_sage": "GraphSAGE homogénea: trata todas las relaciones igual. Es la versión simple.",
    "hetero_sage": "GraphSAGE heterogénea: aprende una forma distinta de leer cada relación.",
    "hetero_gat": "GAT heterogénea: además aprende a qué vecinos prestar más atención.",
}
_SHORT = {
    "homo_sage": "todas las relaciones por igual",
    "hetero_sage": "una lectura por relación",
    "hetero_gat": "con atención a los vecinos",
}
_SUBSETS = ("train", "val", "test")
_SAME_SPLIT = {"dataset": "synthetic", "n_samples": 50, "first_seed": 1, "split_seed": 42}


def render() -> None:
    ui.hero(
        "Entrenamiento",
        "Cómo aprende la GNN.",
        "Entrenar es ajustar los números internos del modelo (sus pesos) para que sus "
        "predicciones se acerquen a los AGCC medidos. Aquí puede entrenar una GNN en vivo y "
        "revisar, paso a paso, qué pasó.",
        badges=[("Cohorte sintética", "synthetic"), ("En D1: pendiente (A45-4)", "pending")],
    )
    ui.section(1, "El proceso, en cinco pasos")
    ui.steps(
        [
            ("Preparar", "Se arma el grafo de cada animal y se separan train, val y test.", "done"),
            ("Escalar", "Se llevan los números a una escala común, usando solo train.", "done"),
            (
                "Aprender",
                "En cada época el modelo predice train, mide su error y se corrige.",
                "done",
            ),
            (
                "Elegir",
                "Se guarda la época con menor error en val; si deja de mejorar, se para.",
                "done",
            ),
            (
                "Examinar",
                "La versión elegida rinde el examen en test y todo queda registrado.",
                "done",
            ),
        ],
        per_row=5,
    )
    _train_now()
    _read_result()


def _train_now() -> None:
    ui.section(
        2,
        "Entrenar ahora",
        "Se entrena sobre la cohorte sintética de 50 animales, con la misma partición que los "
        "baselines sintéticos, para poder compararlos. La configuración es la del proyecto.",
    )
    devices = cache.devices()
    left, middle, right = st.columns([2, 1, 1])
    variant = left.selectbox(
        "Variante de GNN", list(_VARIANTS), format_func=lambda v: f"{v} — {_VARIANTS[v]}"
    )
    epochs = middle.slider("Épocas máximas", 10, 200, 100, step=10)
    device = right.selectbox(
        "Dónde entrenar",
        devices,
        format_func=lambda d: "GPU · " + data.device_name(d) if d == "cuda" else "CPU",
    )
    if st.button("▶ Entrenar", type="primary"):
        with st.spinner(f"Entrenando {variant} en {data.device_name(device)}…"):
            run_dir = data.train_synthetic_run(variant, max_epochs=epochs, device=device)
        st.session_state["selected_run"] = str(run_dir)
        st.success("Listo. El resultado aparece abajo.")
    st.caption(
        "Una época es una pasada por los 30 animales de train. El entrenamiento se detiene solo "
        "si val no mejora durante 20 épocas seguidas. Con la preparación de los grafos, tarda "
        "unos 25 segundos en GPU y algo más en CPU. CPU y GPU pueden elegir épocas algo "
        "distintas por redondeo."
    )


def _read_result() -> None:
    ui.section(3, "Leer el resultado")
    runs = data.list_runs()
    if not runs:
        st.info("Todavía no hay corridas: entrene una arriba.")
        return
    paths = [str(run["path"]) for run in runs]
    selected = st.session_state.get("selected_run")
    index = paths.index(selected) if selected in paths else 0
    choice = st.selectbox(
        "Corrida",
        paths,
        index=index,
        format_func=lambda p: _run_label(next(r for r in runs if str(r["path"]) == p)),
    )
    detail = data.run_detail(Path(choice))
    info: dict[str, Any] = detail["info"]
    environment = info.get("environment", {})
    ui.metric_cards(
        [
            ("Variante", info["variant"], _SHORT.get(info["variant"], "")),
            ("Épocas", f"{info['epochs_run']}", f"la mejor fue la {info['best_epoch']}"),
            (
                "Duración",
                f"{info['duration_seconds']:.1f} s",
                environment.get("device_name") or "CPU",
            ),
            (
                "Animales",
                " · ".join(str(info["subsets"][s]["with_any_scfa"]) for s in _SUBSETS),
                "train · val · test",
            ),
        ]
    )
    _learned(detail, info)
    _versus_mean(detail, info)
    _predictions(detail)
    with st.expander("Para expertos: todo lo registrado de esta corrida (run.json)"):
        st.caption(
            "Configuración, commit de Git, versiones, partición con su huella SHA-256, "
            "escalado y dispositivo: lo necesario para reproducirla."
        )
        st.json(info, expanded=False)


def _learned(detail: dict[str, Any], info: dict[str, Any]) -> None:
    st.markdown("#### a) ¿Aprendió?")
    history = detail["history"]
    train = [float(row["train_loss"]) for row in history]
    val = [float(row["val_loss"]) for row in history]
    best = int(info["best_epoch"])
    st.plotly_chart(
        plots.curves_figure(
            {"error en train": train, "error en val": val},
            title="Error del modelo en cada época",
            y_title="error (escala estandarizada)",
            marker_x=best,
        ),
        config=ui.CHART_CONFIG,
        key=f"loss_{info['run_id']}",
    )
    ui.how_to_read(
        "La línea <b>verde</b> es el error con los animales de estudio (train): si baja, el "
        "modelo está aprendiendo. La <b>roja</b> es el error con animales que no usa para "
        "aprender (val): es la que importa. Si la verde baja y la roja sube, el modelo está "
        "<b>memorizando</b> en vez de aprender. La línea punteada marca la época elegida."
    )
    stop = (
        f"después, val no mejoró durante {info['epochs_run'] - best} épocas y el entrenamiento "
        "se detuvo solo"
        if info.get("stopped_early")
        else "el entrenamiento llegó al máximo de épocas"
    )
    memorizing = ""
    if val[-1] > val[best - 1] * 1.05 and train[-1] < train[best - 1]:
        memorizing = (
            f" Desde la época {best} la línea roja sube mientras la verde sigue bajando: el "
            "modelo empezó a memorizar a los animales de train. Por eso no se usa la última "
            "época, sino la mejor."
        )
    st.markdown(
        f"**Lectura:** el error en train bajó de {train[0]:.2f} a {train[-1]:.2f}. El menor "
        f"error en val se logró en la época {best}; {stop}. Se conservan los pesos de esa "
        f"época.{memorizing}"
    )


def _versus_mean(detail: dict[str, Any], info: dict[str, Any]) -> None:
    st.markdown("#### b) ¿Le gana a predecir la media?")
    source = info.get("source", {})
    if any(source.get(key) != value for key, value in _SAME_SPLIT.items()):
        st.info("Esta corrida no usa la partición de los baselines sintéticos; no se compara.")
        return
    baselines = cache.baseline_report(str(data.REPORTS_DIR / "baselines"))
    rows = data.baseline_table(baselines["rows"], "rmse", "test")
    gnn = next(
        float(row["average"])
        for row in detail["metrics"]
        if row["metric"] == "rmse" and row["split"] == "test"
    )
    rows.append({"modelo": f"GNN ({info['variant']})", "promedio": gnn})
    reference = next(row["promedio"] for row in rows if row["modelo"] == "dummy_mean")
    st.plotly_chart(
        plots.versus_mean_figure(
            rows,
            value="promedio",
            reference=reference,
            title="Error típico en test, mismos 10 animales (mmol/kg)",
        ),
        config=ui.CHART_CONFIG,
        key=f"vs_{info['run_id']}",
    )
    change = (gnn - reference) / reference * 100
    ui.how_to_read(
        "La última barra es esta GNN; las demás, los baselines sintéticos de la página "
        "anterior, evaluados con los mismos animales. Más baja es mejor, y la línea punteada es "
        f"predecir siempre la media. Aquí la GNN queda en {gnn:.2f} frente a {reference:.2f} "
        f"de la media ({change:+.0f} %)."
    )
    ui.note(
        "En el sintético <b>nadie puede ganarle a la media</b> por un margen real: los AGCC se "
        "generan sin depender de los datos del animal. Que la GNN quede en el mismo rango que "
        "los baselines es lo esperado, y muestra que el flujo funciona de punta a punta. La "
        "comparación que importa es en D1 (A45-4).",
        warn=True,
    )


def _predictions(detail: dict[str, Any]) -> None:
    st.markdown("#### c) ¿Qué predice?")
    subset = st.radio(
        "Animales",
        ["test", "val", "train"],
        horizontal=True,
        key="pred_subset",
    )
    st.plotly_chart(
        plots.predicted_vs_measured(detail["predictions"], subset=subset),
        config=ui.CHART_CONFIG,
    )
    ui.how_to_read(
        "Cada punto es un animal y un AGCC: a lo ancho, el valor <b>medido</b>; a lo alto, el "
        "que <b>predijo</b> el modelo. Si acertara, los puntos caerían sobre la diagonal "
        "punteada. Cuando los puntos de un AGCC forman una franja casi <b>horizontal</b>, el "
        "modelo predice casi el mismo valor para todos los animales: su promedio. Es lo que "
        "pasa en el sintético, por la razón del punto anterior."
    )


def _run_label(run: dict[str, Any]) -> str:
    where = run["dispositivo"] if run["dispositivo"] != "cpu" else "CPU"
    return f"{run['variante']} · {run['epocas']} épocas · {where} · {run['run_id'][:15]}"
