"""Demo de NutriGraphDT en Streamlit: comparación de grafos y simulador de escenarios.

- **Sintético frente a D1** (página inicial): compara el esquema, una instancia, las aristas y su
  evidencia, los nodos y sus atributos y los AGCC objetivo de cada grafo.
- **Simulador de escenarios** (A81): pide un escenario a una corrida congelada de demostración
  por `nutrigraphdt.api` y muestra la predicción o «no estimable».

Todo sale del código y de los artefactos del repositorio. Requiere los extras `graph`,
`baselines` y `demo`. Uso:

    pip install -e ".[graph,baselines,demo]"
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
from nutrigraphdt.demo.pages import graph_comparison, scenario_simulator  # noqa: E402

LOGO = Path(ui.__file__).parent / "assets" / "logo.svg"

st.set_page_config(page_title="NutriGraphDT", page_icon="🧬", layout="wide")
st.logo(str(LOGO), size="large")
ui.inject_css()

with st.sidebar:
    st.caption("Gemelo digital nutricional basado en grafos · PIA-2, sección 302, UTEM")
    st.caption("Prototipo académico de factibilidad computacional.")

page = st.navigation(
    [
        st.Page(
            graph_comparison.render,
            title="Sintético frente a D1",
            url_path="comparacion",
            default=True,
        ),
        st.Page(scenario_simulator.render, title="Simulador de escenarios", url_path="simulador"),
    ]
)
page.run()
