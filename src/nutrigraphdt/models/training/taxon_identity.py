"""Identidad de los taxones por linaje, multiplicada por la abundancia (#266, decisión de #239).

Con `x_t = [a_t]`, un encoder lineal y la lectura por media, el bloque `taxon` de la lectura es
constante entre animales: las abundancias relativas suman 1 sobre el mismo conjunto de taxones
(`docs/research/check_d1_taxon_readout.py`). Investigación decidió combinar la identidad con la
abundancia **antes** de la lectura: `x_t = a_t · onehot(grupo_t)`, con la familia del taxón o, si no
la tiene, el rango más profundo sobre género que alcance. Así, la media por grafo es el perfil de
abundancia por familia, distinto en cada animal, y cubre también a los géneros sin enlace y a los
residuales.

El vocabulario se ajusta **solo con los grafos de entrenamiento** del fold, con el criterio de
`TaxonFilterConfig` (#160): prevalencia mínima y un máximo de grupos, ordenados por prevalencia y
abundancia total. Un grupo fuera del vocabulario va a la columna `OTHER_GROUP`, de modo que la
suma por grafo se conserva y un grupo nuevo no rompe la evaluación.
"""

from __future__ import annotations

import copy
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from typing import Any, Final

import torch
from torch_geometric.data import HeteroData

from nutrigraphdt.data.taxonomy import lineage_group
from nutrigraphdt.models.gnn.base import GraphMetadata

TAXON: Final = "taxon"
FUNCTION: Final = "function"
OTHER_GROUP: Final = "otras"
"""Columna de los grupos fuera del vocabulario (K5 y K7 de la decisión de #239)."""


@dataclass(frozen=True)
class TaxonIdentityConfig:
    """Criterio del vocabulario de linaje, con el mismo significado que `TaxonFilterConfig`.

    `top_k = 30` viene de la decisión de #239: 30 familias reúnen el 98,9 % de las lecturas que
    llegan a familia, y limita los parámetros nuevos frente a unos 45 animales por fold (K3).
    `min_prevalence` es el valor por omisión de `TaxonFilterConfig`. Ninguno es un dato científico.
    """

    min_prevalence: float = 0.1
    min_abundance: float = 0.0
    top_k: int = 30
    profile_block: bool = False
    """Agrega el perfil por grupo, estandarizado con el train, como `graph_features` (#268).

    Tras estandarizar por nodo y promediar 876 nodos, el perfil llega a la lectura unas 40 veces
    más chico que el diseño. Este bloque entrega la misma información con desviación 1 entre
    animales, sin agrandar los mensajes de los taxones."""

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_prevalence <= 1.0:
            raise ValueError(f"min_prevalence debe estar en [0, 1]: {self.min_prevalence}.")
        if self.min_abundance < 0.0:
            raise ValueError(f"min_abundance no puede ser negativa: {self.min_abundance}.")
        if self.top_k <= 0:
            raise ValueError(f"top_k debe ser positivo: {self.top_k}.")


def taxon_groups(graph: HeteroData) -> list[str]:
    """Grupo de linaje de cada nodo `taxon`, en el orden de `x`."""
    store = graph[TAXON]
    return [
        lineage_group(str(attributes.get("taxonomy_id") or node_id)) or OTHER_GROUP
        for attributes, node_id in zip(store.raw_attributes, store.node_id, strict=True)
    ]


def _abundances(graph: HeteroData) -> torch.Tensor:
    x = graph[TAXON].x
    if x.dim() != 2 or x.size(1) != 1:
        raise ValueError(
            f"La identidad por linaje espera una columna de abundancia; x tiene {list(x.shape)}."
        )
    abundance: torch.Tensor = x[:, 0]
    return abundance


def group_profile(graph: HeteroData) -> dict[str, float]:
    """Abundancia total de cada grupo de linaje en un grafo."""
    totals: defaultdict[str, float] = defaultdict(float)
    for group, value in zip(taxon_groups(graph), _abundances(graph).tolist(), strict=True):
        totals[group] += value
    return dict(totals)


