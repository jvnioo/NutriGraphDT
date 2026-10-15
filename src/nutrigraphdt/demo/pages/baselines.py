"""Partición (entrenamiento, validación y prueba) y baselines: el piso de comparación."""

from __future__ import annotations

from typing import Any

import streamlit as st

from nutrigraphdt.demo import cache, data, plots, ui

_MODELS = (
    (
        "dummy_mean",
        "Predice para cada AGCC su media en entrenamiento; no usa atributos. Es la referencia "
        "mínima: un modelo útil debe tener menor error que ella.",
    ),
    ("ridge", "Regresión lineal con regularización L2 sobre los coeficientes."),
    (
        "elasticnet",
        "Regresión lineal con regularización L1 + L2; la parte L1 puede anular coeficientes "
        "(selección de atributos).",
    ),
    (
        "random_forest",
        "Ensamble de árboles de decisión entrenados sobre muestras bootstrap; promedia sus "
        "predicciones.",
    ),
    (
        "hist_gradient_boosting",
        "Boosting por gradiente: árboles añadidos en secuencia, cada uno ajustado a los "
        "residuos del anterior, con atributos discretizados en histogramas.",
    ),
)


def render() -> None:
    ui.hero(
        "Partición y baselines",
        "¿Qué tan difícil es predecir los AGCC?",
        "Antes de juzgar a la GNN hay que saber cuánto se logra con métodos simples. Ese piso se "
        "llama baseline: si la GNN no lo supera, no aporta. Para que la comparación sea justa, "
        "todos los modelos usan los mismos animales, separados de la misma forma.",
    )
    _split()
    _models()
    _results()


def _split() -> None:
    ui.section(
        1,
        "Partición en entrenamiento, validación y prueba",
        "Los animales se dividen en tres conjuntos disjuntos antes de entrenar. Cada conjunto "
        "cumple un rol distinto en el ajuste y la evaluación del modelo.",
    )
    split = cache.split_summary()
    real = cache.baseline_report(str(data.REPORTS_DIR / "baselines" / "d1"))["run"]["subset_sizes"]
    synthetic = cache.baseline_report(str(data.REPORTS_DIR / "baselines"))["run"]["subset_sizes"]
    header = (
        "| Conjunto | Uso | ¿Ajusta los parámetros? | ¿Interviene en la selección? "
        "| D1 (con los tres AGCC) | Sintético |\n|---|---|:---:|:---:|:---:|:---:|"
    )
    rows = [
        (
            "**Entrenamiento** (`train`)",
            "Ajustar los parámetros del modelo minimizando la pérdida sobre sus valores medidos.",
            "Sí",
            "Sí (validación cruzada de los baselines)",
            "train",
        ),
        (
            "**Validación** (`val`)",
            "Seleccionar el modelo: detención temprana (época con menor error) y comparación "
            "de configuraciones.",
            "No",
            "Sí",
            "val",
        ),
        (
            "**Prueba** (`test`)",
            "Estimar el error de generalización del modelo ya seleccionado. Se evalúa al final.",
            "No",
            "No",
            "test",
        ),
    ]
    st.markdown(
        header
        + "".join(
            f"\n| {name} | {use} | {fits} | {selects} | {real[key]} | {synthetic[key]} |"
            for name, use, fits, selects, key in rows
        )
    )
    st.plotly_chart(
        plots.split_figure(
            [
                {"población": "Con los tres AGCC medidos", **real},
                {"población": "Todos los animales de D1", **split["counts"]},
            ]
        ),
        config=ui.CHART_CONFIG,
    )
    ui.takeaway(
        f"De {sum(split['counts'].values())} animales de D1, {sum(real.values())} tienen los tres "
        "AGCC medidos: solo con ellos se puede entrenar y evaluar."
    )
    ui.how_to_read(
        f"La barra inferior es la partición de los {sum(split['counts'].values())} animales con "
        f"metadatos ({split['ratios'].get('train', 0):.0%} / {split['ratios'].get('val', 0):.0%} "
        f"/ {split['ratios'].get('test', 0):.0%}, semilla {split['seed']}). La superior es el "
        "subconjunto con los tres AGCC, que conserva la asignación de cada animal: por eso sus "
        "proporciones no son exactamente las mismas."
    )
    with st.expander("Por qué tres conjuntos y por qué agrupar por corral", expanded=True):
        st.markdown(
            f"""
- **Error en entrenamiento.** Es optimista: el modelo se ajustó a esos mismos animales. Si el
  error de entrenamiento baja mientras el de validación sube, hay **sobreajuste**.
- **Error en validación.** También queda sesgado a la baja después de usarlo para seleccionar
  (la época o la configuración elegida es la que mejor resultó justamente en validación).
- **Error en prueba.** Es la estimación sin sesgo de selección, porque esos animales no
  intervinieron ni en el ajuste ni en la selección. Es la cifra que se reporta.
- **Partición agrupada por `{split["group_key"]}` (corral) y estratificada por
  `{split["stratify_key"]}`.** Los animales de un corral comparten ambiente y alimentación,
  así que sus mediciones están correlacionadas. Si un corral quedara repartido entre
  entrenamiento y prueba, habría **fuga de información** y el error de prueba subestimaría el
  error real. La estratificación mantiene la proporción de tratamientos en cada conjunto.
- **Validación pequeña.** En D1 la validación tiene {real["val"]} animales: la selección
  (por ejemplo, la época de detención temprana) tiene alta varianza.
"""
        )


