"""GraphSAGE heterogénea con una convolución por relación (A41-3, #79)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from torch import Tensor, nn
from torch_geometric.nn import HeteroConv, SAGEConv

from nutrigraphdt.models.gnn.base import EdgeType, GraphMetadata, ModelConfig, SCFAGraphModel
from nutrigraphdt.models.gnn.homo_sage import SAGE_AGGREGATIONS

HETERO_RELATION_AGGREGATIONS: Final[frozenset[str]] = frozenset({"mean", "sum"})


class HeteroSAGE(SCFAGraphModel):
    """`hetero_sage`: SAGEConv independiente por tripleta de relación y capa.

    Parameters
    ----------
    metadata, config:
        Como en `SCFAGraphModel`.
    aggr:
        Agregación de vecinos de cada `SAGEConv`.
    relation_aggr:
        Agregación de actualizaciones de relaciones en cada `HeteroConv`.
    """

    def __init__(
        self,
        metadata: GraphMetadata,
        config: ModelConfig,
        *,
        aggr: str = "mean",
        relation_aggr: str = "sum",
    ) -> None:
        if aggr not in SAGE_AGGREGATIONS:
            raise ValueError(f"aggr {aggr!r} no válida. Permitidas: {sorted(SAGE_AGGREGATIONS)}")
        if relation_aggr not in HETERO_RELATION_AGGREGATIONS:
            raise ValueError(
                f"relation_aggr {relation_aggr!r} no válida. "
                f"Permitidas: {sorted(HETERO_RELATION_AGGREGATIONS)}"
            )
        super().__init__(metadata, config)
        self.aggr = aggr
        self.relation_aggr = relation_aggr
        hidden = config.hidden_channels
        self.convs = nn.ModuleList(
            HeteroConv(
                {
                    edge_type: SAGEConv((-1, -1), hidden, aggr=aggr)
                    for edge_type in metadata.edge_types
                },
                aggr=relation_aggr,
            )
            for _ in range(config.num_layers)
        )

    def convolve(
        self,
        layer: int,
        h_dict: Mapping[str, Tensor],
        edge_index_dict: Mapping[EdgeType, Tensor],
    ) -> dict[str, Tensor]:
        """Aplica la convolución relacional de la capa, sin activar ni aplicar dropout."""
        output: dict[str, Tensor] = self.convs[layer](dict(h_dict), dict(edge_index_dict))
        return output


__all__ = ["HETERO_RELATION_AGGREGATIONS", "HeteroSAGE"]
