"""Incertidumbre, calibración y coherencia bioquímica de las predicciones de D1 (A75, #282).

- **A75-P1 (#283).** En cada fold del plan de #139 entrena un ensamble de `--ensemble-size`
  modelos (`hetero_sage` por omisión, con `TaxonIdentityConfig()`, la configuración que #268
  decidió no cambiar) y aplica MC-dropout de `--mc-passes` pasadas sobre el modelo del fold. Cada
  animal de test recibe media e intervalos de los dos métodos, con el modelo del fold en que estuvo
  en test. El método de cada fold se elige con la NLL del val interno (`select_method`).
- **A75-P2 (#284).** Mide la cobertura al 50, 80 y 90 % en el val interno, por salida y por día,
  antes y después de un factor de escala ajustado **solo** con ese val interno, y evalúa una sola
  vez en el test de los folds.
- **A75-P3 (#285).** Comprueba en las predicciones de test el cierre de las fracciones, la cota de
  D-06 (`p_p ≤ 2/3`) y el soporte empírico del train (D-06, sección 7), y compara las fracciones
  predichas con las medidas por día y con la Tabla 6 de D-06.

Escribe en `--output` (por defecto `reports/uncertainty/d1/`):

- `fold_coverage.csv`: cubiertos y ancho medio por fold, subconjunto, método, calibración, nivel,
  salida y día (incremental);
- `predictions.csv`: punto e intervalos de cada animal de test por método y calibración, y la
  predicción del modelo del fold (`reference`), incremental;
- `selection.csv`: NLL del val interno, método elegido, factores, épocas y soporte por fold;
- `coverage.csv`: cobertura nominal y observada con su dispersión entre folds;
- `coherence.csv`: hallazgos de la revisión de coherencia, con estado y fuente;
- `report.md` y `run.json`.

Uso:

    python scripts/estimate_uncertainty.py                       # 10 semillas × 5 folds
    python scripts/estimate_uncertainty.py --resume              # retoma una corrida cortada
    python scripts/estimate_uncertainty.py --report-only         # rehace los agregados
    python scripts/estimate_uncertainty.py --seeds 0 --ensemble-size 2 --mc-passes 5 \\
        --max-epochs 3 --output <carpeta>                        # humo rápido

Código de salida: `0` si escribió el reporte; `2` si faltan datos o grafos.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
import time
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any, Final

import torch

from nutrigraphdt.models.gnn.factory import load_model_config
from nutrigraphdt.models.training import load_training_config
from nutrigraphdt.models.training.cv_inputs import load_d1_cv_inputs
from nutrigraphdt.models.training.taxon_identity import TaxonIdentityConfig
from nutrigraphdt.models.training.tracking import environment_info, git_info
from nutrigraphdt.models.uncertainty import (
    CALIBRATION_LEVEL,
    DEFAULT_ENSEMBLE_SIZE,
    DEFAULT_FRACTION_DRAWS,
    DEFAULT_LEVELS,
    DEFAULT_MC_PASSES,
    FRACTION_NAMES,
    METHODS,
    OUTPUT_NAMES,
    UNCERTAINTY_FORMAT_VERSION,
    FoldUncertainty,
    combined_intervals,
    fractions_from_outputs,
    observed_with_fractions,
    run_uncertainty_fold,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = REPO_ROOT / "configs" / "sources.json"
DEFAULT_GRAPHS = REPO_ROOT / "artifacts" / "graphs" / "D1_holofood"
DEFAULT_PLAN = REPO_ROOT / "configs" / "splits" / "d1_holofood_cv.json"
DEFAULT_TRAINING_CONFIG = REPO_ROOT / "configs" / "training" / "default.json"
DEFAULT_MODEL_CONFIGS = REPO_ROOT / "configs" / "models"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "uncertainty" / "d1"
DEFAULT_VARIANT: Final = "hetero_sage"
TRAIN_SEED_BASE: Final = 42000
"""La base de semillas de #142, #185 y #266: el miembro 0 es el modelo de esas evaluaciones."""

