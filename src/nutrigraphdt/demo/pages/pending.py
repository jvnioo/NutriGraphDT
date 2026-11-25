"""Páginas de la Web App que aún no están implementadas (A88-P1, #298).

Dicen «pendiente», nombran la actividad que las implementa y no muestran datos de relleno.
"""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from nutrigraphdt.demo import ui

PENDING_LABEL = "Pendiente"


def page(title: str, lead: str, activity: str) -> Callable[[], None]:
    """Función `render()` de una página pendiente."""

    def render() -> None:
        ui.hero(title, title, lead, badges=[(PENDING_LABEL, "synthetic")])
        st.info(f"{PENDING_LABEL}: esta página la implementa {activity}. Aún no muestra datos.")

    render.__name__ = f"render_{title.lower().replace(' ', '_')}"
    return render


__all__ = ["PENDING_LABEL", "page"]
