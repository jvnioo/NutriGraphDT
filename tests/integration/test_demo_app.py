"""Web App (A88, #297): navegación, layout común, estado de sesión y caché del motor.

Usa `streamlit.testing.v1.AppTest`, que ejecuta la app sin navegador ni red. Requiere los extras
`graph`, `baselines` y `demo`. Las páginas se registran con funciones, y `AppTest.switch_page`
solo cambia entre archivos: por eso las pruebas de cada página la dibujan con el mismo marco que
la app (`app.framed`) y eligen la página con una clave de prueba.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")
pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from streamlit.testing.v1 import AppTest  # noqa: E402

from nutrigraphdt.demo import app as web_app  # noqa: E402
from nutrigraphdt.demo import layout, state  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
TIMEOUT = 300
PAGE_KEY = "_test_page"


def _page_app() -> None:
    import streamlit as st

    from nutrigraphdt.demo import app, layout

    specs = {spec.url_path: spec for spec in app.PAGES}
    layout.sidebar()
    app.framed(specs[st.session_state.get("_test_page", "inicio")].render)()


def _text(at: AppTest) -> str:
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption]
    parts += [w.value for w in (*at.info, *at.success, *at.warning, *at.error)]
    return "\n".join(parts)


@pytest.fixture
def pages() -> AppTest:
    at = AppTest.from_function(_page_app, default_timeout=TIMEOUT)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def test_entry_point_opens_on_home_without_d1_download() -> None:
    at = AppTest.from_file(str(REPO_ROOT / "scripts" / "demo_app.py"), default_timeout=TIMEOUT)
    at.run()

    assert not at.exception, [str(e.value) for e in at.exception]
    assert layout.SYNTHETIC_LABEL in _text(at)
    assert "Corrida activa" in [s.value for s in at.subheader]


def test_entry_point_only_builds_the_navigation() -> None:
    source = (REPO_ROOT / "scripts" / "demo_app.py").read_text(encoding="utf-8")
    code = [line for line in source.splitlines() if line and not line.startswith(("#", " "))]
    assert "from nutrigraphdt.demo.app import main  # noqa: E402" in code
    assert "st." not in source


def test_navigation_has_the_planned_pages() -> None:
    assert [spec.url_path for spec in web_app.PAGES] == [
        "inicio",
        "escenario",
        "resultados",
        "grafo",
        "explicacion",
        "comparacion",
        "simulador",
    ]
    assert [spec.default for spec in web_app.PAGES].count(True) == 1


@pytest.mark.parametrize("url_path", [spec.url_path for spec in web_app.PAGES])
def test_every_page_opens_with_the_synthetic_label(pages: AppTest, url_path: str) -> None:
    pages.session_state[PAGE_KEY] = url_path
    pages.run()

    assert not pages.exception, [str(e.value) for e in pages.exception]
    text = _text(pages)
    assert layout.SYNTHETIC_LABEL in text
    assert "Contrato de la API v1.0.0" in text
    assert "commit `" in text


@pytest.mark.parametrize("url_path", ["escenario", "resultados", "grafo", "explicacion"])
def test_pending_pages_say_so_and_show_no_data(pages: AppTest, url_path: str) -> None:
    pages.session_state[PAGE_KEY] = url_path
    pages.run()

    assert pages.info and "Pendiente" in pages.info[0].value
    assert not pages.dataframe
    assert not pages.metric


def test_state_survives_page_changes_and_reset_clears_it(pages: AppTest) -> None:
    pages.session_state[state.SCENARIO] = "escenario-de-prueba"
    pages.session_state[state.RESULT] = "resultado-de-prueba"
    for url_path in ("resultados", "grafo", "inicio"):
        pages.session_state[PAGE_KEY] = url_path
        pages.run()
        assert pages.session_state[state.SCENARIO] == "escenario-de-prueba"
        assert pages.session_state[state.RESULT] == "resultado-de-prueba"

    pages.button(key="reset_state").click().run()

    assert not pages.exception
    assert state.SCENARIO not in pages.session_state
    assert state.RESULT not in pages.session_state
