"""Motor de simulación de escenarios de referencia (A93-P1, #309).

Ejecuta el par basal / intervenido contra el mismo modelo congelado y devuelve
los resultados con el estado de estimabilidad (D-06 §7).

La arquitectura del runner es **libre de PyTorch**: acepta cualquier predictor
que implemente el protocolo ``ScenarioPredictor``, lo que permite usarlo tanto
con modelos tabulares (baseline) como con GNN sin cambiar la interfaz.

**Datos sintéticos.** Los escenarios proceden de DS-04 y DS-05; los resultados
no representan efectos biológicos reales.

Uso mínimo::

    from nutrigraphdt.simulation import run_scenario_pair, ScenarioPair
    from nutrigraphdt.simulation.runner import ConstantPredictor

    predictor = ConstantPredictor({"acetate": 0.70, "propionate": 0.15, "butyrate": 0.15})
    result = run_scenario_pair(ScenarioPair.default(), predictor)
    for diff in result.diffs:
        print(diff.component, diff.diff, diff.status)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from nutrigraphdt.data.synthetic.scenarios import (
    SCENARIO_BASAL_GRAPH_ID,
    SCENARIO_INTERVENED_GRAPH_ID,
    ScenarioInstance,
    build_basal_scenario,
    build_intervened_scenario,
)
from nutrigraphdt.scenarios import (
    ESTIMABLE,
    EmpiricalSupport,
    SupportResult,
)
from nutrigraphdt.simulation.outcome import (
    SCFA_COMPONENTS,
    SCFA_UNITS,
    SYNTHETIC_DATA_WARNING,
    OutcomeStatus,
    ScfaDiff,
    ScfaOutcome,
    compute_scfa_diff,
)

# ---------------------------------------------------------------------------
# Error propio del módulo
# ---------------------------------------------------------------------------


class SimulationError(RuntimeError):
    """Error en la ejecución de la simulación de escenarios."""


# ---------------------------------------------------------------------------
# Protocolo de predicción
# ---------------------------------------------------------------------------


@runtime_checkable
class ScenarioPredictor(Protocol):
    """Interfaz mínima que debe cumplir un predictor de escenarios.

    El predictor recibe una instancia de escenario (basal o intervenida) y
    devuelve las fracciones molares predichas para cada AGCC canónico.

    Returns:
        dict que mapea nombre de AGCC → fracción molar predicha (float).
        Debe contener al menos las claves de ``SCFA_COMPONENTS``.
    """

    def predict(self, scenario: ScenarioInstance) -> dict[str, float]:
        """Predice las fracciones molares de AGCC para el escenario dado."""
        ...


# ---------------------------------------------------------------------------
# Predictor constante (para pruebas y referencia)
# ---------------------------------------------------------------------------


class ConstantPredictor:
    """Predictor de referencia que siempre devuelve fracciones fijas.

    Útil para pruebas unitarias y como predictor de «cero cambio» en el
    catálogo de escenarios.

    Args:
        fractions: dict con las fracciones por componente.
            Debe contener ``acetate``, ``propionate`` y ``butyrate``.
    """

    def __init__(self, fractions: dict[str, float]) -> None:
        missing = set(SCFA_COMPONENTS) - set(fractions)
        if missing:
            raise SimulationError(f"ConstantPredictor: faltan componentes AGCC: {sorted(missing)}.")
        self._fractions = dict(fractions)

    def predict(self, scenario: ScenarioInstance) -> dict[str, float]:  # noqa: ARG002
        return dict(self._fractions)


# ---------------------------------------------------------------------------
# Par de escenarios
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioPair:
    """Par basal / intervenido que se ejecuta contra el mismo modelo congelado.

    Attributes:
        basal: Instancia del escenario basal (DS-04).
        intervened: Instancia del escenario intervenido (DS-04).
        catalog_basal: Ruta al archivo de configuración del escenario basal.
        catalog_intervened: Ruta al archivo de configuración del escenario intervenido.
    """

    basal: ScenarioInstance
    intervened: ScenarioInstance
    catalog_basal: Path | None = None
    catalog_intervened: Path | None = None

    @classmethod
    def default(cls) -> ScenarioPair:
        """Construye el par con los escenarios canónicos de DS-04."""
        return cls(
            basal=build_basal_scenario(),
            intervened=build_intervened_scenario(),
        )

    @classmethod
    def from_catalog(cls, catalog_dir: str | Path) -> ScenarioPair:
        """Construye el par leyendo los metadatos del catálogo (configs/scenarios/).

        Solo lee los metadatos JSON para verificar la identidad de los escenarios;
        los escenarios reales se construyen siempre con las funciones canónicas de
        ``nutrigraphdt.data.synthetic.scenarios``.

        Args:
            catalog_dir: Directorio que contiene ``basal_v1.json`` e
                ``intervened_v1.json``.

        Raises:
            SimulationError: Si los archivos no existen o los ``scenario_id`` no
                coinciden con los identificadores canónicos de DS-04.
        """
        catalog_dir = Path(catalog_dir)
        basal_path = catalog_dir / "basal_v1.json"
        intervened_path = catalog_dir / "intervened_v1.json"

        for p in (basal_path, intervened_path):
            if not p.exists():
                raise SimulationError(f"Archivo de catálogo no encontrado: {p}")

        basal_meta = json.loads(basal_path.read_text(encoding="utf-8"))
        intervened_meta = json.loads(intervened_path.read_text(encoding="utf-8"))

        if basal_meta.get("scenario_id") != SCENARIO_BASAL_GRAPH_ID:
            raise SimulationError(
                f"El catálogo basal declara scenario_id="
                f"'{basal_meta.get('scenario_id')}'; "
                f"se esperaba '{SCENARIO_BASAL_GRAPH_ID}'."
            )
        if intervened_meta.get("scenario_id") != SCENARIO_INTERVENED_GRAPH_ID:
            raise SimulationError(
                f"El catálogo intervenido declara scenario_id="
                f"'{intervened_meta.get('scenario_id')}'; "
                f"se esperaba '{SCENARIO_INTERVENED_GRAPH_ID}'."
            )

        return cls(
            basal=build_basal_scenario(),
            intervened=build_intervened_scenario(),
            catalog_basal=basal_path,
            catalog_intervened=intervened_path,
        )


# ---------------------------------------------------------------------------
# Resultado de la simulación
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioResult:
    """Resultado de la ejecución del par de escenarios contra un predictor.

    Attributes:
        basal_outcomes: Resultados del escenario basal por AGCC.
        intervened_outcomes: Resultados del escenario intervenido por AGCC.
        diffs: Diferencia (intervenido − basal) por AGCC.
        synthetic_data_warning: Advertencia de datos sintéticos (D-06 §7).
        support_used: Indica si se aplicó control de soporte empírico.
        predictor_name: Nombre del predictor (si se proporcionó).
    """

    basal_outcomes: list[ScfaOutcome]
    intervened_outcomes: list[ScfaOutcome]
    diffs: list[ScfaDiff]
    synthetic_data_warning: str = SYNTHETIC_DATA_WARNING
    support_used: bool = False
    predictor_name: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "predictor_name": self.predictor_name,
            "support_used": self.support_used,
            "synthetic_data_warning": self.synthetic_data_warning,
            "basal_outcomes": [o.to_dict() for o in self.basal_outcomes],
            "intervened_outcomes": [o.to_dict() for o in self.intervened_outcomes],
            "diffs": [d.to_dict() for d in self.diffs],
        }


# ---------------------------------------------------------------------------
# Función principal del runner
# ---------------------------------------------------------------------------


def _support_result_to_outcome(
    component: str,
    result: SupportResult,
    raw_value: float | None,
) -> ScfaOutcome:
    """Convierte un ``SupportResult`` en un ``ScfaOutcome``."""
    unit = SCFA_UNITS.get(component, "fraccion_molar")
    if result.status == ESTIMABLE and result.fractions is not None:
        idx = list(SCFA_COMPONENTS).index(component)
        value: float | None = result.fractions[idx]
        status = OutcomeStatus.ESTIMABLE
        reasons: tuple[str, ...] = ()
    else:
        value = None
        status = OutcomeStatus.NOT_ESTIMABLE
        reasons = result.reasons

    return ScfaOutcome(
        component=component,
        value=value,
        unit=unit,
        status=status,
        reasons=reasons,
    )


def _predictions_to_outcomes(
    predictions: dict[str, float],
    support: EmpiricalSupport | None,
) -> list[ScfaOutcome]:
    """Convierte predicciones crudas a ``ScfaOutcome``, con control de soporte opcional."""
    fractions_row = [predictions[c] for c in SCFA_COMPONENTS]

    if support is not None:
        results: list[SupportResult] = support.check([fractions_row])
        result = results[0]
        outcomes: list[ScfaOutcome] = []
        for idx, component in enumerate(SCFA_COMPONENTS):
            unit = SCFA_UNITS.get(component, "fraccion_molar")
            if result.status == ESTIMABLE and result.fractions is not None:
                outcomes.append(
                    ScfaOutcome(
                        component=component,
                        value=result.fractions[idx],
                        unit=unit,
                        status=OutcomeStatus.ESTIMABLE,
                    )
                )
            else:
                outcomes.append(
                    ScfaOutcome(
                        component=component,
                        value=None,
                        unit=unit,
                        status=OutcomeStatus.NOT_ESTIMABLE,
                        reasons=result.reasons,
                    )
                )
        return outcomes

    # Sin control de soporte: todos los valores se marcan como ESTIMABLE
    return [
        ScfaOutcome(
            component=c,
            value=predictions[c],
            unit=SCFA_UNITS.get(c, "fraccion_molar"),
            status=OutcomeStatus.ESTIMABLE,
        )
        for c in SCFA_COMPONENTS
    ]


def run_scenario_pair(
    pair: ScenarioPair,
    predictor: ScenarioPredictor,
    *,
    support: EmpiricalSupport | None = None,
    predictor_name: str = "unknown",
) -> ScenarioResult:
    """Ejecuta el par de escenarios contra el predictor y devuelve el resultado.

    El predictor se llama primero con el escenario basal y luego con el
    intervenido; ambas llamadas usan exactamente el mismo objeto predictor,
    lo que garantiza que el modelo es el mismo en los dos escenarios.

    Args:
        pair: Par basal / intervenido (ver ``ScenarioPair.default()`` o
            ``ScenarioPair.from_catalog()``).
        predictor: Objeto que implementa el protocolo ``ScenarioPredictor``.
        support: Control de soporte empírico (``EmpiricalSupport``). Si se
            proporciona, las predicciones fuera del soporte se devuelven como
            «no estimable» (D-06 §7). Si es ``None``, no se aplica el control.
        predictor_name: Nombre del predictor para el registro de resultados.

    Returns:
        ``ScenarioResult`` con los resultados del basal, el intervenido y la
        diferencia por AGCC.

    Raises:
        SimulationError: Si el predictor no devuelve las fracciones de los
            tres AGCC canónicos.
    """
    try:
        basal_preds = predictor.predict(pair.basal)
        intervened_preds = predictor.predict(pair.intervened)
    except Exception as exc:
        raise SimulationError(f"El predictor lanzó una excepción: {exc}") from exc

    for preds, label in ((basal_preds, "basal"), (intervened_preds, "intervenido")):
        missing = set(SCFA_COMPONENTS) - set(preds)
        if missing:
            raise SimulationError(
                f"El predictor no devolvió las fracciones AGCC para '{label}': "
                f"faltan {sorted(missing)}."
            )

    basal_outcomes = _predictions_to_outcomes(basal_preds, support)
    intervened_outcomes = _predictions_to_outcomes(intervened_preds, support)
    diffs = compute_scfa_diff(basal_outcomes, intervened_outcomes)

    return ScenarioResult(
        basal_outcomes=basal_outcomes,
        intervened_outcomes=intervened_outcomes,
        diffs=diffs,
        support_used=support is not None,
        predictor_name=predictor_name,
    )


__all__ = [
    "ConstantPredictor",
    "ScenarioPair",
    "ScenarioPredictor",
    "ScenarioResult",
    "SimulationError",
    "run_scenario_pair",
]
