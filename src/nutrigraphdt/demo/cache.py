"""Recursos en caché de la Web App (A88-P3, #300) y de la página de comparación.

Los datos de entrada no cambian durante la demo, así que se calculan una vez por proceso:
`st.cache_resource` para objetos (el `ScenarioEngine`, datasets, grafos) y `st.cache_data` para
resultados serializables (`run.json`, métricas y versión del contrato).

`ENGINE_LOADS` cuenta cuántas veces se construyó un motor en este proceso: la prueba de A88-P3
exige que sea una sola vez por corrida.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import streamlit as st

from nutrigraphdt.demo import data, platform

ENGINE_LOADS: Counter[str] = Counter()
"""Motores construidos en este proceso, por corrida."""


@st.cache_resource(show_spinner="Cargando la corrida congelada (unos segundos la primera vez)…")
def engine(run: str) -> Any:
    """`ScenarioEngine` de la corrida `run`, cargado una vez por proceso del servidor."""
    from nutrigraphdt import api

    ENGINE_LOADS[run] += 1
    return api.DEMO_RUNS[run].engine()


@st.cache_data(show_spinner=False)
def run_metadata(run: str) -> dict[str, Any]:
    """`run.json`, métricas y versión del contrato de la corrida, sin cargar el modelo."""
    return platform.run_metadata(run)


def active_run() -> str:
    """Corrida activa según `configs/platform.json` o `NUTRIGRAPHDT_RUN`."""
    return platform.active_run_name()


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


@st.cache_data(show_spinner="Leyendo el reporte de los grafos de D1…")
def d1_graph_report() -> dict[str, Any] | None:
    return data.d1_graph_report()


@st.cache_data(show_spinner=False)
def synthetic_features() -> dict[str, list[str]]:
    from nutrigraphdt.demo.graph_comparison import feature_columns

    return feature_columns(scenarios())


__all__ = [
    "ENGINE_LOADS",
    "active_run",
    "engine",
    "run_metadata",
    "d1_agcc",
    "d1_graph_report",
    "d1_records",
    "scenarios",
    "synthetic_features",
]