def _models() -> None:
    ui.section(
        2,
        "Cinco modelos de referencia",
        "Todos reciben la misma tabla por animal: la abundancia de cada taxón, el peso y la "
        "dieta (1319 columnas en D1). Sus ajustes se eligen con validación cruzada dentro de "
        "train, sin tocar val ni test.",
    )
    st.markdown(
        "| Modelo | Idea |\n|---|---|\n"
        + "\n".join(
            f"| **{data.MODEL_LABELS[name]}** <br><small>`{name}`</small> | {idea} |"
            for name, idea in _MODELS
        ),
        unsafe_allow_html=True,
    )


def _results() -> None:
    ui.section(3, "Resultados: ¿alguno le gana a la media?")
    left, right = st.columns(2)
    dataset = left.radio("Datos", ["D1 HoloFood (real)", "Sintético"], horizontal=True)
    subset = right.radio(
        "Animales evaluados",
        ["test", "val"],
        horizontal=True,
        format_func=lambda s: "prueba (test)" if s == "test" else "validación (val)",
    )
    real = dataset.startswith("D1")
    directory = data.REPORTS_DIR / "baselines" / ("d1" if real else "")
    report = cache.baseline_report(str(directory))
    rmse = data.baseline_table(report["rows"], "rmse", subset)
    r2 = {row["modelo"]: row for row in data.baseline_table(report["rows"], "r2", subset)}
    reference = next(row["promedio"] for row in rmse if row["clave"] == "dummy_mean")
    st.plotly_chart(
        plots.versus_mean_figure(
            rmse,
            value="promedio",
            reference=reference,
            title=f"RMSE promedio de los tres AGCC en {subset}",
        ),
        config=ui.CHART_CONFIG,
    )
    ui.takeaway(_reading(rmse, reference, subset))
    ui.how_to_read(
        "Cada barra es el <b>RMSE</b> (raíz del error cuadrático medio) del modelo, promediado "
        "entre los tres AGCC, en mmol/kg. Menor es mejor. La línea punteada es el error de "
        "predecir siempre la media; cada barra dice si queda <b>▼ mejor</b> o <b>▲ peor</b> que "
        "ella (también en verde o rojo)."
    )
    with st.expander("Detalle por AGCC y R²"):
        st.markdown(
            "**R²** indica cuánto mejor que la media es el modelo: 1 es perfecto, 0 es igual a la "
            "media y un valor negativo es peor que ella."
        )
        st.dataframe(
            [
                {
                    "modelo": row["modelo"],
                    "RMSE acetato": round(row["acetato"], 2),
                    "RMSE propionato": round(row["propionato"], 2),
                    "RMSE butirato": round(row["butirato"], 2),
                    "R² promedio": round(r2[row["modelo"]]["promedio"], 3),
                }
                for row in rmse
            ],
            hide_index=True,
        )
    _conclusion(real, report["run"], rmse, reference)


def _reading(rows: list[dict[str, Any]], reference: float, subset: str) -> str:
    models = [row for row in rows if row["clave"] != "dummy_mean"]
    better = [row for row in models if row["promedio"] < reference]
    best = min(models, key=lambda row: row["promedio"])
    change = (best["promedio"] - reference) / reference * 100
    if not better:
        return (
            f"En {subset}, ningún modelo se equivoca menos que predecir la media "
            f"({reference:.2f} mmol/kg). El mejor, {best['modelo']}, queda en "
            f"{best['promedio']:.2f} ({change:+.0f} %)."
        )
    return (
        f"En {subset}, {len(better)} de {len(models)} modelos mejoran a la media. "
        f"El mejor, {best['modelo']}, baja el error de {reference:.2f} a "
        f"{best['promedio']:.2f} mmol/kg ({change:+.0f} %)."
    )


def _conclusion(
    real: bool, run: dict[str, Any], rows: list[dict[str, Any]], reference: float
) -> None:
    ui.section(4, "Qué significa para la GNN")
    if not real:
        ui.note(
            "En el sintético los AGCC se generan <b>sin depender</b> de los atributos, así que "
            "ningún modelo puede ganarle a la media: no hay nada que aprender. Esta tabla solo "
            "comprueba que el flujo funciona. Es la misma partición que usa la GNN en "
            "«Entrenamiento», para comparar ahí.",
            warn=True,
        )
        return
    best = min((r for r in rows if r["clave"] != "dummy_mean"), key=lambda r: r["promedio"])
    sizes = run["subset_sizes"]
    st.markdown(
        f"""
- **El piso es bajo.** Con estos datos, el mejor baseline apenas mejora a la media
  ({reference:.2f} → {best["promedio"]:.2f} mmol/kg). Predecir AGCC desde la microbiota es
  difícil, y los datos son pocos.
- **La meta de la GNN** es equivocarse menos que {best["modelo"]} en los mismos
  {sizes["test"]} animales de test. Esa evaluación (A45-4) todavía no se hizo.
- **Ventaja de los baselines:** usan la dieta, y la GNN todavía no (en el grafo, el nodo dieta
  no tiene atributos). En D1 la GNN parte con menos información.
"""
    )
    ui.note(
        f"<b>Cautela.</b> Hay {run['n_features']} atributos para solo {sizes['train']} animales "
        f"de train, y val tiene {sizes['val']} animales: sus resultados cambian mucho con pocos "
        "animales. Por eso estas cifras son una referencia, no una conclusión.",
        warn=True,
    )
