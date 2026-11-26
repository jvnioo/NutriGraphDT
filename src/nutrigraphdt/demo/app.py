"""Navegación de la Web App (A88-P1, #298).

`scripts/demo_app.py` solo llama a `main()`. Cada página es una función `render()` de
`nutrigraphdt.demo.pages` y se dibuja entre el encabezado y el pie comunes de `layout`. Las
páginas que aún no existen dicen «pendiente» (`pages.pending`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import streamlit as st

from nutrigraphdt.demo import layout, ui
from nutrigraphdt.demo.pages import (
    graph,
    graph_comparison,
    home,
    pending,
    results,
    scenario,
    scenario_simulator,
)

LOGO: Final[Path] = Path(ui.__file__).parent / "assets" / "logo.svg"


@dataclass(frozen=True)
class PageSpec:
    title: str
    url_path: str
    render: Callable[[], None]
    default: bool = False


PAGES: Final[tuple[PageSpec, ...]] = (
    PageSpec("Inicio", "inicio", home.render, default=True),
    PageSpec("Escenario", "escenario", scenario.render),
    PageSpec("Resultados", "resultados", results.render),
    PageSpec("Grafo", "grafo", graph.render),
    PageSpec(
        "Explicación",
        "explicacion",
        pending.page(
            "Explicación",
            "Subgrafo explicativo e importancias del explicador.",
            "A104 (#334)",
        ),
    ),
    PageSpec("Sintético frente a D1", "comparacion", graph_comparison.render),
    PageSpec("Simulador (A81, demostración)", "simulador", scenario_simulator.render),
)


def framed(render: Callable[[], None]) -> Callable[[], None]:
    def page() -> None:
        layout.header()
        render()
        layout.footer()

    page.__name__ = f"page_{render.__name__}"
    return page


def main() -> None:
    """Configura la app, dibuja la barra lateral y ejecuta la página elegida."""
    st.set_page_config(page_title="NutriGraphDT", page_icon="🧬", layout="wide")
    st.logo(str(LOGO), size="large")
    ui.inject_css()
    layout.sidebar()
    navigation = st.navigation(
        [
            st.Page(
                framed(spec.render), title=spec.title, url_path=spec.url_path, default=spec.default
            )
            for spec in PAGES
        ]
    )
    navigation.run()


__all__ = ["PAGES", "PageSpec", "framed", "main"]
