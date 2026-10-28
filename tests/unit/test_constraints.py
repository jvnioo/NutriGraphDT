"""Tests for differentiable constraint evaluation and violation contracts."""

from __future__ import annotations

import json
import math
from typing import Final

import pytest

torch = pytest.importorskip("torch")

from nutrigraphdt.constraints import (  # noqa: E402
    CONSTRAINTS_CONTRACT_VERSION,
    STRUCTURAL_CLOSURE_TOLERANCE,
    ConstraintEvaluationError,
    ConstraintInputs,
    ConstraintKind,
    ConstraintMetadata,
    ConstraintSpace,
    ConstraintStatus,
    FunctionalConstraint,
    compositional_constraint_inputs,
    constraint_penalty,
    evaluate_constraints,
    structural_constraints,
)

_SAMPLES: Final[tuple[str, ...]] = ("sample-1", "sample-2")


def _equality_constraint(epsilon: float = 0.0) -> FunctionalConstraint:
    return FunctionalConstraint(
        ConstraintMetadata(
            name="test.equality",
            kind=ConstraintKind.EQUALITY,
            space=ConstraintSpace.FRACTIONS,
            unit="1",
            tolerance=epsilon,
            status=ConstraintStatus.ACTIVE,
        ),
        lambda values: values[:, 0],
    )


def test_contract_metadata_and_violation_summary_are_json_serializable() -> None:
    metadata = structural_constraints()[-1].metadata
    serialized_metadata = json.dumps(metadata.to_dict())
    assert CONSTRAINTS_CONTRACT_VERSION in serialized_metadata
    assert json.loads(serialized_metadata)["status"] == "active"

    evaluation = evaluate_constraints(
        ConstraintInputs(fractions=torch.tensor([[0.5, 0.5]], dtype=torch.float64)),
        ["sample-1"],
        constraints=(structural_constraints()[-1],),
    )
    serialized_summary = json.dumps(evaluation.summary.to_dict())
    assert json.loads(serialized_summary)["contract_version"] == CONSTRAINTS_CONTRACT_VERSION


def test_structural_constraints_report_real_unit_values_and_sample_ids() -> None:
    fractions = torch.tensor([[0.5, 0.5, 0.0], [0.4, 0.4, 0.3]], dtype=torch.float64)
    concentrations = torch.tensor([[1.0, 2.0, 3.0], [-1.0, 2.0, 3.0]], dtype=torch.float64)
    evaluation = evaluate_constraints(
        ConstraintInputs(fractions=fractions, concentrations=concentrations),
        _SAMPLES,
    )

    assert len(evaluation.results) == 7
    assert len(evaluation.records) == 14
    negative_concentration = next(
        row
        for row in evaluation.records
        if row.sample_id == "sample-2"
        and row.constraint == "structural.non_negative.concentrations.acetate"
    )
    assert negative_concentration.value == pytest.approx(1.0)
    assert negative_concentration.magnitude == pytest.approx(1.0)
    assert negative_concentration.violated
    assert negative_concentration.unit == "mmol/kg"
    assert evaluation.summary.excluded_sample_count == 0
    assert evaluation.summary.joint_feasibility_rate_percent == pytest.approx(50.0)


def test_equality_boundary_is_not_violated_and_values_beyond_it_are() -> None:
    epsilon = 0.1
    evaluation = evaluate_constraints(
        ConstraintInputs(
            fractions=torch.tensor([[epsilon], [-epsilon], [epsilon + 1e-6]], dtype=torch.float64)
        ),
        ["positive-boundary", "negative-boundary", "outside"],
        constraints=(_equality_constraint(epsilon),),
    )

    assert [row.violated for row in evaluation.records] == [False, False, True]
    assert [row.magnitude for row in evaluation.records] == pytest.approx([0.0, 0.0, 1e-6])
    assert evaluation.summary.constraints[0].violation_count == 1


