"""Simulador de escenarios: lo que predice una corrida de demostración para un escenario (A81).

La página solo habla con el motor por `nutrigraphdt.api` (#287): arma un `ScenarioRequest`, lo
envía a un `ScenarioEngine` de `DEMO_RUNS` y muestra el `ScenarioResponse` tal como llega. No
calcula nada por su cuenta: si la respuesta es `no_estimable`, no hay números que mostrar.
"""

from __future__ import annotations

import math
from typing import Any

import streamlit as st

from nutrigraphdt import api
from nutrigraphdt.demo import ui

EXAMPLE_MODE = "Escenario de ejemplo"
CUSTOM_MODE = "Escenario propio"
SPLIT_LABELS = {"train": "train", "inner_val": "val interno", "test": "test", "unused": "sin usar"}
COMPONENT_LABELS = {"acetate": "Acetato", "propionate": "Propionato", "butyrate": "n-Butirato"}


@st.cache_resource(show_spinner="Cargando la corrida de demostración (unos segundos)…")
def _engine(run: str) -> Any:
    return api.DEMO_RUNS[run].engine()


def render() -> None:
    ui.hero(
        "Simulador de escenarios",
        "Qué predice el modelo para una instancia que no se observó.",
        "Un escenario parte de un animal y cambia algunas de sus variables de entrada. La "
        "respuesta es la predicción de una corrida congelada de demostración, o «no estimable» "
        "si cae fuera de lo que esa corrida vio en su entrenamiento. Un escenario no es un "
        "efecto causal.",
    )
    run = st.selectbox(
        "Corrida de demostración",
        list(api.DEMO_RUNS),
        format_func=lambda name: api.DEMO_RUNS[name].label,
        key="sim_run",
    )
    demo_run = api.DEMO_RUNS[run]
    kind = ("Datos sintéticos", "synthetic") if demo_run.is_synthetic else ("Datos reales", "real")
    st.markdown(ui.badge(*kind), unsafe_allow_html=True)
    st.caption(demo_run.description + " Modelo de demostración, sin valor científico.")

    try:
        engine = _engine(run)
    except ImportError as error:
        st.error(f"Faltan dependencias para cargar la corrida: {error}")
        return
    except api.ScenarioContractError as error:
        st.error("La corrida no se pudo cargar:\n\n" + _bullets(error.problems))
        return

    mode = st.radio("Escenario", [EXAMPLE_MODE, CUSTOM_MODE], horizontal=True, key="sim_mode")
    try:
        request = _example_request(run) if mode == EXAMPLE_MODE else _custom_request(run, engine)
    except ValueError as error:
        st.error("El escenario no cumple el contrato:\n\n" + _bullets(_problems(error)))
        return
    if request is None:
        return

    try:
        response = engine.predict(request)
        basal = (
            engine.predict(request.model_copy(update={"intervention": ()}))
            if request.intervention
            else None
        )
    except api.ScenarioContractError as error:
        st.error("El motor rechazó el escenario:\n\n" + _bullets(error.problems))
        return
    _show(response, basal, engine)


# ---------------------------------------------------------------------------
# Petición
# ---------------------------------------------------------------------------


def _example_request(run: str) -> Any:
    examples = {s.id: s for s in api.demo_scenarios(run)}
    if not examples:
        st.info("Esta corrida no tiene escenarios de ejemplo.")
        return None
    chosen = examples[
        st.selectbox(
            "Ejemplo",
            list(examples),
            format_func=lambda key: examples[key].label,
            key=f"sim_example_{run}",
        )
    ]
    st.caption(chosen.note)
    return chosen.request


