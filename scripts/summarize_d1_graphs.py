"""Genera el resumen versionado de los grafos de D1 que muestra la demo (`scripts/demo_app.py`).

Lee el reporte de `scripts/build_graph.py` (`artifacts/graphs/D1_holofood/report.json`, decenas
de MB, no versionado) y los AGCC de la descarga completa de D1, y escribe
`reports/graphs/d1_summary.json`: totales de integración, nodos y aristas por tipo, validación
por regla, contratos y cuantiles de los AGCC. No guarda valores por animal ni datos crudos.

Uso:

    python scripts/fetch_holofood.py
    python scripts/build_graph.py
    python scripts/summarize_d1_graphs.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from nutrigraphdt.demo.data import (
    D1_REPORT,
    D1_SUMMARY,
    agcc_by_animal,
    d1_records,
    summarize_d1_report,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--report", type=Path, default=D1_REPORT)
    parser.add_argument("--output", type=Path, default=D1_SUMMARY)
    args = parser.parse_args(argv)
    if not args.report.is_file():
        print(f"No existe {args.report}: ejecute scripts/build_graph.py.", file=sys.stderr)
        return 2
    d1 = d1_records()
    if not d1.full:
        print(
            "Falta la descarga completa de D1: ejecute scripts/fetch_holofood.py.", file=sys.stderr
        )
        return 2
    summary = summarize_d1_report(args.report, agcc_by_animal(d1.records))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"{summary['graphs']['instances']} grafos, {summary['deliverable']} entregables, "
        f"AGCC de {summary['agcc']['acetate']['n']} animales. Archivo: {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
