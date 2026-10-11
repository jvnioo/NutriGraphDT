"""Módulo de partición para modelos y baselines (A40-1, #71).

Reexporta las funciones canónicas de partición desde `nutrigraphdt.data.split`.
"""

from nutrigraphdt.data.split import (
    DatasetSplit,
    create_split,
    get_split,
    load_split,
    save_split,
)

__all__ = [
    "DatasetSplit",
    "create_split",
    "get_split",
    "load_split",
    "save_split",
]
