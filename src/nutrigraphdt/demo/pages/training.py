"""Entrenamiento: cómo aprende la GNN, entrenar en vivo y leer el resultado paso a paso."""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

import streamlit as st

from nutrigraphdt.demo import cache, data, plots, ui

_VARIANTS = {
    "homo_sage": "GraphSAGE homogénea: trata todas las relaciones igual. Es la versión simple.",
    "hetero_sage": "GraphSAGE heterogénea: aprende una forma distinta de leer cada relación.",
    "hetero_gat": "GAT heterogénea: además aprende a qué vecinos prestar más atención.",
}
_SUBSETS = ("train", "val", "test")
_RECENT_RUNS = 8
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
            (
                "Escalar",
                "Estandarización de atributos y target con estadísticas de entrenamiento.",
                "done",
            ),
            (
                "Ajustar",
                "En cada época se minimiza la pérdida sobre entrenamiento con Adam.",
                "done",
            ),
            (
                "Seleccionar",
                "Se conserva la época con menor error en validación (detención temprana).",
                "done",
            ),
            (
                "Evaluar",
                "El modelo seleccionado se evalúa en prueba y la corrida queda registrada.",
                "done",
            ),
        ],
        per_row=5,
    )
    _train_now()
    _read_result()
    _closing()


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
        "Variante de GNN",
        list(_VARIANTS),
        index=2,
        format_func=lambda v: f"{data.MODEL_LABELS[v]} — {_VARIANTS[v].split(': ', 1)[1]}",
    )
    epochs = middle.slider("Épocas máximas", 10, 200, 100, step=10)
    device = right.selectbox(
        "Dónde entrenar",
        devices,
        format_func=lambda d: "GPU · " + data.device_name(d) if d == "cuda" else "CPU",
    )
    if st.button("▶ Entrenar", type="primary"):
        with st.spinner(f"Entrenando {data.MODEL_LABELS[variant]} en {data.device_name(device)}…"):
            run_dir = data.train_synthetic_run(variant, max_epochs=epochs, device=device)
        st.session_state["selected_run"] = str(run_dir)
        st.success("Listo. El resultado aparece abajo.")
    st.caption(
        "Una época es una pasada completa por los 30 animales de entrenamiento. La detención "
        "temprana corta el entrenamiento si el error de validación no mejora durante 20 "
        "épocas. Con la preparación de los grafos, tarda unos 25 segundos en GPU y algo más "
        "en CPU. CPU y GPU pueden seleccionar épocas algo distintas por diferencias de "
        "redondeo."
    )


