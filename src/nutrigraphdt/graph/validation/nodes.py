"""Validación de nodos, identificadores y atributos obligatorios (VG-02).

Implementa las reglas NOD-01 a NOD-12 e INS-01 a INS-04 de `docs/graph-integrity-rules.md`
sobre los registros de `instances.jsonl` y `nodes.jsonl`, antes de construir tensores. Cada
incumplimiento se informa como un `Finding` con su regla, severidad y ubicación. Se informan
todos los hallazgos, no solo el primero.

El validador solo lee los registros: no corrige, completa ni elimina nodos. Tampoco interpreta
biología. Comprueba estructura, tipos e identificadores, no rangos fisiológicos.

Acepta objetos `Node` e `InstanceRecord` o diccionarios con la forma de una línea JSONL. Así
puede evaluar registros que `load_dataset` rechazaría en el primer error.

Criterios de aplicación de la especificación:

- Un atributo obligatorio de tipo `str`, y cada elemento de `ingredients`, debe ser una cadena
  no vacía: DS-01 prohíbe representar un valor ausente con una cadena vacía.
- Un atributo obligatorio con valor `null` no incumple NOD-05, porque es un valor ausente.
  NOD-07 exige marcarlo en `missing_mask` y NOD-08 lo informa.
- Las claves de `missing_mask` son rutas relativas a `attributes`. Una ruta con puntos, como
  `covariates.sex`, recorre objetos anidados.
- NOD-04 solo se evalúa en instancias existentes con `is_synthetic = true`. NOD-12 trata como no
  sintética cualquier instancia cuyo `is_synthetic` no sea `true`.
- NOD-11 solo se evalúa si se entregan los metadatos del dataset. Un vocabulario que no está
  declarado en ellos se trata como vacío.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final, Literal

from nutrigraphdt.data.synthetic.export import SCENARIO_IDS, SCHEMA_VERSION, InstanceRecord
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

AttributeKind = Literal["str", "number", "object", "list[str]", "list[object]"]
"""Tipo de intercambio JSON de un atributo obligatorio."""


def _kinds(**kinds: AttributeKind) -> Mapping[str, AttributeKind]:
    return MappingProxyType(kinds)


NODE_ATTRIBUTE_CONTRACT: Mapping[str, Mapping[str, AttributeKind]] = MappingProxyType(
    {
        NodeType.DIET.value: _kinds(
            name="str",
            ingredients="list[str]",
            composition="list[object]",
            source_version="str",
        ),
        NodeType.ADDITIVE.value: _kinds(
            category="str",
            substance="str",
            dose="number",
            dose_unit="str",
            control_label="str",
        ),
        NodeType.SUBSTRATE.value: _kinds(
            chemical_id="str",
            name="str",
            quantity="number",
            unit="str",
        ),
        NodeType.TAXON.value: _kinds(
            taxonomy_id="str",
            taxonomy_level="str",
            abundance="number",
            abundance_unit="str",
            quantification_method="str",
        ),
        NodeType.FUNCTION.value: _kinds(
            function_id="str",
            function_type="str",
            annotation_source="str",
            annotation_value="number",
            annotation_value_type="str",
            unit="str",
        ),
        NodeType.METABOLITE.value: _kinds(
            chemical_id="str",
            name="str",
            sample_matrix="str",
            concentration="number",
            unit="str",
        ),
        NodeType.HOST.value: _kinds(
            species="str",
            gut_segment="str",
            cohort_id="str",
            covariates="object",
        ),
        NodeType.PHENOTYPE.value: _kinds(
            trait="str",
            timepoint="str",
            value="number",
            unit="str",
        ),
    }
)
"""Atributos obligatorios por tipo de nodo, transcritos de la tabla "Tipos de nodo y
atributos" de `docs/synthetic-dataset-spec.md`."""

SYNTHETIC_ID_PREFIX: Final = "synthetic:"
"""Prefijo que exige NOD-04 a los identificadores de una instancia sintética."""

