"""Datos de la demo: todo sale del código y de los artefactos del repositorio.

Las funciones no dependen de Streamlit; las páginas las envuelven con `st.cache_data` o
`st.cache_resource`. Las rutas se resuelven desde la raíz del repositorio (`REPO_ROOT`), así que
la demo funciona sin la descarga completa de D1: usa la cohorte sintética, el fixture de D1
(`tests/fixtures/holofood/`, 6 animales) y los reportes versionados en `reports/`.
"""

from __future__ import annotations

import contextlib
import csv
import dataclasses
import io
import json
import math
import warnings
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
FIXTURE_DIR: Final[Path] = REPO_ROOT / "tests" / "fixtures" / "holofood"
D1_DIR: Final[Path] = REPO_ROOT / "data" / "raw" / "D1_holofood"
REPORTS_DIR: Final[Path] = REPO_ROOT / "reports"
RUNS_DIR: Final[Path] = REPO_ROOT / "runs"

NODE_TYPE_ORDER: Final[tuple[str, ...]] = (
    "diet",
    "additive",
    "substrate",
    "taxon",
    "function",
    "metabolite",
    "host",
    "phenotype",
)
"""Orden de izquierda a derecha en el explorador: de la dieta al fenotipo del huésped."""

NODE_TYPE_LABELS: Final[Mapping[str, str]] = {
    "diet": "Dieta",
    "additive": "Aditivo",
    "substrate": "Sustrato",
    "taxon": "Taxón",
    "function": "Función",
    "metabolite": "Metabolito",
    "host": "Huésped",
    "phenotype": "Fenotipo",
}

NODE_TYPE_DESCRIPTIONS: Final[Mapping[str, str]] = {
    "diet": "La dieta que recibe el animal.",
    "additive": "Un aditivo agregado a la dieta (por ejemplo, un probiótico).",
    "substrate": "Un componente de la dieta que llega al intestino (fibra, almidón…).",
    "taxon": "Un grupo de bacterias del intestino, con su abundancia.",
    "function": "Una capacidad metabólica de las bacterias (una enzima, una ruta).",
    "metabolite": "Un compuesto medido en el ciego; los AGCC son el objetivo.",
    "host": "El animal: especie, segmento intestinal y peso.",
    "phenotype": "Un rasgo productivo del animal (por ejemplo, conversión alimenticia).",
}

MODEL_LABELS: Final[Mapping[str, str]] = {
    "dummy_mean": "Media (referencia)",
    "ridge": "Ridge (lineal)",
    "elasticnet": "Elastic Net (lineal)",
    "random_forest": "Bosque aleatorio",
    "hist_gradient_boosting": "Gradient boosting",
    "homo_sage": "GNN simple",
    "hetero_sage": "GNN por relación",
    "hetero_gat": "GNN con atención",
}
"""Nombres para mostrar de los modelos; la clave es el nombre del código."""

RELATION_LABELS: Final[Mapping[str, str]] = {
    "provides": "aporta",
    "modulates": "modula",
    "available_to": "alimenta a",
    "has_capacity": "realiza",
    "interacts_with": "interactúa con",
    "cross_feeds": "abastece a",
    "produces": "produce",
    "associated_with": "se asocia con",
    "measured_in": "se midió en",
    "exhibits": "manifiesta",
}

_LABEL_KEYS: Final[tuple[str, ...]] = ("name", "substance", "taxonomy_id", "trait", "function_id")


# ---------------------------------------------------------------------------
# Registros (sintético y D1)
# ---------------------------------------------------------------------------


def _field(record: Any, name: str) -> Any:
    """Lee `name` de un registro sintético (dataclass) o de D1 (diccionario)."""
    if isinstance(record, Mapping):
        return record.get(name)
    return getattr(record, name, None)


def synthetic_scenarios() -> Any:
    """Dataset con los escenarios basal e intervenido de DS-04 (`SyntheticDataset`)."""
    from nutrigraphdt.data.synthetic import generate_scenario_dataset

    return generate_scenario_dataset()


def synthetic_cohort(n_samples: int = 50, first_seed: int = 1) -> Any:
    """La cohorte de `compare_baselines.py` y `train_gnn.py` (`SyntheticDataset`)."""
    from nutrigraphdt.models.baselines import build_synthetic_cohort

    return build_synthetic_cohort(n_samples, first_seed)


