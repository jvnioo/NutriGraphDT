"""Interfaz común de los modelos GNN (A41-5, #81; §3 del diseño de A41-1, #77).

Las tres variantes (`homo_sage` #78, `hetero_sage` #79 y `hetero_gat` #80) heredan de
`SCFAGraphModel` e implementan solo `convolve`: encoder, residual, lectura y cabeza son los de
`components.py`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from torch import Tensor, nn
from torch_geometric.data import HeteroData

from nutrigraphdt.models.gnn.components import (
    READOUT_NODE_TYPES,
    NodeTypeEncoder,
    ResidualUpdate,
    ScfaRegressionHead,
    check_dropout,
    check_positive,
    infer_in_channels,
    mean_readout,
)
from nutrigraphdt.models.metrics import DEFAULT_SCFA_TARGETS

EdgeType = tuple[str, str, str]


@dataclass(frozen=True)
class GraphMetadata:
    """Describe un dataset, no un grafo.

    `node_channels` da el número de columnas de `x` (`F_t`) por tipo de nodo. `edge_types` es la
    **unión** de tipos de arista de todos los grafos, incluidas las inversas `rev_*`: un grafo
    que no tiene alguna relación usa el mismo modelo.
    """

    node_channels: Mapping[str, int]
    edge_types: tuple[EdgeType, ...]

    def __post_init__(self) -> None:
        if not self.node_channels:
            raise ValueError("GraphMetadata requiere al menos un tipo de nodo.")
        for node_type, channels in self.node_channels.items():
            if isinstance(channels, bool) or not isinstance(channels, int) or channels < 0:
                raise ValueError(
                    f"node_channels de '{node_type}' debe ser un entero >= 0; "
                    f"se recibió {channels!r}."
                )
        edge_types = tuple(sorted({tuple(edge_type) for edge_type in self.edge_types}))
        for edge_type in edge_types:
            if len(edge_type) != 3:
                raise ValueError(f"Tipo de arista {edge_type!r} no es (origen, relación, destino).")
            for node_type in (edge_type[0], edge_type[2]):
                if node_type not in self.node_channels:
                    raise ValueError(
                        f"La arista {edge_type} usa el tipo de nodo '{node_type}', "
                        "que no está en node_channels."
                    )
        object.__setattr__(
            self, "node_channels", MappingProxyType(dict(sorted(self.node_channels.items())))
        )
        object.__setattr__(self, "edge_types", edge_types)

    @property
    def node_types(self) -> tuple[str, ...]:
        """Tipos de nodo, en orden alfabético."""
        return tuple(self.node_channels)

    def to_pyg(self) -> tuple[list[str], list[EdgeType]]:
        """Mismo formato que `HeteroData.metadata()`, para `HeteroConv` y `to_hetero`."""
        return list(self.node_types), list(self.edge_types)

    @classmethod
    def from_graphs(cls, graphs: Iterable[HeteroData]) -> GraphMetadata:
        """Unión de tipos de nodo y de arista de `graphs`.

        Raises
        ------
        ValueError
            Si no hay grafos o un tipo de nodo cambia de número de columnas entre grafos.
        """
        node_channels: dict[str, int] = {}
        edge_types: set[EdgeType] = set()
        count = 0
        for graph in graphs:
            count += 1
            x_dict = {t: graph[t].x for t in graph.node_types if "x" in graph[t]}
            for node_type, channels in infer_in_channels(x_dict).items():
                previous = node_channels.setdefault(node_type, channels)
                if previous != channels:
                    raise ValueError(
                        f"'{node_type}' tiene {previous} columnas en un grafo y {channels} en "
                        "otro; el dataset debe usar un esquema de features común."
                    )
            edge_types.update(
                (str(source), str(relation), str(target))
                for source, relation, target in graph.edge_types
            )
        if count == 0:
            raise ValueError("from_graphs requiere al menos un grafo.")
        return cls(node_channels, tuple(edge_types))

    @classmethod
    def from_feature_schema(
        cls,
        node_feature_schema: Mapping[str, Sequence[Any]],
        edge_types: Iterable[EdgeType],
    ) -> GraphMetadata:
        """Desde `node_feature_schema` de los metadatos del dataset (una columna por entrada)."""
        node_channels = {t: len(columns) for t, columns in node_feature_schema.items()}
        return cls(node_channels, tuple(edge_types))


@dataclass(frozen=True)
class ModelConfig:
    """Hiperparámetros comunes, con los valores iniciales del §6 del diseño.

    Los de cada variante (agregación, cabezas de atención) y la lectura desde YAML corresponden
    a #78, #79, #80 y a la fábrica de A41-8 (#84).
    """

    hidden_channels: int = 64
    num_layers: int = 2
    dropout: float = 0.2

    def __post_init__(self) -> None:
        check_positive("hidden_channels", self.hidden_channels)
        check_positive("num_layers", self.num_layers)
        check_dropout(self.dropout)


def layer_edge_types(metadata: GraphMetadata, num_layers: int) -> tuple[tuple[EdgeType, ...], ...]:
    """Tripletas que reciben convolución en cada capa (#111), de la capa 0 a la `num_layers - 1`.

    Una convolución de la capa `l` con destino `t` solo afecta la predicción si `t` entra a la
    lectura o si su embedding alimenta, como origen, una convolución que sí la afecta en una
    capa posterior. Se recorre desde la última capa hacia la primera: en la última solo quedan
    los destinos de `READOUT_NODE_TYPES`; en las anteriores se agregan los orígenes de las
    tripletas ya conservadas. Las demás convoluciones nunca reciben gradiente y no se crean.
    """
    check_positive("num_layers", num_layers)
    relevant = set(READOUT_NODE_TYPES)
    layers: list[tuple[EdgeType, ...]] = []
    for _ in range(num_layers):
        kept = tuple(edge_type for edge_type in metadata.edge_types if edge_type[2] in relevant)
        relevant.update(edge_type[0] for edge_type in kept)
        layers.append(kept)
    return tuple(reversed(layers))


def graph_batch(data: HeteroData) -> tuple[dict[str, Tensor] | None, int]:
    """`batch_dict` y número de grafos de `data`.

    Un lote de `DataLoader` tiene `batch` por tipo de nodo y `num_graphs`. Un grafo individual no
    tiene `batch`: se devuelve `(None, 1)`.
    """
    batch_dict = {t: data[t].batch for t in data.node_types if "batch" in data[t]}
    if not batch_dict:
        return None, 1
    return batch_dict, int(data.num_graphs)


class SCFAGraphModel(nn.Module, ABC):
    """Clase base de las GNN que predicen los tres AGCC por grafo.

    `forward` aplica el encoder por tipo, `num_layers` veces `convolve` con residual, la lectura
    por grafo y la cabeza. Devuelve `float32` `[B, 3]`, en el orden de `target_names`. Lee
    `x_dict`, `missing_mask_dict`, `edge_index_dict` y `batch_dict`; no lee `y`, `y_mask`,
    `y_graph`, `y_graph_mask`, `raw_attributes` ni la evidencia.
    """

    target_names: tuple[str, ...] = DEFAULT_SCFA_TARGETS

    def __init__(self, metadata: GraphMetadata, config: ModelConfig) -> None:
        super().__init__()
        self.metadata = metadata
        self.config = config
        self.encoder = NodeTypeEncoder(metadata.node_channels, config.hidden_channels)
        self.residual = ResidualUpdate(config.dropout)
        self.head = ScfaRegressionHead(
            config.hidden_channels, dropout=config.dropout, targets=self.target_names
        )

    @abstractmethod
    def convolve(
        self,
        layer: int,
        h_dict: Mapping[str, Tensor],
        edge_index_dict: Mapping[EdgeType, Tensor],
    ) -> dict[str, Tensor]:
        """Convolución de la capa `layer` (de 0 a `num_layers - 1`), sin activación.

        Devuelve `[N_t, hidden_channels]` para los tipos que actualiza; los que no devuelve
        conservan su embedding (ver `ResidualUpdate`).
        """

    def forward(self, data: HeteroData) -> Tensor:
        """Predicción `[B, 3]` para un grafo (`B = 1`) o un lote de `DataLoader`."""
        x_dict = {t: data[t].x for t in data.node_types if "x" in data[t]}
        mask_dict = {t: data[t].missing_mask for t in data.node_types if "missing_mask" in data[t]}
        edge_index_dict: dict[EdgeType, Tensor] = {
            (str(s), str(r), str(t)): data[(s, r, t)].edge_index
            for s, r, t in data.edge_types
            if "edge_index" in data[(s, r, t)]
        }
        h_dict = self.encoder(x_dict, mask_dict)
        for layer in range(self.config.num_layers):
            h_dict = self.residual(h_dict, self.convolve(layer, h_dict, edge_index_dict))
        batch_dict, num_graphs = graph_batch(data)
        pooled = mean_readout(h_dict, batch_dict, num_graphs, self.config.hidden_channels)
        output: Tensor = self.head(pooled)
        return output


__all__ = [
    "EdgeType",
    "GraphMetadata",
    "ModelConfig",
    "SCFAGraphModel",
    "graph_batch",
    "layer_edge_types",
]
