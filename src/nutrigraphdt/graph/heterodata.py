"""Prototipo del constructor `HeteroData` desde el dataset sintético (A35-1, #28).

Convierte cada instancia de un dataset en un `HeteroData` según la sección "Correspondencia con
`HeteroData`" de `docs/synthetic-dataset/synthetic-dataset-spec.md` (DS-01), declara en los
metadatos las columnas de features y del target, y serializa los grafos. Requiere el extra `graph`.

Es un **prototipo**. DS-01 no aprueba ninguna codificación de features, así que la de este
módulo (`ENCODING_VERSION`) es mínima y provisional. El constructor desde datos
preprocesados (A39-1, #35, `nutrigraphdt.graph.builder`) traduce las tablas normalizadas a
registros DS-01 y reutiliza `build_heterodata`.

Codificación del prototipo:

- **Features numéricas crudas, sin normalizar.** No existe partición de datos, y DS-01 exige
  ajustar los escaladores solo sobre entrenamiento.
- **Una columna por magnitud y unidad.** Si los nodos de un tipo declaran la misma magnitud con
  unidades o calificadores distintos (dosis en `CFU/kg` y `mg/kg`, anotaciones de presencia y de
  abundancia), cada combinación es una columna: DS-01 prohíbe mezclar unidades. Un nodo sin
  valor en una columna (`null` o de otra unidad) tiene `0.0` y máscara `true`.
- **Sin categorías codificadas** (nivel taxonómico, categoría de aditivo, sexo): quedan para
  el constructor definitivo.
- **Target sin fuga.** La variable objetivo (concentración de AGCC) se materializa en `y` desde
  los registros de `outputs.jsonl`. Por eso `x` de `metabolite` no incluye la concentración, y
  `x` de `phenotype` no incluye su valor: un fenotipo es un resultado observado, y rasgos como
  `cecal_scfa_total` se derivan de los AGCC.
- **`y` solo con valores de referencia.** Se materializan las salidas `measured` o `synthetic`,
  nunca las `predicted`, que se conservan solo en `data.output_records` (DS-01: una predicción no
  reemplaza una medición). Todas las salidas de un tipo deben compartir origen, unidad y matriz.

Además de los atributos de DS-01, cada almacén de nodos guarda `raw_missing_mask`, la máscara
JSON original de cada nodo. Así el round-trip JSONL -> `HeteroData` -> JSONL no pierde campos.

Los `.pt` se cargan con `torch.load(weights_only=True)` y una lista explícita de clases de PyG.
Nunca se ejecuta código arbitrario de un archivo (ver `load_graphs`).
"""

from __future__ import annotations

import copy
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

import torch
from torch_geometric.data import HeteroData
from torch_geometric.data.storage import BaseStorage, EdgeStorage, GlobalStorage, NodeStorage

from nutrigraphdt.data.synthetic.edges import Edge
from nutrigraphdt.data.synthetic.export import InstanceRecord, OutputRecord, SyntheticDataset
from nutrigraphdt.data.synthetic.nodes import Node, NodeType
from nutrigraphdt.graph.validation.pipeline import prepare_graphs_for_model, validate_graph
from nutrigraphdt.graph.validation.report import ValidationReport

ENCODING_VERSION: Final = "prototype-0.1"
"""Versión de la codificación de features y target de este prototipo."""

GRAPH_FORMAT: Final = "nutrigraphdt-heterodata"
GRAPH_FORMAT_VERSION: Final = "1.0"
MANIFEST_FILE: Final = "manifest.json"

REFERENCE_KINDS: frozenset[str] = frozenset({"measured", "synthetic"})
"""Orígenes de salida que pueden materializarse en `y`; `predicted` nunca."""

_INSTANCE_FIELDS: tuple[str, ...] = tuple(item.name for item in fields(InstanceRecord))
_EDGE_KEY_FIELDS: tuple[str, ...] = (
    "graph_id",
    "source_type",
    "relation_type",
    "target_type",
    "source_id",
    "target_id",
)
_SAFE_PYG_CLASSES: tuple[type, ...] = (BaseStorage, NodeStorage, EdgeStorage, GlobalStorage)
"""Clases de PyG que `load_graphs` permite deserializar con `weights_only=True`."""

