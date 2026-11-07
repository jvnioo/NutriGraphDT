#!/usr/bin/env python3
"""Comprueba si el bloque `taxon` de la lectura de la GNN puede variar entre animales de D1 (#239).

El encoder de nodos es lineal (`NodeTypeEncoder`), los taxones de D1 no son destino de ninguna
arista y `mean_readout` promedia por tipo. Entonces el bloque `taxon` de la lectura es una función
afín de la media por grafo de `[x ‖ missing_mask]` de los taxones. Si esa media es la misma en
todos los grafos, la GNN no recibe información del microbioma.

Requiere el extra `graph` y los grafos guardados (`scripts/build_graph.py --save-graphs`):

    python docs/research/check_d1_taxon_readout.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch

from nutrigraphdt.graph.heterodata import load_graphs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--graphs", type=Path, default=Path("artifacts/graphs/D1_holofood/graphs"))
    args = parser.parse_args()

    graphs = load_graphs(args.graphs)
    incoming = {
        edge_type
        for data in graphs.values()
        for edge_type in data.edge_types
        if edge_type[2] == "taxon" and data[edge_type].edge_index.numel() > 0
    }
    shapes = {tuple(data["taxon"].x.shape) for data in graphs.values()}
    means = torch.stack([data["taxon"].x.mean(dim=0) for data in graphs.values()])
    sums = torch.stack([data["taxon"].x.sum(dim=0) for data in graphs.values()])
    masks = torch.stack(
        [data["taxon"].missing_mask.float().mean(dim=0) for data in graphs.values()]
    )

    print(f"Grafos: {len(graphs)}. Forma de x de taxon: {sorted(shapes)}.")
    print(f"Aristas que llegan a taxon: {sorted(incoming) or 'ninguna'}.")
    print(
        f"Media de x por grafo: mín {means.min():.10f}, máx {means.max():.10f}, "
        f"desviación {means.std():.2e}."
    )
    print(f"Suma de x por grafo: mín {sums.min():.8f}, máx {sums.max():.8f}.")
    print(f"Fracción de ausentes por grafo: mín {masks.min():.4f}, máx {masks.max():.4f}.")
    constant = means.std() < 1e-6 and masks.std() < 1e-6 and not incoming
    print(
        "El bloque taxon de la lectura es constante entre animales."
        if constant
        else "El bloque taxon de la lectura puede variar entre animales."
    )


if __name__ == "__main__":
    main()
