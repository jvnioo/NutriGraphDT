"""Servicio en memoria entre la Web App y el motor (A96, #314), sin Streamlit.

La interfaz no importa nada interno del motor: habla con este servicio, que usa solo
`nutrigraphdt.api` (contrato y `ScenarioEngine`) y `nutrigraphdt.simulation` (A93).

- `prepare` convierte el formulario en `ScenarioRequest` y en la instancia derivada, y la valida
  con `validate_graph`, sin escribir en disco (A96-P1).
- `simulate` ejecuta el par basal / intervenido con `compare_scenario` y lo envuelve en
  `SimulationResult`, el formato único que exportan la app y A101 (A96-P2).
- `user_message` traduce cada clase de error a un mensaje sin trazas (A96-P3).

`SimulationResult` serializa a JSON con la versión del contrato, la corrida, el commit con que se
entrenó y el rótulo de datos sintéticos; `SimulationResult.model_validate_json` lo lee de vuelta
sin pérdida.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict

from nutrigraphdt.api.contract import (
    API_CONTRACT_VERSION,
    ScenarioContractError,
    ScenarioRequest,
)
from nutrigraphdt.simulation.compare import (
    ScenarioComparison,
    SimulationError,
    compare_scenario,
)

RESULT_FORMAT_VERSION: Final = "1.0.0"
SYNTHETIC_LABEL: Final[str] = "Datos sintéticos: no describen animales reales"


class ServiceError(RuntimeError):
    """El escenario no se pudo preparar; `problems` dice por qué."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("\n".join(problems))


class SimulationResult(BaseModel):
    """Resultado exportable de una simulación: comparación y sus metadatos."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    format_version: Literal["1.0.0"]
    contract_version: Literal["1.0.0"]
    run: str
    """Nombre de la corrida en `DEMO_RUNS`."""
    run_id: str
    commit: str | None
    """Commit con que se entrenó la corrida (de su `run.json`)."""
    dataset_id: str
    is_synthetic: bool
    data_label: str
    """`SYNTHETIC_LABEL` si los datos son sintéticos."""
    elapsed_seconds: float
    """Tiempo del par basal / intervenido en este proceso."""
    comparison: ScenarioComparison


@dataclass(frozen=True)
class Prepared:
    """Petición validada y su instancia derivada, en memoria."""

    request: ScenarioRequest
    instance: dict[str, Any]
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


@dataclass(frozen=True)
class _Records:
    metadata: Any
    instances: list[dict[str, Any]]
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    outputs: list[dict[str, Any]]


def prepare(engine: Any, request: ScenarioRequest) -> Prepared:
    """Instancia derivada del escenario, validada con `validate_graph`; no escribe en disco.

    Raises:
        ScenarioContractError: si la petición no cumple el contrato de la corrida.
        ServiceError: si la instancia derivada tiene hallazgos de error en la validación.
    """
    from nutrigraphdt.graph.validation.pipeline import validate_graph

    instance, nodes, edges = engine.base.derive(request)
    report = validate_graph(_Records(None, [instance], nodes, edges, []))
    errors = [f for f in report.findings if f.severity.name == "ERROR"]
    if errors:
        raise ServiceError([f"{f.rule_id}: {f.message}" for f in errors])
    return Prepared(request, instance, nodes, edges)


def simulate(
    engine: Any, run: str, request: ScenarioRequest, *, with_interval: bool = True
) -> SimulationResult:
    """Par basal / intervenido con el motor de la corrida `run`, listo para exportar.

    Con `with_interval` (por omisión), cada predicción estimable lleva su intervalo MC-dropout,
    calibrado si la corrida tiene calibración (A101-P1 y A101-P1b).
    """
    prepare(engine, request)
    start = time.perf_counter()
    comparison = compare_scenario(engine, request, with_interval=with_interval)
    elapsed = time.perf_counter() - start
    info = engine.loaded.info
    return SimulationResult(
        format_version=RESULT_FORMAT_VERSION,
        contract_version=API_CONTRACT_VERSION,
        run=run,
        run_id=comparison.model.run_id,
        commit=comparison.model.git_commit,
        dataset_id=str(info["dataset_id"]),
        is_synthetic=comparison.is_synthetic,
        data_label=SYNTHETIC_LABEL if comparison.is_synthetic else "Datos reales",
        elapsed_seconds=elapsed,
        comparison=comparison,
    )


def to_json(result: SimulationResult) -> str:
    return result.model_dump_json(indent=2)


def from_json(text: str) -> SimulationResult:
    return SimulationResult.model_validate_json(text)


ERROR_MESSAGES: Final[dict[str, str]] = {
    "ScenarioContractError": "El escenario no cumple el contrato de la corrida",
    "FormError": "El formulario tiene valores no válidos",
    "ServiceError": "La instancia del escenario no pasó la validación del grafo",
    "SimulationError": "Las dos predicciones no salieron del mismo modelo",
    "ImportError": "Faltan dependencias para cargar la corrida (extras graph y baselines)",
    "ModuleNotFoundError": "Faltan dependencias para cargar la corrida (extras graph y baselines)",
    "FileNotFoundError": "No se encontró la corrida congelada",
}
UNEXPECTED_MESSAGE: Final[str] = (
    "El motor falló de forma inesperada. El detalle quedó en el registro del servidor."
)


def user_message(error: BaseException) -> tuple[str, list[str]]:
    """Mensaje para el usuario y sus detalles, sin traza, para cada clase de error del motor."""
    name = type(error).__name__
    title = ERROR_MESSAGES.get(name)
    if title is None:
        return UNEXPECTED_MESSAGE, []
    problems = getattr(error, "problems", None)
    if problems:
        return title, [str(p) for p in problems]
    if isinstance(error, ImportError | FileNotFoundError):
        return title, [str(error)]
    return title, [str(error)] if str(error) else []


__all__ = [
    "ERROR_MESSAGES",
    "RESULT_FORMAT_VERSION",
    "SYNTHETIC_LABEL",
    "UNEXPECTED_MESSAGE",
    "Prepared",
    "ScenarioContractError",
    "ServiceError",
    "SimulationError",
    "SimulationResult",
    "from_json",
    "prepare",
    "simulate",
    "to_json",
    "user_message",
]
