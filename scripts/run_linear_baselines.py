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

from nutrigraphdt.models.baselines import (
    SYNTHETIC_COHORT_ID,
    LinearBaselineConfig,
    build_synthetic_baseline_dataset,
    train_linear_baselines,
)

DEFAULT_CONFIG = Path("configs/baselines/linear.json")
DEFAULT_OUTPUT = Path("artifacts/baselines/linear")


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
    dataset, groups = build_synthetic_baseline_dataset(
        args.n_samples, args.first_seed, args.split_seed
    )
    result = train_linear_baselines(dataset, groups, config)

    args.output.mkdir(parents=True, exist_ok=True)
    markdown = result.report.to_markdown()
    (args.output / "report.csv").write_text(result.report.to_csv(), encoding="utf-8")
    (args.output / "report.md").write_text(markdown + "\n", encoding="utf-8")
    run = {
        "dataset_id": SYNTHETIC_COHORT_ID,
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
