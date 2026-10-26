"""Validación cruzada por corral de D1 (D-07; #139).

La respuesta de Investigación del 16-10-2026 (sección 4.7) fija la evaluación principal de D1:
validación cruzada **agrupada por corral** (`pen_code`) y **estratificada por dieta**
(`StratifiedGroupKFold`), con **k = 5** y **al menos 10 semillas**, informando media y
dispersión. Este módulo:

1. genera y versiona la asignación de folds por semilla (`make_pen_folds`, `PenFoldPlan`);
2. la verifica (`check_plan`): todas las dietas en todos los folds de todas las semillas y ningún
   corral en más de un fold de la misma semilla;
3. describe cada fold (`fold_table`): animales, corrales, dietas y días de muestreo, y los folds
   a los que les falta algún día (la dieta está confundida con el día; D-07 lo encontró en 40 de
   100 semillas);
4. ofrece una API común para baselines y GNN (`run_cross_validation`) que entrena y evalúa por
   fold y agrega las métricas (`aggregate_fold_reports`): media, desviación estándar entre todos
   los folds y semillas, y desviación estándar entre las medias por semilla.

`k` no puede superar el número de corrales de la dieta con menos corrales (6 para `CE` en la
cohorte de 56). La implementación usa `sklearn.model_selection.StratifiedGroupKFold` con
`shuffle=True` y `random_state = semilla`, sobre los animales ordenados por `sample_id`; requiere
el extra `baselines`.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from nutrigraphdt.models.metrics import EvaluationReport, MetricRow

CV_FORMAT_VERSION: Final[str] = "1.0.0"
DEFAULT_K: Final[int] = 5
DEFAULT_SEEDS: Final[tuple[int, ...]] = tuple(range(10))
MIN_SEEDS: Final[int] = 10
GROUP_KEY: Final[str] = "pen_code"
STRATIFY_KEY: Final[str] = "diet_treatment_code"
DAY_KEY: Final[str] = "sampling_day"
METHOD: Final[str] = "sklearn.model_selection.StratifiedGroupKFold(shuffle=True)"


class CrossValidationError(ValueError):
    """La cohorte o el plan de folds no cumplen las condiciones de D-07."""


@dataclass(frozen=True)
class CVAnimal:
    """Lo que la partición necesita de un animal."""

    sample_id: str
    pen_code: str
    diet: str
    sampling_day: str | None = None

    @classmethod
    def from_mapping(
        cls,
        record: Mapping[str, Any],
        *,
        group_key: str = GROUP_KEY,
        stratify_key: str = STRATIFY_KEY,
        day_key: str = DAY_KEY,
    ) -> CVAnimal:
        missing = [k for k in ("sample_id", group_key, stratify_key) if not record.get(k)]
        if missing:
            raise CrossValidationError(
                f"Animal {record.get('sample_id')!r} sin {', '.join(missing)}."
            )
        day = record.get(day_key)
        return cls(
            sample_id=str(record["sample_id"]),
            pen_code=str(record[group_key]),
            diet=str(record[stratify_key]),
            sampling_day=None if day in (None, "") else str(day),
        )


def _animals(records: Sequence[CVAnimal | Mapping[str, Any]]) -> list[CVAnimal]:
    animals = [r if isinstance(r, CVAnimal) else CVAnimal.from_mapping(r) for r in records]
    counts = Counter(a.sample_id for a in animals)
    repeated = sorted(s for s, n in counts.items() if n > 1)
    if repeated:
        raise CrossValidationError(f"sample_id repetido: {repeated}.")
    pens: dict[str, set[str]] = defaultdict(set)
    for animal in animals:
        pens[animal.pen_code].add(animal.diet)
    mixed = sorted(p for p, diets in pens.items() if len(diets) > 1)
    if mixed:
        raise CrossValidationError(f"Corrales con más de una dieta: {mixed}.")
    return sorted(animals, key=lambda a: a.sample_id)


def max_folds(records: Sequence[CVAnimal | Mapping[str, Any]]) -> int:
    """Mayor k posible: el número de corrales de la dieta con menos corrales."""
    pens_by_diet: dict[str, set[str]] = defaultdict(set)
    for animal in _animals(records):
        pens_by_diet[animal.diet].add(animal.pen_code)
    if not pens_by_diet:
        raise CrossValidationError("La cohorte está vacía.")
    return min(len(p) for p in pens_by_diet.values())


@dataclass(frozen=True)
class PenFoldPlan:
    """Asignación versionada de folds por semilla: `assignments[seed][sample_id] = fold`."""

    dataset_id: str
    k: int
    seeds: tuple[int, ...]
    assignments: Mapping[int, Mapping[str, int]]
    group_key: str = GROUP_KEY
    stratify_key: str = STRATIFY_KEY
    method: str = METHOD
    version: str = CV_FORMAT_VERSION
    cohort: Mapping[str, Any] = field(default_factory=dict)

    @property
    def sample_ids(self) -> tuple[str, ...]:
        first = self.assignments[self.seeds[0]]
        return tuple(sorted(first))

    def folds(self, seed: int) -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
        """`(train, test)` de cada fold de la semilla, con los `sample_id` ordenados."""
        assignment = self.assignments[seed]
        result = []
        for fold in range(self.k):
            test = tuple(sorted(s for s, f in assignment.items() if f == fold))
            train = tuple(sorted(s for s, f in assignment.items() if f != fold))
            result.append((train, test))
        return result

    def iter_folds(self) -> Iterator[tuple[int, int, tuple[str, ...], tuple[str, ...]]]:
        """`(seed, fold, train, test)` para todas las semillas, en orden."""
        for seed in self.seeds:
            for fold, (train, test) in enumerate(self.folds(seed)):
                yield seed, fold, train, test

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "version": self.version,
            "method": self.method,
            "group_key": self.group_key,
            "stratify_key": self.stratify_key,
            "k": self.k,
            "seeds": list(self.seeds),
            "cohort": dict(self.cohort),
            "assignments": {
                str(seed): dict(sorted(self.assignments[seed].items())) for seed in self.seeds
            },
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PenFoldPlan:
        seeds = tuple(int(s) for s in data["seeds"])
        raw = data["assignments"]
        assignments = {seed: {str(s): int(f) for s, f in raw[str(seed)].items()} for seed in seeds}
        return cls(
            dataset_id=str(data["dataset_id"]),
            k=int(data["k"]),
            seeds=seeds,
            assignments=assignments,
            group_key=str(data.get("group_key", GROUP_KEY)),
            stratify_key=str(data.get("stratify_key", STRATIFY_KEY)),
            method=str(data.get("method", METHOD)),
            version=str(data.get("version", CV_FORMAT_VERSION)),
            cohort=dict(data.get("cohort", {})),
        )

    def save(self, path: str | Path) -> Path:
        """Escribe el JSON con fines de línea LF en cualquier sistema."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return out

    @classmethod
    def load(cls, path: str | Path) -> PenFoldPlan:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def make_pen_folds(
    records: Sequence[CVAnimal | Mapping[str, Any]],
    *,
    dataset_id: str = "D1_holofood",
    k: int = DEFAULT_K,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    min_seeds: int = MIN_SEEDS,
    cohort: Mapping[str, Any] | None = None,
) -> PenFoldPlan:
    """Folds de `StratifiedGroupKFold` (grupo corral, estrato dieta) para cada semilla.

    Raises:
        CrossValidationError: si `k` supera los corrales de alguna dieta, si hay menos de
            `min_seeds` semillas o semillas repetidas, o si la cohorte es inválida.
        ImportError: si falta scikit-learn (extra `baselines`).
    """
    try:
        from sklearn.model_selection import StratifiedGroupKFold
    except ImportError as error:  # pragma: no cover - depende del entorno
        raise ImportError(
            'La validación cruzada por corral requiere scikit-learn: pip install -e ".[baselines]".'
        ) from error

    animals = _animals(records)
    seeds = tuple(int(s) for s in seeds)
    if len(set(seeds)) != len(seeds):
        raise CrossValidationError(f"Semillas repetidas: {seeds}.")
    if len(seeds) < min_seeds:
        raise CrossValidationError(f"D-07 pide al menos {min_seeds} semillas; hay {len(seeds)}.")
    limit = max_folds(animals)
    if k < 2 or k > limit:
        raise CrossValidationError(
            f"k = {k} no es válido: debe estar entre 2 y {limit} (corrales de la dieta con "
            "menos corrales)."
        )

    ids = [a.sample_id for a in animals]
    diets = [a.diet for a in animals]
    pens = [a.pen_code for a in animals]
    assignments: dict[int, dict[str, int]] = {}
    for seed in seeds:
        splitter = StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=seed)
        assignment: dict[str, int] = {}
        for fold, (_, test) in enumerate(splitter.split(ids, diets, groups=pens)):
            for index in test:
                assignment[ids[int(index)]] = fold
        assignments[seed] = assignment
    plan = PenFoldPlan(
        dataset_id=dataset_id,
        k=k,
        seeds=seeds,
        assignments=assignments,
        cohort=dict(cohort or {"size": len(animals)}),
    )
    problems = check_plan(plan, animals)
    if problems:
        raise CrossValidationError("; ".join(problems))
    return plan


