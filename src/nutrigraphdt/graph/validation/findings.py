"""Estructura común de los hallazgos de integridad del grafo.

Implementa las severidades y la "Estructura de un hallazgo" de
`docs/graph-integrity-rules.md` (VG-01). Los validadores de VG-02 a VG-05 producen `Finding`;
VG-07 los consolida en el reporte y decide su efecto en el pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    """Severidad de un hallazgo, con los valores literales de la especificación."""

    ERROR = "ERROR"
    """Se incumple el contrato o la integridad computacional: el grafo no llega al modelo."""

    WARNING = "ADVERTENCIA"
    """Condición que el contrato admite, pero que requiere revisión humana."""

    INFO = "INFO"
    """Excepción admitida explícitamente por la especificación; solo se registra."""


@dataclass(frozen=True)
class Finding:
    """Incumplimiento de una regla de integridad en un grafo concreto.

    `graph_id` es `None` cuando el hallazgo es de nivel dataset o cuando el registro afectado no
    tiene un `graph_id` utilizable; en ese caso, `location` lo identifica por su posición.
    `location` solo contiene valores compatibles con JSON. `expected` y `observed` son textos
    legibles: el valor observado se transcribe en notación JSON cuando es posible.
    """

    rule_id: str
    severity: Severity
    graph_id: str | None
    location: dict[str, Any]
    expected: str
    observed: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        """Serializa el hallazgo a un diccionario compatible con JSON."""
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "graph_id": self.graph_id,
            "location": dict(self.location),
            "expected": self.expected,
            "observed": self.observed,
            "message": self.message,
        }
