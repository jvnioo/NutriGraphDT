"""Búsqueda acotada de hiperparámetros y variabilidad por semilla (A45-5, #105).

Dos fases, sobre una partición fija:

1. **Grilla.** Para una variante, entrena cada combinación de `hidden_channels` y `num_layers`
   (por defecto 32/64/128 × 1/2/3, el rango del §6 de `docs/models/gnn-architecture.md`) con
   una misma semilla, y elige la de menor RMSE promedio de `val`. La selección **solo lee
   `val`**: `select_best` recibe las métricas de `test`, pero no las usa.
2. **Semillas.** Repite con varias semillas la configuración inicial de cada variante y la
   elegida, y resume media y desviación estándar de las métricas en `val` y `test`.

El entrenamiento se inyecta como una función (`TrainFn`): `scripts/tune_gnn.py` usa
`run_training` (A44-6) y los tests, una función rápida. Todo lo que se ajusta a los datos
(escalado, detención temprana) sigue ocurriendo dentro de cada corrida, solo con `train` y `val`.
"""

from __future__ import annotations

import csv
import io
import math
import statistics
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from nutrigraphdt.models.gnn.factory import GNNModelConfig, parse_model_config
from nutrigraphdt.models.metrics import EvaluationReport

GRID_HIDDEN_CHANNELS: Final[tuple[int, ...]] = (32, 64, 128)
GRID_NUM_LAYERS: Final[tuple[int, ...]] = (1, 2, 3)
DEFAULT_SEEDS: Final[tuple[int, ...]] = (42, 43, 44, 45, 46)
SELECTION_SPLIT: Final[str] = "val"
SELECTION_METRIC: Final[str] = "rmse"
SUMMARY_METRICS: Final[tuple[str, ...]] = ("rmse", "mae", "r2")
SUMMARY_SPLITS: Final[tuple[str, ...]] = ("val", "test")
INITIAL: Final[str] = "inicial"
SELECTED: Final[str] = "elegida"


@dataclass(frozen=True)
class RunOutcome:
    """Una corrida: configuración, semilla y métricas promedio por subconjunto.

    `averages[(split, metric)]` es el promedio no ponderado de los tres AGCC (la columna
    `average` de `EvaluationReport`).
    """

    model_config: GNNModelConfig
    seed: int
    run_id: str
    averages: Mapping[tuple[str, str], float] = field(default_factory=dict)

    @property
    def variant(self) -> str:
        return str(self.model_config.variant)

    @property
    def hidden_channels(self) -> int:
        return int(self.model_config.hidden_channels)

    @property
    def num_layers(self) -> int:
        return int(self.model_config.num_layers)

    def value(self, split: str, metric: str) -> float | None:
        return self.averages.get((split, metric))


TrainFn = Callable[[GNNModelConfig, int], RunOutcome]
"""Entrena `model_config` con la semilla indicada y devuelve el resultado."""


@dataclass(frozen=True)
class SummaryRow:
    """Media y desviación estándar (muestral) de una métrica sobre las semillas."""

    variant: str
    configuration: str
    hidden_channels: int
    num_layers: int
    split: str
    metric: str
    mean: float
    std: float
    n: int


@dataclass(frozen=True)
class TuningResult:
    """Resultado de `run_tuning`."""

    variant: str
    grid_seed: int
    grid: tuple[RunOutcome, ...]
    selected: RunOutcome
    seed_runs: Mapping[tuple[str, str], tuple[RunOutcome, ...]]
    summary: tuple[SummaryRow, ...]


def outcome_from_report(
    report: EvaluationReport, *, model_config: GNNModelConfig, seed: int, run_id: str
) -> RunOutcome:
    """Extrae los promedios de `report` (filas con `split`) para `model_config`."""
    averages = {
        (row.split, row.metric): float(row.average)
        for row in report.rows
        if row.split is not None and row.model == model_config.variant
    }
    return RunOutcome(model_config=model_config, seed=seed, run_id=run_id, averages=averages)


def with_capacity(
    model_config: GNNModelConfig, hidden_channels: int, num_layers: int
) -> GNNModelConfig:
    """Copia de `model_config` con otra capacidad, validada como un YAML de `configs/models/`.

    Raises:
        ModelConfigError: si la combinación es inválida (por ejemplo, `hidden_channels` no
            divisible por `heads` en `hetero_gat`).
    """
    data = {
        **model_config.model_dump(),
        "hidden_channels": hidden_channels,
        "num_layers": num_layers,
    }
    return parse_model_config(data, source=f"grilla {hidden_channels}×{num_layers}")


def grid_configs(
    base: GNNModelConfig,
    hidden_channels: Sequence[int] = GRID_HIDDEN_CHANNELS,
    num_layers: Sequence[int] = GRID_NUM_LAYERS,
) -> tuple[GNNModelConfig, ...]:
    """Las combinaciones de la grilla, en orden de `hidden_channels` y luego `num_layers`."""
    _check_values("hidden_channels", hidden_channels)
    _check_values("num_layers", num_layers)
    return tuple(
        with_capacity(base, hidden, layers) for hidden in hidden_channels for layers in num_layers
    )


