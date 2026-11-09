"""Incertidumbre de las predicciones composicionales (A75-P1 y A75-P2; #283 y #284).

Cubre la forma de las salidas, el determinismo con semilla, que `model.eval()` se restaure tras
MC-dropout y que la calibración y la elección del método solo usen el val interno. Requiere el
extra `graph` (y `baselines` para el reparto interno por corral).
"""

from __future__ import annotations

import csv
import importlib.util
import math
import sys
from pathlib import Path
from typing import Any

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")

from torch import nn  # noqa: E402
from torch_geometric.data import HeteroData  # noqa: E402
from torch_geometric.loader import DataLoader  # noqa: E402

from nutrigraphdt.graph.builder import add_reverse_edges  # noqa: E402
from nutrigraphdt.graph.heterodata import build_synthetic_graphs  # noqa: E402
from nutrigraphdt.models.baselines import build_synthetic_cohort  # noqa: E402
from nutrigraphdt.models.composition import (  # noqa: E402
    MODEL_OUTPUT_NAMES,
    fractions_from_log_ratios,
)
from nutrigraphdt.models.gnn import load_model_config  # noqa: E402
from nutrigraphdt.models.gnn.base import GraphMetadata  # noqa: E402
from nutrigraphdt.models.gnn.batching import align_graph_types  # noqa: E402
from nutrigraphdt.models.gnn.factory import build_model  # noqa: E402
from nutrigraphdt.models.gnn.target import add_graph_target  # noqa: E402
from nutrigraphdt.models.training import TrainingConfig  # noqa: E402
from nutrigraphdt.models.training.compositional import (  # noqa: E402
    CompositionalTargetTransform,
    run_compositional_fold,
)
from nutrigraphdt.models.uncertainty import (  # noqa: E402
    ENSEMBLE,
    MC_DROPOUT,
    MEMBER_SEED_STRIDE,
    METHODS,
    OUTPUT_NAMES,
    PredictiveDistribution,
    UncertaintyError,
    combined_intervals,
    coverage,
    fit_scale,
    fractions_from_outputs,
    gaussian_nll,
    gaussian_quantile,
    interval_rows,
    mc_dropout,
    member_seed,
    observed_with_fractions,
    run_uncertainty_fold,
    sample_mc_dropout,
    select_method,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
N_SAMPLES = 16
SEED = 42


def _config(**overrides: object) -> TrainingConfig:
    values: dict[str, object] = {
        "lr": 1e-2,
        "weight_decay": 1e-4,
        "batch_size": 4,
        "max_epochs": 2,
        "patience": 2,
        "seed": SEED,
        "dataset_id": "synthetic_cohort",
        "split_file": "configs/splits/d1_holofood.json",
    }
    values.update(overrides)
    return TrainingConfig.model_validate(values)


@pytest.fixture(scope="module")
def graphs() -> dict[str, HeteroData]:
    built = build_synthetic_graphs(build_synthetic_cohort(N_SAMPLES, first_seed=1))
    prepared: dict[str, HeteroData] = {}
    for graph_id, graph in built.graphs.items():
        with_target = add_graph_target(add_reverse_edges(graph))
        with_target.graph_id = graph_id
        prepared[str(with_target.sample_id)] = with_target
    align_graph_types(list(prepared.values()), inplace=True)
    return prepared


@pytest.fixture(scope="module")
def fold_inputs(graphs: dict[str, HeteroData]) -> dict[str, object]:
    ids = sorted(graphs)
    pens = {s: f"pen{index // 2}" for index, s in enumerate(ids)}
    diets = {s: f"dieta{(index // 2) % 2}" for index, s in enumerate(ids)}
    test_ids = tuple(ids[:4])
    return {
        "train_ids": tuple(ids[4:]),
        "test_ids": test_ids,
        "graphs": graphs,
        "pens": pens,
        "diets": diets,
        "model_config": load_model_config(REPO_ROOT / "configs" / "models" / "hetero_sage.yaml"),
        "metadata": GraphMetadata.from_graphs(graphs.values()),
        "config": _config(),
    }


@pytest.fixture(scope="module")
def fold(fold_inputs: dict[str, object]):  # type: ignore[no-untyped-def]
    return run_uncertainty_fold(seed=0, fold=0, ensemble_size=3, mc_passes=4, **fold_inputs)


# ---------------------------------------------------------------------------
# Distribución e intervalos
# ---------------------------------------------------------------------------


def _distribution() -> PredictiveDistribution:
    samples = torch.tensor(
        [
            [[-2.0, -1.5, 4.0], [-1.0, -1.0, 4.5]],
            [[-2.2, -1.3, 4.2], [-1.4, -0.8, 4.3]],
            [[-1.8, -1.7, 3.8], [-1.2, -1.2, 4.7]],
        ]
    )
    return PredictiveDistribution.from_samples(samples, ["a", "b"])


def test_distribution_mean_std_and_interval() -> None:
    distribution = _distribution()
    assert distribution.mean.shape == distribution.std.shape == (2, 3)
    assert distribution.n_samples == 3
    assert float(distribution.std[0, 0]) == pytest.approx(0.2)  # desviación con S − 1
    lower, upper = distribution.interval(0.8)
    z = gaussian_quantile(0.8)
    assert torch.allclose(upper - lower, 2 * z * distribution.std)
    wide_lower, wide_upper = distribution.interval(0.8, scale=(2.0, 2.0, 2.0))
    assert torch.allclose(wide_upper - wide_lower, 2 * (upper - lower))
    with pytest.raises(UncertaintyError):
        distribution.interval(0.8, scale=(1.0, -1.0, 1.0))
    with pytest.raises(UncertaintyError):
        PredictiveDistribution.from_samples(torch.zeros(1, 2, 3), ["a", "b"])


def test_gaussian_quantile() -> None:
    assert gaussian_quantile(0.9) == pytest.approx(1.6448536, rel=1e-6)
    for level in (0.0, 1.0, 1.5):
        with pytest.raises(UncertaintyError):
            gaussian_quantile(level)


def test_fractions_are_the_softmax_of_the_mean_log_ratios() -> None:
    distribution = _distribution()
    point = distribution.point_fractions()
    for row in range(2):
        expected = fractions_from_log_ratios(*distribution.mean[row, :2].tolist())
        assert point[row].tolist() == pytest.approx(expected)
    assert torch.allclose(point.sum(dim=1), torch.ones(2, dtype=torch.float64))
    # No es el promedio de las fracciones de cada muestra.
    samples = torch.tensor([[[-3.0, -3.0, 0.0]], [[1.0, 1.0, 0.0]]])
    averaged = fractions_from_outputs(samples).mean(dim=0)
    from_mean = PredictiveDistribution.from_samples(samples, ["a"]).point_fractions()
    assert not torch.allclose(averaged.to(torch.float64), from_mean)


def test_fraction_interval_is_deterministic_and_contains_the_point() -> None:
    distribution = _distribution()
    first = distribution.fraction_interval(0.8, seed=3)
    second = distribution.fraction_interval(0.8, seed=3)
    assert all(torch.equal(a, b) for a, b in zip(first, second, strict=True))
    point = distribution.point_fractions()
    assert bool(((first[0] <= point) & (point <= first[1])).all())
    point6, lower6, upper6 = combined_intervals(distribution, 0.8, seed=3)
    assert point6.shape == lower6.shape == upper6.shape == (2, len(OUTPUT_NAMES))


# ---------------------------------------------------------------------------
# Calibración y elección
# ---------------------------------------------------------------------------


def test_coverage_ignores_missing_values() -> None:
    observed = torch.tensor([[0.0, math.nan], [2.0, 1.0], [5.0, 1.0]])
    lower = torch.zeros(3, 2)
    upper = torch.full((3, 2), 3.0)
    assert coverage(observed, lower, upper) == pytest.approx([2 / 3, 1.0])
    assert math.isnan(coverage(torch.full((2, 1), math.nan), lower[:2, :1], upper[:2, :1])[0])


def test_fit_scale_reaches_the_nominal_level_on_its_own_data() -> None:
    generator = torch.Generator().manual_seed(0)
    mean = torch.zeros(40, 3, dtype=torch.float64)
    std = torch.full((40, 3), 0.1, dtype=torch.float64)
    distribution = PredictiveDistribution(tuple(str(i) for i in range(40)), mean, std, 5)
    observed = torch.randn((40, 3), generator=generator, dtype=torch.float64)
    scale = fit_scale(observed, distribution, 0.8)
    assert all(factor > 1 for factor in scale)  # la dispersión subestimaba el error
    lower, upper = distribution.interval(0.8, scale)
    assert all(value >= 0.8 for value in coverage(observed, lower, upper))


def test_select_method_uses_the_lowest_nll_and_breaks_ties_by_order() -> None:
    assert select_method({ENSEMBLE: 2.0, MC_DROPOUT: 1.0}) == MC_DROPOUT
    assert select_method({ENSEMBLE: 1.0, MC_DROPOUT: 1.0}) == ENSEMBLE
    with pytest.raises(UncertaintyError):
        select_method({"bootstrap": 1.0})
    distribution = _distribution()
    observed = distribution.mean.clone()
    expected = float((0.5 * torch.log(2 * math.pi * distribution.std.pow(2))).mean())
    assert gaussian_nll(observed, distribution) == pytest.approx(expected)


def test_member_seeds_do_not_collide_across_folds() -> None:
    assert member_seed(42000, 0) == 42000
    assert member_seed(42000, 1) == 42000 + MEMBER_SEED_STRIDE
    fold_seeds = {42000 + 100 * seed + fold for seed in range(10) for fold in range(5)}
    members = {member_seed(s, m) for s in fold_seeds for m in range(1, 5)}
    assert not members & fold_seeds


# ---------------------------------------------------------------------------
# MC-dropout
# ---------------------------------------------------------------------------


def test_mc_dropout_restores_each_module_mode() -> None:
    model = nn.Sequential(nn.Linear(2, 2), nn.Dropout(0.5), nn.BatchNorm1d(2))
    model.eval()
    with mc_dropout(model):
        assert model[1].training
        assert not model[2].training
    assert not any(module.training for module in model.modules())
    model.train()
    with mc_dropout(model):
        assert not model[2].training
    assert all(module.training for module in model.modules())
    with pytest.raises(UncertaintyError), mc_dropout(nn.Linear(2, 2)):
        pass


def test_mc_dropout_samples_are_deterministic_and_keep_eval(
    graphs: dict[str, HeteroData],
) -> None:
    selected = [graphs[s] for s in sorted(graphs)[:5]]
    model = build_model(
        load_model_config(REPO_ROOT / "configs" / "models" / "hetero_sage.yaml"),
        GraphMetadata.from_graphs(graphs.values()),
        target_names=MODEL_OUTPUT_NAMES,
    )
    model(next(iter(DataLoader(selected, batch_size=5))))  # inicializa los parámetros perezosos
    model.eval()
    transform = CompositionalTargetTransform.fit(selected)
    state = torch.random.get_rng_state()
    first = sample_mc_dropout(model, selected, transform, passes=3, seed=7, batch_size=2)
    second = sample_mc_dropout(model, selected, transform, passes=3, seed=7, batch_size=2)
    assert torch.equal(torch.random.get_rng_state(), state)
    assert first.shape == (3, 5, 3)
    assert torch.equal(first, second)
    assert float(first.std(dim=0).max()) > 0
    assert not any(module.training for module in model.modules())


# ---------------------------------------------------------------------------
# Un fold completo
# ---------------------------------------------------------------------------


def test_fold_shapes_and_selection_use_only_inner_validation(fold) -> None:  # type: ignore[no-untyped-def]
    for subset in (fold.inner_val, fold.test):
        assert set(subset) == set(METHODS)
    assert fold.test[ENSEMBLE].sample_ids == fold.test[MC_DROPOUT].sample_ids
    assert fold.test[ENSEMBLE].n_samples == 3
    assert fold.test[MC_DROPOUT].n_samples == 4
    assert fold.test[ENSEMBLE].mean.shape == (4, 3)
    assert fold.observed_test.shape == (4, 3)
    assert fold.reference_test.shape == (4, 3)
    assert len(fold.member_seeds) == len(fold.member_epochs) == 3
    assert fold.selected == select_method(fold.nll)
    assert set(fold.test[ENSEMBLE].sample_ids).isdisjoint(fold.inner_val[ENSEMBLE].sample_ids)
    for method in METHODS:
        # Factor y NLL se recalculan igual con solo el val interno.
        assert fold.scales[method] == fit_scale(fold.observed_inner_val, fold.inner_val[method])
        assert fold.nll[method] == gaussian_nll(fold.observed_inner_val, fold.inner_val[method])
    for low, high in fold.train_fraction_support:
        assert 0 < low <= high < 1


def test_fold_is_deterministic(fold, fold_inputs) -> None:  # type: ignore[no-untyped-def]
    again = run_uncertainty_fold(seed=0, fold=0, ensemble_size=3, mc_passes=4, **fold_inputs)
    for method in METHODS:
        assert torch.equal(again.test[method].mean, fold.test[method].mean)
        assert torch.equal(again.test[method].std, fold.test[method].std)
    assert again.scales == fold.scales


def test_member_zero_is_the_model_of_the_fold(fold, fold_inputs) -> None:  # type: ignore[no-untyped-def]
    evaluation = run_compositional_fold(
        seed=0, fold=0, model_name="hetero_sage", edges_arm="x", days={}, **fold_inputs
    )
    expected = {p["sample_id"]: (p["z1"], p["z2"], p["log_total"]) for p in evaluation.predictions}
    for row, sample_id in enumerate(fold.test[ENSEMBLE].sample_ids):
        assert fold.reference_test[row].tolist() == pytest.approx(expected[sample_id])


def test_interval_rows_cover_every_output_and_level(fold) -> None:  # type: ignore[no-untyped-def]
    rows = interval_rows(fold, "test", levels=(0.5, 0.9), draws=50)
    assert len(rows) == 4 * len(METHODS) * 2 * 2 * len(OUTPUT_NAMES)
    assert all(row["lower"] <= row["upper"] for row in rows)
    measured = observed_with_fractions(fold.observed_test)
    assert measured.shape == (4, len(OUTPUT_NAMES))
    with pytest.raises(UncertaintyError):
        interval_rows(fold, "train")


def test_invalid_fold_configuration(fold_inputs) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(UncertaintyError):
        run_uncertainty_fold(seed=0, fold=0, ensemble_size=1, **fold_inputs)
    leaked = {**fold_inputs, "test_ids": (*fold_inputs["test_ids"], fold_inputs["train_ids"][0])}
    with pytest.raises(UncertaintyError):
        run_uncertainty_fold(seed=0, fold=0, ensemble_size=2, mc_passes=2, **leaked)


# ---------------------------------------------------------------------------
# Agregados y reporte de scripts/estimate_uncertainty.py (A75-P2 y A75-P3)
# ---------------------------------------------------------------------------

_SPEC = importlib.util.spec_from_file_location(
    "estimate_uncertainty_script", REPO_ROOT / "scripts" / "estimate_uncertainty.py"
)
assert _SPEC is not None and _SPEC.loader is not None
script = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = script
_SPEC.loader.exec_module(script)


def test_wilson_and_verdict() -> None:
    low, high = script.wilson(45, 56)
    assert low < 45 / 56 < high
    assert script.verdict(0.8, low, high) == "compatible"
    assert script.verdict(0.9, 0.5, 0.7) == "subcobertura"
    assert script.verdict(0.5, 0.6, 0.9) == "sobrecobertura"
    assert script.verdict(0.5, math.nan, math.nan) == "sin datos"


def test_aggregate_uses_animals_per_seed_not_the_sum_of_seeds() -> None:
    rows = [
        {
            "seed": str(seed),
            "fold": str(fold_index),
            "subset": "test",
            "method": "selected",
            "calibrated": "True",
            "level": "0.8",
            "output": "acetate",
            "day": "all",
            "n": "10",
            "covered": "8",
            "mean_width": "0.1",
        }
        for seed in range(2)
        for fold_index in range(3)
    ]
    (row,) = script.aggregate_coverage(rows)
    assert row["observed"] == pytest.approx(0.8)
    assert row["animals_per_seed"] == 30
    assert row["n_folds"] == 6
    assert row["verdict"] == "compatible"


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def test_report_from_a_synthetic_fold(fold, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    ids = [*fold.test["ensemble"].sample_ids, *fold.inner_val["ensemble"].sample_ids]
    days = {s: ("7" if index % 2 else "35") for index, s in enumerate(ids)}
    levels = (0.5, 0.8, 0.9)
    script._append(
        tmp_path / "fold_coverage.csv",
        script.COVERAGE_HEADER,
        script.coverage_rows(fold, days, levels, 200),
    )
    script._append(
        tmp_path / "predictions.csv",
        script.PREDICTION_HEADER,
        script.prediction_rows(fold, days, levels, 200),
    )
    script._append(
        tmp_path / "selection.csv", script.SELECTION_HEADER, [script.selection_row(fold)]
    )
    report = script.write_aggregates(
        tmp_path,
        {
            "variant": "hetero_sage",
            "seeds": [0],
            "ensemble_size": 3,
            "mc_passes": 4,
            "levels": levels,
            "device": "cpu",
            "note": "",
        },
    )
    assert "Revisión de Desarrollo, no aprobación de Investigación" in report
    assert "muy ruidosa" in report
    assert "Conclusión de calibración" in report
    with (tmp_path / "coverage.csv").open(encoding="utf-8") as handle:
        coverage = list(csv.DictReader(handle))
    selected = [r for r in coverage if r["method"] == "selected"]
    assert {r["subset"] for r in selected} == {"inner_val", "test"}
    assert {r["day"] for r in selected} == {"all", "7", "35"}
    with (tmp_path / "coherence.csv").open(encoding="utf-8") as handle:
        findings = {r["id"]: r for r in csv.DictReader(handle)}
    assert findings["A75-C1"]["status"] == "coherente"
    assert findings["A75-C2"]["status"] == "coherente"  # p_p ≤ 2/3
    assert findings["A75-C5"]["status"] == "sin fuente"
    assert all(r["source"] for r in findings.values())
    with (tmp_path / "predictions.csv").open(encoding="utf-8") as handle:
        predictions = list(csv.DictReader(handle))
    reference = [r for r in predictions if r["method"] == "reference"]
    assert len(reference) == 4 * 6
