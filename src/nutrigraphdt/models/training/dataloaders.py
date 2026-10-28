"""Preparación de grafos y construcción de DataLoaders por subconjunto (A44-1, #95).

Centraliza la compuerta de validación (`prepare_graphs_for_model`), la adición de aristas inversas
(`add_reverse_edges`) y la asignación del target a nivel de grafo (`add_graph_target`), dividiendo
los grafos en `train`, `val` y `test` según `data.sample_id` con `DatasetSplit.subset_of`.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field

import torch
from torch_geometric.data import HeteroData
from torch_geometric.loader import DataLoader

from nutrigraphdt.data.split import DatasetSplit
from nutrigraphdt.graph.builder import add_reverse_edges
from nutrigraphdt.graph.validation.pipeline import GraphRecords, prepare_graphs_for_model
from nutrigraphdt.graph.validation.report import ValidationReport
from nutrigraphdt.models.gnn.base import GraphMetadata
from nutrigraphdt.models.gnn.batching import align_graph_types
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
    outside_cohort : int
        Número de grafos entregables con algún AGCC medido que quedaron fuera de los DataLoaders
        por no pertenecer a la cohorte (#138). `with_any_scfa` y `with_all_scfa` ya los
        descuentan. Es 0 si no se pasó una cohorte.
    """

    received: int
    deliverable: int
    with_any_scfa: int
    with_all_scfa: int
    outside_cohort: int = 0


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
        Metadatos construidos a partir de todos los grafos entregables.
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


