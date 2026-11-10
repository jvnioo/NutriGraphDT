"""Comparación entre el grafo sintético y el grafo reconstruido con datos reales de D1.

Cuenta nodos por tipo y aristas por relación en una instancia de cada fuente, con los mismos
registros que dibuja la página «Grafos». Lo único escrito a mano es por qué una relación del
esquema no está en D1 (decisión de Investigación de #256, sección 1).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any, Final

from nutrigraphdt.demo.data import NODE_TYPE_LABELS, _field

PRESENT: Final = "Presente"
LIMITATION: Final = "Limitación declarada"
OUT_OF_D1: Final = "Fuera de D1"

_NOT_IN_D1: Final[Mapping[tuple[str, str, str], tuple[str, str]]] = {
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


def instance_counts(
    records: Any, graph_id: str
) -> tuple[Counter[str], Counter[tuple[str, str, str]]]:
    """Nodos por tipo y aristas por relación `(origen, relación, destino)` de una instancia."""
    nodes: Counter[str] = Counter(
        str(_field(n, "node_type")) for n in records.nodes if _field(n, "graph_id") == graph_id
    )
    edges: Counter[tuple[str, str, str]] = Counter(
        (
            str(_field(e, "source_type")),
            str(_field(e, "relation_type")),
            str(_field(e, "target_type")),
        )
        for e in records.edges
        if _field(e, "graph_id") == graph_id
    )
    return nodes, edges


def relation_rows(
    synthetic: Counter[tuple[str, str, str]], real: Counter[tuple[str, str, str]]
) -> list[dict[str, Any]]:
    """Una fila por relación del esquema v1, con sus aristas en cada grafo y su estado en D1."""
    from nutrigraphdt.graph.schema import ALLOWED_RELATIONS

    rows: list[dict[str, Any]] = []
    for edge_type, spec in ALLOWED_RELATIONS.items():
        if real[edge_type]:
            state, reason = PRESENT, spec.semantics
        else:
            state, reason = _NOT_IN_D1.get(edge_type, (OUT_OF_D1, _HYPOTHETICAL))
        rows.append(
            {
                "origen": edge_type[0],
                "relación": edge_type[1],
                "destino": edge_type[2],
                "sintético": synthetic[edge_type],
                "D1": real[edge_type],
                "estado": state,
                "motivo": reason,
            }
        )
    order = {PRESENT: 0, LIMITATION: 1, OUT_OF_D1: 2}
    rows.sort(key=lambda row: (order[str(row["estado"])], -int(row["sintético"])))
    return rows


def node_rows(synthetic: Counter[str], real: Counter[str]) -> list[dict[str, Any]]:
    """Nodos por tipo en cada grafo, en el orden del esquema."""
    return [
        {
            "tipo": node_type,
            "nombre": label,
            "sintético": synthetic[node_type],
            "D1": real[node_type],
        }
        for node_type, label in NODE_TYPE_LABELS.items()
    ]


def synthetic_view(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Las mismas filas con el estado del grafo sintético, que tiene todas las relaciones."""
    return [{**row, "estado": PRESENT if row["sintético"] else OUT_OF_D1} for row in rows]


__all__ = [
    "LIMITATION",
    "OUT_OF_D1",
    "PRESENT",
    "instance_counts",
    "node_rows",
    "relation_rows",
    "synthetic_view",
]
