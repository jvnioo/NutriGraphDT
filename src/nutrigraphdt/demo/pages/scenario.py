"""Página Escenario: formulario, catálogo y comparación basal / intervenido (A90 y A96).

El formulario (`nutrigraphdt.demo.form`, A90) o el catálogo (`configs/scenarios/`, A93) arman un
`ScenarioRequest` y lo guardan en el estado de sesión. La página lo envía al servicio en memoria
(`nutrigraphdt.demo.service`, A96), que predice el escenario y el basal del mismo animal con el
motor en caché de la corrida elegida, y guarda el resultado. Si la comparación es `no_estimable`,
no hay números que mostrar. Ningún error del motor llega como traza.
"""

from __future__ import annotations

import math
from typing import Any

import streamlit as st

from nutrigraphdt import api
from nutrigraphdt.demo import cache, service, state, ui
from nutrigraphdt.demo import form as scenario_form
from nutrigraphdt.simulation import load_catalog

SUBMIT_LABEL = "Simular escenario"
CATALOG_MODE = "Catálogo de referencia"
FORM_MODE = "Formulario"
QUANTITY_LABELS = {
    "acetate": "Acetato",
    "propionate": "Propionato",
    "butyrate": "n-Butirato",
    "log_total": "ln T",
}
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
        "Elija un escenario del catálogo de referencia o arme uno con el formulario, prellenado "
        "con los valores del animal base: solo los que cambian quedan declarados como "
        "intervención. La corrida congelada predice el escenario y el basal del mismo animal con "
        "el mismo modelo; si una predicción cae fuera de lo que la corrida vio, es «no estimable».",
        badges=[("Datos sintéticos", "synthetic")],
    )
    run = _run()
    try:
        engine = cache.engine(run)
    except Exception as error:  # noqa: BLE001 - toda falla del motor llega como mensaje
        _error(error)
        return

    current = state.scenario()
    from_catalog = current is None or any(s.request() == current for s in load_catalog())
    mode = st.radio(
        "Escenario",
        [CATALOG_MODE, FORM_MODE],
        index=0 if from_catalog else 1,
        horizontal=True,
        key="ng_mode",
    )
    request = _catalog() if mode == CATALOG_MODE else _form(engine)
    if request is not None:
        state.set_scenario(request)
    current = state.scenario()
    if current is None:
        st.caption("Envíe el formulario para simular el escenario.")
        return
    result = state.result()
    if result is None or result.run != run or result.comparison.intervened.request != current:
        try:
            result = service.simulate(engine, run, current)
        except Exception as error:  # noqa: BLE001 - toda falla del motor llega como mensaje
            _error(error)
            return
        state.set_result(result)
    show_result(result)


def _run() -> str:
    runs = [name for name, run in api.DEMO_RUNS.items() if run.is_synthetic]
    active = state.get(state.ACTIVE_RUN) or cache.active_run()
    run = st.selectbox(
        "Corrida",
        runs,
        index=runs.index(active) if active in runs else 0,
        format_func=lambda name: api.DEMO_RUNS[name].label,
        key="ng_run_select",
    )
    if run != state.get(state.ACTIVE_RUN):
        state.put(state.ACTIVE_RUN, run)
        state.set_result(None)
    st.caption(api.DEMO_RUNS[run].description + " Modelo de demostración, sin valor científico.")
    return str(run)


def _catalog() -> Any:
    """Escenario del catálogo; solo se simula al enviar (A105: no pisa el de la sesión)."""
    scenarios = {s.id: s for s in load_catalog()}
    ids = list(scenarios)
    current = state.scenario()
    matching = [i for i, s in enumerate(scenarios.values()) if s.request() == current]
    with st.form(key="ng_catalog_form"):
        chosen = scenarios[
            st.selectbox(
                "Escenario del catálogo",
                ids,
                index=matching[0] if matching else 0,
                format_func=lambda key: scenarios[key].label,
                key="ng_catalog",
            )
        ]
        st.caption(chosen.description)
        submitted = st.form_submit_button(SUBMIT_LABEL)
    return chosen.request() if submitted else None


def _error(error: BaseException) -> None:
    title, details = service.user_message(error)
    st.error(title + (":\n\n" + _bullets(details) if details else "."))


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


def show_result(result: Any) -> None:
    """Basal frente a intervenido por AGCC, o «no estimable» con sus motivos y sin cifras."""
    comparison = result.comparison
    response = comparison.intervened
    st.subheader("Predicción")
    st.info(api.CAUSAL_WARNING)
    declared = [f"{i.variable} = {i.value}" for i in response.request.intervention]
    st.caption(
        "Intervención declarada: " + (", ".join(declared) if declared else "ninguna (basal).")
    )
    if comparison.status == api.ESTIMABLE:
        st.success("Estimable: el basal y el escenario caen dentro del soporte de la corrida.")
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
        st.dataframe(
            [
                {
                    "cantidad": QUANTITY_LABELS[d.quantity],
                    "basal": f"{d.basal:.4f}",
                    "escenario": f"{d.intervened:.4f}",
                    "diferencia": f"{d.difference:+.4f}",
                    "unidad de la diferencia": d.difference_unit,
                }
                for d in comparison.differences
            ],
            hide_index=True,
            key="ng_result_table",
        )
    else:
        st.warning(NOT_ESTIMABLE_TEXT + "\n\n" + _bullets(list(comparison.reasons)))
    others = [w for w in comparison.warnings if w != api.CAUSAL_WARNING]
    if others:
        st.markdown("**Advertencias**\n\n" + _bullets(others))
    st.caption(
        f"Corrida `{result.run_id}` · checkpoint `{comparison.checkpoint_sha256[:12]}` · "
        f"{result.elapsed_seconds * 1000:.0f} ms"
    )
    st.download_button(
        "Descargar resultado (JSON)",
        service.to_json(result),
        file_name="nutrigraphdt-escenario.json",
        mime="application/json",
        key="ng_download_json",
    )


def _bullets(lines: list[str]) -> str:
    return "\n".join(f"- {line}" for line in lines)


__all__ = [
    "CATALOG_MODE",
    "FORM_MODE",
    "NOT_ESTIMABLE_TEXT",
    "SUBMIT_LABEL",
    "render",
    "show_result",
]
