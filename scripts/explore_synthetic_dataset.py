"""Ejemplo de carga y exploración del dataset sintético de NutriGraphDT (DS-07).

Carga un dataset exportado con `generate_synthetic_dataset.py`, lo valida mediante la interfaz
pública `nutrigraphdt.data.synthetic` y resume su contenido. Todo el contenido es sintético:
los valores no son observaciones reales ni resultados biológicos.

Uso:

    python scripts/generate_synthetic_dataset.py
    python scripts/explore_synthetic_dataset.py

    # Otro directorio exportado
    python scripts/explore_synthetic_dataset.py --input artifacts/synthetic/seed-7
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from nutrigraphdt.data.synthetic import (
    DatasetFormatError,
    DatasetValidationError,
    SyntheticDataset,
    load_dataset,
)

DEFAULT_INPUT = Path("artifacts/synthetic/v1")


def diet_composition(dataset: SyntheticDataset, graph_id: str) -> dict[str, tuple[float, str]]:
    """Devuelve `{component_id: (valor, unidad)}` de la dieta de una instancia."""
    composition: dict[str, tuple[float, str]] = {}
    for node in dataset.nodes:
        if node.graph_id == graph_id and node.node_type == "diet":
            for item in node.attributes["composition"]:
                composition[item["component_id"]] = (item["value"], item["unit"])
    return composition


def summarize(dataset: SyntheticDataset) -> list[str]:
    """Construye un resumen legible del dataset cargado."""
    metadata = dataset.metadata
    lines = [
        f"dataset_id: {metadata['dataset_id']}",
        f"schema_version: {metadata['schema_version']}  "
        f"generator_version: {metadata['generator_version']}",
        f"is_synthetic: {metadata['is_synthetic']}  random_seed: {metadata['random_seed']}",
        f"instancias: {len(dataset.instances)}  nodos: {len(dataset.nodes)}  "
        f"aristas: {len(dataset.edges)}  salidas: {len(dataset.outputs)}",
    ]

    for instance in dataset.instances:
        graph_id = instance.graph_id
        lines.append("")
        lines.append(f"[{graph_id}] scenario_id={instance.scenario_id}")
        lines.append(f"  diet_treatment: {instance.diet_treatment}")
        node_counts = Counter(n.node_type for n in dataset.nodes if n.graph_id == graph_id)
        lines.append("  nodos: " + ", ".join(f"{t}={c}" for t, c in sorted(node_counts.items())))
        edge_counts = Counter(
            "|".join(e.edge_type) for e in dataset.edges if e.graph_id == graph_id
        )
        lines.append("  aristas:")
        lines.extend(f"    {key}: {count}" for key, count in sorted(edge_counts.items()))

    # Comparación de la dieta entre escenarios: identifica la variable intervenida sin
    # afirmar ningún efecto sobre el resto del grafo.
    scenarios = {instance.scenario_id: instance.graph_id for instance in dataset.instances}
    if {"basal", "intervention"} <= scenarios.keys():
        basal = diet_composition(dataset, scenarios["basal"])
        intervened = diet_composition(dataset, scenarios["intervention"])
        changed = sorted(key for key in basal if basal[key] != intervened.get(key))
        lines.append("")
        lines.append("Componentes de dieta que difieren entre basal e intervención:")
        for key in changed:
            (before, unit), (after, _) = basal[key], intervened[key]
            lines.append(f"  {key}: {before} -> {after} {unit} [sintético]")
    return lines


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Carga y resume un dataset sintético exportado.")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Directorio exportado (por defecto: {DEFAULT_INPUT.as_posix()}).",
    )
    args = parser.parse_args(argv)

    try:
        dataset = load_dataset(args.input)
    except DatasetFormatError as error:
        raise SystemExit(
            f"No se pudo leer el dataset: {error}\n"
            "Genera uno con: python scripts/generate_synthetic_dataset.py"
        ) from error
    except DatasetValidationError as error:
        raise SystemExit(f"El dataset no cumple el contrato:\n{error}") from error

    print("\n".join(summarize(dataset)))


if __name__ == "__main__":
    main()
