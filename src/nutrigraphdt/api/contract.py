"""Contrato versionado entre el motor y la interfaz: entrada y salida de un escenario (#287).

La interfaz pide un escenario con `ScenarioRequest` y recibe un `ScenarioResponse`; no ve
tensores, grafos ni corridas. Los modelos son estrictos (`extra="forbid"`): un campo no declarado
se rechaza, igual que una versión de contrato distinta de `API_CONTRACT_VERSION`.

**Entrada.** Un escenario parte de un animal observado (`base_instance`, su `sample_id`) y declara
las variables que cambian, con el vocabulario de las instancias derivadas
(`nutrigraphdt.data.derived`, contrato de datos v2 §7): `<tipo de nodo>.<ruta del atributo>`,
por ejemplo `diet.composition.crude_protein` o `host.covariates.sex`. Una lista vacía es el
escenario basal. El motor rechaza toda variable que no esté en el vocabulario de la corrida
(`ScenarioVariable`): una variable que el modelo no lee no puede cambiar la predicción, y
aceptarla haría creer que sí.

**Salida.** Las fracciones molares de acetato, propionato y n-butirato y `ln T`, o `no_estimable`
con sus motivos cuando la predicción cae fuera del soporte empírico de la corrida
(`nutrigraphdt.scenarios.support`, D-06 §7). Una respuesta `no_estimable` **no lleva números**:
`ScenarioResponse` lo exige al validarse. Además declara la corrida que predijo, el soporte que se
aplicó, las advertencias de interpretación y un intervalo opcional que A75 podrá llenar.

Un escenario no es un efecto causal: es lo que el modelo predice para una instancia que nunca se
observó. Toda respuesta lo advierte (`CAUSAL_WARNING`).
"""

from __future__ import annotations

import math
from typing import Annotated, Final, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from nutrigraphdt.data.derived import DerivedVariable, intervention_problems

ContractVersion = Literal["1.0.0"]
"""Versiones del contrato que este módulo acepta."""
API_CONTRACT_VERSION: Final[ContractVersion] = "1.0.0"
"""Versión del contrato; cambia el mayor si una interfaz anterior deja de ser compatible."""

ESTIMABLE: Final = "estimable"
NOT_ESTIMABLE: Final = "no_estimable"
SCFA_COMPONENTS: Final[tuple[str, str, str]] = ("acetate", "propionate", "butyrate")

CAUSAL_WARNING: Final[str] = (
    "Escenario hipotético: es la predicción del modelo para una instancia que no se observó, "
    "no un efecto causal de la intervención."
)
SYNTHETIC_WARNING: Final[str] = (
    "Datos sintéticos: la instancia base y el modelo no describen animales reales."
)

Text = Annotated[str, Field(min_length=1)]
Fraction = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
Finite = Annotated[float, Field(allow_inf_nan=False)]
InterventionValue = StrictBool | StrictInt | StrictFloat | StrictStr
"""Valor JSON no nulo; `bool` va primero para que `True` no se lea como `1`."""