ALL: Final = "all"
SUBSETS: Final = ("inner_val", "test")
SELECTED: Final = "selected"
"""Método «elegido»: en cada fold, el que eligió `select_method` con el val interno."""
REFERENCE: Final = "reference"
CLOSURE_TOLERANCE: Final = 1e-9
"""Tolerancia numérica del cierre de las fracciones (no es un valor científico)."""
D06_BOUND: Final = 2.0 / 3.0
D06_SOURCE: Final = "docs/research/D-06 — Restricciones bioquímicas para D1.md"
TABLE6: Final = (
    ("van der Wielen et al. (2000)", "≥ 15", 0.686, 0.078, 0.235),
    ("Mátis et al. (2022), control", "10", 0.908, 0.025, 0.067),
    ("Mátis et al. (2022), control", "21", 0.852, 0.047, 0.101),
    ("Bautil et al. (2021)", "36", 0.748, 0.116, 0.136),
)
"""Tabla 6 de D-06 (sección 5): medias de grupo de fuentes independientes de D1."""
WILSON_Z: Final = 1.959963984540054
"""Cuantil normal del 97,5 % para el intervalo de Wilson al 95 %."""

COVERAGE_HEADER: Final = [
    "seed",
    "fold",
    "subset",
    "method",
    "calibrated",
    "level",
    "output",
    "day",
    "n",
    "covered",
    "mean_width",
]
PREDICTION_HEADER: Final = [
    "seed",
    "fold",
    "sample_id",
    "sampling_day",
    "method",
    "selected",
    "calibrated",
    "output",
    "observed",
    "point",
    *[f"{bound}_{round(level * 100)}" for level in DEFAULT_LEVELS for bound in ("lower", "upper")],
]
SELECTION_HEADER: Final = [
    "seed",
    "fold",
    "train_seed",
    "selected",
    *[f"nll_{m}" for m in METHODS],
    *[f"scale_{m}_{o}" for m in METHODS for o in OUTPUT_NAMES[:3]],
    *[f"support_{f}_{b}" for f in FRACTION_NAMES for b in ("min", "max")],
    "member_epochs",
    "n_train",
    "n_inner_val",
    "n_test",
    "duration_seconds",
]

EXIT_OK: Final = 0
EXIT_INPUT: Final = 2


# ---------------------------------------------------------------------------
# Escritura incremental
# ---------------------------------------------------------------------------


def _append(path: Path, header: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(header), lineterminator="\n")
        if new:
            writer.writeheader()
        writer.writerows(rows)