def check_plan(plan: PenFoldPlan, records: Sequence[CVAnimal | Mapping[str, Any]]) -> list[str]:
    """Problemas del plan frente a la cohorte; lista vacía si cumple D-07.

    Comprueba que cada semilla asigne exactamente los animales de la cohorte a folds `0..k-1`,
    que ningún corral quede en más de un fold de la misma semilla y que las dietas de la
    cohorte aparezcan en todos los folds de todas las semillas.
    """
    animals = {a.sample_id: a for a in _animals(records)}
    all_diets = {a.diet for a in animals.values()}
    problems: list[str] = []
    for seed in plan.seeds:
        assignment = plan.assignments.get(seed)
        if assignment is None:
            problems.append(f"semilla {seed}: sin asignación")
            continue
        if set(assignment) != set(animals):
            problems.append(f"semilla {seed}: los animales no coinciden con la cohorte")
            continue
        if not set(assignment.values()) <= set(range(plan.k)):
            problems.append(f"semilla {seed}: folds fuera de 0..{plan.k - 1}")
        pen_folds: dict[str, set[int]] = defaultdict(set)
        fold_diets: dict[int, set[str]] = defaultdict(set)
        for sample_id, fold in assignment.items():
            pen_folds[animals[sample_id].pen_code].add(fold)
            fold_diets[fold].add(animals[sample_id].diet)
        for pen, folds in sorted(pen_folds.items()):
            if len(folds) > 1:
                problems.append(
                    f"semilla {seed}: el corral {pen} está en los folds {sorted(folds)}"
                )
        for fold in range(plan.k):
            missing = sorted(all_diets - fold_diets.get(fold, set()))
            if missing:
                problems.append(f"semilla {seed}, fold {fold}: faltan las dietas {missing}")
    return problems


