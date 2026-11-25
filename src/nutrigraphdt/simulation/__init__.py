"""Simulación de escenarios de referencia (A93, #308).

- `catalog`: catálogo versionado de escenarios de `configs/scenarios/` (A93-P2).
- `compare`: comparación basal / intervenido con el mismo modelo congelado y criterios de
  resultado por AGCC (A93-P1 y A93-P3).

Reutiliza el motor de `nutrigraphdt.api` (#287); no crea otro. Ninguno de los dos módulos importa
PyTorch: el motor se carga solo al construir un `ScenarioEngine`.

**Datos sintéticos.** Los escenarios derivan de la cohorte sintética: una diferencia entre un
escenario y su basal describe al modelo, no un efecto biológico. Ver
`docs/models/scenario-comparison.md`.
"""

from __future__ import annotations

from nutrigraphdt.simulation.catalog import (
    CATALOG_DIR,
    CatalogError,
    CatalogScenario,
    load_catalog,
    load_scenario,
    scenario_by_id,
)
from nutrigraphdt.simulation.compare import (
    DIFFERENCE_WARNING,
    QUANTITIES,
    UNITS,
    QuantityDifference,
    ScenarioComparison,
    SimulationError,
    build_comparison,
    checkpoint_sha256,
    compare_scenario,
)

__all__ = [
    "CATALOG_DIR",
    "DIFFERENCE_WARNING",
    "QUANTITIES",
    "UNITS",
    "CatalogError",
    "CatalogScenario",
    "QuantityDifference",
    "ScenarioComparison",
    "SimulationError",
    "build_comparison",
    "checkpoint_sha256",
    "compare_scenario",
    "load_catalog",
    "load_scenario",
    "scenario_by_id",
]
