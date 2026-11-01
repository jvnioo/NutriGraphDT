"""Vocabulario del tratamiento dietario de D1 y su codificación en el nodo `diet` (A65-P1, #176).

El nodo `diet` de D1 conserva en `name` el nombre del tratamiento de la fuente
(`diet_treatment_name` de HoloFood). Con el contrato v2, el constructor declara este vocabulario
en `metadata.json` (clave `diet.name`, evaluada por NOD-11) y codifica el tratamiento one-hot en
`x` del nodo `diet`, una columna por tratamiento:

| Código (`diet_treatment_code`) | Nombre en la fuente | Rótulo del proyecto | Columna de `x` |
|---|---|---|---|
| `CC` | `Control` | Control | `diet_treatment=CC` |
| `CO` | `Probiotic` | Probiótico | `diet_treatment=CO` |
| `CE` | `Prebiotic` | Fitobiótico | `diet_treatment=CE` |

La fuente llama `Prebiotic` al tratamiento `CE`; el proyecto lo rotula Fitobiótico (extracto de
uva blanca; contrato de datos v2 §3 y D-06 §9). La columna conserva los dos nombres. Un nombre
fuera del vocabulario no se codifica: sus tres columnas quedan en `0.0` con máscara `true` y
NOD-11 lo informa. `CC` también es un código de ensayo (`trial_code`): en los reportes, el código
se califica siempre con su campo.

El tratamiento no se mezcla con el día de muestreo, aunque estén confundidos en D1: el día es una
covariable del huésped (`data.covariates`) y el tratamiento es un atributo de la dieta.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final


@dataclass(frozen=True)
class DietTreatment:
    """Un tratamiento dietario de D1: código, nombre en la fuente y rótulo del proyecto."""

    code: str
    source_name: str
    label: str

    @property
    def column_name(self) -> str:
        """Nombre de su columna one-hot en `x` del nodo `diet`: `diet_treatment=CE`."""
        return f"{DIET_TREATMENT_FEATURE}={self.code}"


DIET_TREATMENT_FEATURE: Final = "diet_treatment"
"""Prefijo de las columnas one-hot del tratamiento en `x` del nodo `diet`."""

DIET_TREATMENT_ATTRIBUTE: Final = "name"
"""Atributo del nodo `diet` que lleva el nombre del tratamiento en la fuente."""

DIET_TREATMENT_VOCABULARY_KEY: Final = "diet.name"
"""Clave del vocabulario en `metadata.json` (NOD-11)."""

DIET_TREATMENTS: Final[tuple[DietTreatment, ...]] = (
    DietTreatment("CC", "Control", "Control"),
    DietTreatment("CO", "Probiotic", "Probiótico"),
    DietTreatment("CE", "Prebiotic", "Fitobiótico"),
)
"""Tratamientos de D1 HoloFood, en el orden de sus columnas."""

DIET_TREATMENTS_BY_NAME: Final[Mapping[str, DietTreatment]] = MappingProxyType(
    {treatment.source_name: treatment for treatment in DIET_TREATMENTS}
)


def diet_treatment_vocabulary() -> dict[str, list[str]]:
    """Vocabulario de `name` del nodo `diet` para `metadata.json` (NOD-11)."""
    return {DIET_TREATMENT_VOCABULARY_KEY: [t.source_name for t in DIET_TREATMENTS]}


__all__ = [
    "DIET_TREATMENTS",
    "DIET_TREATMENTS_BY_NAME",
    "DIET_TREATMENT_ATTRIBUTE",
    "DIET_TREATMENT_FEATURE",
    "DIET_TREATMENT_VOCABULARY_KEY",
    "DietTreatment",
    "diet_treatment_vocabulary",
]
