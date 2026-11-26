"""Comparación basal / intervenido con el mismo modelo congelado (A93-P1 y A93-P3, #309 y #311).

`compare_scenario` recibe un `ScenarioEngine` de `nutrigraphdt.api` y una petición, y predice con
ese mismo motor el escenario y el basal del mismo animal (la petición sin intervención). No hay un
segundo motor ni entrenamiento: las dos predicciones salen del mismo checkpoint cargado una vez,
y la comparación lo comprueba (misma corrida en las dos respuestas y el hash SHA-256 del
checkpoint).

**Criterios de resultado** (`docs/models/scenario-comparison.md`):

- La diferencia es `intervenido − basal` para cada fracción molar de AGCC (adimensional) y para
  `ln T` (con `T` en mmol/kg de digesta fresca; la diferencia es `ln(T_int / T_basal)`, también
  adimensional).
- Si el basal o el intervenido es `no_estimable`, la comparación también lo es: no lleva ninguna
  diferencia numérica y declara los motivos de cada lado.
- No se fija un umbral de «diferencia relevante»: no hay una fuente que lo defina (pregunta
  abierta para Investigación).

**Datos sintéticos.** Los targets sintéticos son independientes de la dieta y del aditivo
(DS-01): una diferencia describe al modelo, no un efecto biológico. Toda comparación lleva
`CAUSAL_WARNING` y, si la corrida es sintética, `SYNTHETIC_WARNING`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from nutrigraphdt.api.contract import (
    CAUSAL_WARNING,
    ESTIMABLE,
    NOT_ESTIMABLE,
    SCFA_COMPONENTS,
    SYNTHETIC_WARNING,
    ModelRef,
    ScenarioRequest,
    ScenarioResponse,
)

if TYPE_CHECKING:
    from nutrigraphdt.api.engine import ScenarioEngine

COMPARISON_VERSION: Final = "1.0.0"
"""Versión del formato de `ScenarioComparison`."""

CHECKPOINT_FILE: Final[str] = "checkpoint.pt"

LOG_TOTAL: Final[str] = "log_total"
QUANTITIES: Final[tuple[str, ...]] = (*SCFA_COMPONENTS, LOG_TOTAL)
"""Cantidades comparadas: las tres fracciones molares y `ln T`."""

FRACTION_UNIT: Final[str] = "fracción molar (adimensional)"
LOG_TOTAL_UNIT: Final[str] = "ln(mmol/kg de digesta fresca)"
LOG_RATIO_UNIT: Final[str] = "ln(T_int / T_basal) (adimensional)"

UNITS: Final[dict[str, tuple[str, str]]] = {
    **{name: (FRACTION_UNIT, FRACTION_UNIT) for name in SCFA_COMPONENTS},
    LOG_TOTAL: (LOG_TOTAL_UNIT, LOG_RATIO_UNIT),
}
"""Unidad de cada cantidad: `(unidad del valor, unidad de la diferencia)`."""

DIFFERENCE_WARNING: Final[str] = (
    "La diferencia entre el escenario y el basal es la de dos predicciones del mismo modelo: "
    "describe al modelo, no un efecto de la intervención."
)

Finite = Annotated[float, Field(allow_inf_nan=False)]


class SimulationError(RuntimeError):
    """Las dos predicciones de una comparación no salieron del mismo modelo."""


class QuantityDifference(BaseModel):
    """Valor basal, valor intervenido y diferencia de una cantidad."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    quantity: Literal["acetate", "propionate", "butyrate", "log_total"]
    unit: str
    difference_unit: str
    basal: Finite
    intervened: Finite
    difference: Finite
    """`intervenido − basal`."""


