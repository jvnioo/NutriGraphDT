"""Restricciones estructurales diferenciables y reporte independiente (A57-P1, #163)."""

from nutrigraphdt.constraints.contracts import (
    CONSTRAINTS_CONTRACT_VERSION,
    Constraint,
    ConstraintEvaluationError,
    ConstraintInputs,
    ConstraintKind,
    ConstraintMetadata,
    ConstraintResult,
    ConstraintSpace,
    ConstraintStatus,
    FunctionalConstraint,
)
from nutrigraphdt.constraints.evaluation import (
    ConstraintEvaluation,
    ConstraintViolationSummary,
    ViolationRecord,
    ViolationSummary,
    compositional_constraint_inputs,
    evaluate_constraints,
)
from nutrigraphdt.constraints.penalties import constraint_penalty
from nutrigraphdt.constraints.structural import (
    STRUCTURAL_CLOSURE_TOLERANCE,
    structural_constraints,
)

__all__ = [
    "CONSTRAINTS_CONTRACT_VERSION",
    "STRUCTURAL_CLOSURE_TOLERANCE",
    "Constraint",
    "ConstraintEvaluation",
    "ConstraintEvaluationError",
    "ConstraintInputs",
    "ConstraintKind",
    "ConstraintMetadata",
    "ConstraintResult",
    "ConstraintSpace",
    "ConstraintStatus",
    "ConstraintViolationSummary",
    "FunctionalConstraint",
    "ViolationRecord",
    "ViolationSummary",
    "compositional_constraint_inputs",
    "constraint_penalty",
    "evaluate_constraints",
    "structural_constraints",
]
