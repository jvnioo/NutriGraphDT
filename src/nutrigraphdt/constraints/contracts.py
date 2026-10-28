"""Contratos versionados para evaluar restricciones diferenciables (A57-P1, #163)."""

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
    """Forma matemática del operador de restricción."""

    INEQUALITY = "inequality"
    EQUALITY = "equality"


class ConstraintSpace(StrEnum):
    """Representación física que recibe una restricción."""

    FRACTIONS = "fractions"
    CONCENTRATIONS = "concentrations"


class ConstraintStatus(StrEnum):
    """Estado de implementación o científico registrado para una restricción."""

    ACTIVE = "active"
    PENDING_D06 = "pending_d06"


@dataclass(frozen=True)
class ConstraintMetadata:
    """Descripción serializable y versionada de una restricción."""

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
        """Devuelve metadatos del contrato compatibles con JSON."""
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
    """Operador escalar con nombre, evaluado independientemente por muestra."""

    @property
    def metadata(self) -> ConstraintMetadata: ...

    def evaluate(self, values: Tensor) -> Tensor:
        """Devuelve ``h`` o ``g`` con exactamente un valor por muestra de entrada."""


@dataclass(frozen=True)
class FunctionalConstraint:
    """Implementación que asocia metadatos versionados con un operador tensorial."""

    metadata: ConstraintMetadata
    operator: Callable[[Tensor], Tensor]

    def evaluate(self, values: Tensor) -> Tensor:
        return self.operator(values)


@dataclass(frozen=True)
class ConstraintInputs:
    """Entradas en unidades reales que se entregan a los operadores.

    Los valores nunca son objetivos escalados. Para salidas composicionales, primero se pasa
    el tensor ``(z1, z2, ln T)`` des-escalado a ``compositional_constraint_inputs``.
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
    """Valores diferenciables y magnitudes de violación de una restricción."""

    metadata: ConstraintMetadata
    values: Tensor
    magnitudes: Tensor
    violated: Tensor


class ConstraintEvaluationError(ValueError):
    """Error cuando las predicciones no se pueden evaluar según el contrato."""


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
