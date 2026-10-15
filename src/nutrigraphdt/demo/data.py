"""Datos de la demo: todo sale del código y de los artefactos del repositorio.

Las funciones no dependen de Streamlit; las páginas las envuelven con `st.cache_data` o
`st.cache_resource`. Las rutas se resuelven desde la raíz del repositorio (`REPO_ROOT`), así que
la demo funciona sin la descarga completa de D1: usa la cohorte sintética, el fixture de D1
(`tests/fixtures/holofood/`, 6 animales) y los reportes versionados en `reports/`.
"""

from __future__ import annotations

import csv
import dataclasses
import json
import math
import re
import warnings
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
FIXTURE_DIR: Final[Path] = REPO_ROOT / "tests" / "fixtures" / "holofood"
REPORTS_DIR: Final[Path] = REPO_ROOT / "reports"
RUNS_DIR: Final[Path] = REPO_ROOT / "runs"
OVERFIT_DIR: Final[Path] = REPO_ROOT / "artifacts" / "gnn-overfit"
RULES_DOC: Final[Path] = REPO_ROOT / "docs" / "graph" / "graph-integrity-rules.md"
PROGRESS_FILE: Final[Path] = REPORTS_DIR / "progress" / "board_snapshot.json"

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


def d1_fixture() -> Any:
    """Grafos del fixture real de D1 (6 animales) con su auditoría (`HeteroGraphs`, `BuildAudit`).

    Sigue el flujo de `scripts/build_graph.py` sobre `tests/fixtures/holofood/`. Silencia los
    avisos de ingesta (taxones repetidos que se suman), que ya documenta el constructor.
    """
    from nutrigraphdt.data.config import load_sources
    from nutrigraphdt.data.integration import attach_sample_context
    from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader
    from nutrigraphdt.data.pipeline import DataPipeline
    from nutrigraphdt.graph.audit import audit_built_graphs
    from nutrigraphdt.graph.builder import build_hetero_graph

    sources = load_sources(REPO_ROOT / "configs" / "sources.json")

    def source(source_id: str, file_name: str) -> Any:
        return dataclasses.replace(sources[source_id], path_or_url=str(FIXTURE_DIR / file_name))

    with warnings.catch_warnings():
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
        built = build_hetero_graph(tables)
    return built, audit_built_graphs(built)


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
    """Nodos por tipo y aristas por relación (`origen → relación → destino`) de una instancia."""
    nodes: Counter[str] = Counter(
        str(_field(node, "node_type"))
        for node in records.nodes
        if _field(node, "graph_id") == graph_id
    )
    edges: Counter[str] = Counter(
        f"{_field(edge, 'source_type')} → {_field(edge, 'relation_type')} → "
        f"{_field(edge, 'target_type')}"
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


# ---------------------------------------------------------------------------
# Escenarios basal e intervenido
# ---------------------------------------------------------------------------


def scenario_differences(dataset: Any) -> list[dict[str, Any]]:
    """Atributos que cambian entre el escenario basal y el intervenido.

    Compara los nodos con el mismo `node_id` en las dos instancias de `synthetic_scenarios()`.
    Devuelve una fila por atributo distinto, con el valor de cada escenario.
    """
    ids = graph_ids(dataset)
    if len(ids) != 2:
        raise ValueError(f"Se esperaban 2 escenarios; hay {len(ids)}.")
    basal_id = next(gid for gid in ids if "basal" in gid)
    other_id = next(gid for gid in ids if gid != basal_id)
    basal = {(n.node_type, n.node_id): n for n in dataset.nodes if n.graph_id == basal_id}
    other = {(n.node_type, n.node_id): n for n in dataset.nodes if n.graph_id == other_id}
    rows: list[dict[str, Any]] = []
    for key in sorted(basal.keys() & other.keys()):
        flat_basal = _flatten(basal[key].attributes)
        flat_other = _flatten(other[key].attributes)
        for name in sorted(flat_basal.keys() | flat_other.keys()):
            if flat_basal.get(name) != flat_other.get(name):
                rows.append(
                    {
                        "tipo": NODE_TYPE_LABELS.get(key[0], key[0]),
                        "nodo": node_label(key[1], basal[key].attributes),
                        "atributo": name,
                        "basal": flat_basal.get(name),
                        "intervenido": flat_other.get(name),
                    }
                )
    return rows


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, Mapping):
        flat: dict[str, Any] = {}
        for key, item in value.items():
            flat.update(_flatten(item, f"{prefix}{key}."))
        return flat
    if isinstance(value, list):
        flat = {}
        for position, item in enumerate(value):
            label = (
                item.get("component_id") or item.get("ingredient_id")
                if isinstance(item, Mapping)
                else None
            )
            flat.update(_flatten(item, f"{prefix}{label or position}."))
        return flat
    return {prefix.rstrip("."): value}


# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------

_RULE_ROW = re.compile(
    r"^\| ([A-Z]{3}-\d{2})(?: \*\*\(P\)\*\*)? \| (.+?) \| (ERROR|ADVERTENCIA|INFO)"
)


