"""Docstrings de la API pública (A120-P2, #353).

Toda función y clase pública definida en un módulo de `nutrigraphdt` tiene docstring, y todo
módulo tiene el suyo. Las páginas de Streamlit (`nutrigraphdt.demo.pages`) se excluyen: solo
exponen `render()`. Requiere los extras `graph`, `baselines` y `demo` para importar todo.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")
pytest.importorskip("streamlit")
pytest.importorskip("plotly")

import nutrigraphdt  # noqa: E402

EXCLUDED_PREFIXES = ("nutrigraphdt.demo.pages",)


def _modules() -> list[str]:
    names = ["nutrigraphdt"]
    for info in pkgutil.walk_packages(nutrigraphdt.__path__, "nutrigraphdt."):
        if not info.name.startswith(EXCLUDED_PREFIXES):
            names.append(info.name)
    return names


def _missing(name: str) -> list[str]:
    module = importlib.import_module(name)
    missing = [] if (module.__doc__ or "").strip() else [f"{name} (módulo)"]
    public = getattr(module, "__all__", None) or [n for n in vars(module) if not n.startswith("_")]
    for attribute in public:
        value = getattr(module, attribute, None)
        defined_here = getattr(value, "__module__", None) == name
        is_api = inspect.isfunction(value) or inspect.isclass(value)
        if is_api and defined_here and not (value.__doc__ or "").strip():
            missing.append(f"{name}.{attribute}")
    return missing


def test_every_public_function_and_class_has_a_docstring() -> None:
    missing = [item for name in _modules() for item in _missing(name)]
    assert missing == []


def test_public_api_modules_are_covered() -> None:
    modules = set(_modules())
    for name in ("nutrigraphdt.api.contract", "nutrigraphdt.api.engine", "nutrigraphdt.simulation"):
        assert name in modules
