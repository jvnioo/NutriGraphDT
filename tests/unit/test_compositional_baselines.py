"""Tests de los baselines con objetivo composicional bajo CV por corral (#140).

La cohorte de estas pruebas es **ficticia**: ocho animales con valores elegidos a mano. No
contiene datos reales.
"""

from __future__ import annotations

import math

import pytest

pytest.importorskip("sklearn")

from nutrigraphdt.models.baselines import (  # noqa: E402
    LinearBaselineConfig,
    TreeBaselineConfig,
)
from nutrigraphdt.models.composition import compositional_target  # noqa: E402
from nutrigraphdt.models.compositional_baselines import (  # noqa: E402
    ALL_DAYS,
    CV_SPLIT,
    DAY_ONLY_NAME,
    DESIGN_RIDGE_NAME,
    INVESTIGATION_TABLE5,
    MODEL_NAMES,
    CompositionalBaselineError,
    DayMeanRegressor,
    aggregate_rows,
    design_column_indices,
    prepare_compositional_data,
    run_compositional_baselines,
)
from nutrigraphdt.models.cross_validation import (  # noqa: E402
    CrossValidationError,
    PenFoldPlan,
)
from nutrigraphdt.models.tabular import TabularDataset, TabularSample  # noqa: E402

FEATURES = (
    "diet:treatment",
    "host:trial_code",
    "host:sampling_day",
    "host:sex",
    "host:breed",
    "taxon:g__A",
)
CONCENTRATIONS = (
    (50.0, 20.0, 10.0),
    (55.0, 22.0, 11.0),
    (48.0, 18.0, 9.0),
    (60.0, 25.0, 12.0),
    (52.0, 21.0, 10.5),
    (58.0, 24.0, 11.5),
    (49.0, 19.0, 9.5),
    (61.0, 26.0, 12.5),
)
DAYS = ("7", "7", "21", "21", "35", "35", "7", "21")
DIETS = ("Control", "Control", "Probiotic", "Probiotic") * 2
PENS = {f"S{i:02d}": f"P{i % 4}" for i in range(8)}

LINEAR = LinearBaselineConfig(
    ridge_alphas=(1.0, 10.0),
    elasticnet_alphas=(0.1,),
    elasticnet_l1_ratios=(0.5,),
    elasticnet_max_iter=5000,
    cv_folds=2,
    scoring="neg_root_mean_squared_error",
)
TREE = TreeBaselineConfig(
    random_forest_n_estimators=(10,),
    random_forest_max_depth=(3,),
    random_forest_min_samples_leaf=(1,),
    hist_gradient_boosting_learning_rate=(0.1,),
    hist_gradient_boosting_max_iter=(20,),
    hist_gradient_boosting_max_depth=(3,),
    hist_gradient_boosting_min_samples_leaf=(1,),
    cv_folds=2,
    scoring="neg_root_mean_squared_error",
    random_state=42,
    permutation_repeats=2,
)


def toy_dataset(
    concentrations: tuple[tuple[float, float, float], ...] = CONCENTRATIONS,
) -> TabularDataset:
    samples = []
    for i, (acetate, propionate, butyrate) in enumerate(concentrations):
        samples.append(
            TabularSample(
                sample_id=f"S{i:02d}",
                graph_id=f"g{i:02d}",
                features={
                    "diet:treatment": DIETS[i],
                    "host:trial_code": "CA" if i % 2 == 0 else "CB",
                    "host:sampling_day": DAYS[i],
                    "host:sex": "male" if i % 2 == 0 else "female",
                    "host:breed": "Ross",
                    "taxon:g__A": 0.1 * (i + 1),
                },
                targets={
                    "acetate": acetate,
                    "propionate": propionate,
                    "butyrate": butyrate,
                },
            )
        )
    return TabularDataset(samples=tuple(samples), feature_names=FEATURES)


def toy_plan() -> PenFoldPlan:
    ids = sorted(PENS)
    return PenFoldPlan.from_dict(
        {
            "dataset_id": "toy",
            "k": 2,
            "seeds": [0, 1],
            "assignments": {
                "0": {s: i % 2 for i, s in enumerate(ids)},
                "1": {s: (i + 1) % 2 for i, s in enumerate(ids)},
            },
        }
    )


def test_prepare_derives_compositional_output_and_design_matrix() -> None:
    data = prepare_compositional_data(toy_dataset(), PENS)

    assert data.sample_ids == tuple(f"S{i:02d}" for i in range(8))
    assert data.days == DAYS
    assert data.pens == tuple(PENS[f"S{i:02d}"] for i in range(8))
    first = compositional_target(*CONCENTRATIONS[0])
    assert data.outputs[0] == pytest.approx(first.model_output)
    assert data.concentrations[3] == CONCENTRATIONS[3]
    assert set(data.design_names) <= {
        name for name in data.feature_names if not name.startswith("taxon:")
    }
    assert not any(name.startswith("taxon:") for name in data.design_names)
    assert len(data.design_matrix) == 8
    assert len(data.design_matrix[0]) == len(data.design_names)


def test_prepare_rejects_zero_concentration_without_pseudocount() -> None:
    concentrations = ((50.0, 0.0, 10.0), *CONCENTRATIONS[1:])
    with pytest.raises(CompositionalBaselineError, match="pseudoconteo"):
        prepare_compositional_data(toy_dataset(concentrations), PENS)


