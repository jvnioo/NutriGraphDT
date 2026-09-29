"""Utilidades compartidas por los validadores de registros (VG-02 en adelante).

Los validadores aceptan dataclasses del paquete de datos o diccionarios con la forma de una
línea JSONL, y transcriben los valores observados para el reporte. Estas funciones concentran
esos criterios para que todos los validadores los apliquen igual.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any, Final, TypeGuard

from nutrigraphdt.data.synthetic.edges import Edge
from nutrigraphdt.data.synthetic.export import InstanceRecord, OutputRecord
from nutrigraphdt.data.synthetic.nodes import Node

ABSENT: Final = object()
"""Marca una clave inexistente, para distinguirla de una clave con valor `null`."""


def is_text(value: object) -> TypeGuard[str]:
    """Cadena no vacía: DS-01 prohíbe representar un valor ausente con una cadena vacía."""
    return isinstance(value, str) and value != ""


def is_finite_number(value: object) -> TypeGuard[float]:
    """Número JSON finito. Un booleano no cuenta como número."""
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def describe(value: object) -> str:
    """Transcribe un valor observado para el reporte, en notación JSON cuando es posible."""
    if value is ABSENT:
        return "campo ausente"
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return repr(value)


def as_record(record: object) -> Mapping[str, Any] | None:
    """Registro como diccionario; `None` si no es un registro ni un objeto JSON."""
    if isinstance(record, Node | InstanceRecord | Edge | OutputRecord):
        return record.to_dict()
    if isinstance(record, Mapping):
        return record
    return None


def declared_vocabularies(
    metadata: Mapping[str, Any] | None,
) -> dict[str, frozenset[str]] | None:
    """Vocabularios declarados en `metadata.json`; `None` si no se entregan los metadatos.

    Un vocabulario que no está declarado, o cuyo valor no es una lista, se trata como vacío.
    """
    if metadata is None:
        return None
    declared = metadata.get("vocabularies")
    if not isinstance(declared, dict):
        return {}
    return {
        str(name): frozenset(value for value in values if isinstance(value, str))
        for name, values in declared.items()
        if isinstance(values, list)
    }
