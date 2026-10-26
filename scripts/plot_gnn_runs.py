"""Curvas de aprendizaje y predicho vs. medido de corridas GNN registradas (A45-7).

Lee `run.json`, `history.csv`, `metrics.csv` y `predictions.csv` de una corrida por variante,
verifica que sus métricas coincidan con `reports/gnn/<dataset>/report.csv` y escribe en
`reports/gnn/figures/`:

- `learning_curves_<dataset>.png`: pérdida de `train` y `val` (escala estandarizada) y RMSE de
  `val` por época (unidades de la fuente), con la mejor época marcada;
- `predictions_<dataset>.png`: predicho vs. medido por AGCC en `test`;
- `diagnostics_<dataset>.md` y `.json`: procedencia de las corridas y cifras de diagnóstico.

No reentrena ni recarga checkpoints. Requiere matplotlib (extra `plots`).

Uso:

    python scripts/plot_gnn_runs.py runs/<homo_sage> runs/<hetero_sage> runs/<hetero_gat>

Termina con código 2 si una corrida no se puede leer, si las corridas son de datasets distintos
o si sus métricas no coinciden con el reporte (salvo con `--no-report-check`).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from nutrigraphdt.models.diagnostics import (
    DATASET_LABELS,
    DIAGNOSIS_SPLIT,
    TARGET_LABELS,
    TARGET_UNITS,
    RunData,
    RunDataError,
    diagnose,
    diagnoses_to_markdown,
    load_run,
    order_runs,
    report_mismatches,
    unit_label,
)
from nutrigraphdt.models.metrics import DEFAULT_SCFA_TARGETS

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "gnn" / "figures"
COMMAND = "python scripts/plot_gnn_runs.py <corridas>"
DPI = 120


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "runs", nargs="+", type=Path, help="Carpetas de corrida (una por variante)."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Carpeta de salida.")
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="report.csv con el que se verifican las métricas "
        "(por defecto, reports/gnn/<dataset>/report.csv).",
    )
    parser.add_argument(
        "--no-report-check",
        action="store_true",
        help="No verificar las métricas contra el reporte (por ejemplo, corridas nuevas).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        runs = order_runs([load_run(path) for path in args.runs])
        dataset = runs[0].dataset
        if not args.no_report_check:
            report = args.report or REPO_ROOT / "reports" / "gnn" / dataset / "report.csv"
            problems = [p for run in runs for p in report_mismatches(run, report)]
            if problems:
                raise RunDataError(
                    "Las corridas no coinciden con el reporte "
                    f"{report}:\n  " + "\n  ".join(problems)
                )
        diagnoses = [diagnose(run) for run in runs]
    except RunDataError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print(
            'Error: se requiere matplotlib; instale el extra con `pip install -e ".[plots]"`.',
            file=sys.stderr,
        )
        return 2

    output: Path = args.output
    output.mkdir(parents=True, exist_ok=True)
    curves = f"learning_curves_{dataset}.png"
    predictions = f"predictions_{dataset}.png"
    _save(plot_learning_curves(plt, runs), output / curves, plt)
    _save(plot_predictions(plt, runs), output / predictions, plt)

    (output / f"diagnostics_{dataset}.md").write_text(
        diagnoses_to_markdown(diagnoses, runs, [curves, predictions], COMMAND), encoding="utf-8"
    )
    (output / f"diagnostics_{dataset}.json").write_text(
        json.dumps(
            {
                "dataset": dataset,
                "split": DIAGNOSIS_SPLIT,
                "figures": [curves, predictions],
                "runs": [_provenance(run) for run in runs],
                "diagnoses": [d.to_dict() for d in diagnoses],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    for d in diagnoses:
        print(
            f"{d.variant}: mejor época {d.best_epoch}/{d.epochs_run}, "
            f"RMSE val {d.val_rmse_first:.2f} → {d.val_rmse_best:.2f}, RMSE test {d.test_rmse:.2f}"
        )
    print(f"Escrito en {output}: {curves}, {predictions}, diagnostics_{dataset}.md/.json")
    return 0


def plot_learning_curves(plt: Any, runs: Sequence[RunData]) -> Any:
    """Una fila por variante: pérdidas (izquierda) y RMSE de `val` por época (derecha)."""
    dataset = runs[0].dataset
    unit = TARGET_UNITS.get(dataset, "unidades de la fuente")
    fig, axes = plt.subplots(len(runs), 2, figsize=(11, 3.2 * len(runs)), squeeze=False)
    for row, run in zip(axes, runs, strict=True):
        epochs = [r.epoch for r in run.history]
        loss_ax, rmse_ax = row
        loss_ax.plot(epochs, [r.train_loss for r in run.history], label="train")
        loss_ax.plot(epochs, [r.val_loss for r in run.history], label="val")
        loss_ax.set_ylabel("MSE (escala estandarizada)")
        loss_ax.set_title(f"{run.variant}: pérdida")
        for target in DEFAULT_SCFA_TARGETS:
            rmse_ax.plot(
                epochs,
                [r.val_rmse[target] for r in run.history],
                linewidth=0.9,
                alpha=0.6,
                label=TARGET_LABELS.get(target, target),
            )
        rmse_ax.plot(
            epochs,
            [r.val_rmse["average"] for r in run.history],
            color="black",
            linewidth=1.8,
            label="Promedio",
        )
        rmse_ax.set_ylabel(f"RMSE val ({unit})")
        rmse_ax.set_title(f"{run.variant}: RMSE de val")
        for ax in row:
            ax.axvline(run.best_epoch, color="grey", linestyle="--", linewidth=1)
            ax.set_xlabel("Época")
            ax.grid(alpha=0.3)
        loss_ax.legend(title=f"mejor época {run.best_epoch}", fontsize=8)
        rmse_ax.legend(fontsize=8)
    label = DATASET_LABELS.get(dataset, dataset)
    fig.suptitle(
        f"{label}: curvas de aprendizaje (línea discontinua: mejor época según val)\n"
        f"AGCC en {unit_label(dataset)}"
    )
    fig.tight_layout()
    return fig


def plot_predictions(plt: Any, runs: Sequence[RunData]) -> Any:
    """Una fila por variante y una columna por AGCC: predicho vs. medido en `test`."""
    dataset = runs[0].dataset
    unit = TARGET_UNITS.get(dataset, "unidades de la fuente")
    targets = DEFAULT_SCFA_TARGETS
    fig, axes = plt.subplots(
        len(runs), len(targets), figsize=(4 * len(targets), 3.8 * len(runs)), squeeze=False
    )
    for row, run in zip(axes, runs, strict=True):
        points = run.subset(DIAGNOSIS_SPLIT)
        for ax, target in zip(row, targets, strict=True):
            measured = [p.measured[target] for p in points]
            predicted = [p.predicted[target] for p in points]
            low = min(0.0, *measured, *predicted)
            high = max(*measured, *predicted) * 1.05
            ax.plot([low, high], [low, high], color="grey", linestyle="--", linewidth=1)
            ax.scatter(measured, predicted, s=18, alpha=0.8)
            ax.set_xlim(low, high)
            ax.set_ylim(low, high)
            ax.set_aspect("equal")
            rmse = run.metric(DIAGNOSIS_SPLIT, "rmse", target)
            r2 = run.metric(DIAGNOSIS_SPLIT, "r2", target)
            ax.set_title(
                f"{run.variant} — {TARGET_LABELS.get(target, target)}\n"
                f"RMSE {rmse:.2f}, R² {r2:.2f}, n = {len(points)}",
                fontsize=9,
            )
            ax.set_xlabel(f"Medido ({unit})", fontsize=8)
            ax.set_ylabel(f"Predicho ({unit})", fontsize=8)
            ax.grid(alpha=0.3)
    label = DATASET_LABELS.get(dataset, dataset)
    fig.suptitle(
        f"{label}: predicho vs. medido en {DIAGNOSIS_SPLIT} (línea: y = x)\n"
        f"AGCC en {unit_label(dataset)}"
    )
    fig.tight_layout()
    return fig


def _save(fig: Any, path: Path, plt: Any) -> None:
    # Sin fecha ni versión en los metadatos, para que la misma entrada dé el mismo PNG.
    fig.savefig(path, dpi=DPI, metadata={"Software": None})
    plt.close(fig)


def _provenance(run: RunData) -> dict[str, Any]:
    git = run.info.get("git") or {}
    split = run.info.get("split") or {}
    return {
        "variant": run.variant,
        "run_id": run.run_id,
        "seed": run.info.get("seed"),
        "model_config": run.info.get("model_config"),
        "best_epoch": run.best_epoch,
        "git": {"commit": git.get("commit"), "dirty": git.get("dirty")},
        "split": {k: split.get(k) for k in ("file", "version", "sha256", "counts")},
    }


if __name__ == "__main__":
    raise SystemExit(main())
