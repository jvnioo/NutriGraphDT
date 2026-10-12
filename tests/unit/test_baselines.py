"""Baselines trivial y lineales (A40-4, #74).

Las tablas de prueba tienen objetivos que dependen linealmente de los atributos, de modo que
Ridge debe superar al piso de la media; así se comprueba que el modelo aprende y no solo que
corre. Requiere el extra `baselines`.
"""

from __future__ import annotations

import dataclasses
import json
import math
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("sklearn")

from sklearn.model_selection import GridSearchCV, GroupKFold  # noqa: E402

from nutrigraphdt.models.baselines import (  # noqa: E402
    LINEAR_BASELINE_NAMES,
    LinearBaselineConfig,
    build_linear_baselines,
    train_linear_baselines,
)
from nutrigraphdt.models.tabular import TabularDataset, TabularSample  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "configs" / "baselines" / "linear.json"

SMALL_CONFIG = LinearBaselineConfig(
    ridge_alphas=(0.01, 1.0),
    elasticnet_alphas=(0.01, 1.0),
    elasticnet_l1_ratios=(0.5,),
    elasticnet_max_iter=10000,
    cv_folds=3,
    scoring="neg_root_mean_squared_error",
)


def _targets(x1: float, x2: float) -> dict[str, float]:
    return {
        "acetate": 50.0 + 3.0 * x1,
        "propionate": 20.0 - 2.0 * x2,
        "butyrate": 10.0 + x1 + x2,
    }


def _sample(index: int, split: str) -> TabularSample:
    x1 = float(index % 7)
    x2 = float((index * 3) % 5)
    return TabularSample(
        sample_id=f"s{index:02d}",
        graph_id=f"g{index:02d}",
        features={"host:x1": x1, "host:x2": x2, "host:sex": "male" if index % 2 else "female"},
        targets=_targets(x1, x2),
        split=split,
    )


def _dataset(n_train: int = 12, n_val: int = 4, n_test: int = 4) -> TabularDataset:
    splits = ["train"] * n_train + ["val"] * n_val + ["test"] * n_test
    return TabularDataset(
        samples=tuple(_sample(i, split) for i, split in enumerate(splits)),
        feature_names=("host:sex", "host:x1", "host:x2"),
        dataset_id="test_linear",
    )


def _groups(dataset: TabularDataset, per_group: int = 2) -> dict[str, str]:
    return {sid: f"pen{i // per_group}" for i, sid in enumerate(dataset.sample_ids)}


def _row(result: Any, model: str, split: str, metric: str) -> float:
    row = result.report.get_row(metric, model=model, split=split)
    assert row is not None
    return float(row.average)


class TestConfig:
    def test_repository_config_loads(self) -> None:
        config = LinearBaselineConfig.load(CONFIG_PATH)
        assert config.cv_folds >= 2
        assert config.to_dict() == json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    def test_rejects_unknown_and_missing_keys(self) -> None:
        data = SMALL_CONFIG.to_dict()
        with pytest.raises(ValueError, match="desconocidas"):
            LinearBaselineConfig.from_dict({**data, "alpha": 1.0})
        del data["cv_folds"]
        with pytest.raises(ValueError, match="faltan"):
            LinearBaselineConfig.from_dict(data)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("ridge_alphas", ()),
            ("ridge_alphas", (0.0,)),
            ("elasticnet_alphas", (math.nan,)),
            ("elasticnet_l1_ratios", (1.5,)),
            ("cv_folds", 1),
            ("elasticnet_max_iter", 0),
            ("scoring", ""),
        ],
    )
    def test_rejects_invalid_values(self, field: str, value: object) -> None:
        with pytest.raises(ValueError):
            dataclasses.replace(SMALL_CONFIG, **{field: value})

    def test_rejects_non_integer_folds(self) -> None:
        with pytest.raises(ValueError, match="entero"):
            LinearBaselineConfig.from_dict({**SMALL_CONFIG.to_dict(), "cv_folds": 3.5})


