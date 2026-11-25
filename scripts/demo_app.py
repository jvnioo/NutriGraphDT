"""Web App de NutriGraphDT en Streamlit (A88, #297): solo arma la navegación.

Las páginas, el layout, el estado de sesión y la caché del motor viven en `nutrigraphdt.demo`
(`nutrigraphdt.demo.app`). La app trabaja con la corrida sintética configurada en
`configs/platform.json` y no necesita la descarga de D1. Requiere los extras `graph`,
`baselines` y `demo`. Uso:

    pip install -e ".[graph,baselines,demo]"
    streamlit run scripts/demo_app.py

Ver docs/demo.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

# En Streamlit Community Cloud el proyecto no se instala: se importa desde src/.
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nutrigraphdt.demo.app import main  # noqa: E402

main()