EdgeType = tuple[str, str, str]


# ---------------------------------------------------------------------------
# Codificación de features
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NumericFeature:
    """Magnitud numérica de `attributes` que se usa como feature.

    `unit_path` es el atributo que declara la unidad del valor. `unit` fija la unidad cuando el
    contrato no la declara (por ejemplo, las covariables, cuya unidad documenta el diccionario
    de datos). `qualifier_path` es el atributo que distingue magnitudes distintas con el mismo
    nombre, como `annotation_value_type` (presencia o abundancia).
    """

    path: str
    unit_path: str | None = None
    unit: str | None = None
    qualifier_path: str | None = None


NODE_FEATURES: Mapping[str, tuple[NumericFeature, ...]] = MappingProxyType(
    {
        NodeType.DIET.value: (),  # la composición se codifica por componente (ver abajo)
        NodeType.ADDITIVE.value: (NumericFeature("dose", unit_path="dose_unit"),),
        NodeType.SUBSTRATE.value: (NumericFeature("quantity", unit_path="unit"),),
        NodeType.TAXON.value: (NumericFeature("abundance", unit_path="abundance_unit"),),
        NodeType.FUNCTION.value: (
            NumericFeature(
                "annotation_value", unit_path="unit", qualifier_path="annotation_value_type"
            ),
        ),
        NodeType.METABOLITE.value: (),  # la concentración es el target
        NodeType.HOST.value: (
            NumericFeature("covariates.age_days", unit="d"),
            NumericFeature("covariates.body_weight_g", unit="g"),
        ),
        NodeType.PHENOTYPE.value: (),  # resultado observado: no es una entrada
    }
)
"""Features numéricas por tipo de nodo (codificación `prototype-0.1`)."""

EDGE_FEATURES: Mapping[EdgeType, tuple[NumericFeature, ...]] = MappingProxyType(
    {
        (NodeType.DIET.value, "provides", NodeType.SUBSTRATE.value): (
            NumericFeature("proportion", unit_path="unit"),
        )
    }
)
"""Features numéricas por relación; las demás relaciones usan `edge_attr` `[E, 0]`."""

COMPOSITION_PATH: Final = "composition"
"""Atributo de `diet` que se codifica con una columna por componente y unidad."""


@dataclass(frozen=True)
class Column:
    """Columna declarada de `x`, `edge_attr` o `y`."""

    name: str
    source: str
    unit: str
    qualifier: str | None = None
    feature: NumericFeature | None = None

    def to_dict(self) -> dict[str, Any]:
        described: dict[str, Any] = {
            "name": self.name,
            "source": self.source,
            "unit": self.unit,
            "encoding": "raw",
        }
        if self.qualifier is not None:
            described["qualifier"] = self.qualifier
        return described


def _resolve(attributes: Mapping[str, Any], path: str) -> Any:
    current: Any = attributes
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _record(item: object) -> Mapping[str, Any]:
    if isinstance(item, Node | Edge | InstanceRecord | OutputRecord):
        return item.to_dict()
    if isinstance(item, Mapping):
        return item
    raise TypeError(f"Se esperaba un registro del dataset; se recibió {type(item).__name__}.")


def _feature_key(
    feature: NumericFeature, attributes: Mapping[str, Any]
) -> tuple[str | None, str | None]:
    """`(calificador, unidad)` con que un registro declara la magnitud."""
    unit = feature.unit if feature.unit_path is None else _resolve(attributes, feature.unit_path)
    qualifier = _resolve(attributes, feature.qualifier_path) if feature.qualifier_path else None
    return (
        qualifier if isinstance(qualifier, str) else None,
        unit if isinstance(unit, str) else None,
    )


