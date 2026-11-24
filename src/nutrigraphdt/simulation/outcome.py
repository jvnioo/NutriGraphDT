"""Criterios de resultado para la comparación de escenarios (A93-P3, #311).

Define la diferencia por AGCC entre el escenario intervenido y el basal, con
unidades explícitas y el estado «no estimable» cuando una predicción queda fuera
del soporte empírico del train (D-06 §7).

**Datos sintéticos.** Todo resultado de esta comparación proviene de escenarios
sintéticos (DS-04). Las diferencias describen el comportamiento del modelo, no
efectos biológicos causales.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final

# ---------------------------------------------------------------------------
# Constantes de dominio
# ---------------------------------------------------------------------------

SCFA_COMPONENTS: Final[tuple[str, str, str]] = ("acetate", "propionate", "butyrate")
"""AGCC canónicos del modelo (acetato, propionato, n-butirato)."""

SCFA_UNITS: Final[dict[str, str]] = {
    "acetate": "fraccion_molar",
    "propionate": "fraccion_molar",
    "butyrate": "fraccion_molar",
}
"""Unidades de cada fracción de AGCC.

Las predicciones del modelo son fracciones molares (composición simplex): suman 1 y
no representan concentraciones absolutas. Ver docs/models/ para la definición del target.
"""

SYNTHETIC_DATA_WARNING: Final[str] = (
    "DATOS SINTÉTICOS. Los resultados describen el comportamiento del modelo sobre "
    "escenarios sintéticos (DS-04) y no representan efectos biológicos causales ni "
    "observaciones reales. Una diferencia entre escenarios describe al modelo, no un "
    "efecto de la dieta."
)
"""Advertencia obligatoria en toda salida de comparación de escenarios (D-06 §7)."""


# ---------------------------------------------------------------------------
# Estado de estimabilidad
# ---------------------------------------------------------------------------


class OutcomeStatus(StrEnum):
    """Estado del resultado de una comparación de escenarios."""

    ESTIMABLE = "estimable"
    """La predicción de ambos escenarios cae dentro del soporte empírico del train."""

    NOT_ESTIMABLE = "no_estimable"
    """Al menos una predicción queda fuera del soporte empírico del train."""

    NO_SUPPORT = "sin_soporte"
    """No se proporcionó soporte empírico: no se puede evaluar la estimabilidad."""


# ---------------------------------------------------------------------------
# Resultado por AGCC
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScfaOutcome:
    """Resultado de la predicción de un AGCC en un escenario dado.

    Attributes:
        component: Nombre del AGCC (``acetate``, ``propionate`` o ``butyrate``).
        value: Fracción molar predicha, o ``None`` si no es estimable.
        unit: Unidad de la fracción (siempre ``'fraccion_molar'``).
        status: ``'estimable'`` o ``'no_estimable'``.
        reasons: Motivos por los que no es estimable (vacío si es estimable).
    """

    component: str
    value: float | None
    unit: str
    status: OutcomeStatus
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "value": self.value,
            "unit": self.unit,
            "status": self.status,
            "reasons": list(self.reasons),
        }


# ---------------------------------------------------------------------------
# Diferencia entre escenarios
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScfaDiff:
    """Diferencia de AGCC entre el escenario intervenido y el basal.

    ``diff = intervenido - basal`` en fracciones molares.

    Si alguno de los dos escenarios tiene ``status = 'no_estimable'`` para un
    componente, la diferencia de ese componente es ``None`` y el estado es
    ``'no_estimable'``.

    Attributes:
        component: Nombre del AGCC.
        diff: Diferencia (intervenido − basal), o ``None`` si no estimable.
        unit: Unidad de la diferencia (siempre ``'fraccion_molar'``).
        status: Estado de estimabilidad del par.
        basal_value: Valor del escenario basal (``None`` si no estimable).
        intervened_value: Valor del escenario intervenido (``None`` si no estimable).
        reasons: Motivos de no estimabilidad (vacío si estimable).
        synthetic_data_warning: Advertencia de datos sintéticos (D-06 §7).
    """

    component: str
    diff: float | None
    unit: str
    status: OutcomeStatus
    basal_value: float | None
    intervened_value: float | None
    reasons: tuple[str, ...]
    synthetic_data_warning: str = SYNTHETIC_DATA_WARNING

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "diff": self.diff,
            "unit": self.unit,
            "status": self.status,
            "basal_value": self.basal_value,
            "intervened_value": self.intervened_value,
            "reasons": list(self.reasons),
            "synthetic_data_warning": self.synthetic_data_warning,
        }


# ---------------------------------------------------------------------------
# Función de cómputo
# ---------------------------------------------------------------------------


def compute_scfa_diff(
    basal_outcomes: list[ScfaOutcome],
    intervened_outcomes: list[ScfaOutcome],
) -> list[ScfaDiff]:
    """Calcula la diferencia (intervenido − basal) por AGCC.

    Ambas listas deben tener una entrada por componente en el mismo orden
    (acetato, propionato, butirato).  Si alguno de los dos escenarios devuelve
    ``'no_estimable'`` para un componente, la diferencia de ese componente es
    ``None`` y el estado es ``'no_estimable'``.

    Args:
        basal_outcomes: Resultados del escenario basal (un ``ScfaOutcome`` por AGCC).
        intervened_outcomes: Resultados del escenario intervenido.

    Returns:
        Lista de ``ScfaDiff``, una por componente, en el mismo orden.

    Raises:
        ValueError: Si las listas tienen longitudes distintas o componentes
            que no coinciden.
    """
    if len(basal_outcomes) != len(intervened_outcomes):
        raise ValueError(
            f"Las listas de resultados tienen longitudes distintas: "
            f"basal={len(basal_outcomes)}, intervenido={len(intervened_outcomes)}."
        )

    diffs: list[ScfaDiff] = []
    for basal_out, interv_out in zip(basal_outcomes, intervened_outcomes, strict=True):
        if basal_out.component != interv_out.component:
            raise ValueError(
                f"Componente desalineado: basal tiene '{basal_out.component}', "
                f"intervenido tiene '{interv_out.component}'."
            )

        component = basal_out.component
        unit = basal_out.unit

        both_estimable = (
            basal_out.status == OutcomeStatus.ESTIMABLE
            and interv_out.status == OutcomeStatus.ESTIMABLE
        )

        if both_estimable and basal_out.value is not None and interv_out.value is not None:
            diff_value: float | None = interv_out.value - basal_out.value
            status = OutcomeStatus.ESTIMABLE
            reasons: tuple[str, ...] = ()
        else:
            diff_value = None
            status = OutcomeStatus.NOT_ESTIMABLE
            reasons = basal_out.reasons + interv_out.reasons

        diffs.append(
            ScfaDiff(
                component=component,
                diff=diff_value,
                unit=unit,
                status=status,
                basal_value=basal_out.value,
                intervened_value=interv_out.value,
                reasons=reasons,
            )
        )

    return diffs


__all__ = [
    "SCFA_COMPONENTS",
    "SCFA_UNITS",
    "SYNTHETIC_DATA_WARNING",
    "OutcomeStatus",
    "ScfaDiff",
    "ScfaOutcome",
    "compute_scfa_diff",
]
