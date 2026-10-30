"""Pruebas de la cota de propionato aprobada en D-06 v1."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from nutrigraphdt.constraints import (  # noqa: E402
    CONSTRAINTS_CONTRACT_VERSION,
    D06_PROPIONATE_BOUND_NAME,
    D06_PROPIONATE_BOUND_VERSION,
    D06_SOURCE_DATE,
    D06_SOURCE_PATH,
    D06_SOURCE_SECTION,
    D06_SOURCE_VERSION,
    ConstraintInputs,
    ConstraintKind,
    ConstraintSpace,
    ConstraintStatus,
    constraint_catalog,
    constraint_penalty,
    d06_constraints,
    evaluate_constraints,
    structural_constraints,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_d06_metadata_and_source_provenance_match_approved_document() -> None:
    constraint = d06_constraints()[0]
    metadata = constraint.metadata
    source = (REPO_ROOT / D06_SOURCE_PATH).read_text(encoding="utf-8")

    assert D06_SOURCE_VERSION == "1.0"
    assert D06_SOURCE_DATE == "29-10-2026"
    assert D06_SOURCE_SECTION == "3.5"
    assert D06_PROPIONATE_BOUND_NAME in source
    assert metadata.name == D06_PROPIONATE_BOUND_NAME
    assert metadata.kind is ConstraintKind.INEQUALITY
    assert metadata.space is ConstraintSpace.FRACTIONS
    assert metadata.unit == "1"
    assert metadata.tolerance == 0.0
    assert metadata.status is ConstraintStatus.ACTIVE
    assert metadata.version == D06_PROPIONATE_BOUND_VERSION == "1.0.0"
    assert metadata.to_dict()["contract_version"] == CONSTRAINTS_CONTRACT_VERSION == "1.0.0"
    assert constraint_catalog()[D06_PROPIONATE_BOUND_NAME].metadata == metadata


def test_table_6_compositions_satisfy_bound_with_reported_operator_values() -> None:
    fractions = torch.tensor(
        [
            [0.686, 0.078, 0.235],
            [0.908, 0.025, 0.067],
            [0.852, 0.047, 0.101],
            [0.748, 0.116, 0.136],
        ],
        dtype=torch.float64,
    )

    raw = d06_constraints()[0].evaluate(fractions)

    # The published operator values are rounded to 2 decimals while fractions are rounded
    # to 3; abs=0.0051 covers that source-table rounding only (no relative tolerance).
    assert raw.tolist() == pytest.approx([-1.76, -1.93, -1.86, -1.65], rel=0.0, abs=0.0051)
    assert bool((raw <= 0).all())


def test_d06_operator_has_hand_computed_feasible_violating_and_boundary_cases() -> None:
    fractions = torch.tensor(
        [
            [0.5, 0.25, 0.25],
            [0.125, 0.75, 0.125],
            [0.125, 0.5, 0.125],
        ],
        dtype=torch.float64,
    )

    raw = d06_constraints()[0].evaluate(fractions)
    evaluation = evaluate_constraints(
        ConstraintInputs(fractions=fractions),
        ["feasible", "violating", "boundary"],
        constraints=d06_constraints(),
    )

    # h = p - 2(a+b): -1.25, 0.25, and 0 respectively.
    assert raw.tolist() == [-1.25, 0.25, 0.0]
    assert evaluation.results[0].magnitudes.tolist() == [0.0, 0.25, 0.0]
    assert evaluation.results[0].violated.tolist() == [False, True, False]


@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
def test_exact_boundary_is_not_violated(dtype: torch.dtype) -> None:
    fractions = torch.tensor([[0.33333333333333337, 0.6666666666666667, 0.0]], dtype=dtype)

    raw = d06_constraints()[0].evaluate(fractions)

    assert raw.item() == 0.0
    evaluation = evaluate_constraints(
        ConstraintInputs(fractions=fractions),
        ["boundary"],
        constraints=d06_constraints(),
    )
    assert evaluation.records[0].magnitude == 0.0
    assert not evaluation.records[0].violated


def test_violation_mask_and_penalty_preserve_exact_gradient() -> None:
    fractions = torch.tensor(
        [[0.125, 0.75, 0.125], [0.5, 0.25, 0.25], [float("nan"), 0.0, 0.0]],
        dtype=torch.float64,
        requires_grad=True,
    )
    evaluation = evaluate_constraints(
        ConstraintInputs(fractions=fractions),
        ["violating", "feasible", "excluded"],
        constraints=d06_constraints(),
        valid_mask=torch.tensor([True, True, False]),
    )

    result = evaluation.results[0]
    penalty = constraint_penalty(evaluation.results, {D06_PROPIONATE_BOUND_NAME: 1.0})
    gradient = torch.autograd.grad(penalty, fractions)[0]

    assert result.values.tolist() == [0.25, -1.25]
    assert result.magnitudes.tolist() == [0.25, 0.0]
    assert [record.sample_id for record in evaluation.records] == ["violating", "feasible"]
    assert evaluation.summary.sample_count == 2
    assert evaluation.summary.excluded_sample_count == 1
    assert gradient[0].tolist() == [-0.5, 0.25, -0.5]
    assert torch.equal(gradient[1], torch.zeros(3, dtype=torch.float64))
    assert torch.equal(gradient[2], torch.zeros(3, dtype=torch.float64))


def test_compositional_reconstruction_can_violate_d06_and_keeps_gradient() -> None:
    pytest.importorskip("torch_geometric")
    from nutrigraphdt.constraints import compositional_constraint_inputs

    output = torch.tensor([[math.log(6.0), 0.0, math.log(8.0)]], dtype=torch.float64)
    output.requires_grad_()
    inputs = compositional_constraint_inputs(output)
    assert inputs.fractions is not None
    assert inputs.concentrations is not None

    assert inputs.fractions[0].tolist() == pytest.approx([0.125, 0.75, 0.125], rel=1e-6, abs=1e-12)
    assert inputs.concentrations[0].tolist() == pytest.approx([1.0, 6.0, 1.0], rel=1e-6, abs=1e-12)
    evaluation = evaluate_constraints(
        inputs,
        ["reconstructed"],
        constraints=d06_constraints(),
    )
    assert evaluation.results[0].values.tolist() == pytest.approx([0.25], rel=1e-6, abs=1e-12)
    penalty = constraint_penalty(evaluation.results, {D06_PROPIONATE_BOUND_NAME: 1.0})
    gradient = torch.autograd.grad(penalty, output)[0]
    assert bool(torch.isfinite(gradient).all())
    assert gradient[0, 0].item() != 0.0


def test_evaluate_constraints_default_is_exactly_structural() -> None:
    evaluation = evaluate_constraints(
        ConstraintInputs(
            fractions=torch.tensor([[0.5, 0.25, 0.25]], dtype=torch.float64),
            concentrations=torch.tensor([[2.0, 1.0, 1.0]], dtype=torch.float64),
        ),
        ["default"],
    )

    assert [result.metadata.name for result in evaluation.results] == [
        constraint.metadata.name for constraint in structural_constraints()
    ]
    assert len(evaluation.results) == 7
    assert D06_PROPIONATE_BOUND_NAME not in {result.metadata.name for result in evaluation.results}
