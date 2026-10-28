"""Explicabilidad de los modelos de NutriGraphDT (F7).

Por ahora contiene el contrato de salida de las explicaciones (A55-P3, #156). El wrapper de
explicadores para `HeteroData` llega con A60-P1 (#170).
"""

from nutrigraphdt.explainability.contract import (
    EXPLANATION_FORMAT,
    EXPLANATION_FORMAT_VERSION,
    Explanation,
    ExplanationContractError,
    validate_explanation,
)

__all__ = [
    "EXPLANATION_FORMAT",
    "EXPLANATION_FORMAT_VERSION",
    "Explanation",
    "ExplanationContractError",
    "validate_explanation",
]