class ScenarioContractError(ValueError):
    """La petición no cumple el contrato; `problems` lista cada infracción."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("Escenario inválido:\n- " + "\n- ".join(problems))


class _Strict(BaseModel):
    # `extra="forbid"`: un campo no declarado se rechaza en vez de ignorarse en silencio.
    model_config = ConfigDict(extra="forbid", frozen=True)


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------


class InterventionItem(_Strict):
    """Variable intervenida y su nuevo valor, como un elemento de `intervention` (#151)."""

    variable: Text
    value: InterventionValue

    @field_validator("variable")
    @classmethod
    def _path(cls, value: str) -> str:
        DerivedVariable.parse(value)
        return value

    @field_validator("value")
    @classmethod
    def _finite(cls, value: InterventionValue) -> InterventionValue:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("el valor debe ser finito.")
        return value


class ScenarioRequest(_Strict):
    """Escenario pedido por la interfaz: animal base y variables que cambian."""

    contract_version: ContractVersion
    base_instance: Text
    """`sample_id` del animal observado del que se deriva el escenario."""
    intervention: tuple[InterventionItem, ...] = ()
    """Variables que cambian; vacía para el escenario basal."""

    @model_validator(mode="after")
    def _intervention(self) -> ScenarioRequest:
        problems = intervention_problems([item.model_dump() for item in self.intervention])
        if problems:
            raise ValueError("; ".join(problems))
        return self


# ---------------------------------------------------------------------------
# Vocabulario
# ---------------------------------------------------------------------------


class ScenarioVariable(_Strict):
    """Variable que una corrida admite en `intervention`: el modelo la lee como entrada."""

    variable: Text
    node_type: Text
    kind: Literal["numeric", "categorical"]
    unit: Text
    categories: tuple[str, ...] = ()
    """Valores admitidos de una variable categórica; vacío si es numérica."""
    label: Text


# ---------------------------------------------------------------------------
# Salida
# ---------------------------------------------------------------------------


class Bounds(_Strict):
    lower: Finite
    upper: Finite

    @model_validator(mode="after")
    def _ordered(self) -> Bounds:
        if self.lower > self.upper:
            raise ValueError(f"lower ({self.lower}) > upper ({self.upper}).")
        return self


class SCFAFractions(_Strict):
    """Fracciones molares de los tres AGCC objetivo; suman 1."""

    acetate: Fraction
    propionate: Fraction
    butyrate: Fraction

    @model_validator(mode="after")
    def _closed(self) -> SCFAFractions:
        total = self.acetate + self.propionate + self.butyrate
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"las fracciones deben sumar 1; suman {total}.")
        return self


class PredictionInterval(_Strict):
    """Intervalo predictivo de un método de incertidumbre (A75); el motor v1 no lo calcula."""

    method: Text
    level: Annotated[float, Field(gt=0.0, lt=1.0)]
    fractions: dict[Literal["acetate", "propionate", "butyrate"], Bounds]
    log_total: Bounds | None = None


class ModelRef(_Strict):
    """Corrida congelada que hizo la predicción (campos de su `run.json`)."""

    run_id: Text
    variant: Text
    edges_arm: Text
    dataset_id: Text
    seed: int
    fold: int
    format_version: Text
    compositional_target_version: Text
    git_commit: str | None


class SupportRef(_Strict):
    """Soporte empírico aplicado a la predicción (D-06 §7)."""

    version: Text
    source: Text
    n_animals: Annotated[int, Field(ge=1)]
    interval: dict[Literal["acetate", "propionate", "butyrate"], Bounds]
    method: Text


class ScenarioResponse(_Strict):
    """Respuesta del motor a un `ScenarioRequest`."""

    contract_version: ContractVersion
    request: ScenarioRequest
    status: Literal["estimable", "no_estimable"]
    fractions: SCFAFractions | None
    log_total: Finite | None
    """`ln T`, con `T` la suma de los tres AGCC en mmol/kg de digesta fresca."""
    reasons: tuple[str, ...] = ()
    """Por qué la predicción no es estimable; vacío si lo es."""
    interval: PredictionInterval | None = None
    model: ModelRef
    support: SupportRef
    is_synthetic: bool
    """`True` si la instancia base y la corrida vienen de datos sintéticos."""
    warnings: tuple[str, ...]

    @model_validator(mode="after")
    def _numbers_only_when_estimable(self) -> ScenarioResponse:
        if self.status == NOT_ESTIMABLE:
            if self.fractions is not None or self.log_total is not None or self.interval:
                raise ValueError("una predicción no estimable no puede llevar números.")
            if not self.reasons:
                raise ValueError("una predicción no estimable debe decir por qué.")
        elif self.fractions is None or self.log_total is None or self.reasons:
            raise ValueError("una predicción estimable lleva fracciones y ln T, sin motivos.")
        if CAUSAL_WARNING not in self.warnings:
            raise ValueError("toda respuesta advierte que un escenario no es un efecto causal.")
        return self


__all__ = [
    "API_CONTRACT_VERSION",
    "CAUSAL_WARNING",
    "ESTIMABLE",
    "NOT_ESTIMABLE",
    "SCFA_COMPONENTS",
    "SYNTHETIC_WARNING",
    "Bounds",
    "InterventionItem",
    "ModelRef",
    "PredictionInterval",
    "SCFAFractions",
    "ContractVersion",
    "ScenarioContractError",
    "ScenarioRequest",
    "ScenarioResponse",
    "ScenarioVariable",
    "SupportRef",
]
