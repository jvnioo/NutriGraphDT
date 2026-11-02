"""Qué salidas se explican y cuán estable es una explicación (C-04 y C-07; #240).

Aplica dos decisiones de la respuesta de Investigación a la revisión A55 (#158):

- **C-04.** Una salida del modelo composicional se explica solo si el modelo supera a
  `dummy_mean` en la métrica de esa salida: `fraction_mae_pp` macro para z1 y z2, y
  `log_total_mae` para ln T. La prueba es el t corregido con IC 95 % bilateral: el modelo supera
  si el límite superior de Δ = MAE(modelo) − MAE(`dummy_mean`) es negativo (`U < 0`).
  `explainable_outputs` devuelve esas salidas; `HeteroExplainer(explainable_outputs=...)` rechaza
  las demás.
- **C-07.** Por cada instancia, salida y modelo, el explicador corre con al menos 5 semillas, y la
  estabilidad del top-k se mide con el estimador Φ̂ de Nogueira et al. (2018), corregido por azar.
  Si Φ̂ < 0,40 en la estimación puntual, cada explicación lleva `explainer_instability`. El IC
  95 % es el asintótico de Nogueira et al. (2018, §5). No se usa bootstrap de las ejecuciones: las
  selecciones repetidas de un remuestreo inflan el acuerdo y sesgan Φ̂ hacia arriba. La
  correlación de Kendall media entre ejecuciones se informa como complemento, sin umbral.

El 0,40 es un traslado desde la selección de atributos y es provisional (respuesta A55, C-07).
"""

from __future__ import annotations

import csv
import math
import statistics
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Final

from nutrigraphdt.explainability.contract import Explanation, Warning_, validate_explanation
from nutrigraphdt.models.composition import MODEL_OUTPUT_NAMES
from nutrigraphdt.models.paired_comparison import paired_comparison

OUTPUT_METRICS: Final[Mapping[str, str]] = {
    MODEL_OUTPUT_NAMES[0]: "fraction_mae_pp",
    MODEL_OUTPUT_NAMES[1]: "fraction_mae_pp",
    MODEL_OUTPUT_NAMES[2]: "log_total_mae",
}
"""Métrica de cada salida del modelo composicional para el criterio de C-04."""

MIN_EXPLAINER_SEEDS: Final[int] = 5
"""Semillas mínimas del explicador por instancia, salida y modelo (C-07)."""

INSTABILITY_THRESHOLD: Final[float] = 0.40
"""Φ̂ por debajo de este valor (estimación puntual) es estabilidad pobre (C-07, provisional)."""

INSTABILITY_WARNING: Final = "explainer_instability"

FoldValues = Mapping[tuple[int, int], float]


# ---------------------------------------------------------------------------
# C-04: salidas explicables
# ---------------------------------------------------------------------------


def read_fold_metric(
    path: str | Path, model: str, metric: str, *, edges_arm: str | None = None
) -> dict[tuple[int, int], float]:
    """Valores de una métrica (grupo `all`) por `(semilla, fold)` desde un `fold_metrics.csv`.

    Lee la columna `log_total` para las métricas de ln T y `average` para las demás.
    """
    column = "log_total" if metric.startswith("log_total") else "average"
    with Path(path).open(encoding="utf-8") as handle:
        return {
            (int(row["seed"]), int(row["fold"])): float(row[column])
            for row in csv.DictReader(handle)
            if row["model"] == model
            and row["metric"] == metric
            and row.get("group") == "all"
            and (edges_arm is None or row.get("edges_arm") == edges_arm)
        }


def explainable_outputs(
    model: Mapping[str, FoldValues],
    dummy: Mapping[str, FoldValues],
    test_train_ratio: float,
) -> tuple[str, ...]:
    """Salidas en que el modelo supera a `dummy_mean` (U < 0 del t corregido; C-04).

    `model` y `dummy` dan, por métrica (`fraction_mae_pp`, `log_total_mae`), sus valores por
    `(semilla, fold)` sobre los mismos folds.

    Raises:
        ValueError: si una métrica falta o los folds no coinciden.
    """
    beats: dict[str, bool] = {}
    for metric in sorted(set(OUTPUT_METRICS.values())):
        if metric not in model or metric not in dummy:
            raise ValueError(f"Falta la métrica {metric!r} del modelo o de dummy_mean.")
        if set(model[metric]) != set(dummy[metric]):
            raise ValueError(f"Los folds de {metric!r} no coinciden entre modelo y dummy_mean.")
        deltas = {key: model[metric][key] - dummy[metric][key] for key in model[metric]}
        beats[metric] = paired_comparison(deltas, test_train_ratio).ci_high < 0
    return tuple(output for output, metric in OUTPUT_METRICS.items() if beats[metric])


