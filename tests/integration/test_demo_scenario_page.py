"""Página «Simulador de escenarios» de la demo (A81): se dibuja y muestra lo que dice el motor.

Usa `streamlit.testing.v1.AppTest`, que ejecuta la página sin navegador, con las corridas de
`tests/fixtures/api/`. Requiere los extras `graph`, `baselines` y `demo`.
"""

from __future__ import annotations

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")
pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from streamlit.testing.v1 import AppTest  # noqa: E402

TIMEOUT = 300


def _page() -> None:
    from nutrigraphdt.demo.pages import scenario_simulator

    scenario_simulator.render()


@pytest.fixture
def app() -> AppTest:
    at = AppTest.from_function(_page, default_timeout=TIMEOUT)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _text(at: AppTest) -> str:
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption]
    parts += [w.value for w in (*at.info, *at.success, *at.warning, *at.error)]
    return "\n".join(parts)


def test_opens_on_a_synthetic_estimable_example(app: AppTest) -> None:
    assert app.selectbox(key="sim_run").value == "synthetic"
    assert app.selectbox(key="sim_example_synthetic").value == "synthetic-basal"
    assert app.success and "Estimable" in app.success[0].value
    text = _text(app)
    assert "no un efecto causal" in text
    assert "Datos sintéticos" in text
    assert "Total T" in text


def test_not_estimable_example_shows_no_numbers(app: AppTest) -> None:
    app.selectbox(key="sim_example_synthetic").set_value("synthetic-no-additive").run()

    assert not app.exception
    assert not app.success
    assert app.warning and "No estimable" in app.warning[0].value
    assert "fuera de" in app.warning[0].value
    assert "Total T" not in _text(app)
    assert "fracción molar" not in _text(app)


def test_custom_scenario_warns_about_unseen_inputs(app: AppTest) -> None:
    app.radio(key="sim_mode").set_value("Escenario propio").run()
    app.multiselect(key="sim_vars_synthetic").set_value(["diet.composition.crude_protein"]).run()
    app.number_input[0].set_value(190.0).run()

    assert not app.exception
    text = _text(app)
    assert "crude_protein = 190.0 no se observó en el train" in text
    assert "basal (predicho)" in str([d.value for d in app.dataframe])


def test_custom_scenario_shows_the_contract_errors(app: AppTest) -> None:
    app.radio(key="sim_mode").set_value("Escenario propio").run()
    app.multiselect(key="sim_vars_synthetic").set_value(["additive.dose"]).run()
    app.number_input[0].set_value(-1.0).run()

    assert not app.exception
    assert app.error and "no puede ser negativo" in app.error[0].value
    assert not app.success


def test_d1_run_is_labelled_real_and_partial(app: AppTest) -> None:
    app.selectbox(key="sim_run").set_value("d1_fixture").run()

    assert not app.exception
    text = _text(app)
    assert "Datos reales" in text
    assert "3 de las 11 relaciones" in text
    assert app.selectbox(key="sim_example_d1_fixture").value == "d1-basal"


def test_d1_breed_example_is_not_estimable(app: AppTest) -> None:
    app.selectbox(key="sim_run").set_value("d1_fixture").run()
    app.selectbox(key="sim_example_d1_fixture").set_value("d1-breed-cobb").run()

    assert app.warning and "No estimable" in app.warning[0].value
    assert not app.success
