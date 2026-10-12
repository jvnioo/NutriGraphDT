"""Entrena los baselines de árboles (A40-5) sobre una cohorte sintética.

Usa la misma cohorte y partición que `run_linear_baselines.py`: `--n-samples` instancias de
semillas consecutivas desde `--first-seed`, partición de `create_split` (A40-1) con
`--split-seed`, y el `sample_id` como grupo de la validación cruzada (el generador no define
corrales). Así los resultados de ambos scripts son comparables con los mismos argumentos.

Los AGCC sintéticos no se derivan de los atributos: estas métricas e importancias verifican que
el flujo funciona, no la capacidad predictiva de los modelos ni la relevancia de los atributos.

Escribe en `--output`:

- `report.csv` y `report.md`: métricas de `val` y `test` con el formato común de A40-2;
- `importances.csv`: importancia por permutación sobre `val` de cada atributo y modelo,
  ordenada de mayor a menor dentro de cada modelo;
- `run.json`: configuración, semillas, tamaños de cada subconjunto e hiperparámetros elegidos.

Uso:

    pip install -e ".[dev,baselines]"
    python scripts/run_tree_baselines.py
    python scripts/run_tree_baselines.py --n-samples 100 --output artifacts/baselines/trees-n100
"""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Sequence
from pathlib import Path

from nutrigraphdt.models.baselines import (
    IMPORTANCE_SPLIT,
    SYNTHETIC_COHORT_ID,
    TreeBaselineConfig,
    build_synthetic_baseline_dataset,
    train_tree_baselines,
)

DEFAULT_CONFIG = Path("configs/baselines/trees.json")
DEFAULT_OUTPUT = Path("artifacts/baselines/trees")
TOP_FEATURES = 5


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--n-samples", type=int, default=50)
    parser.add_argument("--first-seed", type=int, default=1)
    parser.add_argument("--split-seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    config = TreeBaselineConfig.load(args.config)
    dataset, groups = build_synthetic_baseline_dataset(
        args.n_samples, args.first_seed, args.split_seed
    )
    result = train_tree_baselines(dataset, groups, config)

    args.output.mkdir(parents=True, exist_ok=True)
    markdown = result.report.to_markdown()
    (args.output / "report.csv").write_text(result.report.to_csv(), encoding="utf-8")
    (args.output / "report.md").write_text(markdown + "\n", encoding="utf-8")

    ranked = {
        model: sorted(items, key=lambda item: item.importance_mean, reverse=True)
        for model, items in result.feature_importances.items()
    }
    with (args.output / "importances.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["model", "split", "feature", "importance_mean", "importance_std"])
        for model, items in ranked.items():
            for item in items:
                writer.writerow(
                    [
                        model,
                        IMPORTANCE_SPLIT,
                        item.feature,
                        item.importance_mean,
                        item.importance_std,
                    ]
                )

    run = {
        "dataset_id": SYNTHETIC_COHORT_ID,
        "n_samples": args.n_samples,
        "first_seed": args.first_seed,
        "split_seed": args.split_seed,
        "subset_sizes": result.subset_sizes,
        "n_features": len(result.feature_names),
        "importance_split": IMPORTANCE_SPLIT,
        "config": config.to_dict(),
        "best_params": result.best_params,
    }
    (args.output / "run.json").write_text(
        json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(markdown)
    print(f"\nHiperparámetros elegidos: {json.dumps(result.best_params)}")
    for model, items in ranked.items():
        top = ", ".join(f"{i.feature} ({i.importance_mean:.4f})" for i in items[:TOP_FEATURES])
        print(f"Importancia en {IMPORTANCE_SPLIT}, {model}: {top}")
    print(f"Resultados en {args.output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