class TestTraining:
    def test_estimators_use_grouped_cross_validation(self) -> None:
        estimators = build_linear_baselines(SMALL_CONFIG)
        assert tuple(estimators) == LINEAR_BASELINE_NAMES
        for name in ("ridge", "elasticnet"):
            search = estimators[name]
            assert isinstance(search, GridSearchCV)
            assert isinstance(search.cv, GroupKFold)
            assert search.cv.n_splits == SMALL_CONFIG.cv_folds

    def test_reports_every_model_split_and_metric(self) -> None:
        dataset = _dataset()
        result = train_linear_baselines(dataset, _groups(dataset), SMALL_CONFIG)

        keys = {(row.model, row.split, row.metric) for row in result.report.rows}
        assert keys == {
            (model, split, metric)
            for model in LINEAR_BASELINE_NAMES
            for split in ("val", "test")
            for metric in ("mae", "rmse", "r2", "negative_pct")
        }
        assert result.subset_sizes == {"train": 12, "val": 4, "test": 4}
        assert set(result.best_params) == set(LINEAR_BASELINE_NAMES)
        assert result.best_params["ridge"]["model__alpha"] in SMALL_CONFIG.ridge_alphas
        assert "host:sex=male" in result.feature_names

    def test_dummy_predicts_training_mean(self) -> None:
        dataset = _dataset()
        result = train_linear_baselines(dataset, _groups(dataset), SMALL_CONFIG)

        train_y = dataset.train_dataset.y
        val_y = dataset.val_dataset.y
        expected = []
        for k in range(3):
            mean = sum(row[k] for row in train_y) / len(train_y)
            expected.append(sum(abs(row[k] - mean) for row in val_y) / len(val_y))
        assert _row(result, "dummy_mean", "val", "mae") == pytest.approx(sum(expected) / 3)

    def test_ridge_beats_the_mean_on_linear_targets(self) -> None:
        dataset = _dataset()
        result = train_linear_baselines(dataset, _groups(dataset), SMALL_CONFIG)

        for split in ("val", "test"):
            assert _row(result, "ridge", split, "mae") < _row(result, "dummy_mean", split, "mae")
            assert _row(result, "ridge", split, "r2") > 0.9

    def test_val_and_test_do_not_influence_training(self) -> None:
        dataset = _dataset()
        shifted = TabularDataset(
            samples=tuple(
                s
                if s.split == "train"
                else dataclasses.replace(
                    s, features={**s.features, "host:x1": 1e6, "host:x2": -1e6}
                )
                for s in dataset.samples
            ),
            feature_names=dataset.feature_names,
        )
        base = train_linear_baselines(dataset, _groups(dataset), SMALL_CONFIG)
        moved = train_linear_baselines(shifted, _groups(shifted), SMALL_CONFIG)

        assert moved.best_params == base.best_params
        assert _row(moved, "dummy_mean", "val", "mae") == pytest.approx(
            _row(base, "dummy_mean", "val", "mae")
        )


class TestInvalidInputs:
    def test_missing_group(self) -> None:
        dataset = _dataset()
        groups = _groups(dataset)
        del groups["s00"]
        with pytest.raises(ValueError, match="s00"):
            train_linear_baselines(dataset, groups, SMALL_CONFIG)

    def test_fewer_groups_than_folds(self) -> None:
        dataset = _dataset()
        groups = {sid: "pen0" if i % 2 else "pen1" for i, sid in enumerate(dataset.sample_ids)}
        with pytest.raises(ValueError, match="2 grupos"):
            train_linear_baselines(dataset, groups, SMALL_CONFIG)

    def test_missing_target(self) -> None:
        dataset = _dataset()
        first = dataset.samples[0]
        incomplete = dataclasses.replace(first, targets={"acetate": 1.0, "propionate": 2.0})
        broken = dataclasses.replace(dataset, samples=(incomplete, *dataset.samples[1:]))
        with pytest.raises(ValueError, match="'train'.*no finitos"):
            train_linear_baselines(broken, _groups(broken), SMALL_CONFIG)

    def test_empty_evaluation_subset(self) -> None:
        dataset = _dataset(n_test=0)
        with pytest.raises(ValueError, match="'test' no tiene muestras"):
            train_linear_baselines(dataset, _groups(dataset), SMALL_CONFIG)
