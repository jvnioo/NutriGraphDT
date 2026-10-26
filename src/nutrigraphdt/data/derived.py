"""Instancias derivadas de un animal real (contrato de datos v2 §7, V-02; #151).

Una instancia simulada desde un animal observado es **sintética** (`is_synthetic = true`) y
declara:

- `derived_from`: el `sample_id` (BioSample) del animal observado de origen;
- `intervention`: la lista de variables que cambian respecto del origen, cada una como
  `{"variable": "<ruta>", "value": <nuevo valor>}`. Una lista vacía declara que no cambia nada:
  es el escenario `basal` que sirve de control de calidad del simulador, porque debería
  reproducir la observación de su animal.

**Ruta de una variable.** `<tipo de nodo>.<ruta del atributo>`, con la misma notación con
puntos que `missing_mask` (por ejemplo, `host.covariates.body_weight_g` o `additive.dose`).
Un componente de la dieta se nombra por su `component_id`: `diet.composition.<component_id>` es
el `value` de ese elemento de `diet.composition`. La variable se aplica a todos los nodos del
tipo en la instancia.

**Identificadores.** Una instancia derivada reutiliza los `node_id` y los identificadores de
dominio de su origen (decisión del equipo de Desarrollo al implementar #151): así INS-05 a
INS-07 la comparan nodo por nodo con la observación. Por eso NOD-04 no le exige el prefijo
`synthetic:`; la marca de que no es una observación son `is_synthetic` y `derived_from`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

DIET_COMPOSITION_PREFIX: Final = "composition."
"""Prefijo de la ruta de un componente de la dieta, tras `diet.`."""


@dataclass(frozen=True)
class DerivedVariable:
    """Variable intervenida, resuelta desde su ruta."""

    node_type: str
    path: str
    """Ruta del atributo, relativa a `attributes`, con puntos (`covariates.body_weight_g`)."""
    component_id: str | None = None
    """`component_id` si la variable es un componente de `diet.composition`."""

    @classmethod
    def parse(cls, variable: str) -> DerivedVariable:
        """Resuelve `<tipo>.<ruta>`. Lanza `ValueError` si la ruta no tiene esa forma."""
        if not isinstance(variable, str) or not variable.strip():
            raise ValueError("la variable debe ser una cadena no vacía.")
        node_type, _, path = variable.partition(".")
        if not node_type or not path or any(not part for part in path.split(".")):
            raise ValueError(
                f"variable {variable!r} sin la forma '<tipo de nodo>.<ruta del atributo>'."
            )
        component = None
        if node_type == "diet" and path.startswith(DIET_COMPOSITION_PREFIX):
            component = path[len(DIET_COMPOSITION_PREFIX) :]
            if "." in component:
                raise ValueError(
                    f"variable {variable!r}: un componente de la dieta es "
                    "'diet.composition.<component_id>'."
                )
        return cls(node_type, path, component)


def intervention_problems(intervention: object) -> list[str]:
    """Problemas de forma de `intervention`; lista vacía si es válida.

    Debe ser una lista de objetos `{variable, value}`, con rutas válidas y sin repetir una
    variable. `value` puede ser cualquier valor JSON salvo `null` (un valor ausente no es una
    intervención).
    """
    if not isinstance(intervention, list):
        return ["'intervention' debe ser una lista de objetos {variable, value}."]
    problems: list[str] = []
    seen: set[str] = set()
    for position, item in enumerate(intervention):
        where = f"intervention[{position}]"
        if not isinstance(item, Mapping):
            problems.append(f"{where} debe ser un objeto {{variable, value}}.")
            continue
        extra = sorted(set(item) - {"variable", "value"}, key=str)
        if extra:
            problems.append(f"{where} tiene claves no permitidas: {extra}.")
        variable = item.get("variable")
        try:
            DerivedVariable.parse(variable)  # type: ignore[arg-type]
        except ValueError as error:
            problems.append(f"{where}: {error}")
            continue
        if variable in seen:
            problems.append(f"{where}: la variable {variable!r} se declara más de una vez.")
        seen.add(str(variable))
        if "value" not in item or item["value"] is None:
            problems.append(f"{where}: falta el nuevo valor ('value').")
    return problems


def declared_variables(intervention: object) -> list[tuple[DerivedVariable, Any]]:
    """`(variable, valor)` de las entradas válidas de `intervention`, en orden."""
    if not isinstance(intervention, list):
        return []
    declared: list[tuple[DerivedVariable, Any]] = []
    for item in intervention:
        if not isinstance(item, Mapping):
            continue
        try:
            variable = DerivedVariable.parse(item.get("variable"))  # type: ignore[arg-type]
        except ValueError:
            continue
        declared.append((variable, item.get("value")))
    return declared


def is_derived(record: Mapping[str, Any]) -> bool:
    """`True` si el registro de instancia declara `derived_from`."""
    return record.get("derived_from") is not None


__all__ = [
    "DIET_COMPOSITION_PREFIX",
    "DerivedVariable",
    "declared_variables",
    "intervention_problems",
    "is_derived",
]
