"""Comparación pareada en CV repetida (protocolo A55-P1 §4.2; #185).

El caso de referencia son las diferencias que Investigación recalculó por su cuenta en la
revisión del PR #217 a partir de los reportes versionados de #140 y #142
(`reports/{gnn,baselines}/d1_composition/fold_metrics.csv`; t corregido de Nadeau y Bengio con
n_test/n_train ≈ 0,25 y 49 g. l.; Wilcoxon sobre las 10 medias por semilla).
"""

from __future__ import annotations

import csv
import math
import statistics
from pathlib import Path

import pytest

pytest.importorskip("scipy")

from nutrigraphdt.models.paired_comparison import (  # noqa: E402
    classify,
    delta_category,
    paired_comparison,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GNN = REPO_ROOT / "reports" / "gnn" / "d1_composition"
BASELINES = REPO_ROOT / "reports" / "baselines" / "d1_composition"


def _fold_values(path: Path, model: str, metric: str) -> dict[tuple[int, int], float]:
    with path.open(encoding="utf-8") as handle:
        return {
            (int(row["seed"]), int(row["fold"])): float(row["average"])
            for row in csv.DictReader(handle)
            if row["model"] == model
            and row["group"] == "all"
            and row["metric"] == metric
            and row.get("edges_arm", "with_inferred") == "with_inferred"
        }


def _ratio() -> float:
    with (GNN / "folds.csv").open(encoding="utf-8") as handle:
        return statistics.fmean(
            int(row["n_test"]) / (int(row["n_train"]) + int(row["n_inner_val"]))
            for row in csv.DictReader(handle)
            if row["status"] == "ok"
        )


@pytest.mark.parametrize(
    ("baseline", "metric", "mean", "low", "high", "p_t", "p_w"),
    [
        ("random_forest", "fraction_mae_pp", 0.09, -0.32, 0.50, 0.65, 0.049),
        ("day_only", "fraction_mae_pp", -0.14, -0.54, 0.27, 0.50, 0.010),
        ("dummy_mean", "fraction_mae_pp", -0.74, -1.18, -0.30, None, None),
        ("random_forest", "fraction_r2", -0.08, -0.27, 0.11, None, None),
        ("day_only", "fraction_r2", 0.03, -0.13, 0.19, None, None),
        ("dummy_mean", "fraction_r2", 0.31, 0.09, 0.52, None, None),
    ],
)
def test_reproduces_the_figures_checked_by_investigation(
    baseline: str,
    metric: str,
    mean: float,
    low: float,
    high: float,
    p_t: float | None,
    p_w: float | None,
) -> None:
    gnn = _fold_values(GNN / "fold_metrics.csv", "homo_sage", metric)
    base = _fold_values(BASELINES / "fold_metrics.csv", baseline, metric)
    result = paired_comparison({key: gnn[key] - base[key] for key in gnn}, _ratio())

    assert (result.n_folds, result.n_seeds, result.degrees_of_freedom) == (50, 10, 49)
    assert round(result.mean_delta, 2) == mean
    assert (round(result.ci_low, 2), round(result.ci_high, 2)) == (low, high)
    if p_t is not None:
        assert round(result.p_value, 2) == p_t
    if p_w is not None:
        assert round(result.wilcoxon_p_value, 3) == p_w


def test_identical_arms_give_zero_difference_without_a_statistic() -> None:
    result = paired_comparison({(s, f): 0.0 for s in range(10) for f in range(5)}, 0.25)
    assert result.mean_delta == 0.0
    assert (result.ci_low, result.ci_high) == (0.0, 0.0)
    assert math.isnan(result.t_statistic) and math.isnan(result.p_value)


def test_hand_computed_correction() -> None:
    # Δ = (1, 3) en dos folds de una semilla: media 2, s = √2, n = 2, cociente 0,5 →
    # σ² = (1/2 + 0,5)·2 = 2, ES = √2, t = 2/√2 = √2 con 1 g. l.
    result = paired_comparison({(0, 0): 1.0, (0, 1): 3.0}, 0.5)
    assert result.corrected_se == pytest.approx(math.sqrt(2))
    assert result.t_statistic == pytest.approx(math.sqrt(2))
    assert result.cohen_d == pytest.approx(2 / math.sqrt(2))


@pytest.mark.parametrize(
    ("deltas", "ratio", "fragment"),
    [
        ({(0, 0): 1.0}, 0.25, "dos folds"),
        ({(0, 0): 1.0, (0, 1): math.nan}, 0.25, "finitas"),
        ({(0, 0): 1.0, (0, 1): 2.0}, 0.0, "positivo"),
    ],
)
def test_invalid_inputs_are_rejected(
    deltas: dict[tuple[int, int], float], ratio: float, fragment: str
) -> None:
    with pytest.raises(ValueError, match=fragment):
        paired_comparison(deltas, ratio)


@pytest.mark.parametrize(
    ("low", "high", "category"),
    [
        (-1.2, -0.6, 1),  # U < −δ
        (-0.6, -0.1, 2),  # U < 0
        (-0.3, 0.3, 3),  # L > −δ y U < δ
        (-0.8, 0.4, 4),  # U < δ con L ≤ −δ
        (-0.2, 0.7, 5),  # L < δ ≤ U
        (0.5, 1.0, 6),  # L ≥ δ
        (0.0, 0.0, 3),  # brazos idénticos
    ],
)
def test_delta_category_follows_table_4(low: float, high: float, category: int) -> None:
    assert delta_category(low, high, 0.5) == category


@pytest.mark.parametrize(
    ("feasible", "category", "low", "stable", "expected"),
    [
        (False, 1, -1.0, True, "Inoperante"),
        (True, 5, -0.2, True, "Costo inadmisible"),
        (True, 2, -0.6, False, "Inestable"),
        (True, 2, -0.6, True, "Superioridad dual"),
        (True, 3, 0.1, True, "Degradación aceptable"),
        (True, 3, -0.1, True, "Factibilidad sin costo"),
        (True, 4, -0.8, True, "Factibilidad sin costo"),
    ],
)
def test_classification_follows_table_5(
    feasible: bool, category: int, low: float, stable: bool, expected: str
) -> None:
    assert classify(feasible=feasible, category=category, low=low, stable=stable)[0] == expected
