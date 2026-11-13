"""Contrato de `nutrigraphdt.api` (A81-P1, #287): validación sin PyTorch ni corridas."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from nutrigraphdt.api import (
    API_CONTRACT_VERSION,
    CAUSAL_WARNING,
    Bounds,
    InterventionItem,
    ModelRef,
    PredictionInterval,
    ScenarioRequest,
    ScenarioResponse,
    SCFAFractions,
    SupportRef,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SIMULATOR_PAGE = REPO_ROOT / "src" / "nutrigraphdt" / "demo" / "pages" / "scenario_simulator.py"


def _request(**changes: Any) -> dict[str, Any]:
    return {"contract_version": API_CONTRACT_VERSION, "base_instance": "S1", **changes}


def _response(**changes: Any) -> dict[str, Any]:
    model = ModelRef(
        run_id="r",
        variant="homo_sage",
        edges_arm="with_inferred",
        dataset_id="d",
        seed=0,
        fold=0,
        format_version="1.1.0",
        compositional_target_version="1.0.0",
        git_commit=None,
    )
    support = SupportRef(
        version="1.0.0",
        source="train",
        n_animals=3,
        interval={k: Bounds(lower=0.0, upper=1.0) for k in ("acetate", "propionate", "butyrate")},
        method="mínimo y máximo",
    )
    data: dict[str, Any] = {
        "contract_version": API_CONTRACT_VERSION,
        "request": ScenarioRequest.model_validate(_request()),
        "status": "estimable",
        "fractions": SCFAFractions(acetate=0.6, propionate=0.2, butyrate=0.2),
        "log_total": 4.4,
        "model": model,
        "support": support,
        "is_synthetic": True,
        "warnings": (CAUSAL_WARNING,),
    }
    data.update(changes)
    return data


# -- versión y campos ---------------------------------------------------------


def test_request_declares_the_contract_version() -> None:
    request = ScenarioRequest.model_validate(_request())

    assert request.contract_version == API_CONTRACT_VERSION == "1.0.0"
    assert request.intervention == ()


@pytest.mark.parametrize("version", ["0.9.0", "2.0.0", None])
def test_request_rejects_another_contract_version(version: object) -> None:
    with pytest.raises(ValidationError, match="contract_version"):
        ScenarioRequest.model_validate(_request(contract_version=version))


def test_request_requires_the_contract_version() -> None:
    with pytest.raises(ValidationError, match="contract_version"):
        ScenarioRequest.model_validate({"base_instance": "S1"})


def test_request_rejects_undeclared_fields() -> None:
    with pytest.raises(ValidationError, match="extra"):
        ScenarioRequest.model_validate(_request(seed=3))


def test_intervention_item_rejects_undeclared_fields() -> None:
    with pytest.raises(ValidationError, match="extra"):
        InterventionItem.model_validate({"variable": "additive.dose", "value": 1.0, "unit": "g"})


# -- variables intervenidas ----------------------------------------------------


@pytest.mark.parametrize("variable", ["", "dose", "additive.", "diet.composition.a.b"])
def test_intervention_rejects_malformed_variable_paths(variable: str) -> None:
    with pytest.raises(ValidationError):
        ScenarioRequest.model_validate(
            _request(intervention=[{"variable": variable, "value": 1.0}])
        )


def test_intervention_rejects_a_repeated_variable() -> None:
    item = {"variable": "additive.dose", "value": 1.0}

    with pytest.raises(ValidationError, match="más de una vez"):
        ScenarioRequest.model_validate(_request(intervention=[item, item]))


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), [1], {"a": 1}])
def test_intervention_rejects_missing_or_non_scalar_values(value: object) -> None:
    with pytest.raises(ValidationError):
        ScenarioRequest.model_validate(
            _request(intervention=[{"variable": "additive.dose", "value": value}])
        )


def test_intervention_keeps_booleans_and_numbers_apart() -> None:
    request = ScenarioRequest.model_validate(
        _request(intervention=[{"variable": "host.covariates.flag", "value": True}])
    )

    assert request.intervention[0].value is True


def test_request_round_trips_through_json() -> None:
    request = ScenarioRequest.model_validate(
        _request(intervention=[{"variable": "diet.name", "value": "Probiotic"}])
    )

    assert ScenarioRequest.model_validate_json(request.model_dump_json()) == request


# -- salida ----------------------------------------------------------------------


def test_estimable_response_carries_fractions_and_log_total() -> None:
    response = ScenarioResponse.model_validate(_response())

    assert response.fractions is not None
    assert response.log_total == 4.4
    assert response.interval is None


def test_not_estimable_response_without_numbers_is_valid() -> None:
    response = ScenarioResponse.model_validate(
        _response(status="no_estimable", fractions=None, log_total=None, reasons=("fuera",))
    )

    dumped = json.loads(response.model_dump_json())
    assert dumped["fractions"] is None
    assert dumped["log_total"] is None
    assert dumped["interval"] is None


@pytest.mark.parametrize(
    "numbers",
    [
        {"fractions": SCFAFractions(acetate=0.6, propionate=0.2, butyrate=0.2), "log_total": None},
        {"fractions": None, "log_total": 4.4},
        {
            "fractions": None,
            "log_total": None,
            "interval": PredictionInterval(
                method="conformal",
                level=0.9,
                fractions={"acetate": Bounds(lower=0.5, upper=0.7)},
            ),
        },
    ],
)
def test_not_estimable_response_cannot_carry_numbers(numbers: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="no estimable no puede llevar números"):
        ScenarioResponse.model_validate(
            _response(status="no_estimable", reasons=("fuera",), **numbers)
        )


def test_not_estimable_response_must_say_why() -> None:
    with pytest.raises(ValidationError, match="debe decir por qué"):
        ScenarioResponse.model_validate(
            _response(status="no_estimable", fractions=None, log_total=None)
        )


def test_estimable_response_needs_both_numbers_and_no_reasons() -> None:
    with pytest.raises(ValidationError, match="estimable lleva"):
        ScenarioResponse.model_validate(_response(log_total=None))
    with pytest.raises(ValidationError, match="estimable lleva"):
        ScenarioResponse.model_validate(_response(reasons=("fuera",)))


def test_every_response_warns_that_a_scenario_is_not_causal() -> None:
    with pytest.raises(ValidationError, match="efecto causal"):
        ScenarioResponse.model_validate(_response(warnings=()))


def test_fractions_must_close_to_one() -> None:
    with pytest.raises(ValidationError, match="sumar 1"):
        SCFAFractions(acetate=0.6, propionate=0.3, butyrate=0.2)


def test_bounds_must_be_ordered() -> None:
    with pytest.raises(ValidationError, match="lower"):
        Bounds(lower=0.7, upper=0.5)


# -- frontera entre interfaz y motor ---------------------------------------------


def test_contract_imports_without_the_engine_extras() -> None:
    code = (
        "import sys\n"
        "import nutrigraphdt.api as api\n"
        "assert api.API_CONTRACT_VERSION == '1.0.0'\n"
        "heavy = sorted(m for m in ('torch', 'torch_geometric', 'sklearn') if m in sys.modules)\n"
        "assert not heavy, heavy\n"
    )

    subprocess.run([sys.executable, "-c", code], check=True, cwd=REPO_ROOT)


def test_simulator_page_only_reaches_the_engine_through_the_api() -> None:
    tree = ast.parse(SIMULATOR_PAGE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)

    internal = {
        name
        for name in imported
        if name.startswith("nutrigraphdt")
        and name not in {"nutrigraphdt.api", "nutrigraphdt.demo.ui"}
    }
    assert "nutrigraphdt.api" in imported
    assert not internal, internal
