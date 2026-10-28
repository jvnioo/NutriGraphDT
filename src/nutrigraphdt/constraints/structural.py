"""Restricciones estructurales de no negatividad y cierre simplex (A57-P1, #163)."""

from __future__ import annotations

from typing import Final

from nutrigraphdt.constraints.contracts import (
    Constraint,
    ConstraintKind,
    ConstraintMetadata,
    ConstraintSpace,
    FunctionalConstraint,
)

STRUCTURAL_CLOSURE_TOLERANCE: Final[float] = 1e-6
"""Tolerancia numérica adimensional para el cierre simplex en float32."""

_COMPONENTS: Final[tuple[str, ...]] = ("acetate", "propionate", "butyrate")


def _nonnegative_constraint(
    *, space: ConstraintSpace, unit: str, component: str, column: int
) -> Constraint:
    metadata = ConstraintMetadata(
        name=f"structural.non_negative.{space.value}.{component}",
        kind=ConstraintKind.INEQUALITY,
        space=space,
        unit=unit,
        tolerance=0.0,
    )
    return FunctionalConstraint(metadata, lambda values: -values[:, column])


def structural_constraints() -> tuple[Constraint, ...]:
    """Devuelve las restricciones estructurales activas sobre fracciones y concentraciones."""
    constraints: list[Constraint] = []
    for space, unit in (
        (ConstraintSpace.FRACTIONS, "1"),
        (ConstraintSpace.CONCENTRATIONS, "mmol/kg"),
    ):
        constraints.extend(
            _nonnegative_constraint(
                space=space,
                unit=unit,
                component=component,
                column=column,
            )
            for column, component in enumerate(_COMPONENTS)
        )

    closure_metadata = ConstraintMetadata(
        name="structural.simplex_closure",
        kind=ConstraintKind.EQUALITY,
        space=ConstraintSpace.FRACTIONS,
        unit="1",
        tolerance=STRUCTURAL_CLOSURE_TOLERANCE,
    )
    constraints.append(
        FunctionalConstraint(
            closure_metadata,
            lambda fractions: fractions.sum(dim=1) - 1.0,
        )
    )
    return tuple(constraints)


__all__ = ["STRUCTURAL_CLOSURE_TOLERANCE", "structural_constraints"]
