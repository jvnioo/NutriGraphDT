"""Catálogo versionado de escenarios de referencia (A93-P2, #310).

Los escenarios que usan la app, las pruebas E2E y la demostración viven en `configs/scenarios/`,
un archivo JSON por escenario, y se validan con `CatalogScenario` (Pydantic, `extra="forbid"`).
Cada archivo declara la corrida que lo responde, el animal base de la cohorte sintética (por su
semilla), las variables intervenidas con su valor, el estado esperado y de dónde sale cada valor.

Los valores intervenidos salen del diccionario sintético (`nutrigraphdt.data.synthetic`): el par
de proteína de DS-04 y las dosis del catálogo de aditivos. Ninguno se inventa. Ver
`configs/scenarios/README.md`.

**Datos sintéticos.** Todos los escenarios del catálogo derivan de la cohorte sintética: no
describen animales reales, y la diferencia entre un escenario y su basal describe al modelo, no
un efecto de la intervención.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from nutrigraphdt.api.contract import (
    API_CONTRACT_VERSION,
    InterventionItem,
    ScenarioRequest,
)

CATALOG_SCHEMA_VERSION: Final = "1.0.0"
"""Versión del esquema de los archivos del catálogo."""

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
CATALOG_DIR: Final[Path] = REPO_ROOT / "configs" / "scenarios"

SYNTHETIC_SAMPLE_PREFIX: Final[str] = "synthetic:sample:"
"""Prefijo del `sample_id` de la cohorte sintética: `synthetic:sample:<semilla con 4 dígitos>`."""

ScenarioId = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
Text = Annotated[str, Field(min_length=1)]


class CatalogError(ValueError):
    """El catálogo de escenarios no es válido; `problems` lista cada infracción."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("Catálogo de escenarios inválido:\n- " + "\n- ".join(problems))


class ValueSource(BaseModel):
    """De dónde sale el valor de una variable intervenida (sin valores inventados)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    variable: Text
    source: Text
    """Constante o catálogo del diccionario sintético que fija el valor."""


class CatalogScenario(BaseModel):
    """Escenario de referencia del catálogo."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0.0"]
    id: ScenarioId
    version: Annotated[int, Field(ge=1)]
    label: Text
    description: Text
    run: Literal["synthetic"]
    """Corrida que responde el escenario (clave de `nutrigraphdt.api.DEMO_RUNS`)."""
    base_seed: Annotated[int, Field(ge=1)]
    """Semilla del animal base en `build_synthetic_cohort`."""
    intervention: tuple[InterventionItem, ...] = ()
    """Variables que cambian; vacía para el basal."""
    value_sources: tuple[ValueSource, ...] = ()
    expected_status: Literal["estimable", "no_estimable"]
    """Estado que devuelve la corrida; lo exigen las pruebas."""
    null_intervention: bool = False
    """`True` si la intervención fija las variables en el valor que ya tiene el animal base."""
    is_synthetic: Literal[True]

    @model_validator(mode="after")
    def _consistent(self) -> CatalogScenario:
        intervened = [item.variable for item in self.intervention]
        if len(set(intervened)) != len(intervened):
            raise ValueError("una variable aparece dos veces en la intervención.")
        sourced = [source.variable for source in self.value_sources]
        if sorted(sourced) != sorted(intervened):
            raise ValueError(
                "cada variable intervenida necesita exactamente una fuente en value_sources; "
                f"intervenidas: {sorted(intervened)}, con fuente: {sorted(sourced)}."
            )
        if self.null_intervention and not self.intervention:
            raise ValueError("una intervención nula debe declarar al menos una variable.")
        return self

    @property
    def base_instance(self) -> str:
        """`sample_id` del animal base."""
        return f"{SYNTHETIC_SAMPLE_PREFIX}{self.base_seed:04d}"

    @property
    def is_basal(self) -> bool:
        return not self.intervention

    def request(self) -> ScenarioRequest:
        """Petición del escenario en el contrato de `nutrigraphdt.api`."""
        return ScenarioRequest(
            contract_version=API_CONTRACT_VERSION,
            base_instance=self.base_instance,
            intervention=self.intervention,
        )

    def basal_request(self) -> ScenarioRequest:
        """Petición basal del mismo animal: la referencia de la comparación."""
        return self.request().model_copy(update={"intervention": ()})


def load_scenario(path: str | Path) -> CatalogScenario:
    """Lee y valida un archivo del catálogo.

    Raises:
        CatalogError: si el archivo no se puede leer, no es JSON, no cumple el esquema o su
            nombre no es `<id>.json`.
    """
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CatalogError([f"{path.name}: no se pudo leer ({error})."]) from error
    try:
        scenario = CatalogScenario.model_validate(data)
    except ValidationError as error:
        raise CatalogError(
            [
                f"{path.name}: {'.'.join(map(str, e['loc'])) or 'escenario'}: {e['msg']}"
                for e in error.errors()
            ]
        ) from error
    if path.stem != scenario.id:
        raise CatalogError([f"{path.name}: el archivo debe llamarse {scenario.id}.json."])
    return scenario


def load_catalog(directory: str | Path = CATALOG_DIR) -> list[CatalogScenario]:
    """Todos los escenarios de `directory`, ordenados por `id`.

    Raises:
        CatalogError: si un archivo no es válido, si hay `id` repetidos o si el directorio no
            tiene escenarios.
    """
    directory = Path(directory)
    paths = sorted(directory.glob("*.json"))
    if not paths:
        raise CatalogError([f"{directory} no tiene escenarios (*.json)."])
    problems: list[str] = []
    scenarios: list[CatalogScenario] = []
    for path in paths:
        try:
            scenarios.append(load_scenario(path))
        except CatalogError as error:
            problems.extend(error.problems)
    if problems:
        raise CatalogError(problems)
    return sorted(scenarios, key=lambda s: s.id)


def scenario_by_id(scenario_id: str, directory: str | Path = CATALOG_DIR) -> CatalogScenario:
    """Escenario `scenario_id` del catálogo.

    Raises:
        KeyError: si no existe.
    """
    for scenario in load_catalog(directory):
        if scenario.id == scenario_id:
            return scenario
    raise KeyError(f"El catálogo no tiene el escenario {scenario_id!r}.")


__all__ = [
    "CATALOG_DIR",
    "CATALOG_SCHEMA_VERSION",
    "SYNTHETIC_SAMPLE_PREFIX",
    "CatalogError",
    "CatalogScenario",
    "ValueSource",
    "load_catalog",
    "load_scenario",
    "scenario_by_id",
]
