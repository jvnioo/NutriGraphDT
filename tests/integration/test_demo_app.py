"""Prueba de humo de la demo: la página de comparación se dibuja sin excepciones.

Usa `streamlit.testing.v1.AppTest`, que ejecuta la app sin navegador. Requiere los extras
`graph` y `demo`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from streamlit.testing.v1 import AppTest  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
TIMEOUT = 120


def test_entry_point_opens_on_the_comparison_page() -> None:
    app = AppTest.from_file(str(REPO_ROOT / "scripts" / "demo_app.py"), default_timeout=TIMEOUT)

    app.run()

    assert not app.exception, [str(item.value) for item in app.exception]
    assert any("sintético frente a d1" in item.value.lower() for item in app.markdown)
