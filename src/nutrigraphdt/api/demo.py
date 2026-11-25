"""Catálogo de corridas y escenarios de demostración de la plataforma (A81-P2, #288).

La interfaz y las pruebas eligen una corrida de `DEMO_RUNS` y piden sus escenarios de ejemplo
con `demo_scenarios`; no conocen rutas ni cómo se arma la base. Las corridas están congeladas en
`tests/fixtures/api/frozen_runs/` (las regenera `scripts/build_api_fixtures.py`) y los
escenarios en `tests/fixtures/api/scenarios.json`. Ver `tests/fixtures/api/README.md`.

Son corridas de **demostración**, entrenadas con pocos animales y pocas épocas: sirven para
probar la plataforma sin red ni la descarga completa de D1, y sus predicciones no tienen valor
científico.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from nutrigraphdt.api.contract import ScenarioRequest
from nutrigraphdt.api.engine import REPO_ROOT, ScenarioBase, ScenarioEngine, d1_base

FIXTURES_DIR: Final[Path] = REPO_ROOT / "tests" / "fixtures" / "api"
FROZEN_RUNS_DIR: Final[Path] = FIXTURES_DIR / "frozen_runs"
SCENARIOS_FILE: Final[Path] = FIXTURES_DIR / "scenarios.json"

SYNTHETIC_ANIMALS: Final[int] = 20
"""Animales de la cohorte sintética de la corrida `synthetic` (semillas 1 a 20)."""
SYNTHETIC_FIRST_SEED: Final[int] = 1


def _synthetic_base() -> ScenarioBase:
    from nutrigraphdt.api.engine import synthetic_cohort_base

    return synthetic_cohort_base(SYNTHETIC_ANIMALS, first_seed=SYNTHETIC_FIRST_SEED)


@dataclass(frozen=True)
class DemoRun:
    """Corrida congelada de demostración y la base de escenarios con que se entrenó."""

    name: str
    label: str
    description: str
    is_synthetic: bool
    run_dir: Path
    _base: Callable[[], ScenarioBase]

    def base(self) -> ScenarioBase:
        return self._base()

    def engine(self, *, device: str = "cpu") -> ScenarioEngine:
        """Motor de la corrida; cárguelo una vez y reutilícelo."""
        return ScenarioEngine(self.run_dir, self.base(), device=device)


DEMO_RUNS: Final[dict[str, DemoRun]] = {
    "synthetic": DemoRun(
        name="synthetic",
        label="Cohorte sintética (20 animales)",
        description=(
            "Datos sintéticos: cohorte de build_synthetic_cohort con semillas 1 a 20. Dieta, "
            "aditivo y edad son iguales en todos los animales; solo varían el peso y el sexo."
        ),
        is_synthetic=True,
        run_dir=FROZEN_RUNS_DIR / "synthetic",
        _base=_synthetic_base,
    ),
    "d1_fixture": DemoRun(
        name="d1_fixture",
        label="Fixture de D1 (6 animales reales)",
        description=(
            "Datos reales: los seis animales de HoloFood de tests/fixtures/holofood/. El grafo "
            "de D1 tiene 3 de las 11 relaciones del esquema v1."
        ),
        is_synthetic=False,
        run_dir=FROZEN_RUNS_DIR / "d1_fixture",
        _base=d1_base,
    ),
}


@dataclass(frozen=True)
class DemoScenario:
    """Escenario de ejemplo de una corrida de demostración, con el resultado que se espera."""

    id: str
    run: str
    label: str
    note: str
    expected_status: Literal["estimable", "no_estimable"]
    request: ScenarioRequest


def demo_scenarios(run: str | None = None, path: str | Path = SCENARIOS_FILE) -> list[DemoScenario]:
    """Escenarios de ejemplo de `scenarios.json`; solo los de `run` si se indica.

    Raises:
        ValueError: si un escenario nombra una corrida que no está en `DEMO_RUNS`.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    scenarios: list[DemoScenario] = []
    for item in data["scenarios"]:
        if item["run"] not in DEMO_RUNS:
            raise ValueError(f"El escenario {item['id']!r} nombra una corrida desconocida.")
        scenarios.append(
            DemoScenario(
                id=item["id"],
                run=item["run"],
                label=item["label"],
                note=item["note"],
                expected_status=item["expected_status"],
                request=ScenarioRequest.model_validate(item["request"]),
            )
        )
    return [s for s in scenarios if run is None or s.run == run]


__all__ = [
    "DEMO_RUNS",
    "FIXTURES_DIR",
    "FROZEN_RUNS_DIR",
    "SCENARIOS_FILE",
    "SYNTHETIC_ANIMALS",
    "SYNTHETIC_FIRST_SEED",
    "DemoRun",
    "DemoScenario",
    "demo_scenarios",
]