@dataclass(frozen=True)
class FoldRow:
    """Descripción de un fold de una semilla (tabla de folds de D-07)."""

    seed: int
    fold: int
    animals: int
    pens: int
    animals_by_diet: Mapping[str, int]
    pens_by_diet: Mapping[str, int]
    days: tuple[str, ...]
    missing_days: tuple[str, ...]


def _day_key(day: str) -> tuple[int, float, str]:
    try:
        return (0, float(day), day)
    except ValueError:
        return (1, 0.0, day)


def fold_table(plan: PenFoldPlan, records: Sequence[CVAnimal | Mapping[str, Any]]) -> list[FoldRow]:
    """Una fila por semilla y fold con animales, corrales, dietas y días de muestreo."""
    animals = {a.sample_id: a for a in _animals(records)}
    all_days = sorted({a.sampling_day for a in animals.values() if a.sampling_day}, key=_day_key)
    rows: list[FoldRow] = []
    for seed in plan.seeds:
        for fold, (_, test) in enumerate(plan.folds(seed)):
            members = [animals[s] for s in test]
            days = sorted({a.sampling_day for a in members if a.sampling_day}, key=_day_key)
            pens_by_diet: dict[str, set[str]] = defaultdict(set)
            for a in members:
                pens_by_diet[a.diet].add(a.pen_code)
            rows.append(
                FoldRow(
                    seed=seed,
                    fold=fold,
                    animals=len(members),
                    pens=len({a.pen_code for a in members}),
                    animals_by_diet=dict(sorted(Counter(a.diet for a in members).items())),
                    pens_by_diet={d: len(p) for d, p in sorted(pens_by_diet.items())},
                    days=tuple(days),
                    missing_days=tuple(d for d in all_days if d not in days),
                )
            )
    return rows


def summarize_fold_table(rows: Sequence[FoldRow]) -> dict[str, Any]:
    """Rangos de animales y corrales por fold, y semillas con algún fold sin un día."""
    if not rows:
        raise CrossValidationError("La tabla de folds está vacía.")
    seeds = sorted({r.seed for r in rows})
    seeds_missing_day = sorted({r.seed for r in rows if r.missing_days})
    return {
        "seeds": len(seeds),
        "folds_per_seed": len(rows) // len(seeds),
        "animals_per_fold": [min(r.animals for r in rows), max(r.animals for r in rows)],
        "pens_per_fold": [min(r.pens for r in rows), max(r.pens for r in rows)],
        "folds_missing_a_day": sum(1 for r in rows if r.missing_days),
        "seeds_with_a_fold_missing_a_day": seeds_missing_day,
    }


# ---------------------------------------------------------------------------
# Entrenamiento y evaluación por fold
# ---------------------------------------------------------------------------

FoldRunner = Callable[[int, int, tuple[str, ...], tuple[str, ...]], EvaluationReport]
"""`(seed, fold, train_ids, test_ids) -> EvaluationReport` del modelo entrenado en ese fold."""


