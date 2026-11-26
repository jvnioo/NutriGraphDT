"""Suite E2E de la Web App (A105, #338): recorrido completo con `streamlit.testing.v1.AppTest`.

Cada prueba es un caso de `docs/process/e2e-cases.md` (`E2E-NN` en el nombre). Recorre la app
como la usaría una persona: Escenario → Resultados → exportar → Grafo → Explicación, sobre las
corridas sintéticas congeladas y el catálogo de `configs/scenarios/`. Corre sin navegador ni red.

`AppTest.switch_page` solo cambia entre páginas de archivo y las de esta app son funciones: el
script de prueba dibuja la página elegida con el mismo marco que la app (`app.framed`) y la
misma barra lateral, y el estado de sesión es el de una sola sesión durante todo el recorrido.

Uso: `pytest -m e2e`. Requiere los extras `graph`, `baselines` y `demo`.
"""

from __future__ import annotations

import csv
import io
from typing import Any

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")
pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from streamlit.testing.v1 import AppTest  # noqa: E402

from nutrigraphdt import api  # noqa: E402
from nutrigraphdt.demo import layout, results, service  # noqa: E402
from nutrigraphdt.simulation import load_catalog, scenario_by_id  # noqa: E402

pytestmark = pytest.mark.e2e

TIMEOUT = 300
PAGE_KEY = "_e2e_page"


def _app() -> None:
    import streamlit as st

    from nutrigraphdt.demo import app, layout

    specs = {spec.url_path: spec for spec in app.PAGES}
    layout.sidebar()
    app.framed(specs[st.session_state.get("_e2e_page", "inicio")].render)()


class Session:
    """Una sesión de la app: navegar, leer textos y estado."""

    def __init__(self) -> None:
        self.at = AppTest.from_function(_app, default_timeout=TIMEOUT)
        self.at.run()
        self.check()

    def check(self) -> None:
        assert not self.at.exception, [str(e.value) for e in self.at.exception]

    def go(self, page: str) -> Session:
        self.at.session_state[PAGE_KEY] = page
        self.at.run()
        self.check()
        assert layout.SYNTHETIC_LABEL in self.text()
        return self

    def text(self) -> str:
        at = self.at
        parts = [m.value for m in at.markdown] + [c.value for c in at.caption]
        parts += [w.value for w in (*at.info, *at.success, *at.warning, *at.error)]
        return "\n".join(parts)

    def catalog(self, scenario_id: str) -> Session:
        self.go("escenario")
        self.at.radio(key="ng_mode").set_value("Catálogo de referencia").run()
        self.at.selectbox(key="ng_catalog").set_value(scenario_id)
        return self.submit()

    def form(self, **numbers: float) -> Session:
        self.go("escenario")
        self.at.radio(key="ng_mode").set_value("Formulario").run()
        for key, value in numbers.items():
            self.at.number_input(key=key).set_value(value)
        return self.submit()

    def submit(self) -> Session:
        labels = [b.label for b in self.at.button]
        self.at.button[labels.index("Simular escenario")].click().run()
        self.check()
        return self

    @property
    def result(self) -> Any:
        try:
            return self.at.session_state["ng_result"]
        except KeyError:
            return None


# ---------------------------------------------------------------------------
# Recorrido completo
# ---------------------------------------------------------------------------


def test_e2e_01_full_flow_with_a_reference_scenario() -> None:
    """Abrir, elegir un escenario de referencia, simular, ver resultados, exportar, grafo y
    explicación."""
    session = Session()
    assert "Corrida activa" in [s.value for s in session.at.subheader]

    session.catalog("crude-protein-270")
    result = session.result
    assert result.comparison.status == "estimable"
    assert session.at.success and "Estimable" in session.at.success[0].value

    session.go("resultados")
    assert any("**calibrado**" in c.value for c in session.at.caption)
    assert "Asociación no es causalidad" in session.text()
    exported = service.to_json(result)
    assert service.from_json(exported) == result
    rows = list(csv.DictReader(io.StringIO(results.to_csv(result))))
    assert len(rows) == 8 and {r["rotulo"] for r in rows} == {service.SYNTHETIC_LABEL}

    session.go("grafo")
    assert "Escenario de la página Escenario" in session.text()
    assert "de 10 taxones" in session.text()

    session.go("explicacion")
    assert "GNNExplainer" in session.text()
    assert "Asociación no es causalidad" in session.text()


