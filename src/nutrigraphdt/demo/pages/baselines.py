"""Partición y baselines: separar los animales sin trampa y medir el piso de comparación."""

from __future__ import annotations

from typing import Any

import streamlit as st

from nutrigraphdt.demo import cache, data, plots, ui

_MODELS = (
    (
        "dummy_mean",
        "Predice siempre el promedio de train, sin mirar al animal. Es la vara mínima: cualquier "
        "modelo útil debe equivocarse menos que él.",
    ),
    (
        "ridge",
        "Regresión lineal: una suma ponderada de los atributos, con un freno para que ningún "
        "peso se dispare.",
    ),
    (
        "elasticnet",
        "Como ridge, pero además puede apagar atributos completos (elige cuáles usar).",
    ),
    ("random_forest", "Cientos de árboles de decisión que votan la predicción."),
    (
        "hist_gradient_boosting",
        "Árboles en secuencia, donde cada uno corrige los errores del anterior.",
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
        "Separar los animales para no hacer trampa",
        "Como en un curso: el modelo estudia con unos animales, ensaya con otros y rinde el "
        "examen final con animales que nunca vio.",
    )
    ui.legend(
        [
            ("🟩", "<b>train</b>: las clases. El modelo aprende con estos animales."),
            ("🟧", "<b>val</b>: los ensayos. Sirven para elegir la mejor versión del modelo."),
            ("🟦", "<b>test</b>: el examen final. Se mira al final y no se usa para decidir nada."),
            ("🏠", "Se separa <b>por corral</b>: los animales de un corral van juntos."),
        ]
    )
    split = cache.split_summary()
    with_targets = cache.baseline_report(str(data.REPORTS_DIR / "baselines" / "d1"))["run"][
        "subset_sizes"
    ]
    st.plotly_chart(
        plots.split_figure(
            [
                {"población": "Con los tres AGCC medidos", **with_targets},
                {"población": "Todos los animales de D1", **split["counts"]},
            ]
        ),
        config=ui.CHART_CONFIG,
    )
    ui.takeaway(
        f"De {sum(split['counts'].values())} animales, solo {sum(with_targets.values())} sirven "
        "para entrenar y evaluar: son los únicos con los tres AGCC medidos."
    )
    ui.how_to_read(
        f"La barra de abajo son los {sum(split['counts'].values())} animales de D1, repartidos "
        f"en {sum(split['groups'].values())} corrales. La de arriba son los "
        f"{sum(with_targets.values())} animales a los que además se les midieron los tres AGCC: "
        "solo con ellos se puede entrenar y evaluar, porque son los únicos con respuesta "
        "conocida."
    )
    ui.note(
        "<b>¿Por qué por corral?</b> Los pollos de un mismo corral comparten ambiente, agua y "
        "alimento, así que se parecen entre sí. Si unos quedaran en train y otros en test, el "
        "modelo podría «reconocer el corral» en lugar de aprender biología, y el examen saldría "
        "mejor de lo que es."
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
        format_func=lambda s: "test (examen final)" if s == "test" else "val (ensayos)",
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
            title=f"Error típico (RMSE promedio de los tres AGCC) en {subset}",
        ),
        config=ui.CHART_CONFIG,
    )
    ui.takeaway(_reading(rmse, reference, subset))
    ui.how_to_read(
        "Cada barra es el <b>error típico</b> del modelo, en mmol/kg: cuánto se equivoca, en "
        "promedio, al predecir un AGCC. Más baja es mejor. La línea punteada es el error de "
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
