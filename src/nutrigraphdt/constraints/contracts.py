"""Versioned contracts for differentiable constraint evaluation."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from torch import Tensor

CONSTRAINTS_CONTRACT_VERSION = "1.0.0"
"""Version of the public constraint metadata and evaluation contract."""


class ConstraintKind(StrEnum):
    """Mathematical form of a constraint operator."""

    INEQUALITY = "inequality"
    EQUALITY = "equality"


class ConstraintSpace(StrEnum):
    """Physical representation consumed by a constraint."""

    FRACTIONS = "fractions"
    CONCENTRATIONS = "concentrations"


class ConstraintStatus(StrEnum):
    """Implementation/scientific status recorded with a constraint."""

    ACTIVE = "active"
    PENDING_D06 = "pending_d06"


@dataclass(frozen=True)
class ConstraintMetadata:
    """Serializable, versioned description of one constraint."""

    name: str
    kind: ConstraintKind
    space: ConstraintSpace
    unit: str
    tolerance: float
    version: str = "1.0.0"
    status: ConstraintStatus = ConstraintStatus.ACTIVE

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ConstraintKind):
            raise ValueError("kind debe ser ConstraintKind.")
        if not isinstance(self.space, ConstraintSpace):
            raise ValueError("space debe ser ConstraintSpace.")
        if not isinstance(self.status, ConstraintStatus):
            raise ValueError("status debe ser ConstraintStatus.")
        if not self.name.strip():
            raise ValueError("El nombre de la restricción no puede estar vacío.")
        if not self.unit.strip():
            raise ValueError("La unidad de la restricción no puede estar vacía.")
        if not self.version.strip():
            raise ValueError("La versión de la restricción no puede estar vacía.")
        if (
            isinstance(self.tolerance, bool)
            or not math.isfinite(self.tolerance)
            or self.tolerance < 0
        ):
            raise ValueError("La tolerancia debe ser finita y no negativa.")
        if self.kind is ConstraintKind.INEQUALITY and self.tolerance != 0:
            raise ValueError("Las desigualdades usan tolerancia 0; solo igualdades usan epsilon.")

    def to_dict(self) -> dict[str, str | float]:
        """Return JSON-compatible contract metadata."""
        return {
            "contract_version": CONSTRAINTS_CONTRACT_VERSION,
            "name": self.name,
            "kind": self.kind.value,
            "space": self.space.value,
            "unit": self.unit,
            "tolerance": self.tolerance,
            "version": self.version,
            "status": self.status.value,
        }


class Constraint(Protocol):
    """One named scalar operator evaluated independently for every sample."""

    @property
    def metadata(self) -> ConstraintMetadata: ...

    def evaluate(self, values: Tensor) -> Tensor:
        """Return ``h`` or ``g`` with exactly one value per input sample."""


@dataclass(frozen=True)
class FunctionalConstraint:
    """Constraint implementation pairing versioned metadata with a tensor operator."""

    metadata: ConstraintMetadata
    operator: Callable[[Tensor], Tensor]

    def evaluate(self, values: Tensor) -> Tensor:
        return self.operator(values)


@dataclass(frozen=True)
class ConstraintInputs:
    """Real-unit inputs supplied to constraint operators.

    Values are never scaled targets. For compositional model outputs, first pass the
    descaled ``(z1, z2, ln T)`` tensor to ``compositional_constraint_inputs``.
    """

    fractions: Tensor | None = None
    concentrations: Tensor | None = None

    def for_space(self, space: ConstraintSpace) -> Tensor:
        values = self.fractions if space is ConstraintSpace.FRACTIONS else self.concentrations
        if values is None:
            raise ValueError(f"No se proporcionaron valores para el espacio '{space.value}'.")
        return values


@dataclass(frozen=True)
class ConstraintResult:
    """Differentiable values and violation magnitudes for one constraint."""

    metadata: ConstraintMetadata
    values: Tensor
    magnitudes: Tensor
    violated: Tensor


class ConstraintEvaluationError(ValueError):
    """Raised when predictions cannot be evaluated against the constraint contract."""


__all__ = [
    "CONSTRAINTS_CONTRACT_VERSION",
    "Constraint",
    "ConstraintEvaluationError",
    "ConstraintInputs",
    "ConstraintKind",
    "ConstraintMetadata",
    "ConstraintResult",
    "ConstraintSpace",
    "ConstraintStatus",
    "FunctionalConstraint",
]
