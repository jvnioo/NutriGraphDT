"""Estado de sesión de la Web App, tipado y en un solo lugar (A88-P2, #299).

Las páginas de escenario, resultados, grafo y explicación comparten el escenario en edición, el
último resultado y la corrida activa. Ninguna página escribe una clave de `st.session_state` a
mano: usan estas funciones, así una clave no se escribe dos veces con nombres distintos.
"""

from __future__ import annotations

from typing import Any, Final

import streamlit as st

PREFIX: Final[str] = "ng_"
SCENARIO: Final[str] = "ng_scenario"
"""Escenario en edición: un `ScenarioRequest` del contrato de `nutrigraphdt.api`."""
RESULT: Final[str] = "ng_result"
"""Último resultado: la comparación basal / intervenido (`ScenarioComparison`, A93)."""
ACTIVE_RUN: Final[str] = "ng_active_run"
"""Nombre de la corrida activa (clave de `DEMO_RUNS`)."""

KEYS: Final[tuple[str, ...]] = (SCENARIO, RESULT, ACTIVE_RUN)


def get(key: str, default: Any = None) -> Any:
    """Lee una clave conocida del estado de la sesión de Streamlit."""
    _check(key)
    return st.session_state.get(key, default)


def put(key: str, value: Any) -> None:
    """Guarda una clave conocida en el estado de la sesión de Streamlit."""
    _check(key)
    st.session_state[key] = value


def scenario() -> Any:
    """Escenario en edición de la sesión, o `None`."""
    return get(SCENARIO)


def result() -> Any:
    """Último resultado de simulación de la sesión, o `None`."""
    return get(RESULT)


def set_scenario(request: Any) -> None:
    """Guarda el escenario en edición; un escenario nuevo invalida el resultado anterior."""
    if get(SCENARIO) != request:
        put(RESULT, None)
    put(SCENARIO, request)


def set_result(comparison: Any) -> None:
    """Guarda el último resultado de simulación de la sesión."""
    put(RESULT, comparison)


def reset() -> None:
    """Borra el escenario, el resultado y todo widget con prefijo `ng_`."""
    for key in [k for k in st.session_state if str(k).startswith(PREFIX)]:
        del st.session_state[key]


def _check(key: str) -> None:
    if key not in KEYS:
        raise KeyError(f"{key!r} no es una clave de estado de la app; use una de {KEYS}.")


__all__ = [
    "ACTIVE_RUN",
    "KEYS",
    "PREFIX",
    "RESULT",
    "SCENARIO",
    "get",
    "put",
    "reset",
    "result",
    "scenario",
    "set_result",
    "set_scenario",
]
