"""Validación de dimensiones y tipos de tensores (VG-05).

Implementa las reglas TEN-01 a TEN-12 de `docs/graph-integrity-rules.md` sobre un objeto
`HeteroData` construido a partir de una instancia válida, según la sección "Correspondencia con
`HeteroData`" de DS-01. Valida el contrato, no una implementación concreta del constructor
(#28): cualquier conversión que declare cumplir DS-01 debe superar estas reglas.

Requiere el extra `graph` (`torch` y `torch-geometric`). Los validadores de registros no
dependen de este módulo.

El validador solo lee el objeto: no crea almacenes, no convierte tensores ni corrige valores.
Por eso **no** llama a `HeteroData.validate()`. Con `raise_on_error=True`, esa función se
detiene en el primer error. Con `raise_on_error=False`, que sería necesario para un reporte
completo, crea un almacén vacío cuando una relación referencia un tipo de nodo inexistente
(efecto lateral verificado con torch-geometric 2.8.0). TEN-01 a TEN-04 se evalúan aquí sin mutar
el grafo. La llamada final `data.validate(raise_on_error=True)` que exige DS-01 sigue siendo
responsabilidad del constructor y no tiene ese efecto, porque lanza la excepción antes.

Criterios de aplicación de la especificación:

- `N_type` es `num_nodes` de PyG: el valor explícito o, si no existe, el que PyG infiere de `x`.
  Se lee sin emitir las advertencias de inferencia de PyG.
- Las columnas declaradas de un tipo son `metadata["node_feature_schema"][node_type]`, y las de
  una relación, `metadata["edge_feature_schema"]["origen|relación|destino"]` (la misma clave que
  usa `counts`). Cada entrada es la **lista ordenada** de descriptores de columna, porque DS-01
  prohíbe inferir el orden de un objeto JSON; el número de columnas es su largo. Un tipo o
  relación sin entrada declara cero columnas. Una entrada que no es una lista es un `ERROR` de
  TEN-06 o TEN-09. El contenido de cada descriptor lo define el constructor.
- TEN-04 y TEN-11 solo se evalúan si `edge_index` tiene forma `[2, E]` y un `dtype` entero: con
  otro `dtype` sus valores no son índices, y TEN-05 ya informa el defecto.
- TEN-10 informa, por tensor, el número de valores no finitos y las posiciones de los primeros
  diez.
- TEN-11 compara, por tupla, el multiconjunto de pares `(source_id, target_id)` que codifican las
  columnas con el de los registros de arista de la instancia. No exige un orden de columnas
  concreto: DS-01 no lo fija. Se evalúa cuando `node_id` de ambos tipos tiene `N_type` elementos
  y todos los índices están dentro de rango.
- TEN-12 compara los once campos del contrato de instancia con los atributos globales, con tipo
  y valor. `timepoint = null` corresponde a un atributo ausente, porque PyG no almacena `None`.
"""

from __future__ import annotations

import warnings
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import fields
from typing import Any, Final, TypeGuard

import torch
from torch import Tensor
from torch_geometric.data import HeteroData

from nutrigraphdt.data.synthetic.edges import Edge
from nutrigraphdt.data.synthetic.export import InstanceRecord
from nutrigraphdt.graph.validation._common import (
    ABSENT,
    as_record,
    describe,
    is_text,
    node_type_sort_key,
)
from nutrigraphdt.graph.validation.findings import Finding, Severity

MAX_REPORTED_POSITIONS: Final = 10
"""Máximo de posiciones, columnas o registros que un hallazgo enumera; el resto se cuenta."""

INSTANCE_FIELDS: tuple[str, ...] = tuple(field.name for field in fields(InstanceRecord))
"""Campos del contrato de instancia que DS-01 guarda como atributos globales (TEN-12)."""

_NODE_LISTS: tuple[str, ...] = ("node_id", "source_id", "raw_attributes")
"""Listas alineadas con las filas de `x` (TEN-08)."""

_EDGE_LISTS: tuple[str, ...] = (
    "evidence_id",
    "evidence_status",
    "evidence_method",
    "raw_attributes",
)
"""Listas alineadas con las columnas de `edge_index` (TEN-09)."""

EdgeType = tuple[str, str, str]


def edge_type_key(edge_type: EdgeType) -> str:
    """Clave de `edge_feature_schema` para una tupla, con la convención de `counts`."""
    return "|".join(edge_type)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _shape(tensor: Tensor) -> list[int]:
    return [int(size) for size in tensor.shape]