def _custom_request(run: str, engine: Any) -> Any:
    sample_ids = engine.base.sample_ids
    tests = [s for s in sample_ids if engine.split_of(s) == "test"]
    sample_id = st.selectbox(
        "Animal base",
        sample_ids,
        index=sample_ids.index(tests[0]) if tests else 0,
        format_func=lambda s: f"{s} · {SPLIT_LABELS.get(engine.split_of(s), '?')}",
        key=f"sim_base_{run}",
    )
    variables = {v.variable: v for v in engine.variables}
    chosen = st.multiselect(
        "Variables que cambian (vacío: escenario basal)",
        list(variables),
        format_func=lambda name: f"{variables[name].label} ({variables[name].unit})",
        key=f"sim_vars_{run}",
    )
    items = []
    for name in chosen:
        variable = variables[name]
        observed = engine.base.values_of(sample_id, name)
        help_text = "Observado en el animal base: " + (
            ", ".join(map(str, observed)) if observed else "sin valor"
        )
        key = f"sim_value_{run}_{sample_id}_{name}"
        if variable.kind == "numeric":
            default = float(observed[0]) if observed else 0.0
            value: Any = st.number_input(
                f"{variable.label} ({variable.unit})", value=default, help=help_text, key=key
            )
        else:
            options = list(variable.categories)
            current = str(observed[0]) if observed else None
            value = st.selectbox(
                variable.label,
                options,
                index=options.index(current) if current in options else 0,
                help=help_text,
                key=key,
            )
        items.append(api.InterventionItem(variable=name, value=value))
    return api.ScenarioRequest(
        contract_version=api.API_CONTRACT_VERSION,
        base_instance=sample_id,
        intervention=tuple(items),
    )


# ---------------------------------------------------------------------------
# Respuesta
# ---------------------------------------------------------------------------


def _show(response: Any, basal: Any, engine: Any) -> None:
    st.subheader("Resultado")
    st.info(api.CAUSAL_WARNING)
    if response.status == api.ESTIMABLE:
        st.success(
            "Estimable: las fracciones predichas caen dentro del soporte empírico de la corrida."
        )
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
        if basal is not None:
            _basal_table(response, basal)
    else:
        st.warning(
            "No estimable: la predicción cae fuera del soporte empírico de la corrida, así que "
            "no se informan fracciones ni ln T.\n\n" + _bullets(list(response.reasons))
        )
    others = [w for w in response.warnings if w != api.CAUSAL_WARNING]
    if others:
        st.markdown("**Advertencias**\n\n" + _bullets(others))

    left, right = st.columns(2)
    left.markdown("**Soporte empírico aplicado**")
    left.dataframe(
        [
            {
                "AGCC": COMPONENT_LABELS[name],
                "mínimo": f"{response.support.interval[name].lower:.4f}",
                "máximo": f"{response.support.interval[name].upper:.4f}",
            }
            for name in api.SCFA_COMPONENTS
        ],
        hide_index=True,
    )
    left.caption(
        f"{response.support.method}; {response.support.n_animals} animales del "
        f"{response.support.source}."
    )
    right.markdown("**Corrida que predijo**")
    right.dataframe(
        [{"campo": k, "valor": str(v)} for k, v in response.model.model_dump().items()],
        hide_index=True,
    )
    st.caption(
        "Intervalo predictivo: "
        + (
            "no calculado en el contrato v1 (campo reservado para A75)."
            if response.interval is None
            else f"{response.interval.method}, nivel {response.interval.level:.0%}."
        )
    )
    with st.expander("Respuesta del contrato (JSON)"):
        st.json(response.model_dump(mode="json"))


def _basal_table(response: Any, basal: Any) -> None:
    if basal.status != api.ESTIMABLE:
        st.caption("La predicción basal del mismo animal no es estimable.")
        return
    st.dataframe(
        [
            {
                "AGCC": COMPONENT_LABELS[name],
                "basal (predicho)": f"{getattr(basal.fractions, name):.1%}",
                "escenario (predicho)": f"{getattr(response.fractions, name):.1%}",
            }
            for name in api.SCFA_COMPONENTS
        ],
        hide_index=True,
    )
    st.caption(
        "Las dos columnas son predicciones del mismo modelo; su diferencia no es un efecto de "
        "la intervención."
    )


def _problems(error: ValueError) -> list[str]:
    if isinstance(error, api.ScenarioContractError):
        return error.problems
    errors = getattr(error, "errors", None)
    if callable(errors):
        return [f"{'.'.join(map(str, e['loc'])) or 'petición'}: {e['msg']}" for e in errors()]
    return [str(error)]


def _bullets(lines: list[str]) -> str:
    return "\n".join(f"- {line}" for line in lines)


__all__ = ["render"]
