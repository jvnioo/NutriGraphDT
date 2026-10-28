"""Tests de la validación cruzada por corral (D-07, #139).

La cohorte de estas pruebas es **ficticia**: imita solo la estructura de D1 (56 animales; 15
corrales Control, 10 Probiótico y 6 Fitobiótico; días 7, 21 y 35). No contiene datos reales.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import pytest

pytest.importorskip("sklearn")

from nutrigraphdt.models.cross_validation import (  # noqa: E402
    CrossValidationError,
    CVAnimal,
    PenFoldPlan,
    aggregate_fold_reports,
    check_plan,
    fold_table,
    make_pen_folds,
    max_folds,
    run_cross_validation,
    summarize_fold_table,
)
from nutrigraphdt.models.metrics import EvaluationReport, MetricRow  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.create_cv_folds import build_report, cohort_animals, to_markdown  # noqa: E402

DIET_PENS = {"CC": 15, "CO": 10, "CE": 6}
DIET_DAYS = {"CC": ("7", "21", "35", "35"), "CO": ("7", "21", "35"), "CE": ("7", "21")}


def toy_cohort() -> list[CVAnimal]:
    animals: list[CVAnimal] = []
    sizes = {"CC": 34, "CO": 15, "CE": 7}
    for diet, n_pens in DIET_PENS.items():
        for i in range(sizes[diet]):
            pen = f"{diet}{i % n_pens:02d}"
            days = DIET_DAYS[diet]
            animals.append(CVAnimal(f"S{diet}{i:03d}", pen, diet, days[i % len(days)]))
    return animals


@pytest.fixture(scope="module")
def plan() -> PenFoldPlan:
    return make_pen_folds(toy_cohort(), seeds=range(12))


def test_every_diet_appears_in_every_fold_of_every_seed(plan: PenFoldPlan) -> None:
    animals = {a.sample_id: a for a in toy_cohort()}
    for seed, fold, _, test in plan.iter_folds():
        diets = {animals[s].diet for s in test}
        assert diets == set(DIET_PENS), (seed, fold)
    assert check_plan(plan, toy_cohort()) == []


def test_no_pen_is_in_more_than_one_fold_of_a_seed(plan: PenFoldPlan) -> None:
    animals = {a.sample_id: a for a in toy_cohort()}
    for seed in plan.seeds:
        folds_by_pen: dict[str, set[int]] = defaultdict(set)
        for sample_id, fold in plan.assignments[seed].items():
            folds_by_pen[animals[sample_id].pen_code].add(fold)
        assert all(len(f) == 1 for f in folds_by_pen.values()), seed


def test_folds_partition_the_cohort_without_leakage(plan: PenFoldPlan) -> None:
    ids = {a.sample_id for a in toy_cohort()}
    for seed in plan.seeds:
        tests = [set(test) for _, test in plan.folds(seed)]
        assert set().union(*tests) == ids
        assert sum(len(t) for t in tests) == len(ids)
        for train, test in plan.folds(seed):
            assert not set(train) & set(test)


def test_plan_is_deterministic_and_seeds_differ(plan: PenFoldPlan) -> None:
    again = make_pen_folds(list(reversed(toy_cohort())), seeds=range(12))
    assert again.assignments == plan.assignments
    assert len({json.dumps(plan.assignments[s], sort_keys=True) for s in plan.seeds}) > 1


def test_plan_round_trips_through_json_with_lf(plan: PenFoldPlan, tmp_path: Path) -> None:
    path = plan.save(tmp_path / "cv.json")
    assert b"\r\n" not in path.read_bytes()
    loaded = PenFoldPlan.load(path)
    assert loaded == plan
    assert loaded.to_dict()["assignments"]["0"] == dict(sorted(plan.assignments[0].items()))


def test_k_is_limited_by_the_diet_with_fewest_pens() -> None:
    assert max_folds(toy_cohort()) == 6
    make_pen_folds(toy_cohort(), k=6)
    with pytest.raises(CrossValidationError, match="k = 7"):
        make_pen_folds(toy_cohort(), k=7)


def test_requires_at_least_ten_distinct_seeds() -> None:
    with pytest.raises(CrossValidationError, match="al menos 10"):
        make_pen_folds(toy_cohort(), seeds=range(9))
    with pytest.raises(CrossValidationError, match="repetidas"):
        make_pen_folds(toy_cohort(), seeds=[0] * 10)


def test_invalid_cohorts_are_rejected() -> None:
    cohort = toy_cohort()
    with pytest.raises(CrossValidationError, match="repetido"):
        make_pen_folds([*cohort, cohort[0]])
    mixed = [*cohort, CVAnimal("SX", cohort[0].pen_code, "CO", "7")]
    with pytest.raises(CrossValidationError, match="más de una dieta"):
        make_pen_folds(mixed)
    with pytest.raises(CrossValidationError, match="sin pen_code"):
        CVAnimal.from_mapping({"sample_id": "S", "diet_treatment_code": "CC"})


def test_check_plan_reports_split_pens_and_missing_diets(plan: PenFoldPlan) -> None:
    cohort = toy_cohort()
    broken = {s: dict(a) for s, a in plan.assignments.items()}
    same_pen = [a.sample_id for a in cohort if a.pen_code == "CE00"]
    broken[0][same_pen[0]] = (broken[0][same_pen[1]] + 1) % plan.k
    ce = [a.sample_id for a in cohort if a.diet == "CE"]
    for sample_id in ce:
        broken[1][sample_id] = 0
    problems = check_plan(PenFoldPlan(plan.dataset_id, plan.k, plan.seeds, broken), cohort)
    assert any("semilla 0" in p and "CE00" in p for p in problems)
    assert any("semilla 1, fold 1" in p and "CE" in p for p in problems)


def test_fold_table_reports_days_missing_from_a_fold(plan: PenFoldPlan) -> None:
    rows = fold_table(plan, toy_cohort())
    assert len(rows) == 12 * plan.k
    assert all(sum(r.animals_by_diet.values()) == r.animals for r in rows)
    assert all(set(r.days) | set(r.missing_days) == {"7", "21", "35"} for r in rows)
    summary = summarize_fold_table(rows)
    assert summary["seeds"] == 12 and summary["folds_per_seed"] == plan.k
    assert summary["animals_per_fold"][0] <= summary["animals_per_fold"][1]
    assert summary["folds_missing_a_day"] == sum(1 for r in rows if r.missing_days)


def test_report_and_markdown_from_the_script(plan: PenFoldPlan) -> None:
    metadata = {
        a.sample_id: {
            "sample_id": a.sample_id,
            "pen_code": a.pen_code,
            "diet_treatment_code": a.diet,
            "sampling_day": a.sampling_day or "",
        }
        for a in toy_cohort()
    }
    animals = cohort_animals(sorted(metadata), metadata)
    rows = fold_table(plan, animals)
    report = build_report(plan, animals, rows)
    assert report["max_k"] == 6
    assert len(report["folds"]) == len(rows)
    markdown = to_markdown(report, rows)
    assert "Comparación con D-07" in markdown
    assert "| Las tres dietas en todos los folds | sí | sí (verificado) |" in markdown
    with pytest.raises(ValueError, match="sin metadatos"):
        cohort_animals(["missing"], metadata)


# ---------------------------------------------------------------------------
# Entrenamiento por fold y agregación
# ---------------------------------------------------------------------------


def _report(value: float, seed_offset: float = 0.0) -> EvaluationReport:
    return EvaluationReport(
        rows=(
            MetricRow("toy", "mae", {"acetate": value, "butyrate": 2 * value}, 1.5 * value, "test"),
        )
    )


def test_aggregate_reports_mean_std_and_seed_std() -> None:
    # Semilla 0: folds 1 y 3 (media 2); semilla 1: folds 5 y 7 (media 6).
    reports = {(0, 0): _report(1), (0, 1): _report(3), (1, 0): _report(5), (1, 1): _report(7)}
    aggregate = aggregate_fold_reports(reports)

    by_metric = {row.metric: row for row in aggregate.rows}
    assert list(by_metric) == ["mae_mean", "mae_std", "mae_seed_std", "mae_n"]
    assert by_metric["mae_mean"].targets == pytest.approx({"acetate": 4.0, "butyrate": 8.0})
    assert by_metric["mae_mean"].average == pytest.approx(6.0)
    std = math.sqrt(sum((v - 4) ** 2 for v in (1, 3, 5, 7)) / 3)
    assert by_metric["mae_std"].targets["acetate"] == pytest.approx(std)
    assert by_metric["mae_seed_std"].targets["acetate"] == pytest.approx(math.sqrt(8))
    assert by_metric["mae_n"].targets["acetate"] == 4.0
    assert all(row.split == "test" for row in aggregate.rows)


def test_aggregate_skips_nan_cells() -> None:
    reports = {(0, 0): _report(1.0), (0, 1): _report(math.nan)}
    by_metric = {row.metric: row for row in aggregate_fold_reports(reports).rows}
    assert by_metric["mae_mean"].targets["acetate"] == 1.0
    assert math.isnan(by_metric["mae_std"].targets["acetate"])
    assert by_metric["mae_n"].targets["acetate"] == 1.0


def test_run_cross_validation_calls_the_runner_once_per_fold(plan: PenFoldPlan) -> None:
    calls: list[tuple[int, int]] = []

    def runner(
        seed: int, fold: int, train: tuple[str, ...], test: tuple[str, ...]
    ) -> EvaluationReport:
        assert not set(train) & set(test)
        calls.append((seed, fold))
        return _report(float(len(test)))

    result = run_cross_validation(plan, runner)

    assert calls == [(s, f) for s in plan.seeds for f in range(plan.k)]
    assert set(result.fold_reports) == set(calls)
    mean = next(r for r in result.aggregate.rows if r.metric == "mae_mean")
    assert mean.targets["acetate"] == pytest.approx(56 / plan.k)


def test_aggregate_requires_reports() -> None:
    with pytest.raises(CrossValidationError):
        aggregate_fold_reports({})