_INSTANCE_FIELDS: tuple[str, ...] = (
    "graph_id",
    "species",
    "gut_segment",
    "study_id",
    "sample_id",
    "scenario_id",
    "diet_treatment",
    "timepoint",
    "is_synthetic",
    "schema_version",
    "generator_version",
)
"""Campos obligatorios de un registro de `instances.jsonl` (contrato de instancia)."""

_INS02_FIELDS: frozenset[str] = frozenset({"is_synthetic", "schema_version"})
"""Campos cuyo valor evalúa INS-02; INS-01 solo comprueba que existan."""

_DOMAIN_ID_ATTRIBUTES: Mapping[str, str] = MappingProxyType(
    {
        NodeType.SUBSTRATE.value: "chemical_id",
        NodeType.TAXON.value: "taxonomy_id",
        NodeType.FUNCTION.value: "function_id",
        NodeType.METABOLITE.value: "chemical_id",
    }
)
"""Identificador de dominio de cada tipo que lo tiene (NOD-04)."""

_NON_NEGATIVE_ATTRIBUTES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        NodeType.ADDITIVE.value: ("dose",),
        NodeType.SUBSTRATE.value: ("quantity",),
        NodeType.TAXON.value: ("abundance",),
        NodeType.FUNCTION.value: ("annotation_value",),
        NodeType.METABOLITE.value: ("concentration",),
        NodeType.HOST.value: ("covariates.body_weight_g",),
    }
)
"""Magnitudes que físicamente no pueden ser negativas (NOD-10)."""

_VOCABULARY_ATTRIBUTES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {NodeType.FUNCTION.value: ("function_type", "annotation_value_type")}
)
"""Atributos que deben pertenecer a un vocabulario declarado en `metadata.json` (NOD-11)."""

_COMPOSITION_FIELDS: tuple[tuple[str, AttributeKind], ...] = (
    ("component_id", "str"),
    ("value", "number"),
    ("unit", "str"),
)
"""Campos obligatorios de cada elemento de `diet.composition` (NOD-06)."""

_KIND_DESCRIPTIONS: Mapping[AttributeKind, str] = MappingProxyType(
    {
        "str": "una cadena no vacía",
        "number": "un número finito (no booleano)",
        "object": "un objeto",
        "list[str]": "una lista de cadenas no vacías",
        "list[object]": "una lista",
    }
)

_KNOWN_NODE_TYPES: tuple[str, ...] = tuple(node_type.value for node_type in NodeType)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _matches(kind: AttributeKind, value: object) -> bool:
    if kind == "str":
        return is_text(value)
    if kind == "number":
        return is_finite_number(value)
    if kind == "object":
        return isinstance(value, dict)
    if kind == "list[str]":
        return isinstance(value, list) and all(is_text(item) for item in value)
    # Los elementos de `composition` los evalúa NOD-06.
    return isinstance(value, list)


def _resolve(attributes: Mapping[str, Any], path: str) -> object:
    """Lee el valor de una ruta relativa a `attributes`; `ABSENT` si no existe."""
    if path in attributes:
        return attributes[path]
    current: object = attributes
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return ABSENT
        current = current[part]
    return current


def _null_paths(attributes: Mapping[Any, Any], prefix: str = "") -> Iterator[str]:
    """Rutas de los valores `null` de `attributes`, recorriendo objetos anidados."""
    for key, value in attributes.items():
        path = f"{prefix}{key}"
        if value is None:
            yield path
        elif isinstance(value, dict):
            yield from _null_paths(value, f"{path}.")


