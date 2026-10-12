"""Componentes compartidos por las variantes GNN (A41-5, #81).

Implementa el §4 del diseño de A41-1 (`docs/models/gnn-architecture.md`, #77):

```text
x_t, missing_mask_t ──► NodeTypeEncoder ──► h^0 ──► [convolución × L + ResidualUpdate] ──► h^L
h^L ──► mean_readout (media por grafo de cada tipo de entrada) ──► ScfaRegressionHead ──► [B, 3]
```

Todos trabajan con diccionarios por tipo de nodo (`x_dict`, `h_dict`, `batch_dict`), el formato
de `HeteroData` y de un lote de `torch_geometric.loader.DataLoader`. Requiere el extra `graph`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

import torch
from torch import Tensor, nn
from torch_geometric.nn import global_mean_pool

from nutrigraphdt.graph.schema import NODE_TYPES
from nutrigraphdt.models.metrics import DEFAULT_SCFA_TARGETS

# Nodos objetivo y de resultado: participan en el paso de mensajes, pero no en la lectura (§2.2).
EXCLUDED_FROM_READOUT: Final[frozenset[str]] = frozenset({"metabolite", "phenotype"})

# Tipos de entrada que se promedian, en el orden de `NODE_TYPES`: diet, additive, substrate,
# taxon, function y host. La dimensión de la lectura es len(READOUT_NODE_TYPES) · hidden.
READOUT_NODE_TYPES: Final[tuple[str, ...]] = tuple(
    node_type for node_type in NODE_TYPES if node_type not in EXCLUDED_FROM_READOUT
)


def check_positive(name: str, value: int) -> None:
    """Exige un entero positivo (sin aceptar `bool`)."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} debe ser un entero positivo; se recibió {value!r}.")


