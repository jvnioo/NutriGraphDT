"""Tests del objetivo composicional de los AGCC y sus métricas (contrato v2, sección 1; #146)."""

from __future__ import annotations

import math
import random
import struct

import pytest

from nutrigraphdt.models.composition import (
    ALL_DAYS,
    COMPOSITION_METRICS,
    ROUND_TRIP_RTOL,
    CompositionalReconstructionError,
    compositional_target,
    compositional_targets,
    concentrations_from_output,
    evaluate_composition,
    fractions_from_log_ratios,
)
from nutrigraphdt.models.metrics import EvaluationReport

# ---------------------------------------------------------------------------
# Transformación e inversa
# ---------------------------------------------------------------------------


def test_forward_transform_matches_the_contract_definitions() -> None:
    target = compositional_target(50.0, 20.0, 30.0)

    assert target.valid
    assert target.total == pytest.approx(100.0, rel=1e-6, abs=1e-12)
    assert target.fractions == pytest.approx((0.5, 0.2, 0.3), rel=1e-6, abs=1e-12)
    assert target.log_ratios == pytest.approx(
        (math.log(20 / 50), math.log(30 / 50)), rel=1e-6, abs=1e-12
    )
    assert target.log_total == pytest.approx(math.log(100.0), rel=1e-6, abs=1e-12)
    assert target.model_output == pytest.approx(
        (*target.log_ratios, target.log_total), rel=1e-6, abs=1e-12
    )


def test_round_trip_concentrations_target_concentrations() -> None:
    rng = random.Random(146)
    for _ in range(500):
        values = tuple(10 ** rng.uniform(-3, 3) for _ in range(3))
        target = compositional_target(*values)
        rebuilt = concentrations_from_output(*target.model_output)
        for original, back in zip(values, rebuilt, strict=True):
            assert math.isclose(original, back, rel_tol=ROUND_TRIP_RTOL)
        assert sum(target.fractions) == pytest.approx(1.0, rel=1e-6, abs=1e-12)


@pytest.mark.parametrize(
    "output",
    [
        (math.log(0.4), math.log(0.6), math.log(100.0)),
        (0.0, 0.0, 0.0),
        (10.0, -8.0, 4.0),
    ],
)
def test_scalar_reconstruction_preserves_legacy_bits(output: tuple[float, float, float]) -> None:
    z1, z2, log_total = output
    fractions = fractions_from_log_ratios(z1, z2)
    total = math.exp(log_total)
    legacy = (total * fractions[0], total * fractions[1], total * fractions[2])

    reconstructed = concentrations_from_output(*output)

    assert tuple(struct.pack("!d", value) for value in reconstructed) == tuple(
        struct.pack("!d", value) for value in legacy
    )


@pytest.mark.parametrize(
    "output",
    [
        (math.nan, 0.0, 0.0),
        (0.0, math.inf, 0.0),
        (0.0, 0.0, math.nan),
        (0.0, 0.0, math.inf),
    ],
)
def test_scalar_reconstruction_rejects_non_finite_inputs(
    output: tuple[float, float, float],
) -> None:
    with pytest.raises(CompositionalReconstructionError, match="no finita"):
        concentrations_from_output(*output)


def test_scalar_reconstruction_converts_exp_overflow_to_domain_error() -> None:
    with pytest.raises(CompositionalReconstructionError, match="desborda"):
        concentrations_from_output(0.0, 0.0, 1000.0)


@pytest.mark.parametrize(
    "values",
    [
        (0.0, 20.0, 30.0),
        (50.0, 0.0, 30.0),
        (50.0, 20.0, 0.0),
        (None, 20.0, 30.0),
        (50.0, math.nan, 30.0),
        (50.0, 20.0, math.inf),
        (-1.0, 20.0, 30.0),
    ],
)
def test_zero_or_missing_value_invalidates_the_target_without_pseudocount(
    values: tuple[float | None, float | None, float | None],
) -> None:
    target = compositional_target(*values)

    assert target.valid is False
    assert math.isnan(target.total)
    assert all(math.isnan(v) for v in target.model_output)


def test_inverse_is_a_stable_softmax_with_acetate_as_reference() -> None:
    assert fractions_from_log_ratios(0.0, 0.0) == pytest.approx(
        (1 / 3, 1 / 3, 1 / 3), rel=1e-6, abs=1e-12
    )
    extreme = fractions_from_log_ratios(800.0, -800.0)
    assert extreme == pytest.approx((0.0, 1.0, 0.0), rel=1e-6, abs=1e-12)
    assert sum(extreme) == pytest.approx(1.0, rel=1e-6, abs=1e-12)
    with pytest.raises(ValueError, match="no finitas"):
        fractions_from_log_ratios(math.nan, 0.0)


def test_compositional_targets_checks_row_length() -> None:
    assert [t.valid for t in compositional_targets([(1, 2, 3), (0, 2, 3)])] == [True, False]
    with pytest.raises(ValueError, match="3"):
        compositional_targets([(1.0, 2.0)])


