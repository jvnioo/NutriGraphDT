"""Inicialización de parámetros lazy de modelos GNN heterogéneos."""

from __future__ import annotations

import torch
from torch_geometric.data import HeteroData

from nutrigraphdt.models.gnn.base import SCFAGraphModel


def initialize_lazy_parameters(model: SCFAGraphModel) -> None:
    """Inicializa capas lazy con una pasada sintética que cubre toda la metadata.

    Ejecute esta función antes de crear el optimizador. Incluye cada relación declarada por el
    modelo, aunque no aparezca en un lote real. No modifica el modo train/eval del modelo.
    """
    reference = next(model.parameters())
    graph = HeteroData()
    for node_type, channels in model.metadata.node_channels.items():
        graph[node_type].num_nodes = 1
        graph[node_type].x = torch.zeros(
            (1, channels), device=reference.device, dtype=reference.dtype
        )
        graph[node_type].missing_mask = torch.zeros(
            (1, channels), device=reference.device, dtype=torch.bool
        )
    for edge_type in model.metadata.edge_types:
        graph[edge_type].edge_index = torch.empty((2, 0), device=reference.device, dtype=torch.long)

    with torch.no_grad():
        model(graph)


__all__ = ["initialize_lazy_parameters"]