@dataclass(frozen=True)
class D1Records:
    """Registros del grafo de D1 y de dónde salieron."""

    records: Any
    full: bool
    """`True` si vienen de la descarga completa; `False` si del fixture de 6 animales."""


def d1_records(*, prefer_full: bool = True) -> D1Records:
    """Registros (nodos, aristas, salidas) de los animales de D1, sin construir tensores.

    Usa la descarga completa de `data/raw/D1_holofood/` (`scripts/fetch_holofood.py`) si
    existe y `prefer_full` es `True`; si no, el fixture de `tests/fixtures/holofood/`. Sigue el
    flujo de `scripts/build_graph.py` hasta `records_from_tables`, que es lo que necesita el
    explorador (unos segundos para los 185 animales). Silencia los avisos de ingesta (taxones
    repetidos que se suman), que ya documenta el constructor.
    """
    from nutrigraphdt.data.config import load_sources
    from nutrigraphdt.data.integration import attach_sample_context
    from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader
    from nutrigraphdt.data.pipeline import DataPipeline
    from nutrigraphdt.graph.builder import records_from_tables

    full = prefer_full and (D1_DIR / "manifest.json").is_file()
    directory = D1_DIR if full else FIXTURE_DIR
    sources = load_sources(REPO_ROOT / "configs" / "sources.json")

    def source(source_id: str, file_name: str) -> Any:
        return dataclasses.replace(sources[source_id], path_or_url=str(directory / file_name))

    with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
        warnings.simplefilter("ignore")
        abundance = source("D1_holofood", "abundance_ssu_caecum.tsv")
        tables = DataPipeline({"D1_holofood": abundance}).run(["D1_holofood"]).dataset
        tables, _ = attach_sample_context(
            tables,
            metadata=MetadataLoader(source("D1_holofood_metadata", "metadata.tsv")).load(),
            metabolites=MetaboliteLoader(
                source("D1_holofood_scfa_content", "scfa_caecum_content.tsv")
            ).load(),
        )
        records = records_from_tables(tables)
    return D1Records(records=records, full=full)


SCFA_NAMES: Final[tuple[str, ...]] = ("acetate", "propionate", "butyrate")


def agcc_by_animal(records: Any) -> list[dict[str, Any]]:
    """Animales con los tres AGCC: identificador, dieta, día y valores (mmol/kg)."""
    rows: list[dict[str, Any]] = []
    for graph_id in graph_ids(records):
        targets = targets_of(records, graph_id)
        if not all(name in targets for name in SCFA_NAMES):
            continue
        info = instance_info(records, graph_id)
        rows.append(
            {
                "graph_id": graph_id,
                "animal": info["sample_id"],
                "dieta": info["diet_treatment"],
                "día": info["timepoint"],
                **{name: targets[name] for name in SCFA_NAMES},
            }
        )
    return rows


def graph_ids(records: Any) -> list[str]:
    """Identificadores de las instancias, en orden."""
    return sorted({str(_field(instance, "graph_id")) for instance in records.instances})


def instance_info(records: Any, graph_id: str) -> dict[str, Any]:
    """Campos de la instancia `graph_id` (especie, segmento, escenario, dieta…)."""
    for instance in records.instances:
        if _field(instance, "graph_id") == graph_id:
            if isinstance(instance, Mapping):
                return dict(instance)
            return dataclasses.asdict(instance)
    raise KeyError(graph_id)


def node_label(node_id: str, attributes: Mapping[str, Any], node_type: str | None = None) -> str:
    """Nombre legible de un nodo: su nombre, sustancia o identificador taxonómico.

    El huésped no tiene nombre propio (su `node_id` es un código), así que se rotula por tipo.
    """
    if node_type == "host":
        return "huésped"
    for key in _LABEL_KEYS:
        value = attributes.get(key)
        if isinstance(value, str) and value:
            return _short(value)
    return _short(node_id)


def _short(value: str) -> str:
    # `synthetic:taxon:bacteroides` → `bacteroides`; `SAMEA…:host` → `host`.
    return value.rsplit(":", 1)[-1].replace("_", " ")


# ---------------------------------------------------------------------------
# Explorador del grafo
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GraphView:
    """Nodos y aristas de una instancia, con posiciones por columna de tipo."""

    graph_id: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    hidden: dict[str, int] = field(default_factory=dict)
    """Nodos omitidos por tipo (los de menor abundancia o sin aristas)."""

    @property
    def node_types(self) -> list[str]:
        present = {node["node_type"] for node in self.nodes}
        return [t for t in NODE_TYPE_ORDER if t in present]