def prepare_training_graphs(
    records: GraphRecords | None,
    graphs: Mapping[str, HeteroData] | Sequence[HeteroData],
    split: DatasetSplit,
    *,
    validated: bool = False,
    batch_size: int = 16,
    seed: int | None = 42,
    generator: torch.Generator | None = None,
    targets: Sequence[str] = DEFAULT_SCFA_TARGETS,
    cohort: Collection[str] | None = None,
) -> PreparedDataLoaders:
    """Prepara grafos y construye DataLoaders para entrenamiento, validación y prueba.

    Aplica en orden canónico (§3 de `docs/models/gnn-architecture.md`):
    1. Compuerta de validación: si se proveen registros (`GraphRecords`), ejecuta
       `prepare_graphs_for_model` y conserva únicamente los grafos entregables.
       Si `records` es None, se exige `validated=True` de forma explícita.
    2. Construcción de relaciones inversas (`add_reverse_edges`) sobre cada grafo entregable.
    3. Adición del target a nivel de grafo (`add_graph_target`).
    4. Asignación y agrupación de cada grafo por `data.sample_id` con `DatasetSplit.subset_of`.
       Si el `sample_id` de un grafo entregable no está en la partición, lanza un `ValueError`
       explícito.
    5. Exclusión de grafos sin ningún AGCC medido (`y_graph_mask` todo en False) de los DataLoaders,
       y de los que no pertenecen a `cohort` cuando se indica (#138).
    6. Construcción de `GraphMetadata.from_graphs` con la unión de tipos de arista de todos los
       grafos entregables (incluidas las aristas inversas), y `align_graph_types` para que cada
       grafo tenga todos esos tipos (vacíos si no los tiene) y los lotes no mezclen aristas.
    7. Creación de los tres `DataLoader`: `train` barajado con un `torch.Generator` sembrado
       (o el suministrado); `val` y `test` sin barajar.

    Parameters
    ----------
    records : GraphRecords | None
        Registros del dataset para validar tensores y contratos con `prepare_graphs_for_model`.
        Obligatorio a menos que `validated=True`.
    graphs : Mapping[str, HeteroData] | Sequence[HeteroData]
        Conjunto de grafos `HeteroData` indexados por `graph_id` o como secuencia de grafos
        con atributo `graph_id`.
    split : DatasetSplit
        Partición inmutable con subconjuntos `train`, `val` y `test`.
    validated : bool, default=False
        Si es True, omite la compuerta de validación asumiendo que los grafos ya fueron
        auditados y validados previamente (por ejemplo, cargados con `load_graphs`).
    batch_size : int, default=16
        Tamaño de lote para los DataLoaders (debe ser >= 1).
    seed : int | None, default=42
        Semilla para el generador de barajado en `train`. Se ignora si se pasa `generator`.
    generator : torch.Generator | None, optional
        Generador de PyTorch para el barajado de `train`.
    targets : Sequence[str], default=DEFAULT_SCFA_TARGETS
        Nombres canónicos de los AGCC objetivo.
    cohort : Collection[str] | None, optional
        `sample_id` de la cohorte supervisada (`nutrigraphdt.data.cohort`). Un grafo fuera de
        ella sigue contando como recibido y entregable, pero no entra a ningún DataLoader.
        `None` no filtra.

    Returns
    -------
    PreparedDataLoaders
        Contenedor con `train`, `val`, `test`, `metadata`, `summary` y `report`.

    Raises
    ------
    ValueError
        Si `batch_size < 1`.
        Si `records` es None y `validated=False`.
        Si se detectan identificadores `graph_id` duplicados o claves incongruentes.
        Si en una secuencia algún grafo no define el atributo `graph_id`.
        Si algún grafo entregable no define el atributo `sample_id` o este no pertenece
        a la partición.
        Si no hay ningún grafo entregable para construir los DataLoaders.
    """
    if batch_size < 1:
        raise ValueError(f"batch_size debe ser >= 1; recibido: {batch_size}.")

    if not isinstance(split, DatasetSplit):
        raise ValueError(
            f"'split' debe ser una instancia de DatasetSplit; recibido: {type(split)}."
        )

    if records is None and not validated:
        raise ValueError(
            "records es obligatorio para ejecutar la compuerta de validación "
            "prepare_graphs_for_model. Si los grafos ya fueron validados previamente "
            "al construirlos o guardarlos, indique explícitamente validated=True."
        )

    # 1. Normalizar entrada de grafos e indexar por graph_id sin mutar los objetos originales
    graphs_dict: dict[str, HeteroData] = {}
    if isinstance(graphs, Mapping):
        for key, g in graphs.items():
            gid = getattr(g, "graph_id", None)
            if gid is not None and str(gid) != str(key):
                raise ValueError(
                    f"La clave del mapeo {key!r} no coincide con el graph_id del grafo {gid!r}."
                )
            graph_id = str(key)
            if graph_id in graphs_dict:
                raise ValueError(f"Se encontró un graph_id duplicado: {graph_id!r}.")
            graphs_dict[graph_id] = g
    else:
        for i, g in enumerate(graphs):
            gid = getattr(g, "graph_id", None)
            if gid is None:
                raise ValueError(
                    f"El grafo en el índice {i} no define el atributo obligatorio 'graph_id'."
                )
            graph_id = str(gid)
            if graph_id in graphs_dict:
                raise ValueError(f"Se encontró un graph_id duplicado: {graph_id!r}.")
            graphs_dict[graph_id] = g

    # 2. Paso 1 del orden canónico: Compuerta de validación prepare_graphs_for_model
    report: ValidationReport | None = None
    if records is not None:
        delivered_dict, report = prepare_graphs_for_model(records, graphs_dict)
    else:
        delivered_dict = graphs_dict

    # Conteos de grafos recibidos asignables a cada subconjunto
    received_count: dict[str, int] = {
        "train": 0,
        "val": 0,
        "test": 0,
    }
    for g in graphs_dict.values():
        sid = getattr(g, "sample_id", None)
        if sid is not None:
            sub = split.subset_of(str(sid))
            if sub in received_count:
                received_count[sub] += 1

    # 3. Pasos 2, 3 y 4 del orden canónico sobre grafos entregables
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
    outside_cohort_count: dict[str, int] = {
        "train": 0,
        "val": 0,
        "test": 0,
    }
    cohort_ids = None if cohort is None else frozenset(str(sid) for sid in cohort)

    for gid, g in delivered_dict.items():
        # Paso 2: Relaciones inversas (add_reverse_edges clona y no muta el original)
        g_rev = add_reverse_edges(g)

        # Paso 3: Target a nivel de grafo (preservando graph_id de la clave)
        g_target = add_graph_target(g_rev, targets=targets)
        g_target.graph_id = gid

        # Paso 4: Asignación por sample_id
        sample_id = getattr(g, "sample_id", None)
        if sample_id is None:
            raise ValueError(f"El grafo {gid!r} no define el atributo obligatorio 'sample_id'.")
        g_target.sample_id = sample_id

        subset = split.subset_of(str(sample_id))
        if subset is None:
            raise ValueError(
                f"El sample_id {sample_id!r} del grafo {gid!r} no está en la partición "
                "(train, val, test)."
            )

        deliverable_by_subset[subset].append(g_target)

        # Paso 5: Filtrado de instancias con/sin target medido
        mask = g_target.y_graph_mask
        has_any = bool(mask.any().item())
        has_all = bool(mask.all().item())
        if has_any and cohort_ids is not None and str(sample_id) not in cohort_ids:
            outside_cohort_count[subset] += 1
            continue

        if has_any:
            with_any_by_subset[subset].append(g_target)
        if has_all:
            with_all_count[subset] += 1

    # 4. Resumen por subconjunto
    summary: dict[str, SubsetSummary] = {}
    for subset in ("train", "val", "test"):
        summary[subset] = SubsetSummary(
            received=received_count[subset],
            deliverable=len(deliverable_by_subset[subset]),
            with_any_scfa=len(with_any_by_subset[subset]),
            with_all_scfa=with_all_count[subset],
            outside_cohort=outside_cohort_count[subset],
        )

    # 6. Construir GraphMetadata.from_graphs con todos los grafos entregables
    all_deliverable = [
        g for subset in ("train", "val", "test") for g in deliverable_by_subset[subset]
    ]
    if not all_deliverable:
        raise ValueError("No hay ningún grafo entregable para preparar los DataLoaders.")

    metadata = GraphMetadata.from_graphs(all_deliverable)

    # 6b. Completar cada grafo con los tipos de la unión, vacíos (#119): PyG exige las mismas
    # claves en todos los grafos de un lote; si no, reasigna aristas a otro grafo.
    align_graph_types(all_deliverable, inplace=True)

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


__all__ = [
    "PreparedDataLoaders",
    "SubsetSummary",
    "prepare_training_graphs",
]