def _non_finite_numbers(value: object, path: str) -> Iterator[tuple[str, float]]:
    """Números no finitos dentro de un valor compuesto, con su ruta."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _non_finite_numbers(item, f"{path}.{key}")
    elif isinstance(value, list):
        for position, item in enumerate(value):
            yield from _non_finite_numbers(item, f"{path}[{position}]")
    elif isinstance(value, float) and not math.isfinite(value):
        yield path, value


@dataclass(frozen=True)
class _KnownInstance:
    """Primera instancia registrada con un `graph_id` válido."""

    index: int
    record: Mapping[str, Any]

    @property
    def is_synthetic(self) -> bool:
        return self.record.get("is_synthetic") is True


@dataclass(frozen=True)
class _NodeRef:
    """Identifica un registro de nodo en los hallazgos, aunque sus campos sean inválidos."""

    index: int
    graph_id: str | None
    node_type: str | None
    node_id: str | None

    @classmethod
    def of(cls, index: int, record: Mapping[str, Any]) -> _NodeRef:
        graph_id = record.get("graph_id")
        node_type = record.get("node_type")
        node_id = record.get("node_id")
        return cls(
            index=index,
            graph_id=graph_id if is_text(graph_id) else None,
            node_type=node_type if is_text(node_type) else None,
            node_id=node_id if is_text(node_id) else None,
        )

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
        base: dict[str, Any] = {"node_index": self.index}
        if self.node_type is not None:
            base["node_type"] = self.node_type
        if self.node_id is not None:
            base["node_id"] = self.node_id
        label = self.node_id or f"en la posición {self.index}"
        return Finding(
            rule_id=rule_id,
            severity=severity,
            graph_id=self.graph_id,
            location={**base, **location},
            expected=expected,
            observed=observed,
            message=f"Nodo {label}: {message}",
        )


# ---------------------------------------------------------------------------
# Reglas de instancia (INS-01 a INS-03)
# ---------------------------------------------------------------------------


def _check_instance(index: int, record: Mapping[str, Any]) -> Iterator[Finding]:
    graph_id = record.get("graph_id")
    known_id = graph_id if is_text(graph_id) else None
    label = known_id or f"en la posición {index}"

    def finding(rule_id: str, field: str, expected: str, value: object, message: str) -> Finding:
        return Finding(
            rule_id=rule_id,
            severity=Severity.ERROR,
            graph_id=known_id,
            location={"instance_index": index, "field": field},
            expected=expected,
            observed=describe(value),
            message=f"Instancia {label}: {message}",
        )

    for name in _INSTANCE_FIELDS:
        value = record.get(name, ABSENT)
        if value is ABSENT:
            yield finding("INS-01", name, "campo presente", value, f"falta el campo '{name}'.")
        elif name in _INS02_FIELDS:
            continue
        elif name == "timepoint":
            if value is not None and not is_text(value):
                yield finding(
                    "INS-01",
                    name,
                    "una cadena no vacía o null",
                    value,
                    "'timepoint' debe ser una cadena no vacía o null.",
                )
        elif not is_text(value):
            yield finding(
                "INS-01",
                name,
                "una cadena no vacía",
                value,
                f"'{name}' debe ser una cadena no vacía.",
            )

    schema_version = record.get("schema_version", ABSENT)
    if schema_version is not ABSENT and schema_version != SCHEMA_VERSION:
        yield finding(
            "INS-02",
            "schema_version",
            describe(SCHEMA_VERSION),
            schema_version,
            f"schema_version {describe(schema_version)} no es compatible con {SCHEMA_VERSION}.",
        )
    is_synthetic = record.get("is_synthetic", ABSENT)
    if is_synthetic is not ABSENT and not isinstance(is_synthetic, bool):
        yield finding(
            "INS-02", "is_synthetic", "un booleano", is_synthetic, "'is_synthetic' no es booleano."
        )

    scenario_id = record.get("scenario_id")
    if is_text(scenario_id) and scenario_id not in SCENARIO_IDS:
        yield finding(
            "INS-03",
            "scenario_id",
            f"uno de {describe(sorted(SCENARIO_IDS))}",
            scenario_id,
            f"scenario_id {scenario_id!r} no es un escenario permitido.",
        )


def _check_instances(
    instances: Iterable[object],
) -> tuple[list[Finding], dict[str, _KnownInstance]]:
    findings: list[Finding] = []
    known: dict[str, _KnownInstance] = {}
    positions: dict[str, list[int]] = defaultdict(list)
    for index, instance in enumerate(instances):
        record = as_record(instance)
        if record is None:
            findings.append(
                Finding(
                    rule_id="INS-01",
                    severity=Severity.ERROR,
                    graph_id=None,
                    location={"instance_index": index},
                    expected="un objeto con los campos de instancia",
                    observed=type(instance).__name__,
                    message=f"La instancia en la posición {index} no es un objeto.",
                )
            )
            continue
        findings.extend(_check_instance(index, record))
        graph_id = record.get("graph_id")
        if is_text(graph_id):
            positions[graph_id].append(index)
            known.setdefault(graph_id, _KnownInstance(index, record))

    for graph_id, indices in positions.items():
        if len(indices) > 1:
            findings.append(
                Finding(
                    rule_id="INS-01",
                    severity=Severity.ERROR,
                    graph_id=graph_id,
                    location={"instance_indices": indices, "field": "graph_id"},
                    expected="graph_id único en el dataset",
                    observed=f"{len(indices)} instancias",
                    message=f"El graph_id {graph_id} se repite en {len(indices)} instancias.",
                )
            )
    return findings, known


# ---------------------------------------------------------------------------
# Reglas de nodo evaluadas registro a registro
# ---------------------------------------------------------------------------


def _check_required_attributes(
    ref: _NodeRef, contract: Mapping[str, AttributeKind], attributes: Mapping[str, Any]
) -> Iterator[Finding]:
    """NOD-05: atributos obligatorios presentes y con su tipo JSON."""
    for name, kind in contract.items():
        expected = _KIND_DESCRIPTIONS[kind]
        value = attributes.get(name, ABSENT)
        if value is ABSENT:
            yield ref.finding(
                "NOD-05",
                expected,
                describe(value),
                f"falta el atributo obligatorio '{name}'.",
                attribute=name,
            )
        elif value is None:
            continue
        elif not _matches(kind, value):
            yield ref.finding(
                "NOD-05",
                expected,
                describe(value),
                f"el atributo '{name}' no es {expected}.",
                attribute=name,
            )
        elif kind == "object":
            for path, number in _non_finite_numbers(value, name):
                yield ref.finding(
                    "NOD-05",
                    "un número finito",
                    describe(number),
                    f"el valor de '{path}' no es finito.",
                    attribute=path,
                )


def _check_domain_id(
    ref: _NodeRef, node_type: str, attributes: Mapping[str, Any]
) -> Iterator[Finding]:
    """NOD-04 sobre el identificador de dominio del tipo, si lo tiene."""
    name = _DOMAIN_ID_ATTRIBUTES.get(node_type)
    if name is None:
        return
    value = attributes.get(name)
    if is_text(value) and not value.startswith(SYNTHETIC_ID_PREFIX):
        yield ref.finding(
            "NOD-04",
            f"prefijo {SYNTHETIC_ID_PREFIX!r}",
            describe(value),
            f"'{name}' de una instancia sintética no usa el prefijo {SYNTHETIC_ID_PREFIX!r}.",
            attribute=name,
        )


def _check_composition(ref: _NodeRef, attributes: Mapping[str, Any]) -> Iterator[Finding]:
    """NOD-06: campos de cada elemento de `diet.composition`."""
    composition = attributes.get("composition")
    if not isinstance(composition, list):
        # NOD-05 ya informó el tipo, o el valor es ausente.
        return
    for position, item in enumerate(composition):
        path = f"composition[{position}]"
        if not isinstance(item, dict):
            yield ref.finding(
                "NOD-06",
                "un objeto con component_id, value y unit",
                describe(item),
                f"'{path}' no es un objeto.",
                attribute=path,
            )
            continue
        for name, kind in _COMPOSITION_FIELDS:
            value = item.get(name, ABSENT)
            if not _matches(kind, value):
                expected = _KIND_DESCRIPTIONS[kind]
                yield ref.finding(
                    "NOD-06",
                    expected,
                    describe(value),
                    f"'{path}.{name}' no es {expected}.",
                    attribute=f"{path}.{name}",
                )


def _check_missing_mask(
    ref: _NodeRef, attributes: Mapping[str, Any], mask: object
) -> Iterator[Finding]:
    """NOD-07: coherencia entre `missing_mask` y los valores `null` de `attributes`."""
    if not isinstance(mask, dict):
        yield ref.finding(
            "NOD-07",
            "un objeto con valores booleanos",
            describe(mask),
            "'missing_mask' debe ser un objeto.",
            field="missing_mask",
        )
        return

    for key, flag in mask.items():
        path = str(key)
        value = _resolve(attributes, key) if isinstance(key, str) else ABSENT
        if value is ABSENT:
            yield ref.finding(
                "NOD-07",
                "la ruta de un atributo existente",
                describe(path),
                f"la clave de missing_mask '{path}' no corresponde a ningún atributo.",
                attribute=path,
            )
        elif not isinstance(flag, bool):
            yield ref.finding(
                "NOD-07",
                "un booleano",
                describe(flag),
                f"la máscara de '{path}' no es booleana.",
                attribute=path,
            )
        elif flag and value is not None:
            yield ref.finding(
                "NOD-07",
                "valor null cuando la máscara es true",
                describe(value),
                f"'{path}' está marcado como ausente, pero tiene valor.",
                attribute=path,
            )

    for path in _null_paths(attributes):
        flag = mask.get(path, ABSENT)
        # Una máscara no booleana ya se informó arriba.
        if flag is not True and (flag is ABSENT or isinstance(flag, bool)):
            yield ref.finding(
                "NOD-07",
                "máscara true para un valor null",
                describe(flag),
                f"'{path}' es null, pero no está marcado como ausente.",
                attribute=path,
            )


def _check_non_negative(
    ref: _NodeRef, node_type: str, attributes: Mapping[str, Any]
) -> Iterator[Finding]:
    """NOD-10 (provisional): magnitudes físicamente no negativas."""
    for path in _NON_NEGATIVE_ATTRIBUTES.get(node_type, ()):
        value = _resolve(attributes, path)
        if is_finite_number(value) and value < 0:
            yield ref.finding(
                "NOD-10",
                "un valor >= 0",
                describe(value),
                f"'{path}' es negativo.",
                severity=Severity.WARNING,
                attribute=path,
            )


def _check_vocabularies(
    ref: _NodeRef,
    node_type: str,
    attributes: Mapping[str, Any],
    vocabularies: Mapping[str, frozenset[str]],
) -> Iterator[Finding]:
    """NOD-11 (provisional): categorías dentro de los vocabularios declarados."""
    for name in _VOCABULARY_ATTRIBUTES.get(node_type, ()):
        value = attributes.get(name)
        declared = vocabularies.get(name, frozenset())
        if is_text(value) and value not in declared:
            yield ref.finding(
                "NOD-11",
                f"uno de {describe(sorted(declared))}, declarado en metadata.json",
                describe(value),
                f"'{name}' no pertenece al vocabulario declarado.",
                severity=Severity.WARNING,
                attribute=name,
            )


def _check_host_context(
    ref: _NodeRef, attributes: Mapping[str, Any], instance: _KnownInstance
) -> Iterator[Finding]:
    """INS-04: el host declara la misma especie y segmento que su instancia."""
    for name in ("species", "gut_segment"):
        expected = instance.record.get(name)
        observed = attributes.get(name)
        if is_text(expected) and is_text(observed) and expected != observed:
            yield ref.finding(
                "INS-04",
                describe(expected),
                describe(observed),
                f"el host declara {name} {observed!r}, pero la instancia declara {expected!r}.",
                attribute=name,
            )


def _check_node(
    ref: _NodeRef,
    record: Mapping[str, Any],
    instances: Mapping[str, _KnownInstance],
    vocabularies: Mapping[str, frozenset[str]] | None,
) -> Iterator[Finding]:
    node_type = ref.node_type
    known_type = node_type is not None and node_type in NODE_ATTRIBUTE_CONTRACT
    if not known_type:
        yield ref.finding(
            "NOD-01",
            f"uno de {describe(list(_KNOWN_NODE_TYPES))}",
            describe(record.get("node_type", ABSENT)),
            "node_type desconocido; no se evalúan sus atributos.",
            field="node_type",
        )

    for name in ("graph_id", "node_id", "source_id"):
        value = record.get(name, ABSENT)
        if not is_text(value):
            yield ref.finding(
                "NOD-02",
                "una cadena no vacía",
                describe(value),
                f"'{name}' debe ser una cadena no vacía.",
                field=name,
            )
    instance = instances.get(ref.graph_id) if ref.graph_id is not None else None
    if ref.graph_id is not None and instance is None:
        yield ref.finding(
            "NOD-02",
            "el graph_id de una instancia existente",
            describe(ref.graph_id),
            f"no existe una instancia con graph_id {ref.graph_id!r}.",
            field="graph_id",
        )

    synthetic = instance is not None and instance.is_synthetic
    if synthetic and ref.node_id is not None and not ref.node_id.startswith(SYNTHETIC_ID_PREFIX):
        yield ref.finding(
            "NOD-04",
            f"prefijo {SYNTHETIC_ID_PREFIX!r}",
            describe(ref.node_id),
            f"el node_id de una instancia sintética no usa el prefijo {SYNTHETIC_ID_PREFIX!r}.",
            field="node_id",
        )

    # NOD-05 a NOD-11 e INS-04 no se evalúan sobre nodos de tipo desconocido.
    if node_type is None or not known_type:
        return
    attributes = record.get("attributes", ABSENT)
    if not isinstance(attributes, dict):
        yield ref.finding(
            "NOD-05",
            "un objeto",
            describe(attributes),
            "'attributes' debe ser un objeto.",
            field="attributes",
        )
        return

    contract = NODE_ATTRIBUTE_CONTRACT[node_type]
    yield from _check_required_attributes(ref, contract, attributes)
    if synthetic:
        yield from _check_domain_id(ref, node_type, attributes)
    if node_type == NodeType.DIET.value:
        yield from _check_composition(ref, attributes)
    yield from _check_missing_mask(ref, attributes, record.get("missing_mask", ABSENT))

    extra = sorted(str(key) for key in attributes if key not in contract)
    if extra:
        yield ref.finding(
            "NOD-09",
            "solo atributos del contrato del tipo",
            describe(extra),
            f"atributos fuera del contrato: {', '.join(extra)}.",
            severity=Severity.WARNING,
            attributes=extra,
        )

    yield from _check_non_negative(ref, node_type, attributes)
    if vocabularies is not None:
        yield from _check_vocabularies(ref, node_type, attributes, vocabularies)
    if node_type == NodeType.HOST.value and instance is not None:
        yield from _check_host_context(ref, attributes, instance)


# ---------------------------------------------------------------------------
# Reglas de nodo evaluadas sobre el conjunto
# ---------------------------------------------------------------------------


def _check_duplicate_ids(refs: Iterable[_NodeRef]) -> Iterator[Finding]:
    """NOD-03: `node_id` único dentro de `(graph_id, node_type)`."""
    positions: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for ref in refs:
        if ref.graph_id is not None and ref.node_type is not None and ref.node_id is not None:
            positions[(ref.graph_id, ref.node_type, ref.node_id)].append(ref.index)
    for (graph_id, node_type, node_id), indices in positions.items():
        if len(indices) > 1:
            yield Finding(
                rule_id="NOD-03",
                severity=Severity.ERROR,
                graph_id=graph_id,
                location={"node_type": node_type, "node_id": node_id, "node_indices": indices},
                expected="node_id único dentro de (graph_id, node_type)",
                observed=f"{len(indices)} apariciones",
                message=(
                    f"El node_id {node_id} se repite {len(indices)} veces entre los nodos "
                    f"{node_type}."
                ),
            )


def _check_missing_values(
    records: Iterable[tuple[_NodeRef, Mapping[str, Any]]],
) -> Iterator[Finding]:
    """NOD-08: conteo de atributos marcados como ausentes, por tipo y atributo."""
    groups: dict[tuple[str | None, str, str], list[_NodeRef]] = defaultdict(list)
    for ref, record in records:
        node_type = ref.node_type
        mask = record.get("missing_mask")
        if node_type is None or node_type not in NODE_ATTRIBUTE_CONTRACT:
            continue
        if not isinstance(mask, dict):
            continue
        for key, flag in mask.items():
            if flag is True:
                groups[(ref.graph_id, node_type, str(key))].append(ref)
    for (graph_id, node_type, attribute), refs in groups.items():
        yield Finding(
            rule_id="NOD-08",
            severity=Severity.WARNING,
            graph_id=graph_id,
            location={
                "node_type": node_type,
                "attribute": attribute,
                "node_ids": [ref.node_id for ref in refs if ref.node_id is not None],
            },
            expected="ningún atributo marcado como ausente",
            observed=f"{len(refs)} nodo(s) con el atributo ausente",
            message=(
                f"{len(refs)} nodo(s) {node_type} tienen '{attribute}' marcado como ausente; "
                "afecta sus features."
            ),
        )


def _check_type_coverage(
    instances: Mapping[str, _KnownInstance], refs: Iterable[_NodeRef]
) -> Iterator[Finding]:
    """NOD-12 (provisional): al menos un nodo de cada tipo por instancia."""
    present: dict[str, set[str]] = defaultdict(set)
    for ref in refs:
        if ref.graph_id is not None and ref.node_type is not None:
            present[ref.graph_id].add(ref.node_type)
    for graph_id, instance in instances.items():
        missing = [
            node_type for node_type in _KNOWN_NODE_TYPES if node_type not in present[graph_id]
        ]
        if missing:
            yield Finding(
                rule_id="NOD-12",
                severity=Severity.ERROR if instance.is_synthetic else Severity.WARNING,
                graph_id=graph_id,
                location={"instance_index": instance.index, "node_types": missing},
                expected="al menos un nodo de cada uno de los ocho tipos",
                observed=f"tipos sin nodos: {', '.join(missing)}",
                message=f"La instancia {graph_id} no tiene nodos de tipo {', '.join(missing)}.",
            )


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def find_node_findings(
    instances: Iterable[InstanceRecord | Mapping[str, Any]],
    nodes: Iterable[Node | Mapping[str, Any]],
    *,
    metadata: Mapping[str, Any] | None = None,
) -> list[Finding]:
    """Evalúa NOD-01 a NOD-12 e INS-01 a INS-04 y devuelve todos los hallazgos.

    `instances` y `nodes` pueden ser registros del paquete de datos o diccionarios con la forma
    de una línea JSONL. `metadata` es el contenido de `metadata.json`; sin él, NOD-11 no se
    evalúa. La ubicación de cada hallazgo usa la posición del registro en la secuencia recibida
    (`instance_index` o `node_index`).

    Una lista vacía indica que no hay hallazgos. Un hallazgo `ADVERTENCIA` no invalida el grafo.
    Para una misma entrada, el orden de los hallazgos es determinista.
    """
    findings, known_instances = _check_instances(instances)
    vocabularies = declared_vocabularies(metadata)

    records: list[tuple[_NodeRef, Mapping[str, Any]]] = []
    for index, node in enumerate(nodes):
        record = as_record(node)
        if record is None:
            findings.append(
                Finding(
                    rule_id="NOD-02",
                    severity=Severity.ERROR,
                    graph_id=None,
                    location={"node_index": index},
                    expected="un objeto con el envoltorio de nodo",
                    observed=type(node).__name__,
                    message=f"El nodo en la posición {index} no es un objeto.",
                )
            )
            continue
        ref = _NodeRef.of(index, record)
        records.append((ref, record))
        findings.extend(_check_node(ref, record, known_instances, vocabularies))

    refs = [ref for ref, _ in records]
    findings.extend(_check_duplicate_ids(refs))
    findings.extend(_check_missing_values(records))
    findings.extend(_check_type_coverage(known_instances, refs))
    return findings
