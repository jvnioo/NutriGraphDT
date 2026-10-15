"""Entrena una variante GNN de principio a fin y registra la corrida (A44-6, #100).

Prepara los grafos y la partición (A44-1), ajusta el escalado con `train` (A44-2), entrena con
detención temprana sobre `val` (A44-3) con la configuración versionada (A44-4) y deja la corrida
en `runs/<run_id>/` (A44-5). El modelo se instancia con `build_model` (A41-8).

- `--dataset synthetic`: la misma cohorte y partición que `scripts/compare_baselines.py`
  (`build_synthetic_cohort(50, 1)`, `create_split` con semilla 42), convertida con
  `build_synthetic_graphs`. La partición se crea en memoria: `split_file` de la configuración
  no se usa y `run.json` guarda el hash de la partición.
- `--dataset d1`: los grafos guardados por `scripts/build_graph.py --save-graphs`, filtrados
  por los entregables de su `report.json`, y la partición `split_file` de la configuración.

Requiere el extra `graph`. Uso:

    python scripts/train_gnn.py --model homo_sage --dataset synthetic
    python scripts/train_gnn.py --model hetero_gat --dataset d1 --seed 7
    python scripts/train_gnn.py --model hetero_sage --dataset synthetic --max-epochs 2

Código de salida: `0` si la corrida quedó registrada; `2` si faltan datos o la configuración es
inválida.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from nutrigraphdt.data.split import DatasetSplit, create_split, get_split
from nutrigraphdt.graph.heterodata import build_synthetic_graphs, load_graphs
from nutrigraphdt.models.baselines import SYNTHETIC_COHORT_ID, build_synthetic_cohort
from nutrigraphdt.models.gnn import MODEL_VARIANTS, ModelConfigError, load_model_config
from nutrigraphdt.models.training import (
    PreparedDataLoaders,
    TrainingConfig,
    TrainingConfigError,
    add_override_arguments,
    apply_overrides,
    load_training_config,
    overrides_from_args,
    prepare_training_graphs,
)
from nutrigraphdt.models.training.pipeline import run_training

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASETS = ("synthetic", "d1")
DEFAULT_CONFIG = REPO_ROOT / "configs" / "training" / "default.json"
DEFAULT_MODEL_CONFIGS = REPO_ROOT / "configs" / "models"
DEFAULT_D1_GRAPHS = REPO_ROOT / "artifacts" / "graphs" / "D1_holofood"
DEFAULT_RUNS_DIR = REPO_ROOT / "runs"
EXIT_OK = 0
EXIT_INPUT = 2


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    args = _parser().parse_args(argv)
    try:
        model_config = load_model_config(
            args.model_config or DEFAULT_MODEL_CONFIGS / f"{args.model}.yaml"
        )
        if model_config.variant != args.model:
            raise ModelConfigError(
                f"--model {args.model} no coincide con variant: {model_config.variant} "
                "en la configuración del modelo."
            )
        overrides = overrides_from_args(args)
        if args.dataset == "synthetic":
            overrides.setdefault("dataset_id", SYNTHETIC_COHORT_ID)
        config = apply_overrides(load_training_config(args.config), overrides)
        prepared, split, split_file, source = _load_dataset(args, config)
    except (FileNotFoundError, ModelConfigError, TrainingConfigError, ValueError) as error:
        print(f"No se pudo preparar el entrenamiento: {error}", file=sys.stderr)
        return EXIT_INPUT

    for subset, summary in prepared.summary.items():
        print(
            f"{subset}: {summary.received} recibidos, {summary.deliverable} entregables, "
            f"{summary.with_any_scfa} con algún AGCC, {summary.with_all_scfa} con los tres"
        )
    run = run_training(
        prepared,
        model_config,
        config,
        split,
        split_file=split_file,
        runs_dir=args.runs_dir,
        repo_root=REPO_ROOT,
        source=source,
    )
    result = run.result
    stop = "detención temprana" if result.stopped_early else "máximo de épocas"
    print(
        f"{args.model}: {result.epochs_run} épocas ({stop}); mejor época {result.best_epoch}, "
        f"RMSE promedio de val {result.best_val_rmse:.4f}"
    )
    print(run.report.to_markdown())
    print(f"Corrida: {_display(run.run_dir)}")
    return EXIT_OK


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", choices=MODEL_VARIANTS, required=True)
    parser.add_argument("--dataset", choices=DATASETS, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--model-config",
        type=Path,
        default=None,
        help="YAML del modelo; por defecto configs/models/<model>.yaml.",
    )
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    parser.add_argument(
        "--graphs-dir",
        type=Path,
        default=DEFAULT_D1_GRAPHS,
        help="Salida de scripts/build_graph.py --save-graphs (solo d1).",
    )
    parser.add_argument("--n-samples", type=int, default=50, help="Solo synthetic.")
    parser.add_argument("--first-seed", type=int, default=1, help="Solo synthetic.")
    parser.add_argument("--split-seed", type=int, default=42, help="Solo synthetic.")
    add_override_arguments(parser)
    return parser


def _load_dataset(
    args: argparse.Namespace, config: TrainingConfig
) -> tuple[PreparedDataLoaders, DatasetSplit, str | None, dict[str, Any]]:
    if args.dataset == "synthetic":
        cohort = build_synthetic_cohort(args.n_samples, args.first_seed)
        split = create_split(
            [
                {"sample_id": inst.sample_id, "diet_treatment": inst.diet_treatment}
                for inst in cohort.instances
            ],
            group_key=None,
            stratify_key="diet_treatment",
            seed=args.split_seed,
            dataset_id=SYNTHETIC_COHORT_ID,
        )
        built = build_synthetic_graphs(cohort)
        prepared = prepare_training_graphs(
            built.dataset, built.graphs, split, batch_size=config.batch_size, seed=config.seed
        )
        source = {
            "dataset": "synthetic",
            "n_samples": args.n_samples,
            "first_seed": args.first_seed,
            "split_seed": args.split_seed,
        }
        return prepared, split, None, source

    graphs_dir = Path(args.graphs_dir)
    report = json.loads((graphs_dir / "report.json").read_text(encoding="utf-8"))
    status = report["validation"]["graphs"]
    graphs = {
        graph_id: graph
        for graph_id, graph in load_graphs(graphs_dir / "graphs").items()
        if status.get(graph_id, {}).get("deliverable", False)
    }
    split = get_split(split_file=config.split_file)
    prepared = prepare_training_graphs(
        None, graphs, split, validated=True, batch_size=config.batch_size, seed=config.seed
    )
    source = {
        "dataset": "d1",
        "graphs": _display(graphs_dir),
        "graphs_saved": len(status),
        "graphs_deliverable": len(graphs),
    }
    return prepared, split, config.split_file, source


def _display(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


if __name__ == "__main__":
    raise SystemExit(main())
