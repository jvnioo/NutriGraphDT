"""Control de soporte empírico de las predicciones de escenarios (F6, D-06 §7; #245).

Las fracciones son de prueba, escritas a mano; no son datos de D1.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nutrigraphdt.scenarios import (
    ESTIMABLE,
    NOT_ESTIMABLE,
    EmpiricalSupport,
    SupportError,
    support_from_run,
)

TRAIN = [(0.70, 0.10, 0.20), (0.80, 0.05, 0.15), (0.60, 0.15, 0.25)]
# Mínimos y máximos calculados a mano: acetato [0,60; 0,80], propionato [0,05; 0,15],
# butirato [0,15; 0,25].


@pytest.fixture
def support() -> EmpiricalSupport:
    return EmpiricalSupport.fit(TRAIN, source="train del fold de prueba")


def test_support_is_the_min_and_max_of_the_training_fractions(support: EmpiricalSupport) -> None:
    assert support.interval == {
        "acetate": (0.60, 0.80),
        "propionate": (0.05, 0.15),
        "butyrate": (0.15, 0.25),
    }
    assert (support.n_animals, support.source) == (3, "train del fold de prueba")


def test_inside_and_boundary_predictions_are_estimable(support: EmpiricalSupport) -> None:
    inside, boundary = support.check([(0.70, 0.10, 0.20), (0.60, 0.15, 0.25)])
    assert (inside.status, inside.fractions) == (ESTIMABLE, (0.70, 0.10, 0.20))
    assert boundary.status == ESTIMABLE
    assert inside.reasons == ()


def test_out_of_support_prediction_is_not_reported_as_a_number(support: EmpiricalSupport) -> None:
    (result,) = support.check([(0.55, 0.20, 0.25)])
    assert result.status == NOT_ESTIMABLE
    assert result.fractions is None
    assert len(result.reasons) == 2
    assert "acetate = 0.55 fuera de [0.6, 0.8]" in result.reasons
    assert "propionate = 0.2 fuera de [0.05, 0.15]" in result.reasons
    data = result.to_dict()
    assert data["interval"]["propionate"] == [0.05, 0.15]
    assert data["source"] == "train del fold de prueba"


def test_support_by_sampling_day() -> None:
    support = EmpiricalSupport.fit(TRAIN, source="train", days=["7", "7", "21"])
    assert support.by_day["7"]["propionate"] == (0.05, 0.10)
    assert support.n_by_day == {"7": 2, "21": 1}
    in_day_21, out_day_7, unknown = support.check(
        [(0.60, 0.15, 0.25), (0.60, 0.15, 0.25), (0.70, 0.10, 0.20)], days=["21", "7", "35"]
    )
    assert in_day_21.status == ESTIMABLE
    assert out_day_7.status == NOT_ESTIMABLE  # 0,15 de propionato está fuera del día 7
    assert unknown.status == NOT_ESTIMABLE
    assert "no tiene animales de entrenamiento" in unknown.reasons[0]


@pytest.mark.parametrize(
    ("rows", "fragment"),
    [
        ([], "al menos un animal"),
        ([(0.5, 0.5)], "3 fracciones"),
        ([(0.5, 0.6, 0.1)], "sumar 1"),
        ([(1.2, -0.1, -0.1)], "no negativas"),
        ([(float("nan"), 0.5, 0.5)], "finitas"),
    ],
)
def test_invalid_compositions_are_rejected(rows: list[tuple[float, ...]], fragment: str) -> None:
    with pytest.raises(SupportError, match=fragment):
        EmpiricalSupport.fit(rows, source="train")


def test_days_requested_without_day_support_are_rejected(support: EmpiricalSupport) -> None:
    with pytest.raises(SupportError, match="sin días"):
        support.check([(0.70, 0.10, 0.20)], days=["7"])


def test_run_support_uses_only_the_training_animals(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "run.json").write_text(
        json.dumps(
            {
                "run_id": "r1",
                "seed": 0,
                "fold": 2,
                "sample_ids": {"train": ["a", "b", "c"], "inner_val": ["v"], "test": ["t"]},
            }
        ),
        encoding="utf-8",
    )
    fractions = dict(zip("abc", TRAIN, strict=True))
    # El val interno y el test tienen composiciones extremas: si entraran, ampliarían el soporte.
    fractions["v"] = (0.10, 0.80, 0.10)
    fractions["t"] = (0.98, 0.01, 0.01)

    support = support_from_run(run, fractions)

    assert support.interval["acetate"] == (0.60, 0.80)
    assert support.interval["propionate"] == (0.05, 0.15)
    assert support.source == "train de la corrida r1 (semilla 0, fold 2)"
    with pytest.raises(SupportError, match="sin composición medida"):
        support_from_run(run, {"a": TRAIN[0]})
