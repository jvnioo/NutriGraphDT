"""Búsqueda acotada de hiperparámetros y variabilidad por semilla (A45-5, #105).

Para una variante y un dataset:

1. **Grilla** sobre `hidden_channels` × `num_layers` (por defecto 32/64/128 × 1/2/3) con una
   semilla fija; elige la combinación de menor RMSE promedio de `val`. `test` no interviene.
2. **Semillas:** repite con 5 semillas la configuración inicial de las tres variantes
   (`configs/models/*.yaml`) y la elegida, y resume media ± desviación estándar en `val` y
   `test`.

Cada corrida se entrena con `run_training` (A44-6), igual que `scripts/train_gnn.py`, y se
registra en `--runs-dir` (ignorado por Git). Escribe en `--output`:

- `grid.csv`: la grilla, solo con métricas de `val`;
- `selection.json`: criterio, candidatas con su RMSE de `val` y la elegida (`test_used: false`);
- `seeds.csv` y `summary.csv`: cada corrida de la fase de semillas y su resumen;
- `report.md`: tabla media ± desviación estándar;
- `runs/<subcarpeta>/<run_id>.json`: copia del `run.json` de cada corrida.

La configuración elegida queda en `--selected-config` (por defecto
`configs/models/tuned/<dataset>_<variante>.yaml`).

Requiere el extra `graph`; `--dataset synthetic` requiere además el extra `baselines`
(scikit-learn), con el que se arma la cohorte sintética. Uso:

    python scripts/tune_gnn.py --dataset synthetic --model hetero_gat
    python scripts/tune_gnn.py --dataset d1 --model homo_sage

Código de salida: `0` si terminó; `2` si faltan datos o la configuración es inválida.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from nutrigraphdt.data.split import DatasetSplit, create_split, get_split
from nutrigraphdt.graph.heterodata import build_synthetic_graphs, load_graphs
from nutrigraphdt.models.gnn import MODEL_VARIANTS, ModelConfigError, load_model_config
from nutrigraphdt.models.gnn.factory import GNNModelConfig
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
from nutrigraphdt.models.training.tracking import RUN_FILE
from nutrigraphdt.models.training.tuning import (
    DEFAULT_SEEDS,
    GRID_HIDDEN_CHANNELS,
    GRID_NUM_LAYERS,
    RunOutcome,
    TuningResult,
    grid_to_csv,
    outcome_from_report,
    run_tuning,
    seed_runs_to_csv,
    selection_to_dict,
    summary_to_csv,
    summary_to_markdown,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASETS = ("synthetic", "d1")
DEFAULT_CONFIG = REPO_ROOT / "configs" / "training" / "default.json"
DEFAULT_MODEL_CONFIGS = REPO_ROOT / "configs" / "models"
DEFAULT_D1_GRAPHS = REPO_ROOT / "artifacts" / "graphs" / "D1_holofood"
DEFAULT_RUNS_DIR = REPO_ROOT / "runs" / "tuning"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "reports" / "gnn" / "tuning"
DEFAULT_SELECTED_DIR = REPO_ROOT / "configs" / "models" / "tuned"
EXIT_OK = 0
EXIT_INPUT = 2


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    args = _parser().parse_args(argv)
    if args.seed is not None:
        print("Use --seeds (y --grid-seed) en lugar de --seed.", file=sys.stderr)
        return EXIT_INPUT
    output = args.output or DEFAULT_OUTPUT_DIR / args.dataset
    selected_path = args.selected_config or (
        DEFAULT_SELECTED_DIR / f"{args.dataset}_{args.model}.yaml"
    )
    runs_dir = Path(args.runs_dir) / args.dataset
    try:
        variants = MODEL_VARIANTS if args.all_variants else (args.model,)
        initial = {
            variant: load_model_config(Path(args.model_configs) / f"{variant}.yaml")
            for variant in variants
        }
        overrides = overrides_from_args(args)
        if args.dataset == "synthetic":
            overrides.setdefault("dataset_id", _synthetic_cohort_id())
        config = apply_overrides(load_training_config(args.config), overrides)
        prepared, split, split_file, source = _load_dataset(args, config)
    except (
        FileNotFoundError,
        ImportError,
        ModelConfigError,
        TrainingConfigError,
        ValueError,
    ) as error:
        print(f"No se pudo preparar la búsqueda: {error}", file=sys.stderr)
        return EXIT_INPUT

    run_files: dict[str, Path] = {}

    def train(model_config: GNNModelConfig, seed: int) -> RunOutcome:
        variant = model_config.variant
        hidden, layers = model_config.hidden_channels, model_config.num_layers
        folder = runs_dir / f"{variant}_h{hidden}_l{layers}"
        run = run_training(
            prepared,
            model_config,
            apply_overrides(config, {"seed": seed}),
            split,
            split_file=split_file,
            runs_dir=folder,
            repo_root=REPO_ROOT,
            source=source,
        )
        # El run_id de A44-5 lleva hora, variante y semilla; con la subcarpeta queda único.
        run_id = f"{folder.name}/{run.run_dir.name}"
        outcome = outcome_from_report(
            run.report, model_config=model_config, seed=seed, run_id=run_id
        )
        run_files[outcome.run_id] = run.run_dir / RUN_FILE
        print(
            f"{variant} h={hidden} capas={layers} semilla={seed}: "
            f"RMSE val {outcome.value('val', 'rmse'):.4f} ({run.result.epochs_run} épocas)"
        )
        return outcome

    try:
        result = run_tuning(
            initial,
            args.model,
            train,
            hidden_channels=args.hidden,
            num_layers=args.layers,
            seeds=args.seeds,
            grid_seed=args.grid_seed,
        )
    except (ModelConfigError, ValueError) as error:
        print(f"No se pudo completar la búsqueda: {error}", file=sys.stderr)
        return EXIT_INPUT

    _write_outputs(result, Path(output), run_files, args.dataset)
    _write_selected_config(result, Path(selected_path), args.dataset)
    chosen = result.selected
    print(
        f"Elegida para {args.model} en {args.dataset}: hidden_channels={chosen.hidden_channels}, "
        f"num_layers={chosen.num_layers} (RMSE val {chosen.value('val', 'rmse'):.4f})"
    )
    print(summary_to_markdown(result.summary))
    print(f"Reporte: {_display(Path(output))}; configuración: {_display(Path(selected_path))}")
    return EXIT_OK


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", choices=MODEL_VARIANTS, required=True)
    parser.add_argument("--dataset", choices=DATASETS, required=True)
    parser.add_argument("--hidden", type=int, nargs="+", default=list(GRID_HIDDEN_CHANNELS))
    parser.add_argument("--layers", type=int, nargs="+", default=list(GRID_NUM_LAYERS))
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument(
        "--grid-seed", type=int, default=None, help="Semilla de la grilla; por defecto, la 1.ª."
    )
    parser.add_argument(
        "--only-model",
        dest="all_variants",
        action="store_false",
        help="Repetir con semillas solo la variante de --model (por defecto, las tres).",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--model-configs", type=Path, default=DEFAULT_MODEL_CONFIGS)
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--selected-config", type=Path, default=None)
    parser.add_argument("--graphs-dir", type=Path, default=DEFAULT_D1_GRAPHS)
    parser.add_argument("--n-samples", type=int, default=50, help="Solo synthetic.")
    parser.add_argument("--first-seed", type=int, default=1, help="Solo synthetic.")
    parser.add_argument("--split-seed", type=int, default=42, help="Solo synthetic.")
    add_override_arguments(parser)
    return parser


def _synthetic_cohort_id() -> str:
    # La cohorte sintética se arma con el módulo de baselines, que requiere scikit-learn. Se
    # importa solo para `--dataset synthetic`, de modo que `d1` funciona sin ese extra.
    from nutrigraphdt.models.baselines import SYNTHETIC_COHORT_ID

    return SYNTHETIC_COHORT_ID


def _load_dataset(
    args: argparse.Namespace, config: TrainingConfig
) -> tuple[PreparedDataLoaders, DatasetSplit, str | None, dict[str, Any]]:
    """La misma carga que `scripts/train_gnn.py` (A44-6), para comparar con A45-3 y A45-4."""
    if args.dataset == "synthetic":
        from nutrigraphdt.models.baselines import SYNTHETIC_COHORT_ID, build_synthetic_cohort

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


def _write_outputs(
    result: TuningResult, output: Path, run_files: dict[str, Path], dataset: str
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "grid.csv").write_text(grid_to_csv(result.grid), encoding="utf-8", newline="")
    (output / "seeds.csv").write_text(
        seed_runs_to_csv(result.seed_runs), encoding="utf-8", newline=""
    )
    (output / "summary.csv").write_text(
        summary_to_csv(result.summary), encoding="utf-8", newline=""
    )
    selection = selection_to_dict(result)
    selection["dataset"] = dataset
    (output / "selection.json").write_text(
        json.dumps(selection, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    copies = output / "runs"
    if copies.exists():
        shutil.rmtree(copies)
    for run_id, path in sorted(run_files.items()):
        target = copies / f"{run_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    (output / "report.md").write_text(_report(result, dataset), encoding="utf-8")


def _report(result: TuningResult, dataset: str) -> str:
    chosen = result.selected
    grid_rows = "\n".join(
        f"| {o.hidden_channels} | {o.num_layers} | {o.value('val', 'rmse'):.4f} |"
        + (" **elegida** |" if o is chosen else " |")
        for o in result.grid
    )
    return (
        f"# Búsqueda de hiperparámetros y variabilidad por semilla: {dataset} (A45-5)\n\n"
        f"- **Variante de la grilla:** `{result.variant}`.\n"
        f"- **Semilla de la grilla:** {result.grid_seed}.\n"
        "- **Criterio:** menor RMSE promedio de `val`; empate, modelo más chico. `test` no "
        "interviene: `grid.csv` y `selection.json` solo tienen métricas de `val`.\n\n"
        "## Grilla (RMSE promedio de val)\n\n"
        "| hidden_channels | num_layers | RMSE val | |\n| ---: | ---: | ---: | :--- |\n"
        f"{grid_rows}\n\n"
        "## Media ± desviación estándar por semilla (RMSE promedio)\n\n"
        f"{summary_to_markdown(result.summary)}\n\n"
        "MAE y R² están en `summary.csv`; cada corrida, en `seeds.csv` y `runs/`.\n"
    )


def _write_selected_config(result: TuningResult, path: Path, dataset: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"# Configuración elegida por A45-5 (#105) para {dataset}: menor RMSE promedio de val en\n"
        f"# la grilla de reports/gnn/tuning/{dataset}/ (test no interviene). Provisional: se\n"
        "# revisa en la reunión de ajuste posterior al avance 2 (act. 49).\n"
    )
    body = yaml.safe_dump(result.selected.model_config.model_dump(mode="json"), sort_keys=False)
    path.write_text(header + body, encoding="utf-8")


def _display(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
