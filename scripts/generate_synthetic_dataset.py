"""Genera y exporta el dataset sintético de NutriGraphDT (DS-05) y, opcionalmente, sus grafos.

Uso:

    # Escenarios basal e intervenido de DS-04 (opción por defecto)
    python scripts/generate_synthetic_dataset.py

    # Una sola instancia con una semilla propia
    python scripts/generate_synthetic_dataset.py --seed 7 --output artifacts/synthetic/seed-7

    # Además, el prototipo HeteroData de cada instancia (A35-1; requiere el extra `graph`)
    python scripts/generate_synthetic_dataset.py --graphs

Con `--graphs`, los grafos se validan con todas las reglas de integridad antes de guardarse en
`<salida>/graphs/`, y el esquema de features y target se declara en `metadata.json`. Solo se
guardan los grafos entregables; si alguno se retiene, el script termina con código 1.

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

GRAPHS_DIR = "graphs"


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
        "--graphs",
        action="store_true",
        help="Construye, valida y guarda el prototipo HeteroData de cada instancia (A35-1).",
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

    build = None
    if args.graphs:
        try:
            from nutrigraphdt.graph.heterodata import build_synthetic_graphs
        except ImportError as error:
            raise SystemExit(
                "--graphs requiere PyTorch y PyTorch Geometric (extra `graph`); ver "
                "docs/process/development.md."
            ) from error
        build = build_synthetic_graphs(dataset)
        dataset = build.dataset

    try:
        root = export_dataset(dataset, args.output, overwrite=args.overwrite)
    except FileExistsError as error:
        raise SystemExit(
            f"Ya existe un dataset en {args.output}. Agrega --overwrite para reemplazarlo."
        ) from error
    print(f"Dataset sintético exportado en {root}")
    print(
        f"  instancias: {len(dataset.instances)}  nodos: {len(dataset.nodes)}  "
        f"aristas: {len(dataset.edges)}  salidas: {len(dataset.outputs)}"
    )

    if build is None:
        return
    from nutrigraphdt.graph.heterodata import save_graphs

    graphs_dir = save_graphs(build.graphs, root / GRAPHS_DIR, overwrite=args.overwrite)
    report = build.report
    print(f"Grafos HeteroData guardados en {graphs_dir}: {len(build.graphs)}")
    summary = report.to_dict()["summary"]
    print(
        f"  validación: {'valid' if report.is_valid else 'invalid'}  ERROR={summary['ERROR']}  "
        f"ADVERTENCIA={summary['ADVERTENCIA']}  INFO={summary['INFO']}"
    )
    if report.blocked_graph_ids:
        raise SystemExit(f"Grafos retenidos por errores: {', '.join(report.blocked_graph_ids)}")


if __name__ == "__main__":
    main()
