"""Barrido acotado de λ con selección solo por validación interna (A68-P1, #178).

Corre la configuración versionada de `configs/constraints/lambda_sweep_<dataset>.json` sobre D1
o sobre la cohorte sintética de A68. Para cada variante, cada λ de la grilla y cada fold de las
semillas de selección, entrena con la pérdida compuesta `L_datos + λ·L_bio` usando solo el train
del fold (train interno y val interno por corral). Elige λ por variante con el criterio
declarado en la configuración (`nutrigraphdt.models.training.lambda_sweep`). El test de los
folds no se lee.

Escribe en `--output` (por defecto `reports/constraints/lambda_sweep/<dataset>/`):

- `sweep.csv`: una fila por `(variante, λ, semilla, fold)`, incluidas las fallidas, escrita de
  forma incremental;
- `selection.json`: λ elegida por variante, razón y resumen de cada candidata;
- `report.md`: método, tabla de candidatas, elección y limitaciones;
- `run.json`: configuración del barrido (con su SHA-256), plan, cohorte, Git, entorno y duración.

Uso:
    python scripts/sweep_constraint_lambda.py --dataset synthetic
    python scripts/sweep_constraint_lambda.py --dataset d1 --device cuda
    python scripts/sweep_constraint_lambda.py --dataset d1 --from-sweep   # sin reentrenar

Requiere los extras `graph` y `baselines`; D1 además necesita los grafos de
`scripts/build_graph.py --save-graphs`. Código de salida: `0` si escribió el reporte; `2` si
faltan datos, la configuración es inválida o supera el presupuesto.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from nutrigraphdt.models.gnn import load_model_config
from nutrigraphdt.models.training.compositional_tracking import plan_content_sha256
from nutrigraphdt.models.training.config import load_training_config
from nutrigraphdt.models.training.cv_inputs import (
    CVInputs,
    load_d1_cv_inputs,
    load_synthetic_cv_inputs,
)
from nutrigraphdt.models.training.lambda_sweep import (
    SWEEP_COLUMNS,
    SWEEP_FORMAT_VERSION,
    LambdaSelection,
    LambdaSweepConfig,
    SweepRow,
    load_lambda_sweep_config,
    read_sweep_rows,
    run_lambda_sweep,
    select_lambdas,
    trainings_needed,
)
from nutrigraphdt.models.training.tracking import environment_info, git_info

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASETS = ("d1", "synthetic")
DEFAULT_SOURCES = REPO_ROOT / "configs" / "sources.json"
DEFAULT_GRAPHS = REPO_ROOT / "artifacts" / "graphs" / "D1_holofood"
DEFAULT_TRAINING_CONFIG = REPO_ROOT / "configs" / "training" / "default.json"
DEFAULT_MODEL_CONFIGS = REPO_ROOT / "configs" / "models"
PLANS = {
    "d1": REPO_ROOT / "configs" / "splits" / "d1_holofood_cv.json",
    "synthetic": REPO_ROOT / "configs" / "splits" / "synthetic_cohort_cv.json",
}

EXIT_OK = 0
EXIT_INPUT = 2


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(REPO_ROOT).as_posix()
        if resolved.is_relative_to(REPO_ROOT)
        else path.as_posix()
    )


def _load_inputs(dataset: str, args: argparse.Namespace) -> CVInputs:
    plan = args.plan or PLANS[dataset]
    if dataset == "d1":
        return load_d1_cv_inputs(args.sources, args.graphs_dir, plan)
    return load_synthetic_cv_inputs(plan)


def _fmt(value: float | None, digits: int = 4) -> str:
    return "—" if value is None or math.isnan(value) else f"{value:.{digits}f}"


def build_report(
    *,
    config: LambdaSweepConfig,
    inputs: CVInputs,
    rows: Sequence[SweepRow],
    selections: Mapping[str, LambdaSelection],
    elapsed: float,
    config_path: str,
) -> str:
    failed = [row for row in rows if row.status != "ok"]
    lines = [
        f"# Barrido de λ en `{inputs.dataset_id}` (A68-P1, #178)",
        "",
        f"Generado con `python scripts/sweep_constraint_lambda.py` en {elapsed:.0f} s.",
        "",
        "## Método (fijado antes de correr)",
        "",
        f"- **Configuración:** `{config_path}` (versión {config.version}).",
        f"- **Grilla de λ:** {list(config.grid)}. Es una elección de Desarrollo, sin valor "
        "científico de referencia: cubre desde el brazo libre (λ = 0) hasta una penalización "
        "que domina la pérdida de datos estandarizada.",
        f"- **Pérdida:** `L_datos + λ·L_bio` con los términos {list(config.constraint_terms)}.",
        f"- **Folds de selección:** semillas {list(config.selection_seeds)} del plan "
        f"`{_relative(inputs.plan_path)}` (k = {inputs.plan.k}), {len(rows)} entrenamientos "
        f"(presupuesto: {config.max_trainings}). En cada fold solo se usa el train: un val "
        f"interno de 1/{config.inner_folds} de los grupos para la detención temprana y la "
        "selección. **El test de los folds no se lee.**",
        f"- **Entrenamiento:** variantes {list(config.variants)} con su YAML de "
        f"`configs/models/`; máx. {config.max_epochs} épocas, paciencia {config.patience}; "
        f"semilla `{config.train_seed_base} + semilla·100 + fold`.",
        "- **Candidatas:** las λ > 0 de la grilla. λ = 0 es el brazo libre $M_0$ del "
        "protocolo: se entrena en los mismos folds como referencia, pero no se elige.",
        "- **Criterio:** (1) factibilidad: se descartan las λ con VR > 0 de "
        f"`{config.feasibility_constraint}` en el val interno, en la mejor época de algún fold; "
        "(2) menor `val_data_loss` media (MSE estandarizado sin la penalización) entre las λ que "
        "entrenaron en todos los folds; (3) a igual media, la menor λ.",
        "",
        "## Candidatas",
        "",
        "| Variante | λ | Folds ok | `val_data_loss` (media ± std) | VR val interno (%) | "
        "Factible | Elegida |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for variant in config.variants:
        selection = selections[variant]
        for candidate in selection.candidates:
            chosen = "**sí**" if candidate.constraint_lambda == selection.selected_lambda else ""
            lines.append(
                f"| `{variant}` | {candidate.constraint_lambda:g} | "
                f"{candidate.folds_ok}/{candidate.folds_total} | "
                f"{_fmt(candidate.mean_val_data_loss)} ± {_fmt(candidate.std_val_data_loss)} | "
                f"{_fmt(candidate.mean_feasibility_violation_rate_percent, 2)} | "
                f"{'sí' if candidate.feasible else 'no'} | {chosen} |"
            )
    lines += ["", "## Elección", ""]
    for variant in config.variants:
        selection = selections[variant]
        lines.append(f"- `{variant}`: λ = {selection.selected_lambda:g} ({selection.reason}).")
    lines += [
        "",
        "## Advertencias y limitaciones",
        "",
        "- La λ elegida aquí es la que usa la evaluación pareada con y sin restricciones (#185). "
        "Ampliar la grilla después de ver resultados de evaluación exige registrar una fase "
        "exploratoria nueva.",
        "- Si todas las λ empatan exactamente, la penalización no cambió el entrenamiento: "
        "ninguna predicción del val interno violó la cota y su gradiente fue cero. D-06 §6 lo "
        "anticipa para D1 (p_p ≤ 0,12 en la literatura frente a la cota 2/3).",
        f"- Folds fallidos: {len(failed)} (`status = error` en `sweep.csv`).",
    ]
    if inputs.is_synthetic:
        lines.append(
            "- **Cohorte sintética.** Sus animales no son reales: cada uno es su propio grupo "
            "y no hay dietas ni días de muestreo."
        )
    lines += [
        "",
        "## Archivos",
        "",
        "- `sweep.csv`: una fila por variante, λ, semilla y fold, incluidas las fallidas.",
        "- `selection.json`: λ elegida, razón y candidatas por variante.",
        "- `run.json`: configuración (con SHA-256), plan, cohorte, Git, entorno y duración.",
        "",
    ]
    return "\n".join(lines)


def _run_and_write(
    sweep_path: Path,
    needed: int,
    config: LambdaSweepConfig,
    inputs: CVInputs,
    model_configs: Mapping[str, Any],
    base_training: Any,
) -> list[SweepRow]:
    """Corre el barrido y escribe `sweep.csv` fila a fila."""
    sweep_path.unlink(missing_ok=True)
    with sweep_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(SWEEP_COLUMNS), lineterminator="\n")
        writer.writeheader()
        done = 0

        def write(row: SweepRow) -> None:
            nonlocal done
            done += 1
            writer.writerow(row.to_dict())
            handle.flush()
            print(
                f"[{done}/{needed}] {row.variant} λ={row.constraint_lambda:g} s{row.seed} "
                f"f{row.fold}: {row.status} val_data_loss={row.val_data_loss}",
                flush=True,
            )

        rows = run_lambda_sweep(
            config=config,
            plan=inputs.plan,
            graphs=inputs.graphs,
            pens=inputs.pens,
            diets=inputs.diets,
            model_configs=model_configs,
            metadata=inputs.metadata,
            base_training=base_training,
            on_row=write,
        )
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset", choices=DATASETS, required=True)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--plan", type=Path, default=None)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--graphs-dir", type=Path, default=DEFAULT_GRAPHS)
    parser.add_argument("--training-config", type=Path, default=DEFAULT_TRAINING_CONFIG)
    parser.add_argument("--model-configs", type=Path, default=DEFAULT_MODEL_CONFIGS)
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--from-sweep",
        action="store_true",
        help="Vuelve a elegir y a escribir el reporte desde el sweep.csv de --output, sin "
        "reentrenar.",
    )
    args = parser.parse_args(argv)

    config_path = args.config or (
        REPO_ROOT / "configs" / "constraints" / f"lambda_sweep_{args.dataset}.json"
    )
    output = args.output or REPO_ROOT / "reports" / "constraints" / "lambda_sweep" / args.dataset
    started = time.monotonic()
    try:
        config = load_lambda_sweep_config(config_path)
        inputs = _load_inputs(args.dataset, args)
        if config.dataset_id != inputs.dataset_id:
            raise ValueError(
                f"La configuración es de {config.dataset_id!r} y los datos de "
                f"{inputs.dataset_id!r}."
            )
        base_training = load_training_config(args.training_config)
        base_training = base_training.model_copy(
            update={
                "dataset_id": inputs.dataset_id,
                **({"device": args.device} if args.device else {}),
            }
        )
        model_configs = {
            variant: load_model_config(args.model_configs / f"{variant}.yaml")
            for variant in config.variants
        }
        needed = trainings_needed(config, inputs.plan)
        if needed > config.max_trainings:
            raise ValueError(
                f"El barrido necesita {needed} entrenamientos; presupuesto {config.max_trainings}."
            )
    except (FileNotFoundError, KeyError, ValueError) as error:
        print(f"No se pudo preparar el barrido: {error}", file=sys.stderr)
        return EXIT_INPUT

    output.mkdir(parents=True, exist_ok=True)
    sweep_path = output / "sweep.csv"
    if args.from_sweep:
        rows = read_sweep_rows(sweep_path)
    else:
        rows = _run_and_write(sweep_path, needed, config, inputs, model_configs, base_training)
    try:
        selections = select_lambdas(rows, config)
    except ValueError as error:
        print(f"No se pudo elegir λ: {error}", file=sys.stderr)
        return EXIT_INPUT
    elapsed = time.monotonic() - started

    (output / "selection.json").write_text(
        json.dumps(
            {
                "format_version": SWEEP_FORMAT_VERSION,
                "dataset_id": inputs.dataset_id,
                "criterion": config.criterion,
                "tie_break": config.tie_break,
                "feasibility_constraint": config.feasibility_constraint,
                "test_used": False,
                "selections": {v: s.to_dict() for v, s in selections.items()},
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    report = build_report(
        config=config,
        inputs=inputs,
        rows=rows,
        selections=selections,
        elapsed=elapsed,
        config_path=_relative(config_path),
    )
    (output / "report.md").write_text(report, encoding="utf-8", newline="\n")
    run_meta: dict[str, Any] = {
        "issue": 178,
        "command": "python scripts/sweep_constraint_lambda.py",
        "argv": list(argv) if argv is not None else sys.argv[1:],
        "dataset_id": inputs.dataset_id,
        "config": _relative(config_path),
        "config_sha256": _sha256(config_path),
        "sweep_config": config.model_dump(mode="json"),
        "plan": _relative(inputs.plan_path),
        "plan_canonical_sha256": plan_content_sha256(
            json.loads(inputs.plan_path.read_text(encoding="utf-8"))
        ),
        "cohort": dict(inputs.cohort),
        "training_config": base_training.model_dump(mode="json"),
        "model_configs": {v: c.model_dump(mode="json") for v, c in model_configs.items()},
        "trainings": len(rows),
        "failed": sum(1 for row in rows if row.status != "ok"),
        "test_used": False,
        "git": git_info(REPO_ROOT),
        "environment": environment_info(base_training.device),
        "elapsed_seconds": round(elapsed, 1),
        "reselected": bool(args.from_sweep),
        "files": {"sweep": "sweep.csv", "selection": "selection.json", "report": "report.md"},
    }
    (output / "run.json").write_text(
        json.dumps(run_meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    print(report)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
