"""Grafos con los mismos tipos de nodo y de arista antes de agruparlos en lotes (#119).

PyG exige que todos los grafos de un lote tengan las mismas claves. Si un tipo de arista falta en
un grafo, `Batch.from_data_list` lo salta al calcular los desplazamientos de `edge_index`, y las
aristas de los grafos siguientes quedan apuntando a nodos de **otro** grafo del lote. Además, en
`hetero_sage` y `hetero_gat` una relación presente en el lote suma `lin_r(x) + bias` a sus
destinos aunque no tengan vecinos, así que un grafo se procesaría distinto solo que en un lote.

`align_graph_types` completa cada grafo con los tipos de la unión que le faltan, vacíos, para que
la predicción de un grafo no dependa de con qué otros grafos comparte lote.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import torch
from torch import Tensor
from torch_geometric.data import HeteroData

StoreKey = str | tuple[str, str, str]


def align_graph_types(graphs: Sequence[HeteroData], *, inplace: bool = False) -> list[HeteroData]:
    """Grafos que tienen todos los tipos de nodo y de arista presentes en `graphs`.

    Un tipo que falta se agrega vacío, con los atributos que tiene en los demás grafos: tensores
    con tamaño 0 en la dimensión en que PyG los concatena (`edge_index` `[2, 0]`, `x`
    `[0, F_t]`) y listas vacías. No agrega ni quita nodos o aristas. Con `inplace=False` trabaja
    sobre copias y no modifica `graphs`.
    """
    aligned = list(graphs) if inplace else [graph.clone() for graph in graphs]
    templates: dict[StoreKey, dict[str, Any]] = {}
    for graph in aligned:
        for key in (*graph.node_types, *graph.edge_types):
            if key in templates:
                continue
            store = graph[key]
            templates[key] = {
                name: _empty_like(graph, name, value, store)
                for name, value in store.items()
                if isinstance(value, (list, tuple))
                or (isinstance(value, Tensor) and value.dim() > 0)
            }
    for graph in aligned:
        present = set(graph.node_types) | set(graph.edge_types)
        for key, attributes in templates.items():
            if key in present:
                continue
            store = graph[key]
            for name, empty in attributes.items():
                store[name] = empty.clone() if isinstance(empty, Tensor) else []
    return aligned


def _empty_like(graph: HeteroData, name: str, value: Any, store: Any) -> Tensor | list[Any]:
    if not isinstance(value, Tensor):
        return []
    shape = list(value.shape)
    dim = graph.__cat_dim__(name, value, store)
    shape[dim] = 0
    return torch.empty(shape, dtype=value.dtype, device=value.device)


__all__ = ["align_graph_types"]
