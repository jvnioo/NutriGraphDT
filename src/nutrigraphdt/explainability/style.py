"""Estilo de las aristas del subgrafo explicativo según su estado de evidencia (C-03; #243).

Aplica la decisión C-03 de la respuesta de Investigación a la revisión A55 (#158): las aristas
`hypothetical` se muestran con un estilo propio y la leyenda «hipotética: sin respaldo
empírico», **sin ocultarlas ni sacarlas del top-k**. Cada uno de los cinco estados de evidencia
de DS-01 tiene su trazo y su color, y la leyenda los distingue todos aunque el subgrafo no los
tenga.

El estilo depende **solo** de la evidencia que declara el grafo; la importancia se codifica
aparte (por ejemplo, con el grosor). Así una arista muy importante no parece mejor respaldada
(principio 1 del contrato de explicaciones). El trazo distingue los estados sin depender del
color.

No depende de Plotly ni de Streamlit: lo usan la demo y cualquier otra visualización.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class EvidenceStyle:
    """Trazo, color y leyenda de un estado de evidencia."""

    status: str
    label: str
    color: str
    dash: str
    """Nombre del trazo en Plotly: `solid`, `dash`, `dashdot`, `dot` o `longdashdot`."""


EVIDENCE_STYLES: Final[Mapping[str, EvidenceStyle]] = {
    style.status: style
    for style in (
        EvidenceStyle("observed", "observada: medida en el animal", "#0E9987", "solid"),
        EvidenceStyle("annotated", "anotada: base curada o tabla", "#0767A0", "dash"),
        EvidenceStyle("inferred", "inferida: predicción o asociación", "#D9973B", "dashdot"),
        EvidenceStyle("hypothetical", "hipotética: sin respaldo empírico", "#C8553D", "dot"),
        EvidenceStyle("synthetic", "sintética: dataset generado", "#5D6B75", "longdashdot"),
    )
}
"""Un estilo por estado de DS-01, de mayor a menor respaldo empírico; `synthetic` al final."""

HYPOTHETICAL_LABEL: Final[str] = EVIDENCE_STYLES["hypothetical"].label


def evidence_style(status: str) -> EvidenceStyle:
    """Estilo de un estado de evidencia.

    Raises:
        ValueError: si el estado no es uno de los cinco de DS-01. No se inventa un estilo.
    """
    try:
        return EVIDENCE_STYLES[status]
    except KeyError:
        raise ValueError(
            f"Estado de evidencia desconocido {status!r}; se esperaba uno de "
            f"{sorted(EVIDENCE_STYLES)} (DS-01)."
        ) from None


def evidence_legend() -> list[EvidenceStyle]:
    """Los cinco estilos, en el orden de la leyenda."""
    return list(EVIDENCE_STYLES.values())


__all__ = [
    "EVIDENCE_STYLES",
    "HYPOTHETICAL_LABEL",
    "EvidenceStyle",
    "evidence_legend",
    "evidence_style",
]