def _read(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def coverage_rows(
    result: FoldUncertainty, days: Mapping[str, str], levels: Sequence[float], draws: int
) -> list[dict[str, Any]]:
    """Cubiertos y ancho medio por subconjunto, método, calibración, nivel, salida y día."""
    rows: list[dict[str, Any]] = []
    for subset in SUBSETS:
        distributions = result.inner_val if subset == "inner_val" else result.test
        observed = observed_with_fractions(
            result.observed_inner_val if subset == "inner_val" else result.observed_test
        )
        for method, distribution in distributions.items():
            labels = [method, SELECTED] if method == result.selected else [method]
            day_of = [days.get(s, "?") for s in distribution.sample_ids]
            groups = {ALL: list(range(len(day_of)))}
            for index, day in enumerate(day_of):
                groups.setdefault(day, []).append(index)
            for calibrated in (False, True):
                scale = result.scales[method] if calibrated else None
                for level in levels:
                    _, lower, upper = combined_intervals(
                        distribution, level, scale, draws=draws, seed=result.train_seed
                    )
                    inside = (observed >= lower) & (observed <= upper)
                    width = upper - lower
                    for day, index in groups.items():
                        for column, output in enumerate(OUTPUT_NAMES):
                            valid = [i for i in index if math.isfinite(float(observed[i, column]))]
                            for label in labels:
                                rows.append(
                                    {
                                        "seed": result.seed,
                                        "fold": result.fold,
                                        "subset": subset,
                                        "method": label,
                                        "calibrated": calibrated,
                                        "level": level,
                                        "output": output,
                                        "day": day,
                                        "n": len(valid),
                                        "covered": sum(bool(inside[i, column]) for i in valid),
                                        "mean_width": statistics.fmean(
                                            float(width[i, column]) for i in valid
                                        )
                                        if valid
                                        else "",
                                    }
                                )
    return rows


def prediction_rows(
    result: FoldUncertainty, days: Mapping[str, str], levels: Sequence[float], draws: int
) -> list[dict[str, Any]]:
    """Punto e intervalos de cada animal de test; `reference` es el modelo del fold."""
    observed = observed_with_fractions(result.observed_test)
    rows: list[dict[str, Any]] = []
    ids = result.test[METHODS[0]].sample_ids
    reference_outputs = result.reference_test.to(torch.float64)
    reference = torch.cat([reference_outputs, fractions_from_outputs(reference_outputs)], dim=1)
    for row, sample_id in enumerate(ids):
        for column, output in enumerate(OUTPUT_NAMES):
            rows.append(
                {
                    "seed": result.seed,
                    "fold": result.fold,
                    "sample_id": sample_id,
                    "sampling_day": days.get(sample_id, "?"),
                    "method": REFERENCE,
                    "selected": False,
                    "calibrated": False,
                    "output": output,
                    "observed": float(observed[row, column]),
                    "point": float(reference[row, column]),
                }
            )
    for method, distribution in result.test.items():
        for calibrated in (False, True):
            scale = result.scales[method] if calibrated else None
            bounds = {
                level: combined_intervals(
                    distribution, level, scale, draws=draws, seed=result.train_seed
                )
                for level in levels
            }
            for row, sample_id in enumerate(distribution.sample_ids):
                for column, output in enumerate(OUTPUT_NAMES):
                    item: dict[str, Any] = {
                        "seed": result.seed,
                        "fold": result.fold,
                        "sample_id": sample_id,
                        "sampling_day": days.get(sample_id, "?"),
                        "method": method,
                        "selected": method == result.selected,
                        "calibrated": calibrated,
                        "output": output,
                        "observed": float(observed[row, column]),
                        "point": float(bounds[levels[0]][0][row, column]),
                    }
                    for level, (_, lower, upper) in bounds.items():
                        item[f"lower_{round(level * 100)}"] = float(lower[row, column])
                        item[f"upper_{round(level * 100)}"] = float(upper[row, column])
                    rows.append(item)
    return rows


def selection_row(result: FoldUncertainty) -> dict[str, Any]:
    row: dict[str, Any] = {
        "seed": result.seed,
        "fold": result.fold,
        "train_seed": result.train_seed,
        "selected": result.selected,
        "member_epochs": " ".join(str(e) for e in result.member_epochs),
        "n_train": result.n_train,
        "n_inner_val": result.n_inner_val,
        "n_test": len(result.test[METHODS[0]].sample_ids),
        "duration_seconds": round(result.duration_seconds, 1),
    }
    for method in METHODS:
        row[f"nll_{method}"] = result.nll[method]
        for output, value in zip(OUTPUT_NAMES[:3], result.scales[method], strict=True):
            row[f"scale_{method}_{output}"] = value
    for fraction, (low, high) in zip(FRACTION_NAMES, result.train_fraction_support, strict=True):
        row[f"support_{fraction}_min"] = low
        row[f"support_{fraction}_max"] = high
    return row


# ---------------------------------------------------------------------------
# Agregados
# ---------------------------------------------------------------------------


def wilson(covered: int, n: int) -> tuple[float, float]:
    """Intervalo de Wilson al 95 % de una proporción."""
    if n == 0:
        return (math.nan, math.nan)
    p = covered / n
    denominator = 1 + WILSON_Z**2 / n
    center = (p + WILSON_Z**2 / (2 * n)) / denominator
    half = WILSON_Z * math.sqrt(p * (1 - p) / n + WILSON_Z**2 / (4 * n * n)) / denominator
    return (center - half, center + half)


def verdict(nominal: float, low: float, high: float) -> str:
    if math.isnan(low):
        return "sin datos"
    if nominal < low:
        return "sobrecobertura"
    if nominal > high:
        return "subcobertura"
    return "compatible"


def aggregate_coverage(rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    """Cobertura observada por grupo: media y desviación entre folds, y agregado por semilla.

    En el test, cada semilla del plan reparte a todos los animales en sus folds: la cobertura por
    semilla tiene `n` animales independientes. El intervalo de Wilson usa ese `n` (no la suma de
    las semillas, que repite animales) sobre la media de la cobertura por semilla.
    """
    groups: dict[tuple[str, ...], list[Mapping[str, str]]] = defaultdict(list)
    for row in rows:
        key = (
            row["subset"],
            row["method"],
            row["calibrated"],
            row["level"],
            row["output"],
            row["day"],
        )
        groups[key].append(row)
    result: list[dict[str, Any]] = []
    for key, items in sorted(groups.items()):
        per_fold = [int(r["covered"]) / int(r["n"]) for r in items if int(r["n"]) > 0]
        by_seed: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        widths = [float(r["mean_width"]) for r in items if r["mean_width"] not in ("", None)]
        for r in items:
            by_seed[r["seed"]][0] += int(r["covered"])
            by_seed[r["seed"]][1] += int(r["n"])
        seed_coverage = [c / n for c, n in by_seed.values() if n > 0]
        animals = round(statistics.fmean(n for _, n in by_seed.values())) if by_seed else 0
        mean = statistics.fmean(seed_coverage) if seed_coverage else math.nan
        low, high = wilson(round(mean * animals), animals) if seed_coverage else (math.nan,) * 2
        nominal = float(key[3])
        result.append(
            {
                "subset": key[0],
                "method": key[1],
                "calibrated": key[2],
                "level": nominal,
                "output": key[4],
                "day": key[5],
                "observed": mean,
                "fold_std": statistics.stdev(per_fold) if len(per_fold) > 1 else math.nan,
                "seed_std": statistics.stdev(seed_coverage) if len(seed_coverage) > 1 else math.nan,
                "n_folds": len(per_fold),
                "animals_per_seed": animals,
                "wilson_low": low,
                "wilson_high": high,
                "verdict": verdict(nominal, low, high) if key[0] == "test" else "",
                "mean_width": statistics.fmean(widths) if widths else math.nan,
            }
        )
    return result


def coherence_findings(
    predictions: Sequence[Mapping[str, str]], selection: Sequence[Mapping[str, str]]
) -> list[dict[str, Any]]:
    """Hallazgos de A75-P3 sobre las predicciones de test del modelo del fold (`reference`)."""
    by_animal: dict[tuple[str, str, str], dict[str, float]] = defaultdict(dict)
    observed: dict[tuple[str, str, str], dict[str, float]] = defaultdict(dict)
    days: dict[tuple[str, str, str], str] = {}
    for row in predictions:
        if row["method"] != REFERENCE:
            continue
        key = (row["seed"], row["fold"], row["sample_id"])
        by_animal[key][row["output"]] = float(row["point"])
        observed[key][row["output"]] = float(row["observed"])
        days[key] = row["sampling_day"]
    support = {
        (r["seed"], r["fold"]): {
            f: (float(r[f"support_{f}_min"]), float(r[f"support_{f}_max"])) for f in FRACTION_NAMES
        }
        for r in selection
    }
    findings: list[dict[str, Any]] = []
    closure = max(abs(sum(v[f] for f in FRACTION_NAMES) - 1.0) for v in by_animal.values())
    findings.append(
        {
            "id": "A75-C1",
            "check": "Cierre de las fracciones predichas",
            "value": f"máx. abs(p_a + p_p + p_b − 1) = {closure:.1e} "
            f"en {len(by_animal)} predicciones",
            "status": "coherente" if closure <= CLOSURE_TOLERANCE else "a revisar",
            "source": "Contrato de datos v2, sección 1 (softmax de (0, z1, z2))",
        }
    )
    propionate = [v["propionate"] for v in by_animal.values()]
    above = sum(p > D06_BOUND for p in propionate)
    findings.append(
        {
            "id": "A75-C2",
            "check": "Cota de D-06: p_p ≤ 2/3",
            "value": f"{above} de {len(propionate)} sobre la cota; "
            f"máximo p_p = {max(propionate):.3f}",
            "status": "coherente" if above == 0 else "a revisar",
            "source": f"{D06_SOURCE}, secciones 3 y 6",
        }
    )
    outside = defaultdict(int)
    for key, values in by_animal.items():
        bounds = support[(key[0], key[1])]
        for fraction in FRACTION_NAMES:
            low, high = bounds[fraction]
            outside[fraction] += not low <= values[fraction] <= high
    total_outside = sum(outside.values())
    findings.append(
        {
            "id": "A75-C3",
            "check": "Soporte empírico del train interno (mínimo y máximo por fracción)",
            "value": "; ".join(f"{f}: {outside[f]} fuera" for f in FRACTION_NAMES)
            + f" (de {len(by_animal)})",
            "status": "coherente" if total_outside == 0 else "a revisar",
            "source": f"{D06_SOURCE}, sección 7; `EmpiricalSupport` de #245",
        }
    )
    day_values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    day_observed: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for key, values in by_animal.items():
        for fraction in FRACTION_NAMES:
            day_values[days[key]][fraction].append(values[fraction])
            if math.isfinite(observed[key][fraction]):
                day_observed[days[key]][fraction].append(observed[key][fraction])
    for day in sorted(day_values, key=lambda d: (len(d), d)):
        parts = []
        status = "coherente"
        for fraction in FRACTION_NAMES:
            predicted = statistics.fmean(day_values[day][fraction])
            measured = day_observed[day][fraction]
            low, high = min(measured), max(measured)
            parts.append(
                f"{fraction} {predicted:.3f} (medida {statistics.fmean(measured):.3f}, "
                f"rango {low:.3f}–{high:.3f})"
            )
            if not low <= predicted <= high:
                status = "a revisar"
        findings.append(
            {
                "id": f"A75-C4-d{day}",
                "check": f"Fracción media predicha frente a la medida, día {day}",
                "value": "; ".join(parts),
                "status": status,
                "source": "Cohorte oficial de D1 (configs/cohorts/d1_holofood.json), "
                "test de los folds",
            }
        )
    literature_max = max(row[3] for row in TABLE6)
    findings.append(
        {
            "id": "A75-C5",
            "check": "Fracciones predichas frente a la Tabla 6 de D-06 (medias de grupo)",
            "value": f"p_p predicha: media {statistics.fmean(propionate):.3f}, máximo "
            f"{max(propionate):.3f}; máximo publicado {literature_max:.3f}",
            "status": "sin fuente",
            "source": f"{D06_SOURCE}, sección 5 y Tabla 7, N° 4: no hay rangos por animal",
        }
    )
    return findings


# ---------------------------------------------------------------------------
# Reporte
# ---------------------------------------------------------------------------


def _pct(value: float) -> str:
    return "—" if not math.isfinite(value) else f"{100 * value:.0f} %"


def _find(coverage: Sequence[Mapping[str, Any]], **where: Any) -> Mapping[str, Any] | None:
    for row in coverage:
        if all(str(row[k]) == str(v) for k, v in where.items()):
            return row
    return None


def build_report(context: Mapping[str, Any]) -> str:
    coverage = context["coverage"]
    selection = context["selection"]
    levels = context["levels"]
    counts = {m: sum(r["selected"] == m for r in selection) for m in METHODS}
    lines = [
        "# Incertidumbre, calibración y coherencia de las predicciones de D1 (A75, #282)",
        "",
        "Generado con `python scripts/estimate_uncertainty.py`. Modelo: "
        f"`{context['variant']}` con `TaxonIdentityConfig()`; plan de #139 con las semillas "
        f"{context['seeds']} ({len(selection)} folds); ensamble de {context['ensemble_size']} "
        f"modelos por fold y MC-dropout de {context['mc_passes']} pasadas. Dispositivo "
        f"`{context['device']}`.",
        "",
        "**Revisión de Desarrollo, no aprobación de Investigación.** Con 56 animales, la "
        "cobertura por día es **muy ruidosa**: cada día tiene pocos animales por fold.",
        "",
        "## Elección del método (solo con el val interno)",
        "",
        "En cada fold se elige el método con menor log-verosimilitud negativa (NLL) de la normal "
        "predictiva en el val interno, sin escalar; el test no interviene. "
        + ", ".join(f"`{m}`: {counts[m]} folds" for m in METHODS)
        + ".",
        "",
        "## Cobertura en el val interno (antes y después del factor)",
        "",
        "Media entre folds ± desviación entre folds. El factor de cada salida se ajusta al "
        f"{round(100 * CALIBRATION_LEVEL)} % con el mismo val interno, así que su cobertura "
        "después del ajuste es optimista por construcción.",
        "",
        "| Método | Salida | "
        + " | ".join(f"{round(100 * lv)} % antes | {round(100 * lv)} % después" for lv in levels)
        + " |",
        "|---|---|" + "---:|---:|" * len(levels),
    ]
    for method in (*METHODS, SELECTED):
        for output in OUTPUT_NAMES:
            cells = []
            for level in levels:
                for calibrated in (False, True):
                    row = _find(
                        coverage,
                        subset="inner_val",
                        method=method,
                        calibrated=calibrated,
                        level=level,
                        output=output,
                        day=ALL,
                    )
                    cells.append(
                        "—" if row is None else f"{_pct(row['observed'])} ± {_pct(row['fold_std'])}"
                    )
            lines.append(f"| `{method}` | `{output}` | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Cobertura en el test de los folds (una sola evaluación)",
        "",
        "Método elegido en cada fold, con su factor del val interno. Cobertura media por semilla "
        "(cada semilla reparte a los 56 animales), desviación entre semillas, intervalo de Wilson "
        "al 95 % con n = animales por semilla y veredicto: `compatible` si el nominal cae en el "
        "intervalo; si no, `subcobertura` o `sobrecobertura`.",
        "",
        "| Salida | Nivel | Observada | Desv. semillas | Wilson 95 % | Ancho medio | Veredicto |",
        "|---|---:|---:|---:|---|---:|---|",
    ]
    for output in OUTPUT_NAMES:
        for level in levels:
            row = _find(
                coverage,
                subset="test",
                method=SELECTED,
                calibrated=True,
                level=level,
                output=output,
                day=ALL,
            )
            if row is None:
                continue
            lines.append(
                f"| `{output}` | {round(100 * level)} % | {_pct(row['observed'])} | "
                f"{_pct(row['seed_std'])} | {_pct(row['wilson_low'])}–{_pct(row['wilson_high'])} "
                f"| {row['mean_width']:.3g} | {row['verdict']} |"
            )
    verdicts = [
        r["verdict"]
        for r in coverage
        if r["subset"] == "test"
        and r["method"] == SELECTED
        and r["calibrated"] in (True, "True")
        and r["day"] == ALL
    ]
    calibrated_ok = bool(verdicts) and all(v == "compatible" for v in verdicts)
    lines += [
        "",
        "**Conclusión de calibración:** "
        + (
            "los intervalos calibrados son compatibles con su nivel nominal en todas las salidas "
            "y niveles del test."
            if calibrated_ok
            else "**los intervalos no están calibrados** en el test en "
            f"{sum(v != 'compatible' for v in verdicts)} de {len(verdicts)} combinaciones de "
            "salida y nivel (ver la tabla); no se deben citar como intervalos de ese nivel."
        ),
        "",
        "Sin el factor (intervalos crudos de cada método), en el test:",
        "",
        "| Método | Salida | " + " | ".join(f"{round(100 * lv)} %" for lv in levels) + " |",
        "|---|---|" + "---:|" * len(levels),
    ]
    for method in METHODS:
        for output in OUTPUT_NAMES:
            cells = []
            for level in levels:
                row = _find(
                    coverage,
                    subset="test",
                    method=method,
                    calibrated=False,
                    level=level,
                    output=output,
                    day=ALL,
                )
                cells.append("—" if row is None else _pct(row["observed"]))
            lines.append(f"| `{method}` | `{output}` | " + " | ".join(cells) + " |")
    lines += [
        "",
        "### Por día de muestreo (test, método elegido, calibrado, 80 %)",
        "",
        "| Salida | " + " | ".join(f"día {d}" for d in context["days"]) + " |",
        "|---|" + "---:|" * len(context["days"]),
    ]
    for output in OUTPUT_NAMES:
        cells = []
        for day in context["days"]:
            row = _find(
                coverage,
                subset="test",
                method=SELECTED,
                calibrated=True,
                level=0.8,
                output=output,
                day=day,
            )
            cells.append(
                "—"
                if row is None
                else f"{_pct(row['observed'])} ± {_pct(row['seed_std'])} "
                f"(n≈{row['animals_per_seed']})"
            )
        lines.append(f"| `{output}` | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Coherencia bioquímica (A75-P3)",
        "",
        "Sobre la predicción de test del modelo de cada fold (el miembro 0 del ensamble, que es el "
        "de #266). Estados: `coherente`, `a revisar` o `sin fuente`. Detalle y fuentes en "
        "[`docs/models/a75-biochemical-coherence.md`](../../../docs/models/a75-biochemical-coherence.md).",
        "",
        "| ID | Comprobación | Resultado | Estado | Fuente |",
        "|---|---|---|---|---|",
    ]
    for finding in context["coherence"]:
        lines.append(
            f"| {finding['id']} | {finding['check']} | {finding['value']} | "
            f"{finding['status']} | {finding['source']} |"
        )
    lines += [
        "",
        "## Limitaciones",
        "",
        f"- La dispersión de un ensamble de {context['ensemble_size']} modelos o de "
        f"{context['mc_passes']} pasadas de MC-dropout mide la "
        "variabilidad del modelo, no el error de predicción; por eso el factor del val interno "
        "puede ser grande.",
        "- El val interno tiene unos 10 animales por fold: el factor de escala de cada fold es "
        "ruidoso. No se agrega entre folds porque el val interno de un fold puede contener "
        "animales del test de otro.",
        "- Los intervalos en `(z_1, z_2, ln T)` suponen una normal por salida; los de fracciones "
        "muestrean `z_1` y `z_2` como independientes.",
        "- El val interno también decide la detención temprana: la NLL y el factor se calculan "
        "sobre animales que ya influyeron en el entrenamiento.",
    ]
    if context.get("note"):
        lines += ["", f"Nota: {context['note']}"]
    return "\n".join(lines) + "\n"


def write_aggregates(output: Path, context: dict[str, Any]) -> str:
    coverage = aggregate_coverage(_read(output / "fold_coverage.csv"))
    selection = _read(output / "selection.csv")
    predictions = _read(output / "predictions.csv")
    with (output / "coverage.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(coverage[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(coverage)
    coherence = coherence_findings(predictions, selection)
    with (output / "coherence.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(coherence[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(coherence)
    days = sorted({r["day"] for r in coverage if r["day"] != ALL}, key=lambda d: (len(d), d))
    report = build_report(
        {
            **context,
            "coverage": coverage,
            "selection": selection,
            "coherence": coherence,
            "days": days,
        }
    )
    (output / "report.md").write_text(report, encoding="utf-8", newline="\n")
    return report


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--graphs-dir", type=Path, default=DEFAULT_GRAPHS)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--training-config", type=Path, default=DEFAULT_TRAINING_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--variant", default=DEFAULT_VARIANT)
    parser.add_argument("--seeds", nargs="+", type=int, default=None)
    parser.add_argument("--ensemble-size", type=int, default=DEFAULT_ENSEMBLE_SIZE)
    parser.add_argument("--mc-passes", type=int, default=DEFAULT_MC_PASSES)
    parser.add_argument("--draws", type=int, default=DEFAULT_FRACTION_DRAWS)
    parser.add_argument("--max-epochs", type=int, default=None)
    parser.add_argument("--patience", type=int, default=None)
    parser.add_argument("--device", default=None)
    parser.add_argument("--resume", action="store_true", help="Retoma los folds ya escritos.")
    parser.add_argument(
        "--report-only", action="store_true", help="Rehace los agregados sin entrenar."
    )
    parser.add_argument("--note", default="", help="Nota de procedencia para el reporte.")
    args = parser.parse_args(argv)

    started = time.monotonic()
    levels = DEFAULT_LEVELS
    try:
        inputs = load_d1_cv_inputs(args.sources, args.graphs_dir, args.plan)
        seeds = list(args.seeds if args.seeds is not None else inputs.plan.seeds)
        unknown = sorted(set(seeds) - set(inputs.plan.seeds))
        if unknown:
            raise ValueError(f"Semillas que no están en el plan: {unknown}.")
        updates: dict[str, Any] = {"dataset_id": inputs.dataset_id}
        for name in ("device", "max_epochs", "patience"):
            if getattr(args, name) is not None:
                updates[name] = getattr(args, name)
        training = load_training_config(args.training_config).model_copy(update=updates)
        model_config = load_model_config(DEFAULT_MODEL_CONFIGS / f"{args.variant}.yaml")
    except (FileNotFoundError, KeyError, ValueError) as error:
        print(f"No se pudo preparar la estimación: {error}", file=sys.stderr)
        return EXIT_INPUT

    identity = TaxonIdentityConfig()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    incremental = ("fold_coverage.csv", "predictions.csv", "selection.csv")
    if not (args.resume or args.report_only):
        for name in incremental:
            (output / name).unlink(missing_ok=True)
    done = {(int(r["seed"]), int(r["fold"])) for r in _read(output / "selection.csv")}

    total = len(seeds) * inputs.plan.k
    count = 0
    for seed in [] if args.report_only else seeds:
        for fold, (train_ids, test_ids) in enumerate(inputs.plan.folds(seed)):
            count += 1
            if (seed, fold) in done:
                continue
            train_seed = TRAIN_SEED_BASE + seed * 100 + fold
            result = run_uncertainty_fold(
                seed=seed,
                fold=fold,
                train_ids=train_ids,
                test_ids=test_ids,
                graphs=inputs.graphs,
                pens=inputs.pens,
                diets=inputs.diets,
                model_config=model_config,
                metadata=inputs.metadata,
                config=training.model_copy(update={"seed": train_seed}),
                taxon_identity=identity,
                ensemble_size=args.ensemble_size,
                mc_passes=args.mc_passes,
            )
            # La selección se escribe al final: marca el fold como completo para `--resume`.
            _append(
                output / "fold_coverage.csv",
                COVERAGE_HEADER,
                coverage_rows(result, inputs.days, levels, args.draws),
            )
            _append(
                output / "predictions.csv",
                PREDICTION_HEADER,
                prediction_rows(result, inputs.days, levels, args.draws),
            )
            _append(output / "selection.csv", SELECTION_HEADER, [selection_row(result)])
            print(
                f"[{count}/{total}] s{seed} f{fold}: {result.selected}, épocas "
                f"{list(result.member_epochs)}, {result.duration_seconds:.0f} s",
                flush=True,
            )

    if not _read(output / "selection.csv"):
        print("No hay folds terminados para agregar.", file=sys.stderr)
        return EXIT_INPUT
    elapsed = time.monotonic() - started
    context = {
        "variant": args.variant,
        "seeds": sorted({int(r["seed"]) for r in _read(output / "selection.csv")}),
        "ensemble_size": args.ensemble_size,
        "mc_passes": args.mc_passes,
        "levels": levels,
        "device": training.device,
        "note": args.note,
    }
    report = write_aggregates(output, context)
    run_info = {
        "issue": 282,
        "format_version": UNCERTAINTY_FORMAT_VERSION,
        "dataset_id": inputs.dataset_id,
        "command": "python scripts/estimate_uncertainty.py " + " ".join(argv or sys.argv[1:]),
        "plan_version": inputs.plan.version,
        "cohort": dict(inputs.cohort),
        "seeds": context["seeds"],
        "variant": args.variant,
        "model_config": model_config.model_dump(mode="json"),
        "identity": asdict(identity),
        "training_config": training.model_dump(mode="json"),
        "train_seed_base": TRAIN_SEED_BASE,
        "ensemble_size": args.ensemble_size,
        "mc_passes": args.mc_passes,
        "levels": list(levels),
        "calibration_level": CALIBRATION_LEVEL,
        "fraction_draws": args.draws,
        "selection_rule": "menor NLL normal en el val interno, sin escalar; empate: ensemble",
        "elapsed_seconds": round(elapsed, 1),
        "resumed": args.resume,
        "report_only": args.report_only,
        "note": args.note,
        "git": git_info(REPO_ROOT),
        "environment": environment_info(training.device),
    }
    (output / "run.json").write_text(
        json.dumps(run_info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    print(report)
    print(f"Archivos en {output} ({elapsed / 60:.1f} min).")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
