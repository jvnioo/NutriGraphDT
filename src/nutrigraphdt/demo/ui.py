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
.ng-badge.pending {{ color: #8A5A12; border-color: {AMBER}; background: #FBF1E2; }}
.ng-badge.done {{ color: #1D6B46; border-color: #2F9E6A; background: #E7F6EE; }}
.ng-card {{ background: white; border: 1px solid #E3E6E2; border-radius: 10px;
  padding: .9rem 1rem; height: 100%; }}
.ng-card .label {{ font-size: .72rem; letter-spacing: .1em; text-transform: uppercase;
  color: {MUTED}; }}
.ng-card .value {{ font-family: Georgia, serif; font-size: 2rem; color: {NAVY}; }}
.ng-card .help {{ font-size: .8rem; color: {MUTED}; }}
.ng-note {{ border-left: 4px solid {TEAL}; background: #EEF6F4; padding: .7rem 1rem;
  border-radius: 6px; color: {INK}; font-size: .92rem; margin: .6rem 0 1rem 0; }}
.ng-note.warn {{ border-color: {AMBER}; background: #FBF4E8; }}
.ng-step {{ background: white; border: 1px solid #E3E6E2; border-radius: 10px; padding: .8rem;
  min-height: 9.5rem; }}
.ng-step .num {{ font-family: Georgia, serif; color: {TEAL_LIGHT}; font-size: 1.4rem; }}
.ng-step .title {{ font-weight: 600; color: {NAVY}; }}
.ng-step .text {{ font-size: .82rem; color: {MUTED}; }}
.ng-section {{ display: flex; gap: .9rem; align-items: baseline; margin: 2.2rem 0 .3rem 0; }}
.ng-section .n {{ font-family: Georgia, serif; font-size: 2rem; color: {TEAL_LIGHT}; }}
.ng-section .t {{ font-size: 1.45rem; font-weight: 650; color: {NAVY}; }}
.ng-intro {{ color: {INK}; font-size: 1rem; max-width: 56rem; margin-bottom: .8rem; }}
.ng-read {{ background: white; border: 1px dashed #B9C7C4; border-radius: 8px;
  padding: .6rem .9rem; font-size: .9rem; color: {INK}; margin: .2rem 0 1rem 0; }}
.ng-takeaway {{ font-size: 1.02rem; color: {NAVY}; background: #E9F5F2;
  border-radius: 8px; padding: .55rem .9rem; margin: .2rem 0 .5rem 0; }}
.ng-read b.h {{ color: {TEAL}; letter-spacing: .06em; text-transform: uppercase;
  font-size: .72rem; display: block; margin-bottom: .2rem; }}
.ng-legend {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .6rem;
  margin: .4rem 0 1rem 0; }}
.ng-legend div {{ background: white; border: 1px solid #E3E6E2; border-radius: 8px;
  padding: .55rem .7rem; font-size: .85rem; color: {INK}; }}
.ng-legend .sym {{ font-size: 1.2rem; margin-right: .35rem; }}
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


def note(text: str, *, warn: bool = False) -> None:
    """Recuadro de aclaración (`warn=True` para advertencias metodológicas)."""
    css = "ng-note warn" if warn else "ng-note"
    st.markdown(f'<div class="{css}">{text}</div>', unsafe_allow_html=True)


def badge(text: str, kind: str) -> str:
    """HTML de una insignia (`synthetic`, `real`, `pending`, `done`)."""
    return f'<span class="ng-badge {escape(kind)}">{escape(text)}</span>'


def steps(items: Sequence[tuple[str, str, str]], *, per_row: int = 4) -> None:
    """Pasos numerados en filas de `per_row`: `(título, texto, estado)`; `done` o `pending`."""
    for start in range(0, len(items), per_row):
        row = items[start : start + per_row]
        columns = st.columns(per_row)
        for offset, (column, (title, text, state)) in enumerate(zip(columns, row, strict=False)):
            label = "Listo" if state == "done" else "Pendiente"
            column.markdown(
                f'<div class="ng-step"><div class="num">{start + offset + 1:02d}</div>'
                f'<div class="title">{escape(title)}</div>'
                f'<div class="text">{escape(text)}</div><div style="margin-top:.5rem">'
                f"{badge(label, state)}</div></div>",
                unsafe_allow_html=True,
            )
        if start + per_row < len(items):
            st.write("")


def section(number: int, title: str, intro: str = "") -> None:
    """Encabezado de sección numerada, con una bajada opcional (admite HTML)."""
    st.markdown(
        f'<div class="ng-section"><span class="n">{number}</span>'
        f'<span class="t">{escape(title)}</span></div>'
        + (f'<div class="ng-intro">{intro}</div>' if intro else ""),
        unsafe_allow_html=True,
    )


def takeaway(text: str) -> None:
    """La idea clave de un gráfico, en una línea siempre visible (admite HTML)."""
    st.markdown(f'<div class="ng-takeaway">💡 {text}</div>', unsafe_allow_html=True)


def how_to_read(text: str, *, expanded: bool = False) -> None:
    """Explicación detallada de un gráfico, plegada bajo "Cómo leer este gráfico"."""
    with st.expander("Cómo leer este gráfico", expanded=expanded):
        st.markdown(f'<div class="ng-read">{text}</div>', unsafe_allow_html=True)


def legend(items: Sequence[tuple[str, str]]) -> None:
    """Fila de símbolos explicados: `(símbolo, texto HTML)`."""
    cells = "".join(f'<div><span class="sym">{sym}</span>{text}</div>' for sym, text in items)
    st.markdown(f'<div class="ng-legend">{cells}</div>', unsafe_allow_html=True)


GLOSSARY: Final[tuple[tuple[str, str], ...]] = (
    (
        "AGCC",
        "Ácidos grasos de cadena corta (acetato, propionato, butirato): los produce la "
        "microbiota al fermentar la dieta. Son lo que el modelo intenta predecir.",
    ),
    ("Grafo", "Red de entidades (nodos) unidas por relaciones (aristas)."),
    (
        "GNN",
        "Red neuronal de grafos: aprende combinando la información de cada nodo con la de "
        "sus vecinos.",
    ),
    ("Baseline", "Modelo simple de referencia. Si la GNN no lo supera, no aporta."),
    (
        "train / val / test",
        "Animales para aprender, para elegir la mejor versión y para el "
        "examen final, respectivamente.",
    ),
    ("RMSE", "Error típico de la predicción, en mmol/kg. Menor es mejor."),
    (
        "R²",
        "Cuánto mejor que predecir la media: 1 es perfecto, 0 es igual a la media, negativo "
        "es peor.",
    ),
    ("Época", "Una pasada completa del modelo por todos los animales de train."),
)


def glossary() -> None:
    """Glosario breve en la barra lateral."""
    with st.sidebar.expander("📖 Glosario de términos", expanded=False):
        for term, meaning in GLOSSARY:
            st.markdown(f"**{term}.** {meaning}")


__all__ = [
    "AMBER",
    "BLUE",
    "CHART_CONFIG",
    "CORAL",
    "CYAN",
    "GLOSSARY",
    "MUTED",
    "NAVY",
    "NODE_COLORS",
    "TEAL",
    "TEAL_LIGHT",
    "badge",
    "glossary",
    "how_to_read",
    "hero",
    "inject_css",
    "legend",
    "metric_cards",
    "note",
    "section",
    "steps",
    "takeaway",
]
