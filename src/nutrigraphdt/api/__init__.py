"""Capa entre el motor y la interfaz (A81-P1, #287): contrato versionado y motor de escenarios.

La interfaz importa solo este paquete. `contract` no depende de PyTorch; el motor
(`ScenarioEngine`, `predict_scenario` y las bases de escenarios) y el catálogo de demostración
(`DEMO_RUNS`, `demo_scenarios`; A81-P2, #288) se importan al usarlos, así que la interfaz arranca
sin cargar los extras `graph` y `baselines`. Ver `docs/architecture/api-contract.md`.
"""

from __future__ import annotations

from typing import Any

from nutrigraphdt.api.contract import (
    API_CONTRACT_VERSION,
    CAUSAL_WARNING,
    ESTIMABLE,
    NOT_ESTIMABLE,
    SCFA_COMPONENTS,
    SYNTHETIC_WARNING,
    Bounds,
    InterventionItem,
    ModelRef,
    PredictionInterval,
    ScenarioContractError,
    ScenarioRequest,
    ScenarioResponse,
    ScenarioVariable,
    SCFAFractions,
    SupportRef,
)

_ENGINE_NAMES = frozenset(
    {
        "BASAL_WARNING",
        "COVERAGE_WARNING",
        "D1_DATASET_ID",
        "D1_FIXTURE_DATASET_ID",
        "D1_FIXTURE_WARNING",
        "D1_PARTIAL_WARNING",
        "IN_TRAIN_WARNING",
        "INTERVENABLE_NODE_TYPES",
        "ScenarioBase",
        "ScenarioEngine",
        "d1_base",
        "predict_scenario",
        "synthetic_cohort_base",
    }
)


_DEMO_NAMES = frozenset({"DEMO_RUNS", "DemoRun", "DemoScenario", "demo_scenarios"})


def __getattr__(name: str) -> Any:
    if name in _ENGINE_NAMES:
        from nutrigraphdt.api import engine

        return getattr(engine, name)
    if name in _DEMO_NAMES:
        from nutrigraphdt.api import demo

        return getattr(demo, name)
    raise AttributeError(f"module 'nutrigraphdt.api' has no attribute {name!r}")


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
    "ScenarioContractError",
    "ScenarioRequest",
    "ScenarioResponse",
    "ScenarioVariable",
    "SupportRef",
    *sorted(_ENGINE_NAMES),
    *sorted(_DEMO_NAMES),
]
