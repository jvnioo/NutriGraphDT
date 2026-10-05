"""Interfaz base y tipos comunes para los cargadores de datos de NutriGraphDT."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nutrigraphdt.data.schema import ALLOWED_GUT_SEGMENTS, ALLOWED_SPECIES


@dataclass
class SourceMetadata:
    """Metadatos de una fuente de datos registrada en configs/sources.json."""

    source_id: str
    name: str
    species: str
    gut_segment: str
    data_types: tuple[str, ...]
    format: str
    path_or_url: str | None = None
    is_synthetic: bool = False
    version: str = "1.0.0"
    description: str = ""
    citation_or_url: str = ""
    options: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("El identificador 'source_id' no puede estar vacío.")
        if not self.name:
            raise ValueError("El nombre 'name' no puede estar vacío.")
        if not self.species:
            raise ValueError("La especie 'species' no puede estar vacía.")
        if self.species not in ALLOWED_SPECIES:
            raise ValueError(
                f"Especie '{self.species}' no válida. Permitidas: {sorted(ALLOWED_SPECIES)}"
            )
        if not self.gut_segment:
            raise ValueError("El segmento 'gut_segment' no puede estar vacío.")
        if self.gut_segment not in ALLOWED_GUT_SEGMENTS:
            allowed = sorted(ALLOWED_GUT_SEGMENTS)
            raise ValueError(f"Segmento '{self.gut_segment}' no válido. Permitidos: {allowed}")
        if not self.format:
            raise ValueError("El formato 'format' no puede estar vacío.")
        if not self.data_types:
            raise ValueError("Debe especificarse al menos un tipo en 'data_types'.")

    def to_dict(self) -> dict[str, Any]:
        """Serializa los metadatos a diccionario."""
        return {
            "source_id": self.source_id,
            "name": self.name,
            "species": self.species,
            "gut_segment": self.gut_segment,
            "data_types": list(self.data_types),
            "format": self.format,
            "path_or_url": self.path_or_url,
            "is_synthetic": self.is_synthetic,
            "version": self.version,
            "description": self.description,
            "citation_or_url": self.citation_or_url,
            "options": self.options,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SourceMetadata:
        """Crea una instancia desde un diccionario validando tipos básicos."""
        source_id = data["source_id"]
        name = data["name"]
        species = data["species"]
        gut_segment = data["gut_segment"]
        raw_types = data["data_types"]
        if not isinstance(raw_types, (list, tuple)):
            raise TypeError("El campo 'data_types' debe ser una lista o tupla.")
        data_types = tuple(str(t) for t in raw_types)
        fmt = data["format"]
        path_or_url = data.get("path_or_url", None)
        is_synthetic = data.get("is_synthetic", False)
        version = data.get("version", "1.0.0")
        description = data.get("description", "")
        citation_or_url = data.get("citation_or_url", "")
        raw_options = data.get("options", {})
        options = dict(raw_options) if raw_options else {}
        return cls(
            source_id=source_id,
            name=name,
            species=species,
            gut_segment=gut_segment,
            data_types=data_types,
            format=fmt,
            path_or_url=path_or_url,
            is_synthetic=is_synthetic,
            version=version,
            description=description,
            citation_or_url=citation_or_url,
            options=options,
        )


@dataclass
class IngestionPayload:
    """Contenedor de datos sin procesar resultantes de la ingesta de una fuente."""

    metadata: SourceMetadata
    raw_data: Any
    records_count: int
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.records_count < 0:
            raise ValueError("records_count no puede ser negativo.")


class BaseLoader(ABC):
    """Interfaz abstracta común para todos los cargadores de datos."""

    def __init__(self, metadata: SourceMetadata) -> None:
        """Inicializa el loader con los metadatos de su fuente."""
        self._metadata = metadata

    @property
    def metadata(self) -> SourceMetadata:
        """Metadatos de la fuente asociada al loader."""
        return self._metadata

    @abstractmethod
    def load(self, source_path: Path | str | None = None) -> IngestionPayload:
        """Carga y devuelve los datos crudos estructurados en un IngestionPayload.

        Parameters
        ----------
        source_path : Path | str | None
            Ruta local o referencia a los archivos de datos. Si es None, utiliza
            el valor definido en `self.metadata.path_or_url`.

        Returns
        -------
        IngestionPayload
            Carga de datos crudos acompañada de sus metadatos de procedencia.
        """
        raise NotImplementedError

    def resolve_path(self, source_path: Path | str | None = None) -> Path:
        """Resuelve y verifica la existencia de la ruta del archivo o directorio."""
        # Usar comparación explícita con None para no descartar Path("") u otros
        # valores falsy válidos que source_path pueda representar.
        target = source_path if source_path is not None else self.metadata.path_or_url
        if target is None:
            raise ValueError(
                f"No se proporcionó una ruta para la fuente '{self.metadata.source_id}'"
                " ni está definida en sus metadatos."
            )
        path = Path(target)
        if not path.exists():
            raise FileNotFoundError(
                f"No se encontró la ruta de datos para '{self.metadata.source_id}': {path}"
            )
        return path


class LoaderRegistry:
    """Registro de loaders por formato o source_id."""

    def __init__(self) -> None:
        self._by_format: dict[str, type[BaseLoader]] = {}
        self._by_source: dict[str, type[BaseLoader]] = {}

    def register_format(self, fmt: str, loader_cls: type[BaseLoader]) -> None:
        """Registra una clase de loader para un formato específico (ej. 'jsonl', 'tsv')."""
        self._by_format[fmt] = loader_cls

    def register_source(self, source_id: str, loader_cls: type[BaseLoader]) -> None:
        """Registra una clase de loader para una fuente específica."""
        self._by_source[source_id] = loader_cls

    def get_loader(self, metadata: SourceMetadata) -> BaseLoader:
        """Instancia el loader adecuado según el source_id o el formato configurado."""
        loader_cls = self._by_source.get(metadata.source_id) or self._by_format.get(metadata.format)
        if loader_cls is None:
            raise KeyError(
                f"No existe un loader registrado para el source_id '{metadata.source_id}'"
                f" ni para el formato '{metadata.format}'."
            )
        return loader_cls(metadata)


_TRUE_STRINGS = frozenset({"true", "1", "yes", "si", "sí"})
_FALSE_STRINGS = frozenset({"false", "0", "no"})


def parse_bool_option(value: Any, option_name: str = "option") -> bool:
    """Interpreta una opción booleana de `SourceMetadata.options`.

    Acepta booleanos, los enteros 0 y 1 y los textos ``true``/``false``, ``1``/``0``,
    ``yes``/``no`` y ``si``/``no`` sin distinguir mayúsculas. Cualquier otro valor levanta
    `ValueError`: ``bool("false")`` sería verdadero y activaría la opción en silencio.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in _TRUE_STRINGS:
            return True
        if text in _FALSE_STRINGS:
            return False
    raise ValueError(f"La opción '{option_name}' debe ser booleana; se recibió {value!r}.")


def validate_finite_number(value: Any, field_name: str = "value") -> float:
    """Valida que el valor sea un número finito y lo devuelve como float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"'{field_name}' debe ser numérico, se recibió {type(value).__name__}.")
    if not math.isfinite(value):
        raise ValueError(f"'{field_name}' debe ser un número finito, se recibió {value!r}.")
    return float(value)
