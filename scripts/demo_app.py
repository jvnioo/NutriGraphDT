"""Demo de NutriGraphDT en Streamlit: el grafo sintético frente al grafo de D1.

Una sola página compara el esquema, una instancia, las aristas y su evidencia, los nodos y sus
atributos y los AGCC objetivo de cada grafo. Todo sale del código y de los artefactos del
repositorio.

Requiere los extras `graph` y `demo`. Uso:

    pip install -e ".[graph,demo]"
    streamlit run scripts/demo_app.py

Ver docs/demo.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# En Streamlit Community Cloud el proyecto no se instala: se importa desde src/.
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nutrigraphdt.demo import ui  # noqa: E402
from nutrigraphdt.demo.pages import graph_comparison  # noqa: E402

LOGO = Path(ui.__file__).parent / "assets" / "logo.svg"

st.set_page_config(page_title="NutriGraphDT · Sintético vs. D1", page_icon="🧬", layout="wide")
st.logo(str(LOGO), size="large")
ui.inject_css()

with st.sidebar:
    st.caption("Gemelo digital nutricional basado en grafos · PIA-2, sección 302, UTEM")
    st.caption("Prototipo académico de factibilidad computacional.")

graph_comparison.render()
