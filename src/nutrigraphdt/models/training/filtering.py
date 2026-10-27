"""Filtrado de taxones raros ajustado exclusivamente con train (A52-P2, #160).

Selecciona el vocabulario de taxones sobre la partición de entrenamiento (`train`) según
un umbral de prevalencia mínima (`min_prevalence`), abundancia mínima (`min_abundance`)
o un límite superior de taxones más frecuentes (`top_k`).

Aplica el filtrado podando los nodos `taxon` no seleccionados tanto en `train` como en `val`
y `test`, garantizando que ninguna información de validación o prueba intervenga en la
selección (prevención estricta de fuga de datos). Reindexa coherentemente las aristas
conectadas a taxones cuando existen en el grafo.
"""

from __future__ import annotations

import dataclasses
import warnings
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import torch
from torch_geometric.data import HeteroData
from torch_geometric.loader import DataLoader

from nutrigraphdt.models.gnn.base import GraphMetadata
from nutrigraphdt.models.training.dataloaders import PreparedDataLoaders

SUBSETS: tuple[str, ...] = ("train", "val", "test")


@dataclass(frozen=True)
class TaxonFilterConfig:
    """Configuración para el filtrado de taxones raros.

    Attributes
    ----------
    min_prevalence : float
        Fracción mínima de muestras de entrenamiento en las que el taxón debe estar presente
        (abundancia > `min_abundance`) para ser conservado. Rango [0.0, 1.0].
    min_abundance : float
        Umbral de abundancia para considerar presencia en una muestra (por defecto 0.0).
    top_k : int | None
        Número máximo de taxones a conservar tras aplicar el filtro de prevalencia, ordenados
        por prevalencia y abundancia total descendente. `None` conserva todos los que superen
        el umbral.
    """

    min_prevalence: float = 0.1
    min_abundance: float = 0.0
    top_k: int | None = None

    def __post_init__(self) -> None:
        if not (0.0 <= self.min_prevalence <= 1.0):
            msg = f"min_prevalence debe estar en [0.0, 1.0], recibido: {self.min_prevalence}"
            raise ValueError(msg)
        if self.min_abundance < 0.0:
            raise ValueError(f"min_abundance no puede ser negativa, recibido: {self.min_abundance}")
        if self.top_k is not None and self.top_k <= 0:
            raise ValueError(f"top_k debe ser un entero positivo o None, recibido: {self.top_k}")


@dataclass(frozen=True)
class TaxonStats:
    """Estadísticas de presencia y abundancia de un taxón observadas en train.

    Attributes
    ----------
    node_id : str
        Identificador canónico del nodo taxon (p. ej. 'g__Bacteroides').
    prevalence : float
        Fracción de muestras de train en las que el taxón estuvo presente.
    occurrence_count : int
        Número absoluto de muestras de train donde estuvo presente.
    mean_abundance : float
        Abundancia media en train sobre todas las muestras.
    total_abundance : float
        Abundancia acumulada en train.
    """

    node_id: str
    prevalence: float
    occurrence_count: int
    mean_abundance: float
    total_abundance: float


