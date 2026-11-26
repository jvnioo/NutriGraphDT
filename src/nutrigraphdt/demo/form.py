"""Formulario del escenario: animal base, dieta basal, aditivo y dosis (A90, #302), sin Streamlit.

`form_defaults` prellena el formulario con la instancia base de la corrida activa y solo ofrece
valores que la corrida conoce: la especie y el segmento de su cohorte, los componentes de la dieta
y las covariables del huésped de su vocabulario, y los aditivos del catálogo sintético con la
unidad de dosis que fija cada uno.

`build_request` convierte lo que el usuario llenó en un `ScenarioRequest` del contrato de
`nutrigraphdt.api`. Las reglas de validación **no se escriben aquí**: los valores pasan por los
modelos Pydantic del contrato (`InterventionItem`, `ScenarioRequest`) y por
`ScenarioBase.derive`, que aplica las del motor (vocabulario, número, no negativo, cota de g/kg).
El formulario solo traduce cada error a `FieldProblem` (campo y motivo). La única regla propia es
del formulario: el aditivo elegido debe ser uno que la corrida admite, porque la unidad de la dosis
la fija el aditivo y el contrato no tiene una variable para cambiarlo.

El formulario no llama al motor para predecir: arma la petición. Solo se declaran en
`intervention` las variables que cambian respecto de la instancia base (contrato de datos v2,
INS-06 e INS-07).

**Datos sintéticos.** La especie (`chicken`) y el segmento (`cecum`) son marcadores provisionales
del generador DS-01, no una población.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

from pydantic import ValidationError

from nutrigraphdt.api.contract import (
    API_CONTRACT_VERSION,
    InterventionItem,
    ScenarioContractError,
    ScenarioRequest,
)
from nutrigraphdt.data.derived import DIET_COMPOSITION_PREFIX

DOSE_VARIABLE: Final[str] = "additive.dose"
DIET_PREFIX: Final[str] = f"diet.{DIET_COMPOSITION_PREFIX}"
HOST_PREFIX: Final[str] = "host.covariates."

COMPONENT_LABELS: Final[dict[str, str]] = {
    "crude_protein": "Proteína bruta",
    "crude_fiber": "Fibra bruta",
    "crude_fat": "Grasa bruta",
    "metabolizable_energy": "Energía metabolizable",
    "calcium": "Calcio",
    "total_phosphorus": "Fósforo total",
}
HOST_LABELS: Final[dict[str, str]] = {
    "age_days": "Edad",
    "body_weight_g": "Peso corporal",
    "sex": "Sexo",
}
ADDITIVE_LABELS: Final[dict[str, str]] = {
    "probiotic": "Probiótico",
    "prebiotic": "Prebiótico",
    "phytogenic": "Fitogénico",
    "organic_acid": "Ácido orgánico",
    "control": "Control (sin aditivo)",
}
UNIT_LABELS: Final[dict[str, str]] = {
    "g_kg": "g/kg",
    "MJ_kg": "MJ/kg",
    "CFU_kg": "UFC/kg",
    "mg_kg": "mg/kg",
    "d": "días",
    "g": "g",
}
SPECIES_NOTE: Final[str] = (
    "Especie y segmento son marcadores provisionales del generador sintético (DS-01), no una "
    "población: la corrida solo conoce estos valores."
)


@dataclass(frozen=True)
class FieldProblem:
    """Un rechazo del formulario: qué campo y por qué."""

    field: str
    message: str

    def __str__(self) -> str:
        return f"{self.field}: {self.message}"


class FormError(ValueError):
    """El formulario no produce una petición válida; `problems` nombra cada campo."""

    def __init__(self, problems: list[FieldProblem]) -> None:
        self.problems = problems
        super().__init__("Formulario inválido:\n- " + "\n- ".join(map(str, problems)))


@dataclass(frozen=True)
class AdditiveOption:
    """Aditivo del catálogo sintético con la unidad de dosis que fija."""

    category: str
    substance: str
    dose: float
    dose_unit: str

    @property
    def label(self) -> str:
        unit = UNIT_LABELS.get(self.dose_unit, self.dose_unit)
        return f"{ADDITIVE_LABELS.get(self.category, self.category)} · {self.substance} ({unit})"


def additive_options() -> list[AdditiveOption]:
    """Los aditivos del catálogo sintético, en su orden."""
    from nutrigraphdt.data.synthetic.nodes import additive_catalog

    return [
        AdditiveOption(
            category=str(entry["category"]),
            substance=str(entry["substance"]),
            dose=float(entry["dose"]),
            dose_unit=str(entry["dose_unit"]),
        )
        for entry in additive_catalog()
    ]


@dataclass(frozen=True)
class NumericField:
    """Campo numérico del formulario: variable del contrato, rótulo, unidad y valor base."""

    variable: str
    label: str
    unit: str
    value: float

    @property
    def unit_label(self) -> str:
        return UNIT_LABELS.get(self.unit, self.unit)


@dataclass(frozen=True)
class FormDefaults:
    """Lo que el formulario ofrece y sus valores prellenados para un animal base."""

    base_instance: str
    species_options: tuple[str, ...]
    segment_options: tuple[str, ...]
    species: str
    segment: str
    diet: tuple[NumericField, ...]
    host: tuple[NumericField, ...]
    additive_category: str
    dose: float
    dose_unit: str
    admitted_additives: tuple[str, ...]
    """Categorías de aditivo cuya unidad de dosis admite la corrida."""


@dataclass
class FormInput:
    """Lo que el usuario llenó."""

    base_instance: str
    species: str
    segment: str
    diet: dict[str, float] = field(default_factory=dict)
    """Valor por variable `diet.composition.<componente>`."""
    host: dict[str, float] = field(default_factory=dict)
    """Valor por variable `host.covariates.<covariable>`."""
    additive_category: str = ""
    dose: Any = None


def _label(variable: str) -> str:
    if variable.startswith(DIET_PREFIX):
        name = variable.removeprefix(DIET_PREFIX)
        return f"Dieta · {COMPONENT_LABELS.get(name, name)}"
    if variable.startswith(HOST_PREFIX):
        name = variable.removeprefix(HOST_PREFIX)
        return f"Huésped · {HOST_LABELS.get(name, name)}"
    if variable == DOSE_VARIABLE:
        return "Dosis del aditivo"
    return variable


def _first(values: tuple[Any, ...]) -> Any:
    return values[0] if values else None


def form_defaults(engine: Any, sample_id: str) -> FormDefaults:
    """Opciones y valores prellenados del formulario para el animal `sample_id`.

    Raises:
        ScenarioContractError: si el animal no existe en la base de la corrida.
    """
    base = engine.base
    instance = base.instance(sample_id)
    variables = base.variables

    def numeric(prefix: str) -> tuple[NumericField, ...]:
        fields = []
        for name, variable in variables.items():
            if not name.startswith(prefix) or variable.kind != "numeric":
                continue
            value = _first(base.values_of(sample_id, name))
            if value is None:
                continue
            fields.append(NumericField(name, _label(name), variable.unit, float(value)))
        return tuple(fields)

    graph_id = str(instance["graph_id"])
    additive = next(
        (n for n in base.records_of(graph_id)["nodes"] if n["node_type"] == "additive"), None
    )
    attributes = (additive or {}).get("attributes") or {}
    dose_variable = variables.get(DOSE_VARIABLE)
    admitted = tuple(
        option.category
        for option in additive_options()
        if dose_variable is not None
        and option.dose_unit == dose_variable.unit
        and option.category == attributes.get("category")
    )
    return FormDefaults(
        base_instance=sample_id,
        species_options=tuple(sorted({str(i["species"]) for i in base.instances})),
        segment_options=tuple(sorted({str(i["gut_segment"]) for i in base.instances})),
        species=str(instance["species"]),
        segment=str(instance["gut_segment"]),
        diet=numeric(DIET_PREFIX),
        host=numeric(HOST_PREFIX),
        additive_category=str(attributes.get("category", "")),
        dose=float(attributes.get("dose", 0.0)),
        dose_unit=str(attributes.get("dose_unit", "")),
        admitted_additives=admitted,
    )


def _validation_problems(error: ValidationError, name: str) -> list[FieldProblem]:
    return [
        FieldProblem(name, str(entry["msg"]).removeprefix("Value error, "))
        for entry in error.errors()
    ]


def _contract_problems(error: ScenarioContractError) -> list[FieldProblem]:
    problems = []
    for problem in error.problems:
        variable, sep, rest = problem.partition(": ")
        if sep and (variable.startswith(("diet.", "host.", "additive."))):
            problems.append(FieldProblem(_label(variable), rest))
        else:
            problems.append(FieldProblem("Escenario", problem))
    return problems


def build_request(engine: Any, form: FormInput) -> ScenarioRequest:
    """`ScenarioRequest` del formulario, validado con el contrato y las reglas del motor.

    Raises:
        FormError: con un `FieldProblem` por cada rechazo.
    """
    defaults = form_defaults(engine, form.base_instance)
    problems: list[FieldProblem] = []
    if form.species not in defaults.species_options:
        problems.append(
            FieldProblem(
                "Especie", f"{form.species!r} no está en {list(defaults.species_options)}."
            )
        )
    if form.segment not in defaults.segment_options:
        problems.append(
            FieldProblem(
                "Segmento", f"{form.segment!r} no está en {list(defaults.segment_options)}."
            )
        )
    options = {option.category: option for option in additive_options()}
    if form.additive_category not in options:
        problems.append(
            FieldProblem("Aditivo", f"{form.additive_category!r} no está en el catálogo sintético.")
        )
    elif form.additive_category not in defaults.admitted_additives:
        chosen = options[form.additive_category]
        problems.append(
            FieldProblem(
                "Aditivo",
                f"la corrida solo admite la dosis del aditivo de su cohorte "
                f"({ADDITIVE_LABELS.get(defaults.additive_category, defaults.additive_category)}, "
                f"en {UNIT_LABELS.get(defaults.dose_unit, defaults.dose_unit)}); "
                f"{ADDITIVE_LABELS.get(chosen.category, chosen.category)} usa "
                f"{UNIT_LABELS.get(chosen.dose_unit, chosen.dose_unit)}, una unidad que el modelo "
                "no vio.",
            )
        )
    if problems:
        raise FormError(problems)

    items: list[dict[str, Any]] = []
    base_values = {f.variable: f.value for f in (*defaults.diet, *defaults.host)}
    for variable, value in (*form.diet.items(), *form.host.items()):
        if variable not in base_values:
            problems.append(FieldProblem(_label(variable), "no es un campo de esta corrida."))
        elif value != base_values[variable]:
            items.append({"variable": variable, "value": value})
    if form.dose != defaults.dose:
        items.append({"variable": DOSE_VARIABLE, "value": form.dose})
    if problems:
        raise FormError(problems)
    validated: list[InterventionItem] = []
    for item in items:
        try:
            validated.append(InterventionItem.model_validate(item))
        except ValidationError as error:
            problems.extend(_validation_problems(error, _label(str(item["variable"]))))
    if problems:
        raise FormError(problems)
    try:
        request = ScenarioRequest(
            contract_version=API_CONTRACT_VERSION,
            base_instance=form.base_instance,
            intervention=tuple(validated),
        )
    except ValidationError as error:
        raise FormError(_validation_problems(error, "Petición")) from error
    try:
        engine.base.derive(request)
    except ScenarioContractError as error:
        raise FormError(_contract_problems(error)) from error
    return request


def default_input(defaults: FormDefaults) -> FormInput:
    """Entrada con los valores prellenados: produce el escenario basal."""
    return FormInput(
        base_instance=defaults.base_instance,
        species=defaults.species,
        segment=defaults.segment,
        diet={f.variable: f.value for f in defaults.diet},
        host={f.variable: f.value for f in defaults.host},
        additive_category=defaults.additive_category,
        dose=defaults.dose,
    )


__all__ = [
    "ADDITIVE_LABELS",
    "COMPONENT_LABELS",
    "DOSE_VARIABLE",
    "SPECIES_NOTE",
    "UNIT_LABELS",
    "AdditiveOption",
    "FieldProblem",
    "FormDefaults",
    "FormError",
    "FormInput",
    "NumericField",
    "additive_options",
    "build_request",
    "default_input",
    "form_defaults",
]
