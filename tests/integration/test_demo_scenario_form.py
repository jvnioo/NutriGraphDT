"""Formulario del escenario (A90, #302): valores ofrecidos, prellenado y cada regla de validación.

Usa la corrida sintética congelada; corre sin navegador ni red. Requiere los extras `graph`,
`baselines` y `demo`.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")
pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from streamlit.testing.v1 import AppTest  # noqa: E402

from nutrigraphdt import api  # noqa: E402
from nutrigraphdt.data.synthetic.nodes import additive_catalog, diet_catalog  # noqa: E402
from nutrigraphdt.demo import form  # noqa: E402

BASE = "synthetic:sample:0017"
PROTEIN = "diet.composition.crude_protein"
TIMEOUT = 300


@pytest.fixture(scope="module")
def engine() -> Any:
    return api.DEMO_RUNS["synthetic"].engine()


@pytest.fixture(scope="module")
def defaults(engine: Any) -> form.FormDefaults:
    return form.form_defaults(engine, BASE)


def _input(defaults: form.FormDefaults, **changes: Any) -> form.FormInput:
    return dataclasses.replace(form.default_input(defaults), **changes)


def _problems(engine: Any, value: form.FormInput) -> list[form.FieldProblem]:
    with pytest.raises(form.FormError) as error:
        form.build_request(engine, value)
    return error.value.problems


# -- valores ofrecidos y prellenado ------------------------------------------


def test_only_values_the_run_knows_are_offered(engine: Any, defaults: form.FormDefaults) -> None:
    assert defaults.species_options == ("chicken",)
    assert defaults.segment_options == ("cecum",)
    vocabulary = set(engine.base.variables)
    assert {f.variable for f in (*defaults.diet, *defaults.host)} <= vocabulary
    assert defaults.admitted_additives == ("probiotic",)


def test_prefilled_values_match_the_base_instance(engine: Any, defaults: form.FormDefaults) -> None:
    for field in (*defaults.diet, *defaults.host):
        observed = tuple(float(v) for v in engine.base.values_of(BASE, field.variable))
        assert (field.value,) == observed
    assert defaults.dose == engine.base.values_of(BASE, form.DOSE_VARIABLE)[0]
    assert defaults.dose_unit == "CFU_kg"


def test_diet_components_and_units_come_from_the_dictionary(defaults: form.FormDefaults) -> None:
    dictionary = {c["component_id"]: c["unit"] for c in diet_catalog()[0]["composition"]}
    for field in defaults.diet:
        component = field.variable.removeprefix(form.DIET_PREFIX)
        assert dictionary[component] == field.unit


def test_additives_and_dose_units_come_from_the_dictionary() -> None:
    options = form.additive_options()
    assert [(o.category, o.dose_unit) for o in options] == [
        (e["category"], e["dose_unit"]) for e in additive_catalog()
    ]


def test_defaults_give_a_valid_basal_request(engine: Any, defaults: form.FormDefaults) -> None:
    request = form.build_request(engine, form.default_input(defaults))
    assert isinstance(request, api.ScenarioRequest)
    assert request.base_instance == BASE
    assert request.intervention == ()


def test_only_changed_variables_are_declared(engine: Any, defaults: form.FormDefaults) -> None:
    diet = {**form.default_input(defaults).diet, PROTEIN: 270.0}
    request = form.build_request(engine, _input(defaults, diet=diet))
    assert [(i.variable, i.value) for i in request.intervention] == [(PROTEIN, 270.0)]


def test_dose_zero_is_a_valid_request(engine: Any, defaults: form.FormDefaults) -> None:
    request = form.build_request(engine, _input(defaults, dose=0.0))
    assert [(i.variable, i.value) for i in request.intervention] == [("additive.dose", 0.0)]


# -- cada regla tiene una prueba que la hace fallar --------------------------


@pytest.mark.parametrize("dose", [-1.0, math.inf, math.nan])
def test_negative_or_non_finite_dose_is_rejected(
    engine: Any, defaults: form.FormDefaults, dose: float
) -> None:
    problems = _problems(engine, _input(defaults, dose=dose))
    assert problems and problems[0].field == "Dosis del aditivo"


def test_non_numeric_dose_is_rejected(engine: Any, defaults: form.FormDefaults) -> None:
    problems = _problems(engine, _input(defaults, dose="mucho"))
    assert problems[0].field == "Dosis del aditivo"
    assert "número" in problems[0].message


@pytest.mark.parametrize("category", ["prebiotic", "phytogenic", "organic_acid", "control"])
def test_additive_with_another_unit_is_rejected(
    engine: Any, defaults: form.FormDefaults, category: str
) -> None:
    problems = _problems(engine, _input(defaults, additive_category=category))
    assert problems[0].field == "Aditivo"
    assert "UFC/kg" in problems[0].message


def test_unknown_additive_is_rejected(engine: Any, defaults: form.FormDefaults) -> None:
    problems = _problems(engine, _input(defaults, additive_category="otro"))
    assert problems[0].field == "Aditivo"


def test_diet_component_above_one_kilogram_is_rejected(
    engine: Any, defaults: form.FormDefaults
) -> None:
    diet = {**form.default_input(defaults).diet, PROTEIN: 1500.0}
    problems = _problems(engine, _input(defaults, diet=diet))
    assert problems[0].field == "Dieta · Proteína bruta"
    assert "1000" in problems[0].message


def test_negative_diet_component_is_rejected(engine: Any, defaults: form.FormDefaults) -> None:
    diet = {**form.default_input(defaults).diet, PROTEIN: -5.0}
    problems = _problems(engine, _input(defaults, diet=diet))
    assert problems[0].field == "Dieta · Proteína bruta"
    assert "negativo" in problems[0].message


def test_undeclared_variable_is_rejected(engine: Any, defaults: form.FormDefaults) -> None:
    diet = {**form.default_input(defaults).diet, "diet.composition.lysine": 10.0}
    problems = _problems(engine, _input(defaults, diet=diet))
    assert "no es un campo" in problems[0].message


@pytest.mark.parametrize("field", ["species", "segment"])
def test_unknown_species_or_segment_is_rejected(
    engine: Any, defaults: form.FormDefaults, field: str
) -> None:
    problems = _problems(engine, _input(defaults, **{field: "pig"}))
    assert problems[0].field in {"Especie", "Segmento"}


def test_extra_fields_are_rejected_by_the_contract() -> None:
    with pytest.raises(ValueError, match="Extra inputs"):
        api.ScenarioRequest.model_validate(
            {"contract_version": "1.0.0", "base_instance": BASE, "extra": 1}
        )


def test_every_problem_names_field_and_reason(engine: Any, defaults: form.FormDefaults) -> None:
    for problem in _problems(engine, _input(defaults, additive_category="prebiotic")):
        assert problem.field and problem.message
        assert str(problem).startswith(f"{problem.field}: ")


# -- envío con AppTest --------------------------------------------------------


def _page() -> None:
    from nutrigraphdt.demo.pages import scenario

    scenario.render()


def _app() -> AppTest:
    at = AppTest.from_function(_page, default_timeout=TIMEOUT)
    at.run()
    at.radio(key="ng_mode").set_value("Formulario").run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _submit(at: AppTest) -> AppTest:
    at.button[0].click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def test_submitting_the_defaults_predicts_the_basal() -> None:
    at = _submit(_app())
    assert at.success and "Estimable" in at.success[0].value
    assert any("ninguna (basal)" in c.value for c in at.caption)
    assert at.session_state["ng_scenario"].intervention == ()


def test_not_estimable_response_shows_no_numbers() -> None:
    at = _app()
    at.number_input(key="ng_form_dose").set_value(0.0)
    _submit(at)
    assert not at.success
    assert at.warning and "No estimable" in at.warning[0].value
    text = " ".join(m.value for m in at.markdown)
    assert "Total T" not in text and "fracción molar" not in text


def test_invalid_input_names_the_field() -> None:
    at = _app()
    at.number_input(key="ng_form_dose").set_value(-1.0)
    _submit(at)
    assert at.error and "Dosis del aditivo" in at.error[0].value
    assert "ng_scenario" not in at.session_state