class TaxonFilter:
    """Filtro de taxones raros ajustado exclusivamente con estadísticas de entrenamiento.

    Calcula la prevalencia y abundancia de cada taxón únicamente sobre los grafos de `train`
    y poda en todos los subconjuntos los nodos que no alcanzaron el umbral. Reasigna los
    índices de aristas que apunten a nodos podados para preservar la integridad del grafo.
    """

    def __init__(
        self,
        selected_taxa: frozenset[str] | None = None,
        config: TaxonFilterConfig | None = None,
        taxon_stats: Mapping[str, TaxonStats] | None = None,
        train_num_graphs: int = 0,
    ) -> None:
        self._config = config or TaxonFilterConfig()
        self._selected_taxa: frozenset[str] = (
            selected_taxa if selected_taxa is not None else frozenset()
        )
        self._taxon_stats: dict[str, TaxonStats] = (
            dict(taxon_stats) if taxon_stats is not None else {}
        )
        self._train_num_graphs: int = train_num_graphs
        self._is_fitted: bool = selected_taxa is not None

    @property
    def is_fitted(self) -> bool:
        """Indica si el filtro ya fue ajustado sobre un conjunto de entrenamiento."""
        return self._is_fitted

    @property
    def config(self) -> TaxonFilterConfig:
        """Configuración del filtro."""
        return self._config

    @property
    def selected_taxa(self) -> frozenset[str]:
        """Conjunto inmutable de identificadores de taxones retenidos."""
        return self._selected_taxa

    @property
    def taxon_stats(self) -> dict[str, TaxonStats]:
        """Estadísticas de los taxones observados en el conjunto de entrenamiento."""
        return dict(self._taxon_stats)

    @property
    def train_num_graphs(self) -> int:
        """Número de grafos de entrenamiento sobre los que se ajustó el filtro."""
        return self._train_num_graphs

    @classmethod
    def fit(
        cls,
        train_graphs: Sequence[HeteroData],
        *,
        config: TaxonFilterConfig | None = None,
        min_prevalence: float = 0.1,
        min_abundance: float = 0.0,
        top_k: int | None = None,
    ) -> TaxonFilter:
        """Ajusta un `TaxonFilter` usando exclusivamente los grafos de entrenamiento.

        Parameters
        ----------
        train_graphs : Sequence[HeteroData]
            Grafos pertenecientes únicamente a la partición de entrenamiento.
        config : TaxonFilterConfig | None
            Objeto de configuración explícito; si se omite, se construye con los
            argumentos restantes.
        min_prevalence : float
            Prevalencia mínima [0.0, 1.0].
        min_abundance : float
            Abundancia mínima requerida para considerar presencia en una muestra.
        top_k : int | None
            Límite superior de taxones a conservar.

        Returns
        -------
        TaxonFilter
            Filtro ajustado listo para transformar grafos.
        """
        if not train_graphs:
            raise ValueError(
                "No se puede ajustar TaxonFilter sobre una colección vacía de grafos de train."
            )

        cfg = config or TaxonFilterConfig(
            min_prevalence=min_prevalence,
            min_abundance=min_abundance,
            top_k=top_k,
        )

        n_graphs = len(train_graphs)
        counts: dict[str, int] = defaultdict(int)
        totals: dict[str, float] = defaultdict(float)
        seen_taxa: set[str] = set()

        for g in train_graphs:
            if "taxon" not in g.node_types:
                continue
            t_store = g["taxon"]
            if t_store.num_nodes == 0:
                continue

            node_ids = getattr(t_store, "node_id", None)
            if node_ids is None:
                continue

            x_tensor = getattr(t_store, "x", None)
            sample_taxa_seen: set[str] = set()

            for i, nid in enumerate(node_ids):
                seen_taxa.add(nid)
                val = 0.0
                if x_tensor is not None and x_tensor.ndim >= 2 and x_tensor.shape[0] > i:
                    val = float(x_tensor[i, 0].item())
                elif x_tensor is not None and x_tensor.ndim == 1 and x_tensor.shape[0] > i:
                    val = float(x_tensor[i].item())

                totals[nid] += val
                if val > cfg.min_abundance and nid not in sample_taxa_seen:
                    counts[nid] += 1
                    sample_taxa_seen.add(nid)

        stats: dict[str, TaxonStats] = {}
        for nid in seen_taxa:
            occ = counts[nid]
            prev = occ / n_graphs
            tot = totals[nid]
            mean_ab = tot / n_graphs
            stats[nid] = TaxonStats(
                node_id=nid,
                prevalence=prev,
                occurrence_count=occ,
                mean_abundance=mean_ab,
                total_abundance=tot,
            )

        # Filtrar por prevalencia mínima
        filtered = [nid for nid, st in stats.items() if st.prevalence >= cfg.min_prevalence]

        # Ordenar por prevalencia descendente y abundancia total descendente
        filtered.sort(
            key=lambda nid: (stats[nid].prevalence, stats[nid].total_abundance),
            reverse=True,
        )

        if cfg.top_k is not None:
            filtered = filtered[: cfg.top_k]

        if not filtered and seen_taxa:
            warnings.warn(
                f"TaxonFilter: Ningún taxón de train superó min_prevalence={cfg.min_prevalence}. "
                "El vocabulario resultante quedará vacío.",
                UserWarning,
                stacklevel=2,
            )

        selected = frozenset(filtered)
        return cls(
            selected_taxa=selected,
            config=cfg,
            taxon_stats=stats,
            train_num_graphs=n_graphs,
        )

    def transform_graph(self, graph: HeteroData) -> HeteroData:
        """Aplica el filtro a un único grafo, podando los taxones ausentes de `selected_taxa`.

        Preserva inmutabilidad clonando el grafo original. Reasigna `edge_index` para
        aristas que conecten con `taxon`.
        """
        if not self._is_fitted:
            raise RuntimeError(
                "TaxonFilter debe ser ajustado con `fit()` antes de transformar grafos."
            )

        new_g = graph.clone()
        if "taxon" not in new_g.node_types:
            return new_g

        t_store = new_g["taxon"]
        if t_store.num_nodes == 0:
            return new_g

        node_ids = getattr(t_store, "node_id", None)
        if node_ids is None:
            return new_g

        num_original = len(node_ids)
        keep_mask = [nid in self._selected_taxa for nid in node_ids]

        # Si todos los taxones son retenidos, no hay poda que hacer
        if all(keep_mask):
            return new_g

        keep_indices = [i for i, k in enumerate(keep_mask) if k]
        tensor_mask = torch.tensor(keep_mask, dtype=torch.bool)
        old_to_new = {old_i: new_i for new_i, old_i in enumerate(keep_indices)}

        # Filtrar atributos nodales en taxon
        new_g["taxon"].node_id = [nid for nid, k in zip(node_ids, keep_mask, strict=True) if k]

        for k in list(t_store.keys()):
            if k == "node_id":
                continue
            v = t_store[k]
            if isinstance(v, torch.Tensor) and v.ndim >= 1 and v.shape[0] == num_original:
                new_g["taxon"][k] = v[tensor_mask]

        # Actualizar aristas que involucran 'taxon'
        for edge_type in new_g.edge_types:
            src_t, rel, dst_t = edge_type
            if src_t != "taxon" and dst_t != "taxon":
                continue

            e_store = new_g[edge_type]
            edge_index = getattr(e_store, "edge_index", None)
            if edge_index is None or edge_index.ndim != 2 or edge_index.shape[1] == 0:
                continue

            num_edges = edge_index.shape[1]
            valid_edge_mask = torch.ones(num_edges, dtype=torch.bool, device=edge_index.device)

            if src_t == "taxon":
                # Nodos de origen podados
                src_nodes = edge_index[0]
                valid_src = tensor_mask[src_nodes]
                valid_edge_mask = valid_edge_mask & valid_src

            if dst_t == "taxon":
                # Nodos de destino podados
                dst_nodes = edge_index[1]
                valid_dst = tensor_mask[dst_nodes]
                valid_edge_mask = valid_edge_mask & valid_dst

            filtered_edge_index = edge_index[:, valid_edge_mask]

            # Reasignar punteros nodales
            if filtered_edge_index.shape[1] > 0:
                new_src = filtered_edge_index[0].clone()
                new_dst = filtered_edge_index[1].clone()

                if src_t == "taxon":
                    new_src = torch.tensor(
                        [old_to_new[int(idx.item())] for idx in new_src],
                        dtype=edge_index.dtype,
                        device=edge_index.device,
                    )
                if dst_t == "taxon":
                    new_dst = torch.tensor(
                        [old_to_new[int(idx.item())] for idx in new_dst],
                        dtype=edge_index.dtype,
                        device=edge_index.device,
                    )
                new_g[edge_type].edge_index = torch.stack([new_src, new_dst], dim=0)
            else:
                new_g[edge_type].edge_index = torch.empty(
                    (2, 0), dtype=edge_index.dtype, device=edge_index.device
                )

            # Filtrar atributos de arista asociados
            for k in list(e_store.keys()):
                if k == "edge_index":
                    continue
                attr = e_store[k]
                if isinstance(attr, torch.Tensor) and attr.ndim >= 1 and attr.shape[0] == num_edges:
                    new_g[edge_type][k] = attr[valid_edge_mask]

        return new_g

    def transform(self, graphs: Sequence[HeteroData]) -> tuple[HeteroData, ...]:
        """Aplica `transform_graph` a una secuencia de grafos."""
        return tuple(self.transform_graph(g) for g in graphs)

    def to_dict(self) -> dict[str, Any]:
        """Serializa el estado del filtro a un diccionario compatible con JSON."""
        return {
            "config": {
                "min_prevalence": self._config.min_prevalence,
                "min_abundance": self._config.min_abundance,
                "top_k": self._config.top_k,
            },
            "train_num_graphs": self._train_num_graphs,
            "selected_taxa": sorted(self._selected_taxa),
            "taxon_stats": {nid: dataclasses.asdict(st) for nid, st in self._taxon_stats.items()},
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TaxonFilter:
        """Reconstruye un `TaxonFilter` a partir de un diccionario serializado."""
        cfg_dict = data.get("config", {})
        config = TaxonFilterConfig(
            min_prevalence=float(cfg_dict.get("min_prevalence", 0.1)),
            min_abundance=float(cfg_dict.get("min_abundance", 0.0)),
            top_k=cfg_dict.get("top_k"),
        )
        selected_taxa = frozenset(data.get("selected_taxa", []))
        train_num_graphs = int(data.get("train_num_graphs", 0))

        raw_stats = data.get("taxon_stats", {})
        stats = {
            nid: TaxonStats(
                node_id=nid,
                prevalence=float(s["prevalence"]),
                occurrence_count=int(s["occurrence_count"]),
                mean_abundance=float(s["mean_abundance"]),
                total_abundance=float(s["total_abundance"]),
            )
            for nid, s in raw_stats.items()
        }

        return cls(
            selected_taxa=selected_taxa,
            config=config,
            taxon_stats=stats,
            train_num_graphs=train_num_graphs,
        )


def apply_taxon_filter_to_loaders(
    prepared: PreparedDataLoaders,
    taxon_filter: TaxonFilter,
    *,
    batch_size: int,
    seed: int = 42,
) -> PreparedDataLoaders:
    """Aplica `taxon_filter` a los grafos de `train`, `val` y `test` y rehace los DataLoaders.

    Actualiza los metadatos globales (`GraphMetadata`) reflejando la nueva estructura.
    """
    filtered_graphs = {
        subset: taxon_filter.transform(prepared.graphs[subset])
        for subset in SUBSETS
        if subset in prepared.graphs
    }

    all_deliverable = [g for sub in SUBSETS for g in filtered_graphs.get(sub, ())]
    new_metadata = (
        GraphMetadata.from_graphs(all_deliverable) if all_deliverable else prepared.metadata
    )

    train_graphs = filtered_graphs.get("train", ())
    val_graphs = filtered_graphs.get("val", ())
    test_graphs = filtered_graphs.get("test", ())

    return dataclasses.replace(
        prepared,
        train=DataLoader(
            train_graphs,
            batch_size=batch_size,
            shuffle=bool(train_graphs),
            generator=torch.Generator().manual_seed(seed) if train_graphs else None,
        ),
        val=DataLoader(val_graphs, batch_size=batch_size, shuffle=False),
        test=DataLoader(test_graphs, batch_size=batch_size, shuffle=False),
        metadata=new_metadata,
        graphs={subset: tuple(graphs) for subset, graphs in filtered_graphs.items()},
    )
