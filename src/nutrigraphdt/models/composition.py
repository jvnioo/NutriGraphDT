"""Objetivo composicional de los AGCC y sus métricas (contrato de datos v2, sección 1; #146).

El grafo guarda las concentraciones medidas de acetato, propionato y n-butirato (mmol/kg de
digesta fresca). Este módulo es la **única** transformación versionada que deriva de ellas el
objetivo de los modelos, y la usan por igual la GNN y los baselines:

| Magnitud | Definición |
|---|---|
| Total | `T = acetato + propionato + butirato` (no el «AGCC totales» del portal). |
| Fracción molar | `p_i = c_i / T`. |
| Log-razones (salida) | `z_1 = ln(propionato / acetato)`, `z_2 = ln(butirato / acetato)`. |
| Total (salida) | `ln T`. |
| Cantidad reconstruida | `c_i = T · p_i`. |

La inversa de `(z_1, z_2)` es una softmax de tres componentes con el acetato como referencia
(logit 0), así que cualquier salida real da fracciones positivas que suman 1.

**Ceros y ausencias.** Una log-razón no admite ceros. Un animal con algún AGCC objetivo
ausente, no finito, igual a cero o negativo no tiene objetivo composicional: su máscara queda
en `False` y no se agrega pseudoconteo (pregunta 1 de la sección 9 del contrato, confirmada
por Investigación el 25-10-2026).

**Métricas (D-03).** `evaluate_composition` calcula, globales y por día de muestreo:

- R² y MAE de cada fracción, en puntos porcentuales, y su promedio macro;
- R² y MAE de `ln T`;
- R² y MAE de las cantidades reconstruidas en mmol/kg, y su promedio macro.

La media y la dispersión entre folds y semillas quedan para la validación cruzada (#139).

Este módulo no depende de PyTorch; `models.gnn.target` ofrece la versión con tensores.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from nutrigraphdt.models.metrics import (
    DEFAULT_SCFA_TARGETS,
    EvaluationReport,
    MetricRow,
    mean_absolute_error,
    r2_score,
)

COMPOSITIONAL_TARGET_VERSION: Final[str] = "1.0.0"
"""Versión de la transformación; cambia si cambia cualquier definición de este módulo."""

NONNEGATIVITY_POLICY_VERSION: Final[str] = "1.0.0"
"""Versión de la política numérica de no negatividad para la reconstrucción composicional."""

NONNEGATIVITY_POLICY: Final[str] = "intrinsic_softmax"
UNREPRESENTABLE_OUTPUT: Final[str] = "fail_fold"

COMPOSITIONAL_TARGET_CONTRACT: Final[str] = "docs/graph/data-contract-v2.md#1"

REFERENCE_SCFA: Final[str] = "acetate"
"""AGCC de referencia (denominador) de las log-razones."""

LOG_RATIO_NAMES: Final[tuple[str, str]] = ("log_propionate_acetate", "log_butyrate_acetate")
LOG_TOTAL_NAME: Final[str] = "log_total"
MODEL_OUTPUT_NAMES: Final[tuple[str, str, str]] = (*LOG_RATIO_NAMES, LOG_TOTAL_NAME)
"""Orden de las tres salidas del modelo: `z_1`, `z_2` y `ln T`."""

ROUND_TRIP_RTOL: Final[float] = 1e-9
"""Tolerancia relativa documentada de la ida y vuelta concentraciones → objetivo → concentraciones.

