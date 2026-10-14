"""Baselines no basados en grafos para la predicción de AGCC (A40-4, #74; A40-5, #75).

Fija los pisos de desempeño que la GNN debe superar, sobre la tabla de atributos de A40-3:

- `dummy_mean`: `DummyRegressor` que predice la media de cada AGCC en entrenamiento (A40-4).
- `ridge` y `elasticnet`: modelos multisalida (acetato, propionato y butirato a la vez) dentro de
  un `Pipeline` con `StandardScaler` (A40-4).
- `random_forest`: `RandomForestRegressor`, multisalida nativo (A40-5).
- `hist_gradient_boosting`: `HistGradientBoostingRegressor` envuelto en `MultiOutputRegressor`,
  un modelo por AGCC con la misma combinación de hiperparámetros (A40-5).

Garantías:

1. **Ajuste sin fuga**: todo lo que se ajusta a los datos (escalado y modelo) se ajusta solo con
   la parte de entrenamiento de cada fold y, en el modelo final, solo con `train`. `val` y
   `test` nunca participan en el ajuste ni en la selección de hiperparámetros.
2. **Validación cruzada agrupada**: los hiperparámetros se eligen con `GroupKFold` sobre
   `train`. El grupo lo entrega quien llama, y debe ser la misma unidad de la partición de
   A40-1 (en D1, el corral `pen_code`), para que un grupo nunca quede a ambos lados de un fold.
3. **Formato común**: las métricas de `val` y `test` se calculan con `evaluate_predictions`
   (A40-2), una fila por modelo, partición y métrica.
4. **Importancia de atributos comparable** (árboles): importancia por permutación sobre `val`
   para ambos modelos de árboles, con el mismo criterio que la selección de hiperparámetros.

Las grillas y el número de folds se leen de `configs/baselines/linear.json` y
`configs/baselines/trees.json`; son decisiones de implementación, no constantes científicas.
Requiere el extra `baselines` (scikit-learn).
"""

from __future__ import annotations

import csv
import io
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final

try:
    from sklearn.dummy import DummyRegressor
    from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
    from sklearn.inspection import permutation_importance
    from sklearn.linear_model import ElasticNet, Ridge
    from sklearn.model_selection import GridSearchCV, GroupKFold
    from sklearn.multioutput import MultiOutputRegressor
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
except ImportError as exc:  # pragma: no cover - depende del entorno
    raise ImportError(
        "nutrigraphdt.models.baselines requiere scikit-learn; instale el extra con "
        '`pip install -e ".[baselines]"`.'
    ) from exc

from nutrigraphdt.data.split import create_split
from nutrigraphdt.data.synthetic import (
    SyntheticDataset,
    SyntheticEdgeConfig,
    SyntheticNodeConfig,
    generate_synthetic_dataset,
)
from nutrigraphdt.models.metrics import (
    EvaluationReport,
    MetricRow,
    combine_reports,
    evaluate_predictions,
)
from nutrigraphdt.models.tabular import TabularDataset, build_tabular_dataset

LINEAR_BASELINE_NAMES: Final[tuple[str, ...]] = ("dummy_mean", "ridge", "elasticnet")
TREE_BASELINE_NAMES: Final[tuple[str, ...]] = ("random_forest", "hist_gradient_boosting")
ALL_BASELINE_NAMES: Final[tuple[str, ...]] = LINEAR_BASELINE_NAMES + TREE_BASELINE_NAMES
EVALUATION_SPLITS: Final[tuple[str, ...]] = ("val", "test")
IMPORTANCE_SPLIT: Final[str] = "val"
"""Subconjunto de la importancia por permutación: no participa en el ajuste y deja `test` intacto
para la comparación final."""

SYNTHETIC_COHORT_ID: Final[str] = "synthetic_baseline_cohort"

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

