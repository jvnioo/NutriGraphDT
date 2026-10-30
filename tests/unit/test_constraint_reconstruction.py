"""Casos mínimos para la reconstrucción tensorial sin modelo ni pipeline de entrenamiento."""

from __future__ import annotations

import math

import pytest

torch = pytest.importorskip("torch")


@pytest.mark.parametrize(
    ("dtype", "rtol", "atol"),
    [
        ("float32", 1e-6, 1e-8),
        ("float64", 1e-12, 1e-12),
    ],
)
def test_compositional_reconstruction_matches_hand_computed_concentrations(
    dtype: str, rtol: float, atol: float
) -> None:
    pytest.importorskip("torch_geometric")
    from nutrigraphdt.models.gnn.target import concentrations_from_graph_output

    tensor_dtype = getattr(torch, dtype)
    output = torch.tensor(
        [[math.log(0.4), math.log(0.6), math.log(100.0)]],
        dtype=tensor_dtype,
        requires_grad=True,
    )

    concentrations = concentrations_from_graph_output(output)
    concentrations.sum().backward()

    # Softmax weights 1:0.4:0.6 give fractions (0.5, 0.2, 0.3); T=100,
    # hence concentrations (50, 20, 30). Float32 needs relative precision 1e-6
    # plus a small near-zero allowance; float64 uses 1e-12 for both tolerances.
    expected = torch.tensor([[50.0, 20.0, 30.0]], dtype=tensor_dtype)
    assert torch.allclose(concentrations, expected, rtol=rtol, atol=atol)
    assert bool((concentrations >= 0).all())
    assert output.grad is not None
    assert bool(torch.isfinite(output.grad).all())