En `float64` el error observado es del orden de 1e-15; la tolerancia deja margen para entradas
de varios órdenes de magnitud sin ocultar un error de fórmula.
"""

ALL_DAYS: Final[str] = "all"
"""Etiqueta de las métricas globales en la columna `group`."""

COMPOSITION_METRICS: Final[tuple[str, ...]] = (
    "fraction_mae_pp",
    "fraction_r2",
    "log_total_mae",
    "log_total_r2",
    "reconstructed_mae",
    "reconstructed_r2",
)


@dataclass(frozen=True)
class CompositionalTarget:
    """Objetivo composicional de un animal.

    `valid` es la máscara: si es `False` (algún AGCC ausente, no finito o ≤ 0), los demás
    campos son `nan` y el animal no entra al entrenamiento ni a las métricas composicionales.
    """

    valid: bool
    total: float
    fractions: tuple[float, float, float]
    log_ratios: tuple[float, float]
    log_total: float

    @property
    def model_output(self) -> tuple[float, float, float]:
        """`(z_1, z_2, ln T)` en el orden de `MODEL_OUTPUT_NAMES`."""
        return (*self.log_ratios, self.log_total)


_NAN3: Final = (math.nan, math.nan, math.nan)
_INVALID: Final = CompositionalTarget(False, math.nan, _NAN3, (math.nan, math.nan), math.nan)


class CompositionalReconstructionError(ValueError):
    """La salida composicional no puede reconstruirse en el tipo numérico solicitado."""


def _valid_concentration(value: float | None) -> bool:
    if value is None:
        return False
    number = float(value)
    return math.isfinite(number) and number > 0.0


def compositional_target(
    acetate: float | None, propionate: float | None, butyrate: float | None
) -> CompositionalTarget:
    """Concentraciones medidas (mmol/kg) → total, fracciones, log-razones y `ln T`.

    Un valor ausente (`None`), no finito, cero o negativo deja el objetivo inválido
    (`valid=False`), sin pseudoconteo.
    """
    values = (acetate, propionate, butyrate)
    if not all(_valid_concentration(v) for v in values):
        return _INVALID
    a, p, b = (float(v) for v in values)  # type: ignore[arg-type]
    total = a + p + b
    return CompositionalTarget(
        valid=True,
        total=total,
        fractions=(a / total, p / total, b / total),
        log_ratios=(math.log(p / a), math.log(b / a)),
        log_total=math.log(total),
    )


def fractions_from_log_ratios(z1: float, z2: float) -> tuple[float, float, float]:
    """Inversa de las log-razones: fracciones de acetato, propionato y butirato.

    Softmax de `(0, z_1, z_2)`, estable para valores grandes (resta el máximo).
    """
    logits = (0.0, float(z1), float(z2))
    if not all(math.isfinite(v) for v in logits):
        raise ValueError(f"Log-razones no finitas: z_1={z1}, z_2={z2}.")
    shift = max(logits)
    weights = [math.exp(v - shift) for v in logits]
    norm = sum(weights)
    return (weights[0] / norm, weights[1] / norm, weights[2] / norm)


def concentrations_from_output(
    z1: float, z2: float, log_total: float
) -> tuple[float, float, float]:
    """Salida del modelo `(z_1, z_2, ln T)` → concentraciones reconstruidas en mmol/kg."""
    values = (float(z1), float(z2), float(log_total))
    if not all(math.isfinite(value) for value in values):
        raise CompositionalReconstructionError(
            f"Salida composicional no finita: z_1={z1}, z_2={z2}, ln T={log_total}."
        )
    try:
        total = math.exp(values[2])
    except OverflowError as error:
        raise CompositionalReconstructionError(
            f"ln T={values[2]} desborda al reconstruir la concentración."
        ) from error
    fractions = fractions_from_log_ratios(values[0], values[1])
    concentrations = (total * fractions[0], total * fractions[1], total * fractions[2])
    if not all(math.isfinite(value) for value in concentrations):
        raise CompositionalReconstructionError(
            "La salida composicional produjo concentraciones no finitas."
        )
    return concentrations


def compositional_targets(
    concentrations: Sequence[Sequence[float | None]],
) -> list[CompositionalTarget]:
    """`compositional_target` por fila de una matriz `[N, 3]` (acetato, propionato, butirato)."""
    targets: list[CompositionalTarget] = []
    for index, row in enumerate(concentrations):
        if len(row) != 3:
            raise ValueError(f"La fila {index} tiene {len(row)} valores; se esperaban 3.")
        targets.append(compositional_target(row[0], row[1], row[2]))
    return targets


def _pp(value: float) -> float:
    return 100.0 * value


def _rows(
    model: str,
    split: str | None,
    group: str,
    true: Sequence[CompositionalTarget],
    pred: Sequence[tuple[float, float, float]],
) -> list[MetricRow]:
    names = DEFAULT_SCFA_TARGETS
    pred_fractions = [fractions_from_log_ratios(z1, z2) for z1, z2, _ in pred]
    pred_conc = [concentrations_from_output(*row) for row in pred]

    frac_mae: dict[str, float] = {}
    frac_r2: dict[str, float] = {}
    conc_mae: dict[str, float] = {}
    conc_r2: dict[str, float] = {}
    for i, name in enumerate(names):
        t_frac = [_pp(t.fractions[i]) for t in true]
        p_frac = [_pp(f[i]) for f in pred_fractions]
        frac_mae[name] = mean_absolute_error(t_frac, p_frac)
        frac_r2[name] = r2_score(t_frac, p_frac)
        t_conc = [t.total * t.fractions[i] for t in true]
        p_conc = [c[i] for c in pred_conc]
        conc_mae[name] = mean_absolute_error(t_conc, p_conc)
        conc_r2[name] = r2_score(t_conc, p_conc)

    t_log = [t.log_total for t in true]
    p_log = [row[2] for row in pred]
    log_mae = mean_absolute_error(t_log, p_log)
    log_r2 = r2_score(t_log, p_log)

    def macro(values: dict[str, float]) -> float:
        return sum(values.values()) / len(values)

    def row(metric: str, targets: dict[str, float], average: float) -> MetricRow:
        return MetricRow(model, metric, targets, average, split=split, group=group)

    return [
        row("fraction_mae_pp", frac_mae, macro(frac_mae)),
        row("fraction_r2", frac_r2, macro(frac_r2)),
        row("log_total_mae", {LOG_TOTAL_NAME: log_mae}, log_mae),
        row("log_total_r2", {LOG_TOTAL_NAME: log_r2}, log_r2),
        row("reconstructed_mae", conc_mae, macro(conc_mae)),
        row("reconstructed_r2", conc_r2, macro(conc_r2)),
    ]


def evaluate_composition(
    true_concentrations: Sequence[Sequence[float | None]],
    predicted_output: Sequence[Sequence[float]],
    model_name: str,
    *,
    split: str | None = None,
    sampling_days: Sequence[object] | None = None,
) -> EvaluationReport:
    """Métricas D-03 del objetivo composicional, globales y por día de muestreo.

    Args:
        true_concentrations: concentraciones medidas `[N, 3]` (acetato, propionato, butirato),
            en mmol/kg; `None` donde falta.
        predicted_output: salida del modelo `[N, 3]` en el orden de `MODEL_OUTPUT_NAMES`
            (`z_1`, `z_2`, `ln T`).
        model_name: nombre del modelo en las filas del reporte.
        split: subconjunto evaluado (`val`, `test`…).
        sampling_days: día de muestreo de cada animal; agrega un bloque de filas por día,
            además del global (`group = "all"`).

    Solo se evalúan los animales con objetivo válido (máscara `True`). Las fracciones se
    informan en puntos porcentuales; las cantidades reconstruidas, en mmol/kg.

    Raises:
        ValueError: si las longitudes no coinciden, si una salida no es finita o si no queda
            ningún animal con objetivo válido (globalmente).
    """
    if len(true_concentrations) != len(predicted_output):
        raise ValueError(
            f"true_concentrations tiene {len(true_concentrations)} filas y predicted_output "
            f"{len(predicted_output)}."
        )
    if sampling_days is not None and len(sampling_days) != len(true_concentrations):
        raise ValueError(
            f"sampling_days tiene {len(sampling_days)} valores; se esperaban "
            f"{len(true_concentrations)}."
        )
    targets = compositional_targets(true_concentrations)
    outputs: list[tuple[float, float, float]] = []
    for index, row in enumerate(predicted_output):
        if len(row) != 3:
            raise ValueError(f"La fila {index} de predicted_output tiene {len(row)} valores.")
        values = (float(row[0]), float(row[1]), float(row[2]))
        if not all(math.isfinite(v) for v in values):
            raise ValueError(f"Salida no finita en la fila {index}: {values}.")
        outputs.append(values)

    valid = [i for i, t in enumerate(targets) if t.valid]
    if not valid:
        raise ValueError("Ningún animal tiene objetivo composicional válido.")

    rows = _rows(
        model_name, split, ALL_DAYS, [targets[i] for i in valid], [outputs[i] for i in valid]
    )
    if sampling_days is not None:
        by_day: dict[str, list[int]] = {}
        for i in valid:
            by_day.setdefault(str(sampling_days[i]), []).append(i)
        for day in sorted(by_day, key=_day_sort_key):
            indices = by_day[day]
            rows.extend(
                _rows(
                    model_name,
                    split,
                    day,
                    [targets[i] for i in indices],
                    [outputs[i] for i in indices],
                )
            )
    return EvaluationReport(rows=tuple(rows))


def _day_sort_key(day: str) -> tuple[int, float, str]:
    try:
        return (0, float(day), day)
    except ValueError:
        return (1, 0.0, day)


__all__ = [
    "ALL_DAYS",
    "COMPOSITIONAL_TARGET_CONTRACT",
    "COMPOSITIONAL_TARGET_VERSION",
    "COMPOSITION_METRICS",
    "CompositionalReconstructionError",
    "LOG_RATIO_NAMES",
    "LOG_TOTAL_NAME",
    "MODEL_OUTPUT_NAMES",
    "NONNEGATIVITY_POLICY",
    "NONNEGATIVITY_POLICY_VERSION",
    "REFERENCE_SCFA",
    "ROUND_TRIP_RTOL",
    "UNREPRESENTABLE_OUTPUT",
    "CompositionalTarget",
    "compositional_target",
    "compositional_targets",
    "concentrations_from_output",
    "evaluate_composition",
    "fractions_from_log_ratios",
]
