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
from nutrigraphdt.explainability.subgraph import (
    DEFAULT_SELECTION,
    DEFAULT_TIE_BREAK,
    ExplanatorySubgraphView,
    SubgraphEdgeView,
    SubgraphNodeView,
    extract_subgraph_view,
    extract_top_k_subgraph,
    load_explanation,
    load_subgraph_view,
    serialize_explanation,
    serialize_subgraph_view,
)

if TYPE_CHECKING:
    from nutrigraphdt.explainability.importance import (
        compute_attribute_importance,
        compute_edge_importance,
        compute_node_importance,
        compute_norm_factor,
    )
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

_IMPORTANCE_NAMES = frozenset(
    {
        "compute_attribute_importance",
        "compute_edge_importance",
        "compute_node_importance",
        "compute_norm_factor",
    }
)


def __getattr__(name: str) -> Any:
    if name in _WRAPPER_NAMES:
        wrapper = importlib.import_module("nutrigraphdt.explainability.wrapper")
        return getattr(wrapper, name)
    if name in _IMPORTANCE_NAMES:
        importance = importlib.import_module("nutrigraphdt.explainability.importance")
        return getattr(importance, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ATTENTION_WARNING",
    "AttributeImportance",
    "DEFAULT_MODEL_CONFIG",
    "DEFAULT_SELECTION",
    "DEFAULT_TIE_BREAK",
    "EVIDENCE_METHOD_STATUS",
    "EXPLANATION_FORMAT",
    "EXPLANATION_FORMAT_VERSION",
    "EdgeImportance",
    "EdgeRef",
    "Evidence",
    "ExplainerRef",
    "Explanation",
    "ExplanationContractError",
    "ExplanatorySubgraphView",
    "HeteroAdapter",
    "HeteroExplainer",
    "HeteroExplainerConfig",
    "Importance",
    "IncompatibleExplainerError",
    "NodeImportance",
    "NodeRef",
    "REQUIRED_WARNINGS",
    "RunRef",
    "SYNTHETIC_WARNING",
    "Scale",
    "SplitRef",
    "Subgraph",
    "SubgraphEdgeView",
    "SubgraphNodeView",
    "TargetRef",
    "Warning_",
    "compute_attribute_importance",
    "compute_edge_importance",
    "compute_node_importance",
    "compute_norm_factor",
    "edge_mask_effect",
    "edge_mask_reach",
    "explained_inputs",
    "extract_subgraph_view",
    "extract_top_k_subgraph",
    "load_explanation",
    "load_subgraph_view",
    "serialize_explanation",
    "serialize_subgraph_view",
    "validate_explanation",
]
