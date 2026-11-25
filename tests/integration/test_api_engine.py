"""Motor de escenarios de `nutrigraphdt.api` con las corridas de demostración (A81, #287, #288).

Usa las corridas congeladas de `tests/fixtures/api/frozen_runs/` y los escenarios de
`tests/fixtures/api/scenarios.json`; no usa red ni `data/raw/`. Requiere los extras `graph` y
`baselines`.
"""

from __future__ import annotations

import csv
import json
import socket
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")

from nutrigraphdt.api import (  # noqa: E402
    API_CONTRACT_VERSION,
    CAUSAL_WARNING,
    D1_PARTIAL_WARNING,
    DEMO_RUNS,
    IN_TRAIN_WARNING,
    SYNTHETIC_WARNING,
    ScenarioBase,
    ScenarioContractError,
    ScenarioEngine,
    ScenarioRequest,
    demo_scenarios,
    predict_scenario,
)
from nutrigraphdt.models.composition import fractions_from_log_ratios  # noqa: E402

SYNTHETIC_TEST = "synthetic:sample:0017"
D1_TEST = "SAMEA112904810"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("las pruebas de la plataforma no usan red")

    monkeypatch.setattr(socket.socket, "connect", refuse)


@pytest.fixture(scope="module")
def engines() -> Iterator[dict[str, ScenarioEngine]]:
    yield {name: run.engine() for name, run in DEMO_RUNS.items()}


