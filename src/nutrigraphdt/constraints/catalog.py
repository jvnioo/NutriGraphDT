"""Catálogo único de restricciones activas para configuración y selección."""

from __future__ import annotations

from nutrigraphdt.constraints.contracts import Constraint
from nutrigraphdt.constraints.d06 import d06_constraints
from nutrigraphdt.constraints.structural import structural_constraints


def constraint_catalog() -> dict[str, Constraint]:
    """Devuelve las restricciones activas indexadas por su nombre estable."""
    constraints = (*structural_constraints(), *d06_constraints())
    catalog = {constraint.metadata.name: constraint for constraint in constraints}
    if len(catalog) != len(constraints):
        raise RuntimeError("El catálogo contiene nombres de restricciones duplicados.")
    return catalog


__all__ = ["constraint_catalog"]
