"""Covariables del huésped declaradas en el contrato de datos v2 (sección 3, S-07; #147).

`host.covariates` deja de ser un objeto libre: cada covariable tiene nombre, tipo, vocabulario
o unidad y un uso fijo en F4.

| Covariable | Tipo | Vocabulario o unidad en D1 | ¿Entrada del modelo? |
|---|---|---|---|
| `trial_code` | `str` | `CA`, `CB`, `CC` | sí |
| `pen_code` | `str` | código del corral | **no**: solo agrupa la partición y los folds |
| `sampling_day` | `int` | 7, 21, 35 | sí; también estrato de las métricas por día |
| `sex` | `str` | `female`, `male` | sí |
| `breed` | `str` | `Ross`, `Cobb` | sí |
| `body_weight_g` | `number` | g | **no**: se informa; depende del tratamiento y del día |

Las covariables categóricas de entrada se codifican one-hot (una columna por categoría del
vocabulario) en `x` del host y en la tabla de atributos de los baselines. `trial_code` y el
tratamiento dietario comparten el código `CC`; en los reportes se califica siempre con el campo.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final, Literal

CovariateKind = Literal["str", "int", "number"]


@dataclass(frozen=True)
class HostCovariate:
    """Una covariable declarada de `host.covariates`."""

    name: str
    kind: CovariateKind
    is_input: bool
    vocabulary: tuple[str, ...] = ()
    """Valores admitidos (como texto); vacío si no hay vocabulario cerrado."""
    unit: str | None = None
    metadata_field: str | None = None
    """Columna de los metadatos de D1 que la entrega; por omisión, `name`."""

    @property
    def source_field(self) -> str:
        return self.metadata_field or self.name

    def normalize(self, value: Any) -> str | int | float | None:
        """Valor tipado desde los metadatos; `None` si falta. `35.0` → `35` para `int`."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if self.kind == "str":
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value).strip()
        if isinstance(value, bool):
            raise ValueError(f"{self.name}: se esperaba un número; se recibió {value!r}.")
        number = float(value)
        if self.kind == "int":
            if not number.is_integer():
                raise ValueError(f"{self.name}: se esperaba un entero; se recibió {value!r}.")
            return int(number)
        return number

    def in_vocabulary(self, value: Any) -> bool:
        """`True` si no hay vocabulario cerrado o si el valor pertenece a él."""
        return not self.vocabulary or str(value) in self.vocabulary


HOST_COVARIATES: Final[tuple[HostCovariate, ...]] = (
    HostCovariate("trial_code", "str", True, ("CA", "CB", "CC")),
    HostCovariate("pen_code", "str", False),
    HostCovariate("sampling_day", "int", True, ("7", "21", "35"), unit="d"),
    HostCovariate("sex", "str", True, ("female", "male")),
    HostCovariate("breed", "str", True, ("Ross", "Cobb")),
    HostCovariate("body_weight_g", "number", False, unit="g"),
)
"""Covariables del contrato v2 §3, en el orden de la tabla del contrato."""

HOST_COVARIATES_BY_NAME: Final[Mapping[str, HostCovariate]] = MappingProxyType(
    {covariate.name: covariate for covariate in HOST_COVARIATES}
)

INPUT_COVARIATES: Final[tuple[HostCovariate, ...]] = tuple(c for c in HOST_COVARIATES if c.is_input)
"""Covariables que entran a `x` del host y a la tabla de atributos (todas categóricas en D1)."""

NON_INPUT_COVARIATES: Final[frozenset[str]] = frozenset(
    c.name for c in HOST_COVARIATES if not c.is_input
)
"""`pen_code` y `body_weight_g`: se registran, pero nunca son entrada de un modelo."""

CONTEXT_COVARIATES: Final[tuple[HostCovariate, ...]] = tuple(
    c for c in HOST_COVARIATES if c.kind != "number"
)
"""Covariables que llegan del contexto de la muestra (no como feature numérica)."""


def covariate_vocabularies() -> dict[str, list[str]]:
    """Vocabularios para `metadata.json`, con la clave `covariates.<nombre>` (NOD-11)."""
    return {f"covariates.{c.name}": list(c.vocabulary) for c in HOST_COVARIATES if c.vocabulary}


def one_hot_name(covariate: HostCovariate, category: str) -> str:
    """Nombre de la columna one-hot de una categoría: `covariates.sex=male`."""
    return f"covariates.{covariate.name}={category}"


__all__ = [
    "CONTEXT_COVARIATES",
    "HOST_COVARIATES",
    "HOST_COVARIATES_BY_NAME",
    "INPUT_COVARIATES",
    "NON_INPUT_COVARIATES",
    "CovariateKind",
    "HostCovariate",
    "covariate_vocabularies",
    "one_hot_name",
]
