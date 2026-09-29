"""Interfaz común de validación e integración en el pipeline (VG-07).

`validate_graph` ejecuta todas las reglas de `docs/graph-integrity-rules.md` sobre un dataset y,
si se entregan, sobre sus `HeteroData`, y consolida los hallazgos en un `ValidationReport`.
`prepare_graphs_for_model` es el punto del pipeline previo al modelo: devuelve solo los grafos
entregables según la tabla de severidades, junto con el reporte completo.

Orden de evaluación (VG-01, "Alcance y orden de evaluación"):

1. Registros: INS, NOD, EDG, CON, OUT y MET.
2. Tensores: TEN, y OUT sobre `data.output_records`. Solo se evalúan en instancias sin `ERROR`
   de registro y sin `ERROR` de nivel dataset, porque la conversión de registros inválidos
   produciría índices o features sin significado. El reporte indica qué instancias quedaron sin
   evaluar y por qué.

Los validadores de registros no dependen de PyTorch. El módulo de tensores (extra `graph`) solo
se importa cuando se entregan `HeteroData`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from nutrigraphdt.data.synthetic.export import (
    EDGES_FILE,
    INSTANCES_FILE,
    METADATA_FILE,
    NODES_FILE,
    OUTPUTS_FILE,
    RAW_DIR,
    DatasetFormatError,
)
from nutrigraphdt.graph.validation._common import ABSENT, as_record, is_text
from nutrigraphdt.graph.validation.connectivity import find_connectivity_findings
from nutrigraphdt.graph.validation.dataset import find_metadata_findings, find_scenario_findings
from nutrigraphdt.graph.validation.edges import find_edge_findings
from nutrigraphdt.graph.validation.findings import Finding, Severity
from nutrigraphdt.graph.validation.nodes import find_node_findings
from nutrigraphdt.graph.validation.outputs import find_output_findings
from nutrigraphdt.graph.validation.report import ValidationReport

if TYPE_CHECKING:
    from torch_geometric.data import HeteroData

RECORD_FAMILIES: tuple[str, ...] = ("INS", "NOD", "EDG", "CON", "OUT", "MET")
"""Familias de reglas que se evalúan sobre registros."""


class GraphRecords(Protocol):
    """Registros de un dataset: `SyntheticDataset`, `RawDataset` o equivalente."""

    @property
    def metadata(self) -> Any: ...

    @property
    def instances(self) -> Sequence[Any]: ...

    @property
    def nodes(self) -> Sequence[Any]: ...

    @property
    def edges(self) -> Sequence[Any]: ...

    @property
    def outputs(self) -> Sequence[Any]: ...


@dataclass(frozen=True)
class RawDataset:
    """Registros de un dataset exportado, leídos como JSON sin validar su contenido.

    A diferencia de `load_dataset`, no rechaza el dataset en el primer defecto: los valores
    llegan tal cual (incluidos `NaN` o tipos incorrectos) para que los validadores informen
    todos los hallazgos. `metadata` es `None` si no se entregan metadatos.
    """

    metadata: Any
    instances: list[Any] = field(default_factory=list)
    nodes: list[Any] = field(default_factory=list)
    edges: list[Any] = field(default_factory=list)
    outputs: list[Any] = field(default_factory=list)


def _read_json_lines(path: Path) -> list[Any]:
    if not path.is_file():
        raise DatasetFormatError(f"No existe el archivo obligatorio {path}.")
    records: list[Any] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                raise DatasetFormatError(f"{path}:{line_number}: línea vacía no permitida.")
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise DatasetFormatError(
                    f"{path}:{line_number}: JSON no válido: {error}"
                ) from error
    return records


def read_raw_dataset(directory: str | Path) -> RawDataset:
    """Lee `metadata.json` y `raw/*.jsonl` de un dataset exportado con `export_dataset`.

    Lanza `DatasetFormatError` si falta un archivo o una línea no es JSON: sin registros
    legibles no hay nada que validar. Todo lo demás lo informan los validadores.
    """
    root = Path(directory)
    metadata_path = root / METADATA_FILE
    if not metadata_path.is_file():
        raise DatasetFormatError(f"No existe {metadata_path}.")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise DatasetFormatError(f"{metadata_path}: JSON no válido: {error}") from error
    raw = root / RAW_DIR
    return RawDataset(
        metadata=metadata,
        instances=_read_json_lines(raw / INSTANCES_FILE),
        nodes=_read_json_lines(raw / NODES_FILE),
        edges=_read_json_lines(raw / EDGES_FILE),
        outputs=_read_json_lines(raw / OUTPUTS_FILE),
    )


def _instances_by_id(instances: Sequence[Any]) -> dict[str, Mapping[str, Any]]:
    """Primer registro de cada `graph_id` válido, como en VG-02."""
    known: dict[str, Mapping[str, Any]] = {}
    for instance in instances:
        record = as_record(instance)
        if record is not None:
            graph_id = record.get("graph_id")
            if is_text(graph_id):
                known.setdefault(graph_id, record)
    return known


def _output_records_findings(data: Any, graph_id: str, records: GraphRecords) -> list[Finding]:
    """OUT-01 a OUT-04 sobre `data.output_records`, cuando existe."""
    output_records = getattr(data, "output_records", ABSENT)
    if output_records is ABSENT:
        return []
    if not isinstance(output_records, list | tuple):
        return [
            Finding(
                rule_id="OUT-01",
                severity=Severity.ERROR,
                graph_id=graph_id,
                location={"source": "output_records"},
                expected="una lista de registros de salida",
                observed=type(output_records).__name__,
                message="data.output_records no es una lista de registros de salida.",
            )
        ]
    return find_output_findings(
        output_records, records.nodes, records.instances, source="output_records"
    )


def validate_graph(
    records: GraphRecords, *, heterodata: Mapping[str, HeteroData] | None = None
) -> ValidationReport:
    """Ejecuta todas las reglas de integridad y devuelve el reporte consolidado.

    `records` contiene `metadata`, `instances`, `nodes`, `edges` y `outputs` (por ejemplo, un
    `SyntheticDataset` o un `RawDataset`). `heterodata` asocia cada `graph_id` con su
    `HeteroData`; sin él, las reglas `TEN` no se evalúan y el reporte lo indica. Lanza
    `ValueError` si `heterodata` contiene un `graph_id` sin instancia, porque las reglas `TEN`
    se evalúan contra el registro de instancia.

    No modifica los registros ni los grafos.
    """
    metadata = records.metadata
    declared = metadata if isinstance(metadata, Mapping) else None
    instances = _instances_by_id(records.instances)

    findings: list[Finding] = [
        *find_node_findings(records.instances, records.nodes, metadata=declared),
        *find_edge_findings(records.nodes, records.edges, metadata=declared),
        *find_connectivity_findings(records.nodes, records.edges, metadata=declared),
        *find_scenario_findings(records.instances, records.nodes, records.edges),
        *find_output_findings(records.outputs, records.nodes, records.instances),
    ]
    evaluated = list(RECORD_FAMILIES)
    not_evaluated: dict[str, str] = {}
    if metadata is None:
        evaluated.remove("MET")
        not_evaluated["MET"] = "no se entregó metadata.json"
    else:
        findings += find_metadata_findings(
            metadata, records.instances, records.nodes, records.edges, records.outputs
        )

    if heterodata is None:
        not_evaluated["TEN"] = "no se entregó HeteroData"
        return ValidationReport(tuple(findings), tuple(instances), tuple(evaluated), not_evaluated)

    unknown = sorted(set(heterodata) - set(instances))
    if unknown:
        raise ValueError(f"heterodata contiene graph_id sin instancia: {', '.join(unknown)}.")

    from nutrigraphdt.graph.validation.tensors import find_tensor_findings

    evaluated.append("TEN")
    record_errors = {finding.graph_id for finding in findings if finding.severity is Severity.ERROR}
    for graph_id in sorted(instances):
        data = heterodata.get(graph_id)
        if data is None:
            not_evaluated[f"TEN:{graph_id}"] = "no se entregó el HeteroData de la instancia"
        elif None in record_errors or graph_id in record_errors:
            not_evaluated[f"TEN:{graph_id}"] = (
                "errores de registro: la conversión a tensores no tiene significado"
            )
        else:
            findings += find_tensor_findings(
                data,
                instance=instances[graph_id],
                nodes=records.nodes,
                edges=records.edges,
                metadata=declared or {},
            )
            findings += _output_records_findings(data, graph_id, records)
    return ValidationReport(tuple(findings), tuple(instances), tuple(evaluated), not_evaluated)


def prepare_graphs_for_model(
    records: GraphRecords, heterodata: Mapping[str, HeteroData]
) -> tuple[dict[str, HeteroData], ValidationReport]:
    """Valida y devuelve solo los grafos que pueden entregarse al modelo, con el reporte.

    Un grafo con un `ERROR` propio, o con un `ERROR` de nivel dataset, se retiene. Las
    advertencias y los hallazgos `INFO` no bloquean: quedan en el reporte para revisión humana.
    """
    report = validate_graph(records, heterodata=heterodata)
    delivered = {
        graph_id: heterodata[graph_id]
        for graph_id in report.deliverable_graph_ids
        if graph_id in heterodata
    }
    return delivered, report
