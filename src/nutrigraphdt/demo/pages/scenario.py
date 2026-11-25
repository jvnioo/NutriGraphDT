"""Página Escenario: formulario de dieta, aditivo y parámetros (A90, #302).

El formulario (`nutrigraphdt.demo.form`) arma un `ScenarioRequest` y lo guarda en el estado de
sesión; la página lo envía al motor en caché de la corrida activa y muestra la respuesta tal como
llega. Si la respuesta es `no_estimable`, no hay números que mostrar.
"""

from __future__ import annotations

import math
from typing import Any

import streamlit as st

from nutrigraphdt import api
from nutrigraphdt.demo import cache, state, ui
from nutrigraphdt.demo import form as scenario_form

SUBMIT_LABEL = "Simular escenario"
COMPONENT_LABELS = {"acetate": "Acetato", "propionate": "Propionato", "butyrate": "n-Butirato"}
SPLIT_LABELS = {"train": "train", "inner_val": "val interno", "test": "test", "unused": "sin usar"}
NOT_ESTIMABLE_TEXT = (
    "No estimable: la predicción cae fuera del soporte empírico de la corrida (lo que vio en su "
    "entrenamiento), así que no se informan fracciones ni total."
)


def render() -> None:
    ui.hero(
        "Escenario",
        "Animal base, dieta, aditivo y parámetros.",
        "El formulario parte de un animal de la cohorte sintética, prellenado con sus valores. "
        "Cambie los que quiera simular: solo los que cambian quedan declarados como intervención. "
        "La predicción es la de la corrida congelada activa, o «no estimable» si cae fuera de lo "
        "que esa corrida vio.",
        badges=[("Datos sintéticos", "synthetic")],
    )
    try:
        engine = cache.engine(cache.active_run())
    except ImportError as error:
        st.error(f"Faltan dependencias para cargar la corrida: {error}")
        return
    except api.ScenarioContractError as error:
        st.error("La corrida no se pudo cargar:\n\n" + _bullets(error.problems))
        return

    request = _form(engine)
    if request is not None:
        state.set_scenario(request)
    current = state.scenario()
    if current is None:
        st.caption("Envíe el formulario para simular el escenario.")
        return
    try:
        response = engine.predict(current)
    except api.ScenarioContractError as error:
        st.error("El motor rechazó el escenario:\n\n" + _bullets(error.problems))
        return
    show_response(response)


def _form(engine: Any) -> Any:
    sample_ids = engine.base.sample_ids
    tests = [s for s in sample_ids if engine.split_of(s) == "test"]
    sample_id = st.selectbox(
        "Animal base",
        sample_ids,
        index=sample_ids.index(tests[0]) if tests else 0,
        format_func=lambda s: f"{s} · {SPLIT_LABELS.get(engine.split_of(s), '?')}",
        key="ng_form_base",
    )
    defaults = scenario_form.form_defaults(engine, sample_id)
    options = scenario_form.additive_options()
    categories = [o.category for o in options]
    by_category = {o.category: o for o in options}
    with st.form(key=f"ng_form_{sample_id}"):
        left, right = st.columns(2)
        species = left.selectbox("Especie", defaults.species_options, key="ng_form_species")
        segment = right.selectbox("Segmento", defaults.segment_options, key="ng_form_segment")
        st.caption(scenario_form.SPECIES_NOTE)

        st.markdown("**Dieta basal**")
        diet = _numeric(defaults.diet, "diet")
        st.markdown("**Aditivo**")
        left, right = st.columns(2)
        category = left.selectbox(
            "Aditivo",
            categories,
            index=categories.index(defaults.additive_category)
            if defaults.additive_category in categories
            else 0,
            format_func=lambda c: by_category[c].label,
            key="ng_form_additive",
        )
        dose = right.number_input(
            f"Dosis ({scenario_form.UNIT_LABELS.get(defaults.dose_unit, defaults.dose_unit)})",
            value=defaults.dose,
            format="%g",
            help=f"La unidad la fija el aditivo. Observado en el animal base: {defaults.dose:g}.",
            key="ng_form_dose",
        )
        st.markdown("**Huésped**")
        host = _numeric(defaults.host, "host")
        submitted = st.form_submit_button(SUBMIT_LABEL)
    if not submitted:
        return None
    try:
        return scenario_form.build_request(
            engine,
            scenario_form.FormInput(
                base_instance=sample_id,
                species=species,
                segment=segment,
                diet=diet,
                host=host,
                additive_category=category,
                dose=dose,
            ),
        )
    except scenario_form.FormError as error:
        st.error("El escenario no es válido:\n\n" + _bullets([str(p) for p in error.problems]))
        return None


def _numeric(fields: tuple[scenario_form.NumericField, ...], group: str) -> dict[str, float]:
    values: dict[str, float] = {}
    columns = st.columns(3)
    for index, field in enumerate(fields):
        values[field.variable] = columns[index % 3].number_input(
            f"{field.label.split(' · ')[-1]} ({field.unit_label})",
            value=field.value,
            format="%g",
            help=f"Observado en el animal base: {field.value:g} {field.unit_label}.",
            key=f"ng_form_{group}_{field.variable}",
        )
    return values


def show_response(response: Any) -> None:
    """Respuesta del motor: fracciones y total si es estimable; motivos, sin cifras, si no."""
    st.subheader("Predicción")
    st.info(api.CAUSAL_WARNING)
    declared = [f"{i.variable} = {i.value}" for i in response.request.intervention]
    st.caption(
        "Intervención declarada: " + (", ".join(declared) if declared else "ninguna (basal).")
    )
    if response.status == api.ESTIMABLE:
        st.success("Estimable: la predicción cae dentro del soporte empírico de la corrida.")
        fractions = response.fractions
        ui.metric_cards(
            [
                *(
                    (COMPONENT_LABELS[name], f"{getattr(fractions, name):.1%}", "fracción molar")
                    for name in api.SCFA_COMPONENTS
                ),
                ("Total T", f"{math.exp(response.log_total):.1f}", "mmol/kg de digesta"),
            ]
        )
    else:
        st.warning(NOT_ESTIMABLE_TEXT + "\n\n" + _bullets(list(response.reasons)))
    others = [w for w in response.warnings if w != api.CAUSAL_WARNING]
    if others:
        st.markdown("**Advertencias**\n\n" + _bullets(others))


def _bullets(lines: list[str]) -> str:
    return "\n".join(f"- {line}" for line in lines)


__all__ = ["NOT_ESTIMABLE_TEXT", "SUBMIT_LABEL", "render", "show_response"]
