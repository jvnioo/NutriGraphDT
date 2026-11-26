"""Dashboard de resultados (A101, #329): intervalos, panel de métricas y exportación.

Usa las corridas sintéticas congeladas y `AppTest`, sin navegador ni red. Requiere los extras
`graph`, `baselines` y `demo`.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")
pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from streamlit.testing.v1 import AppTest  # noqa: E402

from nutrigraphdt import api  # noqa: E402
from nutrigraphdt.demo import results, service  # noqa: E402
from nutrigraphdt.simulation import scenario_by_id  # noqa: E402

TIMEOUT = 300


@pytest.fixture(scope="module")
def engine() -> Any:
    return api.DEMO_RUNS["synthetic"].engine()


@pytest.fixture(scope="module")
def estimable(engine: Any) -> service.SimulationResult:
    return service.simulate(engine, "synthetic", scenario_by_id("crude-protein-270").request())


@pytest.fixture(scope="module")
def not_estimable(engine: Any) -> service.SimulationResult:
    return service.simulate(engine, "synthetic", scenario_by_id("additive-dose-control").request())


# -- A101-P1: gráfico e intervalos --------------------------------------------


def test_estimable_predictions_carry_an_uncalibrated_mc_dropout_interval(
    estimable: service.SimulationResult,
) -> None:
    for response in (estimable.comparison.basal, estimable.comparison.intervened):
        interval = response.interval
        assert interval is not None
        assert interval.method == "mc_dropout_sin_calibrar" and interval.level == 0.8
        for name in api.SCFA_COMPONENTS:
            bounds = interval.fractions[name]
            assert bounds.lower <= getattr(response.fractions, name) <= bounds.upper
        assert interval.log_total is not None
        assert interval.log_total.lower <= response.log_total <= interval.log_total.upper


def test_interval_is_deterministic(engine: Any) -> None:
    request = scenario_by_id("basal").request()
    assert engine.interval(request) == engine.interval(request)


def test_chart_numbers_match_the_a96_json(estimable: service.SimulationResult) -> None:
    data = json.loads(service.to_json(estimable))["comparison"]
    figure = results.results_figure(estimable)
    for trace in figure.data:
        side = data["basal" if trace.meta["scenario"] == "basal" else "intervened"]
        assert list(trace.y) == [side["fractions"][c] for c in results.COMPONENTS]
        upper = [side["interval"]["fractions"][c]["upper"] for c in results.COMPONENTS]
        assert [y + e for y, e in zip(trace.y, trace.error_y.array, strict=True)] == (
            pytest.approx(upper)
        )
    total = results.results_figure(estimable, ("log_total",))
    assert [t.y[0] for t in total.data] == [
        data["basal"]["log_total"],
        data["intervened"]["log_total"],
    ]


def test_without_interval_no_band_is_drawn(engine: Any) -> None:
    plain = service.simulate(
        engine, "synthetic", scenario_by_id("crude-protein-270").request(), with_interval=False
    )
    assert not results.has_intervals(plain)
    assert all(trace.error_y.array is None for trace in results.results_figure(plain).data)


def test_not_estimable_side_is_not_drawn(not_estimable: service.SimulationResult) -> None:
    figure = results.results_figure(not_estimable)
    assert [trace.meta["scenario"] for trace in figure.data] == ["basal"]
    rows = [r for r in results.chart_rows(not_estimable) if r["scenario"] == "intervenido"]
    assert all(r["value"] is None and r["lower"] is None for r in rows)


# -- A101-P2: panel de métricas ------------------------------------------------


@pytest.mark.parametrize("run", ["synthetic", "synthetic_constrained"])
def test_every_panel_figure_comes_from_a_run_file(run: str) -> None:
    run_dir = api.DEMO_RUNS[run].run_dir
    with (run_dir / "metrics.csv").open(encoding="utf-8", newline="") as handle:
        recorded = {
            r["metric"]: float(r["average"])
            for r in csv.DictReader(handle)
            if r["split"] == "test" and r["group"] == "all"
        }
    rows = results.metric_rows(run_dir)
    assert {r["clave"]: r["promedio"] for r in rows} == pytest.approx(recorded)
    violations = results.violation_rows(run_dir)
    assert violations and all(r["fuente"] == "predictions.csv" for r in violations)
    assert {r["animales de test"] for r in violations} == {4}
    summary = results.training_summary(run_dir)
    assert summary["constraint_lambda"] == (0.1 if run == "synthetic_constrained" else 0.0)


# -- A101-P3: exportación ----------------------------------------------------


def test_exported_json_reloads_without_loss(estimable: service.SimulationResult) -> None:
    assert service.from_json(service.to_json(estimable)) == estimable


@pytest.mark.parametrize("fixture", ["estimable", "not_estimable"])
def test_csv_has_one_row_per_scfa_and_scenario(fixture: str, request: Any) -> None:
    result = request.getfixturevalue(fixture)
    rows = list(csv.DictReader(io.StringIO(results.to_csv(result))))
    assert len(rows) == 8
    assert {(r["escenario"], r["cantidad"]) for r in rows} == {
        (s, q) for s in ("basal", "intervenido") for q in (*results.COMPONENTS, "log_total")
    }
    for row in rows:
        assert row["contrato"] == "1.0.0" and row["run_id"] == result.run_id
        assert row["commit"] == (result.commit or "")
        assert row["rotulo"] == service.SYNTHETIC_LABEL
        if row["estado"] == "no_estimable":
            assert row["valor"] == "" and row["inferior"] == ""


# -- página --------------------------------------------------------------------


def _page() -> None:
    from nutrigraphdt.demo.pages import results as page

    page.render()


def _app(result: Any = None) -> AppTest:
    at = AppTest.from_function(_page, default_timeout=TIMEOUT)
    if result is not None:
        at.session_state["ng_result"] = result
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def test_page_without_result_says_so() -> None:
    at = _app()
    assert at.info and "simule un escenario" in at.info[0].value.lower()


def test_page_shows_chart_panel_and_warnings_together(
    estimable: service.SimulationResult,
) -> None:
    at = _app(estimable)
    warnings = " ".join(w.value for w in at.warning)
    assert "Datos sintéticos" in warnings and "Asociación no es causalidad" in warnings
    assert "No estimable" in warnings
    assert any("sin calibrar" in c.value for c in at.caption)
    assert len(at.dataframe) == 3


def test_page_with_not_estimable_result_has_no_band_for_that_side(
    not_estimable: service.SimulationResult,
) -> None:
    at = _app(not_estimable)
    assert any("No estimable: al menos una" in w.value for w in at.warning)
