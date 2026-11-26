"""Criterios de resultado de una comparación de escenarios (A93-P3, #311), sin PyTorch."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from nutrigraphdt.api import (
    CAUSAL_WARNING,
    SYNTHETIC_WARNING,
    ScenarioRequest,
    ScenarioResponse,
)
from nutrigraphdt.simulation import (
    DIFFERENCE_WARNING,
    QUANTITIES,
    SimulationError,
    build_comparison,
    checkpoint_sha256,
)

HASH = "0" * 64
SUPPORT = {
    "version": "1.0.0",
    "source": "train",
    "n_animals": 12,
    "interval": {
        name: {"lower": 0.0, "upper": 1.0} for name in ("acetate", "propionate", "butyrate")
    },
    "method": "min-max",
}
MODEL = {
    "run_id": "run-a",
    "variant": "homo_sage",
    "edges_arm": "with_inferred",
    "dataset_id": "synthetic_cohort",
    "seed": 0,
    "fold": 0,
    "format_version": "1",
    "compositional_target_version": "1",
    "git_commit": None,
}


def _response(
    fractions: tuple[float, float, float] | None,
    log_total: float | None = 4.0,
    *,
    intervention: list[dict[str, Any]] | None = None,
    run_id: str = "run-a",
) -> ScenarioResponse:
    estimable = fractions is not None
    return ScenarioResponse.model_validate(
        {
            "contract_version": "1.0.0",
            "request": {
                "contract_version": "1.0.0",
                "base_instance": "synthetic:sample:0017",
                "intervention": intervention or [],
            },
            "status": "estimable" if estimable else "no_estimable",
            "fractions": (
                dict(zip(("acetate", "propionate", "butyrate"), fractions, strict=True))
                if fractions
                else None
            ),
            "log_total": log_total if estimable else None,
            "reasons": () if estimable else ("acetate fuera del soporte",),
            "model": {**MODEL, "run_id": run_id},
            "support": SUPPORT,
            "is_synthetic": True,
            "warnings": (CAUSAL_WARNING,),
        }
    )


DOSE = [{"variable": "additive.dose", "value": 0.0}]


def test_difference_is_intervened_minus_basal_with_units() -> None:
    comparison = build_comparison(
        _response((0.6, 0.25, 0.15), 4.0),
        _response((0.5, 0.3, 0.2), 4.5, intervention=DOSE),
        checkpoint=HASH,
    )
    assert comparison.status == "estimable"
    assert [d.quantity for d in comparison.differences] == list(QUANTITIES)
    acetate = comparison.difference("acetate")
    assert acetate is not None and acetate.difference == pytest.approx(-0.1)
    assert acetate.unit.startswith("fracción molar")
    total = comparison.difference("log_total")
    assert total is not None and total.difference == pytest.approx(0.5)
    assert "T_int / T_basal" in total.difference_unit
    shares = [d.difference for d in comparison.differences[:3]]
    assert sum(shares) == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize("side", ["basal", "intervened"])
def test_not_estimable_propagates_to_the_difference(side: str) -> None:
    good = (0.6, 0.25, 0.15)
    basal = _response(None if side == "basal" else good)
    intervened = _response(None if side == "intervened" else good, intervention=DOSE)
    comparison = build_comparison(basal, intervened, checkpoint=HASH)

    assert comparison.status == "no_estimable"
    assert comparison.differences == ()
    assert comparison.difference("acetate") is None
    prefix = "basal:" if side == "basal" else "intervenido:"
    assert comparison.reasons and comparison.reasons[0].startswith(prefix)


def test_every_comparison_warns_that_it_is_not_an_effect() -> None:
    comparison = build_comparison(
        _response((0.6, 0.25, 0.15)),
        _response((0.6, 0.25, 0.15), intervention=DOSE),
        checkpoint=HASH,
    )
    assert CAUSAL_WARNING in comparison.warnings
    assert DIFFERENCE_WARNING in comparison.warnings
    assert SYNTHETIC_WARNING in comparison.warnings
    assert comparison.is_synthetic


def test_different_runs_cannot_be_compared() -> None:
    with pytest.raises(SimulationError, match="mismo modelo"):
        build_comparison(
            _response((0.6, 0.25, 0.15)),
            _response((0.6, 0.25, 0.15), intervention=DOSE, run_id="run-b"),
            checkpoint=HASH,
        )


def test_a_not_estimable_comparison_cannot_carry_numbers() -> None:
    comparison = build_comparison(
        _response(None), _response((0.6, 0.25, 0.15), intervention=DOSE), checkpoint=HASH
    )
    estimable = build_comparison(
        _response((0.6, 0.25, 0.15)),
        _response((0.6, 0.25, 0.15), intervention=DOSE),
        checkpoint=HASH,
    )
    data = comparison.model_dump()
    data["differences"] = estimable.model_dump()["differences"]
    with pytest.raises(ValidationError, match="no lleva diferencias"):
        type(comparison).model_validate(data)


def test_comparison_round_trips_through_json() -> None:
    comparison = build_comparison(
        _response((0.6, 0.25, 0.15)), _response((0.5, 0.3, 0.2), intervention=DOSE), checkpoint=HASH
    )
    again = type(comparison).model_validate_json(comparison.model_dump_json())
    assert again == comparison
    assert isinstance(again.intervened.request, ScenarioRequest)


def test_checkpoint_hash_reads_the_file(tmp_path: Path) -> None:
    (tmp_path / "checkpoint.pt").write_bytes(b"abc")
    assert checkpoint_sha256(tmp_path) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
