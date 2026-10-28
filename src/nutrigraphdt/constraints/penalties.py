"""Penalizaciones con pesos explícitos, separadas de las pérdidas de datos (A57-P1, #163)."""

from __future__ import annotations

import math
from collections.abc import Mapping
from numbers import Real

from torch import Tensor

from nutrigraphdt.constraints.contracts import ConstraintEvaluationError, ConstraintResult


def constraint_penalty(
    results: tuple[ConstraintResult, ...], weights: Mapping[str, Real]
) -> Tensor:
    """Devuelve la suma ponderada de las magnitudes de violación cuadráticas medias.

    Cada restricción evaluada debe tener exactamente un peso explícito, finito y no negativo.
    La elección de esos pesos queda fuera del Issue #163.
    """
    names = {result.metadata.name for result in results}
    if not names:
        raise ConstraintEvaluationError("No hay resultados de restricciones para penalizar.")
    if len(names) != len(results):
        raise ConstraintEvaluationError("Los nombres de las restricciones deben ser únicos.")
    missing = names - set(weights)
    unknown = set(weights) - names
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append(f"faltan pesos para {sorted(missing)}")
        if unknown:
            details.append(f"pesos para restricciones desconocidas {sorted(unknown)}")
        raise ConstraintEvaluationError("Mapa de lambdas inválido: " + "; ".join(details) + ".")

    penalty: Tensor | None = None
    for result in results:
        weight = weights[result.metadata.name]
        if isinstance(weight, bool) or not isinstance(weight, Real):
            raise ConstraintEvaluationError(
                f"El lambda de '{result.metadata.name}' debe ser un número real."
            )
        value = float(weight)
        if not math.isfinite(value) or value < 0:
            raise ConstraintEvaluationError(
                f"El lambda de '{result.metadata.name}' debe ser finito y no negativo."
            )
        term = value * result.magnitudes.square().mean()
        penalty = term if penalty is None else penalty + term
    assert penalty is not None
    return penalty


__all__ = ["constraint_penalty"]
