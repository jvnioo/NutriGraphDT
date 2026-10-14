"""Prueba de cordura: sobreajuste a un lote sintético pequeño (A41-7, #83).

Comprueba que cada variante es capaz de aprender antes del pipeline de entrenamiento (act. 44):
con suficientes épocas sobre un mismo lote pequeño, la pérdida de entrenamiento debe bajar hasta
cerca de cero. Si no baja, hay un defecto de construcción (gradientes que no llegan, capas sin
efecto, escalas que impiden optimizar), no una falta de datos.

El lote se estandariza con sus propias estadísticas (features por tipo y columna, target por
AGCC): aquí el lote **es** el conjunto de entrenamiento, así que no hay fuga. No reemplaza el
escalado del pipeline (A44-2, #96), que ajusta con `train` y aplica a `val` y `test`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import torch
from torch import Tensor
from torch_geometric.data import HeteroData
from torch_geometric.loader import DataLoader

from nutrigraphdt.data.synthetic import (
    SyntheticEdgeConfig,
    SyntheticNodeConfig,
    generate_synthetic_dataset,
)
from nutrigraphdt.graph.builder import add_reverse_edges
from nutrigraphdt.graph.heterodata import build_synthetic_graphs
from nutrigraphdt.models.gnn.base import SCFAGraphModel
from nutrigraphdt.models.gnn.target import add_graph_target, masked_mse_loss


@dataclass(frozen=True)
class OverfitBatch:
    """Lote único con features estandarizadas y target estandarizado por AGCC."""

    batch: HeteroData
    target: Tensor
    mask: Tensor
    graph_ids: tuple[str, ...]


def synthetic_graphs(n_graphs: int, first_seed: int = 1) -> list[HeteroData]:
    """`n_graphs` grafos sintéticos de semillas consecutivas, con inversas y target por grafo.

    Cada semilla se convierte por separado con `build_synthetic_graphs`, que aplica la compuerta
    de VG-07. Los grafos se devuelven en orden de `graph_id`.

    Raises:
        ValueError: si `n_graphs < 1` o alguna semilla no produce un grafo entregable.
    """
    if n_graphs < 1:
        raise ValueError(f"n_graphs debe ser >= 1: {n_graphs}.")
    graphs: dict[str, HeteroData] = {}
    for seed in range(first_seed, first_seed + n_graphs):
        graph_id = f"synthetic:graph:{seed:04d}"
        built = build_synthetic_graphs(
            generate_synthetic_dataset(
                SyntheticNodeConfig(graph_id=graph_id, random_seed=seed),
                SyntheticEdgeConfig(random_seed=seed),
            )
        ).graphs
        if graph_id not in built:
            raise ValueError(f"La semilla {seed} no produjo un grafo entregable.")
        graphs[graph_id] = built[graph_id]
    return [add_graph_target(add_reverse_edges(graphs[gid])) for gid in sorted(graphs)]


def prepare_overfit_batch(graphs: Sequence[HeteroData]) -> OverfitBatch:
    """Estandariza features y target con las estadísticas del propio lote y lo agrupa.

    Features: media y desviación por tipo y columna sobre las celdas observadas; las ausentes
    conservan su valor. Target: media y desviación por AGCC sobre las celdas con valor. Una
    columna constante usa desviación 1. No modifica `graphs`.

    Raises:
        ValueError: si no hay grafos o ningún grafo tiene AGCC.
    """
    if not graphs:
        raise ValueError("prepare_overfit_batch requiere al menos un grafo.")
    copies = [graph.clone() for graph in graphs]
    node_types = sorted({node_type for graph in copies for node_type in graph.node_types})
    for node_type in node_types:
        stores = [graph[node_type] for graph in copies if "x" in graph[node_type]]
        if not stores or stores[0].x.size(1) == 0:
            continue
        x = torch.cat([store.x for store in stores])
        observed = ~torch.cat([store.missing_mask for store in stores])
        mean, std = _masked_mean_std(x, observed)
        for store in stores:
            store.x = torch.where(store.missing_mask, store.x, (store.x - mean) / std)

    batch = next(iter(DataLoader(copies, batch_size=len(copies))))
    mask: Tensor = batch.y_graph_mask
    if not bool(mask.any()):
        raise ValueError("Ningún grafo del lote tiene AGCC; no hay target que ajustar.")
    mean, std = _masked_mean_std(batch.y_graph, mask)
    target = torch.where(mask, (batch.y_graph - mean) / std, 0.0)
    graph_ids = tuple(str(graph.graph_id) for graph in copies)
    return OverfitBatch(batch=batch, target=target, mask=mask, graph_ids=graph_ids)


def overfit_losses(
    model: SCFAGraphModel,
    data: OverfitBatch,
    *,
    epochs: int,
    lr: float,
) -> list[float]:
    """Entrena `model` sobre el mismo lote durante `epochs` pasos de Adam.

    Devuelve la pérdida de entrenamiento (`masked_mse_loss` en la escala estandarizada) antes de
    cada paso. El modelo queda en modo `train`; use `dropout = 0` para que la pérdida refleje
    solo la capacidad de ajuste. Fije la semilla antes de construir el modelo.
    """
    if epochs < 1:
        raise ValueError(f"epochs debe ser >= 1: {epochs}.")
    model.train()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    losses: list[float] = []
    for _ in range(epochs):
        optimizer.zero_grad()
        loss = masked_mse_loss(model(data.batch), data.target, data.mask)
        loss.backward()  # type: ignore[no-untyped-call]
        optimizer.step()
        losses.append(float(loss.detach()))
    return losses


def _masked_mean_std(values: Tensor, mask: Tensor) -> tuple[Tensor, Tensor]:
    count = mask.sum(dim=0).clamp(min=1)
    mean = torch.where(mask, values, 0.0).sum(dim=0) / count
    variance = (torch.where(mask, values - mean, 0.0) ** 2).sum(dim=0) / count
    std = torch.where(variance > 0, variance.sqrt(), torch.ones_like(variance))
    return mean, std


__all__ = [
    "OverfitBatch",
    "overfit_losses",
    "prepare_overfit_batch",
    "synthetic_graphs",
]
