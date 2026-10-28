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
import re
import statistics
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
D1_REPORT: Final[Path] = REPO_ROOT / "artifacts" / "graphs" / "D1_holofood" / "report.json"
D1_SUMMARY: Final[Path] = REPORTS_DIR / "graphs" / "d1_summary.json"
RULES_DOC: Final[Path] = REPO_ROOT / "docs" / "graph" / "graph-integrity-rules.md"

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


MODEL_LABELS: Final[Mapping[str, str]] = {
    "dummy_mean": "Media (referencia)",
    "ridge": "Ridge (lineal)",
    "elasticnet": "Elastic Net (lineal)",
    "random_forest": "Bosque aleatorio",
    "hist_gradient_boosting": "Gradient boosting",
    "homo_sage": "GraphSAGE homogénea",
    "hetero_sage": "GraphSAGE heterogénea",
    "hetero_gat": "GAT heterogénea",
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


# ---------------------------------------------------------------------------
# Partición y baselines
# ---------------------------------------------------------------------------


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


_RULE_ROW = re.compile(
    r"^\| ([A-Z]{3}-\d{2})(?: \*\*\(P\)\*\*)? \| (.+?) \| (ERROR|ADVERTENCIA|INFO)"
)


def rule_catalog(path: Path = RULES_DOC) -> dict[str, str]:
    """Descripción de cada regla de `graph-integrity-rules.md`, por `rule_id`."""
    catalog: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _RULE_ROW.match(line)
        if match:
            catalog[match.group(1)] = re.sub(r"[`*]", "", match.group(2))
    return catalog


def summarize_d1_report(report_path: Path, agcc: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Resumen versionable del reporte de `scripts/build_graph.py` sobre D1.

    El reporte completo incluye cada hallazgo (decenas de MB) y queda en `artifacts/`. El
    resumen conserva solo totales (integración, nodos y aristas por tipo, validación por regla,
    contratos) y cuantiles de los AGCC de `agcc` (`agcc_by_animal`), sin valores por animal.
    """
    report = json.loads(report_path.read_text(encoding="utf-8"))
    validation = report["validation"]
    catalog = rule_catalog()
    return {
        "integration": report["integration"],
        "graphs": report["graphs"],
        "contracts": {
            key: value
            for key, value in report["contracts"].items()
            if key.startswith(("checked", "invalid"))
        },
        "status": validation["status"],
        "rules_version": validation["rules_version"],
        "summary": validation["summary"],
        "deliverable": sum(1 for g in validation["graphs"].values() if g.get("deliverable")),
        "rules": [
            {
                "regla": rule_id,
                "severidad": entry["severity"],
                "hallazgos": entry["count"],
                "descripción": catalog.get(rule_id, ""),
            }
            for rule_id, entry in validation["rules"].items()
        ],
        "evaluated": len(validation["evaluated"]),
        "agcc": {name: _quantiles([float(row[name]) for row in agcc]) for name in SCFA_NAMES},
    }


def _quantiles(values: Sequence[float]) -> dict[str, float]:

    q1, median, q3 = statistics.quantiles(values, n=4)
    return {
        "n": len(values),
        "min": min(values),
        "q1": q1,
        "median": median,
        "q3": q3,
        "max": max(values),
    }


def d1_graph_report(path: Path = D1_SUMMARY) -> dict[str, Any] | None:
    """Resumen versionado de los grafos de D1 (`summarize_d1_report`), o `None` si no existe."""
    if not path.is_file():
        return None
    summary: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return summary


def gnn_synthetic_rows(directory: Path | None = None) -> list[dict[str, str]] | None:
    """Métricas de las tres GNN en la cohorte sintética (`reports/gnn/synthetic/report.csv`).

    Tienen el mismo formato que `report.csv` de los baselines, así que se leen con
    `baseline_table`. Devuelve `None` si el reporte no existe.
    """
    path = (directory or REPORTS_DIR / "gnn" / "synthetic") / "report.csv"
    return _read_csv(path) if path.is_file() else None


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


# ---------------------------------------------------------------------------
# Corridas registradas (A44-5)
# ---------------------------------------------------------------------------


__all__ = [
    "MODEL_LABELS",
    "NODE_TYPE_LABELS",
    "NODE_TYPE_ORDER",
    "RELATION_LABELS",
    "REPO_ROOT",
    "GraphView",
    "SCFA_NAMES",
    "D1Records",
    "agcc_by_animal",
    "baseline_report",
    "baseline_table",
    "d1_graph_report",
    "d1_records",
    "graph_ids",
    "gnn_synthetic_rows",
    "graph_view",
    "instance_info",
    "node_label",
    "relation_text",
    "rule_catalog",
    "summarize_d1_report",
    "synthetic_scenarios",
    "targets_of",
    "type_counts",
]