def _request(base: str, *changes: tuple[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": API_CONTRACT_VERSION,
        "base_instance": base,
        "intervention": [{"variable": v, "value": x} for v, x in changes],
    }


# -- escenarios de ejemplo -------------------------------------------------------


def test_examples_cover_estimable_and_not_estimable_cases_for_each_run() -> None:
    for run in DEMO_RUNS:
        statuses = {s.expected_status for s in demo_scenarios(run)}
        assert statuses == {"estimable", "no_estimable"}, run


@pytest.mark.parametrize("scenario", demo_scenarios(), ids=lambda s: s.id)
def test_example_scenarios_return_their_expected_status(
    engines: dict[str, ScenarioEngine], scenario: Any
) -> None:
    response = engines[scenario.run].predict(scenario.request)

    assert response.status == scenario.expected_status
    assert response.request == scenario.request
    assert response.contract_version == API_CONTRACT_VERSION
    assert CAUSAL_WARNING in response.warnings
    assert response.is_synthetic is DEMO_RUNS[scenario.run].is_synthetic


@pytest.mark.parametrize(
    "scenario",
    [s for s in demo_scenarios() if s.expected_status == "no_estimable"],
    ids=lambda s: s.id,
)
def test_out_of_support_prediction_returns_no_numbers(
    engines: dict[str, ScenarioEngine], scenario: Any
) -> None:
    response = engines[scenario.run].predict(scenario.request)
    dumped = json.loads(response.model_dump_json())

    assert response.status == "no_estimable"
    assert dumped["fractions"] is None
    assert dumped["log_total"] is None
    assert dumped["interval"] is None
    assert response.reasons and all("fuera de" in reason for reason in response.reasons)


# -- coherencia con la corrida congelada -----------------------------------------


@pytest.mark.parametrize("run", list(DEMO_RUNS))
def test_basal_scenario_reproduces_the_frozen_test_predictions(
    engines: dict[str, ScenarioEngine], run: str
) -> None:
    engine = engines[run]
    with (DEMO_RUNS[run].run_dir / "predictions.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows
    for row in rows:
        response = engine.predict(_request(row["sample_id"]))
        expected = fractions_from_log_ratios(float(row["z1"]), float(row["z2"]))
        if response.status == "estimable":
            assert response.fractions is not None and response.log_total is not None
            got = (response.fractions.acetate, response.fractions.propionate)
            assert got == pytest.approx(expected[:2], abs=1e-5)
            assert response.log_total == pytest.approx(float(row["log_total"]), abs=1e-5)
        else:
            assert engine.support.check([expected])[0].status == "no_estimable"


def test_response_declares_the_run_and_support(engines: dict[str, ScenarioEngine]) -> None:
    engine = engines["d1_fixture"]
    response = engine.predict(_request(D1_TEST))
    info = json.loads((DEMO_RUNS["d1_fixture"].run_dir / "run.json").read_text("utf-8"))

    assert response.model.run_id == info["run_id"]
    assert response.model.dataset_id == info["dataset_id"] == "D1_holofood_fixture"
    assert response.support.n_animals == len(info["sample_ids"]["train"])
    assert D1_PARTIAL_WARNING in response.warnings
    assert response.is_synthetic is False


def test_training_config_of_each_run_names_its_own_dataset_and_plan() -> None:
    for run in DEMO_RUNS.values():
        info = json.loads((run.run_dir / "run.json").read_text("utf-8"))
        assert info["training_config"]["dataset_id"] == info["dataset_id"]
        assert info["training_config"]["split_file"].endswith(f"{run.name}/plan.json")


def test_synthetic_responses_are_labelled_synthetic(engines: dict[str, ScenarioEngine]) -> None:
    response = engines["synthetic"].predict(_request(SYNTHETIC_TEST))

    assert response.is_synthetic is True
    assert SYNTHETIC_WARNING in response.warnings


def test_base_in_train_is_flagged(engines: dict[str, ScenarioEngine]) -> None:
    engine = engines["synthetic"]
    in_train = engine.train_ids[0]

    assert engine.split_of(in_train) == "train"
    assert IN_TRAIN_WARNING in engine.predict(_request(in_train)).warnings
    assert IN_TRAIN_WARNING not in engine.predict(_request(SYNTHETIC_TEST)).warnings


def test_predict_scenario_matches_a_reused_engine(engines: dict[str, ScenarioEngine]) -> None:
    run = DEMO_RUNS["d1_fixture"]
    request = _request(D1_TEST, ("diet.name", "Probiotic"))

    once = predict_scenario(request, run_dir=run.run_dir, base=run.base())

    assert once == engines["d1_fixture"].predict(request)


# -- vocabulario y validación ----------------------------------------------------


def test_engine_rejects_undeclared_variables(engines: dict[str, ScenarioEngine]) -> None:
    with pytest.raises(ScenarioContractError, match="no es una variable declarada"):
        engines["synthetic"].predict(_request(SYNTHETIC_TEST, ("diet.composition.lysine", 1.0)))


def test_engine_rejects_microbiome_variables(engines: dict[str, ScenarioEngine]) -> None:
    with pytest.raises(ScenarioContractError, match="no es una variable declarada"):
        engines["d1_fixture"].predict(_request(D1_TEST, ("taxon.abundance", 0.5)))


def test_vocabulary_only_lists_intervenable_node_types(engines: dict[str, ScenarioEngine]) -> None:
    for engine in engines.values():
        assert engine.variables
        assert {v.node_type for v in engine.variables} <= {"diet", "additive", "host"}


@pytest.mark.parametrize(
    ("request_data", "match"),
    [
        ({"base_instance": SYNTHETIC_TEST}, "contract_version"),
        (_request(SYNTHETIC_TEST) | {"contract_version": "2.0.0"}, "contract_version"),
        (_request(SYNTHETIC_TEST) | {"extra": 1}, "extra"),
        (_request("synthetic:sample:9999"), "no existe"),
        (_request(SYNTHETIC_TEST, ("additive.dose", "mucho")), "se esperaba un número"),
        (_request(D1_TEST, ("diet.name", "Fasting")), "no está en"),
    ],
)
def test_engine_rejects_invalid_requests(
    engines: dict[str, ScenarioEngine], request_data: dict[str, Any], match: str
) -> None:
    run = "d1_fixture" if request_data.get("base_instance") == D1_TEST else "synthetic"

    with pytest.raises(ScenarioContractError, match=match):
        engines[run].predict(request_data)


@pytest.mark.parametrize(
    ("variable", "value", "match"),
    [
        ("diet.composition.crude_protein", -1.0, "no puede ser negativo"),
        ("additive.dose", -1.0, "no puede ser negativo"),
        ("host.covariates.age_days", -3, "no puede ser negativo"),
        ("diet.composition.crude_protein", 1000.5, "supera 1000 g/kg"),
    ],
)
def test_engine_rejects_physically_impossible_values(
    engines: dict[str, ScenarioEngine], variable: str, value: float, match: str
) -> None:
    """Regresión de A81-P4 (#290): antes se predecía con valores imposibles por definición."""
    with pytest.raises(ScenarioContractError, match=match):
        engines["synthetic"].predict(_request(SYNTHETIC_TEST, (variable, value)))


def test_mass_fraction_at_its_bound_is_accepted(engines: dict[str, ScenarioEngine]) -> None:
    response = engines["synthetic"].predict(
        _request(SYNTHETIC_TEST, ("diet.composition.crude_protein", 1000.0))
    )

    assert response.status in {"estimable", "no_estimable"}


# -- cobertura de las entradas ---------------------------------------------------


def test_input_outside_the_train_values_is_warned(engines: dict[str, ScenarioEngine]) -> None:
    """Regresión de A81-P4 (#290): una entrada nunca vista se advierte aunque sea estimable."""
    engine = engines["synthetic"]
    assert engine.train_coverage["diet.composition.crude_protein"] == (215.0, 215.0)

    response = engine.predict(_request(SYNTHETIC_TEST, ("diet.composition.crude_protein", 190.0)))

    assert response.status == "estimable"
    assert any("crude_protein = 190.0 no se observó" in w for w in response.warnings)


def test_input_inside_the_train_values_is_not_warned(engines: dict[str, ScenarioEngine]) -> None:
    response = engines["synthetic"].predict(
        _request(SYNTHETIC_TEST, ("host.covariates.body_weight_g", 2500.0))
    )

    assert not any("no se observó en el train" in w for w in response.warnings)


def test_category_outside_the_train_is_warned(engines: dict[str, ScenarioEngine]) -> None:
    engine = engines["d1_fixture"]
    assert "CC" not in engine.train_coverage["host.covariates.trial_code"]

    response = engine.predict(_request(D1_TEST, ("host.covariates.trial_code", "CC")))

    assert any("trial_code = CC no se observó" in w for w in response.warnings)


def test_values_of_reads_the_observed_base(engines: dict[str, ScenarioEngine]) -> None:
    base = engines["synthetic"].base

    assert base.values_of(SYNTHETIC_TEST, "diet.composition.crude_protein") == (215.0,)
    assert base.values_of(SYNTHETIC_TEST, "additive.dose") == (1e9,)
    assert engines["d1_fixture"].base.values_of(D1_TEST, "diet.name") == ("Control",)


# -- límites de la instancia derivada ---------------------------------------------


def test_derived_instance_is_synthetic_and_declares_its_origin(
    engines: dict[str, ScenarioEngine],
) -> None:
    request = ScenarioRequest.model_validate(_request(D1_TEST, ("diet.name", "Probiotic")))

    instance, nodes, _ = engines["d1_fixture"].base.derive(request)

    assert instance["is_synthetic"] is True
    assert instance["derived_from"] == D1_TEST
    assert instance["intervention"] == [{"variable": "diet.name", "value": "Probiotic"}]
    assert [n["attributes"]["name"] for n in nodes if n["node_type"] == "diet"] == ["Probiotic"]


def test_base_with_hypothetical_edges_is_refused(engines: dict[str, ScenarioEngine]) -> None:
    base = engines["d1_fixture"].base
    graph_id = str(base.instance(D1_TEST)["graph_id"])
    edges = [
        {**e, "evidence_status": "hypothetical"} if e["graph_id"] == graph_id else e
        for e in base.edges
    ]
    tainted = ScenarioBase.from_records(
        SimpleNamespace(
            instances=base.instances, nodes=base.nodes, edges=edges, outputs=base.outputs
        ),
        base.schema,
        dataset_id=base.dataset_id,
        is_synthetic=base.is_synthetic,
    )

    with pytest.raises(ScenarioContractError, match="hypothetical"):
        tainted.derive(ScenarioRequest.model_validate(_request(D1_TEST)))


def test_engine_refuses_a_base_from_another_dataset() -> None:
    run = DEMO_RUNS["synthetic"]
    other = DEMO_RUNS["d1_fixture"].base()

    with pytest.raises(ScenarioContractError, match="se entrenó con"):
        ScenarioEngine(run.run_dir, other)
