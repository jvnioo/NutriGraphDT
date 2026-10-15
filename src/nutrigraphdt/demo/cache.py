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


@st.cache_resource(show_spinner="Generando la cohorte sintética…")
def cohort(n_samples: int = 50) -> Any:
    return data.synthetic_cohort(n_samples)


@st.cache_resource(show_spinner="Construyendo los grafos del fixture de D1…")
def d1_fixture() -> Any:
    return data.d1_fixture()


@st.cache_data(show_spinner=False)
def synthetic_validation() -> dict[str, Any]:
    return data.validation_summary(data.synthetic_validation(scenarios()))


@st.cache_data(show_spinner=False)
def d1_validation() -> dict[str, Any]:
    _, audit = d1_fixture()
    return data.validation_summary(audit.report.to_dict())


@st.cache_data(show_spinner=False)
def split_summary() -> dict[str, Any]:
    return data.split_summary()


@st.cache_data(show_spinner=False)
def baseline_report(directory: str) -> dict[str, Any]:
    return data.baseline_report(Path(directory))


@st.cache_data(show_spinner="Construyendo las tres variantes…")
def model_overview() -> list[dict[str, Any]]:
    return data.model_overview(data.synthetic_metadata())


@st.cache_data(show_spinner=False)
def overfit_results() -> dict[str, Any] | None:
    return data.overfit_results()


@st.cache_data(show_spinner=False)
def rule_catalog() -> dict[str, dict[str, str]]:
    return data.rule_catalog()


@st.cache_data(show_spinner=False)
def devices() -> list[str]:
    return data.available_devices()


__all__ = [
    "baseline_report",
    "cohort",
    "d1_fixture",
    "d1_validation",
    "devices",
    "model_overview",
    "overfit_results",
    "rule_catalog",
    "scenarios",
    "split_summary",
    "synthetic_validation",
]
