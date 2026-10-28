"""Explicabilidad de los modelos de NutriGraphDT (F7).

Contiene el contrato de salida de las explicaciones (A55-P3, #156) y el wrapper de
explicadores para `HeteroData` (A60-P1, #170). El contrato solo depende de pydantic; el
wrapper requiere el extra `graph` y se importa al primer acceso a uno de sus nombres.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from nutrigraphdt.explainability.contract import (
    ATTENTION_WARNING,
    EVIDENCE_METHOD_STATUS,
    EXPLANATION_FORMAT,
    EXPLANATION_FORMAT_VERSION,
    REQUIRED_WARNINGS,
    SYNTHETIC_WARNING,
    AttributeImportance,
    EdgeImportance,
    EdgeRef,
    Evidence,
    ExplainerRef,
    Explanation,
    ExplanationContractError,
    Importance,
    NodeImportance,
    NodeRef,
    RunRef,
    Scale,
    SplitRef,
    Subgraph,
    TargetRef,
    Warning_,
    validate_explanation,
)

if TYPE_CHECKING:
    from nutrigraphdt.explainability.wrapper import (
        DEFAULT_MODEL_CONFIG,
        HeteroAdapter,
        HeteroExplainer,
        HeteroExplainerConfig,
        IncompatibleExplainerError,
        edge_mask_effect,
        edge_mask_reach,
        explained_inputs,
    )

_WRAPPER_NAMES = frozenset(
    {
        "DEFAULT_MODEL_CONFIG",
        "HeteroAdapter",
        "HeteroExplainer",
        "HeteroExplainerConfig",
        "IncompatibleExplainerError",
        "edge_mask_effect",
        "edge_mask_reach",
        "explained_inputs",
    }
)


def __getattr__(name: str) -> Any:
    if name in _WRAPPER_NAMES:
        wrapper = importlib.import_module("nutrigraphdt.explainability.wrapper")
        return getattr(wrapper, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ATTENTION_WARNING",
    "DEFAULT_MODEL_CONFIG",
    "EVIDENCE_METHOD_STATUS",
    "EXPLANATION_FORMAT",
    "EXPLANATION_FORMAT_VERSION",
    "HeteroAdapter",
    "HeteroExplainer",
    "HeteroExplainerConfig",
    "IncompatibleExplainerError",
    "REQUIRED_WARNINGS",
    "SYNTHETIC_WARNING",
    "AttributeImportance",
    "EdgeImportance",
    "EdgeRef",
    "Evidence",
    "Explanation",
    "ExplanationContractError",
    "ExplainerRef",
    "Importance",
    "NodeImportance",
    "NodeRef",
    "RunRef",
    "Scale",
    "SplitRef",
    "Subgraph",
    "TargetRef",
    "Warning_",
    "edge_mask_effect",
    "edge_mask_reach",
    "explained_inputs",
    "validate_explanation",
]