@pytest.mark.parametrize("scenario", load_catalog(), ids=lambda s: s.id)
def test_e2e_02_every_reference_scenario_gives_its_expected_status(scenario: Any) -> None:
    session = Session().catalog(scenario.id)
    assert session.result.comparison.status == scenario.expected_status
    session.go("resultados")
    if scenario.expected_status == api.NOT_ESTIMABLE:
        assert "No estimable: al menos una" in session.text()


# ---------------------------------------------------------------------------
# Bordes
# ---------------------------------------------------------------------------


def test_e2e_03_dose_zero_from_the_form_is_not_estimable_and_shows_no_numbers() -> None:
    session = Session().form(ng_form_dose=0.0)
    assert session.result.comparison.status == api.NOT_ESTIMABLE
    assert not session.at.success
    assert "Total T" not in session.text()
    session.go("resultados")
    rows = [r for r in results.chart_rows(session.result) if r["scenario"] == "intervenido"]
    assert all(r["value"] is None for r in rows)


@pytest.mark.parametrize(
    ("value", "status"),
    [(195.0, "estimable"), (270.0, "estimable")],
    ids=["min-dictionary", "max-dictionary"],
)
def test_e2e_04_extreme_dictionary_protein_values(value: float, status: str) -> None:
    session = Session().form(**{"ng_form_diet_diet.composition.crude_protein": value})
    assert session.result.comparison.status == status
    assert "no se observó en el train" in session.text()


def test_e2e_05_out_of_support_from_the_catalog() -> None:
    session = Session().catalog("additive-dose-control")
    comparison = session.result.comparison
    assert comparison.status == api.NOT_ESTIMABLE
    assert comparison.differences == ()
    assert all(r.startswith("intervenido:") for r in comparison.reasons)


def test_e2e_06_invalid_input_names_the_field_and_keeps_the_previous_result() -> None:
    session = Session().catalog("basal")
    previous = session.result
    session.form(ng_form_dose=-1.0)
    assert session.at.error and "Dosis del aditivo" in session.at.error[0].value
    assert "Traceback" not in session.text()
    assert session.result == previous


def test_e2e_07_empty_intervention_is_the_basal_with_zero_difference() -> None:
    session = Session().form()
    comparison = session.result.comparison
    assert comparison.intervened.request.intervention == ()
    assert all(d.difference == 0.0 for d in comparison.differences)
    assert "ninguna (basal)" in session.text()


def test_e2e_08_reloading_a_page_keeps_the_scenario_and_result() -> None:
    session = Session().catalog("crude-protein-195")
    result = session.result
    session.go("resultados")
    session.at.run()
    session.check()
    assert session.result == result
    session.go("escenario")
    assert session.result == result


def test_e2e_09_switching_to_the_constrained_run_recomputes() -> None:
    session = Session().catalog("crude-protein-270")
    session.at.selectbox(key="ng_run_select").set_value("synthetic_constrained").run()
    session.check()
    assert session.result.run == "synthetic_constrained"
    expected = scenario_by_id("crude-protein-270").expected_status
    assert session.result.comparison.status == expected


def test_e2e_10_reset_clears_the_session() -> None:
    session = Session().catalog("crude-protein-270")
    session.at.button(key="reset_state").click().run()
    session.check()
    assert session.result is None
    session.go("resultados")
    assert "Aún no hay resultado" in session.text()


def test_e2e_11_every_page_opens_without_a_scenario() -> None:
    session = Session()
    for page in ("inicio", "escenario", "resultados", "grafo", "explicacion", "comparacion"):
        session.go(page)
