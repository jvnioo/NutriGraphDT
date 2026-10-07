"""Construye y audita los grafos heterogéneos de una fuente real (A39-1 y A39-2).

Uso:

    # Fuente D1 HoloFood ya descargada con scripts/fetch_holofood.py
    python scripts/build_graph.py

    # Además, guarda los HeteroData (requiere el extra `graph`)
    python scripts/build_graph.py --save-graphs --overwrite

Flujo: `DataPipeline` sobre la fuente de abundancias → `attach_sample_context` con sus
metadatos y metabolitos → `build_hetero_graph` → `audit_built_graphs`. Escribe en `--output`
`report.json` (reglas de registro y de tensores, contratos y resumen de los grafos) y, con
`--save-graphs`, un `.pt` por instancia en `graphs/`. Los grafos se guardan aunque tengan
`ERROR`: el reporte indica cuáles son entregables a un modelo.

Código de salida: `0` si los grafos se construyeron (con o sin hallazgos), `2` si la fuente no
pudo leerse o las tablas no tienen traducción al esquema v1.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from nutrigraphdt.data.config import load_sources
from nutrigraphdt.data.integration import attach_sample_context
from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader
from nutrigraphdt.data.pipeline import DataPipeline
from nutrigraphdt.graph.audit import audit_built_graphs
from nutrigraphdt.graph.builder import build_hetero_graph
from nutrigraphdt.graph.heterodata import save_graphs


def main() -> int:
    parser = argparse.ArgumentParser(description="Construye y audita grafos de una fuente real.")
    parser.add_argument("--sources", type=Path, default=Path("configs/sources.json"))
    parser.add_argument("--abundance", default="D1_holofood", help="Fuente de abundancias.")
    parser.add_argument("--metadata", default="D1_holofood_metadata", help="Fuente de metadatos.")
    parser.add_argument(
        "--metabolites", default="D1_holofood_scfa_content", help="Fuente de metabolitos."
    )
    parser.add_argument("--sample-matrix", default="cecal_content")
    parser.add_argument("--output", type=Path, default=Path("artifacts/graphs/D1_holofood"))
    parser.add_argument("--save-graphs", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.output.exists() and any(args.output.iterdir()) and not args.overwrite:
        print(f"{args.output} ya tiene contenido; use --overwrite.", file=sys.stderr)
        return 2
    try:
        sources = load_sources(args.sources)
        tables = DataPipeline({args.abundance: sources[args.abundance]}).run([args.abundance])
        tables_with_context, integration = attach_sample_context(
            tables.dataset,
            metadata=MetadataLoader(sources[args.metadata]).load(),
            metabolites=MetaboliteLoader(sources[args.metabolites]).load(),
            sample_matrix=args.sample_matrix,
        )
        built = build_hetero_graph(tables_with_context)
    except (KeyError, ValueError, FileNotFoundError) as error:
        print(f"No se pudieron construir los grafos: {error}", file=sys.stderr)
        return 2

    audit = audit_built_graphs(built)
    if args.output.exists() and args.overwrite:
        shutil.rmtree(args.output)
    args.output.mkdir(parents=True, exist_ok=True)
    payload = {
        "sources": [args.abundance, args.metadata, args.metabolites],
        "integration": {
            "instances_with_context": integration.instances_with_context,
            "host_features": integration.host_features,
            "targets": integration.targets,
            "unmatched_metadata_samples": len(integration.unmatched_metadata_samples),
            "unmatched_metabolite_samples": len(integration.unmatched_metabolite_samples),
        },
        **audit.to_dict(),
    }
    (args.output / "report.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if args.save_graphs:
        save_graphs(built.graphs, args.output / "graphs", overwrite=True)

    report = audit.report
    print(f"Instancias: {len(built.graphs)}; entregables: {len(report.deliverable_graph_ids)}")
    print(f"Hallazgos: {json.dumps(payload['validation']['summary'], ensure_ascii=False)}")
    for rule_id, entry in payload["validation"]["rules"].items():
        print(f"  {rule_id} {entry['severity']}: {entry['count']}")
    contracts = audit.contracts
    print(
        f"Contratos: {contracts.invalid_nodes}/{contracts.checked_nodes} nodos y "
        f"{contracts.invalid_edges}/{contracts.checked_edges} aristas no los cumplen."
    )
    print(f"Reporte: {args.output / 'report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
