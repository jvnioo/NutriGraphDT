"""Entrena los baselines trivial y lineales (A40-4) sobre una cohorte sintética.

El generador sintético produce una instancia por semilla, así que la cohorte se arma con
`--n-samples` instancias de semillas consecutivas desde `--first-seed`. Cada instancia es un
animal distinto y el generador no define corrales, de modo que el grupo de la partición y de la
validación cruzada es el propio `sample_id`. La partición train/val/test se crea con
`create_split` (A40-1) usando `--split-seed`.

Los AGCC sintéticos no se derivan de los atributos: estas métricas verifican que el flujo de
entrenamiento y evaluación funciona, no la capacidad predictiva de los modelos.

Escribe en `--output`:

- `report.csv` y `report.md`: métricas de `val` y `test` con el formato común de A40-2;
- `run.json`: configuración, semillas, tamaños de cada subconjunto e hiperparámetros elegidos.

Uso:

    pip install -e ".[dev,baselines]"
    python scripts/run_linear_baselines.py
    python scripts/run_linear_baselines.py --n-samples 100 --output artifacts/baselines/n100
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from nutrigraphdt.data.split import create_split
from nutrigraphdt.data.synthetic import (
    SyntheticDataset,
    SyntheticEdgeConfig,
    SyntheticNodeConfig,
    generate_synthetic_dataset,
)
from nutrigraphdt.models.baselines import LinearBaselineConfig, train_linear_baselines
from nutrigraphdt.models.tabular import build_tabular_dataset

DEFAULT_CONFIG = Path("configs/baselines/linear.json")
DEFAULT_OUTPUT = Path("artifacts/baselines/linear")
COHORT_DATASET_ID = "synthetic_baseline_cohort"


def build_synthetic_cohort(n_samples: int, first_seed: int) -> SyntheticDataset:
    """Une `n_samples` instancias sintéticas de semillas consecutivas en un solo dataset."""
    if n_samples < 1:
        raise ValueError(f"n_samples debe ser >= 1: {n_samples}.")
    parts = [
        generate_synthetic_dataset(
            SyntheticNodeConfig(graph_id=f"synthetic:graph:{seed:04d}", random_seed=seed),
            SyntheticEdgeConfig(random_seed=seed),
        )
        for seed in range(first_seed, first_seed + n_samples)
    ]
    return SyntheticDataset(
        metadata={"dataset_id": COHORT_DATASET_ID},
        instances=[inst for part in parts for inst in part.instances],
        nodes=[node for part in parts for node in part.nodes],
        edges=[edge for part in parts for edge in part.edges],
        outputs=[out for part in parts for out in part.outputs],
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--n-samples", type=int, default=50)
    parser.add_argument("--first-seed", type=int, default=1)
    parser.add_argument("--split-seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    config = LinearBaselineConfig.load(args.config)
    cohort = build_synthetic_cohort(args.n_samples, args.first_seed)
    split = create_split(
        [
            {"sample_id": inst.sample_id, "diet_treatment": inst.diet_treatment}
            for inst in cohort.instances
        ],
        group_key=None,
        stratify_key="diet_treatment",
        seed=args.split_seed,
        dataset_id=COHORT_DATASET_ID,
    )
    dataset = build_tabular_dataset(cohort, split=split)
    groups = {sample_id: sample_id for sample_id in dataset.sample_ids}
    result = train_linear_baselines(dataset, groups, config)

    args.output.mkdir(parents=True, exist_ok=True)
    markdown = result.report.to_markdown()
    (args.output / "report.csv").write_text(result.report.to_csv(), encoding="utf-8")
    (args.output / "report.md").write_text(markdown + "\n", encoding="utf-8")
    run = {
        "dataset_id": COHORT_DATASET_ID,
        "n_samples": args.n_samples,
        "first_seed": args.first_seed,
        "split_seed": args.split_seed,
        "subset_sizes": result.subset_sizes,
        "n_features": len(result.feature_names),
        "config": config.to_dict(),
        "best_params": result.best_params,
    }
    (args.output / "run.json").write_text(
        json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(markdown)
    print(f"\nHiperparámetros elegidos: {json.dumps(result.best_params)}")
    print(f"Resultados en {args.output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
