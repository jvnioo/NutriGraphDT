"""Prueba de humo de la demo: cada página se dibuja sin excepciones.

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
PAGES = ("summary", "datasets", "graph", "validation", "baselines", "models", "training", "process")
TIMEOUT = 120


def _render_page(module_name: str) -> None:
    import importlib

    from nutrigraphdt.demo import ui

    ui.inject_css()
    importlib.import_module(f"nutrigraphdt.demo.pages.{module_name}").render()


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exceptions(page: str) -> None:
    app = AppTest.from_function(_render_page, args=(page,), default_timeout=TIMEOUT)

    app.run()

    assert not app.exception, [str(item.value) for item in app.exception]


def test_entry_point_opens_on_the_summary() -> None:
    app = AppTest.from_file(str(REPO_ROOT / "scripts" / "demo_app.py"), default_timeout=TIMEOUT)

    app.run()

    assert not app.exception, [str(item.value) for item in app.exception]
    assert any("gemelo digital" in item.value.lower() for item in app.markdown)
