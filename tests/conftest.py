"""Fixtures compartidas por las pruebas.

`heterodata_builder` convierte una instancia sintética en `HeteroData` siguiendo la sección
"Correspondencia con `HeteroData`" de `docs/synthetic-dataset-spec.md`. Es un fixture de prueba
para ejercitar los validadores de tensores (VG-05 en adelante). **No** es el constructor canónico
del grafo (#28): elige una codificación de features mínima solo para tener columnas declaradas.

Requiere el extra `graph`; las pruebas que lo usan se omiten si PyTorch Geometric no está
instalado.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

import pytest

NODE_FEATURE_COLUMNS: dict[str, list[str]] = {
    "additive": ["dose"],
    "substrate": ["quantity"],
    "taxon": ["abundance"],
    "function": ["annotation_value"],
    "metabolite": ["concentration"],
    "phenotype": ["value"],
}
"""Columna numérica de cada tipo. `diet` y `host` no tienen features: su `x` es `[N, 0]`."""

EDGE_FEATURE_COLUMNS: dict[str, list[str]] = {"diet|provides|substrate": ["proportion"]}
"""Columna numérica de cada relación. Las demás relaciones usan `edge_attr` `[E, 0]`."""


def feature_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Copia de `metadata.json` que declara las columnas de `NODE/EDGE_FEATURE_COLUMNS`."""
    declared = copy.deepcopy(metadata)
    declared["node_feature_schema"] = {
        node_type: [{"name": name, "source": f"attributes.{name}", "encoding": "raw"}]
        for node_type, names in NODE_FEATURE_COLUMNS.items()
        for name in names
    }
    declared["edge_feature_schema"] = {
        key: [{"name": name, "source": f"attributes.{name}", "encoding": "raw"}]
        for key, names in EDGE_FEATURE_COLUMNS.items()
        for name in names
    }
    return declared


def build_heterodata(
    dataset: Any, graph_id: str, *, features: bool = True
) -> tuple[Any, dict[str, Any]]:
    """Convierte la instancia `graph_id` de `dataset` según la correspondencia de DS-01.

    Devuelve el `HeteroData` y el `metadata.json` que declara sus columnas. Con
    `features=False`, todos los tipos y relaciones usan cero columnas, como declara el
    `metadata.json` que exporta DS-05, y se devuelve ese mismo metadata.
    """
    import torch
    from torch_geometric.data import HeteroData

    from nutrigraphdt.data.synthetic.edges import edge_sort_key

    instance = next(item for item in dataset.instances if item.graph_id == graph_id)
    data = HeteroData()

    nodes: dict[str, list[Any]] = {}
    for item in dataset.nodes:
        if item.graph_id == graph_id:
            nodes.setdefault(item.node_type, []).append(item)
    rows: dict[tuple[str, str], int] = {}
    for node_type, items in nodes.items():
        items.sort(key=lambda item: item.node_id)
        columns = NODE_FEATURE_COLUMNS.get(node_type, []) if features else []
        values = [[item.attributes.get(name) for name in columns] for item in items]
        store = data[node_type]
        store.x = torch.tensor(
            [[0.0 if value is None else float(value) for value in row] for row in values],
            dtype=torch.float32,
        ).reshape(len(items), len(columns))
        store.missing_mask = torch.tensor(
            [[bool(item.missing_mask.get(name, False)) for name in columns] for item in items],
            dtype=torch.bool,
        ).reshape(len(items), len(columns))
        store.node_id = [item.node_id for item in items]
        store.source_id = [item.source_id for item in items]
        store.raw_attributes = [copy.deepcopy(item.attributes) for item in items]
        rows.update({(node_type, item.node_id): row for row, item in enumerate(items)})

    edges: dict[tuple[str, str, str], list[Any]] = {}
    for item in sorted(dataset.edges, key=edge_sort_key):
        if item.graph_id == graph_id:
            edges.setdefault(item.edge_type, []).append(item)
    for edge_type, items in edges.items():
        columns = EDGE_FEATURE_COLUMNS.get("|".join(edge_type), []) if features else []
        store = data[edge_type]
        store.edge_index = torch.tensor(
            [
                [rows[(item.source_type, item.source_id)] for item in items],
                [rows[(item.target_type, item.target_id)] for item in items],
            ],
            dtype=torch.long,
        )
        store.edge_attr = torch.tensor(
            [[float(item.attributes[name]) for name in columns] for item in items],
            dtype=torch.float32,
        ).reshape(len(items), len(columns))
        store.evidence_id = [item.evidence_id for item in items]
        store.evidence_status = [item.evidence_status for item in items]
        store.evidence_method = [item.evidence_method for item in items]
        store.raw_attributes = [copy.deepcopy(item.attributes) for item in items]

    for name, value in instance.to_dict().items():
        if value is not None:
            setattr(data, name, value)
    data.output_records = [
        output.to_dict() for output in dataset.outputs if output.graph_id == graph_id
    ]
    metadata = feature_metadata(dataset.metadata) if features else copy.deepcopy(dataset.metadata)
    return data, metadata


@pytest.fixture
def heterodata_builder() -> Callable[..., Any]:
    """Devuelve `build_heterodata`; omite la prueba si falta el extra `graph`."""
    pytest.importorskip("torch_geometric")
    return build_heterodata
