"""Layout común de la Web App (A88-P2, #299): rótulo de datos, pie y reinicio del estado.

Toda página se dibuja entre `header()` y `footer()` (lo hace `nutrigraphdt.demo.app`), así que el
rótulo permanente de datos sintéticos aparece en todas, sin que cada página lo repita.
"""

from __future__ import annotations

from html import escape
from typing import Any, Final

import streamlit as st

from nutrigraphdt.demo import cache, state

SYNTHETIC_LABEL: Final[str] = "Datos sintéticos: no describen animales reales"
"""Rótulo permanente de la interfaz (alcance final, #296, sección 6)."""
CAUSAL_NOTE: Final[str] = "Un escenario es una predicción del modelo, no un efecto causal."
RESET_LABEL: Final[str] = "Reiniciar el escenario"

_BANNER_CSS: Final[str] = (
    "background:#E7F4F6;border:1px solid #087F9E;color:#032E54;border-radius:8px;"
    "padding:.45rem .8rem;margin-bottom:1rem;font-size:.86rem"
)


def _metadata() -> dict[str, Any] | None:
    try:
        return cache.run_metadata(cache.active_run())
    except (OSError, KeyError, ValueError):
        return None


def header() -> None:
    """Rótulo de datos sintéticos y nota de causalidad, arriba de cada página."""
    st.markdown(
        f'<div class="ng-banner" style="{_BANNER_CSS}"><strong>{escape(SYNTHETIC_LABEL)}.</strong> '
        f"{escape(CAUSAL_NOTE)}</div>",
        unsafe_allow_html=True,
    )


def footer() -> None:
    """Versión del contrato, corrida activa y commit con que se entrenó."""
    metadata = _metadata()
    st.divider()
    if metadata is None:
        st.caption("Corrida activa: no se pudo leer la configuración de la plataforma.")
        return
    commit = (metadata["commit"] or "sin registrar")[:12]
    st.caption(
        f"Contrato de la API v{metadata['contract_version']} · corrida `{metadata['run_id']}` "
        f"({metadata['label']}) · commit `{commit}`"
    )


def sidebar() -> None:
    """Barra lateral: créditos y acción para reiniciar el estado de la sesión."""
    with st.sidebar:
        st.caption("Gemelo digital nutricional basado en grafos · PIA-2, sección 302, UTEM")
        st.caption("Prototipo académico de factibilidad computacional.")
        if st.button(RESET_LABEL, key="reset_state", help="Borra el escenario y el resultado."):
            state.reset()
            st.toast("Se borró el escenario y el resultado.")


__all__ = ["CAUSAL_NOTE", "RESET_LABEL", "SYNTHETIC_LABEL", "footer", "header", "sidebar"]
