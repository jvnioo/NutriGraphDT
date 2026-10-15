"""Demo de avance de NutriGraphDT en Streamlit (hasta la actividad 41).

Muestra resultados: los grafos desarrollados (sintético y D1), el resultado de construir y
validar los grafos de D1, y los baselines sobre la cohorte sintética. Todo sale del código y de
los artefactos del repositorio.

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
from nutrigraphdt.demo.pages import baselines, d1, graph  # noqa: E402

LOGO = Path(ui.__file__).parent / "assets" / "logo.svg"

st.set_page_config(page_title="NutriGraphDT · Avance", page_icon="🧬", layout="wide")
st.logo(str(LOGO), size="large")
ui.inject_css()

navigation = st.navigation(
    [
        st.Page(graph.render, title="Grafos", icon="🕸️", url_path="grafos", default=True),
        st.Page(d1.render, title="Grafos de D1", icon="🐔", url_path="d1"),
        st.Page(baselines.render, title="Baselines", icon="📊", url_path="baselines"),
    ]
)

with st.sidebar:
    st.caption("Gemelo digital nutricional basado en grafos · PIA-2, sección 302, UTEM")
    st.caption("Avance hasta la actividad 41. Prototipo académico de factibilidad computacional.")

navigation.run()
