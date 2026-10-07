"""Detección de nodos huérfanos y componentes desconectados (VG-04).

Implementa las reglas CON-01 a CON-04 y la excepción X-01 de `docs/graph/graph-integrity-rules.md`
sobre el grafo de cada instancia, tratando las aristas como no dirigidas. Ninguna condición de
conectividad es `ERROR`: DS-01 prefiere un nodo aislado a una relación no sustentada.

El análisis solo lee los registros: no elimina, conecta ni reordena nodos. Es determinista: el
resultado no depende del orden de los registros recibidos.

Criterios de aplicación de la especificación:

- Un nodo es cada combinación `(graph_id, node_type, node_id)` cuyos tres campos son cadenas no
  vacías. Un `node_id` repetido (NOD-03) cuenta una sola vez.
- Solo conectan las aristas cuyos dos extremos existen como nodos del tipo declarado en la misma
  instancia. Una arista con un extremo inexistente (EDG-02) no conecta nada. Los demás defectos
  de la arista no cambian qué nodos une.
- Un nodo aislado es un componente de tamaño 1, como indica VG-01: su grado se calcula sin
  autolazos, porque un autolazo no lo conecta con otro nodo. EDG-11 informa el autolazo.
- X-01 se aplica a un nodo `additive` cuyo `control_label` pertenece a
  `non_modulating_control_labels`. La lista se lee de `configuration.edges` en `metadata.json`
  cuando está declarada; si no, se usa el valor por defecto del generador (`control_basal`).
- CON-03 considera que una arista referencia un tipo cuando alguno de sus extremos resuelve a un
  nodo de ese tipo, aunque sea un autolazo.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from nutrigraphdt.data.synthetic.edges import Edge, SyntheticEdgeConfig
from nutrigraphdt.data.synthetic.nodes import Node, NodeType
from nutrigraphdt.graph.validation._common import (
    as_record,
    describe,
    is_text,
    node_type_sort_key,
)
from nutrigraphdt.graph.validation.findings import Finding, Severity

_NodeKey = tuple[str, str]
"""`(node_type, node_id)` dentro de una instancia."""

DEFAULT_NON_MODULATING_CONTROL_LABELS: tuple[str, ...] = (
    SyntheticEdgeConfig().non_modulating_control_labels
)
"""Etiquetas de control sin modulación que usa el generador por defecto (X-01)."""


@dataclass(frozen=True)
class _Context:
    """Datos del dataset que necesitan las excepciones."""

    non_modulating_control_labels: frozenset[str]


@dataclass(frozen=True)
class _IsolationException:
    """Excepción admitida para un nodo aislado, transcrita de VG-01."""

    exception_id: str
    description: str
    applies: Callable[[str, list[Mapping[str, Any]], _Context], bool]


def _is_non_modulating_control(
    node_type: str, attributes: list[Mapping[str, Any]], context: _Context
) -> bool:
    """X-01: aditivo de control, al que el generador no crea aristas `modulates`."""
    labels = [attribute.get("control_label") for attribute in attributes]
    # Un `control_label` que no es texto lo informa NOD-05; no puede activar la excepción.
    return (
        node_type == NodeType.ADDITIVE.value
        and bool(labels)
        and all(
            isinstance(label, str) and label in context.non_modulating_control_labels
            for label in labels
        )
    )


_ISOLATION_EXCEPTIONS: tuple[_IsolationException, ...] = (
    _IsolationException(
        exception_id="X-01",
        description=(
            "Nodo additive cuyo control_label pertenece a non_modulating_control_labels: un "
            "control no modula por diseño y ninguna otra relación sale de un aditivo."
        ),
        applies=_is_non_modulating_control,
    ),
)
"""Única fuente de excepciones de CON-02. VG-01 no admite excepciones implícitas: una nueva
excepción se agrega primero a la especificación y después a esta tabla."""

ISOLATED_NODE_EXCEPTIONS: Mapping[str, str] = MappingProxyType(
    {exception.exception_id: exception.description for exception in _ISOLATION_EXCEPTIONS}
)
"""Excepciones admitidas para nodos aislados, por identificador."""


def _context(metadata: Mapping[str, Any] | None) -> _Context:
    labels: object = None
    if metadata is not None:
        configuration = metadata.get("configuration")
        edge_configuration = (
            configuration.get("edges") if isinstance(configuration, Mapping) else None
        )
        if isinstance(edge_configuration, Mapping):
            labels = edge_configuration.get("non_modulating_control_labels")
    if isinstance(labels, list) and all(isinstance(label, str) for label in labels):
        return _Context(frozenset(labels))
    return _Context(frozenset(DEFAULT_NON_MODULATING_CONTROL_LABELS))


# ---------------------------------------------------------------------------
# Grafo de una instancia
# ---------------------------------------------------------------------------


class _InstanceGraph:
    """Nodos y aristas resueltas de una instancia, como grafo no dirigido."""

    def __init__(self) -> None:
        self.attributes: dict[_NodeKey, list[Mapping[str, Any]]] = defaultdict(list)
        self.neighbours: dict[_NodeKey, set[_NodeKey]] = defaultdict(set)
        self.referenced_types: set[str] = set()

    def add_node(self, key: _NodeKey, attributes: object) -> None:
        self.attributes[key].append(attributes if isinstance(attributes, Mapping) else {})

    def add_edge(self, source: _NodeKey, target: _NodeKey) -> None:
        """Registra la arista solo si ambos extremos existen en la instancia."""
        if source not in self.attributes or target not in self.attributes:
            return
        self.referenced_types.update((source[0], target[0]))
        if source != target:
            self.neighbours[source].add(target)
            self.neighbours[target].add(source)

    def components(self) -> list[list[_NodeKey]]:
        """Componentes conexos, cada uno ordenado, del mayor al menor."""
        seen: set[_NodeKey] = set()
        components: list[list[_NodeKey]] = []
        for start in sorted(self.attributes):
            if start in seen:
                continue
            seen.add(start)
            stack = [start]
            component: list[_NodeKey] = []
            while stack:
                key = stack.pop()
                component.append(key)
                for neighbour in self.neighbours.get(key, ()):
                    if neighbour not in seen:
                        seen.add(neighbour)
                        stack.append(neighbour)
            components.append(sorted(component))
        components.sort(key=lambda component: (-len(component), component[0]))
        return components


def _build_graphs(nodes: Iterable[object], edges: Iterable[object]) -> dict[str, _InstanceGraph]:
    graphs: dict[str, _InstanceGraph] = defaultdict(_InstanceGraph)
    for node in nodes:
        record = as_record(node)
        if record is None:
            continue
        graph_id = record.get("graph_id")
        node_type = record.get("node_type")
        node_id = record.get("node_id")
        if is_text(graph_id) and is_text(node_type) and is_text(node_id):
            graphs[graph_id].add_node((node_type, node_id), record.get("attributes"))

    for edge in edges:
        record = as_record(edge)
        if record is None:
            continue
        graph_id = record.get("graph_id")
        source = _endpoint(record, "source")
        target = _endpoint(record, "target")
        if is_text(graph_id) and graph_id in graphs and source and target:
            graphs[graph_id].add_edge(source, target)
    return graphs


def _endpoint(record: Mapping[str, Any], endpoint: str) -> _NodeKey | None:
    node_type = record.get(f"{endpoint}_type")
    node_id = record.get(f"{endpoint}_id")
    if is_text(node_type) and is_text(node_id):
        return (node_type, node_id)
    return None


# ---------------------------------------------------------------------------
# Reglas
# ---------------------------------------------------------------------------


def _check_isolated(graph_id: str, graph: _InstanceGraph, context: _Context) -> Iterator[Finding]:
    """CON-01 y CON-02: nodos aislados, con o sin excepción admitida."""
    isolated: dict[str, list[str]] = defaultdict(list)
    excepted: dict[tuple[str, str], list[str]] = defaultdict(list)
    for key in sorted(graph.attributes):
        if graph.neighbours.get(key):
            continue
        node_type, node_id = key
        exception = next(
            (
                exception
                for exception in _ISOLATION_EXCEPTIONS
                if exception.applies(node_type, graph.attributes[key], context)
            ),
            None,
        )
        if exception is None:
            isolated[node_type].append(node_id)
        else:
            excepted[(node_type, exception.exception_id)].append(node_id)

    for node_type in sorted(isolated, key=node_type_sort_key):
        node_ids = isolated[node_type]
        yield Finding(
            rule_id="CON-01",
            severity=Severity.WARNING,
            graph_id=graph_id,
            location={"node_type": node_type, "node_ids": node_ids},
            expected="al menos una arista hacia otro nodo, o una excepción admitida",
            observed=f"{len(node_ids)} nodo(s) aislado(s)",
            message=(
                f"{len(node_ids)} nodo(s) {node_type} no tienen aristas hacia otros nodos: "
                f"{', '.join(node_ids)}."
            ),
        )

    for node_type, exception_id in sorted(
        excepted, key=lambda item: (node_type_sort_key(item[0]), item[1])
    ):
        node_ids = excepted[(node_type, exception_id)]
        yield Finding(
            rule_id="CON-02",
            severity=Severity.INFO,
            graph_id=graph_id,
            location={"node_type": node_type, "node_ids": node_ids, "exception": exception_id},
            expected=f"aislamiento admitido por la excepción {exception_id}",
            observed=f"{len(node_ids)} nodo(s) aislado(s) por diseño",
            message=(
                f"{len(node_ids)} nodo(s) {node_type} aislados corresponden a la excepción "
                f"{exception_id}: {', '.join(node_ids)}."
            ),
        )


def _check_unreferenced_types(graph_id: str, graph: _InstanceGraph) -> Iterator[Finding]:
    """CON-03: tipos con nodos que ninguna arista referencia."""
    counts: dict[str, int] = defaultdict(int)
    for node_type, _ in graph.attributes:
        counts[node_type] += 1
    for node_type in sorted(counts, key=node_type_sort_key):
        if node_type in graph.referenced_types:
            continue
        yield Finding(
            rule_id="CON-03",
            severity=Severity.WARNING,
            graph_id=graph_id,
            location={"node_type": node_type, "node_count": counts[node_type]},
            expected="al menos una arista que referencie el tipo",
            observed=f"{counts[node_type]} nodo(s) y ninguna arista",
            message=(
                f"El tipo {node_type} tiene {counts[node_type]} nodo(s), pero ninguna arista "
                "de la instancia lo referencia."
            ),
        )


def _composition(component: list[_NodeKey]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for node_type, _ in component:
        counts[node_type] += 1
    return {node_type: counts[node_type] for node_type in sorted(counts, key=node_type_sort_key)}


def _check_components(graph_id: str, graph: _InstanceGraph) -> Iterator[Finding]:
    """CON-04: más de un componente conexo con dos o más nodos."""
    components = [component for component in graph.components() if len(component) >= 2]
    if len(components) <= 1:
        return
    described = [
        {
            "size": len(component),
            "node_types": _composition(component),
            "nodes": [[node_type, node_id] for node_type, node_id in component],
        }
        for component in components
    ]
    sizes = ", ".join(str(len(component)) for component in components)
    yield Finding(
        rule_id="CON-04",
        severity=Severity.WARNING,
        graph_id=graph_id,
        location={"component_count": len(components), "components": described},
        expected="un solo componente conexo con dos o más nodos",
        observed=f"{len(components)} componentes: {describe([d['node_types'] for d in described])}",
        message=(
            f"La instancia {graph_id} tiene {len(components)} componentes conexos con dos o más "
            f"nodos (tamaños {sizes})."
        ),
    )


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def find_connectivity_findings(
    nodes: Iterable[Node | Mapping[str, Any]],
    edges: Iterable[Edge | Mapping[str, Any]],
    *,
    metadata: Mapping[str, Any] | None = None,
) -> list[Finding]:
    """Evalúa CON-01 a CON-04, con la excepción X-01, y devuelve todos los hallazgos.

    `nodes` y `edges` pueden ser registros del paquete de datos o diccionarios con la forma de
    una línea JSONL. Sus defectos propios los evalúan `find_node_findings` y
    `find_edge_findings`; aquí solo determinan la estructura del grafo. `metadata` es el
    contenido de `metadata.json` y solo aporta `non_modulating_control_labels` a X-01.

    Ningún hallazgo es `ERROR`. Las instancias se recorren por `graph_id` y, dentro de cada una,
    los hallazgos siguen el orden de las reglas; el resultado no depende del orden de entrada.
    """
    context = _context(metadata)
    graphs = _build_graphs(nodes, edges)
    findings: list[Finding] = []
    for graph_id in sorted(graphs):
        graph = graphs[graph_id]
        findings.extend(_check_isolated(graph_id, graph, context))
        findings.extend(_check_unreferenced_types(graph_id, graph))
        findings.extend(_check_components(graph_id, graph))
    return findings