def graph_view(records: Any, graph_id: str, *, max_per_type: int = 20) -> GraphView:
    """Vista de la instancia `graph_id` para dibujarla.

    Cada tipo de nodo es una columna, en el orden de `NODE_TYPE_ORDER`. Si un tipo tiene más de
    `max_per_type` nodos, se muestran los que tienen aristas y, entre ellos, los de mayor
    abundancia (taxones de D1). Las aristas se limitan a los nodos mostrados.
    """
    nodes = [node for node in records.nodes if _field(node, "graph_id") == graph_id]
    edges = [edge for edge in records.edges if _field(edge, "graph_id") == graph_id]
    if not nodes:
        raise KeyError(f"No hay nodos para {graph_id!r}.")
    degree: Counter[tuple[str, str]] = Counter()
    for edge in edges:
        degree[(str(_field(edge, "source_type")), str(_field(edge, "source_id")))] += 1
        degree[(str(_field(edge, "target_type")), str(_field(edge, "target_id")))] += 1

    by_type: dict[str, list[Any]] = defaultdict(list)
    for node in nodes:
        by_type[str(_field(node, "node_type"))].append(node)

    shown: list[dict[str, Any]] = []
    hidden: dict[str, int] = {}
    order = [t for t in NODE_TYPE_ORDER if t in by_type] + sorted(
        t for t in by_type if t not in NODE_TYPE_ORDER
    )
    for column, node_type in enumerate(order):

        def priority(node: Any, node_type: str = node_type) -> tuple[int, float, str]:
            node_id = str(_field(node, "node_id"))
            return (-degree[(node_type, node_id)], -_abundance(node), node_id)

        group = sorted(by_type[node_type], key=priority)
        kept = group[:max_per_type]
        if len(group) > len(kept):
            hidden[node_type] = len(group) - len(kept)
        for row, node in enumerate(kept):
            attributes = dict(_field(node, "attributes") or {})
            node_id = str(_field(node, "node_id"))
            shown.append(
                {
                    "node_id": node_id,
                    "node_type": node_type,
                    "label": node_label(node_id, attributes, node_type),
                    "x": float(column),
                    "y": (len(kept) - 1) / 2 - row,
                    "degree": degree[(node_type, node_id)],
                    "attributes": _printable(attributes),
                }
            )
    keys = {(node["node_type"], node["node_id"]) for node in shown}
    view_edges = [
        {
            "source_type": str(_field(edge, "source_type")),
            "source_id": str(_field(edge, "source_id")),
            "relation": str(_field(edge, "relation_type")),
            "target_type": str(_field(edge, "target_type")),
            "target_id": str(_field(edge, "target_id")),
            "evidence_status": str(_field(edge, "evidence_status")),
        }
        for edge in edges
        if (str(_field(edge, "source_type")), str(_field(edge, "source_id"))) in keys
        and (str(_field(edge, "target_type")), str(_field(edge, "target_id"))) in keys
    ]
    return GraphView(graph_id=graph_id, nodes=shown, edges=view_edges, hidden=hidden)


def _abundance(node: Any) -> float:
    value = (_field(node, "attributes") or {}).get("abundance")
    return float(value) if isinstance(value, int | float) and math.isfinite(value) else 0.0


def _printable(attributes: Mapping[str, Any]) -> dict[str, str]:
    printable: dict[str, str] = {}
    for key, value in attributes.items():
        if value is None:
            continue
        if isinstance(value, list | tuple):
            printable[key] = f"{len(value)} elementos"
        elif isinstance(value, Mapping):
            printable[key] = ", ".join(f"{k}={v}" for k, v in value.items())
        elif isinstance(value, float):
            printable[key] = f"{value:.4g}"
        else:
            printable[key] = str(value)
    return printable


def type_counts(records: Any, graph_id: str) -> tuple[dict[str, int], dict[str, int]]:
    """Nodos por tipo y aristas por relación (en palabras, con `relation_text`) de una instancia."""
    nodes: Counter[str] = Counter(
        str(_field(node, "node_type"))
        for node in records.nodes
        if _field(node, "graph_id") == graph_id
    )
    edges: Counter[str] = Counter(
        relation_text(
            str(_field(edge, "source_type")),
            str(_field(edge, "relation_type")),
            str(_field(edge, "target_type")),
        )
        for edge in records.edges
        if _field(edge, "graph_id") == graph_id
    )
    ordered_nodes = {t: nodes[t] for t in NODE_TYPE_ORDER if t in nodes}
    return ordered_nodes, dict(edges.most_common())