def _num_nodes(store: Any) -> int | None:
    """`num_nodes` de un almacén, sin las advertencias de inferencia de PyG."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        value = store.num_nodes
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _is_integer(tensor: Tensor) -> bool:
    dtype = tensor.dtype
    return not dtype.is_floating_point and not dtype.is_complex and dtype != torch.bool


def _is_sequence(value: object) -> TypeGuard[Sequence[Any]]:
    return isinstance(value, Sequence) and not isinstance(value, str | bytes)


def _declared_columns(
    metadata: Mapping[str, Any], schema_name: str, key: str
) -> tuple[int | None, object]:
    """Número de columnas declaradas y la entrada del esquema; `None` si está mal formada."""
    schema = metadata.get(schema_name)
    entry = schema.get(key, ABSENT) if isinstance(schema, Mapping) else ABSENT
    if entry is ABSENT:
        return 0, entry
    if isinstance(entry, list):
        return len(entry), entry
    return None, entry


def _expected_shape(rows: int | None, columns: int | None, rows_name: str) -> str:
    return f"[{rows_name if rows is None else rows}, {'?' if columns is None else columns}]"


def _same(expected: object, observed: object) -> bool:
    """Igualdad con tipo: `True` no equivale a `1`, y un tensor nunca equivale a un escalar."""
    return type(expected) is type(observed) and expected == observed


class _Findings:
    """Construye hallazgos con el `graph_id` de la instancia."""

    def __init__(self, graph_id: str | None) -> None:
        self.graph_id = graph_id

    def error(
        self, rule_id: str, expected: str, observed: str, message: str, **location: Any
    ) -> Finding:
        return Finding(
            rule_id=rule_id,
            severity=Severity.ERROR,
            graph_id=self.graph_id,
            location=location,
            expected=expected,
            observed=observed,
            message=message,
        )


# ---------------------------------------------------------------------------
# TEN-01 y TEN-02: tipos referenciados por las relaciones
# ---------------------------------------------------------------------------


def _check_referenced_types(
    report: _Findings, node_stores: Mapping[str, Any], edge_types: list[EdgeType]
) -> Iterator[Finding]:
    undefined: dict[str, list[list[str]]] = {}
    for edge_type in edge_types:
        source_type, _, target_type = edge_type
        for node_type in dict.fromkeys((source_type, target_type)):
            if node_type not in node_stores:
                yield report.error(
                    "TEN-01",
                    f"un almacén de nodos {node_type}",
                    "almacén inexistente",
                    f"La relación {edge_type} referencia el tipo {node_type}, que no existe "
                    "como almacén de nodos.",
                    edge_type=list(edge_type),
                    node_type=node_type,
                )
            elif _num_nodes(node_stores[node_type]) is None:
                undefined.setdefault(node_type, []).append(list(edge_type))

    for node_type in sorted(undefined, key=node_type_sort_key):
        yield report.error(
            "TEN-02",
            "num_nodes definido",
            "num_nodes indefinido",
            f"El tipo {node_type} se usa en relaciones, pero num_nodes no está definido.",
            node_type=node_type,
            edge_types=undefined[node_type],
        )


# ---------------------------------------------------------------------------
# TEN-03 a TEN-05: edge_index
# ---------------------------------------------------------------------------


def _valid_edge_index(store: Any) -> Tensor | None:
    """`edge_index` si tiene forma `[2, E]`; si no, `None` (lo informa TEN-03)."""
    edge_index = store.get("edge_index", ABSENT)
    if isinstance(edge_index, Tensor) and edge_index.dim() == 2 and edge_index.size(0) == 2:
        return edge_index
    return None


def _check_edge_index(
    report: _Findings, edge_type: EdgeType, store: Any, node_stores: Mapping[str, Any]
) -> Iterator[Finding]:
    location = {"edge_type": list(edge_type), "tensor": "edge_index"}
    edge_index = store.get("edge_index", ABSENT)
    if not isinstance(edge_index, Tensor):
        observed = "tensor ausente" if edge_index is ABSENT else type(edge_index).__name__
        yield report.error(
            "TEN-03",
            "un tensor de forma [2, E]",
            observed,
            f"La relación {edge_type} no tiene un edge_index tensorial.",
            **location,
        )
        return
    if _valid_edge_index(store) is None:
        yield report.error(
            "TEN-03",
            "forma [2, E]",
            describe(_shape(edge_index)),
            f"edge_index de {edge_type} tiene forma {_shape(edge_index)}.",
            **location,
        )
    if edge_index.dtype != torch.long:
        yield report.error(
            "TEN-05",
            str(torch.long),
            str(edge_index.dtype),
            f"edge_index de {edge_type} no es torch.long.",
            **location,
        )
    if _valid_edge_index(store) is None or not _is_integer(edge_index) or not edge_index.numel():
        return

    for row, endpoint, node_type in ((0, "source", edge_type[0]), (1, "target", edge_type[2])):
        limit = _num_nodes(node_stores[node_type]) if node_type in node_stores else None
        values = edge_index[row]
        invalid = values < 0
        if limit is not None:
            invalid |= values >= limit
        columns = invalid.nonzero().flatten()
        if not columns.numel():
            continue
        shown = columns[:MAX_REPORTED_POSITIONS]
        bounds = f"[0, {limit})" if limit is not None else ">= 0"
        yield report.error(
            "TEN-04",
            f"índices {endpoint} en {bounds}",
            f"{columns.numel()} índice(s) fuera de rango",
            f"edge_index de {edge_type} tiene {columns.numel()} índice(s) {endpoint} fuera de "
            f"{bounds}.",
            **location,
            row=endpoint,
            limit=limit,
            invalid_count=int(columns.numel()),
            columns=[int(column) for column in shown],
            values=[int(values[column]) for column in shown],
        )


# ---------------------------------------------------------------------------
# TEN-06 a TEN-08: almacenes de nodos
# ---------------------------------------------------------------------------


def _check_features(
    report: _Findings,
    node_type: str,
    store: Any,
    metadata: Mapping[str, Any],
) -> Iterator[Finding]:
    """TEN-06: `x` de punto flotante con forma `[N_type, F_type]`."""
    location = {"node_type": node_type, "tensor": "x"}
    columns, entry = _declared_columns(metadata, "node_feature_schema", node_type)
    if columns is None:
        yield report.error(
            "TEN-06",
            "una lista ordenada de columnas en node_feature_schema",
            describe(entry),
            f"node_feature_schema declara las columnas de {node_type} con otro formato.",
            node_type=node_type,
            schema="node_feature_schema",
        )

    x = store.get("x", ABSENT)
    if not isinstance(x, Tensor):
        yield report.error(
            "TEN-06",
            "un tensor de punto flotante",
            "tensor ausente" if x is ABSENT else type(x).__name__,
            f"El tipo {node_type} no tiene un tensor x.",
            **location,
        )
        return
    if not x.is_floating_point():
        yield report.error(
            "TEN-06",
            "un dtype de punto flotante",
            str(x.dtype),
            f"x de {node_type} no es de punto flotante.",
            **location,
        )
    rows = _num_nodes(store)
    shape = _shape(x)
    if (
        x.dim() != 2
        or (rows is not None and shape[0] != rows)
        or (columns is not None and shape[1] != columns)
    ):
        yield report.error(
            "TEN-06",
            _expected_shape(rows, columns, "N_type"),
            describe(shape),
            f"x de {node_type} tiene forma {shape}; se esperaban {rows} fila(s) y {columns} "
            "columna(s) declaradas.",
            **location,
            declared_columns=columns,
        )


def _check_missing_mask(report: _Findings, node_type: str, store: Any) -> Iterator[Finding]:
    """TEN-07: `missing_mask` booleana con la forma de `x`."""
    location = {"node_type": node_type, "tensor": "missing_mask"}
    mask = store.get("missing_mask", ABSENT)
    if not isinstance(mask, Tensor):
        yield report.error(
            "TEN-07",
            "un tensor booleano",
            "tensor ausente" if mask is ABSENT else type(mask).__name__,
            f"El tipo {node_type} no tiene un tensor missing_mask.",
            **location,
        )
        return
    if mask.dtype != torch.bool:
        yield report.error(
            "TEN-07",
            str(torch.bool),
            str(mask.dtype),
            f"missing_mask de {node_type} no es booleana.",
            **location,
        )
    x = store.get("x", ABSENT)
    if isinstance(x, Tensor) and mask.shape != x.shape:
        yield report.error(
            "TEN-07",
            describe(_shape(x)),
            describe(_shape(mask)),
            f"missing_mask de {node_type} no tiene la forma de x.",
            **location,
        )


def _check_node_lists(report: _Findings, node_type: str, store: Any) -> Iterator[Finding]:
    """TEN-08: listas alineadas con las filas y `node_id` sin repetidos."""
    rows = _num_nodes(store)
    for name in _NODE_LISTS:
        value = store.get(name, ABSENT)
        location = {"node_type": node_type, "attribute": name}
        if not _is_sequence(value):
            yield report.error(
                "TEN-08",
                "una lista alineada con las filas de x",
                "atributo ausente" if value is ABSENT else type(value).__name__,
                f"{name} de {node_type} no es una lista.",
                **location,
            )
            continue
        if rows is not None and len(value) != rows:
            yield report.error(
                "TEN-08",
                f"{rows} elemento(s)",
                f"{len(value)} elemento(s)",
                f"{name} de {node_type} tiene {len(value)} elemento(s) y el tipo tiene {rows} "
                "nodo(s).",
                **location,
            )
        if name == "node_id":
            try:
                counts = Counter(value)
            except TypeError:
                continue
            repeated = sorted(
                (str(node_id) for node_id, count in counts.items() if count > 1),
            )
            if repeated:
                yield report.error(
                    "TEN-08",
                    "node_id sin repetidos",
                    f"{len(repeated)} node_id repetido(s)",
                    f"node_id de {node_type} repite {', '.join(repeated)}.",
                    **location,
                    repeated=repeated,
                )


# ---------------------------------------------------------------------------
# TEN-09: almacenes de aristas
# ---------------------------------------------------------------------------


def _check_edge_features(
    report: _Findings, edge_type: EdgeType, store: Any, metadata: Mapping[str, Any]
) -> Iterator[Finding]:
    """TEN-09: `edge_attr` `[E, A_type]` y metadatos de evidencia con `E` elementos."""
    key = edge_type_key(edge_type)
    location = {"edge_type": list(edge_type)}
    columns, entry = _declared_columns(metadata, "edge_feature_schema", key)
    if columns is None:
        yield report.error(
            "TEN-09",
            "una lista ordenada de columnas en edge_feature_schema",
            describe(entry),
            f"edge_feature_schema declara las columnas de {edge_type} con otro formato.",
            **location,
            schema="edge_feature_schema",
        )

    edge_index = _valid_edge_index(store)
    edges = int(edge_index.size(1)) if edge_index is not None else None
    edge_attr = store.get("edge_attr", ABSENT)
    if not isinstance(edge_attr, Tensor):
        yield report.error(
            "TEN-09",
            "un tensor de punto flotante [E, A_type]; [E, 0] si no hay features",
            "tensor ausente" if edge_attr is ABSENT else type(edge_attr).__name__,
            f"La relación {edge_type} no tiene un tensor edge_attr.",
            **location,
            tensor="edge_attr",
        )
    else:
        if not edge_attr.is_floating_point():
            yield report.error(
                "TEN-09",
                "un dtype de punto flotante",
                str(edge_attr.dtype),
                f"edge_attr de {edge_type} no es de punto flotante.",
                **location,
                tensor="edge_attr",
            )
        shape = _shape(edge_attr)
        if (
            edge_attr.dim() != 2
            or (edges is not None and shape[0] != edges)
            or (columns is not None and shape[1] != columns)
        ):
            yield report.error(
                "TEN-09",
                _expected_shape(edges, columns, "E"),
                describe(shape),
                f"edge_attr de {edge_type} tiene forma {shape}; se esperaban {edges} arista(s) "
                f"y {columns} columna(s) declaradas.",
                **location,
                tensor="edge_attr",
                declared_columns=columns,
            )

    for name in _EDGE_LISTS:
        value = store.get(name, ABSENT)
        if not _is_sequence(value):
            yield report.error(
                "TEN-09",
                "una lista alineada con las columnas de edge_index",
                "atributo ausente" if value is ABSENT else type(value).__name__,
                f"{name} de {edge_type} no es una lista.",
                **location,
                attribute=name,
            )
        elif edges is not None and len(value) != edges:
            yield report.error(
                "TEN-09",
                f"{edges} elemento(s)",
                f"{len(value)} elemento(s)",
                f"{name} de {edge_type} tiene {len(value)} elemento(s) y edge_index tiene {edges} "
                "columna(s).",
                **location,
                attribute=name,
            )


# ---------------------------------------------------------------------------
# TEN-10: valores no finitos
# ---------------------------------------------------------------------------


def _check_finite(
    report: _Findings, tensor: object, name: str, **location: Any
) -> Iterator[Finding]:
    if not isinstance(tensor, Tensor) or not tensor.is_floating_point():
        return
    positions = (~torch.isfinite(tensor)).nonzero()
    count = int(positions.size(0))
    if not count:
        return
    owner = location.get("node_type") or tuple(location.get("edge_type", ()))
    yield report.error(
        "TEN-10",
        "solo valores finitos",
        f"{count} valor(es) no finito(s)",
        f"{name} de {owner} contiene {count} valor(es) NaN o infinito(s).",
        **location,
        tensor=name,
        non_finite_count=count,
        positions=[[int(index) for index in row] for row in positions[:MAX_REPORTED_POSITIONS]],
    )


# ---------------------------------------------------------------------------
# TEN-11: significado de las aristas
# ---------------------------------------------------------------------------


def _record_pairs(edges: Iterable[object], graph_id: str | None) -> dict[EdgeType, Counter[Any]]:
    """Pares `(source_id, target_id)` de los registros de arista de la instancia, por tupla."""
    pairs: dict[EdgeType, Counter[Any]] = {}
    for edge in edges:
        record = as_record(edge)
        if record is None or record.get("graph_id") != graph_id:
            continue
        source_type = record.get("source_type")
        relation_type = record.get("relation_type")
        target_type = record.get("target_type")
        source_id = record.get("source_id")
        target_id = record.get("target_id")
        if not (
            is_text(source_type)
            and is_text(relation_type)
            and is_text(target_type)
            and is_text(source_id)
            and is_text(target_id)
        ):
            continue
        edge_type = (source_type, relation_type, target_type)
        pairs.setdefault(edge_type, Counter())[(source_id, target_id)] += 1
    return pairs


def _node_ids(store: Any) -> list[Any] | None:
    """`node_id` si tiene exactamente `N_type` elementos."""
    node_ids = store.get("node_id", ABSENT)
    rows = _num_nodes(store)
    if not _is_sequence(node_ids) or rows is None or len(node_ids) != rows:
        return None
    return list(node_ids)


def _column_pairs(
    edge_type: EdgeType, store: Any, node_stores: Mapping[str, Any]
) -> list[tuple[Any, Any]] | None:
    """Pares de IDs que codifica cada columna, o `None` si no pueden reconstruirse."""
    edge_index = _valid_edge_index(store)
    source_type, _, target_type = edge_type
    if (
        edge_index is None
        or not _is_integer(edge_index)
        or source_type not in node_stores
        or target_type not in node_stores
    ):
        return None
    source_ids = _node_ids(node_stores[source_type])
    target_ids = _node_ids(node_stores[target_type])
    if source_ids is None or target_ids is None:
        return None
    sources = [int(index) for index in edge_index[0]]
    targets = [int(index) for index in edge_index[1]]
    if any(not 0 <= index < len(source_ids) for index in sources) or any(
        not 0 <= index < len(target_ids) for index in targets
    ):
        return None
    return [
        (source_ids[source], target_ids[target])
        for source, target in zip(sources, targets, strict=True)
    ]


def _check_edge_meaning(
    report: _Findings,
    edge_stores: Mapping[EdgeType, Any],
    node_stores: Mapping[str, Any],
    expected_pairs: Mapping[EdgeType, Counter[Any]],
) -> Iterator[Finding]:
    """TEN-11: cada columna de `edge_index` corresponde a un registro de arista."""
    edge_types = sorted(
        set(edge_stores) | set(expected_pairs),
        key=lambda item: (node_type_sort_key(item[0]), item[1], node_type_sort_key(item[2])),
    )
    for edge_type in edge_types:
        if edge_type in edge_stores:
            columns = _column_pairs(edge_type, edge_stores[edge_type], node_stores)
            if columns is None:
                continue
        else:
            columns = []
        remaining = Counter(expected_pairs.get(edge_type, Counter()))
        unmatched: list[dict[str, Any]] = []
        for column, (source_id, target_id) in enumerate(columns):
            if remaining[(source_id, target_id)] > 0:
                remaining[(source_id, target_id)] -= 1
            else:
                unmatched.append({"column": column, "source_id": source_id, "target_id": target_id})
        missing = [
            {"source_id": source_id, "target_id": target_id, "count": count}
            for (source_id, target_id), count in sorted(remaining.items())
            if count > 0
        ]
        if not unmatched and not missing:
            continue
        missing_count = sum(item["count"] for item in missing)
        expected_count = sum(expected_pairs.get(edge_type, Counter()).values())
        yield report.error(
            "TEN-11",
            f"{expected_count} arista(s) de edges.jsonl con los mismos extremos",
            f"{len(columns)} columna(s): {len(unmatched)} sin registro y {missing_count} "
            "registro(s) sin columna",
            f"Los extremos que codifica edge_index de {edge_type} no coinciden con los registros "
            "de arista.",
            edge_type=list(edge_type),
            unmatched_column_count=len(unmatched),
            unmatched_columns=unmatched[:MAX_REPORTED_POSITIONS],
            missing_record_count=missing_count,
            missing_records=missing[:MAX_REPORTED_POSITIONS],
        )


# ---------------------------------------------------------------------------
# TEN-12: atributos globales
# ---------------------------------------------------------------------------


def _check_global_attributes(
    report: _Findings, data: HeteroData, instance: Mapping[str, Any]
) -> Iterator[Finding]:
    for name in INSTANCE_FIELDS:
        expected = instance.get(name, ABSENT)
        if expected is ABSENT:
            # INS-01 informa el campo faltante en el registro de instancia.
            continue
        observed = getattr(data, name, ABSENT)
        if expected is None and observed is ABSENT:
            continue
        if observed is ABSENT or not _same(expected, observed):
            yield report.error(
                "TEN-12",
                describe(expected),
                "atributo ausente" if observed is ABSENT else describe(observed),
                f"El atributo global {name} no coincide con el registro de instancia.",
                attribute=name,
            )


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def find_tensor_findings(
    data: HeteroData,
    *,
    instance: InstanceRecord | Mapping[str, Any],
    edges: Iterable[Edge | Mapping[str, Any]],
    metadata: Mapping[str, Any],
) -> list[Finding]:
    """Evalúa TEN-01 a TEN-12 sobre el `HeteroData` de una instancia y devuelve los hallazgos.

    `instance` es el registro de `instances.jsonl` de la instancia convertida. `edges` son los
    registros de arista (pueden incluir otras instancias; se filtran por `graph_id`), y
    `metadata`, el contenido de `metadata.json` con `node_feature_schema` y
    `edge_feature_schema`. Todas las reglas `TEN` son `ERROR`.

    No modifica `data`. Para una misma entrada, el orden de los hallazgos es determinista.
    """
    instance_record = as_record(instance) or {}
    graph_id = instance_record.get("graph_id")
    report = _Findings(graph_id if is_text(graph_id) else None)

    node_stores: dict[str, Any] = {
        node_type: store
        for node_type, store in sorted(
            data.node_items(), key=lambda item: node_type_sort_key(item[0])
        )
    }
    edge_stores: dict[EdgeType, Any] = {
        edge_type: store
        for edge_type, store in sorted(
            data.edge_items(),
            key=lambda item: (
                node_type_sort_key(item[0][0]),
                item[0][1],
                node_type_sort_key(item[0][2]),
            ),
        )
    }

    findings = list(_check_referenced_types(report, node_stores, list(edge_stores)))
    for edge_type, store in edge_stores.items():
        findings.extend(_check_edge_index(report, edge_type, store, node_stores))
    for node_type, store in node_stores.items():
        findings.extend(_check_features(report, node_type, store, metadata))
        findings.extend(_check_missing_mask(report, node_type, store))
        findings.extend(_check_node_lists(report, node_type, store))
    for edge_type, store in edge_stores.items():
        findings.extend(_check_edge_features(report, edge_type, store, metadata))
    for node_type, store in node_stores.items():
        for name in ("x", "y"):
            findings.extend(
                _check_finite(report, store.get(name, ABSENT), name, node_type=node_type)
            )
    for edge_type, store in edge_stores.items():
        findings.extend(
            _check_finite(
                report, store.get("edge_attr", ABSENT), "edge_attr", edge_type=list(edge_type)
            )
        )
    findings.extend(
        _check_edge_meaning(report, edge_stores, node_stores, _record_pairs(edges, graph_id))
    )
    findings.extend(_check_global_attributes(report, data, instance_record))
    return findings
