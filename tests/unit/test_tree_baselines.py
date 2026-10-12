"""Baselines de árboles e importancia por permutación (A40-5, #75).

Los objetivos de prueba dependen de `host:x1` y `host:x2` y no de `host:noise`, de modo que la
importancia de los atributos informativos debe superar a la del ruido. Requiere el extra
`baselines`.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("sklearn")

from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor  # noqa: E402
from sklearn.model_selection import GridSearchCV, GroupKFold  # noqa: E402
from sklearn.multioutput import MultiOutputRegressor  # noqa: E402

from nutrigraphdt.models.baselines import (  # noqa: E402
    IMPORTANCE_SPLIT,
    TREE_BASELINE_NAMES,
    TreeBaselineConfig,
    build_synthetic_baseline_dataset,
    build_tree_baselines,
    train_tree_baselines,
)
from nutrigraphdt.models.tabular import TabularDataset, TabularSample  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "configs" / "baselines" / "trees.json"

SMALL_CONFIG = TreeBaselineConfig(
    random_forest_n_estimators=(50,),
    random_forest_max_depth=(None, 3),
    random_forest_min_samples_leaf=(1,),
    hist_gradient_boosting_learning_rate=(0.1,),
    hist_gradient_boosting_max_iter=(50,),
    hist_gradient_boosting_max_depth=(None,),
    hist_gradient_boosting_min_samples_leaf=(2,),
    cv_folds=3,
    scoring="neg_root_mean_squared_error",
    random_state=0,
    permutation_repeats=5,
)


def _sample(index: int, split: str) -> TabularSample:
    x1 = float(index % 7)
    x2 = float((index * 3) % 5)
    noise = float((index * 5) % 11)
    return TabularSample(
        sample_id=f"s{index:02d}",
        graph_id=f"g{index:02d}",
        features={"host:x1": x1, "host:x2": x2, "host:noise": noise},
        targets={
            "acetate": 50.0 + 6.0 * x1,
            "propionate": 20.0 + 4.0 * x2,
            "butyrate": 10.0 + 2.0 * x1,
        },
        split=split,
    )


def _dataset(n_train: int = 24, n_val: int = 8, n_test: int = 8) -> TabularDataset:
    splits = ["train"] * n_train + ["val"] * n_val + ["test"] * n_test
    return TabularDataset(
        samples=tuple(_sample(i, split) for i, split in enumerate(splits)),
        feature_names=("host:noise", "host:x1", "host:x2"),
        dataset_id="test_trees",
    )


def _groups(dataset: TabularDataset) -> dict[str, str]:
    return {sid: f"pen{i // 2}" for i, sid in enumerate(dataset.sample_ids)}


def _importance(result: Any, model: str) -> dict[str, float]:
    return {item.feature: item.importance_mean for item in result.feature_importances[model]}


@pytest.fixture(scope="module")
def trained() -> Any:
    dataset = _dataset()
    return train_tree_baselines(dataset, _groups(dataset), SMALL_CONFIG)


class TestConfig:
    def test_repository_config_loads(self) -> None:
        config = TreeBaselineConfig.load(CONFIG_PATH)
        assert config.to_dict() == json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        assert None in config.random_forest_max_depth

    def test_rejects_unknown_keys(self) -> None:
        with pytest.raises(ValueError, match="desconocidas"):
            TreeBaselineConfig.from_dict({**SMALL_CONFIG.to_dict(), "n_jobs": 4})

    def test_rejects_null_outside_depth(self) -> None:
        data = {**SMALL_CONFIG.to_dict(), "random_forest_n_estimators": [None]}
        with pytest.raises(ValueError, match="enteros"):
            TreeBaselineConfig.from_dict(data)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("random_forest_n_estimators", ()),
            ("random_forest_max_depth", (0,)),
            ("random_forest_min_samples_leaf", (True,)),
            ("hist_gradient_boosting_learning_rate", (0.0,)),
            ("hist_gradient_boosting_max_iter", (-1,)),
            ("cv_folds", 1),
            ("random_state", True),
            ("permutation_repeats", 0),
            ("scoring", ""),
        ],
    )
    def test_rejects_invalid_values(self, field: str, value: object) -> None:
        with pytest.raises(ValueError):
            dataclasses.replace(SMALL_CONFIG, **{field: value})


class TestTraining:
    def test_estimators_use_grouped_cross_validation(self) -> None:
        estimators = build_tree_baselines(SMALL_CONFIG)
        assert tuple(estimators) == TREE_BASELINE_NAMES
        for search in estimators.values():
            assert isinstance(search, GridSearchCV)
            assert isinstance(search.cv, GroupKFold)
            assert search.cv.n_splits == SMALL_CONFIG.cv_folds
        assert isinstance(estimators["random_forest"].estimator, RandomForestRegressor)
        boosting = estimators["hist_gradient_boosting"].estimator
        assert isinstance(boosting, MultiOutputRegressor)
        assert isinstance(boosting.estimator, HistGradientBoostingRegressor)

    def test_reports_every_model_split_and_metric(self, trained: Any) -> None:
        keys = {(row.model, row.split, row.metric) for row in trained.report.rows}
        assert keys == {
            (model, split, metric)
            for model in TREE_BASELINE_NAMES
            for split in ("val", "test")
            for metric in ("mae", "rmse", "r2", "negative_pct")
        }
        assert set(trained.best_params) == set(TREE_BASELINE_NAMES)
        assert trained.best_params["random_forest"]["max_depth"] in (None, 3)

    def test_models_learn_the_signal(self, trained: Any) -> None:
        for model in TREE_BASELINE_NAMES:
            r2 = trained.report.get_row("r2", model=model, split="test")
            assert r2 is not None
            assert r2.average > 0.5

    def test_importances_cover_every_feature(self, trained: Any) -> None:
        for model in TREE_BASELINE_NAMES:
            features = tuple(item.feature for item in trained.feature_importances[model])
            assert features == trained.feature_names
            assert all(item.importance_std >= 0 for item in trained.feature_importances[model])

    def test_informative_features_outrank_noise(self, trained: Any) -> None:
        for model in TREE_BASELINE_NAMES:
            importance = _importance(trained, model)
            assert importance["host:x1"] > importance["host:noise"]
            assert importance["host:x2"] > importance["host:noise"]

    def test_training_is_reproducible(self, trained: Any) -> None:
        dataset = _dataset()
        again = train_tree_baselines(dataset, _groups(dataset), SMALL_CONFIG)
        assert again.best_params == trained.best_params
        assert again.feature_importances == trained.feature_importances

    def test_test_split_does_not_influence_training_or_importance(self, trained: Any) -> None:
        dataset = _dataset()
        shifted = dataclasses.replace(
            dataset,
            samples=tuple(
                dataclasses.replace(s, features={**s.features, "host:x1": 1e6})
                if s.split == "test"
                else s
                for s in dataset.samples
            ),
        )
        moved = train_tree_baselines(shifted, _groups(shifted), SMALL_CONFIG)
        assert IMPORTANCE_SPLIT != "test"
        assert moved.best_params == trained.best_params
        assert moved.feature_importances == trained.feature_importances

    def test_rejects_fewer_groups_than_folds(self) -> None:
        dataset = _dataset()
        groups = {sid: "pen0" if i % 2 else "pen1" for i, sid in enumerate(dataset.sample_ids)}
        with pytest.raises(ValueError, match="2 grupos"):
            train_tree_baselines(dataset, groups, SMALL_CONFIG)


def test_synthetic_baseline_dataset_groups_by_sample() -> None:
    dataset, groups = build_synthetic_baseline_dataset(n_samples=10, first_seed=1, split_seed=42)
    assert len(dataset) == 10
    assert groups == {sid: sid for sid in dataset.sample_ids}
    assert {s.split for s in dataset.samples} == {"train", "val", "test"}
