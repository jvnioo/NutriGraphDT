"""Estadísticas descriptivas y subgrafo de muestra de los grafos HeteroData (A35-4).

Carga los grafos guardados con `save_graphs` (por ejemplo, con
`generate_synthetic_dataset.py --graphs`), imprime por grafo el conteo de nodos y aristas por
tipo, el grado medio y las componentes conexas, y escribe en `--output`:

- `stats.json`: las mismas estadísticas, una entrada por grafo;
- `sample_NNNN.md`: un subgrafo de muestra por grafo como diagrama Mermaid, numerado en orden
  de `graph_id` (igual que los `.pt`). GitHub y VS Code lo renderizan.

Las convenciones (grado no dirigido, componentes débiles, muestra determinista) están en
`nutrigraphdt.graph.stats`. Requiere el extra `graph`. Las estadísticas son estructurales: no
afirman nada sobre la validez biológica del grafo.

Códigos de salida: 0 si se generó el resumen; 2 si los grafos no se pudieron leer o son
inconsistentes.

Uso:

    python scripts/generate_synthetic_dataset.py --graphs
    python scripts/graph_stats.py

    # Otro directorio de grafos
    python scripts/graph_stats.py --graphs artifacts/synthetic/seed-7/graphs

    # Un solo grafo y una muestra más amplia desde un nodo elegido
    python scripts/graph_stats.py --graph-id synthetic:scenario:basal:0001 \\
        --seed-node taxon:synthetic:taxon:0001 --hops 2 --max-nodes 40
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from collections.abc import Sequence
from pathlib import Path

DEFAULT_GRAPHS = Path("artifacts/synthetic/v1/graphs")
DEFAULT_OUTPUT = Path("artifacts/graph-stats")
EXIT_OK = 0
EXIT_UNREADABLE = 2


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--graphs",
        type=Path,
        default=DEFAULT_GRAPHS,
        help=f"Directorio escrito por save_graphs (por defecto: {DEFAULT_GRAPHS.as_posix()}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Directorio de stats.json y las muestras (por defecto: {DEFAULT_OUTPUT.as_posix()}).",
    )
    parser.add_argument("--graph-id", help="Resume solo este grafo.")
    parser.add_argument(
        "--seed-node",
        help="Nodo inicial de la muestra, como tipo:node_id o tipo:fila "
        "(por defecto, el de mayor grado).",
    )
    parser.add_argument("--hops", type=int, default=1, help="Saltos de la muestra (defecto: 1).")
    parser.add_argument(
        "--max-nodes", type=int, default=25, help="Nodos máximos de la muestra (defecto: 25)."
    )
    args = parser.parse_args(argv)

    try:
        from nutrigraphdt.graph.heterodata import load_graphs
        from nutrigraphdt.graph.stats import (
            compute_stats,
            format_stats,
            resolve_node,
            sample_subgraph,
            to_mermaid,
        )
    except ImportError:
        print(
            "Se requieren PyTorch y PyTorch Geometric (extra `graph`); ver docs/development.md.",
            file=sys.stderr,
        )
        return EXIT_UNREADABLE

    try:
        graphs = load_graphs(args.graphs)
    except FileNotFoundError as error:
        print(f"No se encontraron grafos en {args.graphs}: {error}", file=sys.stderr)
        print(
            "Genéralos con: python scripts/generate_synthetic_dataset.py --graphs", file=sys.stderr
        )
        return EXIT_UNREADABLE
    except (OSError, KeyError, ValueError, RuntimeError, pickle.UnpicklingError) as error:
        print(f"No se pudieron cargar los grafos de {args.graphs}: {error}", file=sys.stderr)
        return EXIT_UNREADABLE

    # Misma numeración que save_graphs: posición en orden de graph_id.
    numbered = {graph_id: number for number, graph_id in enumerate(sorted(graphs), start=1)}
    if args.graph_id is not None:
        if args.graph_id not in graphs:
            print(f"No existe el grafo {args.graph_id!r} en {args.graphs}.", file=sys.stderr)
            return EXIT_UNREADABLE
        numbered = {args.graph_id: numbered[args.graph_id]}

    summaries = []
    samples: dict[str, str] = {}
    try:
        for graph_id, number in numbered.items():
            data = graphs[graph_id]
            stats = compute_stats(data)
            seed = resolve_node(data, args.seed_node) if args.seed_node else None
            subgraph = sample_subgraph(data, seed=seed, hops=args.hops, max_nodes=args.max_nodes)
            summaries.append(stats.to_dict())
            samples[f"sample_{number:04d}.md"] = (
                f"# Subgrafo de muestra de `{graph_id}`\n\n"
                f"{len(subgraph.nodes)} nodos y {len(subgraph.edges)} aristas a {args.hops} "
                f"salto(s) de `{subgraph.seed[0]}` fila {subgraph.seed[1]}. Generado por "
                "`scripts/graph_stats.py`.\n\n"
                f"```mermaid\n{to_mermaid(data, subgraph)}```\n"
            )
            print("\n".join(format_stats(stats)))
    except ValueError as error:
        print(f"No se pudo resumir el grafo: {error}", file=sys.stderr)
        return EXIT_UNREADABLE

    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "stats.json").open("w", encoding="utf-8", newline="\n") as handle:
        json.dump({"graphs": summaries}, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    for name, content in samples.items():
        (args.output / name).write_text(content, encoding="utf-8", newline="\n")
    print(f"resumen: {args.output / 'stats.json'}  muestras: {len(samples)} en {args.output}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
