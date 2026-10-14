"""Prueba de cordura de las GNN: sobreajuste a un lote sintético pequeño (A41-7).

Entrena cada variante (`homo_sage`, `hetero_sage`, `hetero_gat`) sobre el mismo lote de
`--n-graphs` grafos sintéticos durante `--epochs` pasos de Adam y comprueba que la pérdida de
entrenamiento baja de `--threshold`. Usa los hiperparámetros iniciales del §6 del diseño
(`ModelConfig()`, `lr = 1e-3`), salvo `dropout = 0`, para que la pérdida refleje solo la
capacidad de ajuste. La lógica está en `nutrigraphdt.models.gnn.sanity`.

Escribe en `--output`:

- `losses.csv`: pérdida por época y variante;
- `curves.md`: una curva por variante (`log10` de la pérdida) en Mermaid, para pegar en el Issue;
- `summary.json`: configuración, pérdida inicial y final, y si cada variante sobreajustó.

Requiere el extra `graph`. Código de salida 0 si las tres variantes sobreajustan; 1 si alguna no.

Uso:

    python scripts/overfit_gnn.py
    python scripts/overfit_gnn.py --n-graphs 16 --epochs 500 --output artifacts/gnn-overfit/n16
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections.abc import Callable, Sequence
from pathlib import Path

import torch

from nutrigraphdt.models.gnn import (
    GraphMetadata,
    HeteroGAT,
    HeteroSAGE,
    HomoSAGE,
    ModelConfig,
    SCFAGraphModel,
    initialize_lazy_parameters,
)
from nutrigraphdt.models.gnn.sanity import overfit_losses, prepare_overfit_batch, synthetic_graphs

DEFAULT_OUTPUT = Path("artifacts/gnn-overfit")
VARIANTS: dict[str, Callable[[GraphMetadata, ModelConfig], SCFAGraphModel]] = {
    "homo_sage": HomoSAGE,
    "hetero_sage": HeteroSAGE,
    "hetero_gat": HeteroGAT,
}
CURVE_POINTS = 60
EXIT_OK = 0
EXIT_NOT_OVERFIT = 1


def mermaid_curve(name: str, losses: Sequence[float]) -> str:
    """Curva `log10(pérdida)` por época en Mermaid `xychart-beta`, con hasta `CURVE_POINTS`."""
    step = max(1, math.ceil(len(losses) / CURVE_POINTS))
    epochs = list(range(0, len(losses), step))
    if epochs[-1] != len(losses) - 1:
        epochs.append(len(losses) - 1)
    values = [math.log10(max(losses[e], 1e-12)) for e in epochs]
    low, high = math.floor(min(values)), math.ceil(max(values))
    return "\n".join(
        [
            "```mermaid",
            "xychart-beta",
            f'    title "{name}: log10 de la pérdida de entrenamiento"',
            f'    x-axis "época" [{", ".join(str(e + 1) for e in epochs)}]',
            f'    y-axis "log10(MSE)" {low} --> {high}',
            f"    line [{', '.join(f'{v:.3f}' for v in values)}]",
            "```",
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--n-graphs", type=int, default=8)
    parser.add_argument("--first-seed", type=int, default=1)
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=42, help="Semilla de torch por variante.")
    parser.add_argument("--threshold", type=float, default=1e-2)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    graphs = synthetic_graphs(args.n_graphs, args.first_seed)
    data = prepare_overfit_batch(graphs)
    metadata = GraphMetadata.from_graphs(graphs)
    config = ModelConfig(dropout=0.0)

    curves: dict[str, list[float]] = {}
    for name, factory in VARIANTS.items():
        torch.manual_seed(args.seed)
        model = factory(metadata, config)
        initialize_lazy_parameters(model)
        curves[name] = overfit_losses(model, data, epochs=args.epochs, lr=args.lr)

    results = {
        name: {
            "initial_loss": losses[0],
            "final_loss": losses[-1],
            "min_loss": min(losses),
            "overfit": losses[-1] < args.threshold,
        }
        for name, losses in curves.items()
    }
    summary = {
        "n_graphs": args.n_graphs,
        "first_seed": args.first_seed,
        "graph_ids": list(data.graph_ids),
        "epochs": args.epochs,
        "lr": args.lr,
        "seed": args.seed,
        "threshold": args.threshold,
        "model_config": {
            "hidden_channels": config.hidden_channels,
            "num_layers": config.num_layers,
            "dropout": config.dropout,
        },
        "variants": results,
    }

    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "losses.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["epoch", *curves])
        for epoch in range(args.epochs):
            writer.writerow([epoch + 1, *(curves[name][epoch] for name in curves)])
    (args.output / "curves.md").write_text(
        "\n\n".join(mermaid_curve(name, losses) for name, losses in curves.items()) + "\n",
        encoding="utf-8",
    )
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    for name, result in results.items():
        status = "sobreajusta" if result["overfit"] else "NO sobreajusta"
        print(
            f"{name}: pérdida {result['initial_loss']:.4f} -> {result['final_loss']:.2e} "
            f"({status}; umbral {args.threshold:g})"
        )
    print(f"Resultados en {args.output.as_posix()}")
    return EXIT_OK if all(result["overfit"] for result in results.values()) else EXIT_NOT_OVERFIT


if __name__ == "__main__":
    raise SystemExit(main())
