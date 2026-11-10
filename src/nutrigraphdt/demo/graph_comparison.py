"""Comparación entre el grafo sintético y el grafo reconstruido con datos reales de D1.

Todo sale de los registros de cada grafo (nodos, aristas, salidas e instancias) y del resumen
versionado de los 185 grafos de D1 (`reports/graphs/d1_summary.json`). Lo único escrito a mano
es por qué una relación del esquema no está en D1 (#256, sección 1, y #258).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from typing import Any, Final

from nutrigraphdt.demo.data import NODE_TYPE_LABELS, SCFA_NAMES, _field

PRESENT: Final = "Presente"
LIMITATION: Final = "Limitación declarada"
OUT_OF_D1: Final = "Fuera de D1"

EdgeType = tuple[str, str, str]

_NOT_IN_D1: Final[Mapping[EdgeType, tuple[str, str]]] = {
    ("diet", "provides", "substrate"): (
        LIMITATION,
        "La dieta basal es la misma en los tres tratamientos y repite las covariables (#258).",
    ),
    ("substrate", "available_to", "taxon"): (
        LIMITATION,
        "Solo admite `inferred` y no tiene fuente que no use los datos de evaluación (#258).",
    ),
    ("host", "exhibits", "phenotype"): (
        OUT_OF_D1,
        "Los promedios de corral no son fenotipo del animal (V-04).",
    ),
}
_HYPOTHETICAL: Final = "Hipotética: no entra a ningún grafo real (#256, sección 3)."

SCFA_LABELS: Final[Mapping[str, str]] = {
    "acetate": "Acetato",
    "propionate": "Propionato",
    "butyrate": "Butirato",
}
"""Nombre de cada AGCC objetivo; el sintético ya rotula sus metabolitos así."""

_INSTANCE_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("is_synthetic", "Sintético"),
    ("species", "Especie"),
    ("gut_segment", "Segmento"),
    ("study_id", "Estudio o ensayo"),
    ("sample_id", "Muestra"),
    ("scenario_id", "Escenario"),
    ("diet_treatment", "Tratamiento de dieta"),
    ("timepoint", "Día de muestreo"),
    ("schema_version", "Versión del esquema"),
)


# ---------------------------------------------------------------------------
# Conteos de una instancia
# ---------------------------------------------------------------------------


def instance_counts(records: Any, graph_id: str) -> tuple[Counter[str], Counter[EdgeType]]:
    """Nodos por tipo y aristas por relación `(origen, relación, destino)` de una instancia."""
    nodes: Counter[str] = Counter(
        str(_field(n, "node_type")) for n in records.nodes if _field(n, "graph_id") == graph_id
    )
    edges: Counter[EdgeType] = Counter(_edge_type(e) for e in _edges_of(records, graph_id))
    return nodes, edges


def evidence_by_relation(records: Any, graph_id: str) -> dict[EdgeType, str]:
    """Evidencia de las aristas de cada relación: estado, método y fuente, con su conteo.

    Una relación con aristas de varias evidencias las lista todas, de la más a la menos
    frecuente (por ejemplo, `annotated · database_annotation · KEGG@120.0`).
    """
    counts: dict[EdgeType, Counter[str]] = defaultdict(Counter)
    for edge in _edges_of(records, graph_id):
        parts = [
            str(_field(edge, "evidence_status")),
            str(_field(edge, "evidence_method")),
            _field(edge, "evidence_source"),
        ]
        counts[_edge_type(edge)][" · ".join(str(p) for p in parts if p)] += 1
    return {
        edge_type: "; ".join(
            text if len(counter) == 1 else f"{text} ({n})" for text, n in counter.most_common()
        )
        for edge_type, counter in counts.items()
    }


def _edges_of(records: Any, graph_id: str) -> list[Any]:
    return [e for e in records.edges if _field(e, "graph_id") == graph_id]


def _edge_type(edge: Any) -> EdgeType:
    return (
        str(_field(edge, "source_type")),
        str(_field(edge, "relation_type")),
        str(_field(edge, "target_type")),
    )


def _range(stats: Mapping[str, int] | None) -> str:
    if not stats:
        return "0"
    low, high = stats["min"], stats["max"]
    return str(low) if low == high else f"{low}–{high}"


# ---------------------------------------------------------------------------
# Tablas
# ---------------------------------------------------------------------------


def relation_rows(
    synthetic: Counter[EdgeType],
    real: Counter[EdgeType],
    *,
    synthetic_evidence: Mapping[EdgeType, str] | None = None,
    real_evidence: Mapping[EdgeType, str] | None = None,
    d1_graphs: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Una fila por relación del esquema v1: aristas y evidencia en cada grafo y estado en D1.

    `d1_graphs` es `graphs` del resumen de D1; con él, `D1 (185 grafos)` da el mínimo y el
    máximo de aristas por grafo en toda la cohorte.
    """
    from nutrigraphdt.graph.schema import ALLOWED_RELATIONS

    per_relation = (d1_graphs or {}).get("edges_per_relation", {})
    rows: list[dict[str, Any]] = []
    for edge_type, spec in ALLOWED_RELATIONS.items():
        if real[edge_type]:
            state, reason = PRESENT, spec.semantics
        else:
            state, reason = _NOT_IN_D1.get(edge_type, (OUT_OF_D1, _HYPOTHETICAL))
        row: dict[str, Any] = {
            "origen": edge_type[0],
            "relación": edge_type[1],
            "destino": edge_type[2],
            "estado": state,
            "sintético": synthetic[edge_type],
            "D1": real[edge_type],
        }
        if d1_graphs is not None:
            row[_cohort_column(d1_graphs)] = _range(per_relation.get("|".join(edge_type)))
        row["evidencia sintético"] = (synthetic_evidence or {}).get(edge_type, "—")
        row["evidencia D1"] = (real_evidence or {}).get(edge_type, "—")
        row["motivo"] = reason
        rows.append(row)
    order = {PRESENT: 0, LIMITATION: 1, OUT_OF_D1: 2}
    rows.sort(key=lambda row: (order[str(row["estado"])], -int(row["sintético"])))
    return rows


