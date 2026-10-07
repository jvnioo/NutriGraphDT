"""Validación de aristas y consistencia de relaciones (VG-03).

Implementa las reglas EDG-01 a EDG-13 de `docs/graph-integrity-rules.md` sobre los registros de
`edges.jsonl`, antes de construir tensores. Cada incumplimiento se informa como un `Finding` con
su regla, severidad y ubicación. Se informan todos los hallazgos, no solo el primero.

El validador solo lee los registros: no crea, repara ni elimina aristas. Tampoco interpreta
biología: una arista sintética válida no es evidencia de la relación que representa.

Acepta objetos `Edge` y `Node` o diccionarios con la forma de una línea JSONL. Así puede evaluar
registros que `load_dataset` rechazaría en el primer error. Todas las relaciones son dirigidas:
la tupla `(source_type, relation_type, target_type)` fija la dirección, y el catálogo de
relaciones permitidas es `ALLOWED_RELATIONS` de DS-03, que transcribe DS-01.

Criterios de aplicación de la especificación:

- EDG-01 solo se evalúa si los tres tipos de la tupla son cadenas no vacías. Si no lo son,
  EDG-03 ya informa el campo.
- EDG-02 se evalúa aunque la tupla no esté permitida, salvo en un extremo cuyo tipo no es uno de
  los ocho tipos del contrato: ese defecto ya lo informa EDG-01. Un extremo que solo existe en
  otra instancia no resuelve, y el hallazgo indica en qué instancias existe.
- EDG-03 también informa un registro que no es un objeto. EDG-04 solo se evalúa si
  `evidence_status` es uno de los estados permitidos: un estado desconocido ya es EDG-03.
- EDG-05 exige que `attributes` sea un objeto, como NOD-05 en los nodos. Los atributos
  obligatorios solo se evalúan en tuplas permitidas, porque dependen de la relación. Un atributo
  `str` debe ser una cadena no vacía y un `number`, un número finito no booleano. Las aristas no
  tienen `missing_mask`, así que un valor `null` incumple EDG-05.
- EDG-06, EDG-07, EDG-08 y EDG-12 solo comparan valores que EDG-05 aceptó. EDG-07 y EDG-08
  requieren además que el nodo exista una sola vez en la instancia (si se repite, NOD-03 informa
  el defecto y la comparación sería ambigua) y que su valor sea una cadena no vacía (un valor
  ausente lo evalúan NOD-07 y NOD-08).
- EDG-09 y EDG-10 agrupan las aristas por instancia, tupla y extremos, aunque la tupla no esté
  permitida, siempre que esos campos y `evidence_id` sean cadenas no vacías.
- EDG-12 solo se evalúa si se entregan los metadatos del dataset. Un vocabulario que no está
  declarado en ellos se trata como vacío.
- EDG-13 se evalúa en tuplas permitidas cuyo `attributes` es un objeto: son las únicas en las
  que el contrato de la relación define qué claves admite.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal

from nutrigraphdt.data.synthetic.edges import (
    ADDITIVE_MODULATES_FUNCTION,
    ADDITIVE_MODULATES_TAXON,
    ALLOWED_RELATIONS,
    DIET_PROVIDES_SUBSTRATE,
    EVIDENCE_STATUSES,
    FUNCTION_CROSS_FEEDS_FUNCTION,
    FUNCTION_PRODUCES_METABOLITE,
    HOST_EXHIBITS_PHENOTYPE,
    METABOLITE_ASSOCIATED_WITH_PHENOTYPE,
    METABOLITE_MEASURED_IN_HOST,
    SUBSTRATE_AVAILABLE_TO_TAXON,
    SYNTHETIC_EVIDENCE_STATUS,
    TAXON_HAS_CAPACITY_FUNCTION,
    TAXON_INTERACTS_WITH_TAXON,
    Edge,
    EdgeType,
    RelationSpec,
)
from nutrigraphdt.data.synthetic.nodes import Node, NodeType
from nutrigraphdt.graph.validation._common import (
    ABSENT,
    as_record,
    declared_vocabularies,
    describe,
    is_finite_number,
    is_text,
)
from nutrigraphdt.graph.validation.findings import Finding, Severity

Endpoint = Literal["source", "target"]

_COMMON_FIELDS: tuple[str, ...] = (
    "graph_id",
    "source_type",
    "source_id",
    "relation_type",
    "target_type",
    "target_id",
    "evidence_id",
    "evidence_status",
    "evidence_method",
)
"""Campos comunes del contrato de arista que deben ser cadenas no vacías (EDG-03)."""

_NODE_MAGNITUDES: Mapping[EdgeType, tuple[Endpoint, str]] = MappingProxyType(
    {
        METABOLITE_MEASURED_IN_HOST: ("source", "sample_matrix"),
        DIET_PROVIDES_SUBSTRATE: ("target", "unit"),
        HOST_EXHIBITS_PHENOTYPE: ("target", "timepoint"),
    }
)
"""Atributos de arista que describen una magnitud de uno de sus nodos (EDG-07). En los tres
casos el atributo tiene el mismo nombre en la arista y en el nodo."""

_ANNOTATION_SOURCE: tuple[Endpoint, str] = ("target", "annotation_source")
"""Atributo de `has_capacity` que se compara con la función destino (EDG-08)."""

_SELF_LOOP_RELATIONS: frozenset[EdgeType] = frozenset(
    {TAXON_INTERACTS_WITH_TAXON, FUNCTION_CROSS_FEEDS_FUNCTION}
)
"""Relaciones en las que un autolazo se informa como advertencia (EDG-11)."""

OBSERVATION_METHODS: frozenset[str] = frozenset({"measurement"})
"""`evidence_method` que respaldan una arista `observed` (EDG-04, reglas 1.2.0 **(P)**)."""

REAL_EVIDENCE_POLICY: Mapping[str, tuple[frozenset[EdgeType], Severity | None]] = MappingProxyType(
    {
        # Medición directa en el animal (Biolink: knowledge_level = observation).
        "observed": (
            frozenset({METABOLITE_MEASURED_IN_HOST, HOST_EXHIBITS_PHENOTYPE}),
            None,
        ),
        # Afirmación de una base curada o de una tabla de composición.
        "annotated": (
            frozenset({DIET_PROVIDES_SUBSTRATE, TAXON_HAS_CAPACITY_FUNCTION}),
            None,
        ),
        # Resultado de un modelo o de un análisis: se entrega, pero se revisa.
        "inferred": (
            frozenset(
                {
                    SUBSTRATE_AVAILABLE_TO_TAXON,
                    TAXON_HAS_CAPACITY_FUNCTION,
                    FUNCTION_PRODUCES_METABOLITE,
                    DIET_PROVIDES_SUBSTRATE,
                }
            ),
            Severity.WARNING,
        ),
        # Solo en las relaciones que el esquema v1 declara hipotéticas.
        "hypothetical": (
            frozenset(
                {
                    ADDITIVE_MODULATES_TAXON,
                    ADDITIVE_MODULATES_FUNCTION,
                    METABOLITE_ASSOCIATED_WITH_PHENOTYPE,
                    TAXON_INTERACTS_WITH_TAXON,
                    FUNCTION_CROSS_FEEDS_FUNCTION,
                }
            ),
            Severity.WARNING,
        ),
    }
)
"""Estados de evidencia admitidos en datos reales por relación, y la severidad con que se
informan cuando se admiten (`None`: sin hallazgo). Propuesta provisional de Desarrollo
(`docs/evidence-and-scenario-proposal.md`), pendiente de contraste con Investigación."""

_VOCABULARY_ATTRIBUTES: Mapping[EdgeType, tuple[str, ...]] = MappingProxyType(
    {TAXON_INTERACTS_WITH_TAXON: ("interaction_type",)}
)
"""Atributos que deben pertenecer a un vocabulario declarado en `metadata.json` (EDG-12)."""

_KIND_DESCRIPTIONS: Mapping[str, str] = MappingProxyType(
    {"str": "una cadena no vacía", "number": "un número finito (no booleano)"}
)

_KNOWN_NODE_TYPES: frozenset[str] = frozenset(node_type.value for node_type in NodeType)

_NodeKey = tuple[str, str, str]
"""`(graph_id, node_type, node_id)`."""


# ---------------------------------------------------------------------------
# Índice de nodos
# ---------------------------------------------------------------------------


class _NodeIndex:
    """Nodos por `(graph_id, node_type, node_id)`, con sus atributos."""

    def __init__(self, nodes: Iterable[object]) -> None:
        self._attributes: dict[_NodeKey, list[object]] = defaultdict(list)
        self._graphs: dict[tuple[str, str], set[str]] = defaultdict(set)
        for node in nodes:
            record = as_record(node)
            if record is None:
                continue
            graph_id = record.get("graph_id")
            node_type = record.get("node_type")
            node_id = record.get("node_id")
            if is_text(graph_id) and is_text(node_type) and is_text(node_id):
                self._attributes[(graph_id, node_type, node_id)].append(record.get("attributes"))
                self._graphs[(node_type, node_id)].add(graph_id)

    def __contains__(self, key: _NodeKey) -> bool:
        return key in self._attributes

    def graphs_with(self, node_type: str, node_id: str) -> list[str]:
        """Instancias en las que existe un nodo con ese tipo e identificador."""
        return sorted(self._graphs.get((node_type, node_id), ()))

    def unique_attributes(self, key: _NodeKey) -> Mapping[str, Any] | None:
        """Atributos del nodo si existe una sola vez y son un objeto; si no, `None`."""
        found = self._attributes.get(key, [])
        if len(found) != 1 or not isinstance(found[0], dict):
            return None
        return found[0]


# ---------------------------------------------------------------------------
# Referencia a una arista
# ---------------------------------------------------------------------------


def _text_or_none(record: Mapping[str, Any], name: str) -> str | None:
    value = record.get(name)
    return value if is_text(value) else None


@dataclass(frozen=True)
class _EdgeRef:
    """Identifica un registro de arista en los hallazgos, aunque sus campos sean inválidos."""

    index: int
    graph_id: str | None
    source_type: str | None
    source_id: str | None
    relation_type: str | None
    target_type: str | None
    target_id: str | None
    evidence_id: str | None

    @classmethod
    def of(cls, index: int, record: Mapping[str, Any]) -> _EdgeRef:
        return cls(
            index=index,
            graph_id=_text_or_none(record, "graph_id"),
            source_type=_text_or_none(record, "source_type"),
            source_id=_text_or_none(record, "source_id"),
            relation_type=_text_or_none(record, "relation_type"),
            target_type=_text_or_none(record, "target_type"),
            target_id=_text_or_none(record, "target_id"),
            evidence_id=_text_or_none(record, "evidence_id"),
        )

    @property
    def edge_type(self) -> EdgeType | None:
        """Tupla de la arista si sus tres tipos son cadenas no vacías."""
        if self.source_type is None or self.relation_type is None or self.target_type is None:
            return None
        return (self.source_type, self.relation_type, self.target_type)

    def endpoint(self, endpoint: Endpoint) -> tuple[str | None, str | None]:
        """`(node_type, node_id)` del extremo indicado."""
        if endpoint == "source":
            return self.source_type, self.source_id
        return self.target_type, self.target_id

    def finding(
        self,
        rule_id: str,
        expected: str,
        observed: str,
        message: str,
        *,
        severity: Severity = Severity.ERROR,
        **location: Any,
    ) -> Finding:
        base: dict[str, Any] = {"edge_record_index": self.index}
        edge_type = self.edge_type
        if edge_type is not None:
            base["edge_type"] = list(edge_type)
        if self.source_id is not None:
            base["source_id"] = self.source_id
        if self.target_id is not None:
            base["target_id"] = self.target_id
        label = f"en la posición {self.index}"
        if self.source_id is not None and self.target_id is not None:
            label += f" ({self.source_id} -{self.relation_type or '?'}-> {self.target_id})"
        return Finding(
            rule_id=rule_id,
            severity=severity,
            graph_id=self.graph_id,
            location={**base, **location},
            expected=expected,
            observed=observed,
            message=f"Arista {label}: {message}",
        )


# ---------------------------------------------------------------------------
# Reglas evaluadas registro a registro
# ---------------------------------------------------------------------------


def _check_relation(ref: _EdgeRef) -> Iterator[Finding]:
    """EDG-01: la tupla es una de las relaciones permitidas."""
    edge_type = ref.edge_type
    if edge_type is None or edge_type in ALLOWED_RELATIONS:
        return
    source_type, relation_type, target_type = edge_type
    hint = ""
    if (target_type, relation_type, source_type) in ALLOWED_RELATIONS:
        hint = " Es la inversa de una relación permitida, y no se admiten inversas implícitas."
    yield ref.finding(
        "EDG-01",
        "una de las once tuplas (source_type, relation_type, target_type) de DS-01",
        describe(list(edge_type)),
        f"la tupla ({source_type}, {relation_type}, {target_type}) no es una relación "
        f"permitida.{hint}",
    )


def _check_endpoints(ref: _EdgeRef, nodes: _NodeIndex) -> Iterator[Finding]:
    """EDG-02: los extremos existen con el tipo declarado en la misma instancia."""
    if ref.graph_id is None:
        return
    for endpoint in ("source", "target"):
        node_type, node_id = ref.endpoint(endpoint)
        if node_type is None or node_id is None:
            continue
        if node_type not in _KNOWN_NODE_TYPES and ref.edge_type is not None:
            # EDG-01 ya informa una tupla con un tipo de nodo fuera del contrato.
            continue
        if (ref.graph_id, node_type, node_id) in nodes:
            continue
        elsewhere = nodes.graphs_with(node_type, node_id)
        observed = "no existe en la instancia"
        if elsewhere:
            observed += f"; existe en {describe(elsewhere)}"
        yield ref.finding(
            "EDG-02",
            f"un nodo {node_type} {node_id} en la instancia {ref.graph_id}",
            observed,
            f"el extremo {endpoint} {node_id} no existe como nodo {node_type} de la instancia.",
            endpoint=endpoint,
            node_type=node_type,
            node_id=node_id,
        )


def _check_evidence(
    ref: _EdgeRef, status: str, method: object, is_synthetic: bool
) -> Iterator[Finding]:
    """EDG-04: estado de evidencia admitido según el origen del dataset y la relación."""
    if is_synthetic:
        if status != SYNTHETIC_EVIDENCE_STATUS:
            yield ref.finding(
                "EDG-04",
                describe(SYNTHETIC_EVIDENCE_STATUS),
                describe(status),
                f"evidence_status {status!r} en un dataset sintético: toda arista sintética "
                "declara 'synthetic'.",
                field="evidence_status",
            )
        return
    if status == SYNTHETIC_EVIDENCE_STATUS:
        yield ref.finding(
            "EDG-04",
            "un estado de evidencia real",
            describe(status),
            "evidence_status 'synthetic' en un dataset real: una arista inventada no puede "
            "presentarse como dato real.",
            field="evidence_status",
        )
        return
    relations, severity = REAL_EVIDENCE_POLICY[status]
    edge_type = ref.edge_type
    if edge_type not in relations:
        yield ref.finding(
            "EDG-04",
            f"una relación de {describe(sorted('|'.join(r) for r in relations))}",
            describe("|".join(edge_type) if edge_type else None),
            f"evidence_status {status!r} no está admitido en esta relación.",
            field="evidence_status",
        )
    elif status == "observed" and method not in OBSERVATION_METHODS:
        yield ref.finding(
            "EDG-04",
            f"evidence_method en {describe(sorted(OBSERVATION_METHODS))}",
            describe(method),
            "Una arista 'observed' debe declarar un método de medición.",
            field="evidence_method",
        )
    elif severity is not None:
        yield ref.finding(
            "EDG-04",
            "evidencia observada o anotada",
            describe(status),
            f"Arista {status!r}: se entrega, pero no es una observación ni una anotación "
            "curada; revise su método antes de interpretarla.",
            severity=severity,
            field="evidence_status",
        )


def _check_common_fields(
    ref: _EdgeRef, record: Mapping[str, Any], is_synthetic: bool
) -> Iterator[Finding]:
    """EDG-03 y EDG-04: campos comunes y estado de evidencia."""
    for name in _COMMON_FIELDS:
        value = record.get(name, ABSENT)
        if not is_text(value):
            yield ref.finding(
                "EDG-03",
                "una cadena no vacía",
                describe(value),
                f"'{name}' debe ser una cadena no vacía.",
                field=name,
            )

    status = record.get("evidence_status")
    if not is_text(status):
        return
    if status not in EVIDENCE_STATUSES:
        yield ref.finding(
            "EDG-03",
            f"uno de {describe(sorted(EVIDENCE_STATUSES))}",
            describe(status),
            f"evidence_status {status!r} no es un estado permitido.",
            field="evidence_status",
        )
    else:
        yield from _check_evidence(ref, status, record.get("evidence_method"), is_synthetic)


def _matches(kind: str, value: object) -> bool:
    if kind == "str":
        return is_text(value)
    return is_finite_number(value)


def _check_attributes(
    ref: _EdgeRef, spec: RelationSpec | None, attributes: object
) -> tuple[list[Finding], dict[str, Any]]:
    """EDG-05: devuelve los hallazgos y los atributos obligatorios que sí son válidos."""
    if not isinstance(attributes, dict):
        finding = ref.finding(
            "EDG-05",
            "un objeto",
            describe(attributes),
            "'attributes' debe ser un objeto.",
            field="attributes",
        )
        return [finding], {}
    if spec is None:
        return [], {}

    findings: list[Finding] = []
    valid: dict[str, Any] = {}
    for name, kind in spec.required_attributes.items():
        expected = _KIND_DESCRIPTIONS[kind]
        value = attributes.get(name, ABSENT)
        if value is ABSENT:
            findings.append(
                ref.finding(
                    "EDG-05",
                    expected,
                    describe(value),
                    f"falta el atributo obligatorio '{name}'.",
                    attribute=name,
                )
            )
        elif not _matches(kind, value):
            findings.append(
                ref.finding(
                    "EDG-05",
                    expected,
                    describe(value),
                    f"el atributo '{name}' no es {expected}.",
                    attribute=name,
                )
            )
        else:
            valid[name] = value
    return findings, valid


def _node_attribute(
    ref: _EdgeRef, nodes: _NodeIndex, endpoint: Endpoint, name: str
) -> tuple[str, str, str] | None:
    """`(node_type, node_id, valor)` del atributo de un extremo, si puede compararse."""
    node_type, node_id = ref.endpoint(endpoint)
    if ref.graph_id is None or node_type is None or node_id is None:
        return None
    attributes = nodes.unique_attributes((ref.graph_id, node_type, node_id))
    if attributes is None:
        return None
    value = attributes.get(name)
    if not is_text(value):
        return None
    return node_type, node_id, value


def _check_node_consistency(
    ref: _EdgeRef, edge_type: EdgeType, valid: Mapping[str, Any], nodes: _NodeIndex
) -> Iterator[Finding]:
    """EDG-06, EDG-07 y EDG-08: coherencia de los atributos de arista con los nodos."""
    substrate_id = valid.get("substrate_id")
    if (
        edge_type == FUNCTION_CROSS_FEEDS_FUNCTION
        and substrate_id is not None
        and ref.graph_id is not None
        and (ref.graph_id, NodeType.SUBSTRATE.value, substrate_id) not in nodes
    ):
        yield ref.finding(
            "EDG-06",
            f"el node_id de un nodo substrate de la instancia {ref.graph_id}",
            describe(substrate_id),
            f"substrate_id {substrate_id!r} no identifica un nodo substrate de la instancia.",
            attribute="substrate_id",
        )

    magnitude = _NODE_MAGNITUDES.get(edge_type)
    if magnitude is not None:
        endpoint, name = magnitude
        edge_value = valid.get(name)
        node = _node_attribute(ref, nodes, endpoint, name)
        if edge_value is not None and node is not None and node[2] != edge_value:
            node_type, node_id, node_value = node
            yield ref.finding(
                "EDG-07",
                f"{describe(node_value)}, el valor de '{name}' en el nodo {node_type} {node_id}",
                describe(edge_value),
                f"'{name}' de la arista ({edge_value!r}) difiere del nodo {node_type} "
                f"{node_id} ({node_value!r}).",
                attribute=name,
                node_type=node_type,
                node_id=node_id,
                node_value=node_value,
            )

    if edge_type == TAXON_HAS_CAPACITY_FUNCTION:
        endpoint, name = _ANNOTATION_SOURCE
        edge_value = valid.get(name)
        node = _node_attribute(ref, nodes, endpoint, name)
        if edge_value is not None and node is not None and node[2] != edge_value:
            node_type, node_id, node_value = node
            yield ref.finding(
                "EDG-08",
                f"{describe(node_value)}, el valor de '{name}' en el nodo {node_type} {node_id}",
                describe(edge_value),
                f"'{name}' de la arista ({edge_value!r}) difiere del de la función {node_id} "
                f"({node_value!r}).",
                severity=Severity.WARNING,
                attribute=name,
                node_type=node_type,
                node_id=node_id,
                node_value=node_value,
            )


def _check_self_loop(ref: _EdgeRef, edge_type: EdgeType) -> Iterator[Finding]:
    """EDG-11: autolazo en `interacts_with` o `cross_feeds`."""
    if (
        edge_type in _SELF_LOOP_RELATIONS
        and ref.source_id is not None
        and ref.source_id == ref.target_id
    ):
        yield ref.finding(
            "EDG-11",
            "source_id distinto de target_id",
            describe(ref.source_id),
            f"autolazo en {edge_type[1]}.",
            severity=Severity.WARNING,
        )


def _check_vocabularies(
    ref: _EdgeRef,
    edge_type: EdgeType,
    valid: Mapping[str, Any],
    vocabularies: Mapping[str, frozenset[str]],
) -> Iterator[Finding]:
    """EDG-12 (provisional): categorías dentro de los vocabularios declarados."""
    for name in _VOCABULARY_ATTRIBUTES.get(edge_type, ()):
        value = valid.get(name)
        declared = vocabularies.get(name, frozenset())
        if value is not None and value not in declared:
            yield ref.finding(
                "EDG-12",
                f"uno de {describe(sorted(declared))}, declarado en metadata.json",
                describe(value),
                f"'{name}' no pertenece al vocabulario declarado.",
                severity=Severity.WARNING,
                attribute=name,
            )


def _check_edge(
    ref: _EdgeRef,
    record: Mapping[str, Any],
    nodes: _NodeIndex,
    vocabularies: Mapping[str, frozenset[str]] | None,
    is_synthetic: bool,
) -> Iterator[Finding]:
    edge_type = ref.edge_type
    spec = ALLOWED_RELATIONS.get(edge_type) if edge_type is not None else None

    yield from _check_relation(ref)
    yield from _check_endpoints(ref, nodes)
    yield from _check_common_fields(ref, record, is_synthetic)
    findings, valid = _check_attributes(ref, spec, record.get("attributes", ABSENT))
    yield from findings

    # EDG-06 a EDG-08 y EDG-11 a EDG-13 son propias de relaciones permitidas concretas.
    if edge_type is None or spec is None:
        return
    yield from _check_node_consistency(ref, edge_type, valid, nodes)
    yield from _check_self_loop(ref, edge_type)
    if vocabularies is not None:
        yield from _check_vocabularies(ref, edge_type, valid, vocabularies)
    yield from _check_extra_attributes(ref, spec, record.get("attributes", ABSENT))


def _check_extra_attributes(
    ref: _EdgeRef, spec: RelationSpec, attributes: object
) -> Iterator[Finding]:
    """EDG-13: claves de `attributes` fuera de los atributos de la relación."""
    if not isinstance(attributes, dict):
        # EDG-05 ya informa unos atributos que no son un objeto.
        return
    extra = sorted(str(key) for key in attributes if key not in spec.required_attributes)
    if extra:
        yield ref.finding(
            "EDG-13",
            "solo los atributos de la relación en el contrato",
            describe(extra),
            f"atributos fuera del contrato de {spec.edge_type[1]}: {', '.join(extra)}.",
            severity=Severity.WARNING,
            attributes=extra,
        )


# ---------------------------------------------------------------------------
# Reglas evaluadas sobre el conjunto
# ---------------------------------------------------------------------------


def _check_duplicates(refs: Iterable[_EdgeRef]) -> Iterator[Finding]:
    """EDG-09 y EDG-10: aristas repetidas sobre la misma tupla y los mismos extremos."""
    groups: dict[tuple[str, EdgeType, str, str], list[_EdgeRef]] = defaultdict(list)
    for ref in refs:
        edge_type = ref.edge_type
        if (
            ref.graph_id is not None
            and edge_type is not None
            and ref.source_id is not None
            and ref.target_id is not None
            and ref.evidence_id is not None
        ):
            groups[(ref.graph_id, edge_type, ref.source_id, ref.target_id)].append(ref)

    for (graph_id, edge_type, source_id, target_id), members in groups.items():
        if len(members) < 2:
            continue
        location: dict[str, Any] = {
            "edge_type": list(edge_type),
            "source_id": source_id,
            "target_id": target_id,
        }
        label = f"{source_id} -{edge_type[1]}-> {target_id}"
        by_evidence: dict[str, list[int]] = defaultdict(list)
        for ref in members:
            if ref.evidence_id is not None:
                by_evidence[ref.evidence_id].append(ref.index)

        for evidence_id, indices in by_evidence.items():
            if len(indices) > 1:
                yield Finding(
                    rule_id="EDG-09",
                    severity=Severity.ERROR,
                    graph_id=graph_id,
                    location={
                        **location,
                        "evidence_id": evidence_id,
                        "edge_record_indices": indices,
                    },
                    expected="una sola arista por tupla, extremos y evidence_id",
                    observed=f"{len(indices)} repeticiones",
                    message=(
                        f"La arista {label} con evidence_id {evidence_id} se repite "
                        f"{len(indices)} veces."
                    ),
                )

        if len(by_evidence) > 1:
            evidence_ids = sorted(by_evidence)
            yield Finding(
                rule_id="EDG-10",
                severity=Severity.WARNING,
                graph_id=graph_id,
                location={
                    **location,
                    "evidence_ids": evidence_ids,
                    "edge_record_indices": [ref.index for ref in members],
                },
                expected="una sola procedencia por tupla y extremos",
                observed=f"{len(evidence_ids)} evidence_id distintos",
                message=(
                    f"La arista {label} aparece con {len(evidence_ids)} evidence_id distintos: "
                    f"{', '.join(evidence_ids)}."
                ),
            )


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def _real_graph_ids(
    metadata: Mapping[str, Any] | None,
    instances: Iterable[object] | None,
    edges: Iterable[Edge | Mapping[str, Any]],
) -> frozenset[str | None]:
    """`graph_id` de las instancias reales, para elegir la política de evidencia (EDG-04)."""
    if instances is not None:
        real: set[str | None] = set()
        for instance in instances:
            record = as_record(instance)
            if record is not None and record.get("is_synthetic") is False:
                graph_id = record.get("graph_id")
                if is_text(graph_id):
                    real.add(graph_id)
        return frozenset(real)
    if isinstance(metadata, Mapping) and metadata.get("is_synthetic") is False:
        return frozenset(
            _text_or_none(record, "graph_id")
            for record in (as_record(edge) for edge in edges)
            if record is not None
        )
    return frozenset()


def find_edge_findings(
    nodes: Iterable[Node | Mapping[str, Any]],
    edges: Iterable[Edge | Mapping[str, Any]],
    *,
    metadata: Mapping[str, Any] | None = None,
    instances: Iterable[object] | None = None,
) -> list[Finding]:
    """Evalúa EDG-01 a EDG-13 y devuelve todos los hallazgos.

    EDG-04 aplica la política de evidencia según el origen de la instancia de cada arista:
    `instances` (los registros de instancia) dice cuáles son reales (`is_synthetic = false`).
    Sin `instances`, el origen se toma de `metadata["is_synthetic"]`; sin ninguno de los dos,
    se aplica la política sintética, la más estricta.

    `nodes` y `edges` pueden ser registros del paquete de datos o diccionarios con la forma de
    una línea JSONL. Los nodos solo se usan para resolver extremos y comparar atributos: sus
    propios defectos los evalúa `find_node_findings`. `metadata` es el contenido de
    `metadata.json`; sin él, EDG-12 no se evalúa. La ubicación de cada hallazgo usa la posición
    de la arista en la secuencia recibida (`edge_record_index`).

    Una lista vacía indica que no hay hallazgos. Un hallazgo `ADVERTENCIA` no invalida el grafo.
    Para una misma entrada, el orden de los hallazgos es determinista.
    """
    node_index = _NodeIndex(nodes)
    vocabularies = declared_vocabularies(metadata)
    edges = list(edges)
    real_graph_ids = _real_graph_ids(metadata, instances, edges)

    findings: list[Finding] = []
    refs: list[_EdgeRef] = []
    for index, edge in enumerate(edges):
        record = as_record(edge)
        if record is None:
            findings.append(
                Finding(
                    rule_id="EDG-03",
                    severity=Severity.ERROR,
                    graph_id=None,
                    location={"edge_record_index": index},
                    expected="un objeto con los campos del contrato de arista",
                    observed=type(edge).__name__,
                    message=f"La arista en la posición {index} no es un objeto.",
                )
            )
            continue
        ref = _EdgeRef.of(index, record)
        refs.append(ref)
        is_synthetic = ref.graph_id not in real_graph_ids
        findings.extend(_check_edge(ref, record, node_index, vocabularies, is_synthetic))

    findings.extend(_check_duplicates(refs))
    return findings
