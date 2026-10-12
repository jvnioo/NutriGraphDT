"""Baselines trivial y lineales para la predicción de AGCC (A40-4, #74).

Fija los pisos de desempeño que la GNN debe superar, sobre la tabla de atributos de A40-3:

- `dummy_mean`: `DummyRegressor` que predice la media de cada AGCC en entrenamiento.
- `ridge` y `elasticnet`: modelos multisalida (acetato, propionato y butirato a la vez) dentro de
  un `Pipeline` con `StandardScaler`.

Garantías:

1. **Escalado sin fuga**: el `StandardScaler` vive dentro del `Pipeline`, de modo que en cada
   fold de la validación cruzada se ajusta solo con la parte de entrenamiento del fold, y el
   modelo final solo con el subconjunto `train`. `val` y `test` nunca participan en el ajuste.
2. **Validación cruzada agrupada**: los hiperparámetros se eligen con `GroupKFold` sobre
   `train`. El grupo lo entrega quien llama, y debe ser la misma unidad de la partición de
   A40-1 (en D1, el corral `pen_code`), para que un grupo nunca quede a ambos lados de un fold.
3. **Formato común**: las métricas de `val` y `test` se calculan con `evaluate_predictions`
   (A40-2), una fila por modelo, partición y métrica.

Los valores de la grilla y el número de folds se leen de `configs/baselines/linear.json`; son
decisiones de implementación, no constantes científicas. Requiere el extra `baselines`
(scikit-learn).
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

try:
    from sklearn.dummy import DummyRegressor
    from sklearn.linear_model import ElasticNet, Ridge
    from sklearn.model_selection import GridSearchCV, GroupKFold
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
except ImportError as exc:  # pragma: no cover - depende del entorno
    raise ImportError(
        "nutrigraphdt.models.baselines requiere scikit-learn; instale el extra con "
        '`pip install -e ".[baselines]"`.'
    ) from exc

from nutrigraphdt.models.metrics import EvaluationReport, combine_reports, evaluate_predictions
from nutrigraphdt.models.tabular import TabularDataset

LINEAR_BASELINE_NAMES: Final[tuple[str, ...]] = ("dummy_mean", "ridge", "elasticnet")
EVALUATION_SPLITS: Final[tuple[str, ...]] = ("val", "test")

_CONFIG_KEYS: Final[frozenset[str]] = frozenset(
    {
        "ridge_alphas",
        "elasticnet_alphas",
        "elasticnet_l1_ratios",
        "elasticnet_max_iter",
        "cv_folds",
        "scoring",
    }
)


@dataclass(frozen=True)
class LinearBaselineConfig:
    """Grilla de hiperparámetros y validación cruzada de los baselines lineales."""

    ridge_alphas: tuple[float, ...]
    elasticnet_alphas: tuple[float, ...]
    elasticnet_l1_ratios: tuple[float, ...]
    elasticnet_max_iter: int
    cv_folds: int
    scoring: str

    def __post_init__(self) -> None:
        for name in ("ridge_alphas", "elasticnet_alphas", "elasticnet_l1_ratios"):
            values = getattr(self, name)
            if not values:
                raise ValueError(f"{name} debe tener al menos un valor.")
            if not all(_is_finite_number(v) and v > 0 for v in values):
                raise ValueError(f"{name} solo admite números finitos y positivos: {values}.")
        if any(v > 1 for v in self.elasticnet_l1_ratios):
            raise ValueError(
                f"elasticnet_l1_ratios debe estar en (0, 1]: {self.elasticnet_l1_ratios}."
            )
        if isinstance(self.elasticnet_max_iter, bool) or self.elasticnet_max_iter < 1:
            raise ValueError(f"elasticnet_max_iter debe ser >= 1: {self.elasticnet_max_iter}.")
        if isinstance(self.cv_folds, bool) or self.cv_folds < 2:
            raise ValueError(f"cv_folds debe ser >= 2 (GroupKFold): {self.cv_folds}.")
        if not self.scoring:
            raise ValueError("scoring no puede estar vacío.")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LinearBaselineConfig:
        """Construye la configuración rechazando claves faltantes o desconocidas."""
        missing = _CONFIG_KEYS - data.keys()
        unknown = data.keys() - _CONFIG_KEYS
        if missing or unknown:
            raise ValueError(
                "Configuración de baselines inválida: "
                f"faltan {sorted(missing)}, desconocidas {sorted(unknown)}."
            )
        return cls(
            ridge_alphas=_float_tuple(data, "ridge_alphas"),
            elasticnet_alphas=_float_tuple(data, "elasticnet_alphas"),
            elasticnet_l1_ratios=_float_tuple(data, "elasticnet_l1_ratios"),
            elasticnet_max_iter=_int_value(data, "elasticnet_max_iter"),
            cv_folds=_int_value(data, "cv_folds"),
            scoring=str(data["scoring"]),
        )

    @classmethod
    def load(cls, path: str | Path) -> LinearBaselineConfig:
        """Lee la configuración desde un JSON (por ejemplo `configs/baselines/linear.json`)."""
        content = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(content, Mapping):
            raise ValueError(f"{path}: se esperaba un objeto JSON.")
        return cls.from_dict(content)

    def to_dict(self) -> dict[str, Any]:
        """Configuración efectiva, para registrarla junto a los resultados."""
        return {key: list(v) if isinstance(v, tuple) else v for key, v in asdict(self).items()}


@dataclass(frozen=True)
class BaselineResult:
    """Métricas de `val` y `test` y los hiperparámetros elegidos por la validación cruzada."""

    report: EvaluationReport
    best_params: dict[str, dict[str, Any]]
    feature_names: tuple[str, ...]
    subset_sizes: dict[str, int]
    cv_folds: int


def build_linear_baselines(config: LinearBaselineConfig) -> dict[str, Any]:
    """Estimadores sin entrenar, en el orden de `LINEAR_BASELINE_NAMES`.

    `ridge` y `elasticnet` son `GridSearchCV` con `GroupKFold`; deben ajustarse pasando
    `groups`. Ambos modelos lineales admiten `y` con varias columnas de forma nativa.
    """
    cv = GroupKFold(n_splits=config.cv_folds)
    ridge = Pipeline([("scale", StandardScaler()), ("model", Ridge())])
    elasticnet = Pipeline(
        [
            ("scale", StandardScaler()),
            ("model", ElasticNet(max_iter=config.elasticnet_max_iter)),
        ]
    )
    return {
        "dummy_mean": DummyRegressor(strategy="mean"),
        "ridge": GridSearchCV(
            ridge,
            {"model__alpha": list(config.ridge_alphas)},
            cv=cv,
            scoring=config.scoring,
            error_score="raise",
        ),
        "elasticnet": GridSearchCV(
            elasticnet,
            {
                "model__alpha": list(config.elasticnet_alphas),
                "model__l1_ratio": list(config.elasticnet_l1_ratios),
            },
            cv=cv,
            scoring=config.scoring,
            error_score="raise",
        ),
    }


def train_linear_baselines(
    dataset: TabularDataset,
    groups: Mapping[str, str],
    config: LinearBaselineConfig,
) -> BaselineResult:
    """Entrena los baselines con `train` y los evalúa en `val` y `test`.

    Args:
        dataset: Tabla de A40-3 con la partición de A40-1 aplicada.
        groups: Grupo de validación cruzada de cada `sample_id` de `train` (la unidad de la
            partición: corral en D1, animal en el sintético).
        config: Grilla y número de folds.

    Raises:
        ValueError: si algún subconjunto está vacío, tiene objetivos ausentes o no finitos,
            falta el grupo de una muestra de `train` o hay menos grupos que folds.
    """
    vocab = dataset.categorical_vocabulary()
    feature_names, _ = dataset.get_subset("train").to_numeric_matrix(categorical_vocab=vocab)

    matrices: dict[str, tuple[list[list[float]], list[list[float]]]] = {}
    for subset in ("train", *EVALUATION_SPLITS):
        X, y = dataset.get_split_matrices(subset, numeric=True, one_hot=True)
        if not X:
            raise ValueError(f"El subconjunto '{subset}' no tiene muestras.")
        if not all(math.isfinite(v) for row in y for v in row):
            raise ValueError(
                f"El subconjunto '{subset}' tiene objetivos ausentes o no finitos; "
                "los baselines requieren los tres AGCC en cada muestra."
            )
        matrices[subset] = (X, y)

    train_ids = dataset.get_subset("train").sample_ids
    missing = [sid for sid in train_ids if sid not in groups]
    if missing:
        raise ValueError(f"Faltan grupos de validación cruzada para: {missing}.")
    train_groups = [groups[sid] for sid in train_ids]
    n_groups = len(set(train_groups))
    if n_groups < config.cv_folds:
        raise ValueError(
            f"train tiene {n_groups} grupos y la configuración pide {config.cv_folds} folds; "
            "reduzca cv_folds o use más grupos."
        )

    X_train, y_train = matrices["train"]
    reports: list[EvaluationReport] = []
    best_params: dict[str, dict[str, Any]] = {}
    for name, estimator in build_linear_baselines(config).items():
        if isinstance(estimator, GridSearchCV):
            estimator.fit(X_train, y_train, groups=train_groups)
            best_params[name] = dict(estimator.best_params_)
        else:
            estimator.fit(X_train, y_train)
            best_params[name] = {}
        for subset in EVALUATION_SPLITS:
            X_eval, y_eval = matrices[subset]
            reports.append(
                evaluate_predictions(
                    y_eval,
                    estimator.predict(X_eval).tolist(),
                    model_name=name,
                    targets=dataset.target_names,
                    split=subset,
                )
            )

    return BaselineResult(
        report=combine_reports(reports),
        best_params=best_params,
        feature_names=feature_names,
        subset_sizes={subset: len(matrices[subset][0]) for subset in matrices},
        cv_folds=config.cv_folds,
    )


def _is_finite_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _float_tuple(data: Mapping[str, Any], key: str) -> tuple[float, ...]:
    values = data[key]
    if not isinstance(values, Sequence) or isinstance(values, str):
        raise ValueError(f"{key} debe ser una lista de números.")
    if not all(_is_finite_number(v) for v in values):
        raise ValueError(f"{key} solo admite números finitos: {values}.")
    return tuple(float(v) for v in values)


def _int_value(data: Mapping[str, Any], key: str) -> int:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} debe ser un entero: {value!r}.")
    return value