_TREE_CONFIG_KEYS: Final[frozenset[str]] = frozenset(
    {
        "random_forest_n_estimators",
        "random_forest_max_depth",
        "random_forest_min_samples_leaf",
        "hist_gradient_boosting_learning_rate",
        "hist_gradient_boosting_max_iter",
        "hist_gradient_boosting_max_depth",
        "hist_gradient_boosting_min_samples_leaf",
        "cv_folds",
        "scoring",
        "random_state",
        "permutation_repeats",
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
        _check_cv(self.cv_folds, self.scoring)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LinearBaselineConfig:
        """Construye la configuración rechazando claves faltantes o desconocidas."""
        _check_keys(data, _CONFIG_KEYS)
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
        return cls.from_dict(_read_json_object(path))

    def to_dict(self) -> dict[str, Any]:
        """Configuración efectiva, para registrarla junto a los resultados."""
        return _config_to_dict(self)


@dataclass(frozen=True)
class TreeBaselineConfig:
    """Grilla, validación cruzada e importancia por permutación de los baselines de árboles.

    En las grillas de profundidad, `None` significa profundidad sin límite.
    """

    random_forest_n_estimators: tuple[int, ...]
    random_forest_max_depth: tuple[int | None, ...]
    random_forest_min_samples_leaf: tuple[int, ...]
    hist_gradient_boosting_learning_rate: tuple[float, ...]
    hist_gradient_boosting_max_iter: tuple[int, ...]
    hist_gradient_boosting_max_depth: tuple[int | None, ...]
    hist_gradient_boosting_min_samples_leaf: tuple[int, ...]
    cv_folds: int
    scoring: str
    random_state: int
    permutation_repeats: int

    def __post_init__(self) -> None:
        for name in (
            "random_forest_n_estimators",
            "random_forest_min_samples_leaf",
            "hist_gradient_boosting_max_iter",
            "hist_gradient_boosting_min_samples_leaf",
            "random_forest_max_depth",
            "hist_gradient_boosting_max_depth",
        ):
            values = getattr(self, name)
            allow_none = name.endswith("max_depth")
            if not values:
                raise ValueError(f"{name} debe tener al menos un valor.")
            if not all(_is_positive_int(v) or (allow_none and v is None) for v in values):
                raise ValueError(f"{name} solo admite enteros >= 1: {values}.")
        rates = self.hist_gradient_boosting_learning_rate
        if not rates or not all(_is_finite_number(v) and v > 0 for v in rates):
            raise ValueError(
                f"hist_gradient_boosting_learning_rate solo admite números positivos: {rates}."
            )
        _check_cv(self.cv_folds, self.scoring)
        if isinstance(self.random_state, bool) or not isinstance(self.random_state, int):
            raise ValueError(f"random_state debe ser un entero: {self.random_state!r}.")
        if not _is_positive_int(self.permutation_repeats):
            raise ValueError(f"permutation_repeats debe ser >= 1: {self.permutation_repeats}.")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TreeBaselineConfig:
        """Construye la configuración rechazando claves faltantes o desconocidas."""
        _check_keys(data, _TREE_CONFIG_KEYS)
        return cls(
            random_forest_n_estimators=_int_tuple(data, "random_forest_n_estimators"),
            random_forest_max_depth=_depth_tuple(data, "random_forest_max_depth"),
            random_forest_min_samples_leaf=_int_tuple(data, "random_forest_min_samples_leaf"),
            hist_gradient_boosting_learning_rate=_float_tuple(
                data, "hist_gradient_boosting_learning_rate"
            ),
            hist_gradient_boosting_max_iter=_int_tuple(data, "hist_gradient_boosting_max_iter"),
            hist_gradient_boosting_max_depth=_depth_tuple(data, "hist_gradient_boosting_max_depth"),
            hist_gradient_boosting_min_samples_leaf=_int_tuple(
                data, "hist_gradient_boosting_min_samples_leaf"
            ),
            cv_folds=_int_value(data, "cv_folds"),
            scoring=str(data["scoring"]),
            random_state=_int_value(data, "random_state"),
            permutation_repeats=_int_value(data, "permutation_repeats"),
        )

    @classmethod
    def load(cls, path: str | Path) -> TreeBaselineConfig:
        """Lee la configuración desde un JSON (por ejemplo `configs/baselines/trees.json`)."""
        return cls.from_dict(_read_json_object(path))

    def to_dict(self) -> dict[str, Any]:
        """Configuración efectiva, para registrarla junto a los resultados."""
        return _config_to_dict(self)


@dataclass(frozen=True)
class FeatureImportance:
    """Importancia por permutación de un atributo: caída media del puntaje al permutarlo."""

    feature: str
    importance_mean: float
    importance_std: float


@dataclass(frozen=True)
class BaselineResult:
    """Métricas de `val` y `test` y los hiperparámetros elegidos por la validación cruzada.

    `feature_importances` solo se llena para los baselines de árboles.
    """

    report: EvaluationReport
    best_params: dict[str, dict[str, Any]]
    feature_names: tuple[str, ...]
    subset_sizes: dict[str, int]
    cv_folds: int
    feature_importances: dict[str, tuple[FeatureImportance, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class BaselineData:
    """Matrices validadas de `train`, `val` y `test` y los grupos de la validación cruzada."""

    feature_names: tuple[str, ...]
    target_names: tuple[str, ...]
    matrices: dict[str, tuple[list[list[float]], list[list[float]]]]
    train_groups: list[str]


def prepare_baseline_data(
    dataset: TabularDataset,
    groups: Mapping[str, str],
    cv_folds: int,
) -> BaselineData:
    """Extrae y valida las matrices numéricas y los grupos de la validación cruzada.

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
    if n_groups < cv_folds:
        raise ValueError(
            f"train tiene {n_groups} grupos y la configuración pide {cv_folds} folds; "
            "reduzca cv_folds o use más grupos."
        )
    return BaselineData(
        feature_names=feature_names,
        target_names=dataset.target_names,
        matrices=matrices,
        train_groups=train_groups,
    )


def fit_and_evaluate(
    estimators: Mapping[str, Any],
    data: BaselineData,
) -> tuple[EvaluationReport, dict[str, dict[str, Any]], dict[str, Any]]:
    """Ajusta cada estimador con `train` y lo evalúa en `val` y `test`.

    Un `GridSearchCV` se ajusta con los grupos de `data`; los demás estimadores, directamente.
    Devuelve el reporte, los hiperparámetros elegidos y los estimadores ajustados.
    """
    X_train, y_train = data.matrices["train"]
    reports: list[EvaluationReport] = []
    best_params: dict[str, dict[str, Any]] = {}
    for name, estimator in estimators.items():
        if isinstance(estimator, GridSearchCV):
            estimator.fit(X_train, y_train, groups=data.train_groups)
            best_params[name] = dict(estimator.best_params_)
        else:
            estimator.fit(X_train, y_train)
            best_params[name] = {}
        for subset in EVALUATION_SPLITS:
            X_eval, y_eval = data.matrices[subset]
            reports.append(
                evaluate_predictions(
                    y_eval,
                    estimator.predict(X_eval).tolist(),
                    model_name=name,
                    targets=data.target_names,
                    split=subset,
                )
            )
    return combine_reports(reports), best_params, dict(estimators)


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


def build_tree_baselines(config: TreeBaselineConfig) -> dict[str, GridSearchCV]:
    """`GridSearchCV` con `GroupKFold` sin entrenar, en el orden de `TREE_BASELINE_NAMES`.

    Los árboles no necesitan escalado. `HistGradientBoostingRegressor` predice un solo objetivo,
    así que `MultiOutputRegressor` entrena una copia por AGCC con los mismos hiperparámetros.
    """
    cv = GroupKFold(n_splits=config.cv_folds)
    forest = RandomForestRegressor(random_state=config.random_state)
    boosting = MultiOutputRegressor(HistGradientBoostingRegressor(random_state=config.random_state))
    return {
        "random_forest": GridSearchCV(
            forest,
            {
                "n_estimators": list(config.random_forest_n_estimators),
                "max_depth": list(config.random_forest_max_depth),
                "min_samples_leaf": list(config.random_forest_min_samples_leaf),
            },
            cv=cv,
            scoring=config.scoring,
            error_score="raise",
        ),
        "hist_gradient_boosting": GridSearchCV(
            boosting,
            {
                "estimator__learning_rate": list(config.hist_gradient_boosting_learning_rate),
                "estimator__max_iter": list(config.hist_gradient_boosting_max_iter),
                "estimator__max_depth": list(config.hist_gradient_boosting_max_depth),
                "estimator__min_samples_leaf": list(config.hist_gradient_boosting_min_samples_leaf),
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
    """Entrena los baselines trivial y lineales con `train` y los evalúa en `val` y `test`.

    Args:
        dataset: Tabla de A40-3 con la partición de A40-1 aplicada.
        groups: Grupo de validación cruzada de cada `sample_id` de `train` (la unidad de la
            partición: corral en D1, animal en el sintético).
        config: Grilla y número de folds.

    Raises:
        ValueError: en los casos de `prepare_baseline_data`.
    """
    data = prepare_baseline_data(dataset, groups, config.cv_folds)
    report, best_params, _ = fit_and_evaluate(build_linear_baselines(config), data)
    return BaselineResult(
        report=report,
        best_params=best_params,
        feature_names=data.feature_names,
        subset_sizes={subset: len(X) for subset, (X, _) in data.matrices.items()},
        cv_folds=config.cv_folds,
    )


def train_tree_baselines(
    dataset: TabularDataset,
    groups: Mapping[str, str],
    config: TreeBaselineConfig,
) -> BaselineResult:
    """Entrena los baselines de árboles, los evalúa y calcula su importancia de atributos.

    La importancia es por permutación sobre `IMPORTANCE_SPLIT`, con `config.scoring` (el mismo
    criterio de la selección) y `config.permutation_repeats` permutaciones por atributo. Mide
    cuánto empeora el puntaje promedio de los tres AGCC al romper cada atributo; no es causal.

    Args:
        dataset: Tabla de A40-3 con la partición de A40-1 aplicada.
        groups: Grupo de validación cruzada de cada `sample_id` de `train`.
        config: Grillas, folds, semilla y repeticiones de la permutación.

    Raises:
        ValueError: en los casos de `prepare_baseline_data`.
    """
    data = prepare_baseline_data(dataset, groups, config.cv_folds)
    report, best_params, fitted = fit_and_evaluate(build_tree_baselines(config), data)

    X_eval, y_eval = data.matrices[IMPORTANCE_SPLIT]
    importances: dict[str, tuple[FeatureImportance, ...]] = {}
    for name, search in fitted.items():
        result = permutation_importance(
            search.best_estimator_,
            X_eval,
            y_eval,
            scoring=config.scoring,
            n_repeats=config.permutation_repeats,
            random_state=config.random_state,
        )
        importances[name] = tuple(
            FeatureImportance(
                feature=feature, importance_mean=float(mean), importance_std=float(std)
            )
            for feature, mean, std in zip(
                data.feature_names, result.importances_mean, result.importances_std, strict=True
            )
        )

    return BaselineResult(
        report=report,
        best_params=best_params,
        feature_names=data.feature_names,
        subset_sizes={subset: len(X) for subset, (X, _) in data.matrices.items()},
        cv_folds=config.cv_folds,
        feature_importances=importances,
    )


@dataclass(frozen=True)
class BaselineComparisonRow:
    """Fila consolidada de comparación de baselines para un modelo y partición."""

    model: str
    split: str
    mae: float
    rmse: float
    r2: float
    negative_pct: float
    targets_mae: dict[str, float]
    targets_rmse: dict[str, float]
    targets_r2: dict[str, float]
    targets_negative_pct: dict[str, float]


def build_comparison_summary(report: EvaluationReport) -> list[BaselineComparisonRow]:
    """Construye un resumen comparativo agrupado por modelo y split desde un `EvaluationReport`."""
    grouped: dict[tuple[str, str], dict[str, MetricRow]] = {}
    for row in report.rows:
        split_key = row.split if row.split is not None else ""
        key = (row.model, split_key)
        if key not in grouped:
            grouped[key] = {}
        grouped[key][row.metric] = row

    summary: list[BaselineComparisonRow] = []
    for (model, split), metrics in grouped.items():
        mae_row = metrics.get("mae")
        rmse_row = metrics.get("rmse")
        r2_row = metrics.get("r2")
        neg_row = metrics.get("negative_pct")

        if not (mae_row and rmse_row and r2_row and neg_row):
            continue

        summary.append(
            BaselineComparisonRow(
                model=model,
                split=split,
                mae=mae_row.average,
                rmse=rmse_row.average,
                r2=r2_row.average,
                negative_pct=neg_row.average,
                targets_mae=dict(mae_row.targets),
                targets_rmse=dict(rmse_row.targets),
                targets_r2=dict(r2_row.targets),
                targets_negative_pct=dict(neg_row.targets),
            )
        )
    return summary


def format_comparison_table_markdown(
    report: EvaluationReport,
    include_targets: bool = True,
) -> str:
    """Genera la tabla comparativa consolidada en formato Markdown."""
    summary = build_comparison_summary(report)
    lines: list[str] = [
        "### Promedio macro de los tres AGCC (acetato, propionato, butirato)",
        "",
        "| Modelo | Split | MAE | RMSE | R² | % Neg |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            f"| `{row.model}` | {row.split} | {row.mae:.4f} | {row.rmse:.4f} | "
            f"{row.r2:.4f} | {row.negative_pct:.1f}% |"
        )

    if include_targets and summary:
        targets = list(summary[0].targets_mae.keys())
        for target in targets:
            lines.extend(
                [
                    "",
                    f"### Detalle por objetivo: {target.capitalize()}",
                    "",
                    "| Modelo | Split | MAE | RMSE | R² | % Neg |",
                    "|---|---|---:|---:|---:|---:|",
                ]
            )
            for row in summary:
                t_mae = row.targets_mae.get(target, float("nan"))
                t_rmse = row.targets_rmse.get(target, float("nan"))
                t_r2 = row.targets_r2.get(target, float("nan"))
                t_neg = row.targets_negative_pct.get(target, float("nan"))
                lines.append(
                    f"| `{row.model}` | {row.split} | {t_mae:.4f} | {t_rmse:.4f} | "
                    f"{t_r2:.4f} | {t_neg:.1f}% |"
                )

    return "\n".join(lines)


def format_comparison_table_csv(report: EvaluationReport) -> str:
    """Genera la tabla comparativa consolidada en formato CSV."""
    summary = build_comparison_summary(report)
    if not summary:
        return ""

    targets = list(summary[0].targets_mae.keys())
    output = io.StringIO()
    writer = csv.writer(output)

    header = ["model", "split", "mae", "rmse", "r2", "negative_pct"]
    for t in targets:
        header.extend([f"mae_{t}", f"rmse_{t}", f"r2_{t}", f"negative_pct_{t}"])
    writer.writerow(header)

    for row in summary:
        line: list[Any] = [
            row.model,
            row.split,
            f"{row.mae:.6f}",
            f"{row.rmse:.6f}",
            f"{row.r2:.6f}",
            f"{row.negative_pct:.4f}",
        ]
        for t in targets:
            line.extend(
                [
                    f"{row.targets_mae.get(t, float('nan')):.6f}",
                    f"{row.targets_rmse.get(t, float('nan')):.6f}",
                    f"{row.targets_r2.get(t, float('nan')):.6f}",
                    f"{row.targets_negative_pct.get(t, float('nan')):.4f}",
                ]
            )
        writer.writerow(line)

    return output.getvalue()


def train_all_baselines(
    dataset: TabularDataset,
    groups: Mapping[str, str],
    linear_config: LinearBaselineConfig | None = None,
    tree_config: TreeBaselineConfig | None = None,
) -> BaselineResult:
    """Entrena y evalúa todos los baselines (lineales y de árboles) de NutriGraphDT (A40-6).

    Args:
        dataset: Tabla de A40-3 con la partición de A40-1 aplicada.
        groups: Grupo de validación cruzada de cada `sample_id` de `train`.
        linear_config: Configuración lineal (por defecto configs/baselines/linear.json).
        tree_config: Configuración de árboles (por defecto configs/baselines/trees.json).

    Returns:
        BaselineResult con el reporte combinado de los 5 modelos, mejores parámetros,
        tamaños de partición e importancia de atributos de los árboles.

    Raises:
        ValueError: Si los folds de validación cruzada no coinciden o ante errores de datos.
    """
    lin_cfg = linear_config or LinearBaselineConfig.load(_default_linear_config_path())
    tr_cfg = tree_config or TreeBaselineConfig.load(_default_tree_config_path())

    if lin_cfg.cv_folds != tr_cfg.cv_folds:
        raise ValueError(
            f"cv_folds debe coincidir entre linear ({lin_cfg.cv_folds}) "
            f"y trees ({tr_cfg.cv_folds})."
        )

    linear_result = train_linear_baselines(dataset, groups, lin_cfg)
    tree_result = train_tree_baselines(dataset, groups, tr_cfg)

    combined_report = combine_reports([linear_result.report, tree_result.report])
    combined_params = {**linear_result.best_params, **tree_result.best_params}

    return BaselineResult(
        report=combined_report,
        best_params=combined_params,
        feature_names=linear_result.feature_names,
        subset_sizes=linear_result.subset_sizes,
        cv_folds=lin_cfg.cv_folds,
        feature_importances=tree_result.feature_importances,
    )


def build_synthetic_cohort(n_samples: int, first_seed: int) -> SyntheticDataset:
    """Une `n_samples` instancias sintéticas de semillas consecutivas en un solo dataset.

    El generador produce una instancia por semilla; cada una es un animal distinto.
    Copia los metadatos de `parts[0].metadata` (como `node_feature_schema`), asumiendo que
    el esquema de atributos nodales es uniforme entre todas las semillas generadas.
    """
    if n_samples < 1:
        raise ValueError(f"n_samples debe ser >= 1: {n_samples}.")
    parts = [
        generate_synthetic_dataset(
            SyntheticNodeConfig(graph_id=f"synthetic:graph:{seed:04d}", random_seed=seed),
            SyntheticEdgeConfig(random_seed=seed),
        )
        for seed in range(first_seed, first_seed + n_samples)
    ]
    counts = {gid: c for part in parts for gid, c in part.metadata.get("counts", {}).items()}
    metadata = {
        **parts[0].metadata,
        "dataset_id": SYNTHETIC_COHORT_ID,
        "counts": counts,
    }
    return SyntheticDataset(
        metadata=metadata,
        instances=[inst for part in parts for inst in part.instances],
        nodes=[node for part in parts for node in part.nodes],
        edges=[edge for part in parts for edge in part.edges],
        outputs=[out for part in parts for out in part.outputs],
    )


def build_synthetic_baseline_dataset(
    n_samples: int,
    first_seed: int,
    split_seed: int,
) -> tuple[TabularDataset, dict[str, str]]:
    """Tabla de la cohorte sintética con su partición y sus grupos de validación cruzada.

    El generador no define corrales, así que el grupo de la partición (`create_split`, A40-1)
    y de la validación cruzada es el propio `sample_id`.
    """
    cohort = build_synthetic_cohort(n_samples, first_seed)
    split = create_split(
        [
            {"sample_id": inst.sample_id, "diet_treatment": inst.diet_treatment}
            for inst in cohort.instances
        ],
        group_key=None,
        stratify_key="diet_treatment",
        seed=split_seed,
        dataset_id=SYNTHETIC_COHORT_ID,
    )
    dataset = build_tabular_dataset(cohort, split=split)
    return dataset, {sample_id: sample_id for sample_id in dataset.sample_ids}


def _check_keys(data: Mapping[str, Any], expected: frozenset[str]) -> None:
    missing = expected - data.keys()
    unknown = data.keys() - expected
    if missing or unknown:
        raise ValueError(
            "Configuración de baselines inválida: "
            f"faltan {sorted(missing)}, desconocidas {sorted(unknown)}."
        )


def _check_cv(cv_folds: int, scoring: str) -> None:
    if isinstance(cv_folds, bool) or cv_folds < 2:
        raise ValueError(f"cv_folds debe ser >= 2 (GroupKFold): {cv_folds}.")
    if not scoring:
        raise ValueError("scoring no puede estar vacío.")


def _find_repo_root() -> Path:
    """Encuentra la raíz del repositorio de manera robusta."""
    file_root = Path(__file__).resolve().parents[3]
    if (file_root / "pyproject.toml").exists() or (file_root / "configs").exists():
        return file_root
    cwd = Path.cwd()
    if (cwd / "pyproject.toml").exists() or (cwd / "configs").exists():
        return cwd
    for parent in cwd.parents:
        if (parent / "pyproject.toml").exists() or (parent / "configs").exists():
            return parent
    return file_root


def _default_linear_config_path() -> Path:
    return _find_repo_root() / "configs" / "baselines" / "linear.json"


def _default_tree_config_path() -> Path:
    return _find_repo_root() / "configs" / "baselines" / "trees.json"


def _read_json_object(path: str | Path) -> Mapping[str, Any]:
    content = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(content, Mapping):
        raise ValueError(f"{path}: se esperaba un objeto JSON.")
    return content


def _config_to_dict(config: LinearBaselineConfig | TreeBaselineConfig) -> dict[str, Any]:
    return {key: list(v) if isinstance(v, tuple) else v for key, v in asdict(config).items()}


def _is_finite_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _sequence(data: Mapping[str, Any], key: str) -> Sequence[Any]:
    values = data[key]
    if not isinstance(values, Sequence) or isinstance(values, str):
        raise ValueError(f"{key} debe ser una lista.")
    return values


def _float_tuple(data: Mapping[str, Any], key: str) -> tuple[float, ...]:
    values = _sequence(data, key)
    if not all(_is_finite_number(v) for v in values):
        raise ValueError(f"{key} solo admite números finitos: {values}.")
    return tuple(float(v) for v in values)


def _int_tuple(data: Mapping[str, Any], key: str) -> tuple[int, ...]:
    values = _sequence(data, key)
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in values):
        raise ValueError(f"{key} solo admite enteros: {values}.")
    return tuple(values)


def _depth_tuple(data: Mapping[str, Any], key: str) -> tuple[int | None, ...]:
    values = _sequence(data, key)
    if not all(v is None or (isinstance(v, int) and not isinstance(v, bool)) for v in values):
        raise ValueError(f"{key} solo admite enteros o null: {values}.")
    return tuple(values)


def _int_value(data: Mapping[str, Any], key: str) -> int:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} debe ser un entero: {value!r}.")
    return value
