"""Fixtures compartidas por las pruebas.

`heterodata_builder` convierte una instancia sintética en `HeteroData` siguiendo la sección
"Correspondencia con `HeteroData`" de `docs/synthetic-dataset-spec.md`. Es un fixture de prueba
para ejercitar los validadores de tensores (VG-05 en adelante). **No** es el prototipo del
constructor (`nutrigraphdt.graph.heterodata`, #28): se mantiene independiente a propósito, para
que los validadores se prueben contra el contrato y no contra una implementación concreta.

Requiere el extra `graph`; las pruebas que lo usan se omiten si PyTorch Geometric no está
instalado.

`minimal_synthetic_dataset` es el grafo sintético mínimo de A35-3 (#30): una instancia con
pocos nodos por tipo y todas las relaciones permitidas activas con probabilidad 1, de modo que
sus conteos de nodos y aristas se pueden calcular a mano.

Con la variable de entorno `NUTRIGRAPHDT_REQUIRE_GRAPH=1` (la fija el CI), la sesión falla si
falta el extra `graph`, en lugar de omitir en silencio las pruebas de tensores.
"""

from __future__ import annotations

import copy
import importlib.util
import os
from collections.abc import Callable
from typing import Any

import pytest

from nutrigraphdt.data.synthetic import (
    NodeCountConfig,
    SyntheticDataset,
    SyntheticEdgeConfig,
    SyntheticNodeConfig,
    generate_synthetic_dataset,
)
from nutrigraphdt.data.synthetic.edges import ALLOWED_RELATIONS

REQUIRE_GRAPH_ENV = "NUTRIGRAPHDT_REQUIRE_GRAPH"

MINIMAL_SEED = 7
MINIMAL_NODE_COUNTS = NodeCountConfig(
    diet=1, additive=1, substrate=2, taxon=3, function=2, metabolite=2, host=1, phenotype=1
)
"""Nodos por tipo del grafo mínimo: suficientes para que cada relación tenga varias aristas."""


def pytest_configure(config: pytest.Config) -> None:
    """Exige el extra `graph` cuando `NUTRIGRAPHDT_REQUIRE_GRAPH=1`."""
    if os.environ.get(REQUIRE_GRAPH_ENV) == "1" and (
        importlib.util.find_spec("torch") is None
        or importlib.util.find_spec("torch_geometric") is None
    ):
        raise pytest.UsageError(
            f"{REQUIRE_GRAPH_ENV}=1 pero falta el extra `graph` (torch y torch-geometric); "
            "las pruebas de HeteroData no pueden omitirse."
        )


def generate_minimal_dataset() -> SyntheticDataset:
    """Dataset sintético de una instancia con `MINIMAL_NODE_COUNTS` y todas las relaciones.

    Cada relación permitida tiene probabilidad 1, así que se conecta todo par candidato y el
    resultado no depende del azar de las aristas.
    """
    return generate_synthetic_dataset(
        SyntheticNodeConfig(random_seed=MINIMAL_SEED, counts=MINIMAL_NODE_COUNTS),
        SyntheticEdgeConfig(
            random_seed=MINIMAL_SEED,
            relation_probabilities=dict.fromkeys(ALLOWED_RELATIONS, 1.0),
        ),
    )


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


@pytest.fixture
def minimal_synthetic_dataset() -> SyntheticDataset:
    """Grafo sintético mínimo de A35-3 (ver `generate_minimal_dataset`)."""
    return generate_minimal_dataset()
