"""Control de soporte empírico de las predicciones de escenarios (F6, D-06 §7; #245).

Los escenarios de F6 extrapolan: un modelo puede predecir una composición de AGCC que nunca vio.
D-06 §7 recomienda que esas predicciones se informen como **«no estimable»**, con su motivo, en
vez de como un número. Este módulo implementa ese control, separado de la pérdida y de las
restricciones de F5:

- `EmpiricalSupport.fit` calcula, para cada fracción molar (acetato, propionato y n-butirato),
  el mínimo $L_k$ y el máximo $U_k$ **solo con los animales con que se entrenó el modelo
  congelado** (en validación cruzada, el train de su fold; nunca el val interno ni el test). Usa
  el mínimo y el máximo para no introducir un percentil sin fuente. Con días de muestreo, calcula
  además un intervalo por día.
- `EmpiricalSupport.check` marca cada predicción: `estimable` si todas sus fracciones caen en
  $[L_k, U_k]$ (con los extremos incluidos) y `no_estimable` si alguna queda fuera. En ese caso,
  `fractions` es `None` y `reasons` dice qué fracción, con qué valor y fuera de qué intervalo.

El control no fija ningún umbral científico: los límites salen de los datos de entrenamiento, y
el resultado registra el intervalo, el subconjunto fuente y el motivo. Integrarlo con el motor de
escenarios de F6 queda para cuando ese motor exista.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

SUPPORT_VERSION: Final[str] = "1.0.0"
COMPONENTS: Final[tuple[str, str, str]] = ("acetate", "propionate", "butyrate")
ESTIMABLE: Final = "estimable"
NOT_ESTIMABLE: Final = "no_estimable"
CLOSURE_TOLERANCE: Final[float] = 1e-6
"""Tolerancia numérica del cierre `Σ p_k = 1` de una fila de fracciones (no fisiológica)."""


class SupportError(ValueError):
    """Los datos no permiten calcular o aplicar el soporte."""


Interval = tuple[float, float]


@dataclass(frozen=True)
class SupportResult:
    """Resultado del control para una predicción."""

    status: Literal["estimable", "no_estimable"]
    fractions: tuple[float, float, float] | None
    """Fracciones predichas; `None` si no es estimable, para que no se informen como número."""
    interval: Mapping[str, Interval]
    """Intervalo `[L_k, U_k]` que se aplicó a cada fracción."""
    source: str
    """Subconjunto con que se calculó el soporte (por ejemplo, el train de un fold)."""
    day: str | None = None
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["interval"] = {k: list(v) for k, v in self.interval.items()}
        return data


def _validated(row: Sequence[float], where: str) -> tuple[float, float, float]:
    if len(row) != len(COMPONENTS):
        raise SupportError(f"{where}: se esperaban {len(COMPONENTS)} fracciones; hay {len(row)}.")
    values = tuple(float(value) for value in row)
    if not all(math.isfinite(value) and value >= 0 for value in values):
        raise SupportError(f"{where}: las fracciones deben ser finitas y no negativas: {values}.")
    if abs(sum(values) - 1.0) > CLOSURE_TOLERANCE:
        raise SupportError(f"{where}: las fracciones deben sumar 1; suman {sum(values)}.")
    return values[0], values[1], values[2]


def _interval(rows: Sequence[tuple[float, float, float]]) -> dict[str, Interval]:
    return {
        name: (min(row[i] for row in rows), max(row[i] for row in rows))
        for i, name in enumerate(COMPONENTS)
    }


@dataclass(frozen=True)
class EmpiricalSupport:
    """Mínimo y máximo de cada fracción en el conjunto de entrenamiento del modelo."""

    interval: Mapping[str, Interval]
    source: str
    n_animals: int
    by_day: Mapping[str, Mapping[str, Interval]] = field(default_factory=dict)
    n_by_day: Mapping[str, int] = field(default_factory=dict)
    version: str = SUPPORT_VERSION

    @classmethod
    def fit(
        cls,
        fractions: Sequence[Sequence[float]],
        *,
        source: str,
        days: Sequence[str] | None = None,
    ) -> EmpiricalSupport:
        """Soporte de las fracciones **de entrenamiento** (una fila por animal).

        Quien llama entrega solo el train del modelo congelado; el val interno y el test no
        entran. `source` describe ese subconjunto. Con `days`, también calcula el soporte de
        cada día de muestreo.

        Raises:
            SupportError: si no hay filas, alguna fila no es una composición válida o `days` no
                tiene una entrada por fila.
        """
        if not source.strip():
            raise SupportError("`source` debe describir el subconjunto de entrenamiento.")
        rows = [_validated(row, f"fila {i}") for i, row in enumerate(fractions)]
        if not rows:
            raise SupportError("El soporte necesita al menos un animal de entrenamiento.")
        by_day: dict[str, dict[str, Interval]] = {}
        n_by_day: dict[str, int] = {}
        if days is not None:
            if len(days) != len(rows):
                raise SupportError("`days` debe tener una entrada por fila de fracciones.")
            for day in sorted({str(d) for d in days}):
                selected = [row for row, d in zip(rows, days, strict=True) if str(d) == day]
                by_day[day] = _interval(selected)
                n_by_day[day] = len(selected)
        return cls(
            interval=_interval(rows),
            source=source,
            n_animals=len(rows),
            by_day=by_day,
            n_by_day=n_by_day,
        )

    def check(
        self, fractions: Sequence[Sequence[float]], *, days: Sequence[str | None] | None = None
    ) -> list[SupportResult]:
        """Marca cada predicción como `estimable` o `no_estimable`.

        Con `days`, cada predicción se compara con el soporte de su día; si ese día no tiene
        soporte (no hubo animales de entrenamiento en él), la predicción es `no_estimable`.

        Raises:
            SupportError: si una fila no es una composición válida o se piden días sin haberlos
                usado al calcular el soporte.
        """
        if days is not None and not self.by_day:
            raise SupportError("El soporte se calculó sin días de muestreo.")
        if days is not None and len(days) != len(fractions):
            raise SupportError("`days` debe tener una entrada por predicción.")
        results = []
        for i, row in enumerate(fractions):
            values = _validated(row, f"predicción {i}")
            day = None if days is None else days[i]
            if days is not None and (day is None or str(day) not in self.by_day):
                results.append(
                    SupportResult(
                        status=NOT_ESTIMABLE,
                        fractions=None,
                        interval={},
                        source=self.source,
                        day=None if day is None else str(day),
                        reasons=(f"el día {day!r} no tiene animales de entrenamiento",),
                    )
                )
                continue
            interval = self.interval if day is None else self.by_day[str(day)]
            reasons = tuple(
                f"{name} = {value:.6g} fuera de [{low:.6g}, {high:.6g}]"
                for name, value, (low, high) in (
                    (name, values[j], interval[name]) for j, name in enumerate(COMPONENTS)
                )
                if not (low <= value <= high)
            )
            results.append(
                SupportResult(
                    status=NOT_ESTIMABLE if reasons else ESTIMABLE,
                    fractions=None if reasons else values,
                    interval=dict(interval),
                    source=self.source,
                    day=None if day is None else str(day),
                    reasons=reasons,
                )
            )
        return results

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "source": self.source,
            "n_animals": self.n_animals,
            "interval": {k: list(v) for k, v in self.interval.items()},
            "by_day": {
                day: {k: list(v) for k, v in interval.items()}
                for day, interval in self.by_day.items()
            },
            "n_by_day": dict(self.n_by_day),
            "method": "mínimo y máximo de cada fracción en el train del modelo (D-06 §7)",
        }


def support_from_run(
    run_dir: str | Path,
    fractions: Mapping[str, Sequence[float]],
    *,
    days: Mapping[str, str] | None = None,
) -> EmpiricalSupport:
    """Soporte de una corrida guardada (#180), con los animales de su `train` y nada más.

    Lee `sample_ids.train` de su `run.json`: el train interno con que se ajustaron los pesos.
    El val interno (`inner_val`) y el test del fold no entran. `fractions` da las fracciones
    **medidas** de cada animal (por `sample_id`) y `days`, su día de muestreo, si se quiere
    soporte por día.

    Raises:
        SupportError: si el `run.json` no lista el train o falta la composición de algún animal.
    """
    directory = Path(run_dir)
    info = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    train = info.get("sample_ids", {}).get("train")
    if not train:
        raise SupportError(f"{directory / 'run.json'} no lista `sample_ids.train`.")
    missing = sorted(sample for sample in train if sample not in fractions)
    if missing:
        raise SupportError(f"Animales de train sin composición medida: {missing}.")
    return EmpiricalSupport.fit(
        [fractions[sample] for sample in train],
        source=(
            f"train de la corrida {info.get('run_id', directory.name)} "
            f"(semilla {info.get('seed')}, fold {info.get('fold')})"
        ),
        days=None if days is None else [days[sample] for sample in train],
    )


__all__ = [
    "CLOSURE_TOLERANCE",
    "COMPONENTS",
    "ESTIMABLE",
    "NOT_ESTIMABLE",
    "SUPPORT_VERSION",
    "EmpiricalSupport",
    "SupportError",
    "SupportResult",
    "support_from_run",
]
