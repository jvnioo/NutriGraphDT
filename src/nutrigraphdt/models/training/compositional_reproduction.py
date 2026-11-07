"""Reproducción independiente de una corrida composicional por fold (A68-P4, #182).

Reentrena un fold guardado con `save_compositional_run` (#180) **solo desde archivos
versionados y su `run.json`**, sin copiar resultados de la corrida original, y compara:

1. **Plan de folds:** el SHA-256 canónico del plan (#133) es el registrado, así que un archivo con
   fin de línea CRLF o LF da el mismo resultado; los animales de `train`, `inner_val` y `test`
   coinciden con los registrados.
2. **Configuración:** entrenamiento, modelo, nombres de salida, λ, términos y restricciones
   monitoreadas.
3. **Escalado, épocas, historial, predicciones, métricas y violaciones**, con las tolerancias de
   `reproducibility` (A45-8), fijadas antes de comparar: `PREDICTIONS_TOLERANCE` (1e-4) para
   `(z_1, z_2, ln T)`, el historial y las magnitudes de violación; `METRICS_TOLERANCE` (1e-5) para
   `metrics.csv`; `SCALING_RTOL` (1e-6, relativa) para el escalado. Los conteos de violaciones
   deben ser iguales.
4. **Recarga:** el checkpoint original recargado reproduce su `predictions.csv` dentro de
   `RELOAD_ATOL` (#180).

Entre dispositivos distintos (CPU frente a GPU) o con núcleos no deterministas, la optimización
puede tomar otro camino desde la primera época. Esas diferencias se informan como tales; no se
ocultan ampliando tolerancias.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch

from nutrigraphdt.constraints import constraint_catalog
from nutrigraphdt.models.gnn import parse_model_config
from nutrigraphdt.models.training.compositional import FoldEvaluation, run_compositional_fold
from nutrigraphdt.models.training.compositional_tracking import (
    RELOAD_ATOL,
    load_compositional_run,
    plan_content_sha256,
    predict_compositional,
    run_metadata_problems,
)
from nutrigraphdt.models.training.config import parse_training_config
from nutrigraphdt.models.training.cv_inputs import CVInputs
from nutrigraphdt.models.training.reproducibility import (
    DIFFERS,
    METRICS_TOLERANCE,
    OK,
    PREDICTIONS_TOLERANCE,
    Check,
    ReproductionError,
    ReproductionReport,
    compare_rows,
    compare_scaling,
    read_csv,
)
from nutrigraphdt.models.training.taxon_identity import TaxonIdentityConfig

CONFIG_KEYS = (
    "variant",
    "edges_arm",
    "dataset_id",
    "seed",
    "fold",
    "train_seed",
    "training_config",
    "model_config",
    "target_names",
    "constraint_lambda",
    "constraint_terms",
    "monitored_constraints",
)
EPOCH_KEYS = ("best_epoch", "epochs_run", "stopped_early")


@dataclass(frozen=True)
class CompositionalReproduction:
    """Corrida reproducida y su comparación con la original."""

    original_dir: Path
    reproduced_dir: Path
    evaluation: FoldEvaluation
    report: ReproductionReport


def _equal(name: str, original: Any, new: Any) -> Check:
    if original == new:
        return Check(name, OK)
    return Check(name, DIFFERS, f"{original!r} ≠ {new!r}")


def _violation_counts(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], str]:
    return {
        (row["epoch"], row["subset"], row["constraint"]): row["violation_count"] for row in rows
    }


def reproduce_compositional_run(
    run_dir: str | Path,
    load_inputs: Callable[[Path], CVInputs],
    *,
    device: str = "cpu",
    plan_path: Path,
    output_runs_dir: Path | None = None,
) -> CompositionalReproduction:
    """Reentrena el fold de `run_dir` con `load_inputs(plan_path)` y lo compara con el original.

    `load_inputs` construye las entradas desde archivos versionados (por ejemplo,
    `load_synthetic_cv_inputs` o una función que llame a `load_d1_cv_inputs`).

    Raises:
        ReproductionError: si el `run.json` original está incompleto o el plan no es el
            registrado.
    """
    original_dir = Path(run_dir)
    info = json.loads((original_dir / "run.json").read_text(encoding="utf-8"))
    problems = run_metadata_problems(info)
    if problems:
        raise ReproductionError(f"{original_dir / 'run.json'}: " + "; ".join(problems) + ".")
    plan_digest = plan_content_sha256(json.loads(plan_path.read_text(encoding="utf-8")))
    if plan_digest != info["plan"]["sha256"]:
        raise ReproductionError(
            f"El plan {plan_path} (sha256 canónico {plan_digest[:12]}…) no es el registrado "
            f"({str(info['plan']['sha256'])[:12]}…)."
        )
    inputs = load_inputs(plan_path)
    training = parse_training_config(info["training_config"]).model_copy(update={"device": device})
    catalog = constraint_catalog()
    monitored = tuple(catalog[name] for name in info["monitored_constraints"])
    train_ids, test_ids = inputs.plan.folds(int(info["seed"]))[int(info["fold"])]
    runs_dir = output_runs_dir or Path(tempfile.mkdtemp(prefix="reproduce_"))
    evaluation = run_compositional_fold(
        seed=int(info["seed"]),
        fold=int(info["fold"]),
        model_name=str(info["variant"]),
        edges_arm=str(info["edges_arm"]),
        train_ids=train_ids,
        test_ids=test_ids,
        graphs=inputs.graphs,
        pens=inputs.pens,
        diets=inputs.diets,
        days=inputs.days,
        model_config=parse_model_config(info["model_config"]),
        metadata=inputs.metadata,
        config=training,
        monitor_constraints=monitored,
        runs_dir=runs_dir,
        taxon_identity=(
            TaxonIdentityConfig(**info["taxon_identity"]["config"])
            if info.get("taxon_identity")
            else None
        ),
        run_context={
            "dataset_id": inputs.dataset_id,
            "plan": {**info["plan"], "sha256": plan_digest},
            "cohort": dict(inputs.cohort),
            "source": dict(inputs.source),
        },
    )
    assert evaluation.run_dir is not None
    new_dir = evaluation.run_dir
    new_info = json.loads((new_dir / "run.json").read_text(encoding="utf-8"))

    checks = [
        Check("Plan de folds (SHA-256 canónico, #133)", OK, plan_digest[:12] + "…"),
        _equal("Animales de train, val interno y test", info["sample_ids"], new_info["sample_ids"]),
    ]
    # El dispositivo puede cambiar a propósito; el resto de la configuración debe ser igual.
    new_training = {**new_info["training_config"], "device": info["training_config"]["device"]}
    new_config = {**new_info, "training_config": new_training}
    checks += [_equal(f"Configuración: `{key}`", info[key], new_config[key]) for key in CONFIG_KEYS]
    checks.append(compare_scaling(info["scaling"], new_info["scaling"]))
    checks += [_equal(f"Épocas: `{key}`", info[key], new_info[key]) for key in EPOCH_KEYS]
    checks.append(
        compare_rows(
            "Historial por época (pérdidas de datos, bio y total)",
            read_csv(original_dir / "history.csv"),
            read_csv(new_dir / "history.csv"),
            ("epoch",),
            PREDICTIONS_TOLERANCE,
        )
    )
    checks.append(
        compare_rows(
            "Predicciones `(z_1, z_2, ln T)` del test",
            read_csv(original_dir / "predictions.csv"),
            read_csv(new_dir / "predictions.csv"),
            ("sample_id",),
            PREDICTIONS_TOLERANCE,
            columns=("z1", "z2", "log_total"),
        )
    )
    checks.append(
        compare_rows(
            "Métricas de D-03 del test (`metrics.csv`)",
            read_csv(original_dir / "metrics.csv"),
            read_csv(new_dir / "metrics.csv"),
            ("model", "split", "group", "metric"),
            METRICS_TOLERANCE,
        )
    )
    original_violations = read_csv(original_dir / "violations.csv")
    new_violations = read_csv(new_dir / "violations.csv")
    counts_equal = _violation_counts(original_violations) == _violation_counts(new_violations)
    checks.append(
        Check(
            "Violaciones: conteos por época, subconjunto y restricción",
            OK if counts_equal else DIFFERS,
            "" if counts_equal else "conteos distintos",
        )
    )
    checks.append(
        compare_rows(
            "Violaciones: magnitudes y tasas",
            original_violations,
            new_violations,
            ("epoch", "subset", "constraint"),
            PREDICTIONS_TOLERANCE,
            columns=(
                "violation_rate_percent",
                "mean_magnitude",
                "worst_case_magnitude",
                "joint_feasibility_percent",
            ),
        )
    )
    loaded = load_compositional_run(original_dir)
    stored = {row["sample_id"]: row for row in read_csv(original_dir / "predictions.csv")}
    ids, output = predict_compositional(loaded, [inputs.graphs[s] for s in sorted(stored)])
    worst = max(
        abs(float(output[row, column]) - float(stored[sample_id][name]))
        for row, sample_id in enumerate(ids)
        for column, name in enumerate(("z1", "z2", "log_total"))
    )
    checks.append(
        Check(
            "Recarga del checkpoint original",
            OK if worst <= RELOAD_ATOL else DIFFERS,
            "",
            worst,
            RELOAD_ATOL,
        )
    )
    notes = (
        f"Corrida original en `{info['environment'].get('device')}` "
        f"({info['environment'].get('device_name', info['environment'].get('platform'))}); "
        f"reproducida en `{device}`. Entre dispositivos distintos la optimización puede seguir "
        "otro camino desde la primera época, y esas diferencias se informan sin ampliar "
        "tolerancias.",
        f"PyTorch {info['environment'].get('torch')} → {torch.__version__}.",
    )
    report = ReproductionReport(
        original=info, reproduced=new_info, checks=tuple(checks), notes=notes
    )
    return CompositionalReproduction(original_dir, new_dir, evaluation, report)


def report_markdown(reproduction: CompositionalReproduction, command: str) -> str:
    """Reporte en Markdown, con el título de A68-P4."""
    return reproduction.report.to_markdown(command).replace("(A45-8)", "(A68-P4, #182)", 1)


def report_json(reproduction: CompositionalReproduction) -> dict[str, Any]:
    data = reproduction.report.to_dict()
    data["original_dir"] = reproduction.original_dir.as_posix()
    data["reproduced_run_id"] = reproduction.reproduced_dir.name
    return data


__all__ = [
    "CONFIG_KEYS",
    "EPOCH_KEYS",
    "CompositionalReproduction",
    "report_json",
    "report_markdown",
    "reproduce_compositional_run",
]
