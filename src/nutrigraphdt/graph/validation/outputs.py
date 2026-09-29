"""Validación de salidas y targets (VG-07).

Implementa OUT-01 a OUT-04 de `docs/graph-integrity-rules.md` sobre los registros de
`outputs.jsonl` y, cuando existe, sobre `data.output_records` de un `HeteroData`. Una salida
sintética no es una medición: OUT-03 impide que una instancia sintética declare `measured`.

Solo lee los registros; no completa `model_version` ni cambia el origen de una salida.

Criterios de aplicación de la especificación:

- OUT-01 también informa una salida que no es un objeto, o cuyo `graph_id`, `target_type` o
  `target_id` no es una cadena no vacía, porque no identifica un nodo.
- OUT-02 exige la clave `model_version`: una cadena no vacía si la salida es `predicted` y `null`
  en los demás casos. No evalúa `model_version` si `measured_or_predicted` no es un valor
  permitido.
- OUT-03 se evalúa solo si la instancia existe y declara `is_synthetic = true`.
- OUT-04 exige `value` finito y no booleano, con el criterio de NOD-05.
- `location.source` distingue `outputs` (registros de `outputs.jsonl`) de `output_records`
  (atributo del `HeteroData`).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from typing import Any, Literal

from nutrigraphdt.data.synthetic.export import MEASUREMENT_KINDS, OutputRecord
from nutrigraphdt.data.synthetic.nodes import Node
from nutrigraphdt.graph.validation._common import (
    ABSENT,
    as_record,
    describe,
    is_finite_number,
    is_text,
)
from nutrigraphdt.graph.validation.findings import Finding, Severity

OutputSource = Literal["outputs", "output_records"]


def _node_keys(nodes: Iterable[object]) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for node in nodes:
        record = as_record(node)
        if record is None:
            continue
        values = (record.get("graph_id"), record.get("node_type"), record.get("node_id"))
        graph_id, node_type, node_id = values
        if is_text(graph_id) and is_text(node_type) and is_text(node_id):
            keys.add((graph_id, node_type, node_id))
    return keys


def _synthetic_instances(instances: Iterable[object]) -> set[str]:
    synthetic: set[str] = set()
    seen: set[str] = set()
    for instance in instances:
        record = as_record(instance)
        if record is None:
            continue
        graph_id = record.get("graph_id")
        if not is_text(graph_id) or graph_id in seen:
            continue
        seen.add(graph_id)
        if record.get("is_synthetic") is True:
            synthetic.add(graph_id)
    return synthetic


def _check_output(
    index: int,
    record: Mapping[str, Any],
    source: OutputSource,
    nodes: set[tuple[str, str, str]],
    synthetic: set[str],
) -> Iterator[Finding]:
    graph_id = record.get("graph_id")
    target_type = record.get("target_type")
    target_id = record.get("target_id")
    known_graph = graph_id if is_text(graph_id) else None
    base: dict[str, Any] = {"source": source, "output_index": index}
    if is_text(target_type):
        base["target_type"] = target_type
    if is_text(target_id):
        base["target_id"] = target_id
    label = f"Salida {index} de {source}"

    def finding(rule_id: str, expected: str, observed: str, message: str, **extra: Any) -> Finding:
        return Finding(
            rule_id=rule_id,
            severity=Severity.ERROR,
            graph_id=known_graph,
            location={**base, **extra},
            expected=expected,
            observed=observed,
            message=f"{label}: {message}",
        )

    # OUT-01
    for name, value in (
        ("graph_id", graph_id),
        ("target_type", target_type),
        ("target_id", target_id),
    ):
        if not is_text(value):
            yield finding(
                "OUT-01",
                "una cadena no vacía",
                describe(record.get(name, ABSENT)),
                f"'{name}' debe ser una cadena no vacía para identificar el nodo objetivo.",
                field=name,
            )
    if (
        is_text(graph_id)
        and is_text(target_type)
        and is_text(target_id)
        and (graph_id, target_type, target_id) not in nodes
    ):
        yield finding(
            "OUT-01",
            f"un nodo {target_type} {target_id} en la instancia {graph_id}",
            "nodo inexistente",
            f"el nodo objetivo {target_type} {target_id} no existe en la instancia.",
        )

    # OUT-02
    kind = record.get("measured_or_predicted", ABSENT)
    model_version = record.get("model_version", ABSENT)
    if not isinstance(kind, str) or kind not in MEASUREMENT_KINDS:
        yield finding(
            "OUT-02",
            f"uno de {describe(sorted(MEASUREMENT_KINDS))}",
            describe(kind),
            "measured_or_predicted no es un origen permitido.",
            field="measured_or_predicted",
        )
    elif model_version is ABSENT:
        yield finding(
            "OUT-02",
            "campo presente",
            "campo ausente",
            "falta 'model_version' (null si la salida no es una predicción).",
            field="model_version",
        )
    elif kind == "predicted" and not is_text(model_version):
        yield finding(
            "OUT-02",
            "una cadena no vacía",
            describe(model_version),
            "una predicción debe declarar model_version.",
            field="model_version",
        )
    elif kind != "predicted" and model_version is not None:
        yield finding(
            "OUT-02",
            "null",
            describe(model_version),
            "model_version debe ser null si la salida no es una predicción.",
            field="model_version",
        )

    # OUT-03
    if kind == "measured" and known_graph is not None and known_graph in synthetic:
        yield finding(
            "OUT-03",
            '"synthetic" o "predicted"',
            '"measured"',
            "una instancia sintética no puede declarar una salida medida.",
            field="measured_or_predicted",
        )

    # OUT-04
    for name in ("unit", "sample_matrix"):
        value = record.get(name, ABSENT)
        if not is_text(value):
            yield finding(
                "OUT-04",
                "una cadena no vacía",
                describe(value),
                f"'{name}' debe ser una cadena no vacía.",
                field=name,
            )
    value = record.get("value", ABSENT)
    if not is_finite_number(value):
        yield finding(
            "OUT-04",
            "un número finito (no booleano)",
            describe(value),
            "'value' debe ser un número finito.",
            field="value",
        )


def find_output_findings(
    outputs: Iterable[OutputRecord | Mapping[str, Any]],
    nodes: Iterable[Node | Mapping[str, Any]],
    instances: Iterable[object],
    *,
    source: OutputSource = "outputs",
) -> list[Finding]:
    """Evalúa OUT-01 a OUT-04 y devuelve todos los hallazgos, en orden determinista.

    `outputs` son registros de `outputs.jsonl` (o `data.output_records`, con
    `source="output_records"`). `nodes` e `instances` resuelven el nodo objetivo y el origen
    sintético de la instancia. La ubicación usa la posición de la salida (`output_index`).
    """
    node_keys = _node_keys(nodes)
    synthetic = _synthetic_instances(instances)
    findings: list[Finding] = []
    for index, output in enumerate(outputs):
        record = as_record(output)
        if record is None:
            findings.append(
                Finding(
                    rule_id="OUT-01",
                    severity=Severity.ERROR,
                    graph_id=None,
                    location={"source": source, "output_index": index},
                    expected="un objeto con el contrato de salida",
                    observed=type(output).__name__,
                    message=f"La salida {index} de {source} no es un objeto.",
                )
            )
            continue
        findings.extend(_check_output(index, record, source, node_keys, synthetic))
    return findings
