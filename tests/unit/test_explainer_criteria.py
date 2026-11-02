"""Criterios de C-04 y C-07 de la respuesta de Investigación a A55 (#240)."""

from __future__ import annotations

import random

import pytest

from nutrigraphdt.explainability.criteria import (
    OUTPUT_METRICS,
    explainable_outputs,
    nogueira_ci,
    nogueira_phi,
)
from nutrigraphdt.models.composition import MODEL_OUTPUT_NAMES

FOLDS = [(seed, fold) for seed in range(10) for fold in range(5)]


def _sel(*items: str) -> frozenset[tuple[str, ...]]:
    return frozenset((item,) for item in items)


def test_identical_selections_are_perfectly_stable() -> None:
    selections = [_sel("a", "b", "c")] * 5
    assert nogueira_phi(selections, 10) == pytest.approx(1.0)
    low, high = nogueira_ci(selections, 10)
    assert low == pytest.approx(1.0)
    assert high == pytest.approx(1.0)


def test_random_selections_are_near_zero() -> None:
    rng = random.Random(0)
    items = [str(i) for i in range(50)]
    phis = [
        nogueira_phi([frozenset((x,) for x in rng.sample(items, 5)) for _ in range(5)], 50)
        for _ in range(400)
    ]
    assert abs(sum(phis) / len(phis)) < 0.02


def test_fixed_k_matches_kuncheva() -> None:
    # Con k fijo, Φ̂ coincide con el índice de Kuncheva medio entre pares (Nogueira et al., 2018).
    selections = [_sel("a", "b", "c"), _sel("a", "b", "d"), _sel("a", "e", "f")]
    d, k = 10, 3

    def kuncheva(x: frozenset[tuple[str, ...]], y: frozenset[tuple[str, ...]]) -> float:
        return (len(x & y) * d - k * k) / (k * (d - k))

    pairs = [(0, 1), (0, 2), (1, 2)]
    expected = sum(kuncheva(selections[i], selections[j]) for i, j in pairs) / len(pairs)
    assert nogueira_phi(selections, d) == pytest.approx(expected)


def test_ci_contains_the_estimate() -> None:
    selections = [_sel("a", "b", "c"), _sel("a", "b", "d"), _sel("a", "e", "f"), _sel("a", "b")]
    phi = nogueira_phi(selections, 12)
    low, high = nogueira_ci(selections, 12)
    assert low < phi < high


def test_degenerate_selections_are_rejected() -> None:
    with pytest.raises(ValueError):
        nogueira_phi([_sel("a")], 3)
    with pytest.raises(ValueError):
        nogueira_phi([_sel(), _sel()], 3)


def _metric(base: float, shift: float) -> dict[tuple[int, int], float]:
    return {key: base + shift + 0.01 * ((key[0] + key[1]) % 3) for key in FOLDS}


def test_explainable_outputs_follow_each_metric() -> None:
    dummy = {"fraction_mae_pp": _metric(10.0, 0.0), "log_total_mae": _metric(0.5, 0.0)}
    model = {"fraction_mae_pp": _metric(8.0, 0.0), "log_total_mae": _metric(0.5, 0.0)}
    assert explainable_outputs(model, dummy, 0.25) == MODEL_OUTPUT_NAMES[:2]
    assert set(OUTPUT_METRICS) == set(MODEL_OUTPUT_NAMES)


def test_explainable_outputs_need_matching_folds() -> None:
    dummy = {"fraction_mae_pp": _metric(10.0, 0.0), "log_total_mae": _metric(0.5, 0.0)}
    model = {"fraction_mae_pp": dict(list(_metric(8.0, 0.0).items())[:10]), "log_total_mae": {}}
    with pytest.raises(ValueError, match="no coinciden"):
        explainable_outputs(model, dummy, 0.25)
