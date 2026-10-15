"""Demo de avance de NutriGraphDT en Streamlit.

Recorre lo construido con el código y los artefactos reales del repositorio: datos, grafo,
validación, partición y baselines, modelos GNN, entrenamiento y proceso. Funciona sin la
descarga completa de D1 (usa la cohorte sintética, el fixture de D1 y los reportes versionados).

Requiere los extras `graph` y `demo`. Uso:

    pip install -e ".[graph,baselines,demo]"
    streamlit run scripts/demo_app.py

Con una GPU, ejecútelo desde un entorno con PyTorch para CUDA o ROCm para entrenar en vivo en
GPU (ver docs/demo.md).
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from nutrigraphdt.demo import ui
from nutrigraphdt.demo.pages import (
    baselines,
    datasets,
    graph,
    models,
    process,
    summary,
    training,
    validation,
)

LOGO = Path(ui.__file__).parent / "assets" / "logo.svg"

st.set_page_config(page_title="NutriGraphDT · Avance", page_icon="🧬", layout="wide")
st.logo(str(LOGO), size="large")
ui.inject_css()

navigation = st.navigation(
    {
        "Proyecto": [
            st.Page(summary.render, title="Resumen", icon="🏠", url_path="resumen", default=True),
        ],
        "Datos y grafo": [
            st.Page(datasets.render, title="Datos", icon="🧪", url_path="datos"),
            st.Page(graph.render, title="Explorador del grafo", icon="🕸️", url_path="grafo"),
            st.Page(validation.render, title="Validación", icon="✅", url_path="validacion"),
        ],
        "Modelos": [
            st.Page(
                baselines.render, title="Partición y baselines", icon="📊", url_path="baselines"
            ),
            st.Page(models.render, title="Modelos GNN", icon="🧠", url_path="modelos"),
            st.Page(training.render, title="Entrenamiento", icon="⚙️", url_path="entrenamiento"),
        ],
        "Equipo": [
            st.Page(process.render, title="Proceso", icon="🗂️", url_path="proceso"),
        ],
    }
)

with st.sidebar:
    st.divider()
    st.caption("Gemelo digital nutricional basado en grafos · PIA-2, sección 302, UTEM")
    st.caption(
        "Prototipo académico de factibilidad computacional. Nada de lo mostrado es una "
        "recomendación nutricional ni una conclusión biológica."
    )

navigation.run()
