"""Entradas de la validación cruzada composicional para D1 y la cohorte sintética (A68, #178).

El barrido de λ (#178) y la evaluación pareada con y sin restricciones (#185) recorren los mismos
folds sobre dos conjuntos: la cohorte oficial de D1 y una cohorte sintética. `CVInputs` reúne
lo que necesita `run_compositional_fold` para cualquiera de los dos, con el plan de folds leído
de un archivo versionado y verificado contra la cohorte (`verify_plan`, #172):

- **D1** (`load_d1_cv_inputs`): grafos entregables de `artifacts/graphs/D1_holofood` con los
  tres AGCC, de la cohorte oficial; corral, dieta y día desde los metadatos de la fuente; plan
  `configs/splits/d1_holofood_cv.json`.
- **Sintético** (`load_synthetic_cv_inputs`): `build_synthetic_cohort(n, first_seed)`. Los
  animales sintéticos no tienen corral: cada animal es su propio grupo y hay un solo estrato de
  dieta. El plan es `configs/splits/synthetic_cohort_cv.json`, generado con `synthetic_cv_plan`.
  Es un dato **sintético**: no describe animales reales.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from torch_geometric.data import HeteroData

from nutrigraphdt.data.cohort import load_cohort
from nutrigraphdt.data.config import load_sources
from nutrigraphdt.graph.builder import add_reverse_edges
from nutrigraphdt.graph.heterodata import build_synthetic_graphs, load_graphs
from nutrigraphdt.models.cross_validation import (
    CVAnimal,
    PenFoldPlan,
    make_pen_folds,
    verify_plan,
)
from nutrigraphdt.models.gnn.base import GraphMetadata
from nutrigraphdt.models.gnn.batching import align_graph_types
from nutrigraphdt.models.gnn.target import add_graph_target

D1_METADATA_SOURCE: Final[str] = "D1_holofood_metadata"
SYNTHETIC_DATASET_ID: Final[str] = "synthetic_cohort"
SYNTHETIC_ANIMALS: Final[int] = 60
SYNTHETIC_FIRST_SEED: Final[int] = 1
SYNTHETIC_STRATUM: Final[str] = "synthetic"
SYNTHETIC_DAY: Final[str] = "synthetic"


@dataclass(frozen=True)
class CVInputs:
    """Grafos preparados, metadatos, plan verificado y contexto por animal de un conjunto."""

    dataset_id: str
    graphs: Mapping[str, HeteroData]
    metadata: GraphMetadata
    plan: PenFoldPlan
    plan_path: Path
    pens: Mapping[str, str]
    diets: Mapping[str, str]
    days: Mapping[str, str]
    cohort: Mapping[str, Any]
    source: Mapping[str, Any] = field(default_factory=dict)
    is_synthetic: bool = False

    @property
    def animals(self) -> list[CVAnimal]:
        return [CVAnimal(s, self.pens[s], self.diets[s], self.days[s]) for s in sorted(self.graphs)]


def load_d1_metadata(path_or_url: str | None) -> dict[str, dict[str, str]]:
    """Filas de `metadata.tsv` de D1 por `sample_id`."""
    if path_or_url is None:
        raise FileNotFoundError(f"La fuente {D1_METADATA_SOURCE} no tiene archivo local.")
    with Path(path_or_url).open(encoding="utf-8", newline="") as handle:
        return {
            row["sample_id"]: row
            for row in csv.DictReader(handle, delimiter="\t")
            if row.get("sample_id")
        }


def prepare_d1_graphs(
    graphs_dir: Path, cohort_ids: frozenset[str]
) -> tuple[dict[str, HeteroData], GraphMetadata, dict[str, int]]:
    """Grafos entregables de la cohorte con los tres AGCC, listos para los folds.

    Devuelve `(grafos por sample_id, metadatos, conteo de aristas por estado de evidencia)`.

    Raises:
        ValueError: si ningún grafo entregable de la cohorte tiene los tres AGCC.
    """
    report = json.loads((graphs_dir / "report.json").read_text(encoding="utf-8"))
    status = report["validation"]["graphs"]
    evidence_counts: dict[str, int] = {}
    prepared: dict[str, HeteroData] = {}
    for graph_id, graph in load_graphs(graphs_dir / "graphs").items():
        if not status.get(graph_id, {}).get("deliverable", False):
            continue
        sample_id = str(graph.sample_id)
        if sample_id not in cohort_ids:
            continue
        for edge_type in graph.edge_types:
            for value in getattr(graph[edge_type], "evidence_status", []) or []:
                evidence_counts[str(value)] = evidence_counts.get(str(value), 0) + 1
        with_target = add_graph_target(add_reverse_edges(graph))
        with_target.graph_id = graph_id
        if not bool(with_target.y_graph_mask.all()):
            continue
        prepared[sample_id] = with_target
    if not prepared:
        raise ValueError("Ningún grafo entregable de la cohorte tiene los tres AGCC.")
    metadata = GraphMetadata.from_graphs(list(prepared.values()))
    align_graph_types(list(prepared.values()), inplace=True)
    return prepared, metadata, evidence_counts


def load_d1_cv_inputs(sources_path: Path, graphs_dir: Path, plan_path: Path) -> CVInputs:
    """Entradas de D1: cohorte oficial, grafos entregables y plan versionado verificado.

    Raises:
        ValueError: si algún animal del plan no tiene grafo o el plan no corresponde a la cohorte.
    """
    sources = load_sources(sources_path)
    cohort = load_cohort(sources)
    rows = load_d1_metadata(sources[D1_METADATA_SOURCE].path_or_url)
    cohort_ids = frozenset(cohort.sample_ids)
    graphs, metadata, evidence_counts = prepare_d1_graphs(graphs_dir, cohort_ids)
    animals = [CVAnimal.from_mapping(rows[s]) for s in sorted(cohort_ids)]
    plan = verify_plan(PenFoldPlan.load(plan_path), animals)
    missing = [s for s in plan.sample_ids if s not in graphs]
    if missing:
        raise ValueError(f"Animales del plan sin grafo entregable con los tres AGCC: {missing}.")
    return CVInputs(
        dataset_id="D1_holofood",
        graphs={s: graphs[s] for s in plan.sample_ids},
        metadata=metadata,
        plan=plan,
        plan_path=plan_path,
        pens={s: rows[s]["pen_code"] for s in plan.sample_ids},
        diets={s: rows[s]["diet_treatment_code"] for s in plan.sample_ids},
        days={s: rows[s]["sampling_day"] for s in plan.sample_ids},
        cohort=cohort.summary(),
        source={"graphs_dir": graphs_dir.as_posix(), "evidence_counts": evidence_counts},
    )


def synthetic_cohort_graphs(
    n_animals: int = SYNTHETIC_ANIMALS, first_seed: int = SYNTHETIC_FIRST_SEED
) -> dict[str, HeteroData]:
    """Grafos de la cohorte sintética por `sample_id`, con inversas, objetivo y tipos alineados."""
    from nutrigraphdt.models.baselines import build_synthetic_cohort

    built = build_synthetic_graphs(build_synthetic_cohort(n_animals, first_seed=first_seed))
    prepared: dict[str, HeteroData] = {}
    for graph_id, graph in built.graphs.items():
        with_target = add_graph_target(add_reverse_edges(graph))
        with_target.graph_id = graph_id
        prepared[str(with_target.sample_id)] = with_target
    align_graph_types(list(prepared.values()), inplace=True)
    return prepared


def synthetic_animals(sample_ids: list[str]) -> list[CVAnimal]:
    """Cada animal sintético es su propio grupo; un solo estrato y un solo «día»."""
    return [CVAnimal(s, s, SYNTHETIC_STRATUM, SYNTHETIC_DAY) for s in sorted(sample_ids)]


def synthetic_cv_plan(
    n_animals: int = SYNTHETIC_ANIMALS, first_seed: int = SYNTHETIC_FIRST_SEED
) -> PenFoldPlan:
    """Plan de folds de la cohorte sintética (k = 5, semillas 0 a 9), el de D-07 sin corrales."""
    sample_ids = [
        f"synthetic:sample:{seed:04d}" for seed in range(first_seed, first_seed + n_animals)
    ]
    return make_pen_folds(
        synthetic_animals(sample_ids),
        dataset_id=SYNTHETIC_DATASET_ID,
        cohort={"n_animals": n_animals, "first_seed": first_seed, "synthetic": True},
    )


def load_synthetic_cv_inputs(plan_path: Path) -> CVInputs:
    """Entradas de la cohorte sintética con el plan versionado verificado.

    Raises:
        ValueError: si el plan no corresponde a la cohorte que describe.
    """
    plan = PenFoldPlan.load(plan_path)
    n_animals = int(plan.cohort["n_animals"])
    first_seed = int(plan.cohort["first_seed"])
    graphs = synthetic_cohort_graphs(n_animals, first_seed)
    animals = synthetic_animals(list(graphs))
    verify_plan(plan, animals)
    return CVInputs(
        dataset_id=SYNTHETIC_DATASET_ID,
        graphs=graphs,
        metadata=GraphMetadata.from_graphs(list(graphs.values())),
        plan=plan,
        plan_path=plan_path,
        pens={a.sample_id: a.pen_code for a in animals},
        diets={a.sample_id: a.diet for a in animals},
        days={a.sample_id: str(a.sampling_day) for a in animals},
        cohort=dict(plan.cohort),
        source={"generator": "build_synthetic_cohort", "n_animals": n_animals},
        is_synthetic=True,
    )


__all__ = [
    "D1_METADATA_SOURCE",
    "SYNTHETIC_ANIMALS",
    "SYNTHETIC_DATASET_ID",
    "SYNTHETIC_FIRST_SEED",
    "CVInputs",
    "load_d1_cv_inputs",
    "load_d1_metadata",
    "load_synthetic_cv_inputs",
    "prepare_d1_graphs",
    "synthetic_animals",
    "synthetic_cohort_graphs",
    "synthetic_cv_plan",
]
