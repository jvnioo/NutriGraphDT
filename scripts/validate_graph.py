"""Valida la integridad de un dataset exportado y genera un reporte (VG-07).

Lee `metadata.json` y `raw/*.jsonl` sin rechazar el primer defecto, ejecuta todas las reglas de
registro de `docs/graph-integrity-rules.md` mediante `validate_graph` y resume el resultado. Con
`--report`, escribe el reporte completo en JSON.

Las reglas de tensores (`TEN`) no se evalúan aquí, porque requieren los `HeteroData` que
producirá el constructor del grafo. El reporte lo indica en `not_evaluated`.

La validación es estructural: un dataset sin errores es coherente con el contrato, no
biológicamente válido.

Códigos de salida:

- 0: sin hallazgos `ERROR` (puede haber advertencias);
- 1: hay hallazgos `ERROR`, y los grafos afectados no deben entregarse al modelo;
- 2: el dataset no se pudo leer (archivo ausente o JSON no válido).

Uso:

    python scripts/generate_synthetic_dataset.py
    python scripts/validate_graph.py
    python scripts/validate_graph.py --input artifacts/synthetic/v1 --report report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from nutrigraphdt.data.synthetic import DatasetFormatError
from nutrigraphdt.graph.validation import ValidationReport, read_raw_dataset, validate_graph

DEFAULT_INPUT = Path("artifacts/synthetic/v1")
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

    report = validate_graph(dataset)
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
