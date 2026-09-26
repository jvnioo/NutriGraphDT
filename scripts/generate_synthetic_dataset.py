"""Genera y exporta el dataset sintético de NutriGraphDT (DS-05).

Uso:

    # Escenarios basal e intervenido de DS-04 (opción por defecto)
    python scripts/generate_synthetic_dataset.py

    # Una sola instancia con una semilla propia
    python scripts/generate_synthetic_dataset.py --seed 7 --output artifacts/synthetic/seed-7

La salida por defecto queda en `artifacts/`, que Git ignora: los datasets generados son
artefactos locales y no se suben al repositorio.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nutrigraphdt.data.synthetic import (
    SyntheticEdgeConfig,
    SyntheticNodeConfig,
    export_dataset,
    generate_scenario_dataset,
    generate_synthetic_dataset,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera el dataset sintético de NutriGraphDT.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/synthetic/v1"),
        help="Directorio de salida (por defecto: artifacts/synthetic/v1).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Genera una sola instancia con esta semilla en lugar de los escenarios de DS-04.",
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Reemplaza un dataset ya exportado."
    )
    args = parser.parse_args()

    if args.seed is None:
        dataset = generate_scenario_dataset()
    else:
        dataset = generate_synthetic_dataset(
            SyntheticNodeConfig(random_seed=args.seed),
            SyntheticEdgeConfig(random_seed=args.seed),
        )
    try:
        root = export_dataset(dataset, args.output, overwrite=args.overwrite)
    except FileExistsError as error:
        raise SystemExit(
            f"Ya existe un dataset en {args.output}. Agrega --overwrite para reemplazarlo."
        ) from error
    print(f"Dataset sintético exportado en {root}")
    print(
        f"  instancias: {len(dataset.instances)}  nodos: {len(dataset.nodes)}  "
        f"aristas: {len(dataset.edges)}"
    )


if __name__ == "__main__":
    main()