@dataclass(frozen=True)
class CrossValidationResult:
    """Reportes por fold y su agregación."""

    plan: PenFoldPlan
    fold_reports: Mapping[tuple[int, int], EvaluationReport]
    aggregate: EvaluationReport


def run_cross_validation(plan: PenFoldPlan, runner: FoldRunner) -> CrossValidationResult:
    """Llama a `runner` en cada fold de cada semilla y agrega sus métricas.

    `runner` entrena desde cero con `train_ids` (escaladores y selección de hiperparámetros
    ajustados solo con ellos) y devuelve las métricas sobre `test_ids`. Sirve igual para
    baselines (`evaluate_predictions`) y para el objetivo composicional (`evaluate_composition`,
    con métricas por día en la columna `group`).
    """
    reports: dict[tuple[int, int], EvaluationReport] = {}
    for seed, fold, train, test in plan.iter_folds():
        overlap = set(train) & set(test)
        if overlap:  # pragma: no cover - imposible con un plan válido
            raise CrossValidationError(f"semilla {seed}, fold {fold}: fuga {sorted(overlap)}")
        reports[(seed, fold)] = runner(seed, fold, train, test)
    return CrossValidationResult(plan, reports, aggregate_fold_reports(reports))


AGGREGATES: Final[tuple[str, ...]] = ("mean", "std", "seed_std", "n")
"""Sufijos de las filas agregadas: media y desviación estándar muestral entre todos los
(fold, semilla); desviación estándar muestral entre las medias por semilla; número de folds."""


def aggregate_fold_reports(reports: Mapping[tuple[int, int], EvaluationReport]) -> EvaluationReport:
    """Agrega por `(model, split, group, metric)` las filas de los reportes por fold.

    Devuelve, para cada combinación, cuatro filas con `metric` = `<métrica>_mean`, `_std`,
    `_seed_std` y `_n`. Las celdas `nan` (por ejemplo, R² de un día sin animales en un fold) se
    omiten de la agregación de esa celda. Con un solo valor, la desviación estándar es `nan`.
    """
    if not reports:
        raise CrossValidationError("No hay reportes por fold que agregar.")
    cells: dict[tuple[str, str | None, str | None, str], dict[str, list[tuple[int, float]]]] = {}
    order: list[tuple[str, str | None, str | None, str]] = []
    for (seed, _), report in sorted(reports.items()):
        for row in report.rows:
            # `MetricRow.group` (día de muestreo) llega con #146; sin él, el grupo es `None`.
            key = (row.model, row.split, getattr(row, "group", None), row.metric)
            if key not in cells:
                cells[key] = defaultdict(list)
                order.append(key)
            for name, value in (*row.targets.items(), ("average", row.average)):
                if not math.isnan(value):
                    cells[key][name].append((seed, float(value)))

    rows: list[MetricRow] = []
    for key in order:
        model, split, group, metric = key
        stats: dict[str, dict[str, float]] = {a: {} for a in AGGREGATES}
        for name, pairs in cells[key].items():
            values = [v for _, v in pairs]
            by_seed: dict[int, list[float]] = defaultdict(list)
            for seed, value in pairs:
                by_seed[seed].append(value)
            seed_means = [statistics.fmean(v) for v in by_seed.values()]
            stats["mean"][name] = statistics.fmean(values)
            stats["std"][name] = statistics.stdev(values) if len(values) > 1 else math.nan
            stats["seed_std"][name] = (
                statistics.stdev(seed_means) if len(seed_means) > 1 else math.nan
            )
            stats["n"][name] = float(len(values))
        for aggregate in AGGREGATES:
            by_target = stats[aggregate]
            average = by_target.pop("average", math.nan)
            extra: dict[str, Any] = {"group": group} if group is not None else {}
            rows.append(
                MetricRow(model, f"{metric}_{aggregate}", by_target, average, split=split, **extra)
            )
    return EvaluationReport(rows=tuple(rows))


__all__ = [
    "AGGREGATES",
    "CV_FORMAT_VERSION",
    "DAY_KEY",
    "DEFAULT_K",
    "DEFAULT_SEEDS",
    "GROUP_KEY",
    "METHOD",
    "MIN_SEEDS",
    "STRATIFY_KEY",
    "CVAnimal",
    "CrossValidationError",
    "CrossValidationResult",
    "FoldRow",
    "FoldRunner",
    "PenFoldPlan",
    "aggregate_fold_reports",
    "check_plan",
    "fold_table",
    "make_pen_folds",
    "max_folds",
    "run_cross_validation",
    "summarize_fold_table",
]