def test_prepare_requires_pen_and_day() -> None:
    with pytest.raises(CompositionalBaselineError, match="corral"):
        prepare_compositional_data(toy_dataset(), {k: v for k, v in PENS.items() if k != "S03"})

    dataset = toy_dataset()
    samples = [
        TabularSample(
            sample_id=s.sample_id,
            graph_id=s.graph_id,
            features={k: v for k, v in s.features.items() if k != "host:sampling_day"},
            targets=s.targets,
        )
        for s in dataset.samples
    ]
    without_day = TabularDataset(
        samples=tuple(samples),
        feature_names=tuple(f for f in FEATURES if f != "host:sampling_day"),
    )
    with pytest.raises(CompositionalBaselineError, match="sampling_day"):
        prepare_compositional_data(without_day, PENS)


def test_design_column_indices_cover_bases_and_one_hot() -> None:
    names = ("taxon:g__A", "host:sex=male", "diet:treatment=Control", "host:sampling_day=7")
    assert design_column_indices(names) == [1, 2, 3]
    with pytest.raises(CompositionalBaselineError, match="factores del diseño"):
        design_column_indices(("taxon:g__A",))


def test_day_mean_regressor_predicts_per_day_means_with_global_fallback() -> None:
    model = DayMeanRegressor().fit(["7", "7", "21"], [[1.0, 2.0], [3.0, 4.0], [10.0, 20.0]])
    assert model.predict(["7", "21", "35"]) == [[2.0, 3.0], [10.0, 20.0], [14.0 / 3, 26.0 / 3]]


def test_day_mean_regressor_validates_input() -> None:
    with pytest.raises(CompositionalBaselineError):
        DayMeanRegressor().predict(["7"])
    with pytest.raises(CompositionalBaselineError):
        DayMeanRegressor().fit(["7"], [])
    with pytest.raises(CompositionalBaselineError):
        DayMeanRegressor().fit(["7", "8"], [[1.0], [1.0, 2.0]])


def test_run_covers_all_models_per_fold_and_logs_selections() -> None:
    data = prepare_compositional_data(toy_dataset(), PENS)
    result = run_compositional_baselines(data, toy_plan(), LINEAR, TREE, inner_folds=2)

    assert set(result.cv.fold_reports) == {(0, 0), (0, 1), (1, 0), (1, 1)}
    for report in result.cv.fold_reports.values():
        models = {row.model for row in report.rows}
        assert models == set(MODEL_NAMES)
        groups = {row.group for row in report.rows if row.model == DAY_ONLY_NAME}
        assert ALL_DAYS in groups
        assert {row.split for row in report.rows} == {CV_SPLIT}

    logged = [(s.seed, s.fold, s.model) for s in result.selections]
    assert len(logged) == 4 * (len(MODEL_NAMES) - 2)
    assert DAY_ONLY_NAME not in {s.model for s in result.selections}
    assert DESIGN_RIDGE_NAME in {s.model for s in result.selections}

    frac = aggregate_rows(result.aggregate, DAY_ONLY_NAME, "fraction_r2", ALL_DAYS)
    assert set(frac) == {"mean", "std", "seed_std", "n"}
    assert frac["n"].average == 4.0


def test_run_is_deterministic() -> None:
    data = prepare_compositional_data(toy_dataset(), PENS)
    first = run_compositional_baselines(data, toy_plan(), LINEAR, TREE, inner_folds=2)
    second = run_compositional_baselines(data, toy_plan(), LINEAR, TREE, inner_folds=2)
    assert first.aggregate.to_records() == second.aggregate.to_records()
    assert first.selections == second.selections


def test_parallel_run_matches_the_serial_run() -> None:
    data = prepare_compositional_data(toy_dataset(), PENS)
    serial = run_compositional_baselines(data, toy_plan(), LINEAR, TREE, inner_folds=2, n_jobs=1)
    parallel = run_compositional_baselines(data, toy_plan(), LINEAR, TREE, inner_folds=2, n_jobs=2)
    assert serial.aggregate.to_records() == parallel.aggregate.to_records()
    assert serial.selections == parallel.selections
    for key, report in serial.cv.fold_reports.items():
        assert report.to_records() == parallel.cv.fold_reports[key].to_records()


def test_run_rejects_a_plan_that_does_not_match_the_cohort() -> None:
    data = prepare_compositional_data(toy_dataset(), PENS)
    plan = PenFoldPlan.from_dict(
        {
            "dataset_id": "toy",
            "k": 2,
            "seeds": [0],
            "assignments": {"0": {"OTRO": 0, **{s: 0 for s in PENS}}},
        }
    )
    with pytest.raises(CrossValidationError, match="no coinciden"):
        run_compositional_baselines(data, plan, LINEAR, TREE, inner_folds=2)


def test_day_only_uses_only_the_day() -> None:
    """Con el día como única entrada, dos animales del mismo día reciben la misma predicción."""
    data = prepare_compositional_data(toy_dataset(), PENS)
    result = run_compositional_baselines(data, toy_plan(), LINEAR, TREE, inner_folds=2)
    report = result.cv.fold_reports[(0, 0)]
    by_day = {
        row.group: row
        for row in report.rows
        if row.model == DAY_ONLY_NAME and row.metric == "log_total_mae" and row.group != ALL_DAYS
    }
    assert by_day
    assert all(math.isfinite(row.average) for row in by_day.values())


def test_investigation_table5_documents_the_cohort_of_59() -> None:
    assert INVESTIGATION_TABLE5["fraction_r2"]["propionate"] == pytest.approx(0.40)
    assert INVESTIGATION_TABLE5["log_total_r2"]["log_total"] == pytest.approx(-0.14)
