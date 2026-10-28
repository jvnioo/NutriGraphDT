"""Elementos visuales compartidos por las páginas de la demo."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape
from typing import Final

import streamlit as st

# Identidad cromática del proyecto (docs/research/Esquema_General…): turquesas y azules.
TEAL: Final[str] = "#0E9987"
TEAL_LIGHT: Final[str] = "#25A3A8"
CYAN: Final[str] = "#087F9E"
BLUE: Final[str] = "#0767A0"
NAVY: Final[str] = "#032E54"
SAND: Final[str] = "#F6F4EE"
INK: Final[str] = "#14232E"
MUTED: Final[str] = "#5D6B75"
AMBER: Final[str] = "#D9973B"
CORAL: Final[str] = "#C8553D"

NODE_COLORS: Final[dict[str, str]] = {
    "diet": AMBER,
    "additive": CORAL,
    "substrate": "#8FA15B",
    "taxon": TEAL,
    "function": "#4FB7C9",
    "metabolite": BLUE,
    "host": NAVY,
    "phenotype": "#8E6C8A",
}

_CSS: Final[str] = f"""
<style>
:root {{ --ng-teal: {TEAL}; --ng-navy: {NAVY}; --ng-muted: {MUTED}; }}
.block-container {{ padding-top: 3.6rem; max-width: 1200px; }}
[data-testid="stSidebar"] {{ background: {NAVY}; }}
[data-testid="stSidebar"] * {{ color: #E8F1F2 !important; }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{ background: rgba(37,163,168,.22); }}
.ng-kicker {{ letter-spacing: .14em; text-transform: uppercase; font-size: .72rem;
  color: {MUTED}; margin-bottom: .2rem; }}
.ng-hero {{ font-family: Georgia, 'Times New Roman', serif; font-size: 2.6rem; line-height: 1.1;
  color: {NAVY}; margin: 0 0 .4rem 0; }}
.ng-lead {{ color: {MUTED}; font-size: 1.02rem; max-width: 52rem; margin-bottom: 1.2rem; }}
.ng-badge {{ display: inline-block; border-radius: 999px; padding: .15rem .7rem; font-size: .72rem;
  letter-spacing: .08em; text-transform: uppercase; margin-right: .4rem; border: 1px solid; }}
.ng-badge.synthetic {{ color: {CYAN}; border-color: {CYAN}; background: #E7F4F6; }}
.ng-badge.real {{ color: {TEAL}; border-color: {TEAL}; background: #E6F5F1; }}
.ng-card {{ background: white; border: 1px solid #E3E6E2; border-radius: 10px;
  padding: .9rem 1rem; height: 100%; }}
.ng-card .label {{ font-size: .72rem; letter-spacing: .1em; text-transform: uppercase;
  color: {MUTED}; }}
.ng-card .value {{ font-family: Georgia, serif; font-size: 2rem; color: {NAVY}; }}
.ng-card .help {{ font-size: .8rem; color: {MUTED}; }}
</style>
"""


CHART_CONFIG: Final[dict[str, object]] = {"displayModeBar": False}
"""Configuración de Plotly: sin barra de herramientas, que tapa los títulos."""


def inject_css() -> None:
    """Estilos de la demo (una vez por ejecución de la app)."""
    st.markdown(_CSS, unsafe_allow_html=True)


def hero(kicker: str, title: str, lead: str, badges: Sequence[tuple[str, str]] = ()) -> None:
    """Encabezado de página: rótulo, título, insignias y bajada."""
    badge_html = "".join(
        f'<span class="ng-badge {escape(kind)}">{escape(text)}</span>' for text, kind in badges
    )
    st.markdown(
        f'<div class="ng-kicker">{escape(kicker)}</div>'
        f'<div class="ng-hero">{escape(title)}</div>'
        f"<div>{badge_html}</div>"
        f'<div class="ng-lead">{escape(lead)}</div>',
        unsafe_allow_html=True,
    )


def metric_cards(items: Sequence[tuple[str, str, str]]) -> None:
    """Tarjetas de métricas: `(rótulo, valor, ayuda)` por tarjeta."""
    columns = st.columns(len(items))
    for column, (label, value, help_text) in zip(columns, items, strict=True):
        column.markdown(
            f'<div class="ng-card"><div class="label">{escape(label)}</div>'
            f'<div class="value">{escape(value)}</div>'
            f'<div class="help">{escape(help_text)}</div></div>',
            unsafe_allow_html=True,
        )


def badge(text: str, kind: str) -> str:
    """HTML de una insignia (`synthetic` o `real`)."""
    return f'<span class="ng-badge {escape(kind)}">{escape(text)}</span>'


__all__ = [
    "AMBER",
    "BLUE",
    "CHART_CONFIG",
    "CORAL",
    "CYAN",
    "MUTED",
    "NAVY",
    "NODE_COLORS",
    "TEAL",
    "TEAL_LIGHT",
    "badge",
    "hero",
    "inject_css",
    "metric_cards",
]