def _column_name(path: str, qualifier: str | None, unit: str) -> str:
    return f"{path}{':' + qualifier if qualifier else ''} ({unit})"


def _feature_columns(
    features: Sequence[NumericFeature], records: Sequence[Mapping[str, Any]]
) -> list[Column]:
    columns: list[Column] = []
    for feature in features:
        keys = set()
        for record in records:
            attributes = record.get("attributes")
            if not isinstance(attributes, Mapping) or _resolve(attributes, feature.path) is None:
                continue
            qualifier, unit = _feature_key(feature, attributes)
            if unit is None:
                raise ValueError(
                    f"'{feature.path}' no declara unidad en un registro; DS-01 exige unidad "
                    "explícita para toda magnitud."
                )
            keys.add((qualifier or "", unit))
        for qualifier, unit in sorted(keys):
            columns.append(
                Column(
                    name=_column_name(feature.path, qualifier or None, unit),
                    source=f"attributes.{feature.path}",
                    unit=unit,
                    qualifier=qualifier or None,
                    feature=feature,
                )
            )
    return columns


def _composition_columns(records: Sequence[Mapping[str, Any]]) -> list[Column]:
    keys = set()
    for record in records:
        attributes = record.get("attributes")
        items = attributes.get(COMPOSITION_PATH) if isinstance(attributes, Mapping) else None
        for item in items if isinstance(items, list) else []:
            if isinstance(item, Mapping) and item.get("value") is not None:
                keys.add((str(item.get("component_id")), str(item.get("unit"))))
    return [
        Column(
            name=_column_name(f"{COMPOSITION_PATH}.{component}", None, unit),
            source=f"attributes.{COMPOSITION_PATH}[component_id={component}].value",
            unit=unit,
            qualifier=component,
        )
        for component, unit in sorted(keys)
    ]


@dataclass(frozen=True)
class FeatureSchema:
    """Columnas declaradas de un dataset: features de nodo, de arista y target."""

    node: Mapping[str, tuple[Column, ...]]
    edge: Mapping[EdgeType, tuple[Column, ...]]
    target: Mapping[str, Column]
    target_kind: Mapping[str, str] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, Any]:
        """Entradas de `metadata.json` que exigen TEN-06, TEN-09 y DS-01 para `y`."""
        return {
            "feature_encoding": ENCODING_VERSION,
            "node_feature_schema": {
                node_type: [column.to_dict() for column in columns]
                for node_type, columns in self.node.items()
            },
            "edge_feature_schema": {
                "|".join(edge_type): [column.to_dict() for column in columns]
                for edge_type, columns in self.edge.items()
            },
            "target_schema": {
                target_type: {
                    "tensor": "y",
                    "mask": "y_mask",
                    "measured_or_predicted": self.target_kind[target_type],
                    "columns": [column.to_dict()],
                }
                for target_type, column in self.target.items()
            },
        }


def _type_order(node_type: str) -> tuple[int, str]:
    order = [node_type.value for node_type in NodeType]
    return (order.index(node_type) if node_type in order else len(order), node_type)


