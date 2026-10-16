"""Tabla comparativa GNN frente a baselines para el avance 2 (A45-6).

Lee `reports/baselines/` y `reports/gnn/`, verifica con los `run.json` que cada variante GNN use
las mismas muestras y la misma partición que los baselines de su dataset, y escribe
`reports/comparison/model_comparison.md` y `.csv`. No entrena modelos ni requiere PyTorch o
scikit-learn.

Uso:

    python scripts/compare_models.py
    python scripts/compare_models.py --output reports/comparison

Termina con código 2 si falta un reporte de baselines, si un reporte es inválido o si alguna GNN
no está alineada con los baselines.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from nutrigraphdt.models.comparison import (
    ComparisonError,
    assess_criterion,
    default_sources,
    load_dataset,
    to_csv,
    to_markdown,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "comparison"
MARKDOWN_FILE = "model_comparison.md"
CSV_FILE = "model_comparison.csv"
COMMAND = "python scripts/compare_models.py"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Raíz desde la que se leen reports/ y configs/splits/ (por defecto, el repositorio).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Carpeta de salida (por defecto, reports/comparison/ bajo --repo-root).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.repo_root.resolve()
    output = args.output if args.output is not None else root / "reports" / "comparison"
    try:
        comparisons = [load_dataset(sources) for sources in default_sources(root)]
    except ComparisonError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    output.mkdir(parents=True, exist_ok=True)
    (output / MARKDOWN_FILE).write_text(to_markdown(comparisons, COMMAND), encoding="utf-8")
    (output / CSV_FILE).write_text(to_csv(comparisons), encoding="utf-8")

    for comparison in comparisons:
        result = assess_criterion(comparison)
        state = "se cumple" if result.met else "no se cumple"
        pending = f"; pendientes: {', '.join(comparison.pending)}" if comparison.pending else ""
        print(
            f"{comparison.sources.label}: criterio de F4 {state} "
            f"(mejor GNN {result.best_gnn}, mejor baseline {result.best_baseline}){pending}"
        )
    print(f"Escrito {output / MARKDOWN_FILE} y {output / CSV_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
