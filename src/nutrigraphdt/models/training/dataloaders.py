"""Preparación de grafos y construcción de DataLoaders por subconjunto (A44-1, #95).

Centraliza la compuerta de validación (`prepare_graphs_for_model`), la adición de aristas inversas
(`add_reverse_edges`) y la asignación del target a nivel de grafo (`add_graph_target`), dividiendo
los grafos en `train`, `val` y `test` según `data.sample_id` con `DatasetSplit.subset_of`.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

import torch
from torch_geometric.data import HeteroData
from torch_geometric.loader import DataLoader

from nutrigraphdt.data.split import DatasetSplit
from nutrigraphdt.graph.builder import add_reverse_edges
from nutrigraphdt.graph.validation.pipeline import GraphRecords, prepare_graphs_for_model
from nutrigraphdt.graph.validation.report import ValidationReport
from nutrigraphdt.models.gnn.base import GraphMetadata
from nutrigraphdt.models.gnn.target import add_graph_target
from nutrigraphdt.models.metrics import DEFAULT_SCFA_TARGETS


@dataclass(frozen=True)
class SubsetSummary:
    """Resumen de conteos de grafos para un subconjunto (`train`, `val` o `test`).

    Attributes
    ----------
    received : int
        Número de grafos recibidos para este subconjunto.
    deliverable : int
        Número de grafos entregables tras la compuerta `prepare_graphs_for_model`.
    with_any_scfa : int
        Número de grafos entregables con al menos un AGCC medido (`y_graph_mask` no todo en False).
    with_all_scfa : int
        Número de grafos entregables con los tres AGCC medidos (`y_graph_mask` todo en True).
    """

    received: int
    deliverable: int
    with_any_scfa: int
    with_all_scfa: int

    @property
    def recibidos(self) -> int:
        return self.received

    @property
    def entregables(self) -> int:
        return self.deliverable

    @property
    def con_algun_agcc(self) -> int:
        return self.with_any_scfa

    @property
    def con_los_tres_agcc(self) -> int:
        return self.with_all_scfa

    def to_dict(self) -> dict[str, int]:
        """Devuelve un diccionario con las métricas en inglés y español."""
        return {
            "received": self.received,
            "deliverable": self.deliverable,
            "with_any_scfa": self.with_any_scfa,
            "with_all_scfa": self.with_all_scfa,
            "recibidos": self.received,
            "entregables": self.deliverable,
            "con_algun_agcc": self.with_any_scfa,
            "con_los_tres_agcc": self.with_all_scfa,
        }

    def __getitem__(self, key: str) -> int:
        mapping = self.to_dict()
        if key in mapping:
            return mapping[key]
        raise KeyError(
            f"Clave de resumen no válida: {key!r}. "
            "Use 'received'/'recibidos', 'deliverable'/'entregables', "
            "'with_any_scfa'/'con_algun_agcc' o 'with_all_scfa'/'con_los_tres_agcc'."
        )


@dataclass(frozen=True)
class PreparedDataLoaders:
    """Contenedor de los tres DataLoaders (`train`, `val`, `test`), metadatos y resumen.

    Attributes
    ----------
    train : DataLoader
        DataLoader de entrenamiento (barajado con generador sembrado si se configuró).
    val : DataLoader
        DataLoader de validación (sin barajar).
    test : DataLoader
        DataLoader de prueba (sin barajar).
    metadata : GraphMetadata
        Metadatos construidos a partir de todos los grafos entregables (unión de tipos de arista).
    summary : Mapping[str, SubsetSummary]
        Resumen de conteos por subconjunto ('train', 'val', 'test').
    graphs : Mapping[str, tuple[HeteroData, ...]]
        Tupla de grafos incluidos en cada DataLoader.
    report : ValidationReport | None
        Reporte de validación devuelto por `prepare_graphs_for_model` si se pasaron registros.
    """

    train: DataLoader
    val: DataLoader
    test: DataLoader
    metadata: GraphMetadata
    summary: Mapping[str, SubsetSummary]
    graphs: Mapping[str, tuple[HeteroData, ...]] = field(default_factory=dict)
    report: ValidationReport | None = None

    def __iter__(self) -> Iterator[DataLoader]:
        yield self.train
        yield self.val
        yield self.test

    def __getitem__(self, key: str) -> DataLoader:
        if key == "train":
            return self.train
        if key == "val":
            return self.val
        if key == "test":
            return self.test
        raise KeyError(f"Subconjunto no válido: {key!r}. Use 'train', 'val' o 'test'.")

    @property
    def loaders(self) -> dict[str, DataLoader]:
        return {"train": self.train, "val": self.val, "test": self.test}


def _parse_prepare_args(
    *args: Any,
    records: GraphRecords | None = None,
    graphs: Mapping[str, HeteroData] | Sequence[HeteroData] | None = None,
    split: DatasetSplit | None = None,
) -> tuple[GraphRecords | None, Mapping[str, HeteroData] | Sequence[HeteroData], DatasetSplit]:
    """Interpreta argumentos posicionales o por nombre para `prepare_training_graphs`."""
    if len(args) == 3:
        r_arg, g_arg, s_arg = args
        if not isinstance(s_arg, DatasetSplit):
            raise ValueError(
                f"El tercer argumento debe ser un DatasetSplit; recibido: {type(s_arg)}."
            )
        return (
            cast(GraphRecords, r_arg),
            cast(Mapping[str, HeteroData] | Sequence[HeteroData], g_arg),
            s_arg,
        )

    if len(args) == 2:
        g_arg, s_arg = args
        if not isinstance(s_arg, DatasetSplit):
            raise ValueError(
                f"El segundo argumento posicional debe ser un DatasetSplit; "
                f"recibido: {type(s_arg)}."
            )
        return records, cast(Mapping[str, HeteroData] | Sequence[HeteroData], g_arg), s_arg

    if len(args) == 1:
        g_arg = args[0]
        if split is None:
            raise ValueError(
                "Se debe proporcionar 'split' cuando solo se pasa 'graphs' por posición."
            )
        return records, cast(Mapping[str, HeteroData] | Sequence[HeteroData], g_arg), split

    if len(args) == 0:
        if graphs is None or split is None:
            raise ValueError("Se deben proporcionar 'graphs' y 'split'.")
        return records, graphs, split

    raise ValueError(f"Número inesperado de argumentos posicionales: {len(args)}.")


def prepare_training_graphs(
    *args: Any,
    records: GraphRecords | None = None,
    graphs: Mapping[str, HeteroData] | Sequence[HeteroData] | None = None,
    split: DatasetSplit | None = None,
    batch_size: int = 16,
    seed: int | None = 42,
    generator: torch.Generator | None = None,
    targets: Sequence[str] = DEFAULT_SCFA_TARGETS,
) -> PreparedDataLoaders:
    """Prepara grafos y construye DataLoaders para entrenamiento, validación y prueba.

    Aplica en orden riguroso:
    1. Asignación de cada grafo por `data.sample_id` con `DatasetSplit.subset_of`. Si el
       `sample_id` no está en la partición, lanza un `ValueError` explícito.
    2. Compuerta de validación: si se proveen registros (`GraphRecords`), ejecuta
       `prepare_graphs_for_model` y conserva solo los grafos entregables.
    3. Construcción de relaciones inversas (`add_reverse_edges`) sobre cada grafo entregable.
    4. Adición del target a nivel de grafo (`add_graph_target`).
    5. Exclusión de grafos sin ningún AGCC medido (`y_graph_mask` todo en False) de los DataLoaders.
    6. Construcción de `GraphMetadata.from_graphs` con la unión de tipos de arista de todos los
       grafos entregables (incluidas las aristas inversas).
    7. Creación de los tres `DataLoader`: `train` barajado con un `torch.Generator` sembrado
       (o el suministrado); `val` y `test` sin barajar.

    Parameters
    ----------
    *args : Any
        Puede llamarse como `prepare_training_graphs(records, graphs, split)` o
        `prepare_training_graphs(graphs, split)`.
    records : GraphRecords | None, optional
        Registros del dataset para validar tensores y registros con `prepare_graphs_for_model`.
    graphs : Mapping[str, HeteroData] | Sequence[HeteroData] | None, optional
        Conjunto de grafos `HeteroData`.
    split : DatasetSplit | None, optional
        Partición inmutable con subconjuntos `train`, `val` y `test`.
    batch_size : int, default=16
        Tamaño de lote para los DataLoaders (debe ser >= 1).
    seed : int | None, default=42
        Semilla para el generador de barajado en `train`. Se ignora si se pasa `generator`.
    generator : torch.Generator | None, optional
        Generador de PyTorch para el barajado de `train`.
    targets : Sequence[str], default=DEFAULT_SCFA_TARGETS
        Nombres canónicos de los AGCC objetivo.

    Returns
    -------
    PreparedDataLoaders
        Contenedor con `train`, `val`, `test`, `metadata`, `summary` y `report`.

    Raises
    ------
    ValueError
        Si algún grafo no tiene `sample_id` o su `sample_id` no pertenece a la partición.
        Si `batch_size < 1`.
        Si no hay ningún grafo entregable para construir los metadatos y DataLoaders.
    """
    if batch_size < 1:
        raise ValueError(f"batch_size debe ser >= 1; recibido: {batch_size}.")

    input_records, input_graphs, input_split = _parse_prepare_args(
        *args, records=records, graphs=graphs, split=split
    )

    # 1. Normalizar entrada de grafos e indexar por graph_id
    if isinstance(input_graphs, Mapping):
        graphs_dict: dict[str, HeteroData] = {}
        for key, g in input_graphs.items():
            graph_id = str(getattr(g, "graph_id", key) or key)
            if getattr(g, "graph_id", None) is None:
                g.graph_id = graph_id
            graphs_dict[graph_id] = g
    else:
        graphs_dict = {}
        for i, g in enumerate(input_graphs):
            graph_id = str(getattr(g, "graph_id", None) or f"graph_{i:04d}")
            if getattr(g, "graph_id", None) is None:
                g.graph_id = graph_id
            graphs_dict[graph_id] = g

    # 2. Asignar cada grafo a su subconjunto por data.sample_id
    received_by_subset: dict[str, list[HeteroData]] = {
        "train": [],
        "val": [],
        "test": [],
    }

    for graph_id, data in graphs_dict.items():
        sample_id = getattr(data, "sample_id", None)
        if sample_id is None:
            raise ValueError(
                f"El grafo {graph_id!r} no define el atributo obligatorio 'sample_id'."
            )
        subset = input_split.subset_of(str(sample_id))
        if subset is None:
            raise ValueError(
                f"El sample_id {sample_id!r} del grafo {graph_id!r} no está en la partición "
                "(train, val, test)."
            )
        received_by_subset[subset].append(data)

    # 3. Aplicar la compuerta de validación prepare_graphs_for_model
    report: ValidationReport | None = None
    if input_records is not None:
        delivered_dict, report = prepare_graphs_for_model(input_records, graphs_dict)
    else:
        delivered_dict = graphs_dict

    # 4. Procesar grafos entregables: add_reverse_edges y add_graph_target
    deliverable_by_subset: dict[str, list[HeteroData]] = {
        "train": [],
        "val": [],
        "test": [],
    }
    with_any_by_subset: dict[str, list[HeteroData]] = {
        "train": [],
        "val": [],
        "test": [],
    }
    with_all_count: dict[str, int] = {
        "train": 0,
        "val": 0,
        "test": 0,
    }

    for subset in ("train", "val", "test"):
        for g in received_by_subset[subset]:
            gid = str(g.graph_id)
            if gid not in delivered_dict:
                continue

            # Clonar y agregar relaciones inversas
            g_rev = add_reverse_edges(g)
            # Agregar el target a nivel de grafo
            g_target = add_graph_target(g_rev, targets=targets)

            deliverable_by_subset[subset].append(g_target)

            mask = g_target.y_graph_mask
            has_any = bool(mask.any().item())
            has_all = bool(mask.all().item())

            if has_any:
                with_any_by_subset[subset].append(g_target)
            if has_all:
                with_all_count[subset] += 1

    # 5. Resumen por subconjunto
    summary: dict[str, SubsetSummary] = {}
    for subset in ("train", "val", "test"):
        summary[subset] = SubsetSummary(
            received=len(received_by_subset[subset]),
            deliverable=len(deliverable_by_subset[subset]),
            with_any_scfa=len(with_any_by_subset[subset]),
            with_all_scfa=with_all_count[subset],
        )

    # 6. Construir GraphMetadata.from_graphs con todos los grafos entregables
    all_deliverable = [
        g for subset in ("train", "val", "test") for g in deliverable_by_subset[subset]
    ]
    if not all_deliverable:
        raise ValueError("No hay ningún grafo entregable para preparar los DataLoaders.")

    metadata = GraphMetadata.from_graphs(all_deliverable)

    # 7. Crear DataLoaders: train barajado con torch.Generator sembrado, val y test sin barajar
    if generator is None and seed is not None:
        train_generator: torch.Generator | None = torch.Generator().manual_seed(seed)
    else:
        train_generator = generator

    shuffle_train = bool(with_any_by_subset["train"])
    train_loader = DataLoader(
        with_any_by_subset["train"],
        batch_size=batch_size,
        shuffle=shuffle_train,
        generator=train_generator if shuffle_train else None,
    )
    val_loader = DataLoader(
        with_any_by_subset["val"],
        batch_size=batch_size,
        shuffle=False,
    )
    test_loader = DataLoader(
        with_any_by_subset["test"],
        batch_size=batch_size,
        shuffle=False,
    )

    final_graphs: dict[str, tuple[HeteroData, ...]] = {
        "train": tuple(with_any_by_subset["train"]),
        "val": tuple(with_any_by_subset["val"]),
        "test": tuple(with_any_by_subset["test"]),
    }

    return PreparedDataLoaders(
        train=train_loader,
        val=val_loader,
        test=test_loader,
        metadata=metadata,
        summary=summary,
        graphs=final_graphs,
        report=report,
    )