def check_dropout(value: float) -> None:
    """Exige una probabilidad de dropout en [0, 1)."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not 0.0 <= value < 1.0:
        raise ValueError(f"dropout debe estar en [0, 1); se recibió {value!r}.")


def infer_in_channels(x_dict: Mapping[str, Tensor]) -> dict[str, int]:
    """Número de columnas de `x` (`F_t`) por tipo de nodo, por ejemplo desde `data.x_dict`."""
    channels: dict[str, int] = {}
    for node_type, x in x_dict.items():
        if x.dim() != 2:
            raise ValueError(f"x de '{node_type}' debe tener 2 dimensiones; tiene {x.dim()}.")
        channels[node_type] = int(x.size(1))
    return channels


class NodeTypeEncoder(nn.Module):
    """Proyecta los atributos de cada tipo de nodo a `hidden_channels`.

    Un tipo con `F_t > 0` columnas usa `Linear(2·F_t, hidden_channels)` sobre
    `[x_t ‖ missing_mask_t]`: la máscara entra como feature para que un `0.0` ausente no se
    confunda con un cero medido. Un tipo con `F_t = 0` (`x` de forma `[N, 0]`) usa un vector
    aprendido de tamaño `hidden_channels`, igual para todos sus nodos.

    La proyección es lineal; la activación la aplican las capas siguientes.
    """

    def __init__(self, in_channels: Mapping[str, int], hidden_channels: int) -> None:
        super().__init__()
        check_positive("hidden_channels", hidden_channels)
        if not in_channels:
            raise ValueError("in_channels debe declarar al menos un tipo de nodo.")
        self.hidden_channels = hidden_channels
        self.in_channels: dict[str, int] = {}
        self.projections = nn.ModuleDict()
        self.type_embeddings = nn.ParameterDict()
        for node_type in sorted(in_channels):
            channels = in_channels[node_type]
            if isinstance(channels, bool) or not isinstance(channels, int) or channels < 0:
                raise ValueError(
                    f"in_channels de '{node_type}' debe ser un entero >= 0; "
                    f"se recibió {channels!r}."
                )
            self.in_channels[node_type] = channels
            if channels > 0:
                self.projections[node_type] = nn.Linear(2 * channels, hidden_channels)
            else:
                self.type_embeddings[node_type] = nn.Parameter(torch.randn(hidden_channels))

    def forward(
        self, x_dict: Mapping[str, Tensor], missing_mask_dict: Mapping[str, Tensor]
    ) -> dict[str, Tensor]:
        """Devuelve un embedding `[N_t, hidden_channels]` por cada tipo presente en `x_dict`.

        `missing_mask_dict` es `data.missing_mask_dict`: una máscara booleana de la misma forma
        que `x` por tipo de nodo.
        """
        output: dict[str, Tensor] = {}
        for node_type, x in x_dict.items():
            expected = self.in_channels.get(node_type)
            if expected is None:
                raise KeyError(
                    f"Tipo de nodo '{node_type}' no declarado en el encoder. "
                    f"Declarados: {sorted(self.in_channels)}"
                )
            if x.dim() != 2 or x.size(1) != expected:
                raise ValueError(
                    f"x de '{node_type}' debe tener forma [N, {expected}]; tiene {list(x.shape)}."
                )
            if expected == 0:
                embedding = self.type_embeddings[node_type]
                output[node_type] = embedding.unsqueeze(0).expand(x.size(0), -1)
                continue
            mask = missing_mask_dict.get(node_type)
            if mask is None or mask.shape != x.shape:
                raise ValueError(
                    f"missing_mask de '{node_type}' debe tener la forma de x, {list(x.shape)}."
                )
            features = torch.cat([x, mask.to(x.dtype)], dim=-1)
            output[node_type] = self.projections[node_type](features)
        return output


class ResidualUpdate(nn.Module):
    """Conexión residual entre capas: `h_t^{l+1} = h_t^l + dropout(act(conv_t(h^l)))`.

    `HeteroConv` solo devuelve los tipos que son destino de alguna arista. Un tipo ausente de
    `update_dict` (por ejemplo, `taxon` y `diet`, aislados en D1) conserva su embedding sin
    cambios en vez de desaparecer.
    """

    def __init__(self, dropout: float = 0.0) -> None:
        super().__init__()
        check_dropout(dropout)
        self.activation = nn.ReLU()
        self.dropout = nn.Dropout(dropout)

    def forward(
        self, h_dict: Mapping[str, Tensor], update_dict: Mapping[str, Tensor]
    ) -> dict[str, Tensor]:
        """Suma la actualización de cada tipo a su embedding anterior."""
        unknown = sorted(set(update_dict) - set(h_dict))
        if unknown:
            raise KeyError(f"La convolución devolvió tipos sin embedding previo: {unknown}")
        output: dict[str, Tensor] = {}
        for node_type, h in h_dict.items():
            update = update_dict.get(node_type)
            if update is None:
                output[node_type] = h
                continue
            if update.shape != h.shape:
                raise ValueError(
                    f"La actualización de '{node_type}' debe tener forma {list(h.shape)}; "
                    f"tiene {list(update.shape)}."
                )
            output[node_type] = h + self.dropout(self.activation(update))
        return output


def mean_readout(
    h_dict: Mapping[str, Tensor],
    batch_dict: Mapping[str, Tensor] | None,
    num_graphs: int,
    hidden_channels: int,
) -> Tensor:
    """Media por grafo de cada tipo de `READOUT_NODE_TYPES`, concatenada en ese orden.

    Devuelve `[num_graphs, len(READOUT_NODE_TYPES) · hidden_channels]`. `batch_dict` asigna
    cada nodo a su grafo dentro del lote (`batch.batch_dict`); con `None`, todos los nodos son de
    un único grafo. Un tipo sin nodos en un grafo aporta ceros. `metabolite` y `phenotype` no
    entran a la lectura.
    """
    check_positive("num_graphs", num_graphs)
    check_positive("hidden_channels", hidden_channels)
    reference = next(iter(h_dict.values()), None)
    dtype = reference.dtype if reference is not None else torch.float32
    device = reference.device if reference is not None else None
    pooled: list[Tensor] = []
    for node_type in READOUT_NODE_TYPES:
        embeddings = h_dict.get(node_type)
        if embeddings is None or embeddings.size(0) == 0:
            pooled.append(torch.zeros(num_graphs, hidden_channels, dtype=dtype, device=device))
            continue
        if embeddings.dim() != 2 or embeddings.size(1) != hidden_channels:
            raise ValueError(
                f"El embedding de '{node_type}' debe tener forma [N, {hidden_channels}]; "
                f"tiene {list(embeddings.shape)}."
            )
        if batch_dict is None:
            batch = torch.zeros(embeddings.size(0), dtype=torch.long, device=embeddings.device)
        else:
            found = batch_dict.get(node_type)
            if found is None or found.dim() != 1 or found.size(0) != embeddings.size(0):
                raise ValueError(
                    f"batch_dict de '{node_type}' debe asignar un grafo a cada uno de sus "
                    f"{embeddings.size(0)} nodos."
                )
            batch = found
        pooled.append(global_mean_pool(embeddings, batch, size=num_graphs))
    return torch.cat(pooled, dim=-1)


class ScfaRegressionHead(nn.Module):
    """Cabeza de regresión: `Linear(6·hidden, hidden) → ReLU → Dropout → Linear(hidden, 3)`.

    Recibe la salida de `mean_readout` y devuelve `[B, len(targets)]`. No tiene activación
    final: el target está estandarizado y la predicción puede ser negativa. Las columnas siguen
    `targets`, por defecto `DEFAULT_SCFA_TARGETS` = (acetate, propionate, butyrate).
    """

    def __init__(
        self,
        hidden_channels: int,
        *,
        dropout: float = 0.0,
        targets: tuple[str, ...] = DEFAULT_SCFA_TARGETS,
    ) -> None:
        super().__init__()
        check_positive("hidden_channels", hidden_channels)
        check_dropout(dropout)
        if isinstance(targets, str) or not targets or len(set(targets)) != len(targets):
            raise ValueError("targets debe ser una secuencia no vacía de nombres distintos.")
        self.hidden_channels = hidden_channels
        self.targets: tuple[str, ...] = tuple(targets)
        self.in_features = len(READOUT_NODE_TYPES) * hidden_channels
        self.mlp = nn.Sequential(
            nn.Linear(self.in_features, hidden_channels),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_channels, len(self.targets)),
        )

    def forward(self, pooled: Tensor) -> Tensor:
        """Predice los AGCC a partir de la lectura `[B, 6·hidden]`."""
        if pooled.dim() != 2 or pooled.size(1) != self.in_features:
            raise ValueError(
                f"La lectura debe tener forma [B, {self.in_features}]; tiene {list(pooled.shape)}."
            )
        output: Tensor = self.mlp(pooled)
        return output


__all__ = [
    "EXCLUDED_FROM_READOUT",
    "READOUT_NODE_TYPES",
    "NodeTypeEncoder",
    "ResidualUpdate",
    "ScfaRegressionHead",
    "check_dropout",
    "check_positive",
    "infer_in_channels",
    "mean_readout",
]
