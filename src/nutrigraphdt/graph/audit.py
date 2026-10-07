"""Auditoría de los grafos construidos desde datos preprocesados (A39-2, #36).

`audit_built_graphs` aplica a la salida de `build_hetero_graph` las mismas herramientas que se
usaron sobre el prototipo sintético y consolida sus resultados:

1. **Reglas de registro** (`validate_graph`): INS, NOD, EDG, CON, OUT y MET.
2. **Reglas de tensores** (`find_tensor_findings`, TEN-01 a TEN-13): IDs únicos, dimensiones,
   tipos y ausencia de `NaN`. A diferencia de `prepare_graphs_for_model`, se evalúan en
   **todas** las instancias, incluso con `ERROR` de registro: los grafos ya están construidos y
   lo que se audita es el tensor resultante. Los errores de registro siguen decidiendo si un
   grafo se entrega al modelo.
3. **Contratos Pydantic v2** (A38-2, `nutrigraphdt.graph.contracts`) sobre cada nodo y arista.

El resultado es estructural: no afirma validez biológica (ver `ValidationReport`).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from nutrigraphdt.graph.builder import HeteroGraphs
from nutrigraphdt.graph.contracts import validate_edge_records, validate_node_records
from nutrigraphdt.graph.validation.findings import Finding
from nutrigraphdt.graph.validation.pipeline import validate_graph
from nutrigraphdt.graph.validation.report import ValidationReport
from nutrigraphdt.graph.validation.tensors import find_tensor_findings

MAX_EXAMPLES = 3
"""Mensajes de ejemplo por grupo de error de contrato en el resumen."""


@dataclass(frozen=True)
class ContractSummary:
    """Resultado de los contratos Pydantic: totales y errores agrupados por causa."""

    checked_nodes: int
    checked_edges: int
    invalid_nodes: int
    invalid_edges: int
    groups: Mapping[str, int] = field(default_factory=dict)
    examples: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checked_nodes": self.checked_nodes,
            "checked_edges": self.checked_edges,
            "invalid_nodes": self.invalid_nodes,
            "invalid_edges": self.invalid_edges,
            "groups": dict(sorted(self.groups.items())),
            "examples": {key: list(value) for key, value in sorted(self.examples.items())},
        }


@dataclass(frozen=True)
class BuildAudit:
    """Reporte de reglas (registro y tensores) y resumen de contratos de un conjunto de grafos."""

    report: ValidationReport
    contracts: ContractSummary
    graph_summary: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "graphs": dict(self.graph_summary),
            "validation": self.report.to_dict(),
            "contracts": self.contracts.to_dict(),
        }


def _contract_group(kind: str, record: Mapping[str, Any], message: str) -> str:
    """Agrupa un error de contrato por tipo de registro y primer campo señalado por Pydantic."""
    label = record.get("node_type") if kind == "node" else record.get("relation_type")
    detail = message.split("\n")
    field_line = next((line.strip() for line in detail[1:] if line.strip()), "")
    return f"{kind}:{label}:{field_line}"


def summarize_contracts(records: Any) -> ContractSummary:
    """Valida nodos y aristas con los contratos de A38-2 y agrupa los errores por causa."""
    _, node_errors = validate_node_records(list(records.nodes))
    _, edge_errors = validate_edge_records(list(records.edges))
    groups: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    for kind, errors, source in (
        ("node", node_errors, records.nodes),
        ("edge", edge_errors, records.edges),
    ):
        for message in errors:
            index = int(message.split("#", 1)[1].split(" ", 1)[0])
            key = _contract_group(kind, source[index], message)
            groups[key] += 1
            if len(examples[key]) < MAX_EXAMPLES:
                examples[key].append(message.split("\n", 1)[0])
    return ContractSummary(
        checked_nodes=len(records.nodes),
        checked_edges=len(records.edges),
        invalid_nodes=len(node_errors),
        invalid_edges=len(edge_errors),
        groups=dict(groups),
        examples={key: tuple(value) for key, value in examples.items()},
    )


def _graph_summary(built: HeteroGraphs) -> dict[str, Any]:
    node_counts: dict[str, list[int]] = defaultdict(list)
    edge_counts: dict[str, list[int]] = defaultdict(list)
    targets = 0
    for data in built.graphs.values():
        for node_type in data.node_types:
            node_counts[node_type].append(int(data[node_type].num_nodes or 0))
            if "y_mask" in data[node_type]:
                targets += int(data[node_type].y_mask.sum())
        for edge_type in data.edge_types:
            edge_counts["|".join(edge_type)].append(int(data[edge_type].edge_index.size(1)))

    def stats(values: list[int]) -> dict[str, int]:
        return {"min": min(values), "max": max(values), "total": sum(values)}

    return {
        "instances": len(built.graphs),
        "nodes_per_type": {key: stats(value) for key, value in sorted(node_counts.items())},
        "edges_per_relation": {key: stats(value) for key, value in sorted(edge_counts.items())},
        "targets_with_value": targets,
        "feature_columns": {
            node_type: [column.name for column in columns]
            for node_type, columns in built.feature_schema.node.items()
        },
    }


def audit_built_graphs(built: HeteroGraphs) -> BuildAudit:
    """Audita la salida de `build_hetero_graph` (ver el docstring del módulo)."""
    records = built.records
    record_report = validate_graph(records)
    nodes_by_graph: dict[str, list[Any]] = defaultdict(list)
    edges_by_graph: dict[str, list[Any]] = defaultdict(list)
    for node in records.nodes:
        nodes_by_graph[node["graph_id"]].append(node)
    for edge in records.edges:
        edges_by_graph[edge["graph_id"]].append(edge)
    instances = {instance["graph_id"]: instance for instance in records.instances}

    tensor_findings: list[Finding] = []
    for graph_id, data in sorted(built.graphs.items()):
        tensor_findings.extend(
            find_tensor_findings(
                data,
                instance=instances[graph_id],
                nodes=nodes_by_graph[graph_id],
                edges=edges_by_graph[graph_id],
                metadata=records.metadata,
            )
        )
    report = ValidationReport(
        findings=(*record_report.findings, *tensor_findings),
        graph_ids=record_report.graph_ids,
        evaluated=(*record_report.evaluated, "TEN"),
        not_evaluated={
            key: value for key, value in record_report.not_evaluated.items() if key != "TEN"
        },
    )
    return BuildAudit(report, summarize_contracts(records), _graph_summary(built))
