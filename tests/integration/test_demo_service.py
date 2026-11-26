"""Integración en memoria del motor con la Web App (A96, #314).

Servicio (`nutrigraphdt.demo.service`): validación del grafo derivado sin escribir en disco,
corridas con y sin restricciones, ida y vuelta JSON, mensajes de error sin trazas y el recorrido
del catálogo en la página Escenario con `AppTest`. Requiere los extras `graph`, `baselines` y
`demo`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")
pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from streamlit.testing.v1 import AppTest  # noqa: E402

from nutrigraphdt import api  # noqa: E402
from nutrigraphdt.demo import form, service  # noqa: E402
from nutrigraphdt.simulation import SimulationError, load_catalog  # noqa: E402

CATALOG = load_catalog()
SYNTHETIC_RUNS = ["synthetic", "synthetic_constrained"]
TIMEOUT = 300


@pytest.fixture(scope="module")
def engines() -> dict[str, Any]:
    return {run: api.DEMO_RUNS[run].engine() for run in SYNTHETIC_RUNS}


# -- A96-P1: servicio en memoria ----------------------------------------------


@pytest.mark.parametrize("scenario", CATALOG, ids=lambda s: s.id)
def test_prepared_graph_passes_validate_graph(engines: dict[str, Any], scenario: Any) -> None:
    prepared = service.prepare(engines["synthetic"], scenario.request())
    assert prepared.instance["derived_from"] == scenario.base_instance
    assert prepared.nodes and prepared.edges


def test_requests_do_not_write_to_disk(
    engines: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    run_dir = api.DEMO_RUNS["synthetic"].run_dir
    before = {p: p.stat().st_mtime_ns for p in run_dir.iterdir()}
    for scenario in CATALOG:
        service.simulate(engines["synthetic"], "synthetic", scenario.request())
    assert list(tmp_path.iterdir()) == []
    assert {p: p.stat().st_mtime_ns for p in run_dir.iterdir()} == before


def test_constrained_and_unconstrained_runs_are_both_available(engines: dict[str, Any]) -> None:
    infos = {run: engine.loaded.info for run, engine in engines.items()}
    assert infos["synthetic"].get("constraint_lambda", 0.0) in (0.0, None)
    assert infos["synthetic_constrained"]["constraint_lambda"] == 0.1
    assert infos["synthetic_constrained"]["constraint_terms"] == ["d06.hydrogen.propionate_bound"]
    selection = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "reports/constraints/lambda_sweep/synthetic/selection.json"
        ).read_text(encoding="utf-8")
    )
    assert selection["selections"]["homo_sage"]["selected_lambda"] == 0.1


# -- A96-P2: par basal / intervenido y serialización -------------------------


@pytest.mark.parametrize("run", SYNTHETIC_RUNS)
@pytest.mark.parametrize("scenario", CATALOG, ids=lambda s: s.id)
def test_result_round_trips_through_json(engines: dict[str, Any], run: str, scenario: Any) -> None:
    result = service.simulate(engines[run], run, scenario.request())
    text = service.to_json(result)
    assert service.from_json(text) == result
    data = json.loads(text)
    assert data["data_label"] == service.SYNTHETIC_LABEL
    assert data["contract_version"] == "1.0.0"
    assert data["run"] == run and data["run_id"] and data["commit"]
    assert result.comparison.status == scenario.expected_status


# -- A96-P3: errores sin trazas ------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        api.ScenarioContractError(["additive.dose: -1 no puede ser negativo."]),
        form.FormError([form.FieldProblem("Dosis del aditivo", "no puede ser negativo.")]),
        service.ServiceError(["EDG-01: arista inválida"]),
        SimulationError("corridas distintas"),
        ImportError("No module named 'torch'"),
        FileNotFoundError("checkpoint.pt"),
        RuntimeError("detalle interno"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_every_error_class_has_a_message(error: BaseException) -> None:
    title, details = service.user_message(error)
    assert title
    assert "Traceback" not in title + "".join(details)
    if isinstance(error, RuntimeError) and type(error) is RuntimeError:
        assert title == service.UNEXPECTED_MESSAGE
        assert details == []


def test_unknown_base_animal_is_reported(engines: dict[str, Any]) -> None:
    request = api.ScenarioRequest(contract_version="1.0.0", base_instance="synthetic:sample:9999")
    with pytest.raises(api.ScenarioContractError) as error:
        service.simulate(engines["synthetic"], "synthetic", request)
    title, details = service.user_message(error.value)
    assert "contrato" in title and "9999" in details[0]


# -- A96-P4: del catálogo al resultado en la app -----------------------------


def _page() -> None:
    from nutrigraphdt.demo.pages import scenario

    scenario.render()


@pytest.fixture(scope="module")
def app() -> AppTest:
    at = AppTest.from_function(_page, default_timeout=TIMEOUT)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


@pytest.mark.parametrize("scenario", CATALOG, ids=lambda s: s.id)
def test_each_catalog_scenario_gives_the_expected_status_in_the_app(
    app: AppTest, scenario: Any
) -> None:
    app.selectbox(key="ng_catalog").set_value(scenario.id).run()

    assert not app.exception, [str(e.value) for e in app.exception]
    result = app.session_state["ng_result"]
    assert result.comparison.status == scenario.expected_status
    if scenario.expected_status == api.ESTIMABLE:
        assert app.success and "Estimable" in app.success[0].value
        assert not app.warning or "No estimable" not in app.warning[0].value
    else:
        assert not app.success
        assert app.warning and "No estimable" in app.warning[0].value
        assert "Total T" not in " ".join(m.value for m in app.markdown)


def test_switching_run_recomputes_with_the_constrained_model(app: AppTest) -> None:
    app.selectbox(key="ng_catalog").set_value("crude-protein-270").run()
    app.selectbox(key="ng_run_select").set_value("synthetic_constrained").run()

    assert not app.exception
    result = app.session_state["ng_result"]
    assert result.run == "synthetic_constrained"
    assert result.comparison.model.run_id == (
        api.DEMO_RUNS["synthetic_constrained"].engine().model_ref.run_id
    )
