"""Valida la integridad de un dataset exportado y, opcionalmente, de sus grafos (VG-07, A35-2).

Lee `metadata.json` y `raw/*.jsonl` sin rechazar el primer defecto, ejecuta todas las reglas de
`docs/graph/graph-integrity-rules.md` mediante `validate_graph` y resume el resultado. Con
`--report`, escribe el reporte completo en JSON.

Con `--graphs`, carga también los `HeteroData` que guarda `generate_synthetic_dataset.py
--graphs` (por defecto, `<input>/graphs`) y evalúa las reglas de tensores (`TEN`). Requiere el
extra `graph`. Sin `--graphs`, el reporte indica que las reglas `TEN` no se evaluaron.

La validación es estructural: un dataset sin errores es coherente con el contrato, no
biológicamente válido.

Códigos de salida:

- 0: sin hallazgos `ERROR` (puede haber advertencias);
- 1: hay hallazgos `ERROR`, y los grafos afectados no deben entregarse al modelo;
- 2: el dataset o los grafos no se pudieron leer (archivo ausente, JSON no válido o `.pt`
  rechazado por la carga segura).

Uso:

    python scripts/generate_synthetic_dataset.py --graphs
    python scripts/validate_graph.py --graphs
    python scripts/validate_graph.py --input artifacts/synthetic/v1 --graphs --report report.json
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from nutrigraphdt.data.synthetic import DatasetFormatError
from nutrigraphdt.graph.validation import ValidationReport, read_raw_dataset, validate_graph

DEFAULT_INPUT = Path("artifacts/synthetic/v1")
GRAPHS_DIR = "graphs"
EXIT_VALID = 0
EXIT_INVALID = 1
EXIT_UNREADABLE = 2


def summarize(report: ValidationReport, *, max_findings: int) -> list[str]:
    """Resumen legible del reporte: estado, conteos, instancias y primeros errores."""
    data = report.to_dict()
    summary = data["summary"]
    lines = [
        f"estado: {data['status']}  (reglas {data['rules_version']}, "
        f"esquema {data['schema_version']})",
        f"hallazgos: ERROR={summary['ERROR']}  ADVERTENCIA={summary['ADVERTENCIA']}  "
        f"INFO={summary['INFO']}  (errores de nivel dataset: {data['dataset_errors']})",
        f"familias evaluadas: {', '.join(data['evaluated'])}",
    ]
    for graph_id, graph in data["graphs"].items():
        state = "entregable" if graph["deliverable"] else "BLOQUEADO"
        lines.append(
            f"  [{graph_id}] {state}  ERROR={graph['ERROR']}  "
            f"ADVERTENCIA={graph['ADVERTENCIA']}  INFO={graph['INFO']}"
        )
    for family, reason in data["not_evaluated"].items():
        lines.append(f"no evaluado {family}: {reason}")
    if data["rules"]:
        lines.append("reglas con hallazgos:")
        for rule_id, entry in data["rules"].items():
            lines.append(f"  {rule_id} ({entry['severity']}): {entry['count']}")
    errors = report.errors[:max_findings]
    if errors:
        lines.append(f"primeros {len(errors)} error(es):")
        lines.extend(f"  {finding.rule_id}: {finding.message}" for finding in errors)
    lines.append(data["scope"])
    return lines


def _load_graphs(directory: Path) -> dict[str, Any] | None:
    """Carga los grafos con la carga segura del prototipo; `None` (con el motivo) si no puede."""
    try:
        from nutrigraphdt.graph.heterodata import load_graphs
    except ImportError:
        print(
            "--graphs requiere PyTorch y PyTorch Geometric (extra `graph`); ver "
            "docs/process/development.md.",
            file=sys.stderr,
        )
        return None
    try:
        return load_graphs(directory)
    except FileNotFoundError as error:
        print(f"No se encontraron grafos en {directory}: {error}", file=sys.stderr)
        print(
            "Genéralos con: python scripts/generate_synthetic_dataset.py --graphs",
            file=sys.stderr,
        )
    except (OSError, KeyError, ValueError, RuntimeError, pickle.UnpicklingError) as error:
        # Manifiesto mal formado, archivo dañado o `.pt` rechazado por la carga segura.
        print(f"No se pudieron cargar los grafos de {directory}: {error}", file=sys.stderr)
    return None


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Directorio del dataset exportado (por defecto: {DEFAULT_INPUT}).",
    )
    parser.add_argument(
        "--graphs",
        nargs="?",
        const=True,
        default=None,
        metavar="DIR",
        help="Valida también los grafos HeteroData (por defecto, <input>/graphs).",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Ruta donde escribir el reporte completo en JSON.",
    )
    parser.add_argument(
        "--max-findings",
        type=int,
        default=10,
        help="Número máximo de errores que se muestran en consola (por defecto: 10).",
    )
    args = parser.parse_args(argv)

    try:
        dataset = read_raw_dataset(args.input)
    except DatasetFormatError as error:
        print(f"No se pudo leer el dataset: {error}", file=sys.stderr)
        print(
            "Genera uno con: python scripts/generate_synthetic_dataset.py",
            file=sys.stderr,
        )
        return EXIT_UNREADABLE

    heterodata = None
    if args.graphs is not None:
        directory = args.input / GRAPHS_DIR if args.graphs is True else Path(args.graphs)
        heterodata = _load_graphs(directory)
        if heterodata is None:
            return EXIT_UNREADABLE

    try:
        report = validate_graph(dataset, heterodata=heterodata)
    except ValueError as error:
        print(f"Los grafos no corresponden al dataset: {error}", file=sys.stderr)
        return EXIT_UNREADABLE
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(report.to_dict(), handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
    print("\n".join(summarize(report, max_findings=args.max_findings)))
    if args.report is not None:
        print(f"reporte: {args.report}")
    return EXIT_VALID if report.is_valid else EXIT_INVALID


if __name__ == "__main__":
    sys.exit(main())