# ---------------------------------------------------------------------------
# C-07: estabilidad entre semillas del explicador
# ---------------------------------------------------------------------------


def _elements(explanation: Explanation) -> dict[tuple[str, ...], float]:
    """Elementos que compiten en el top-k: aristas si las hay; si no, atributos."""
    if explanation.importance.edges:
        return {
            (e.source_type, e.relation_type, e.target_type, e.source_id, e.target_id): e.importance
            for e in explanation.importance.edges
        }
    return {
        (a.node_type, a.node_id, a.attribute): a.importance
        for a in explanation.importance.attributes
    }


def _top_k(scores: Mapping[tuple[str, ...], float], k: int) -> frozenset[tuple[str, ...]]:
    return frozenset(sorted(scores, key=lambda key: (-abs(scores[key]), key))[:k])


def _check_selections(selections: Sequence[frozenset[tuple[str, ...]]], d: int) -> float:
    if len(selections) < 2 or d < 1:
        raise ValueError("Φ̂ necesita al menos dos selecciones y d ≥ 1.")
    k_mean = statistics.fmean(len(selection) for selection in selections)
    denominator = (k_mean / d) * (1 - k_mean / d)
    if denominator == 0:
        raise ValueError("Φ̂ no está definido si las selecciones están vacías o son completas.")
    return denominator


def _frequencies(selections: Sequence[frozenset[tuple[str, ...]]]) -> dict[tuple[str, ...], float]:
    counts: dict[tuple[str, ...], int] = {}
    for selection in selections:
        for element in selection:
            counts[element] = counts.get(element, 0) + 1
    return {element: count / len(selections) for element, count in counts.items()}


def nogueira_phi(selections: Sequence[frozenset[tuple[str, ...]]], d: int) -> float:
    """Estabilidad Φ̂ de Nogueira et al. (2018) de M selecciones sobre `d` elementos.

    Φ̂ = 1 − ((1/d) Σ_f s_f²) / ((k̄/d)(1 − k̄/d)), con s_f² = M/(M−1) · p̂_f (1 − p̂_f) y p̂_f la
    frecuencia con que se selecciona el elemento f. Vale 1 si todas las selecciones son iguales
    y 0, en esperanza, para selecciones al azar.

    Raises:
        ValueError: si hay menos de dos selecciones, `d` no es positivo o todas las selecciones
            están vacías o completas.
    """
    denominator = _check_selections(selections, d)
    m = len(selections)
    variance_sum = sum(m / (m - 1) * p * (1 - p) for p in _frequencies(selections).values())
    return 1 - (variance_sum / d) / denominator


def nogueira_ci(
    selections: Sequence[frozenset[tuple[str, ...]]], d: int, *, level: float = 0.95
) -> tuple[float, float]:
    """IC asintótico de Φ̂ (Nogueira et al., 2018, §5).

    Var(Φ̂) ≈ 4/M² Σ_i (φ̂_i − φ̄)², con φ̂_i el término de la selección i en la linealización
    del estimador:
    φ̂_i = [(1/d) Σ_f z_if p̂_f − k_i k̄/d² + Φ̂/2 (2 k̄ k_i/d² − k_i/d − k̄/d + 1)] / ((k̄/d)(1 − k̄/d)).

    Raises:
        ValueError: en los mismos casos que `nogueira_phi`.
    """
    denominator = _check_selections(selections, d)
    m = len(selections)
    phi = nogueira_phi(selections, d)
    frequencies = _frequencies(selections)
    k_mean = statistics.fmean(len(selection) for selection in selections)
    terms = []
    for selection in selections:
        k_i = len(selection)
        overlap = sum(frequencies[element] for element in selection) / d
        terms.append(
            (
                overlap
                - k_i * k_mean / d**2
                + phi / 2 * (2 * k_mean * k_i / d**2 - k_i / d - k_mean / d + 1)
            )
            / denominator
        )
    mean = statistics.fmean(terms)
    half_width = NormalDist().inv_cdf(0.5 + level / 2) * math.sqrt(
        4 / m**2 * sum((term - mean) ** 2 for term in terms)
    )
    return phi - half_width, phi + half_width