# ---------------------------------------------------------------------------
# Métricas de D-03 sobre un caso calculado a mano
# ---------------------------------------------------------------------------

# A: (50, 20, 30), T = 100, p = (0.5, 0.2, 0.3); predicción exacta.
# B: (60, 30, 10), T = 100, p = (0.6, 0.3, 0.1); predicción p = (0.5, 0.3, 0.2), T = 80,
#    es decir, concentraciones (40, 24, 16).
# C y D no tienen objetivo composicional (un cero y un valor ausente) y no se evalúan.
TRUE = [(50.0, 20.0, 30.0), (60.0, 30.0, 10.0), (0.0, 10.0, 10.0), (None, 10.0, 10.0)]
PRED = [
    (math.log(0.4), math.log(0.6), math.log(100.0)),
    (math.log(0.6), math.log(0.4), math.log(80.0)),
    (0.0, 0.0, 0.0),
    (0.0, 0.0, 0.0),
]


def _row(report: EvaluationReport, metric: str, group: str = ALL_DAYS) -> dict[str, float]:
    row = next(r for r in report.rows if r.metric == metric and r.group == group)
    return {**row.targets, "average": row.average}


def test_metrics_reproduce_a_hand_computed_case() -> None:
    report = evaluate_composition(TRUE, PRED, "toy", split="val")

    assert [row.metric for row in report.rows] == list(COMPOSITION_METRICS)
    assert all(row.split == "val" and row.group == ALL_DAYS for row in report.rows)
    assert _row(report, "fraction_mae_pp") == pytest.approx(
        {"acetate": 5.0, "propionate": 0.0, "butyrate": 5.0, "average": 10 / 3},
        rel=1e-6,
        abs=1e-12,
    )
    assert _row(report, "fraction_r2") == pytest.approx(
        {"acetate": -1.0, "propionate": 1.0, "butyrate": 0.5, "average": 0.5 / 3},
        rel=1e-6,
        abs=1e-12,
    )
    assert _row(report, "log_total_mae") == pytest.approx(
        {"log_total": math.log(1.25) / 2, "average": math.log(1.25) / 2},
        rel=1e-6,
        abs=1e-12,
    )
    # ln T verdadero constante (100 en ambos): R² = 0 porque el error no es nulo.
    assert _row(report, "log_total_r2") == pytest.approx(
        {"log_total": 0.0, "average": 0.0}, rel=1e-6, abs=1e-12
    )
    assert _row(report, "reconstructed_mae") == pytest.approx(
        {"acetate": 10.0, "propionate": 3.0, "butyrate": 3.0, "average": 16 / 3},
        rel=1e-6,
        abs=1e-12,
    )
    assert _row(report, "reconstructed_r2") == pytest.approx(
        {
            "acetate": -7.0,
            "propionate": 0.28,
            "butyrate": 0.82,
            "average": (-7 + 0.28 + 0.82) / 3,
        },
        rel=1e-6,
        abs=1e-12,
    )


def test_metrics_by_sampling_day() -> None:
    report = evaluate_composition(TRUE, PRED, "toy", sampling_days=[21, 7, 7, 21])

    groups = [row.group for row in report.rows]
    assert groups == [ALL_DAYS] * 6 + ["7"] * 6 + ["21"] * 6
    # Día 7: solo B es válido; día 21: solo A, con predicción exacta.
    assert _row(report, "fraction_mae_pp", "7")["average"] == pytest.approx(
        20 / 3, rel=1e-6, abs=1e-12
    )
    assert _row(report, "reconstructed_mae", "21")["average"] == pytest.approx(
        0.0, rel=1e-6, abs=1e-12
    )


def test_report_exports_group_column_and_mixed_targets() -> None:
    report = evaluate_composition(TRUE, PRED, "toy", sampling_days=[21, 7, 7, 21])

    header = report.to_csv().splitlines()[0].split(",")
    assert header == [
        "model",
        "group",
        "metric",
        "acetate",
        "propionate",
        "butyrate",
        "log_total",
        "average",
    ]
    assert "| model | group | metric |" in report.to_markdown()


def test_metrics_validate_inputs() -> None:
    with pytest.raises(ValueError, match="filas"):
        evaluate_composition(TRUE, PRED[:2], "toy")
    with pytest.raises(ValueError, match="sampling_days"):
        evaluate_composition(TRUE, PRED, "toy", sampling_days=[1])
    with pytest.raises(ValueError, match="no finita"):
        evaluate_composition(TRUE[:1], [(math.nan, 0.0, 0.0)], "toy")
    with pytest.raises(ValueError, match="Ningún animal"):
        evaluate_composition(TRUE[2:], PRED[2:], "toy")


# ---------------------------------------------------------------------------
# Versión con tensores (models.gnn.target)
# ---------------------------------------------------------------------------


