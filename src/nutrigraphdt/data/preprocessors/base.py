"""Interfaz base y tipos comunes de la etapa de preprocesamiento (A34-4).

Un preprocesador recibe el `IngestionPayload` de un loader y devuelve registros del formato
tabular normalizado (`nutrigraphdt.data.schema`) junto con un informe de control de calidad.
El informe conserva cada registro descartado con su motivo, de modo que ninguna fila se pierde
sin dejar rastro.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from nutrigraphdt.data.loaders.base import IngestionPayload
from nutrigraphdt.data.schema import NormalizedFeatureRecord, NormalizedInstanceRecord

# Motivos de descarte registrados en `DiscardedRecord.reason`.
MISSING_VALUE: Final = "missing_value"
INVALID_RECORD: Final = "invalid_record"
DUPLICATE_RECORD: Final = "duplicate_record"
EMPTY_SAMPLE: Final = "empty_sample"
FILTERED_TAXON: Final = "filtered_taxon"

DISCARD_REASONS: Final[frozenset[str]] = frozenset(
    {MISSING_VALUE, INVALID_RECORD, DUPLICATE_RECORD, EMPTY_SAMPLE, FILTERED_TAXON}
)


def _json_safe(value: Any) -> Any:
    """Devuelve un valor serializable a JSON estándar (``NaN``/infinito pasan a texto)."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


@dataclass(frozen=True)
class DiscardedRecord:
    """Registro de entrada que no llegó a la salida normalizada.

    ``index`` es la posición del registro en ``IngestionPayload.raw_data`` y ``record`` una
    copia serializable del registro original, para poder rastrear la fila descartada.
    """

    index: int
    reason: str
    detail: str
    record: dict[str, Any]

    def __post_init__(self) -> None:
        if self.reason not in DISCARD_REASONS:
            raise ValueError(
                f"Motivo de descarte '{self.reason}' no válido. Permitidos: "
                f"{sorted(DISCARD_REASONS)}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serializa el descarte a un diccionario compatible con JSON."""
        return {
            "index": self.index,
            "reason": self.reason,
            "detail": self.detail,
            "record": _json_safe(self.record),
        }


@dataclass
class PreprocessingReport:
    """Informe de control de calidad del preprocesamiento de una fuente.

    Invariante: ``input_records == output_records + len(discarded)``. Los registros imputados
    llegan a la salida y se cuentan aparte en ``imputed_records``.
    """

    source_id: str
    parameters: dict[str, Any]
    input_records: int
    output_records: int
    imputed_records: int = 0
    discarded: list[DiscardedRecord] = field(default_factory=list)
    removed_taxa: dict[str, float] = field(default_factory=dict)
    loader_errors: list[str] = field(default_factory=list)

    def discarded_counts(self) -> dict[str, int]:
        """Cuenta los descartes por motivo, en orden alfabético de motivo."""
        counts: dict[str, int] = {}
        for item in self.discarded:
            counts[item.reason] = counts.get(item.reason, 0) + 1
        return dict(sorted(counts.items()))

    def summary(self) -> dict[str, Any]:
        """Resumen sin el detalle de cada fila, apto para los metadatos del dataset."""
        return {
            "source_id": self.source_id,
            "input_records": self.input_records,
            "output_records": self.output_records,
            "imputed_records": self.imputed_records,
            "discarded_records": len(self.discarded),
            "discarded_by_reason": self.discarded_counts(),
            "removed_taxa_count": len(self.removed_taxa),
            "loader_errors": len(self.loader_errors),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serializa el informe completo, incluidas las filas descartadas."""
        return {
            **self.summary(),
            "parameters": dict(self.parameters),
            "removed_taxa": dict(sorted(self.removed_taxa.items())),
            "discarded": [item.to_dict() for item in self.discarded],
            "loader_errors": list(self.loader_errors),
        }


@dataclass
class PreprocessedData:
    """Salida de un preprocesador: tablas normalizadas parciales e informe de calidad."""

    instances: list[NormalizedInstanceRecord]
    features: list[NormalizedFeatureRecord]
    report: PreprocessingReport


class BasePreprocessor(ABC):
    """Interfaz común de los preprocesadores del módulo de datos."""

    @abstractmethod
    def process(self, payload: IngestionPayload) -> PreprocessedData:
        """Transforma la salida de un loader en registros normalizados.

        No modifica ``payload``. Con la misma entrada y la misma configuración devuelve
        siempre la misma salida.
        """
        raise NotImplementedError