class ScenarioComparison(BaseModel):
    """Comparación de un escenario con el basal del mismo animal, con el mismo modelo."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    comparison_version: Literal["1.0.0"]
    status: Literal["estimable", "no_estimable"]
    basal: ScenarioResponse
    intervened: ScenarioResponse
    model: ModelRef
    checkpoint_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    differences: tuple[QuantityDifference, ...]
    """Una por cantidad de `QUANTITIES` si es estimable; vacía si no."""
    reasons: tuple[str, ...] = ()
    """Por qué la comparación no es estimable, con el lado (`basal` o `intervenido`)."""
    is_synthetic: bool
    warnings: tuple[str, ...]

    @model_validator(mode="after")
    def _consistent(self) -> ScenarioComparison:
        if self.basal.model != self.model or self.intervened.model != self.model:
            raise ValueError("las dos predicciones deben informar la misma corrida.")
        if self.basal.request.base_instance != self.intervened.request.base_instance:
            raise ValueError("el basal y el escenario deben partir del mismo animal.")
        if self.basal.request.intervention:
            raise ValueError("el basal no puede tener intervención.")
        both = self.basal.status == ESTIMABLE and self.intervened.status == ESTIMABLE
        if both != (self.status == ESTIMABLE):
            raise ValueError("la comparación es estimable solo si lo son el basal y el escenario.")
        if self.status == NOT_ESTIMABLE:
            if self.differences:
                raise ValueError("una comparación no estimable no lleva diferencias numéricas.")
            if not self.reasons:
                raise ValueError("una comparación no estimable debe decir por qué.")
        elif [d.quantity for d in self.differences] != list(QUANTITIES) or self.reasons:
            raise ValueError("una comparación estimable lleva una diferencia por cantidad.")
        if CAUSAL_WARNING not in self.warnings or DIFFERENCE_WARNING not in self.warnings:
            raise ValueError("toda comparación advierte que la diferencia no es un efecto.")
        return self

    def difference(self, quantity: str) -> QuantityDifference | None:
        """Diferencia de `quantity`, o `None` si la comparación no es estimable."""
        for item in self.differences:
            if item.quantity == quantity:
                return item
        return None


def checkpoint_sha256(run_dir: str | Path) -> str:
    """SHA-256 del `checkpoint.pt` de una corrida congelada."""
    digest = hashlib.sha256()
    with (Path(run_dir) / CHECKPOINT_FILE).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _values(response: ScenarioResponse) -> dict[str, float]:
    assert response.fractions is not None and response.log_total is not None
    values = {name: float(getattr(response.fractions, name)) for name in SCFA_COMPONENTS}
    values[LOG_TOTAL] = float(response.log_total)
    return values


def build_comparison(
    basal: ScenarioResponse,
    intervened: ScenarioResponse,
    *,
    checkpoint: str,
) -> ScenarioComparison:
    """Comparación de dos respuestas ya calculadas (criterios de A93-P3).

    Raises:
        SimulationError: si las respuestas no informan la misma corrida.
    """
    if basal.model != intervened.model:
        raise SimulationError(
            f"El basal lo predijo {basal.model.run_id} y el escenario {intervened.model.run_id}: "
            "una comparación necesita el mismo modelo."
        )
    estimable = basal.status == ESTIMABLE and intervened.status == ESTIMABLE
    differences: list[QuantityDifference] = []
    reasons: list[str] = []
    if estimable:
        before, after = _values(basal), _values(intervened)
        for quantity in QUANTITIES:
            unit, difference_unit = UNITS[quantity]
            differences.append(
                QuantityDifference(
                    quantity=quantity,  # type: ignore[arg-type]
                    unit=unit,
                    difference_unit=difference_unit,
                    basal=before[quantity],
                    intervened=after[quantity],
                    difference=after[quantity] - before[quantity],
                )
            )
    else:
        reasons.extend(f"basal: {reason}" for reason in basal.reasons)
        reasons.extend(f"intervenido: {reason}" for reason in intervened.reasons)
    notes = [CAUSAL_WARNING, DIFFERENCE_WARNING]
    if basal.is_synthetic or intervened.is_synthetic:
        notes.append(SYNTHETIC_WARNING)
    notes.extend(w for w in intervened.warnings if w not in notes)
    return ScenarioComparison(
        comparison_version=COMPARISON_VERSION,
        status=ESTIMABLE if estimable else NOT_ESTIMABLE,
        basal=basal,
        intervened=intervened,
        model=intervened.model,
        checkpoint_sha256=checkpoint,
        differences=tuple(differences),
        reasons=tuple(reasons),
        is_synthetic=basal.is_synthetic or intervened.is_synthetic,
        warnings=tuple(notes),
    )


def compare_scenario(
    engine: ScenarioEngine, request: ScenarioRequest, *, with_interval: bool = False
) -> ScenarioComparison:
    """Predice el escenario y el basal del mismo animal con `engine` y los compara.

    El basal es la misma petición sin intervención. Las dos predicciones usan el checkpoint que
    `engine` cargó una sola vez; no se entrena nada. Con `with_interval`, cada predicción
    estimable lleva su intervalo MC-dropout sin calibrar (`ScenarioEngine.interval`).

    Raises:
        ScenarioContractError: si la petición no cumple el contrato de la corrida.
        SimulationError: si las respuestas no informan la misma corrida.
    """
    basal = engine.predict(
        request.model_copy(update={"intervention": ()}), with_interval=with_interval
    )
    intervened = engine.predict(request, with_interval=with_interval)
    return build_comparison(basal, intervened, checkpoint=checkpoint_sha256(engine.run_dir))


__all__ = [
    "CHECKPOINT_FILE",
    "COMPARISON_VERSION",
    "DIFFERENCE_WARNING",
    "FRACTION_UNIT",
    "LOG_RATIO_UNIT",
    "LOG_TOTAL",
    "LOG_TOTAL_UNIT",
    "QUANTITIES",
    "UNITS",
    "QuantityDifference",
    "ScenarioComparison",
    "SimulationError",
    "build_comparison",
    "checkpoint_sha256",
    "compare_scenario",
]
