"""Baselines tabulares de D1 con el objetivo composicional y validación cruzada por corral (#140).

Repite los baselines de A45-2 (`nutrigraphdt.models.baselines`) con el objetivo composicional
de D-03 —`(z_1, z_2, ln T)` de `nutrigraphdt.models.composition` (#146)— bajo la validación
cruzada por corral de D-07 (#139), y agrega dos baselines de referencia que piden la respuesta
de Investigación del 16-10-2026 (sección 4.7) y su Tabla 5:

- `day_only`: solo el día de muestreo como entrada. Predice, para cada salida, la media de
  entrenamiento del día del animal (la media global si el día no aparece en el entrenamiento).
  Sin un baseline así no se puede saber si un modelo aprende algo más que la edad del animal:
  el día aporta 25 de los 47 puntos de R² del diseño en log(propionato/acetato) (D-03).
- `ridge_design`: ridge sobre los **factores del diseño** del ensayo (`diet:treatment` y las
  covariables de entrada del huésped `host:trial_code`, `host:sampling_day`, `host:sex` y
  `host:breed`, en one-hot). Es el modelo de la Tabla 5 de la respuesta de Investigación y
  acota lo que explica el diseño sin usar el microbioma.

El resto de los modelos son los de A45-2 (`dummy_mean`, `ridge`, `elasticnet`, `random_forest`,
`hist_gradient_boosting`) sobre la tabla de atributos completa (A40-3, #147 incluidas las
covariables del huésped), con las mismas grillas de `configs/baselines/`.

Protocolo: por cada fold del plan versionado (`PenFoldPlan`), todo lo que se ajusta a los datos
—escalado, selección de hiperparámetros y modelo— se ajusta solo con los animales de
entrenamiento del fold; la selección usa un `GroupKFold` interno agrupado por corral. Las
métricas son las de D-03 (`evaluate_composition`), globales y por día de muestreo, agregadas
entre folds y semillas con `aggregate_fold_reports`. La columna `split` de las filas vale `cv`:
es la predicción **fuera de fold**, sin relación con la partición fija de A45-1.

Ninguna log-razón admite ceros (contrato v2, sección 1): `prepare_compositional_data` rechaza
la tabla si algún animal queda sin objetivo composicional válido, en lugar de inventar un
pseudoconteo. En la cohorte oficial no hay ceros (VR-3 de la respuesta del 25-10-2026).

Requiere el extra `baselines` (scikit-learn).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

try:
    from sklearn.dummy import DummyRegressor
    from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
    from sklearn.linear_model import ElasticNet, Ridge
    from sklearn.model_selection import GridSearchCV, GroupKFold
    from sklearn.multioutput import MultiOutputRegressor
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
except ImportError as exc:  # pragma: no cover - depende del entorno
    raise ImportError(
        "nutrigraphdt.models.compositional_baselines requiere scikit-learn; instale el extra "
        'con `pip install -e ".[baselines]"`.'
    ) from exc

from nutrigraphdt.models.baselines import LinearBaselineConfig, TreeBaselineConfig
from nutrigraphdt.models.composition import (
    ALL_DAYS,
    MODEL_OUTPUT_NAMES,
    compositional_target,
    evaluate_composition,
)
from nutrigraphdt.models.cross_validation import (
    CrossValidationError,
    CrossValidationResult,
    FoldRunner,
    PenFoldPlan,
    aggregate_fold_reports,
    run_cross_validation,
)
from nutrigraphdt.models.metrics import EvaluationReport, MetricRow, combine_reports
from nutrigraphdt.models.tabular import CANONICAL_TARGETS, TabularDataset

DAY_ONLY_NAME: Final[str] = "day_only"
DESIGN_RIDGE_NAME: Final[str] = "ridge_design"
MODEL_NAMES: Final[tuple[str, ...]] = (
    "dummy_mean",
    DAY_ONLY_NAME,
    DESIGN_RIDGE_NAME,
    "ridge",
    "elasticnet",
    "random_forest",
    "hist_gradient_boosting",
)
"""Los cinco baselines de A45-2 más `day_only` y `ridge_design`, en el orden del reporte."""

DAY_FEATURE: Final[str] = "host:sampling_day"
"""Columna de la tabla de atributos con el día de muestreo (entrada de `day_only`)."""

DESIGN_FEATURE_BASES: Final[tuple[str, ...]] = (
    "diet:treatment",
    "host:trial_code",
    DAY_FEATURE,
    "host:sex",
    "host:breed",
)
"""Factores del diseño del ensayo: dieta, ensayo, día, sexo y raza (Tabla 5 de Investigación)."""

CV_SPLIT: Final[str] = "cv"
"""Etiqueta de `split` de las filas: predicción fuera de fold de la validación cruzada."""

DEFAULT_INNER_FOLDS: Final[int] = 5
"""Folds del `GroupKFold` interno (por corral) que elige hiperparámetros dentro de cada fold."""

INVESTIGATION_TABLE5: Final[Mapping[str, Mapping[str, float]]] = {
    "reconstructed_r2": {"acetate": -0.34, "propionate": 0.54, "butyrate": 0.14, "average": 0.11},
    "fraction_r2": {"acetate": 0.32, "propionate": 0.40, "butyrate": 0.10, "average": 0.27},
    "log_total_r2": {"log_total": -0.14},
}
"""R² fuera de fold del ridge de Investigación sobre los factores del diseño: columna «Cohorte
(59)» de la Tabla 5 de la respuesta del 16-10-2026 (cantidad ↔ `reconstructed_r2`, fracción ↔
`fraction_r2`, total ↔ `log_total_r2`). La cohorte oficial es de 56 animales (R-04), así que la
igualdad exacta no es esperable; el reporte documenta las diferencias."""


class CompositionalBaselineError(ValueError):
    """La tabla de atributos no cumple las condiciones del objetivo composicional."""


class DayMeanRegressor:
    """Predice la media de entrenamiento de cada salida dentro de cada día de muestreo.

    Un día que no aparece en el entrenamiento recibe la media global de entrenamiento. No tiene
    hiperparámetros: es el piso que fija la edad del animal (sección 4.7 de la respuesta del
    16-10-2026).
    """

    def __init__(self) -> None:
        self._by_day: dict[str, list[float]] = {}
        self._global: list[float] = []

    def fit(self, days: Sequence[str], y: Sequence[Sequence[float]]) -> DayMeanRegressor:
        if len(days) != len(y) or not days:
            raise CompositionalBaselineError(
                f"day_only: {len(days)} días para {len(y)} filas de objetivo."
            )
        sums: dict[str, list[float]] = {}
        counts: dict[str, int] = {}
        totals: list[float] = []
        for day, row in zip(days, y, strict=True):
            values = [float(v) for v in row]
            if not totals:
                totals = [0.0] * len(values)
            if len(values) != len(totals):
                raise CompositionalBaselineError("day_only: filas de objetivo de ancho distinto.")
            if day not in sums:
                sums[day] = [0.0] * len(values)
                counts[day] = 0
            counts[day] += 1
            for j, value in enumerate(values):
                sums[day][j] += value
                totals[j] += value
        self._by_day = {day: [s / counts[day] for s in column] for day, column in sums.items()}
        self._global = [total / len(days) for total in totals]
        return self

    def predict(self, days: Sequence[str]) -> list[list[float]]:
        if not self._global:
            raise CompositionalBaselineError("day_only: el modelo no está ajustado.")
        return [list(self._by_day.get(day, self._global)) for day in days]


@dataclass(frozen=True)
class CompositionalBaselineData:
    """Matrices y objetivo composicional de la cohorte, listas para los folds.

    `matrix` es la tabla numérica completa (taxones, dieta y covariables del huésped, con las
    categóricas en one-hot) y `design_matrix` solo las columnas de los factores del diseño.
    `outputs` es `(z_1, z_2, ln T)` en el orden de `MODEL_OUTPUT_NAMES`.
    """

    sample_ids: tuple[str, ...]
    pens: tuple[str, ...]
    days: tuple[str, ...]
    concentrations: tuple[tuple[float, float, float], ...]
    outputs: tuple[tuple[float, float, float], ...]
    feature_names: tuple[str, ...]
    matrix: list[list[float]]
    design_names: tuple[str, ...]
    design_matrix: list[list[float]]


def design_column_indices(feature_names: Sequence[str]) -> list[int]:
    """Índices de las columnas de los factores del diseño en la matriz numérica.

    Las categóricas llegan ya expandidas (`<base>=<categoría>`), así que se compara el nombre
    base con `DESIGN_FEATURE_BASES`.
    """
    indices = [
        i for i, name in enumerate(feature_names) if name.split("=", 1)[0] in DESIGN_FEATURE_BASES
    ]
    if not indices:
        raise CompositionalBaselineError(
            "La matriz numérica no tiene columnas de los factores del diseño "
            f"{DESIGN_FEATURE_BASES}."
        )
    return indices


def prepare_compositional_data(
    dataset: TabularDataset, pens: Mapping[str, str]
) -> CompositionalBaselineData:
    """Valida la tabla de la cohorte y deriva el objetivo composicional de cada animal.

    Args:
        dataset: tabla de atributos (A40-3) ya limitada a la cohorte y con los tres AGCC
            completos, con `host:sampling_day` entre los atributos.
        pens: corral (`pen_code`) de cada `sample_id`; agrupa la selección interna de
            hiperparámetros.

    Raises:
        CompositionalBaselineError: si falta el corral o el día de algún animal, si falta la
            columna del día, o si algún animal queda sin objetivo composicional válido (AGCC
            ausente, no finito o igual a cero). No se inventa ningún pseudoconteo.
    """
    if not dataset.samples:
        raise CompositionalBaselineError("La tabla de atributos está vacía.")
    if tuple(dataset.target_names) != CANONICAL_TARGETS:
        raise CompositionalBaselineError(
            f"Los objetivos deben ser {CANONICAL_TARGETS}; son {dataset.target_names}."
        )

    missing_pens = [s.sample_id for s in dataset.samples if s.sample_id not in pens]
    if missing_pens:
        raise CompositionalBaselineError(f"Falta el corral de: {missing_pens}.")
    missing_days = [
        s.sample_id for s in dataset.samples if s.features.get(DAY_FEATURE) in (None, "")
    ]
    if missing_days:
        raise CompositionalBaselineError(
            f"Falta `{DAY_FEATURE}` en la tabla de atributos de: {missing_days}."
        )

    concentrations: list[tuple[float, float, float]] = []
    outputs: list[tuple[float, float, float]] = []
    invalid: list[str] = []
    for sample in dataset.samples:
        row = tuple(float(sample.targets[name]) for name in CANONICAL_TARGETS)
        target = compositional_target(*row)
        if not target.valid:
            invalid.append(sample.sample_id)
            continue
        concentrations.append((row[0], row[1], row[2]))
        outputs.append(target.model_output)
    if invalid:
        raise CompositionalBaselineError(
            "Animales sin objetivo composicional válido (AGCC ausente, no finito o igual a "
            f"cero): {invalid}. Una log-razón no admite ceros y el contrato v2 (sección 1) "
            "prohíbe el pseudoconteo; documéntelo y excluya al animal antes de correr los "
            "baselines."
        )

    feature_names, matrix = dataset.to_numeric_matrix()
    indices = design_column_indices(feature_names)
    design_names = tuple(feature_names[i] for i in indices)
    design_matrix = [[row[i] for i in indices] for row in matrix]
    return CompositionalBaselineData(
        sample_ids=dataset.sample_ids,
        pens=tuple(pens[s.sample_id] for s in dataset.samples),
        days=tuple(str(s.features[DAY_FEATURE]) for s in dataset.samples),
        concentrations=tuple(concentrations),
        outputs=tuple(outputs),
        feature_names=feature_names,
        matrix=matrix,
        design_names=design_names,
        design_matrix=design_matrix,
    )


@dataclass(frozen=True)
class FoldSelection:
    """Hiperparámetros elegidos por la selección interna de un fold, por modelo."""

    seed: int
    fold: int
    model: str
    params: dict[str, Any]
    inner_folds: int


@dataclass(frozen=True)
class CompositionalCVResult:
    """Resultado de los baselines composicionales: CV por fold, agregado y selecciones."""

    cv: CrossValidationResult
    selections: tuple[FoldSelection, ...]
    n_features: int
    design_features: tuple[str, ...]
    inner_folds: int

    @property
    def aggregate(self) -> EvaluationReport:
        return self.cv.aggregate


def _grid_search(
    estimator: Any, grid: Mapping[str, Any], config_scoring: str, inner_folds: int
) -> Any:
    return GridSearchCV(
        estimator,
        {key: list(values) for key, values in grid.items()},
        cv=GroupKFold(n_splits=inner_folds),
        scoring=config_scoring,
        error_score="raise",
    )


def _build_fold_estimators(
    linear_config: LinearBaselineConfig, tree_config: TreeBaselineConfig, inner_folds: int
) -> dict[str, Any]:
    """Estimadores sin entrenar de un fold; los `GridSearchCV` se ajustan con `groups`."""
    ridge = Pipeline([("scale", StandardScaler()), ("model", Ridge())])
    elasticnet = Pipeline(
        [
            ("scale", StandardScaler()),
            ("model", ElasticNet(max_iter=linear_config.elasticnet_max_iter)),
        ]
    )
    return {
        DESIGN_RIDGE_NAME: _grid_search(
            ridge, {"model__alpha": linear_config.ridge_alphas}, linear_config.scoring, inner_folds
        ),
        "ridge": _grid_search(
            ridge, {"model__alpha": linear_config.ridge_alphas}, linear_config.scoring, inner_folds
        ),
        "elasticnet": _grid_search(
            elasticnet,
            {
                "model__alpha": linear_config.elasticnet_alphas,
                "model__l1_ratio": linear_config.elasticnet_l1_ratios,
            },
            linear_config.scoring,
            inner_folds,
        ),
        "random_forest": _grid_search(
            RandomForestRegressor(random_state=tree_config.random_state),
            {
                "n_estimators": tree_config.random_forest_n_estimators,
                "max_depth": tree_config.random_forest_max_depth,
                "min_samples_leaf": tree_config.random_forest_min_samples_leaf,
            },
            tree_config.scoring,
            inner_folds,
        ),
        "hist_gradient_boosting": _grid_search(
            MultiOutputRegressor(
                HistGradientBoostingRegressor(random_state=tree_config.random_state)
            ),
            {
                "estimator__learning_rate": tree_config.hist_gradient_boosting_learning_rate,
                "estimator__max_iter": tree_config.hist_gradient_boosting_max_iter,
                "estimator__max_depth": tree_config.hist_gradient_boosting_max_depth,
                "estimator__min_samples_leaf": tree_config.hist_gradient_boosting_min_samples_leaf,
            },
            tree_config.scoring,
            inner_folds,
        ),
    }


def evaluate_fold(
    data: CompositionalBaselineData,
    linear_config: LinearBaselineConfig,
    tree_config: TreeBaselineConfig,
    inner_folds: int,
    seed: int,
    fold: int,
    train: tuple[str, ...],
    test: tuple[str, ...],
) -> tuple[EvaluationReport, list[FoldSelection]]:
    """Entrena los siete modelos en un fold y devuelve sus métricas y selecciones.

    Ajusta todo solo con `train` y evalúa las métricas de D-03 sobre `test` (globales y por
    día). `day_only` y `dummy_mean` no tienen hiperparámetros; el resto elige los suyos con un
    `GroupKFold` interno de `inner_folds` folds agrupado por corral (recortado al número de
    corrales del entrenamiento si es menor). `ridge_design` usa solo las columnas de los
    factores del diseño; `ridge`, `elasticnet`, `random_forest` e `hist_gradient_boosting`
    usan la tabla completa.

    Es una función de módulo y sin estado para poder ejecutarse en procesos paralelos
    (`run_compositional_baselines` con `n_jobs != 1`); el resultado solo depende de los
    argumentos.
    """
    if inner_folds < 2:
        raise CompositionalBaselineError(f"inner_folds debe ser >= 2: {inner_folds}.")
    overlap = set(train) & set(test)
    if overlap:
        raise CrossValidationError(
            f"semilla {seed}, fold {fold}: fuga entre train y test: {sorted(overlap)}"
        )
    index = {sample_id: i for i, sample_id in enumerate(data.sample_ids)}
    train_idx = [index[s] for s in train]
    test_idx = [index[s] for s in test]
    y_train = [data.outputs[i] for i in train_idx]
    days_train = [data.days[i] for i in train_idx]
    days_test = [data.days[i] for i in test_idx]
    pens_train = [data.pens[i] for i in train_idx]
    n_splits = min(inner_folds, len(set(pens_train)))
    if n_splits < 2:
        raise CrossValidationError(
            f"semilla {seed}, fold {fold}: el entrenamiento tiene {len(set(pens_train))} "
            "corrales; la selección interna necesita al menos 2."
        )
    selections: list[FoldSelection] = []

    def evaluate(model: str, predicted: Sequence[Sequence[float]]) -> EvaluationReport:
        return evaluate_composition(
            [data.concentrations[i] for i in test_idx],
            predicted,
            model,
            split=CV_SPLIT,
            sampling_days=days_test,
        )

    reports: list[EvaluationReport] = []

    X_design_train = [data.design_matrix[i] for i in train_idx]
    dummy = DummyRegressor(strategy="mean").fit(X_design_train, y_train)
    reports.append(evaluate("dummy_mean", dummy.predict([data.design_matrix[i] for i in test_idx])))

    day_model = DayMeanRegressor().fit(days_train, y_train)
    reports.append(evaluate(DAY_ONLY_NAME, day_model.predict(days_test)))

    X_full_train = [data.matrix[i] for i in train_idx]
    estimators = _build_fold_estimators(linear_config, tree_config, inner_folds=n_splits)
    for name, estimator in estimators.items():
        X_train = X_design_train if name == DESIGN_RIDGE_NAME else X_full_train
        estimator.fit(X_train, y_train, groups=pens_train)
        X_test = (
            [data.design_matrix[i] for i in test_idx]
            if name == DESIGN_RIDGE_NAME
            else [data.matrix[i] for i in test_idx]
        )
        selections.append(FoldSelection(seed, fold, name, dict(estimator.best_params_), n_splits))
        reports.append(evaluate(name, estimator.predict(X_test).tolist()))

    return combine_reports(reports), selections


def make_fold_runner(
    data: CompositionalBaselineData,
    linear_config: LinearBaselineConfig,
    tree_config: TreeBaselineConfig,
    *,
    inner_folds: int = DEFAULT_INNER_FOLDS,
) -> tuple[FoldRunner, list[FoldSelection]]:
    """`FoldRunner` que entrena los siete modelos del fold y su registro de selecciones.

    Adaptador serial de `evaluate_fold` a la interfaz de `run_cross_validation`.
    """
    selections: list[FoldSelection] = []

    def runner(
        seed: int, fold: int, train: tuple[str, ...], test: tuple[str, ...]
    ) -> EvaluationReport:
        report, fold_selections = evaluate_fold(
            data, linear_config, tree_config, inner_folds, seed, fold, train, test
        )
        selections.extend(fold_selections)
        return report

    return runner, selections


def run_compositional_baselines(
    data: CompositionalBaselineData,
    plan: PenFoldPlan,
    linear_config: LinearBaselineConfig,
    tree_config: TreeBaselineConfig,
    *,
    inner_folds: int = DEFAULT_INNER_FOLDS,
    n_jobs: int = 1,
) -> CompositionalCVResult:
    """Corre los siete baselines en todos los folds del plan y agrega las métricas.

    Con `n_jobs != 1` los folds se evalúan en procesos paralelos con joblib (cada uno con un
    solo hilo interno); el resultado es idéntico al de la ejecución serial, porque cada fold
    es determinista y la agregación se hace sobre el diccionario ordenado de reportes.

    Raises:
        CrossValidationError: si los animales del plan no coinciden con los de `data`.
    """
    missing = sorted(set(plan.sample_ids) - set(data.sample_ids))
    extra = sorted(set(data.sample_ids) - set(plan.sample_ids))
    if missing or extra:
        raise CrossValidationError(
            "Los animales del plan de folds no coinciden con la tabla: "
            f"faltan en la tabla {missing}, sobran {extra}."
        )
    if n_jobs == 1:
        runner, selections_list = make_fold_runner(
            data, linear_config, tree_config, inner_folds=inner_folds
        )
        cv = run_cross_validation(plan, runner)
        selections = selections_list
    else:
        from joblib import Parallel, delayed

        outcomes = Parallel(n_jobs=n_jobs)(
            delayed(evaluate_fold)(
                data, linear_config, tree_config, inner_folds, seed, fold, train, test
            )
            for seed, fold, train, test in plan.iter_folds()
        )
        keys = list(plan.iter_folds())
        reports = {
            (seed, fold): report
            for (seed, fold, _, _), (report, _) in zip(keys, outcomes, strict=True)
        }
        selections = [s for _, fold_selections in outcomes for s in fold_selections]
        cv = CrossValidationResult(
            plan=plan, fold_reports=reports, aggregate=aggregate_fold_reports(reports)
        )
    return CompositionalCVResult(
        cv=cv,
        selections=tuple(selections),
        n_features=len(data.feature_names),
        design_features=data.design_names,
        inner_folds=inner_folds,
    )


def aggregate_rows(
    report: EvaluationReport, model: str, base_metric: str, group: str | None = ALL_DAYS
) -> dict[str, MetricRow]:
    """Filas `<métrica>_<agregado>` de un modelo y grupo, indexadas por agregado.

    `base_metric` es una de `COMPOSITION_METRICS` (por ejemplo `fraction_r2`); las claves del
    resultado son `mean`, `std`, `seed_std` y `n` (las que existan).
    """
    rows: dict[str, MetricRow] = {}
    for row in report.rows:
        if row.model != model or row.group != group:
            continue
        for aggregate in ("mean", "std", "seed_std", "n"):
            if row.metric == f"{base_metric}_{aggregate}":
                rows[aggregate] = row
    return rows


__all__ = [
    "ALL_DAYS",
    "CV_SPLIT",
    "DAY_FEATURE",
    "DAY_ONLY_NAME",
    "DEFAULT_INNER_FOLDS",
    "DESIGN_FEATURE_BASES",
    "DESIGN_RIDGE_NAME",
    "INVESTIGATION_TABLE5",
    "MODEL_NAMES",
    "MODEL_OUTPUT_NAMES",
    "CompositionalBaselineData",
    "CompositionalBaselineError",
    "CompositionalCVResult",
    "DayMeanRegressor",
    "FoldSelection",
    "aggregate_rows",
    "design_column_indices",
    "evaluate_fold",
    "make_fold_runner",
    "prepare_compositional_data",
    "run_compositional_baselines",
]