def targets_of(records: Any, graph_id: str) -> dict[str, float]:
    """AGCC con valor de una instancia, por nombre de metabolito."""
    names = {
        str(_field(node, "node_id")): node_label(
            str(_field(node, "node_id")), _field(node, "attributes") or {}
        )
        for node in records.nodes
        if _field(node, "graph_id") == graph_id and _field(node, "node_type") == "metabolite"
    }
    values: dict[str, float] = {}
    for output in records.outputs:
        if _field(output, "graph_id") != graph_id:
            continue
        value = _field(output, "value")
        if isinstance(value, int | float) and math.isfinite(value):
            target_id = str(_field(output, "target_id"))
            values[names.get(target_id, _short(target_id))] = float(value)
    return values


def relation_text(source_type: str, relation: str, target_type: str) -> str:
    """Relación en palabras: `taxon → has_capacity → function` da "Taxón realiza función"."""
    return (
        f"{NODE_TYPE_LABELS.get(source_type, source_type)} "
        f"{RELATION_LABELS.get(relation, relation)} "
        f"{NODE_TYPE_LABELS.get(target_type, target_type).lower()}"
    )


def upstream(
    view: GraphView, node_type: str, node_id: str
) -> tuple[set[tuple[str, str]], set[int]]:
    """Nodos y aristas desde los que se llega a un nodo siguiendo las aristas hacia atrás.

    Sirve para resaltar, por ejemplo, todo lo que en el grafo "alimenta" al butirato: los
    sustratos de la dieta, los taxones que los usan y las funciones que lo producen. Devuelve
    las claves `(tipo, id)` de los nodos y los índices de las aristas de `view.edges`.
    """
    nodes = {(node_type, node_id)}
    edges: set[int] = set()
    frontier = [(node_type, node_id)]
    while frontier:
        current = frontier.pop()
        for index, edge in enumerate(view.edges):
            if (edge["target_type"], edge["target_id"]) != current or index in edges:
                continue
            edges.add(index)
            source = (edge["source_type"], edge["source_id"])
            if source not in nodes:
                nodes.add(source)
                frontier.append(source)
    return nodes, edges


def neighborhood(
    view: GraphView, node_type: str, node_id: str, hops: int
) -> tuple[dict[tuple[str, str], int], set[int]]:
    """Nodos a `hops` saltos o menos de un nodo, sin importar la dirección de las aristas.

    Es lo que una GNN de `hops` capas combina para ese nodo: el modelo agrega una arista inversa
    por cada relación, así que la información viaja en ambos sentidos. Devuelve la distancia de
    cada nodo alcanzado (0 para el nodo de partida) y los índices de las aristas entre ellos.
    """
    distance = {(node_type, node_id): 0}
    frontier = [(node_type, node_id)]
    for step in range(1, hops + 1):
        reached = []
        for edge in view.edges:
            source = (edge["source_type"], edge["source_id"])
            target = (edge["target_type"], edge["target_id"])
            for here, there in ((source, target), (target, source)):
                if here in frontier and there not in distance:
                    distance[there] = step
                    reached.append(there)
        frontier = reached
    edges = {
        index
        for index, edge in enumerate(view.edges)
        if (edge["source_type"], edge["source_id"]) in distance
        and (edge["target_type"], edge["target_id"]) in distance
    }
    return distance, edges


def compare_graphs(
    synthetic: Any, synthetic_id: str, real: Any, real_id: str
) -> dict[str, list[dict[str, Any]]]:
    """Nodos por tipo (totales y conectados) y aristas por relación en dos instancias."""
    rows: list[dict[str, Any]] = []
    stats = {
        "sintético": _degree_stats(synthetic, synthetic_id),
        "D1": _degree_stats(real, real_id),
    }
    for node_type in NODE_TYPE_ORDER:
        rows.append(
            {
                "tipo": NODE_TYPE_LABELS[node_type],
                "sintético": stats["sintético"][0].get(node_type, 0),
                "sintético conectados": stats["sintético"][1].get(node_type, 0),
                "D1": stats["D1"][0].get(node_type, 0),
                "D1 conectados": stats["D1"][1].get(node_type, 0),
            }
        )
    _, synthetic_edges = type_counts(synthetic, synthetic_id)
    _, real_edges = type_counts(real, real_id)
    relations = [
        {"relación": name, "sintético": synthetic_edges.get(name, 0), "D1": real_edges.get(name, 0)}
        for name in dict.fromkeys([*synthetic_edges, *real_edges])
    ]
    return {"nodes": rows, "relations": relations}


