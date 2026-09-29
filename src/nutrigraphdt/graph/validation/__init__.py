"""Validadores de integridad del grafo heterogéneo.

Implementan las reglas de `docs/graph-integrity-rules.md`. Cada validador devuelve una lista de
`Finding` con la regla, la severidad y la ubicación de cada incumplimiento, sin modificar el
grafo. Hoy contiene el validador de nodos e instancias (VG-02).
"""

from nutrigraphdt.graph.validation.findings import Finding, Severity
from nutrigraphdt.graph.validation.nodes import (
    NODE_ATTRIBUTE_CONTRACT,
    SYNTHETIC_ID_PREFIX,
    find_node_findings,
)

__all__ = [
    "NODE_ATTRIBUTE_CONTRACT",
    "SYNTHETIC_ID_PREFIX",
    "Finding",
    "Severity",
    "find_node_findings",
]