def _read_result() -> None:
    ui.section(3, "Leer el resultado")
    runs = data.list_runs()[:_RECENT_RUNS]
    if not runs:
        st.info("Todavía no hay corridas: entrene una arriba.")
        return
    paths = [str(run["path"]) for run in runs]
    selected = st.session_state.get("selected_run")
    index = paths.index(selected) if selected in paths else 0
    choice = st.selectbox(
        f"Corrida (las {_RECENT_RUNS} más recientes; por defecto, la última)",
        paths,
        index=index,
        format_func=lambda p: _run_label(next(r for r in runs if str(r["path"]) == p)),
    )
    detail = data.run_detail(Path(choice))
    info: dict[str, Any] = detail["info"]
    environment = info.get("environment", {})
    ui.metric_cards(
        [
            ("Modelo", data.MODEL_LABELS.get(info["variant"], info["variant"]), info["variant"]),
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
            {"entrenamiento (train)": train, "validación (val)": val},
            title="Error del modelo en cada época",
            y_title="error (escala estandarizada)",
            marker_x=best,
        ),
        config=ui.CHART_CONFIG,
        key=f"loss_{info['run_id']}",
    )
    overfitting = val[-1] > val[best - 1] * 1.05 and train[-1] < train[best - 1]
    if overfitting:
        ui.takeaway(
            f"El error de validación es mínimo en la época {best}; después sube mientras el "
            "de entrenamiento sigue bajando: hay <b>sobreajuste</b>. Por eso se conserva la "
            f"época {best}, no la última."
        )
    else:
        ui.takeaway(
            f"La pérdida de entrenamiento bajó de {train[0]:.2f} a {train[-1]:.2f} y la de "
            f"validación fue mínima en la época {best}, que es la que se conserva."
        )
    stop = (
        f"Después de la época {best}, val no mejoró durante {info['epochs_run'] - best} épocas "
        "y el entrenamiento se detuvo solo."
        if info.get("stopped_early")
        else "El entrenamiento llegó al máximo de épocas."
    )
    ui.how_to_read(
        "La línea <b>verde</b> es la pérdida (MSE estandarizado) en entrenamiento: es la que "
        "el optimizador minimiza. La <b>roja</b> es la pérdida en validación, sobre animales "
        "que no ajustan los parámetros: estima cómo generaliza el modelo. Si la de "
        "entrenamiento baja y la de validación sube, hay <b>sobreajuste</b>. La línea punteada "
        "marca la época con menor error en validación, que es la que se conserva (detención "
        "temprana). " + stop
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
    label = data.MODEL_LABELS.get(info["variant"], info["variant"])
    rows.append({"modelo": f"{label} (esta corrida)", "clave": info["variant"], "promedio": gnn})
    reference = next(row["promedio"] for row in rows if row["clave"] == "dummy_mean")
    st.plotly_chart(
        plots.versus_mean_figure(
            rows,
            value="promedio",
            reference=reference,
            title="RMSE promedio en prueba, mismos 10 animales (mmol/kg)",
        ),
        config=ui.CHART_CONFIG,
        key=f"vs_{info['run_id']}",
    )
    change = (gnn - reference) / reference * 100
    ui.takeaway(
        f"La GNN queda en {gnn:.2f} frente a {reference:.2f} de la media ({change:+.0f} %): en el "
        "mismo rango que los demás modelos, como se espera en el sintético."
    )
    ui.how_to_read(
        "La última barra es esta GNN; las demás, los baselines sintéticos de la página "
        "anterior, evaluados con los mismos animales. Más baja es mejor, y la línea punteada es "
        "predecir siempre la media. En el sintético <b>nadie puede ganarle a la media</b> por un "
        "margen real: los AGCC se generan sin depender de los datos del animal. Que la GNN quede "
        "en el mismo rango muestra que el flujo funciona de punta a punta; la comparación que "
        "importa es en D1 (A45-4)."
    )


def _predictions(detail: dict[str, Any]) -> None:
    st.markdown("#### c) ¿Qué predice?")
    subset = st.radio(
        "Animales",
        ["test", "val", "train"],
        horizontal=True,
        key="pred_subset",
        format_func=lambda s: {
            "test": "prueba (test)",
            "val": "validación (val)",
            "train": "entrenamiento (train)",
        }[s],
    )
    st.plotly_chart(
        plots.predicted_vs_measured(detail["predictions"], subset=subset),
        config=ui.CHART_CONFIG,
    )
    spread = _spread_ratio(detail["predictions"], subset)
    if spread is not None:
        ui.takeaway(
            f"Las predicciones varían {spread:.0%} de lo que varían los valores medidos: el "
            "modelo predice casi lo mismo para todos los animales, cerca del promedio de cada "
            "AGCC."
            if spread < 0.5
            else f"Las predicciones varían {spread:.0%} de lo que varían los valores medidos."
        )
    ui.how_to_read(
        "Cada punto es un animal y un AGCC: a lo ancho, el valor <b>medido</b>; a lo alto, el "
        "que <b>predijo</b> el modelo. Si acertara, los puntos caerían sobre la diagonal "
        "punteada. Cuando los puntos de un AGCC forman una franja casi <b>horizontal</b>, el "
        "modelo predice casi el mismo valor para todos los animales: su promedio. En el "
        "sintético es lo esperable, porque los AGCC no dependen de los datos del animal."
    )


def _spread_ratio(rows: list[dict[str, str]], subset: str) -> float | None:
    """Desviación de lo predicho sobre la de lo medido, promediada entre AGCC."""
    ratios = []
    for target in ("acetate", "propionate", "butyrate"):
        pairs = [
            (float(row[f"measured_{target}"]), float(row[f"predicted_{target}"]))
            for row in rows
            if row.get("subset") == subset and row.get(f"measured_{target}")
        ]
        if len(pairs) < 2:
            continue
        measured = statistics.pstdev(p[0] for p in pairs)
        if measured > 0:
            ratios.append(statistics.pstdev(p[1] for p in pairs) / measured)
    return sum(ratios) / len(ratios) if ratios else None


def _closing() -> None:
    ui.section(4, "Dónde estamos y qué sigue")
    left, right = st.columns(2)
    left.markdown(
        """
**Listo**
- Datos reales (D1) y sintéticos con el mismo esquema de grafo.
- Validación de cada grafo antes de entrenar.
- Partición agrupada por corral, sin fuga de información, y cinco modelos de referencia.
- Tres GNN y un pipeline de entrenamiento trazable, en CPU o GPU.
"""
    )
    right.markdown(
        """
**Lo que sigue**
- Entrenar y evaluar la GNN en D1, frente a los baselines (A45-4).
- Darle relaciones a los taxones de D1 con anotación funcional (S-03).
- Aumentar los animales con datos completos, una decisión con Investigación.
- Simular cambios de dieta (el «gemelo digital»): requiere que la dieta entre al grafo.
"""
    )
    ui.note(
        "Prototipo académico de factibilidad computacional: nada de lo mostrado es una "
        "recomendación nutricional ni una conclusión biológica."
    )


def _run_label(run: dict[str, Any]) -> str:
    where = "CPU" if run["dispositivo"] == "cpu" else "GPU"
    stamp = run["run_id"][:15]
    when = f"{stamp[6:8]}/{stamp[4:6]} {stamp[9:11]}:{stamp[11:13]}"
    label = data.MODEL_LABELS.get(run["variante"], run["variante"])
    return f"{label} · {run['epocas']} épocas · {where} · {when} (UTC)"