def derive_schema(
    nodes: Iterable[object], edges: Iterable[object], outputs: Iterable[object]
) -> FeatureSchema:
    """Deriva las columnas de todo el dataset, para que todas sus instancias compartan columnas.

    Lanza `ValueError` si una columna de arista o el target mezclaría unidades, matrices u
    orígenes: `edge_attr` no tiene máscara en DS-01, así que no puede separarse por unidad.
    """
    node_records = [_record(node) for node in nodes]
    edge_records = [_record(edge) for edge in edges]
    by_type: dict[str, list[Mapping[str, Any]]] = {}
    for record in node_records:
        by_type.setdefault(str(record.get("node_type")), []).append(record)

    node_schema: dict[str, tuple[Column, ...]] = {}
    for node_type in sorted(by_type, key=_type_order):
        records = by_type[node_type]
        columns = _feature_columns(NODE_FEATURES.get(node_type, ()), records)
        if node_type == NodeType.DIET.value:
            columns = _composition_columns(records) + columns
        node_schema[node_type] = tuple(columns)

    by_edge: dict[EdgeType, list[Mapping[str, Any]]] = {}
    for record in edge_records:
        edge_type = (
            str(record.get("source_type")),
            str(record.get("relation_type")),
            str(record.get("target_type")),
        )
        by_edge.setdefault(edge_type, []).append(record)
    edge_schema: dict[EdgeType, tuple[Column, ...]] = {}
    for edge_type in sorted(by_edge, key=lambda key: (_type_order(key[0]), key[1], key[2])):
        columns = _feature_columns(EDGE_FEATURES.get(edge_type, ()), by_edge[edge_type])
        names = [column.feature for column in columns]
        if len(names) != len(set(names)):
            raise ValueError(
                f"Una feature de {edge_type} tiene varias unidades; edge_attr no tiene máscara "
                "para separarlas sin ambigüedad."
            )
        edge_schema[edge_type] = tuple(columns)

    targets: dict[str, set[tuple[str, str, str]]] = {}
    for output in (_record(item) for item in outputs):
        kind = output.get("measured_or_predicted")
        if kind not in REFERENCE_KINDS:
            continue
        targets.setdefault(str(output.get("target_type")), set()).add(
            (str(kind), str(output.get("unit")), str(output.get("sample_matrix")))
        )
    target_schema: dict[str, Column] = {}
    target_kind: dict[str, str] = {}
    for target_type in sorted(targets, key=_type_order):
        variants = targets[target_type]
        if len(variants) != 1:
            raise ValueError(
                f"Las salidas de {target_type} mezclan origen, unidad o matriz {sorted(variants)}; "
                "y no puede combinarlas en una columna."
            )
        kind, unit, sample_matrix = next(iter(variants))
        target_schema[target_type] = Column(
            name=f"value ({unit}, {sample_matrix})",
            source="outputs.jsonl:value",
            unit=unit,
            qualifier=sample_matrix,
        )
        target_kind[target_type] = kind
    return FeatureSchema(node_schema, edge_schema, target_schema, target_kind)


# ---------------------------------------------------------------------------
# Conversión de una instancia
# ---------------------------------------------------------------------------