def _degree_stats(records: Any, graph_id: str) -> tuple[Counter[str], Counter[str]]:
    connected_ids: set[tuple[str, str]] = set()
    for edge in records.edges:
        if _field(edge, "graph_id") != graph_id:
            continue
        connected_ids.add((str(_field(edge, "source_type")), str(_field(edge, "source_id"))))
        connected_ids.add((str(_field(edge, "target_type")), str(_field(edge, "target_id"))))
    totals: Counter[str] = Counter()
    connected: Counter[str] = Counter()
    for node in records.nodes:
        if _field(node, "graph_id") != graph_id:
            continue
        key = (str(_field(node, "node_type")), str(_field(node, "node_id")))
        totals[key[0]] += 1
        if key in connected_ids:
            connected[key[0]] += 1
    return totals, connected


# ---------------------------------------------------------------------------
# Partición y baselines
# ---------------------------------------------------------------------------


def split_summary(path: Path | None = None) -> dict[str, Any]:
    """Conteos de la partición canónica de D1 (A45-1) y número de corrales por subconjunto."""
    split_file = path or REPO_ROOT / "configs" / "splits" / "d1_holofood.json"
    data = json.loads(split_file.read_text(encoding="utf-8"))
    # `groups` asigna a cada subconjunto la lista de sus grupos (corrales en D1).
    groups: Mapping[str, Sequence[str]] = data.get("groups", {})
    subsets = data["subsets"]
    return {
        "version": data.get("version"),
        "seed": data.get("seed"),
        "group_key": data.get("group_key"),
        "stratify_key": data.get("stratify_key"),
        "ratios": data.get("ratios", {}),
        "counts": {name: len(subsets[name]) for name in ("train", "val", "test")},
        "groups": {name: len(groups.get(name, ())) for name in ("train", "val", "test")},
    }


def baseline_report(directory: Path) -> dict[str, Any]:
    """`report.csv`, `run.json` y el encabezado de `baseline_comparison.md` de una corrida."""
    rows = _read_csv(directory / "report.csv")
    run = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    header = (directory / "baseline_comparison.md").read_text(encoding="utf-8").split("\n|")[0]
    return {"rows": rows, "run": run, "header": header.strip()}


def baseline_table(
    rows: Iterable[Mapping[str, str]], metric: str, split: str
) -> list[dict[str, Any]]:
    """Una fila por modelo con la métrica `metric` de `split`, por AGCC y promedio.

    `modelo` es el nombre para mostrar (`MODEL_LABELS`) y `clave`, el del código.
    """
    table: list[dict[str, Any]] = []
    for row in rows:
        if row.get("metric") == metric and row.get("split") == split:
            table.append(
                {
                    "modelo": MODEL_LABELS.get(row["model"], row["model"]),
                    "clave": row["model"],
                    "acetato": float(row["acetate"]),
                    "propionato": float(row["propionate"]),
                    "butirato": float(row["butyrate"]),
                    "promedio": float(row["average"]),
                }
            )
    return table


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


# ---------------------------------------------------------------------------
# Corridas registradas (A44-5)
# ---------------------------------------------------------------------------


def list_runs(runs_dir: Path = RUNS_DIR) -> list[dict[str, Any]]:
    """Corridas de `runs/` (las más recientes primero), con lo esencial de `run.json`."""
    if not runs_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for run_file in runs_dir.glob("**/run.json"):
        info = json.loads(run_file.read_text(encoding="utf-8"))
        metrics = (
            _read_csv(run_file.parent / "metrics.csv")
            if (run_file.parent / "metrics.csv").is_file()
            else []
        )
        rmse = {
            row.get("split"): float(row["average"])
            for row in metrics
            if row.get("metric") == "rmse"
        }
        environment = info.get("environment", {})
        rows.append(
            {
                "run_id": info["run_id"],
                "path": run_file.parent,
                "variante": info.get("variant"),
                "dataset": info.get("source", {}).get("dataset", info.get("dataset_id")),
                "dispositivo": environment.get("device_name") or environment.get("device", "cpu"),
                "epocas": info.get("epochs_run"),
                "mejor_epoca": info.get("best_epoch"),
                "rmse_val": rmse.get("val"),
                "rmse_test": rmse.get("test"),
                "segundos": round(float(info.get("duration_seconds", 0.0)), 1),
                "created_at": info.get("created_at", ""),
            }
        )
    return sorted(rows, key=lambda row: row["created_at"], reverse=True)