def select_best(candidates: Sequence[RunOutcome]) -> RunOutcome:
    """La corrida con menor RMSE promedio de `val`.

    Solo se lee `val`. Un empate se resuelve por el modelo más chico (menos `hidden_channels` y
    luego menos `num_layers`).

    Raises:
        ValueError: si no hay candidatas o a alguna le falta el RMSE de `val`.
    """
    if not candidates:
        raise ValueError("No hay corridas candidatas para seleccionar.")
    missing = [c.run_id for c in candidates if _selection_value(c) is None]
    if missing:
        raise ValueError(f"Corridas sin RMSE promedio de val: {missing}")
    return min(
        candidates,
        key=lambda c: (_selection_value(c), c.hidden_channels, c.num_layers),
    )


def summarize(
    runs: Mapping[tuple[str, str], Sequence[RunOutcome]],
    metrics: Sequence[str] = SUMMARY_METRICS,
    splits: Sequence[str] = SUMMARY_SPLITS,
) -> tuple[SummaryRow, ...]:
    """Media y desviación estándar muestral por `(variante, configuración)`, subconjunto y
    métrica. Con una sola semilla, la desviación es `nan`."""
    rows: list[SummaryRow] = []
    for (variant, configuration), outcomes in runs.items():
        if not outcomes:
            continue
        first = outcomes[0]
        for split in splits:
            for metric in metrics:
                values = [v for o in outcomes if (v := o.value(split, metric)) is not None]
                if not values:
                    continue
                rows.append(
                    SummaryRow(
                        variant=variant,
                        configuration=configuration,
                        hidden_channels=first.hidden_channels,
                        num_layers=first.num_layers,
                        split=split,
                        metric=metric,
                        mean=statistics.fmean(values),
                        std=statistics.stdev(values) if len(values) > 1 else math.nan,
                        n=len(values),
                    )
                )
    return tuple(rows)


def run_tuning(
    initial_configs: Mapping[str, GNNModelConfig],
    variant: str,
    train: TrainFn,
    *,
    hidden_channels: Sequence[int] = GRID_HIDDEN_CHANNELS,
    num_layers: Sequence[int] = GRID_NUM_LAYERS,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    grid_seed: int | None = None,
) -> TuningResult:
    """Grilla para `variant` y repetición por semilla.

    `initial_configs` tiene la configuración inicial de cada variante que se repite con
    `seeds` (por ejemplo, las tres de `configs/models/`); debe incluir `variant`. La grilla usa
    `grid_seed`, por defecto la primera de `seeds`. Una misma configuración y semilla se entrena
    una sola vez y se reutiliza.

    Raises:
        ValueError: si `variant` no está en `initial_configs`, o `seeds` está vacía o repetida.
    """
    if variant not in initial_configs:
        raise ValueError(f"La variante {variant!r} no tiene configuración inicial.")
    _check_values("seeds", seeds, minimum=0)
    seed_for_grid = seeds[0] if grid_seed is None else grid_seed

    cache: dict[tuple[str, int], RunOutcome] = {}

    def train_once(config: GNNModelConfig, seed: int) -> RunOutcome:
        key = (_config_key(config), seed)
        if key not in cache:
            cache[key] = train(config, seed)
        return cache[key]

    grid = tuple(
        train_once(config, seed_for_grid)
        for config in grid_configs(initial_configs[variant], hidden_channels, num_layers)
    )
    selected = select_best(grid)

    seed_runs: dict[tuple[str, str], tuple[RunOutcome, ...]] = {}
    for name, config in initial_configs.items():
        seed_runs[(name, INITIAL)] = tuple(train_once(config, seed) for seed in seeds)
    seed_runs[(variant, SELECTED)] = tuple(
        train_once(selected.model_config, seed) for seed in seeds
    )
    return TuningResult(
        variant=variant,
        grid_seed=seed_for_grid,
        grid=grid,
        selected=selected,
        seed_runs=seed_runs,
        summary=summarize(seed_runs),
    )


# ---------------------------------------------------------------------------
# Salidas
# ---------------------------------------------------------------------------


def grid_to_csv(grid: Iterable[RunOutcome]) -> str:
    """Una fila por combinación de la grilla, **solo con métricas de `val`**."""
    header = ["variant", "hidden_channels", "num_layers", "seed", "run_id"]
    header += [f"val_{metric}" for metric in SUMMARY_METRICS]
    rows = [
        [o.variant, o.hidden_channels, o.num_layers, o.seed, o.run_id]
        + [_format(o.value(SELECTION_SPLIT, metric)) for metric in SUMMARY_METRICS]
        for o in grid
    ]
    return _csv(header, rows)