def test_tensor_target_matches_the_reference_transform() -> None:
    torch = pytest.importorskip("torch")
    pytest.importorskip("torch_geometric")
    from nutrigraphdt.models.gnn.target import (
        compositional_graph_target,
        concentrations_from_graph_output,
    )

    y = torch.tensor([[50.0, 20.0, 30.0], [60.0, 30.0, 10.0], [0.0, 10.0, 10.0], [5.0, 10.0, 10.0]])
    mask = torch.ones_like(y, dtype=torch.bool)
    mask[3, 0] = False  # acetato ausente
    y_original = y.clone()
    mask_original = mask.clone()

    target, valid = compositional_graph_target(y, mask)

    assert torch.equal(y, y_original)
    assert torch.equal(mask, mask_original)
    assert valid.shape == (4, 1)
    assert valid[:, 0].tolist() == [True, True, False, False]
    assert torch.equal(target[2:], torch.zeros(2, 3))
    for row in range(2):
        expected = compositional_target(*y[row].tolist()).model_output
        assert target[row].tolist() == pytest.approx(expected, rel=1e-6, abs=1e-12)
    rebuilt = concentrations_from_graph_output(target[:2].to(torch.float64))
    assert torch.allclose(rebuilt, y[:2].to(torch.float64), rtol=1e-6)

    with pytest.raises(ValueError, match="forma"):
        compositional_graph_target(y[:, :2], mask[:, :2])
    with pytest.raises(ValueError, match="booleana"):
        compositional_graph_target(y, mask.float())


def test_tensor_reconstruction_preserves_legacy_bits_and_does_not_mutate_output() -> None:
    torch = pytest.importorskip("torch")
    pytest.importorskip("torch_geometric")
    from nutrigraphdt.models.gnn.target import concentrations_from_graph_output

    output = torch.tensor(
        [[math.log(0.4), math.log(0.6), math.log(100.0)], [10.0, -8.0, 4.0]],
        dtype=torch.float64,
    )
    original = output.clone()
    logits = torch.cat([torch.zeros_like(output[:, :1]), output[:, :2]], dim=1)
    legacy = torch.softmax(logits, dim=1) * output[:, 2:].exp()

    reconstructed = concentrations_from_graph_output(output)

    assert torch.equal(reconstructed, legacy)
    assert torch.equal(output, original)


@pytest.mark.parametrize("dtype", ["float32", "float64"])
def test_tensor_reconstruction_handles_dtype_extremes_and_rejects_overflow(dtype: str) -> None:
    torch = pytest.importorskip("torch")
    pytest.importorskip("torch_geometric")
    from nutrigraphdt.models.gnn.target import concentrations_from_graph_output

    tensor_dtype = getattr(torch, dtype)
    limits = torch.finfo(tensor_dtype)
    log_max = math.log(limits.max)
    near_max = torch.tensor([[0.0, 0.0, log_max - 2.0]], dtype=tensor_dtype)
    near_underflow = torch.tensor([[0.0, 0.0, math.log(limits.tiny) - 2.0]], dtype=tensor_dtype)

    high_result = concentrations_from_graph_output(near_max)
    low_result = concentrations_from_graph_output(near_underflow)

    assert torch.isfinite(high_result).all()
    assert torch.isfinite(low_result).all()
    assert (high_result >= 0).all()
    assert (low_result >= 0).all()
    with pytest.raises(CompositionalReconstructionError, match="no finitas"):
        concentrations_from_graph_output(
            torch.tensor([[0.0, 0.0, log_max + 2.0]], dtype=tensor_dtype)
        )
    with pytest.raises(CompositionalReconstructionError, match="no finitas"):
        concentrations_from_graph_output(
            torch.tensor(
                [[log_max + 2.0, -log_max - 2.0, log_max + 2.0]],
                dtype=tensor_dtype,
            )
        )


@pytest.mark.parametrize("dtype", ["float32", "float64"])
def test_tensor_reconstruction_rejects_non_finite_inputs_and_keeps_finite_gradients(
    dtype: str,
) -> None:
    torch = pytest.importorskip("torch")
    pytest.importorskip("torch_geometric")
    from nutrigraphdt.models.gnn.target import concentrations_from_graph_output

    tensor_dtype = getattr(torch, dtype)
    for bad_value in (math.nan, math.inf, -math.inf):
        output = torch.tensor([[bad_value, 0.0, 0.0]], dtype=tensor_dtype)
        with pytest.raises(CompositionalReconstructionError, match="NaN o infinito"):
            concentrations_from_graph_output(output)

    output = torch.tensor(
        [[100.0, -100.0, math.log(10.0)]],
        dtype=tensor_dtype,
        requires_grad=True,
    )
    concentrations_from_graph_output(output).sum().backward()

    assert output.grad is not None
    assert torch.isfinite(output.grad).all()
