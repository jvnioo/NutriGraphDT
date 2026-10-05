"""Lectura del registro de fuentes de datos (`configs/sources.json`, A34-1)."""

from __future__ import annotations

import json
from pathlib import Path

from nutrigraphdt.data.loaders.base import SourceMetadata

DEFAULT_SOURCES_PATH = Path("configs") / "sources.json"


def load_sources(path: Path | str = DEFAULT_SOURCES_PATH) -> dict[str, SourceMetadata]:
    """Lee el registro de fuentes y devuelve un `SourceMetadata` validado por `source_id`.

    Falla con `ValueError` si la clave de una fuente no coincide con su `source_id`, para que
    el registro no pueda referirse a una fuente con dos nombres distintos.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    sources = data.get("sources")
    if not isinstance(sources, dict):
        raise ValueError(f"{path}: el campo 'sources' debe ser un objeto.")
    registry: dict[str, SourceMetadata] = {}
    for key, entry in sources.items():
        metadata = SourceMetadata.from_dict(entry)
        if metadata.source_id != key:
            raise ValueError(f"{path}: la fuente '{key}' declara source_id '{metadata.source_id}'.")
        registry[key] = metadata
    return registry