def seed_runs_to_csv(seed_runs: Mapping[tuple[str, str], Sequence[RunOutcome]]) -> str:
    """Una fila por corrida de la fase de semillas, con `val` y `test`."""
    header = ["variant", "configuration", "hidden_channels", "num_layers", "seed", "run_id"]
    header += [f"{s}_{m}" for s in SUMMARY_SPLITS for m in SUMMARY_METRICS]
    rows = [
        [variant, configuration, o.hidden_channels, o.num_layers, o.seed, o.run_id]
        + [_format(o.value(s, m)) for s in SUMMARY_SPLITS for m in SUMMARY_METRICS]
        for (variant, configuration), outcomes in seed_runs.items()
        for o in outcomes
    ]
    return _csv(header, rows)


def summary_to_csv(summary: Iterable[SummaryRow]) -> str:
    header = [
        "variant",
        "configuration",
        "hidden_channels",
        "num_layers",
        "split",
        "metric",
        "mean",
        "std",
        "n",
    ]
    rows = [
        [
            r.variant,
            r.configuration,
            r.hidden_channels,
            r.num_layers,
            r.split,
            r.metric,
            _format(r.mean),
            _format(r.std),
            r.n,
        ]
        for r in summary
    ]
    return _csv(header, rows)


def summary_to_markdown(summary: Sequence[SummaryRow], metric: str = SELECTION_METRIC) -> str:
    """Tabla `media ± desviación` de `metric` por variante y configuración, en `val` y `test`."""
    by_key: dict[tuple[str, str, int, int], dict[str, SummaryRow]] = {}
    for row in summary:
        if row.metric == metric:
            key = (row.variant, row.configuration, row.hidden_channels, row.num_layers)
            by_key.setdefault(key, {})[row.split] = row
    lines = [
        f"| Variante | Configuración | hidden × capas | {metric} val | {metric} test | Semillas |",
        "| :--- | :--- | :---: | :---: | :---: | ---: |",
    ]
    for (variant, configuration, hidden, layers), splits in by_key.items():
        n = max(r.n for r in splits.values())
        lines.append(
            f"| {variant} | {configuration} | {hidden} × {layers} | "
            f"{_pm(splits.get('val'))} | {_pm(splits.get('test'))} | {n} |"
        )
    return "\n".join(lines)


def selection_to_dict(result: TuningResult) -> dict[str, Any]:
    """Registro de la selección: criterio, candidatas con su valor de `val` y la elegida.

    No contiene métricas de `test`: es lo que muestra que `test` no intervino.
    """
    return {
        "variant": result.variant,
        "selection": {
            "split": SELECTION_SPLIT,
            "metric": f"{SELECTION_METRIC}_average",
            "rule": "mínimo; empate: menos hidden_channels y luego menos num_layers",
            "test_used": False,
        },
        "grid_seed": result.grid_seed,
        "candidates": [
            {
                "run_id": o.run_id,
                "hidden_channels": o.hidden_channels,
                "num_layers": o.num_layers,
                f"val_{SELECTION_METRIC}_average": o.value(SELECTION_SPLIT, SELECTION_METRIC),
            }
            for o in result.grid
        ],
        "selected": {
            "run_id": result.selected.run_id,
            "model_config": result.selected.model_config.model_dump(),
        },
    }


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _selection_value(outcome: RunOutcome) -> float | None:
    return outcome.value(SELECTION_SPLIT, SELECTION_METRIC)


def _config_key(config: GNNModelConfig) -> str:
    return repr(sorted(config.model_dump().items()))


def _check_values(name: str, values: Sequence[int], minimum: int = 1) -> None:
    if not values:
        raise ValueError(f"{name} no puede estar vacía.")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} tiene valores repetidos: {list(values)}")
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"{name} debe tener enteros >= {minimum}; se recibió {value!r}.")


def _format(value: float | None) -> str:
    if value is None or math.isnan(value):
        return ""
    return f"{value:.6f}"


def _pm(row: SummaryRow | None) -> str:
    if row is None:
        return "—"
    if math.isnan(row.std):
        return f"{row.mean:.4f}"
    return f"{row.mean:.4f} ± {row.std:.4f}"


def _csv(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


__all__ = [
    "DEFAULT_SEEDS",
    "GRID_HIDDEN_CHANNELS",
    "GRID_NUM_LAYERS",
    "INITIAL",
    "SELECTED",
    "SELECTION_METRIC",
    "SELECTION_SPLIT",
    "RunOutcome",
    "SummaryRow",
    "TrainFn",
    "TuningResult",
    "grid_configs",
    "grid_to_csv",
    "outcome_from_report",
    "run_tuning",
    "seed_runs_to_csv",
    "select_best",
    "selection_to_dict",
    "summarize",
    "summary_to_csv",
    "summary_to_markdown",
    "with_capacity",
]