class TaxonLineageEncoder:
    """Codifica `x_t = a_t · onehot(grupo_t)` con un vocabulario ajustado en entrenamiento."""

    def __init__(
        self,
        vocabulary: Sequence[str],
        config: TaxonIdentityConfig | None = None,
        profile_mean: Sequence[float] = (),
        profile_std: Sequence[float] = (),
    ):
        if OTHER_GROUP in vocabulary:
            raise ValueError(f"{OTHER_GROUP!r} es la columna reservada, no un grupo.")
        self.vocabulary: tuple[str, ...] = tuple(vocabulary)
        self.config = config or TaxonIdentityConfig()
        self._column = {group: index for index, group in enumerate(self.vocabulary)}
        self.profile_mean: tuple[float, ...] = tuple(profile_mean)
        self.profile_std: tuple[float, ...] = tuple(profile_std)
        if self.config.profile_block and len(self.profile_mean) != len(self.columns):
            raise ValueError("profile_block necesita la media y la desviación de cada columna.")

    @property
    def columns(self) -> tuple[str, ...]:
        """Grupos del vocabulario y la columna final `OTHER_GROUP`."""
        return (*self.vocabulary, OTHER_GROUP)

    @classmethod
    def fit(
        cls, train_graphs: Sequence[HeteroData], config: TaxonIdentityConfig | None = None
    ) -> TaxonLineageEncoder:
        """Elige el vocabulario solo con `train_graphs`.

        Raises:
            ValueError: si no hay grafos de entrenamiento.
        """
        if not train_graphs:
            raise ValueError("El vocabulario de linaje necesita grafos de entrenamiento.")
        criteria = config or TaxonIdentityConfig()
        present: Counter[str] = Counter()
        totals: defaultdict[str, float] = defaultdict(float)
        for graph in train_graphs:
            for group, value in group_profile(graph).items():
                totals[group] += value
                if value > criteria.min_abundance:
                    present[group] += 1
        total_graphs = len(train_graphs)
        kept = [
            group
            for group in totals
            if group != OTHER_GROUP
            and present[group] > 0
            and present[group] / total_graphs >= criteria.min_prevalence
        ]
        kept.sort(key=lambda group: (-present[group], -totals[group], group))
        encoder = cls(sorted(kept[: criteria.top_k]), replace(criteria, profile_block=False))
        if not criteria.profile_block:
            return encoder
        profiles = torch.stack([encoder.profile(graph) for graph in train_graphs])
        std = profiles.std(dim=0)
        std = torch.where(std > 0, std, torch.ones_like(std))
        return cls(encoder.vocabulary, criteria, profiles.mean(dim=0).tolist(), std.tolist())

    def _index(self, graph: HeteroData) -> torch.Tensor:
        fallback = len(self.vocabulary)
        return torch.tensor(
            [self._column.get(group, fallback) for group in taxon_groups(graph)], dtype=torch.long
        )

    def profile(self, graph: HeteroData) -> torch.Tensor:
        """Abundancia total de cada columna del vocabulario en un grafo."""
        abundance = _abundances(graph)
        totals = torch.zeros(len(self.columns), dtype=abundance.dtype)
        return totals.index_add_(0, self._index(graph), abundance)

    def transform(self, graphs: Sequence[HeteroData]) -> list[HeteroData]:
        """Copias de `graphs` con `x` y `missing_mask` de `taxon` ya codificados."""
        result: list[HeteroData] = []
        width = len(self.columns)
        for graph in graphs:
            abundance = _abundances(graph)
            index = self._index(graph)
            rows = torch.arange(abundance.size(0))
            encoded = torch.zeros((abundance.size(0), width), dtype=abundance.dtype)
            encoded[rows, index] = abundance
            mask = torch.zeros((abundance.size(0), width), dtype=torch.bool)
            mask[rows, index] = graph[TAXON].missing_mask[:, 0]
            output = copy.copy(graph)
            output[TAXON].x = encoded
            output[TAXON].missing_mask = mask
            if self.config.profile_block:
                mean = torch.tensor(self.profile_mean, dtype=abundance.dtype)
                std = torch.tensor(self.profile_std, dtype=abundance.dtype)
                output.graph_features = ((self.profile(graph) - mean) / std).unsqueeze(0)
            result.append(output)
        return result

    def adapt_metadata(self, metadata: GraphMetadata) -> GraphMetadata:
        """`metadata` con las columnas de `taxon` de este vocabulario."""
        return GraphMetadata(
            {**metadata.node_channels, TAXON: len(self.columns)},
            metadata.edge_types,
            len(self.columns) if self.config.profile_block else 0,
        )

    def to_dict(self) -> dict[str, Any]:
        """Forma de `run.json`: el vocabulario y el criterio con que se eligió."""
        return {
            "vocabulary": list(self.vocabulary),
            "config": asdict(self.config),
            "profile_mean": list(self.profile_mean),
            "profile_std": list(self.profile_std),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TaxonLineageEncoder:
        """Reconstruye el codificador desde `to_dict`."""
        return cls(
            data["vocabulary"],
            TaxonIdentityConfig(**data["config"]),
            data.get("profile_mean", ()),
            data.get("profile_std", ()),
        )


def without_functional_structure(graph: HeteroData) -> HeteroData:
    """Copia de `graph` sin los nodos `function` ni sus aristas (brazos de control de #266)."""
    output = copy.copy(graph)
    for edge_type in list(output.edge_types):
        if FUNCTION in (edge_type[0], edge_type[2]):
            del output[edge_type]
    if FUNCTION in output.node_types:
        del output[FUNCTION]
    return output


__all__ = [
    "OTHER_GROUP",
    "TaxonIdentityConfig",
    "TaxonLineageEncoder",
    "group_profile",
    "taxon_groups",
    "without_functional_structure",
]
