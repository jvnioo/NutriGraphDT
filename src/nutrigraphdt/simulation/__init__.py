"""Módulo de simulación de escenarios de referencia para NutriGraphDT (A93, #308).

Compara el escenario basal y el intervenido con el mismo modelo congelado y
devuelve la diferencia por AGCC con unidades explícitas y el estado de estimabilidad
(«no estimable» cuando la predicción queda fuera del soporte empírico del train).

**Datos sintéticos.** Los escenarios proceden de la cohorte sintética (DS-04/DS-05)
y no de observaciones reales. Los resultados describen el comportamiento del modelo
sobre datos sintéticos; no representan efectos biológicos causales.
"""

from nutrigraphdt.simulation.outcome import (
    SCFA_UNITS,
    SYNTHETIC_DATA_WARNING,
    OutcomeStatus,
    ScfaDiff,
    ScfaOutcome,
    compute_scfa_diff,
)
from nutrigraphdt.simulation.runner import (
    ScenarioPair,
    ScenarioResult,
    SimulationError,
    run_scenario_pair,
)

__all__ = [
    "SCFA_UNITS",
    "SYNTHETIC_DATA_WARNING",
    "OutcomeStatus",
    "ScenarioPair",
    "ScenarioResult",
    "ScfaDiff",
    "ScfaOutcome",
    "SimulationError",
    "compute_scfa_diff",
    "run_scenario_pair",
]
