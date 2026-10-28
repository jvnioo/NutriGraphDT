"""Vectorized constraint evaluation, per-sample records, and violation summaries."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import torch
from torch import Tensor

from nutrigraphdt.constraints.contracts import (
    CONSTRAINTS_CONTRACT_VERSION,
    Constraint,
    ConstraintEvaluationError,
    ConstraintInputs,
    ConstraintMetadata,
    ConstraintResult,
)
from nutrigraphdt.constraints.structural import structural_constraints


@dataclass(frozen=True)
class ViolationRecord:
    """One evaluated constraint for one included sample."""

    sample_id: str
    constraint: str
    kind: str
    value: float
    magnitude: float
    violated: bool
    unit: str

    def to_dict(self) -> dict[str, str | float | bool]:
        return {
            "sample_id": self.sample_id,
            "constraint": self.constraint,
            "kind": self.kind,
            "value": self.value,
            "magnitude": self.magnitude,
            "violated": self.violated,
            "unit": self.unit,
        }


@dataclass(frozen=True)
class ConstraintViolationSummary:
    """Protocol metrics for one constraint over valid evaluation samples."""

    metadata: ConstraintMetadata
    sample_count: int
    violation_count: int
    violation_rate_percent: float
    mean_magnitude: float
    conditional_mean_magnitude: float | None
    worst_case_magnitude: float
    percentile_95: float

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.metadata.to_dict(),
            "sample_count": self.sample_count,
            "violation_count": self.violation_count,
            "VR_percent": self.violation_rate_percent,
            "VMM": self.mean_magnitude,
            "VMM_conditional": self.conditional_mean_magnitude,
            "VWM": self.worst_case_magnitude,
            "P95": self.percentile_95,
        }


@dataclass(frozen=True)
class ViolationSummary:
    """Serializable aggregate for all active constraints in an evaluation."""

    sample_count: int
    excluded_sample_count: int
    constraints: tuple[ConstraintViolationSummary, ...]
    joint_feasibility_rate_percent: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": CONSTRAINTS_CONTRACT_VERSION,
            "sample_count": self.sample_count,
            "excluded_sample_count": self.excluded_sample_count,
            "constraints": [summary.to_dict() for summary in self.constraints],
            "FR_percent": self.joint_feasibility_rate_percent,
        }


@dataclass(frozen=True)
class ConstraintEvaluation:
    """Full differentiable evaluation plus detached records and summary."""

    results: tuple[ConstraintResult, ...]
    records: tuple[ViolationRecord, ...]
    summary: ViolationSummary


def compositional_constraint_inputs(output: Tensor) -> ConstraintInputs:
    """Convert already-descaled ``(z1, z2, ln T)`` to fractions and mmol/kg.

    The inverse conversion is delegated to ``models.gnn.target``; no target scaler is
    imported or applied here.
    """
    if output.dim() != 2 or output.shape[1] != 3:
        raise ConstraintEvaluationError(
            f"La salida des-escalada debe tener forma [B, 3]; tiene {list(output.shape)}."
        )
    from nutrigraphdt.models.gnn.target import concentrations_from_graph_output

    concentrations = concentrations_from_graph_output(output)
    total = concentrations.sum(dim=1, keepdim=True)
    fractions = concentrations / total
    return ConstraintInputs(fractions=fractions, concentrations=concentrations)


def _validity_mask(
    valid_mask: Tensor | Sequence[bool] | None,
    *,
    sample_count: int,
    device: torch.device,
) -> Tensor:
    if valid_mask is None:
        return torch.ones(sample_count, dtype=torch.bool, device=device)
    if isinstance(valid_mask, Tensor):
        if valid_mask.dtype != torch.bool or valid_mask.dim() != 1:
            raise ConstraintEvaluationError("valid_mask debe ser un tensor booleano de forma [B].")
        mask = valid_mask.to(device=device)
    else:
        if any(not isinstance(value, bool) for value in valid_mask):
            raise ConstraintEvaluationError("valid_mask debe contener solo valores booleanos.")
        mask = torch.tensor(valid_mask, dtype=torch.bool, device=device)
    if mask.numel() != sample_count:
        raise ConstraintEvaluationError(
            f"valid_mask contiene {mask.numel()} valores; se esperaban {sample_count}."
        )
    return mask


def _summarize_result(
    metadata: ConstraintMetadata, magnitudes: Tensor, violated: Tensor
) -> ConstraintViolationSummary:
    values = magnitudes.detach().to(torch.float64)
    violation_count = int(violated.sum().item())
    conditional = float(values[violated].mean().item()) if violation_count else None
    p95 = torch.quantile(values, 0.95, interpolation="linear")
    return ConstraintViolationSummary(
        metadata=metadata,
        sample_count=values.numel(),
        violation_count=violation_count,
        violation_rate_percent=100.0 * violation_count / values.numel(),
        mean_magnitude=float(values.mean().item()),
        conditional_mean_magnitude=conditional,
        worst_case_magnitude=float(values.max().item()),
        percentile_95=float(p95.item()),
    )


def evaluate_constraints(
    inputs: ConstraintInputs,
    sample_ids: Sequence[str],
    *,
    constraints: Sequence[Constraint] | None = None,
    valid_mask: Tensor | Sequence[bool] | None = None,
) -> ConstraintEvaluation:
    """Evaluate constraints on real-unit tensors and summarize only valid samples.

    A sample is violated exactly when its calculated magnitude is greater than zero.
    Excluded samples produce no records and do not enter any reported metric.
    """
    active_constraints = tuple(constraints) if constraints is not None else structural_constraints()
    if not active_constraints:
        raise ConstraintEvaluationError("Se requiere al menos una restricción activa.")
    names = [constraint.metadata.name for constraint in active_constraints]
    if len(set(names)) != len(names):
        raise ConstraintEvaluationError("Los nombres de las restricciones deben ser únicos.")
    if any(constraint.metadata.status.value != "active" for constraint in active_constraints):
        raise ConstraintEvaluationError("Solo se pueden evaluar restricciones con estado 'active'.")

    available = [
        inputs.fractions if inputs.fractions is not None else None,
        inputs.concentrations if inputs.concentrations is not None else None,
    ]
    tensors = [values for values in available if values is not None]
    if not tensors:
        raise ConstraintEvaluationError("No se proporcionaron tensores de entrada.")
    sample_count = tensors[0].shape[0] if tensors[0].dim() == 2 else -1
    if sample_count < 0:
        raise ConstraintEvaluationError("Los tensores de entrada deben tener forma [B, D].")
    if len(sample_ids) != sample_count:
        raise ConstraintEvaluationError(
            f"sample_ids contiene {len(sample_ids)} IDs; se esperaban {sample_count}."
        )
    device = tensors[0].device
    for values in tensors:
        if values.dim() != 2 or values.shape[0] != sample_count:
            raise ConstraintEvaluationError(
                "Todos los tensores de entrada deben tener forma [B, D]."
            )
        if not torch.is_floating_point(values):
            raise ConstraintEvaluationError("Los tensores de entrada deben usar un tipo flotante.")
        if values.device != device:
            raise ConstraintEvaluationError(
                "Los tensores de entrada deben estar en el mismo device."
            )

    mask = _validity_mask(valid_mask, sample_count=sample_count, device=device)
    valid_count = int(mask.sum().item())
    if valid_count == 0:
        raise ConstraintEvaluationError("No hay muestras válidas para evaluar las restricciones.")
    excluded_count = sample_count - valid_count
    included_ids = [str(sample_ids[index]) for index, keep in enumerate(mask.tolist()) if keep]
    results: list[ConstraintResult] = []
    records: list[ViolationRecord] = []
    summaries: list[ConstraintViolationSummary] = []

    for constraint in active_constraints:
        try:
            values = inputs.for_space(constraint.metadata.space)
        except ValueError as error:
            raise ConstraintEvaluationError(str(error)) from error
        selected = values[mask]
        if not bool(torch.isfinite(selected).all()):
            raise ConstraintEvaluationError(
                f"Predicción no finita para la restricción '{constraint.metadata.name}'."
            )
        raw = constraint.evaluate(selected)
        if raw.dim() == 2 and raw.shape[1] == 1:
            raw = raw[:, 0]
        if raw.dim() != 1 or raw.shape[0] != valid_count:
            raise ConstraintEvaluationError(
                f"El operador '{constraint.metadata.name}' debe devolver forma [N] o [N, 1]."
            )
        if not torch.is_floating_point(raw) or not bool(torch.isfinite(raw).all()):
            raise ConstraintEvaluationError(
                f"El operador '{constraint.metadata.name}' devolvió valores no finitos "
                "o no flotantes."
            )
        if constraint.metadata.kind.value == "inequality":
            magnitudes = torch.relu(raw)
        else:
            magnitudes = torch.relu(raw.abs() - constraint.metadata.tolerance)
        violated = magnitudes > 0
        result = ConstraintResult(constraint.metadata, raw, magnitudes, violated)
        results.append(result)
        summaries.append(_summarize_result(constraint.metadata, magnitudes, violated))
        value_list = raw.detach().tolist()
        magnitude_list = magnitudes.detach().tolist()
        violated_list = violated.detach().tolist()
        records.extend(
            ViolationRecord(
                sample_id=sample_id,
                constraint=constraint.metadata.name,
                kind=constraint.metadata.kind.value,
                value=float(value),
                magnitude=float(magnitude),
                violated=bool(is_violated),
                unit=constraint.metadata.unit,
            )
            for sample_id, value, magnitude, is_violated in zip(
                included_ids, value_list, magnitude_list, violated_list, strict=True
            )
        )

    joint_violated = torch.stack([result.violated for result in results]).any(dim=0)
    joint_feasibility = 100.0 * float((~joint_violated).float().mean().item())
    summary = ViolationSummary(
        sample_count=valid_count,
        excluded_sample_count=excluded_count,
        constraints=tuple(summaries),
        joint_feasibility_rate_percent=joint_feasibility,
    )
    return ConstraintEvaluation(tuple(results), tuple(records), summary)


__all__ = [
    "ConstraintEvaluation",
    "ConstraintViolationSummary",
    "ViolationRecord",
    "ViolationSummary",
    "compositional_constraint_inputs",
    "evaluate_constraints",
]
