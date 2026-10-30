"""Restricciones bioquímicas aprobadas en D-06 v1."""

from __future__ import annotations

from typing import Final

from nutrigraphdt.constraints.contracts import (
    Constraint,
    ConstraintKind,
    ConstraintMetadata,
    ConstraintSpace,
    FunctionalConstraint,
)

D06_PROPIONATE_BOUND_NAME: Final[str] = "d06.hydrogen.propionate_bound"
D06_PROPIONATE_BOUND_VERSION: Final[str] = "1.0.0"
D06_SOURCE_PATH: Final[str] = "docs/research/D-06 — Restricciones bioquímicas para D1.md"
D06_SOURCE_VERSION: Final[str] = "1.0"
D06_SOURCE_DATE: Final[str] = "29-10-2026"
D06_SOURCE_SECTION: Final[str] = "3.5"


def d06_constraints() -> tuple[Constraint, ...]:
    """Devuelve las restricciones activas de D-06 v1."""
    metadata = ConstraintMetadata(
        name=D06_PROPIONATE_BOUND_NAME,
        kind=ConstraintKind.INEQUALITY,
        space=ConstraintSpace.FRACTIONS,
        unit="1",
        tolerance=0.0,
        version=D06_PROPIONATE_BOUND_VERSION,
    )
    return (
        FunctionalConstraint(
            metadata,
            lambda values: values[:, 1] - 2.0 * (values[:, 0] + values[:, 2]),
        ),
    )


__all__ = [
    "D06_PROPIONATE_BOUND_NAME",
    "D06_PROPIONATE_BOUND_VERSION",
    "D06_SOURCE_DATE",
    "D06_SOURCE_PATH",
    "D06_SOURCE_SECTION",
    "D06_SOURCE_VERSION",
    "d06_constraints",
]