def _kendall(a: Sequence[float], b: Sequence[float]) -> float:
    """τ-a de Kendall entre dos vectores (sin corrección por empates)."""
    n = len(a)
    if n < 2:
        return math.nan
    concordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            product = (a[i] - a[j]) * (b[i] - b[j])
            concordant += (product > 0) - (product < 0)
    return concordant / (n * (n - 1) / 2)


@dataclass(frozen=True)
class StabilityReport:
    """Estabilidad del top-k entre semillas del explicador para una instancia y salida."""

    seeds: tuple[int, ...]
    k: int
    d: int
    phi: float
    ci_low: float
    ci_high: float
    kendall_mean: float
    unstable: bool
    explanations: tuple[Explanation, ...]


def explain_across_seeds(
    explain: Callable[[int], Explanation],
    seeds: Sequence[int],
) -> StabilityReport:
    """Explica una instancia con cada semilla y mide la estabilidad del top-k (C-07).

    `explain(seed)` devuelve la explicación con esa semilla del explicador (por ejemplo,
    `lambda s: HeteroExplainer(model, seed=s, ...).explain(data, target=...)`). Si
    Φ̂ < `INSTABILITY_THRESHOLD`, cada explicación devuelta lleva `explainer_instability`.

    Raises:
        ValueError: con menos de `MIN_EXPLAINER_SEEDS` semillas o semillas repetidas.
    """
    if len(set(seeds)) != len(seeds):
        raise ValueError("Las semillas del explicador no pueden repetirse.")
    if len(seeds) < MIN_EXPLAINER_SEEDS:
        raise ValueError(f"C-07 pide al menos {MIN_EXPLAINER_SEEDS} semillas del explicador.")
    explanations = [explain(seed) for seed in seeds]
    scores = [_elements(explanation) for explanation in explanations]
    keys = sorted(set().union(*scores))
    k = explanations[0].subgraph.k
    selections = [_top_k(score, k) for score in scores]
    phi = nogueira_phi(selections, len(keys))
    ci_low, ci_high = nogueira_ci(selections, len(keys))
    vectors = [[score.get(key, 0.0) for key in keys] for score in scores]
    taus = [
        _kendall(vectors[i], vectors[j])
        for i in range(len(vectors))
        for j in range(i + 1, len(vectors))
    ]
    unstable = phi < INSTABILITY_THRESHOLD
    if unstable:
        explanations = [_with_instability_warning(explanation) for explanation in explanations]
    return StabilityReport(
        seeds=tuple(seeds),
        k=k,
        d=len(keys),
        phi=phi,
        ci_low=ci_low,
        ci_high=ci_high,
        kendall_mean=statistics.fmean(t for t in taus if not math.isnan(t)) if taus else math.nan,
        unstable=unstable,
        explanations=tuple(explanations),
    )


def _with_instability_warning(explanation: Explanation) -> Explanation:
    from nutrigraphdt.explainability.wrapper import WARNING_MESSAGES

    if any(w.code == INSTABILITY_WARNING for w in explanation.warnings):
        return explanation
    data = explanation.model_dump()
    data["warnings"].append(
        Warning_(
            code=INSTABILITY_WARNING, message=WARNING_MESSAGES[INSTABILITY_WARNING]
        ).model_dump()
    )
    return validate_explanation(data)


__all__ = [
    "INSTABILITY_THRESHOLD",
    "INSTABILITY_WARNING",
    "MIN_EXPLAINER_SEEDS",
    "OUTPUT_METRICS",
    "StabilityReport",
    "explain_across_seeds",
    "explainable_outputs",
    "nogueira_ci",
    "nogueira_phi",
    "read_fold_metric",
]
