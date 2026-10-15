"""Demo de avance de NutriGraphDT en Streamlit.

Tres páginas, pensadas para leerse en orden: el explorador del grafo (cómo se representa un
animal, sintético y real), la partición y los baselines (qué tan difícil es predecir los AGCC) y
el entrenamiento (cómo aprende la GNN, con entrenamiento en vivo). Todo sale del código y de los
artefactos del repositorio; funciona sin la descarga completa de D1.

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
from nutrigraphdt.demo.pages import baselines, graph, training

LOGO = Path(ui.__file__).parent / "assets" / "logo.svg"

st.set_page_config(page_title="NutriGraphDT · Avance", page_icon="🧬", layout="wide")
st.logo(str(LOGO), size="large")
ui.inject_css()

navigation = st.navigation(
    [
        st.Page(
            graph.render, title="1 · Explorador del grafo", icon="🕸️", url_path="grafo", default=True
        ),
        st.Page(
            baselines.render, title="2 · Partición y baselines", icon="📊", url_path="baselines"
        ),
        st.Page(training.render, title="3 · Entrenamiento", icon="⚙️", url_path="entrenamiento"),
    ]
)

with st.sidebar:
    st.caption(
        "Recorrido sugerido: primero cómo se representa un animal, luego qué tan difícil es "
        "predecir sus AGCC y, al final, cómo aprende la GNN."
    )
ui.glossary()
with st.sidebar:
    st.divider()
    st.caption("Gemelo digital nutricional basado en grafos · PIA-2, sección 302, UTEM")
    st.caption(
        "Prototipo académico de factibilidad computacional. Nada de lo mostrado es una "
        "recomendación nutricional ni una conclusión biológica."
    )

navigation.run()