def rule_catalog(path: Path = RULES_DOC) -> dict[str, dict[str, str]]:
    """Reglas de `graph-integrity-rules.md`: descripción y severidad por `rule_id`."""
    catalog: dict[str, dict[str, str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _RULE_ROW.match(line)
        if match:
            catalog[match.group(1)] = {
                "descripcion": re.sub(r"[`*]", "", match.group(2)),
                "severidad": match.group(3),
            }
    return catalog


def validation_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    """Resumen de un `ValidationReport.to_dict()`: totales, reglas con hallazgos y grafos."""
    catalog = rule_catalog()
    rules = [
        {
            "regla": rule_id,
            "severidad": entry["severity"],
            "hallazgos": entry["count"],
            "descripcion": catalog.get(rule_id, {}).get("descripcion", ""),
        }
        for rule_id, entry in report.get("rules", {}).items()
    ]
    graphs = report.get("graphs", {})
    return {
        "status": report.get("status"),
        "rules_version": report.get("rules_version"),
        "summary": dict(report.get("summary", {})),
        "rules": rules,
        "evaluated": list(report.get("evaluated", [])),
        "deliverable": sum(1 for g in graphs.values() if g.get("deliverable")),
        "graphs": len(graphs),
        "catalog_size": len(catalog),
    }


def synthetic_validation(dataset: Any) -> dict[str, Any]:
    """Reporte de validación (`to_dict()`) de los grafos de un dataset sintético."""
    from nutrigraphdt.graph.heterodata import build_synthetic_graphs

    report: dict[str, Any] = build_synthetic_graphs(dataset).report.to_dict()
    return report


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
    """Una fila por modelo con la métrica `metric` de `split`, por AGCC y promedio."""
    table: list[dict[str, Any]] = []
    for row in rows:
        if row.get("metric") == metric and row.get("split") == split:
            table.append(
                {
                    "modelo": row["model"],
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
# Modelos GNN
# ---------------------------------------------------------------------------


def synthetic_metadata(n_graphs: int = 4) -> Any:
    """`GraphMetadata` de unos grafos sintéticos con inversas y target (como en entrenamiento)."""
    from nutrigraphdt.models.gnn import GraphMetadata
    from nutrigraphdt.models.gnn.sanity import synthetic_graphs

    return GraphMetadata.from_graphs(synthetic_graphs(n_graphs))


def model_overview(metadata: Any) -> list[dict[str, Any]]:
    """Por variante: parámetros entrenables y relaciones que usa cada capa.

    Construye cada modelo con `build_model` y la configuración de `configs/models/`.
    """
    import torch

    from nutrigraphdt.models.gnn import build_model, layer_edge_types, load_model_config

    rows: list[dict[str, Any]] = []
    for variant in ("homo_sage", "hetero_sage", "hetero_gat"):
        config = load_model_config(REPO_ROOT / "configs" / "models" / f"{variant}.yaml")
        torch.manual_seed(0)
        model = build_model(config, metadata)
        layers = (
            [list(metadata.edge_types)] * config.num_layers
            if variant == "homo_sage"
            else [list(layer) for layer in layer_edge_types(metadata, config.num_layers)]
        )
        rows.append(
            {
                "variant": variant,
                "config": config.model_dump(),
                "parameters": sum(p.numel() for p in model.parameters() if p.requires_grad),
                "layers": [[" → ".join(edge) for edge in layer] for layer in layers],
            }
        )
    return rows


def overfit_results(directory: Path = OVERFIT_DIR) -> dict[str, Any] | None:
    """Curvas y resumen de `scripts/overfit_gnn.py`, o `None` si no se ha ejecutado."""
    losses = directory / "losses.csv"
    summary = directory / "summary.json"
    if not losses.is_file() or not summary.is_file():
        return None
    rows = _read_csv(losses)
    curves = {name: [float(row[name]) for row in rows] for name in rows[0] if name != "epoch"}
    return {"curves": curves, "summary": json.loads(summary.read_text(encoding="utf-8"))}


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


# ---------------------------------------------------------------------------
# Avance del proyecto
# ---------------------------------------------------------------------------


def progress_snapshot(path: Path = PROGRESS_FILE) -> dict[str, Any] | None:
    """Foto del tablero exportada con `scripts/export_board_snapshot.py`, si existe."""
    if not path.is_file():
        return None
    snapshot: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return snapshot


__all__ = [
    "NODE_TYPE_LABELS",
    "NODE_TYPE_ORDER",
    "REPO_ROOT",
    "GraphView",
    "available_devices",
    "baseline_report",
    "baseline_table",
    "d1_fixture",
    "device_name",
    "graph_ids",
    "graph_view",
    "instance_info",
    "list_runs",
    "model_overview",
    "node_label",
    "overfit_results",
    "progress_snapshot",
    "rule_catalog",
    "run_detail",
    "scenario_differences",
    "split_summary",
    "synthetic_cohort",
    "synthetic_metadata",
    "synthetic_scenarios",
    "synthetic_validation",
    "targets_of",
    "train_synthetic_run",
    "type_counts",
    "validation_summary",
]