def test_valid_mask_excludes_records_and_metrics_and_reports_excluded_count() -> None:
    constraint = _equality_constraint()
    evaluation = evaluate_constraints(
        ConstraintInputs(fractions=torch.tensor([[0.25], [math.nan], [0.75]])),
        ["included-a", "excluded", "included-b"],
        constraints=(constraint,),
        valid_mask=torch.tensor([True, False, True]),
    )

    assert [row.sample_id for row in evaluation.records] == ["included-a", "included-b"]
    assert evaluation.summary.sample_count == 2
    assert evaluation.summary.excluded_sample_count == 1
    assert evaluation.summary.constraints[0].violation_rate_percent == pytest.approx(100.0)


def test_non_finite_prediction_for_valid_sample_raises_module_error() -> None:
    with pytest.raises(ConstraintEvaluationError, match="Predicción no finita"):
        evaluate_constraints(
            ConstraintInputs(fractions=torch.tensor([[math.nan]], dtype=torch.float64)),
            ["sample-1"],
            constraints=(_equality_constraint(),),
        )


def test_summary_uses_linear_p95_and_conditional_mean_is_undefined_without_violations() -> None:
    equality = _equality_constraint()
    all_feasible = evaluate_constraints(
        ConstraintInputs(fractions=torch.zeros((3, 1), dtype=torch.float64)),
        ["a", "b", "c"],
        constraints=(equality,),
    ).summary.constraints[0]
    assert all_feasible.conditional_mean_magnitude is None

    values = torch.tensor([[0.0], [0.0], [0.0], [0.0], [10.0]], dtype=torch.float64)
    summary = evaluate_constraints(
        ConstraintInputs(fractions=values),
        ["a", "b", "c", "d", "e"],
        constraints=(equality,),
    ).summary.constraints[0]
    assert summary.percentile_95 == pytest.approx(8.0)
    assert summary.worst_case_magnitude == pytest.approx(10.0)


def test_constraint_penalty_requires_exact_finite_nonnegative_weights_and_keeps_gradients() -> None:
    fraction = torch.tensor([[-0.2], [0.0]], dtype=torch.float64, requires_grad=True)
    result = evaluate_constraints(
        ConstraintInputs(fractions=fraction),
        _SAMPLES,
        constraints=(
            FunctionalConstraint(
                ConstraintMetadata(
                    name="test.non_negative",
                    kind=ConstraintKind.INEQUALITY,
                    space=ConstraintSpace.FRACTIONS,
                    unit="1",
                    tolerance=0.0,
                ),
                lambda values: -values[:, 0],
            ),
        ),
    )

    penalty = constraint_penalty(result.results, {"test.non_negative": 2.0})
    penalty.backward()

    assert penalty.item() == pytest.approx(0.04)
    assert fraction.grad is not None
    assert fraction.grad[0, 0].item() == pytest.approx(-0.4)
    assert fraction.grad[1, 0].item() == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("weights", "message"),
    [
        ({}, "faltan pesos"),
        ({"test.equality": 1.0, "unknown": 1.0}, "desconocidas"),
        ({"test.equality": -1.0}, "no negativo"),
        ({"test.equality": math.nan}, "finito"),
        ({"test.equality": math.inf}, "finito"),
    ],
)
def test_constraint_penalty_rejects_missing_unknown_or_invalid_weights(
    weights: dict[str, float], message: str
) -> None:
    evaluation = evaluate_constraints(
        ConstraintInputs(fractions=torch.zeros((1, 1))),
        ["sample-1"],
        constraints=(_equality_constraint(),),
    )
    with pytest.raises(ConstraintEvaluationError, match=message):
        constraint_penalty(evaluation.results, weights)


def test_compositional_adapter_uses_descaled_model_output_for_real_units() -> None:
    pytest.importorskip("torch_geometric")
    output = torch.tensor([[math.log(0.4), math.log(0.6), math.log(100.0)]])

    inputs = compositional_constraint_inputs(output)

    assert inputs.fractions is not None
    assert inputs.concentrations is not None
    assert inputs.fractions[0].tolist() == pytest.approx([0.5, 0.2, 0.3])
    assert inputs.concentrations[0].tolist() == pytest.approx([50.0, 20.0, 30.0])


def test_structural_simplex_tolerance_is_explicit_and_versioned() -> None:
    closure = structural_constraints()[-1].metadata
    assert closure.tolerance == STRUCTURAL_CLOSURE_TOLERANCE
    assert closure.to_dict()["version"] == "1.0.0"
