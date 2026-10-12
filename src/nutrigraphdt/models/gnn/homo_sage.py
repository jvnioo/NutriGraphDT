"""GNN homogénea de referencia, `homo_sage` (A41-2, #78; §5 del diseño de A41-1, #77).

Ignora los tipos de nodo y de arista: después de los encoders por tipo de A41-5, el grafo se
convierte con `to_homogeneous()` y cada capa aplica una única `SAGEConv` compartida por todos
los nodos y relaciones. Es el control que mide cuánto aporta modelar la heterogeneidad frente a
`hetero_sage` (#79) y `hetero_gat` (#80).

La proyección por tipo ocurre antes de `to_homogeneous()`, porque los tipos tienen distinto
número de columnas. Encoder, residual, lectura y cabeza son los de `SCFAGraphModel`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

import torch
from torch import Tensor, nn
from torch_geometric.data import HeteroData
from torch_geometric.nn import SAGEConv

from nutrigraphdt.models.gnn.base import EdgeType, GraphMetadata, ModelConfig, SCFAGraphModel

SAGE_AGGREGATIONS: Final[frozenset[str]] = frozenset({"mean", "max", "sum"})


class HomoSAGE(SCFAGraphModel):
    """`homo_sage`: `num_layers` capas de `SAGEConv(hidden, hidden, aggr)` sobre el grafo
    homogéneo.

    Parameters
    ----------
    metadata, config:
        Como en `SCFAGraphModel`.
    aggr:
        Agregación de vecinos de `SAGEConv`. Valor inicial del diseño: ``"mean"`` (§6).
    """

    def __init__(self, metadata: GraphMetadata, config: ModelConfig, *, aggr: str = "mean") -> None:
        if aggr not in SAGE_AGGREGATIONS:
            raise ValueError(f"aggr {aggr!r} no válida. Permitidas: {sorted(SAGE_AGGREGATIONS)}")
        super().__init__(metadata, config)
        self.aggr = aggr
        hidden = config.hidden_channels
        self.convs = nn.ModuleList(
            SAGEConv(hidden, hidden, aggr=aggr) for _ in range(config.num_layers)
        )

    def convolve(
        self,
        layer: int,
        h_dict: Mapping[str, Tensor],
        edge_index_dict: Mapping[EdgeType, Tensor],
    ) -> dict[str, Tensor]:
        """Convierte `h_dict` a un grafo homogéneo, aplica la `SAGEConv` de la capa y separa la
        salida por tipo de nodo. Devuelve una actualización para todos los tipos de `h_dict`."""
        if not h_dict:
            return {}
        graph = HeteroData()
        for node_type, h in h_dict.items():
            graph[node_type].x = h
        for edge_type, edge_index in edge_index_dict.items():
            source, _, target = edge_type
            if source in h_dict and target in h_dict:
                graph[edge_type].edge_index = edge_index
        homogeneous = graph.to_homogeneous(node_attrs=["x"], add_edge_type=False)
        x: Tensor = homogeneous.x
        edge_index = homogeneous.edge_index
        if edge_index is None:  # sin aristas en el grafo
            edge_index = torch.empty((2, 0), dtype=torch.long, device=x.device)
        output: Tensor = self.convs[layer](x, edge_index)
        type_index: Tensor = homogeneous.node_type
        return {
            name: output[type_index == position] for position, name in enumerate(graph.node_types)
        }


__all__ = ["SAGE_AGGREGATIONS", "HomoSAGE"]
