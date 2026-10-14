"""GAT heterogénea con una convolución por relación (A41-4, #80)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, cast

import torch
from torch import Tensor, nn
from torch_geometric.data import HeteroData
from torch_geometric.nn import GATConv, HeteroConv

from nutrigraphdt.models.gnn.base import (
    EdgeType,
    GraphMetadata,
    ModelConfig,
    SCFAGraphModel,
    layer_edge_types,
)
from nutrigraphdt.models.gnn.components import check_positive
from nutrigraphdt.models.gnn.hetero_sage import HETERO_RELATION_AGGREGATIONS


class HeteroGAT(SCFAGraphModel):
    """`hetero_gat`: GATConv independiente por tripleta de relación y capa.

    Cada capa crea las tripletas de `layer_edge_types`: en la última no hay convoluciones hacia
    `metabolite` ni `phenotype`, que no entran a la lectura y no recibirían gradiente (#111).

    Parameters
    ----------
    metadata, config:
        Como en `SCFAGraphModel`.
    heads:
        Número de cabezas de atención.
    concat:
        Si es `True`, concatena las cabezas; si es `False`, las promedia.
    relation_aggr:
        Agregación de actualizaciones de relaciones en cada `HeteroConv`.
    """

    def __init__(
        self,
        metadata: GraphMetadata,
        config: ModelConfig,
        *,
        heads: int = 4,
        concat: bool = True,
        relation_aggr: str = "sum",
    ) -> None:
        check_positive("heads", heads)
        if not isinstance(concat, bool):
            raise ValueError(f"concat debe ser bool; se recibió {concat!r}.")
        if relation_aggr not in HETERO_RELATION_AGGREGATIONS:
            raise ValueError(
                f"relation_aggr {relation_aggr!r} no válida. "
                f"Permitidas: {sorted(HETERO_RELATION_AGGREGATIONS)}"
            )
        hidden = config.hidden_channels
        if concat and hidden % heads != 0:
            raise ValueError(
                f"hidden_channels ({hidden}) debe ser divisible por heads ({heads}) "
                "cuando concat=True."
            )

        super().__init__(metadata, config)
        self.heads = heads
        self.concat = concat
        self.relation_aggr = relation_aggr
        out_channels = hidden // heads if concat else hidden
        self.convs = nn.ModuleList(
            HeteroConv(
                {
                    edge_type: GATConv(
                        (-1, -1),
                        out_channels,
                        heads=heads,
                        concat=concat,
                        add_self_loops=False,
                    )
                    for edge_type in edge_types
                },
                aggr=relation_aggr,
            )
            for edge_types in layer_edge_types(metadata, config.num_layers)
        )
        self._attention_capture: dict[tuple[int, EdgeType], tuple[Tensor, Tensor]] | None = None

    def convolve(
        self,
        layer: int,
        h_dict: Mapping[str, Tensor],
        edge_index_dict: Mapping[EdgeType, Tensor],
    ) -> dict[str, Tensor]:
        """Aplica la convolución relacional de la capa, sin activar ni aplicar dropout."""
        hetero_conv = self.convs[layer]
        if self._attention_capture is None:
            output: dict[str, Tensor] = hetero_conv(dict(h_dict), dict(edge_index_dict))
            return output

        convolutions = hetero_conv.convs
        if not isinstance(convolutions, nn.ModuleDict):
            raise TypeError("HeteroConv debe contener un ModuleDict para capturar atención.")

        relation_outputs: dict[str, list[Tensor]] = {}
        for relation_key, convolution in convolutions.items():
            edge_type = cast(EdgeType, relation_key)
            if not isinstance(convolution, GATConv):
                raise TypeError(f"La convolución de {edge_type!r} no es una GATConv.")
            if edge_type not in edge_index_dict:
                continue
            output, (attention_edge_index, alpha) = convolution(
                (h_dict[edge_type[0]], h_dict[edge_type[2]]),
                edge_index_dict[edge_type],
                return_attention_weights=True,
            )
            if not isinstance(output, Tensor):
                raise TypeError(f"La salida de GATConv para {edge_type!r} no es un tensor.")
            self._attention_capture[(layer, edge_type)] = (attention_edge_index, alpha)
            relation_outputs.setdefault(edge_type[2], []).append(output)

        if self.relation_aggr == "sum":
            return {
                node_type: torch.stack(outputs).sum(dim=0)
                for node_type, outputs in relation_outputs.items()
            }
        return {
            node_type: torch.stack(outputs).mean(dim=0)
            for node_type, outputs in relation_outputs.items()
        }

    def forward_with_attention(
        self, data: HeteroData
    ) -> tuple[Tensor, dict[tuple[int, EdgeType], tuple[Tensor, Tensor]]]:
        """Devuelve la predicción habitual y pesos por (capa, tripleta de relación)."""
        previous_capture = self._attention_capture
        attention: dict[tuple[int, EdgeType], tuple[Tensor, Tensor]] = {}
        self._attention_capture = attention
        try:
            prediction = self(data)
        finally:
            self._attention_capture = previous_capture
        return prediction, attention


__all__: Final = ["HeteroGAT"]
