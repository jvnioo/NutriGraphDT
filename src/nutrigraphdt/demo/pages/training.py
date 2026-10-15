"""Entrenamiento: corridas registradas y un entrenamiento en vivo (CPU o GPU)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from nutrigraphdt.demo import cache, data, plots, ui

_VARIANTS = ("homo_sage", "hetero_sage", "hetero_gat")


def render() -> None:
    ui.hero(
        "Entrenamiento",
        "Un comando, una corrida trazable.",
        "scripts/train_gnn.py prepara los grafos, ajusta el escalado con train, entrena con "
        "detención temprana sobre val y deja en runs/ todo lo necesario para reproducir la "
        "corrida: configuración, commit, versiones, partición, historial, métricas, "
        "predicciones y pesos.",
        badges=[("Cohorte sintética", "synthetic"), ("D1: pendiente (A45-4)", "pending")],
    )
    recorded, live = st.tabs(["Corridas registradas", "Entrenar ahora"])
    with live:
        _live()
    with recorded:
        _recorded()


def _live() -> None:
    devices = cache.devices()
    left, middle, right = st.columns(3)
    variant = left.selectbox("Variante", _VARIANTS, key="live_variant")
    epochs = middle.slider("Épocas máximas", 5, 200, 60, step=5)
    device = right.selectbox(
        "Dispositivo",
        devices,
        format_func=lambda d: f"{d} · {data.device_name(d)}",
    )
    st.caption(
        "Configuración versionada (configs/training/default.json y configs/models/), cohorte "
        "sintética de 50 animales y partición con semilla 42. La detención temprana puede "
        "terminar antes del máximo."
    )
    if st.button("Entrenar", type="primary"):
        with st.spinner(f"Entrenando {variant} en {data.device_name(device)}…"):
            run_dir = data.train_synthetic_run(variant, max_epochs=epochs, device=device)
        st.session_state["selected_run"] = str(run_dir)
        st.success(f"Corrida registrada en runs/demo/{run_dir.name}")
    if "cuda" in devices:
        ui.note(
            "Con la misma configuración, CPU y GPU dan resultados algo distintos (el redondeo "
            "cambia, y con él la época elegida). CPU es la referencia de reproducibilidad del "
            "proyecto; la GPU acelera las corridas."
        )
    selected = st.session_state.get("selected_run")
    if selected and Path(selected).is_dir():
        _show_run(Path(selected))


def _recorded() -> None:
    runs = data.list_runs()
    if not runs:
        st.info(
            "No hay corridas en runs/. Entrene una en la pestaña «Entrenar ahora» o ejecute "
            "`python scripts/train_gnn.py --model homo_sage --dataset synthetic`."
        )
        return
    table = [{k: v for k, v in run.items() if k not in ("path", "created_at")} for run in runs]
    st.dataframe(table, hide_index=True)
    labels = {f"{run['run_id']} · {run['dispositivo']}": run["path"] for run in runs}
    choice = st.selectbox("Ver corrida", list(labels))
    _show_run(Path(labels[choice]))


def _show_run(run_dir: Path) -> None:
    detail = data.run_detail(run_dir)
    info: dict[str, Any] = detail["info"]
    history = detail["history"]
    environment = info.get("environment", {})
    rmse = {
        row["split"]: float(row["average"]) for row in detail["metrics"] if row["metric"] == "rmse"
    }
    ui.metric_cards(
        [
            ("Variante", info["variant"], f"semilla {info['seed']}"),
            (
                "Épocas",
                f"{info['epochs_run']}",
                f"mejor: {info['best_epoch']}"
                + (" · detención temprana" if info.get("stopped_early") else ""),
            ),
            ("RMSE val", f"{rmse.get('val', float('nan')):.2f}", "mmol/kg, promedio de AGCC"),
            (
                "Duración",
                f"{info['duration_seconds']:.1f} s",
                environment.get("device_name") or environment.get("device", "cpu"),
            ),
        ]
    )
    best = int(info["best_epoch"])
    left, right = st.columns(2)
    left.plotly_chart(
        config=ui.CHART_CONFIG,
        figure_or_data=plots.curves_figure(
            {
                "train": [float(row["train_loss"]) for row in history],
                "val": [float(row["val_loss"]) for row in history],
            },
            title="Pérdida (MSE estandarizado)",
            y_title="MSE",
            marker_x=best,
        ),
    )
    right.plotly_chart(
        config=ui.CHART_CONFIG,
        figure_or_data=plots.curves_figure(
            {"RMSE val": [float(row["val_rmse_average"]) for row in history]},
            title="RMSE promedio de val (mmol/kg): criterio de detención",
            y_title="RMSE",
            marker_x=best,
        ),
    )
    left, right = st.columns([3, 2])
    subset = right.radio(
        "Subconjunto", ["test", "val", "train"], horizontal=True, key=f"subset_{run_dir.name}"
    )
    left.plotly_chart(
        config=ui.CHART_CONFIG,
        figure_or_data=plots.predicted_vs_measured(detail["predictions"], subset=subset),
    )
    right.dataframe(
        [
            {
                "split": row["split"],
                "métrica": row["metric"],
                "promedio": round(float(row["average"]), 3),
            }
            for row in detail["metrics"]
            if row["metric"] in ("rmse", "mae", "r2")
        ],
        hide_index=True,
    )
    with st.expander("run.json: trazabilidad completa"):
        st.json(
            {
                key: info.get(key)
                for key in (
                    "run_id",
                    "created_at",
                    "variant",
                    "dataset_id",
                    "source",
                    "split",
                    "git",
                    "environment",
                    "training_config",
                    "model_config",
                    "subsets",
                )
            }
        )
    ui.note(
        "En la cohorte sintética los AGCC no dependen de los atributos, así que el modelo "
        "aprende a predecir cerca de la media (R² ≈ 0), igual que los baselines. Esta corrida "
        "demuestra que el pipeline funciona de punta a punta; la evaluación en D1 es A45-4.",
        warn=True,
    )
