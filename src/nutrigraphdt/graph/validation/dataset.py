"""Reglas de pares de instancias y de metadatos del dataset (VG-07, VG-08).

Implementa INS-05 a INS-07 y MET-01 a MET-03 de `docs/graph-integrity-rules.md`. A diferencia de
VG-02 a VG-05, estas reglas no se evalúan sobre una sola instancia: comparan instancias
comparables entre sí o el dataset completo con su `metadata.json`.

Solo leen los registros; no corrigen conteos ni alinean escenarios.

Criterios de aplicación de la especificación:

- INS-05 a INS-07 comparan cada instancia `intervention` con la única instancia `basal` que
  comparte su `sample_id`. Si un `sample_id` no tiene exactamente una instancia `basal`, la
  comparación no está definida y no se evalúa. Si un `graph_id` se repite (INS-01), se usa su
  primer registro, como en VG-02.
- INS-07 (provisional) compara, por tupla, los conjuntos de pares `(source_id, target_id)`. No
  compara atributos ni evidencia de las aristas compartidas, y lista hasta diez aristas de cada
  lado, con su conteo total.
- INS-05 compara, por tipo, los conjuntos de `node_id` y, por nodo, las claves de primer nivel
  de `attributes`. INS-06 compara los valores de las claves que ambos nodos comparten, en
  profundidad.
- INS-06 no informa la variable declarada en `diet_treatment` con la convención del exportador
  DS-05, `<etiqueta>:<variable>=<valor>`: el `value` del elemento de `diet.composition` cuyo
  `component_id` es esa variable. Mientras no exista un mecanismo formal para declarar variables
  intervenidas (§6.1-ii), un `diet_treatment` sin esa forma no excluye ninguna diferencia.
- Los hallazgos de INS-05 a INS-07 usan el `graph_id` de la instancia `intervention` e
  identifican ambas instancias en `location`.
- Los hallazgos `MET` son de nivel dataset (`graph_id = null`), porque indican que los archivos
  exportados no son coherentes entre sí. `location` identifica la instancia cuando corresponde.
- MET-02 compara con tipo el `is_synthetic` del dataset y el de cada instancia; omite las
  instancias cuyo `is_synthetic` no es booleano, porque INS-02 ya lo informa.
- MET-03 cuenta los registros presentes, incluidos los repetidos, con la convención de `counts`
  del exportador: nodos por tipo, aristas por `origen|relación|destino` y salidas. Un tipo o una
  relación sin entrada en `counts` declara cero.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from nutrigraphdt.data.synthetic.export import SCHEMA_VERSION
from nutrigraphdt.data.synthetic.nodes import NodeType
from nutrigraphdt.graph.validation._common import (
    ABSENT,
    as_record,
    describe,
    is_text,
    node_type_sort_key,
)
from nutrigraphdt.graph.validation.findings import Finding, Severity

METADATA_FIELDS: tuple[str, ...] = (
    "dataset_id",
    "schema_version",
    "generator_version",
    "is_synthetic",
    "random_seed",
    "configuration",
    "node_feature_schema",
    "edge_feature_schema",
    "counts",
)
"""Campos mínimos de `metadata.json` (DS-01, MET-01)."""

MAX_LISTED = 10
"""Máximo de aristas que INS-07 enumera por lado; el resto se cuenta."""

EdgeType = tuple[str, str, str]

_TREATMENT = re.compile(r"^(?P<label>.+):(?P<variable>[^:=]+)=(?P<value>[^:=]+)$")
"""Convención de DS-05 para `diet_treatment` de una intervención: `etiqueta:variable=valor`."""


def intervened_variable(diet_treatment: object) -> str | None:
    """Variable declarada en `diet_treatment` con la convención de DS-05, si la tiene."""
    if not isinstance(diet_treatment, str):
        return None
    match = _TREATMENT.match(diet_treatment)
    return match.group("variable") if match else None


# ---------------------------------------------------------------------------
# INS-05 e INS-06: escenarios comparables
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Instance:
    graph_id: str
    record: Mapping[str, Any]


def _first_instances(instances: Iterable[object]) -> dict[str, _Instance]:
    known: dict[str, _Instance] = {}
    for instance in instances:
        record = as_record(instance)
        if record is None:
            continue
        graph_id = record.get("graph_id")
        if is_text(graph_id) and graph_id not in known:
            known[graph_id] = _Instance(graph_id, record)
    return known


def _node_attributes(nodes: Iterable[object]) -> dict[str, dict[str, dict[str, object]]]:
    """`graph_id -> node_type -> node_id -> attributes`, con el primer registro de cada nodo."""
    graphs: dict[str, dict[str, dict[str, object]]] = defaultdict(lambda: defaultdict(dict))
    for node in nodes:
        record = as_record(node)
        if record is None:
            continue
        graph_id = record.get("graph_id")
        node_type = record.get("node_type")
        node_id = record.get("node_id")
        if is_text(graph_id) and is_text(node_type) and is_text(node_id):
            graphs[graph_id][node_type].setdefault(node_id, record.get("attributes"))
    return graphs


def _pairs(instances: Mapping[str, _Instance]) -> Iterator[tuple[str, _Instance, _Instance]]:
    """`(sample_id, basal, intervención)` para cada comparación definida."""
    groups: dict[str, dict[str, list[_Instance]]] = defaultdict(lambda: defaultdict(list))
    for instance in instances.values():
        sample_id = instance.record.get("sample_id")
        scenario_id = instance.record.get("scenario_id")
        if is_text(sample_id) and is_text(scenario_id):
            groups[sample_id][scenario_id].append(instance)
    for sample_id in sorted(groups):
        basal = groups[sample_id].get("basal", [])
        if len(basal) != 1:
            continue
        for intervention in sorted(
            groups[sample_id].get("intervention", []), key=lambda item: item.graph_id
        ):
            yield sample_id, basal[0], intervention


def _same(left: object, right: object) -> bool:
    return type(left) is type(right) and left == right


def _differences(basal: object, intervention: object, path: str) -> Iterator[tuple[str, Any, Any]]:
    """Rutas cuyos valores difieren, recorriendo objetos y listas del mismo largo."""
    if isinstance(basal, dict) and isinstance(intervention, dict):
        for key in sorted(set(basal) | set(intervention), key=str):
            yield from _differences(
                basal.get(key, ABSENT), intervention.get(key, ABSENT), f"{path}.{key}"
            )
    elif (
        isinstance(basal, list)
        and isinstance(intervention, list)
        and len(basal) == len(intervention)
    ):
        for position, (left, right) in enumerate(zip(basal, intervention, strict=True)):
            yield from _differences(left, right, f"{path}[{position}]")
    elif not _same(basal, intervention):
        yield path, basal, intervention


def _declared_paths(
    node_type: str, basal: Mapping[str, Any], intervention: Mapping[str, Any], variable: str | None
) -> set[str]:
    """Rutas de la variable intervenida declarada, que INS-06 no informa."""
    if variable is None or node_type != NodeType.DIET.value:
        return set()
    paths: set[str] = set()
    left = basal.get("composition")
    right = intervention.get("composition")
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        for position, (first, second) in enumerate(zip(left, right, strict=True)):
            if (
                isinstance(first, dict)
                and isinstance(second, dict)
                and first.get("component_id") == variable == second.get("component_id")
            ):
                paths.add(f"composition[{position}].value")
    return paths


def _check_pair(
    sample_id: str,
    basal: _Instance,
    intervention: _Instance,
    graphs: Mapping[str, Mapping[str, Mapping[str, object]]],
) -> Iterator[Finding]:
    context = {
        "sample_id": sample_id,
        "basal_graph_id": basal.graph_id,
        "intervention_graph_id": intervention.graph_id,
    }
    label = f"{basal.graph_id} y {intervention.graph_id} (sample_id {sample_id})"
    basal_nodes = graphs.get(basal.graph_id, {})
    intervention_nodes = graphs.get(intervention.graph_id, {})
    variable = intervened_variable(intervention.record.get("diet_treatment"))

    for node_type in sorted(set(basal_nodes) | set(intervention_nodes), key=node_type_sort_key):
        left = basal_nodes.get(node_type, {})
        right = intervention_nodes.get(node_type, {})
        only_basal = sorted(set(left) - set(right))
        only_intervention = sorted(set(right) - set(left))
        if only_basal or only_intervention:
            yield Finding(
                rule_id="INS-05",
                severity=Severity.ERROR,
                graph_id=intervention.graph_id,
                location={
                    **context,
                    "node_type": node_type,
                    "only_in_basal": only_basal,
                    "only_in_intervention": only_intervention,
                },
                expected="los mismos node_id en ambos escenarios",
                observed=(
                    f"{len(only_basal)} solo en basal y {len(only_intervention)} solo en "
                    "intervención"
                ),
                message=f"Los escenarios {label} no tienen los mismos nodos {node_type}.",
            )

        for node_id in sorted(set(left) & set(right)):
            first = left[node_id]
            second = right[node_id]
            if not isinstance(first, dict) or not isinstance(second, dict):
                # NOD-05 informa unos atributos que no son un objeto.
                continue
            keys_basal = sorted(set(first) - set(second), key=str)
            keys_intervention = sorted(set(second) - set(first), key=str)
            if keys_basal or keys_intervention:
                yield Finding(
                    rule_id="INS-05",
                    severity=Severity.ERROR,
                    graph_id=intervention.graph_id,
                    location={
                        **context,
                        "node_type": node_type,
                        "node_id": node_id,
                        "attributes_only_in_basal": [str(key) for key in keys_basal],
                        "attributes_only_in_intervention": [str(key) for key in keys_intervention],
                    },
                    expected="las mismas claves de atributos en ambos escenarios",
                    observed=describe({"basal": keys_basal, "intervention": keys_intervention}),
                    message=(
                        f"El nodo {node_type} {node_id} no tiene las mismas claves de atributos "
                        f"en los escenarios {label}."
                    ),
                )

            declared = _declared_paths(node_type, first, second, variable)
            for key in sorted(set(first) & set(second), key=str):
                for path, value_basal, value_intervention in _differences(
                    first[key], second[key], str(key)
                ):
                    if path in declared:
                        continue
                    yield Finding(
                        rule_id="INS-06",
                        severity=Severity.WARNING,
                        graph_id=intervention.graph_id,
                        location={
                            **context,
                            "node_type": node_type,
                            "node_id": node_id,
                            "attribute": path,
                            "declared_variable": variable,
                        },
                        expected=f"basal: {describe(value_basal)}",
                        observed=f"intervención: {describe(value_intervention)}",
                        message=(
                            f"'{path}' de {node_type} {node_id} difiere entre los escenarios "
                            f"{label}, pero no es la variable declarada en diet_treatment."
                        ),
                    )


def _edge_sets(edges: Iterable[object]) -> dict[str, dict[EdgeType, set[tuple[str, str]]]]:
    """`graph_id -> tupla -> {(source_id, target_id)}` de las aristas con campos de texto."""
    graphs: dict[str, dict[EdgeType, set[tuple[str, str]]]] = defaultdict(lambda: defaultdict(set))
    for edge in edges:
        record = as_record(edge)
        if record is None:
            continue
        graph_id = record.get("graph_id")
        source_type = record.get("source_type")
        relation_type = record.get("relation_type")
        target_type = record.get("target_type")
        source_id = record.get("source_id")
        target_id = record.get("target_id")
        if (
            is_text(graph_id)
            and is_text(source_type)
            and is_text(relation_type)
            and is_text(target_type)
            and is_text(source_id)
            and is_text(target_id)
        ):
            graphs[graph_id][(source_type, relation_type, target_type)].add((source_id, target_id))
    return graphs


def _edge_type_order(edge_type: EdgeType) -> tuple[tuple[int, str], str, tuple[int, str]]:
    return (node_type_sort_key(edge_type[0]), edge_type[1], node_type_sort_key(edge_type[2]))


def _check_pair_edges(
    sample_id: str,
    basal: _Instance,
    intervention: _Instance,
    edges: Mapping[str, Mapping[EdgeType, set[tuple[str, str]]]],
) -> Iterator[Finding]:
    """INS-07 (provisional): los escenarios comparables tienen las mismas aristas."""
    basal_edges = edges.get(basal.graph_id, {})
    intervention_edges = edges.get(intervention.graph_id, {})
    for edge_type in sorted(set(basal_edges) | set(intervention_edges), key=_edge_type_order):
        left = basal_edges.get(edge_type, set())
        right = intervention_edges.get(edge_type, set())
        only_basal = sorted(left - right)
        only_intervention = sorted(right - left)
        if not only_basal and not only_intervention:
            continue
        yield Finding(
            rule_id="INS-07",
            severity=Severity.WARNING,
            graph_id=intervention.graph_id,
            location={
                "sample_id": sample_id,
                "basal_graph_id": basal.graph_id,
                "intervention_graph_id": intervention.graph_id,
                "edge_type": list(edge_type),
                "only_in_basal_count": len(only_basal),
                "only_in_basal": [list(pair) for pair in only_basal[:MAX_LISTED]],
                "only_in_intervention_count": len(only_intervention),
                "only_in_intervention": [list(pair) for pair in only_intervention[:MAX_LISTED]],
            },
            expected="las mismas aristas en ambos escenarios",
            observed=(
                f"{len(only_basal)} solo en basal y {len(only_intervention)} solo en intervención"
            ),
            message=(
                f"Los escenarios {basal.graph_id} y {intervention.graph_id} (sample_id "
                f"{sample_id}) no tienen las mismas aristas {edge_type[1]} "
                f"({edge_type[0]} -> {edge_type[2]})."
            ),
        )


def find_scenario_findings(
    instances: Iterable[object], nodes: Iterable[object], edges: Iterable[object]
) -> list[Finding]:
    """Evalúa INS-05 a INS-07 sobre cada par basal/intervención con el mismo `sample_id`."""
    known = _first_instances(instances)
    graphs = _node_attributes(nodes)
    edge_sets = _edge_sets(edges)
    findings: list[Finding] = []
    for sample_id, basal, intervention in _pairs(known):
        findings.extend(_check_pair(sample_id, basal, intervention, graphs))
        findings.extend(_check_pair_edges(sample_id, basal, intervention, edge_sets))
    return findings


# ---------------------------------------------------------------------------
# MET-01 a MET-03: metadatos del dataset
# ---------------------------------------------------------------------------


def _metadata_finding(
    rule_id: str, expected: str, observed: str, message: str, **location: Any
) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=Severity.ERROR,
        graph_id=None,
        location={"file": "metadata.json", **location},
        expected=expected,
        observed=observed,
        message=message,
    )


def _check_minimal_fields(metadata: Mapping[str, Any]) -> Iterator[Finding]:
    """MET-01: campos mínimos, versión compatible y semilla entera.

    Desde las reglas 1.2.0 **(P)**, un dataset real (`is_synthetic = false`) puede declarar
    `random_seed: null`: sus registros se observan, no se generan, y una semilla inventada
    falsearía su procedencia.
    """
    for name in METADATA_FIELDS:
        if name not in metadata:
            yield _metadata_finding(
                "MET-01",
                "campo presente",
                "campo ausente",
                f"metadata.json no declara '{name}'.",
                field=name,
            )
    version = metadata.get("schema_version", ABSENT)
    if version is not ABSENT and version != SCHEMA_VERSION:
        yield _metadata_finding(
            "MET-01",
            describe(SCHEMA_VERSION),
            describe(version),
            f"schema_version {describe(version)} no es compatible con {SCHEMA_VERSION}.",
            field="schema_version",
        )
    seed = metadata.get("random_seed", ABSENT)
    real_without_seed = seed is None and metadata.get("is_synthetic") is False
    if (
        seed is not ABSENT
        and not real_without_seed
        and (isinstance(seed, bool) or not isinstance(seed, int))
    ):
        yield _metadata_finding(
            "MET-01",
            "un entero (o null en un dataset real)",
            describe(seed),
            "random_seed no es un entero.",
            field="random_seed",
        )


def _check_origin(
    metadata: Mapping[str, Any], instances: Mapping[str, _Instance]
) -> Iterator[Finding]:
    """MET-02: `is_synthetic` del dataset igual al de cada instancia."""
    declared = metadata.get("is_synthetic", ABSENT)
    if declared is ABSENT:
        return
    discordant = sorted(
        graph_id
        for graph_id, instance in instances.items()
        if isinstance(instance.record.get("is_synthetic"), bool)
        and not _same(declared, instance.record.get("is_synthetic"))
    )
    if discordant:
        yield _metadata_finding(
            "MET-02",
            f"is_synthetic = {describe(declared)} en todas las instancias",
            f"{len(discordant)} instancia(s) discordante(s)",
            f"is_synthetic de metadata.json ({describe(declared)}) no coincide con el de "
            f"{', '.join(discordant)}.",
            field="is_synthetic",
            graph_ids=discordant,
        )


def _actual_counts(
    nodes: Iterable[object], edges: Iterable[object], outputs: Iterable[object]
) -> tuple[Counter[tuple[str, str]], Counter[tuple[str, str]], Counter[str]]:
    node_counts: Counter[tuple[str, str]] = Counter()
    for node in nodes:
        record = as_record(node)
        if record is not None:
            graph_id = record.get("graph_id")
            node_type = record.get("node_type")
            if is_text(graph_id) and is_text(node_type):
                node_counts[(graph_id, node_type)] += 1
    edge_counts: Counter[tuple[str, str]] = Counter()
    for edge in edges:
        record = as_record(edge)
        if record is not None:
            graph_id = record.get("graph_id")
            types = [record.get(name) for name in ("source_type", "relation_type", "target_type")]
            if is_text(graph_id) and all(is_text(value) for value in types):
                edge_counts[(graph_id, "|".join(str(value) for value in types))] += 1
    output_counts: Counter[str] = Counter()
    for output in outputs:
        record = as_record(output)
        if record is not None and is_text(record.get("graph_id")):
            output_counts[str(record["graph_id"])] += 1
    return node_counts, edge_counts, output_counts


def _count_mismatch(
    graph_id: str, category: str, key: str | None, declared: object, actual: int
) -> Finding:
    location: dict[str, Any] = {"field": "counts", "graph_id": graph_id, "category": category}
    subject = category
    if key is not None:
        location["key"] = key
        subject = f"{category} {key}"
    return _metadata_finding(
        "MET-03",
        f"{actual} (presentes en los archivos)",
        f"{describe(declared)} (declarado en counts)",
        f"counts declara {describe(declared)} {subject} para {graph_id}, pero hay {actual}.",
        **location,
    )


def _check_counts(
    metadata: Mapping[str, Any],
    instances: Mapping[str, _Instance],
    nodes: Iterable[object],
    edges: Iterable[object],
    outputs: Iterable[object],
) -> Iterator[Finding]:
    """MET-03: `counts` coincide con los registros presentes."""
    counts = metadata.get("counts", ABSENT)
    if counts is ABSENT:
        return
    if not isinstance(counts, dict):
        yield _metadata_finding(
            "MET-03",
            "un objeto con conteos por instancia",
            describe(counts),
            "counts no es un objeto.",
            field="counts",
        )
        return

    node_counts, edge_counts, output_counts = _actual_counts(nodes, edges, outputs)
    for graph_id in sorted(set(counts) - set(instances), key=str):
        yield _metadata_finding(
            "MET-03",
            "conteos solo para instancias existentes",
            describe(str(graph_id)),
            f"counts declara la instancia {graph_id}, que no existe en instances.jsonl.",
            field="counts",
            graph_id=str(graph_id),
        )

    for graph_id in sorted(instances):
        declared = counts.get(graph_id, ABSENT)
        if not isinstance(declared, dict):
            yield _metadata_finding(
                "MET-03",
                "un objeto con los conteos de la instancia",
                describe(declared),
                f"counts no declara los conteos de {graph_id}.",
                field="counts",
                graph_id=graph_id,
            )
            continue
        for category, actual_counts in (("nodes", node_counts), ("edges", edge_counts)):
            section = declared.get(category)
            section = section if isinstance(section, dict) else {}
            keys = {key for gid, key in actual_counts if gid == graph_id} | set(section)
            for key in sorted(keys, key=str):
                expected = section.get(key, 0)
                actual = actual_counts[(graph_id, str(key))]
                if not _same(expected, actual):
                    yield _count_mismatch(graph_id, category, str(key), expected, actual)
        declared_outputs = declared.get("outputs", 0)
        if not _same(declared_outputs, output_counts[graph_id]):
            yield _count_mismatch(
                graph_id, "outputs", None, declared_outputs, output_counts[graph_id]
            )


def find_metadata_findings(
    metadata: object,
    instances: Iterable[object],
    nodes: Iterable[object],
    edges: Iterable[object],
    outputs: Iterable[object] = (),
) -> list[Finding]:
    """Evalúa MET-01 a MET-03 sobre `metadata.json` y los registros del dataset."""
    if not isinstance(metadata, Mapping):
        return [
            _metadata_finding(
                "MET-01",
                "un objeto JSON",
                type(metadata).__name__,
                "metadata.json no contiene un objeto.",
            )
        ]
    known = _first_instances(instances)
    return [
        *_check_minimal_fields(metadata),
        *_check_origin(metadata, known),
        *_check_counts(metadata, known, nodes, edges, outputs),
    ]