def run_detail(run_dir: Path) -> dict[str, Any]:
    """`run.json`, historial, métricas y predicciones de una corrida."""
    return {
        "info": json.loads((run_dir / "run.json").read_text(encoding="utf-8")),
        "history": _read_csv(run_dir / "history.csv"),
        "metrics": _read_csv(run_dir / "metrics.csv"),
        "predictions": _read_csv(run_dir / "predictions.csv"),
    }


def train_synthetic_run(
    variant: str,
    *,
    max_epochs: int,
    device: str,
    n_samples: int = 50,
    runs_dir: Path = RUNS_DIR / "demo",
) -> Path:
    """Entrena `variant` sobre la cohorte sintética con `run_training` y devuelve la corrida.

    Usa la configuración versionada (`configs/training/default.json`,
    `configs/models/<variant>.yaml`) con `max_epochs` y `device` sobrescritos, la misma
    cohorte y partición que `scripts/train_gnn.py --dataset synthetic`.
    """
    from nutrigraphdt.data.split import create_split
    from nutrigraphdt.graph.heterodata import build_synthetic_graphs
    from nutrigraphdt.models.baselines import SYNTHETIC_COHORT_ID
    from nutrigraphdt.models.gnn import load_model_config
    from nutrigraphdt.models.training import (
        apply_overrides,
        load_training_config,
        prepare_training_graphs,
    )
    from nutrigraphdt.models.training.pipeline import run_training

    config = apply_overrides(
        load_training_config(REPO_ROOT / "configs" / "training" / "default.json"),
        {"max_epochs": max_epochs, "device": device, "dataset_id": SYNTHETIC_COHORT_ID},
    )
    cohort = synthetic_cohort(n_samples, 1)
    split = create_split(
        [
            {"sample_id": inst.sample_id, "diet_treatment": inst.diet_treatment}
            for inst in cohort.instances
        ],
        group_key=None,
        stratify_key="diet_treatment",
        seed=42,
        dataset_id=SYNTHETIC_COHORT_ID,
    )
    built = build_synthetic_graphs(cohort)
    prepared = prepare_training_graphs(
        built.dataset, built.graphs, split, batch_size=config.batch_size, seed=config.seed
    )
    run = run_training(
        prepared,
        load_model_config(REPO_ROOT / "configs" / "models" / f"{variant}.yaml"),
        config,
        split,
        split_file=None,
        runs_dir=runs_dir,
        repo_root=REPO_ROOT,
        source={
            "dataset": "synthetic",
            "n_samples": n_samples,
            "first_seed": 1,
            "split_seed": 42,
            "origin": "demo",
        },
    )
    return run.run_dir


def available_devices() -> list[str]:
    """`cpu` y, si PyTorch ve una GPU (CUDA o ROCm), `cuda`."""
    import torch

    return ["cuda", "cpu"] if torch.cuda.is_available() else ["cpu"]


def device_name(device: str) -> str:
    """Nombre legible del dispositivo."""
    import torch

    if device.startswith("cuda") and torch.cuda.is_available():
        return str(torch.cuda.get_device_name(torch.device(device)))
    return "CPU"


__all__ = [
    "MODEL_LABELS",
    "NODE_TYPE_DESCRIPTIONS",
    "NODE_TYPE_LABELS",
    "NODE_TYPE_ORDER",
    "RELATION_LABELS",
    "REPO_ROOT",
    "GraphView",
    "SCFA_NAMES",
    "D1Records",
    "agcc_by_animal",
    "available_devices",
    "baseline_report",
    "baseline_table",
    "compare_graphs",
    "d1_records",
    "device_name",
    "graph_ids",
    "graph_view",
    "instance_info",
    "list_runs",
    "neighborhood",
    "node_label",
    "relation_text",
    "run_detail",
    "split_summary",
    "synthetic_cohort",
    "synthetic_scenarios",
    "targets_of",
    "train_synthetic_run",
    "type_counts",
    "upstream",
]
