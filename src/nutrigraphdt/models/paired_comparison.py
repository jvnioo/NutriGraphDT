"""Comparación pareada de dos brazos en validación cruzada repetida (protocolo A55-P1 §4.2).

La comparación del brazo con restricciones ($M_C$) frente al libre ($M_0$) se hace sobre las
diferencias por fold $\\Delta_{s,k} = \\text{métrica}(M_C)_{s,k} - \\text{métrica}(M_0)_{s,k}$, con
los dos brazos entrenados en los mismos folds y semillas. `paired_comparison` calcula:

- **t corregido para CV repetida** (Nadeau y Bengio, 2003; Bouckaert y Frank, 2004):
  $\\sigma^2 = (1/(K S) + n_{test}/n_{train})\\, s^2_\\Delta$, con $K S - 1$ grados de libertad,
  su p bilateral y el IC bilateral del nivel pedido (95 % por omisión);
- **Wilcoxon** de rangos con signo sobre las medias por semilla (p bilateral);
- **d de Cohen pareada**, $\\bar\\Delta / s_\\Delta$.

`n_test / n_train` es el cociente medio entre los animales de test de cada fold y los de su train
(train interno más val interno). Requiere scipy, que instala el extra `baselines` con
scikit-learn.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Final


@dataclass(frozen=True)
class PairedComparison:
    """Resultado de comparar dos brazos sobre los mismos folds."""

    n_folds: int
    n_seeds: int
    mean_delta: float
    std_delta: float
    test_train_ratio: float
    corrected_se: float
    ci_level: float
    ci_low: float
    ci_high: float
    t_statistic: float
    degrees_of_freedom: int
    p_value: float
    wilcoxon_p_value: float
    cohen_d: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def paired_comparison(
    deltas: Mapping[tuple[int, int], float],
    test_train_ratio: float,
    *,
    ci_level: float = 0.95,
) -> PairedComparison:
    """Compara dos brazos a partir de `Δ` por `(semilla, fold)`.

    Con todas las diferencias iguales a cero (los dos brazos dan lo mismo en cada fold), el
    estadístico no está definido: `t` y los p valen `nan` y el IC es `[0, 0]`.

    Raises:
        ValueError: si hay menos de dos folds, algún `Δ` no es finito o el cociente no es
            positivo.
    """
    from scipy import stats

    if len(deltas) < 2:
        raise ValueError("Se necesitan al menos dos folds para comparar.")
    values = [float(value) for value in deltas.values()]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Todas las diferencias por fold deben ser finitas.")
    if not test_train_ratio > 0:
        raise ValueError("El cociente n_test / n_train debe ser positivo.")
    by_seed: dict[int, list[float]] = defaultdict(list)
    for (seed, _), value in deltas.items():
        by_seed[seed].append(float(value))
    n = len(values)
    mean = statistics.fmean(values)
    std = statistics.stdev(values)
    se = math.sqrt((1.0 / n + test_train_ratio) * std**2)
    df = n - 1
    if se == 0.0:
        t_statistic = p_value = wilcoxon_p = cohen_d = math.nan
        low = high = mean
    else:
        t_statistic = mean / se
        p_value = float(2.0 * stats.t.sf(abs(t_statistic), df))
        half = float(stats.t.ppf(0.5 + ci_level / 2.0, df)) * se
        low, high = mean - half, mean + half
        cohen_d = mean / std
        seed_means = [statistics.fmean(v) for v in by_seed.values()]
        wilcoxon_p = (
            float(stats.wilcoxon(seed_means).pvalue)
            if any(m != 0.0 for m in seed_means) and len(seed_means) > 1
            else math.nan
        )
    return PairedComparison(
        n_folds=n,
        n_seeds=len(by_seed),
        mean_delta=mean,
        std_delta=std,
        test_train_ratio=test_train_ratio,
        corrected_se=se,
        ci_level=ci_level,
        ci_low=low,
        ci_high=high,
        t_statistic=t_statistic,
        degrees_of_freedom=df,
        p_value=p_value,
        wilcoxon_p_value=wilcoxon_p,
        cohen_d=cohen_d,
    )


DELTA_ROPE_PP: Final[float] = 0.5
"""δ del protocolo §4.3 en el MAE macro de fracciones (pp): provisional de Investigación (P-02,
respuesta A55 v1.1), congelado el 02-11-2026 antes de la evaluación de D1 (#185)."""

STABILITY_RATIO: Final[float] = 1.25
"""Paso 3 de §5 (P-03): `_std(M_C)` ≤ 1,25 × `_std(M_0)` en la métrica primaria; provisional."""

CATEGORIES: Final[tuple[str, ...]] = (
    "Superior en la práctica",
    "Superior",
    "Equivalente",
    "No inferior",
    "No concluyente",
    "Inferior en la práctica",
)
"""Tabla 4 del protocolo (P-05), en orden: se asigna la primera que se cumple."""


def delta_category(low: float, high: float, delta: float = DELTA_ROPE_PP) -> int:
    """Categoría 1 a 6 de la Tabla 4 para un IC `[low, high]` de Δ = MAE(M_C) − MAE(M_0)."""
    if high < -delta:
        return 1
    if high < 0:
        return 2
    if low > -delta and high < delta:
        return 3
    if high < delta:
        return 4
    if low < delta <= high:
        return 5
    return 6


def classify(*, feasible: bool, category: int, low: float, stable: bool) -> tuple[str, str]:
    """`(clasificación, decisión)` de la Tabla 5 del protocolo, con el paso 3 de estabilidad."""
    if not feasible:
        return "Inoperante", "Rechazado"
    if category in (5, 6):
        return "Costo inadmisible", "Rechazado"
    if not stable:
        return "Inestable", "Rechazado"
    if category in (1, 2):
        return "Superioridad dual", "Aprobado (preferido)"
    if category == 3 and low > 0:
        return "Degradación aceptable", "Aprobado con reserva"
    return "Factibilidad sin costo", "Aprobado"


__all__ = [
    "CATEGORIES",
    "DELTA_ROPE_PP",
    "STABILITY_RATIO",
    "PairedComparison",
    "classify",
    "delta_category",
    "paired_comparison",
]
