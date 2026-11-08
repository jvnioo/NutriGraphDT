"""Explicación fuera de fold: cada animal con el modelo del fold en que estuvo en test (C-05; #241).

Aplica la decisión C-05 de la respuesta de Investigación a la revisión A55 (#158):

1. Cada animal se explica con el modelo del fold en que estuvo en **test**, en cada semilla del
   plan. Nunca con uno que lo tuvo en `train` ni en `inner_val` (que decide la detención
   temprana): se estaría explicando memorización.
2. El grafo se escala con el `FeatureScaler` guardado en esa corrida (protocolo §1.3).
3. Se informan dos estabilidades separadas: entre semillas del explicador con el modelo fijo
   (C-07, `explain_across_seeds`) y entre semillas del plan, donde cambian la partición y el
   entrenamiento. La segunda compara el top-k de la primera semilla del explicador en cada
   modelo, para que solo cambie el modelo.
4. Un fold fallido (sin corrida guardada) no se reemplaza: el animal queda con menos
   explicaciones y `OutOfFoldPlan.missing` dice en qué semillas.

La agregación de explicaciones entre modelos queda para una versión menor del contrato.

Las corridas son las de `save_compositional_run` (#180): `runs_dir/<run_id>/run.json` con los
animales de cada subconjunto y `checkpoint.pt`.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from torch_geometric.data import HeteroData

from nutrigraphdt.explainability.contract import Explanation, RunRef, SplitRef
from nutrigraphdt.explainability.criteria import (
    StabilityReport,
    explain_across_seeds,
    importance_elements,
    nogueira_ci,
    nogueira_phi,
    top_k_selection,
)
from nutrigraphdt.models.gnn.base import GraphMetadata, SCFAGraphModel
from nutrigraphdt.models.training.compositional_tracking import (
    LoadedCompositionalRun,
    graph_metadata_matches,
    load_compositional_run,
)
from nutrigraphdt.models.training.tracking import CHECKPOINT_FILE, RUN_FILE

ExplainFn = Callable[[SCFAGraphModel, HeteroData, RunRef, str, int], Explanation]
"""`(modelo, grafo escalado, corrida, salida, semilla del explicador) -> explicación`."""


class OutOfFoldError(ValueError):
    """Las corridas no permiten elegir un único modelo fuera de fold por animal y semilla."""


@dataclass(frozen=True)
class FoldRun:
    """Lo que `run.json` dice de una corrida por fold, sin cargar el modelo."""

    run_dir: Path
    run_id: str
    variant: str
    edges_arm: str
    dataset_id: str
    seed: int
    fold: int
    train: frozenset[str]
    inner_val: frozenset[str]
    test: frozenset[str]

    @classmethod
    def read(cls, run_dir: str | Path) -> FoldRun:
        directory = Path(run_dir)
        info = json.loads((directory / RUN_FILE).read_text(encoding="utf-8"))
        ids = info["sample_ids"]
        return cls(
            run_dir=directory,
            run_id=str(info["run_id"]),
            variant=str(info["variant"]),
            edges_arm=str(info["edges_arm"]),
            dataset_id=str(info["dataset_id"]),
            seed=int(info["seed"]),
            fold=int(info["fold"]),
            train=frozenset(ids["train"]),
            inner_val=frozenset(ids["inner_val"]),
            test=frozenset(ids["test"]),
        )

    def saw(self, sample_id: str) -> bool:
        """`True` si el animal participó en el entrenamiento (train o val interno)."""
        return sample_id in self.train or sample_id in self.inner_val


def index_runs(
    runs_dir: str | Path, *, variant: str, edges_arm: str | None = None
) -> list[FoldRun]:
    """Corridas de `runs_dir` de una variante (y brazo), con `run.json` y checkpoint.

    Una corrida sin `checkpoint.pt` no se puede explicar y no se indexa: cuenta como fold
    fallido.
    """
    runs = []
    for run_json in sorted(Path(runs_dir).glob(f"*/{RUN_FILE}")):
        if not (run_json.parent / CHECKPOINT_FILE).exists():
            continue
        run = FoldRun.read(run_json.parent)
        if run.variant == variant and (edges_arm is None or run.edges_arm == edges_arm):
            runs.append(run)
    return runs


@dataclass(frozen=True)
class OutOfFoldPlan:
    """Corrida que explica a cada animal en cada semilla del plan."""

    seeds: tuple[int, ...]
    assignments: Mapping[str, Mapping[int, FoldRun]]
    missing: Mapping[str, tuple[int, ...]]

    def explanation_counts(self) -> dict[str, int]:
        """Semillas del plan con modelo fuera de fold, por animal."""
        return {sample_id: len(runs) for sample_id, runs in self.assignments.items()}


def plan_out_of_fold(
    runs: Iterable[FoldRun], sample_ids: Iterable[str], seeds: Sequence[int]
) -> OutOfFoldPlan:
    """Asigna a cada animal y semilla la corrida en que estuvo en test.

    Raises:
        OutOfFoldError: si las corridas mezclan variantes, brazos o datasets; si una semilla
            repite un fold; si un animal está en el test de dos folds de la misma semilla; o si
            una corrida lo tiene a la vez en test y en train o val interno.
    """
    runs = list(runs)
    kinds = {(run.variant, run.edges_arm, run.dataset_id) for run in runs}
    if len(kinds) > 1:
        raise OutOfFoldError(f"Las corridas mezclan variante, brazo o dataset: {sorted(kinds)}.")
    folds = [(run.seed, run.fold) for run in runs]
    repeated = sorted({key for key in folds if folds.count(key) > 1})
    if repeated:
        raise OutOfFoldError(f"Hay más de una corrida para (semilla, fold) {repeated}.")
    for run in runs:
        leaked = sorted(s for s in run.test if run.saw(s))
        if leaked:
            raise OutOfFoldError(f"{run.run_id}: {leaked} están en test y en entrenamiento.")

    assignments: dict[str, dict[int, FoldRun]] = {}
    missing: dict[str, tuple[int, ...]] = {}
    for sample_id in sorted(set(sample_ids)):
        assignments[sample_id] = {}
        for seed in seeds:
            candidates = [run for run in runs if run.seed == seed and sample_id in run.test]
            if len(candidates) > 1:
                raise OutOfFoldError(
                    f"{sample_id} está en el test de varios folds de la semilla {seed}: "
                    f"{sorted(run.fold for run in candidates)}."
                )
            if candidates:
                assignments[sample_id][seed] = candidates[0]
        missing[sample_id] = tuple(s for s in seeds if s not in assignments[sample_id])
    return OutOfFoldPlan(seeds=tuple(seeds), assignments=assignments, missing=missing)


def run_ref(loaded: LoadedCompositionalRun, repo_root: str | Path) -> RunRef:
    """Referencia del contrato a una corrida recargada, con su `run.json` relativo."""
    info = loaded.info
    try:
        run_json = Path(os.path.relpath(loaded.run_dir / RUN_FILE, repo_root)).as_posix()
    except ValueError:
        # En Windows: si run_dir y repo_root están en unidades distintas
        # (ej. C: en pytest tmp_path y D: para el repositorio)
        parts = (loaded.run_dir / RUN_FILE).parts
        run_indices = [i for i, p in enumerate(parts) if p.startswith("runs")]
        if run_indices:
            run_json = Path(*parts[run_indices[-1] :]).as_posix()
        else:
            run_json = Path(loaded.run_dir.name, RUN_FILE).as_posix()
    return RunRef(
        run_id=str(info["run_id"]),
        run_json=run_json,
        format_version=str(info["format_version"]),
        variant=str(info["variant"]),
        seed=int(info["seed"]),
        dataset_id=str(info["dataset_id"]),
        split=SplitRef(version=str(info["plan"]["version"]), sha256=str(info["plan"]["sha256"])),
        git_commit=info["git"]["commit"],
    )


@dataclass(frozen=True)
class AnimalExplanations:
    """Explicaciones fuera de fold de un animal y una salida."""

    sample_id: str
    output: str
    by_seed: Mapping[int, StabilityReport]
    """Por semilla del plan: las explicaciones del modelo fuera de fold y su estabilidad C-07."""
    missing_seeds: tuple[int, ...]
    plan_phi: float | None
    """Φ̂ del top-k entre semillas del plan (primera semilla del explicador); `None` con < 2."""
    plan_ci: tuple[float, float] | None

    @property
    def count(self) -> int:
        return len(self.by_seed)


def explain_out_of_fold(
    plan: OutOfFoldPlan,
    graphs: Mapping[str, HeteroData],
    explain: ExplainFn,
    *,
    outputs: Sequence[str],
    explainer_seeds: Sequence[int],
    repo_root: str | Path,
    device: str = "cpu",
) -> list[AnimalExplanations]:
    """Explica cada animal con sus modelos fuera de fold, en cada salida.

    `graphs` (por `sample_id`) se preparan como para entrenar (aristas inversas y tipos
    alineados), sin escalar: cada corrida aplica su propio escalado. Cada corrida se carga una
    sola vez.

    Raises:
        OutOfFoldError: si un animal no tiene grafo, si la corrida asignada lo vio en
            entrenamiento o si los grafos no tienen las columnas y relaciones del entrenamiento.
    """
    absent = sorted(s for s in plan.assignments if s not in graphs)
    if absent:
        raise OutOfFoldError(f"Animales sin grafo: {absent}.")
    metadata = GraphMetadata.from_graphs(list(graphs.values()))
    by_run: dict[Path, list[tuple[str, int]]] = {}
    for sample_id, runs in plan.assignments.items():
        for seed, run in runs.items():
            by_run.setdefault(run.run_dir, []).append((sample_id, seed))

    reports: dict[tuple[str, str], dict[int, StabilityReport]] = {}
    for run_dir, members in sorted(by_run.items()):
        loaded = load_compositional_run(run_dir, device=device)
        expected_metadata = (
            loaded.taxon_encoder.adapt_metadata(metadata)
            if loaded.taxon_encoder is not None
            else metadata
        )
        if not graph_metadata_matches(loaded, expected_metadata):
            raise OutOfFoldError(f"{loaded.run_id}: los grafos no coinciden con el entrenamiento.")
        reference = run_ref(loaded, repo_root)
        ids = loaded.info["sample_ids"]
        for sample_id, seed in members:
            # Defensa en profundidad: se vuelve a leer del run.json cargado, no del índice.
            if sample_id not in ids["test"] or sample_id in (*ids["train"], *ids["inner_val"]):
                raise OutOfFoldError(f"{loaded.run_id} no es fuera de fold para {sample_id}.")
            raw_graph = graphs[sample_id]
            if loaded.taxon_encoder is not None:
                raw_graph = loaded.taxon_encoder.transform([raw_graph])[0]
            scaled = loaded.feature_scaler.transform([raw_graph])[0]
            for output in outputs:
                reports.setdefault((sample_id, output), {})[seed] = explain_across_seeds(
                    partial(explain, loaded.model, scaled, reference, output), explainer_seeds
                )

    results = []
    for sample_id in sorted(plan.assignments):
        for output in outputs:
            by_seed = dict(sorted(reports.get((sample_id, output), {}).items()))
            phi, ci = _plan_stability(by_seed)
            results.append(
                AnimalExplanations(
                    sample_id=sample_id,
                    output=output,
                    by_seed=by_seed,
                    missing_seeds=plan.missing[sample_id],
                    plan_phi=phi,
                    plan_ci=ci,
                )
            )
    return results


def _plan_stability(
    by_seed: Mapping[int, StabilityReport],
) -> tuple[float | None, tuple[float, float] | None]:
    if len(by_seed) < 2:
        return None, None
    scores = [importance_elements(report.explanations[0]) for report in by_seed.values()]
    k = next(iter(by_seed.values())).k
    selections = [top_k_selection(score, k) for score in scores]
    d = len(set().union(*scores))
    try:
        return nogueira_phi(selections, d), nogueira_ci(selections, d)
    except ValueError:
        return None, None


__all__ = [
    "AnimalExplanations",
    "ExplainFn",
    "FoldRun",
    "OutOfFoldError",
    "OutOfFoldPlan",
    "explain_out_of_fold",
    "index_runs",
    "plan_out_of_fold",
    "run_ref",
]