def _numeric(value: Any, where: str) -> float | None:
    """Valor de una celda; `None` si es ausente. Un valor no finito es un error de registro."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{where}: se esperaba un número; se recibió {value!r}.")
    if not math.isfinite(value):
        raise ValueError(f"{where}: valor no finito {value!r} (NOD-05); no se convierte.")
    return float(value)


def _cell(column: Column, record: Mapping[str, Any]) -> float | None:
    attributes = record.get("attributes")
    if not isinstance(attributes, Mapping):
        return None
    mask = record.get("missing_mask")
    where = f"{record.get('node_type')} {record.get('node_id')}, {column.name}"
    if column.feature is None:
        # Componente de la dieta.
        for item in attributes.get(COMPOSITION_PATH) or []:
            if (
                isinstance(item, Mapping)
                and item.get("component_id") == column.qualifier
                and item.get("unit") == column.unit
            ):
                return _numeric(item.get("value"), where)
        return None
    feature = column.feature
    if isinstance(mask, Mapping) and mask.get(feature.path) is True:
        return None
    qualifier, unit = _feature_key(feature, attributes)
    if unit != column.unit or (qualifier or None) != column.qualifier:
        return None
    return _numeric(_resolve(attributes, feature.path), where)


def _matrix(
    columns: Sequence[Column], records: Sequence[Mapping[str, Any]]
) -> tuple[torch.Tensor, torch.Tensor]:
    values = torch.zeros((len(records), len(columns)), dtype=torch.float32)
    missing = torch.zeros((len(records), len(columns)), dtype=torch.bool)
    for row, record in enumerate(records):
        for position, column in enumerate(columns):
            value = _cell(column, record)
            if value is None:
                missing[row, position] = True
            else:
                values[row, position] = value
    return values, missing


def build_heterodata(
    dataset: Any, graph_id: str, schema: FeatureSchema | None = None
) -> HeteroData:
    """Convierte la instancia `graph_id` en un `HeteroData` según DS-01.

    `dataset` tiene `instances`, `nodes`, `edges` y `outputs` (por ejemplo, un
    `SyntheticDataset`). `schema` fija las columnas; sin él se derivan del dataset completo. Se
    espera que los registros no tengan hallazgos `ERROR` (el orden de VG-01 impide convertir
    registros inválidos): ante una inconsistencia que impide convertir, lanza `ValueError`.
    Termina con `data.validate(raise_on_error=True)`, como exige DS-01.
    """
    schema = schema or derive_schema(dataset.nodes, dataset.edges, dataset.outputs)
    instance = next(
        (_record(item) for item in dataset.instances if _record(item).get("graph_id") == graph_id),
        None,
    )
    if instance is None:
        raise ValueError(f"No existe una instancia con graph_id {graph_id!r}.")

    data = HeteroData()
    by_type: dict[str, list[Mapping[str, Any]]] = {}
    for node in dataset.nodes:
        record = _record(node)
        if record.get("graph_id") == graph_id:
            by_type.setdefault(str(record["node_type"]), []).append(record)

    rows: dict[tuple[str, str], int] = {}
    for node_type in sorted(by_type, key=_type_order):
        records = sorted(by_type[node_type], key=lambda record: str(record["node_id"]))
        ids = [str(record["node_id"]) for record in records]
        if len(ids) != len(set(ids)):
            raise ValueError(f"node_id repetido en {node_type} de {graph_id} (NOD-03).")
        store = data[node_type]
        store.x, store.missing_mask = _matrix(schema.node.get(node_type, ()), records)
        store.node_id = ids
        store.source_id = [str(record["source_id"]) for record in records]
        store.raw_attributes = [copy.deepcopy(dict(record["attributes"])) for record in records]
        store.raw_missing_mask = [
            copy.deepcopy(dict(record.get("missing_mask") or {})) for record in records
        ]
        rows.update({(node_type, node_id): row for row, node_id in enumerate(ids)})

    by_edge: dict[EdgeType, list[Mapping[str, Any]]] = {}
    for edge in dataset.edges:
        record = _record(edge)
        if record.get("graph_id") == graph_id:
            edge_type = (
                str(record["source_type"]),
                str(record["relation_type"]),
                str(record["target_type"]),
            )
            by_edge.setdefault(edge_type, []).append(record)
    for edge_type in sorted(by_edge, key=lambda key: (_type_order(key[0]), key[1], key[2])):
        records = sorted(
            by_edge[edge_type],
            key=lambda record: tuple(str(record[name]) for name in _EDGE_KEY_FIELDS),
        )
        source_type, _, target_type = edge_type
        try:
            index = [
                [rows[(source_type, str(record["source_id"]))] for record in records],
                [rows[(target_type, str(record["target_id"]))] for record in records],
            ]
        except KeyError as error:
            raise ValueError(
                f"Arista de {edge_type} con un extremo inexistente (EDG-02)."
            ) from error
        columns = schema.edge.get(edge_type, ())
        attr = torch.zeros((len(records), len(columns)), dtype=torch.float32)
        for row, record in enumerate(records):
            for position, column in enumerate(columns):
                value = _numeric(
                    _resolve(record["attributes"], column.feature.path) if column.feature else None,
                    f"{edge_type} {record['source_id']}->{record['target_id']}, {column.name}",
                )
                if value is None:
                    raise ValueError(f"{edge_type}: falta '{column.name}' (EDG-05).")
                attr[row, position] = value
        store = data[edge_type]
        store.edge_index = torch.tensor(index, dtype=torch.long).reshape(2, len(records))
        store.edge_attr = attr
        store.evidence_id = [str(record["evidence_id"]) for record in records]
        store.evidence_status = [str(record["evidence_status"]) for record in records]
        store.evidence_method = [str(record["evidence_method"]) for record in records]
        store.raw_attributes = [copy.deepcopy(dict(record["attributes"])) for record in records]

    outputs = [
        dict(_record(output))
        for output in dataset.outputs
        if _record(output).get("graph_id") == graph_id
    ]
    data.output_records = copy.deepcopy(outputs)
    for target_type in schema.target:
        if target_type not in by_type:
            continue
        size = len(by_type[target_type])
        y = torch.zeros((size, 1), dtype=torch.float32)
        y_mask = torch.zeros((size, 1), dtype=torch.bool)
        for output in outputs:
            if (
                output.get("target_type") != target_type
                or output.get("measured_or_predicted") not in REFERENCE_KINDS
            ):
                continue
            target_row = rows.get((target_type, str(output.get("target_id"))))
            if target_row is None:
                raise ValueError(
                    f"Salida sobre un nodo inexistente {output.get('target_id')} (OUT-01)."
                )
            if y_mask[target_row, 0]:
                raise ValueError(f"Dos salidas de referencia para {output.get('target_id')}.")
            value = _numeric(output.get("value"), f"salida {output.get('target_id')}")
            if value is None:
                raise ValueError(f"Salida sin valor para {output.get('target_id')} (OUT-04).")
            y[target_row, 0] = value
            y_mask[target_row, 0] = True
        data[target_type].y = y
        data[target_type].y_mask = y_mask

    for name in _INSTANCE_FIELDS:
        value = instance.get(name)
        if value is not None:
            setattr(data, name, value)
    data.validate(raise_on_error=True)
    return data


# ---------------------------------------------------------------------------
# Round-trip hacia registros
# ---------------------------------------------------------------------------


def heterodata_to_records(data: HeteroData) -> dict[str, Any]:
    """Reconstruye los registros JSONL de un `HeteroData` construido por este módulo.

    Devuelve `instance`, `nodes`, `edges` y `outputs` como diccionarios, en el orden de
    exportación de DS-05. Comprueba el round-trip JSONL -> `HeteroData` -> JSONL de DS-01.
    """
    graph_id = data.graph_id
    instance = {name: getattr(data, name, None) for name in _INSTANCE_FIELDS}
    nodes = []
    for node_type, store in data.node_items():
        for row, node_id in enumerate(store.node_id):
            nodes.append(
                {
                    "graph_id": graph_id,
                    "node_id": node_id,
                    "node_type": node_type,
                    "source_id": store.source_id[row],
                    "attributes": copy.deepcopy(store.raw_attributes[row]),
                    "missing_mask": copy.deepcopy(store.raw_missing_mask[row]),
                }
            )
    edges = []
    for (source_type, relation_type, target_type), store in data.edge_items():
        source_ids = data[source_type].node_id
        target_ids = data[target_type].node_id
        for column in range(int(store.edge_index.size(1))):
            edges.append(
                {
                    "graph_id": graph_id,
                    "source_type": source_type,
                    "source_id": source_ids[int(store.edge_index[0, column])],
                    "relation_type": relation_type,
                    "target_type": target_type,
                    "target_id": target_ids[int(store.edge_index[1, column])],
                    "evidence_id": store.evidence_id[column],
                    "evidence_status": store.evidence_status[column],
                    "evidence_method": store.evidence_method[column],
                    "attributes": copy.deepcopy(store.raw_attributes[column]),
                }
            )
    nodes.sort(key=lambda node: (node["graph_id"], node["node_type"], node["node_id"]))
    edges.sort(key=lambda edge: tuple(edge[name] for name in _EDGE_KEY_FIELDS))
    outputs = sorted(
        copy.deepcopy(list(getattr(data, "output_records", []))),
        key=lambda output: (output["graph_id"], output["target_type"], output["target_id"]),
    )
    return {"instance": instance, "nodes": nodes, "edges": edges, "outputs": outputs}


# ---------------------------------------------------------------------------
# Construcción validada del dataset completo
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PrototypeGraphs:
    """Resultado de `build_synthetic_graphs`.

    `dataset` es el dataset de entrada con el esquema de features y target en sus metadatos,
    listo para exportar. `graphs` contiene solo los grafos entregables según la tabla de
    severidades, y `report` todos los hallazgos, incluidos los de tensores.
    """

    dataset: SyntheticDataset
    graphs: dict[str, HeteroData]
    report: ValidationReport


def build_synthetic_graphs(dataset: SyntheticDataset) -> PrototypeGraphs:
    """Declara el esquema, convierte las instancias válidas y aplica la compuerta de VG-07.

    Sigue el orden de evaluación de VG-01: primero valida los registros y solo convierte las
    instancias sin `ERROR`; después pasa los grafos por `prepare_graphs_for_model`, que evalúa
    las reglas de tensores y retiene los grafos con errores.
    """
    schema = derive_schema(dataset.nodes, dataset.edges, dataset.outputs)
    declared = replace(dataset, metadata={**dataset.metadata, **schema.to_metadata()})
    convertible = validate_graph(declared).deliverable_graph_ids
    graphs = {graph_id: build_heterodata(declared, graph_id, schema) for graph_id in convertible}
    delivered, report = prepare_graphs_for_model(declared, graphs)
    return PrototypeGraphs(declared, delivered, report)


# ---------------------------------------------------------------------------
# Serialización
# ---------------------------------------------------------------------------


def save_graphs(
    graphs: Mapping[str, HeteroData], directory: str | Path, *, overwrite: bool = False
) -> Path:
    """Guarda cada grafo como `graph_NNNN.pt` y un `manifest.json` con su `graph_id`.

    Los archivos se numeran en orden de `graph_id`, porque un `graph_id` sintético contiene `:`,
    que no es válido en nombres de archivo en todos los sistemas. Por seguridad no reemplaza un
    manifiesto existente salvo que `overwrite=True`; en ese caso elimina los `.pt` que listaba.
    """
    root = Path(directory)
    manifest_path = root / MANIFEST_FILE
    if manifest_path.exists():
        if not overwrite:
            raise FileExistsError(f"Ya existen grafos en {root}. Usa overwrite=True.")
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in previous.get("graphs", []):
            (root / str(entry["file"])).unlink(missing_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    entries = []
    for number, graph_id in enumerate(sorted(graphs), start=1):
        name = f"graph_{number:04d}.pt"
        torch.save(graphs[graph_id], root / name)
        entries.append({"graph_id": graph_id, "file": name})
    manifest = {
        "format": GRAPH_FORMAT,
        "format_version": GRAPH_FORMAT_VERSION,
        "feature_encoding": ENCODING_VERSION,
        "graphs": entries,
    }
    with manifest_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return root


def load_graphs(directory: str | Path) -> dict[str, HeteroData]:
    """Carga los grafos de un directorio escrito por `save_graphs`.

    Usa `torch.load(weights_only=True)` y solo permite las clases de almacenamiento de PyG, así
    que un `.pt` manipulado no puede ejecutar código arbitrario: la carga falla. Verifica que
    cada archivo contenga el `graph_id` que declara el manifiesto.
    """
    root = Path(directory)
    manifest = json.loads((root / MANIFEST_FILE).read_text(encoding="utf-8"))
    if manifest.get("format") != GRAPH_FORMAT:
        raise ValueError(f"{root / MANIFEST_FILE} no es un manifiesto de {GRAPH_FORMAT}.")
    graphs: dict[str, HeteroData] = {}
    with torch.serialization.safe_globals(list(_SAFE_PYG_CLASSES)):
        for entry in manifest["graphs"]:
            data = torch.load(root / str(entry["file"]), weights_only=True)
            if (
                not isinstance(data, HeteroData)
                or getattr(data, "graph_id", None) != entry["graph_id"]
            ):
                raise ValueError(f"{entry['file']} no contiene el grafo {entry['graph_id']}.")
            graphs[str(entry["graph_id"])] = data
    return graphs
