"""Versiones en caché de `nutrigraphdt.demo.data` para las páginas.

Los datos de entrada no cambian durante la demo, así que se calculan una vez por proceso:
`st.cache_resource` para objetos (datasets, grafos) y `st.cache_data` para resultados
serializables.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from nutrigraphdt.demo import data


@st.cache_resource(show_spinner="Generando los escenarios sintéticos…")
def scenarios() -> Any:
    return data.synthetic_scenarios()


@st.cache_resource(
    show_spinner="Cargando los animales reales de D1 (unos segundos la primera vez)…"
)
def d1_records() -> data.D1Records:
    return data.d1_records()


@st.cache_data(show_spinner=False)
def d1_agcc() -> list[dict[str, Any]]:
    return data.agcc_by_animal(d1_records().records)


@st.cache_data(show_spinner=False)
def baseline_report(directory: str) -> dict[str, Any]:
    return data.baseline_report(Path(directory))


@st.cache_data(show_spinner="Leyendo el reporte de los grafos de D1…")
def d1_graph_report() -> dict[str, Any] | None:
    return data.d1_graph_report()


@st.cache_data(show_spinner=False)
def gnn_synthetic_rows() -> list[dict[str, str]] | None:
    return data.gnn_synthetic_rows()


__all__ = [
    "baseline_report",
    "d1_agcc",
    "d1_graph_report",
    "d1_records",
    "gnn_synthetic_rows",
    "scenarios",
]
