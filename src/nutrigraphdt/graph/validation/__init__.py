"""Validadores de integridad del grafo heterogéneo.

Implementan las reglas de `docs/graph/graph-integrity-rules.md`. Cada validador devuelve una lista
de `Finding` con la regla, la severidad y la ubicación de cada incumplimiento, sin modificar el
grafo. `validate_graph` es la interfaz común: ejecuta todas las reglas y consolida los hallazgos en
un `ValidationReport`. `prepare_graphs_for_model` aplica el efecto de cada severidad antes de
entregar los grafos al modelo (VG-07).

Validadores por familia de reglas, todos sobre registros salvo el de tensores:

- nodos e instancias (VG-02), aristas (VG-03) y conectividad (VG-04);
- pares de escenarios y metadatos (INS-05, INS-06, MET) y salidas (OUT) (VG-07);
- tensores (VG-05), en `nutrigraphdt.graph.validation.tensors`. No se importa aquí porque
  requiere el extra `graph` (PyTorch y PyTorch Geometric); `validate_graph` lo carga solo cuando
  recibe `HeteroData`.
"""

from nutrigraphdt.graph.validation.connectivity import find_connectivity_findings
from nutrigraphdt.graph.validation.dataset import find_metadata_findings, find_scenario_findings
from nutrigraphdt.graph.validation.edges import find_edge_findings
from nutrigraphdt.graph.validation.findings import Finding, Severity
from nutrigraphdt.graph.validation.nodes import (
    NODE_ATTRIBUTE_CONTRACT,
    SYNTHETIC_ID_PREFIX,
    find_node_findings,
)
from nutrigraphdt.graph.validation.outputs import find_output_findings
from nutrigraphdt.graph.validation.pipeline import (
    RawDataset,
    prepare_graphs_for_model,
    read_raw_dataset,
    validate_graph,
)
from nutrigraphdt.graph.validation.report import (
    RULES_VERSION,
    GraphIntegrityError,
    ValidationReport,
    require_deliverable,
)

__all__ = [
    "NODE_ATTRIBUTE_CONTRACT",
    "RULES_VERSION",
    "SYNTHETIC_ID_PREFIX",
    "Finding",
    "GraphIntegrityError",
    "RawDataset",
    "Severity",
    "ValidationReport",
    "find_connectivity_findings",
    "find_edge_findings",
    "find_metadata_findings",
    "find_node_findings",
    "find_output_findings",
    "find_scenario_findings",
    "prepare_graphs_for_model",
    "read_raw_dataset",
    "require_deliverable",
    "validate_graph",
]
