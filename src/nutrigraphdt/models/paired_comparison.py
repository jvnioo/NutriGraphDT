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
from typing import Any


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


__all__ = ["PairedComparison", "paired_comparison"]