def node_rows(
    synthetic: Counter[str],
    real: Counter[str],
    *,
    synthetic_features: Mapping[str, list[str]] | None = None,
    real_features: Mapping[str, list[str]] | None = None,
    d1_graphs: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Nodos por tipo en cada grafo y las columnas de atributos (`x`) que recibe el modelo."""
    rows: list[dict[str, Any]] = []
    for node_type, label in NODE_TYPE_LABELS.items():
        row: dict[str, Any] = {
            "tipo": node_type,
            "nombre": label,
            "sintético": synthetic[node_type],
            "D1": real[node_type],
        }
        if d1_graphs is not None:
            row[_cohort_column(d1_graphs)] = _range(
                d1_graphs.get("nodes_per_type", {}).get(node_type)
            )
        row["atributos sintético"] = _columns(synthetic_features, node_type, synthetic[node_type])
        row["atributos D1"] = _columns(real_features, node_type, real[node_type])
        rows.append(row)
    return rows


def _cohort_column(d1_graphs: Mapping[str, Any]) -> str:
    return f"D1 ({d1_graphs.get('instances', '?')} grafos)"


def _columns(features: Mapping[str, list[str]] | None, node_type: str, count: int) -> str:
    if not count:
        return "—"
    if features is None:
        return "sin datos"
    columns = features.get(node_type, [])
    return ", ".join(columns) if columns else "ninguno (solo identidad)"


def feature_columns(dataset: Any) -> dict[str, list[str]]:
    """Columnas de atributos numéricos por tipo de nodo, como las deriva `derive_schema`."""
    from nutrigraphdt.graph.heterodata import derive_schema

    schema = derive_schema(dataset.nodes, dataset.edges, dataset.outputs)
    return {node_type: [c.name for c in columns] for node_type, columns in schema.node.items()}


def instance_rows(synthetic: Mapping[str, Any], real: Mapping[str, Any]) -> list[dict[str, str]]:
    """Metadatos de las dos instancias, campo por campo."""

    def text(value: Any) -> str:
        if isinstance(value, bool):
            return "sí" if value else "no"
        return "—" if value is None else str(value)

    return [
        {"campo": label, "sintético": text(synthetic.get(key)), "D1": text(real.get(key))}
        for key, label in _INSTANCE_FIELDS
    ]


def target_rows(
    synthetic: Mapping[str, float],
    real: Mapping[str, float],
    quantiles: Mapping[str, Mapping[str, float]] | None = None,
) -> list[dict[str, Any]]:
    """Los tres AGCC objetivo (mmol/kg) en cada instancia y, si hay, su mediana en D1.

    `synthetic` y `real` vienen de `targets_of`: el sintético rotula los metabolitos en
    español y D1 por su identificador químico.
    """
    rows: list[dict[str, Any]] = []
    for name in SCFA_NAMES:
        label = SCFA_LABELS[name]
        row: dict[str, Any] = {
            "AGCC": label,
            "sintético": synthetic.get(label),
            "D1": real.get(name),
        }
        stats = (quantiles or {}).get(name)
        if stats:
            row["D1 mediana (Q1–Q3)"] = (
                f"{stats['median']:.1f} ({stats['q1']:.1f}–{stats['q3']:.1f}), n={stats['n']:.0f}"
            )
        rows.append(row)
    return rows


def synthetic_view(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Las mismas filas con el estado del grafo sintético, que tiene todas las relaciones."""
    return [{**row, "estado": PRESENT if row["sintético"] else OUT_OF_D1} for row in rows]


__all__ = [
    "LIMITATION",
    "OUT_OF_D1",
    "PRESENT",
    "SCFA_LABELS",
    "evidence_by_relation",
    "feature_columns",
    "instance_counts",
    "instance_rows",
    "node_rows",
    "relation_rows",
    "synthetic_view",
    "target_rows",
]
