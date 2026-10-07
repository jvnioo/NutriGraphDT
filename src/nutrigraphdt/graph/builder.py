"""Constructor del grafo heterogéneo desde las tablas preprocesadas (A39-1, #35).

`build_hetero_graph` recibe un `NormalizedTabularDataset` (salida de `DataPipeline`, con el
contexto de `nutrigraphdt.data.integration.attach_sample_context`) y el esquema v1
(`nutrigraphdt.graph.schema`), y devuelve un `HeteroData` por instancia.

No reimplementa la codificación: traduce las tablas a registros del contrato DS-01
(`records_from_tables`) y reutiliza `build_heterodata`, de modo que un grafo real y uno
sintético tienen la misma estructura y pasan por las mismas reglas de integridad.

Traducción de las tablas a DS-01:

- **Nodos desde `features`.** Cada `(graph_id, node_type, node_id)` es un nodo. Los atributos
  numéricos del esquema v1 se llenan con la feature del mismo nombre y su unidad. Los atributos
  que las tablas no traen quedan en `null` con `missing_mask: true` (DS-01, ausencia de datos):
  nunca se inventa un valor. En `taxon`, `taxonomy_id` es `raw_id` o, si falta, el `node_id`, y
  `taxonomy_level` viene de la columna homónima de `features`.
- **Un nodo `host` por instancia** (`<sample_id>:host`), con la especie, el segmento y el
  estudio de la instancia, y como covariables sus features (por ejemplo, `body_weight_g`).
- **Un nodo `diet` por instancia con tratamiento conocido** (`<sample_id>:diet`), con el nombre
  del tratamiento. La composición no está en las tablas y queda ausente.
- **Targets → nodos `metabolite` y salidas.** Cada target crea el nodo del metabolito (sin
  concentración en sus atributos, para no filtrar el target a `x`) y su salida DS-01, que
  `build_heterodata` materializa en `y`.
- **Aristas.** Las de la tabla `edges` se traducen tal cual; una relación que no está en el
  esquema v1 es un error. Con `link_measurements`, cada metabolito medido se une a su huésped
  con `metabolite → measured_in → host` y `evidence_status="observed"`: la medición es un hecho
  de la fuente, no una inferencia.

Las relaciones inversas no forman parte del registro (EDG-01 las prohíbe): `add_reverse_edges`
las agrega sobre un grafo ya validado, solo para modelos de paso de mensajes que las necesiten.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from torch_geometric.data import HeteroData

from nutrigraphdt import __version__
from nutrigraphdt.data.integration import host_node_id
from nutrigraphdt.data.schema import NormalizedTabularDataset
from nutrigraphdt.data.synthetic.export import SCHEMA_VERSION
from nutrigraphdt.graph.heterodata import FeatureSchema, build_heterodata, derive_schema
from nutrigraphdt.graph.schema import (
    ALLOWED_RELATIONS,
    GRAPH_SCHEMA_VERSION,
    NODE_TYPES,
    NodeSpec,
    RelationSpec,
)

BUILDER_VERSION: Final = f"nutrigraphdt-builder {__version__}"

METABOLITE_TARGET_TYPES: Final = frozenset({"scfa_concentration", "metabolite_concentration"})
"""Targets tabulares que se materializan como `y` de nodos `metabolite`."""

EVIDENCE_STATUS_MAP: Final[Mapping[str, str]] = {
    "experimental": "observed",
    "literature": "annotated",
}
"""Vocabulario tabular → vocabulario DS-01; los demás valores ya coinciden."""

REVERSE_PREFIX: Final = "rev_"

EdgeType = tuple[str, str, str]


@dataclass(frozen=True)
class GraphRecords:
    """Registros DS-01 derivados de las tablas; cumple el protocolo de `validate_graph`."""

    metadata: dict[str, Any]
    instances: list[dict[str, Any]] = field(default_factory=list)
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class HeteroGraphs:
    """Resultado de `build_hetero_graph`: los registros, el esquema de features y los grafos."""

    records: GraphRecords
    feature_schema: FeatureSchema
    graphs: dict[str, HeteroData]


def _empty_attributes(spec: NodeSpec) -> dict[str, Any]:
    return dict.fromkeys(spec.attributes)


def _node(
    graph_id: str, node_type: str, node_id: str, source_id: str, attributes: dict[str, Any]
) -> dict[str, Any]:
    spec = NODE_TYPES[node_type]
    full = _empty_attributes(spec)
    full.update(attributes)
    return {
        "graph_id": graph_id,
        "node_id": node_id,
        "node_type": node_type,
        "source_id": source_id,
        "attributes": full,
        "missing_mask": {name: full[name] is None for name in spec.attributes},
    }


def _numeric_attributes(spec: NodeSpec, features: Sequence[Any]) -> dict[str, Any]:
    """Atributos numéricos del esquema llenos con la feature homónima y su unidad."""
    values: dict[str, Any] = {}
    by_name = {feature.feature_name: feature for feature in features}
    for name, attribute in spec.attributes.items():
        feature = by_name.get(name)
        if feature is None or attribute.data_type != "number":
            continue
        values[name] = feature.value
        if attribute.unit_field is not None and "." not in attribute.unit_field:
            values[attribute.unit_field] = feature.unit
    return values


def _feature_nodes(
    tables: NormalizedTabularDataset, instances: Mapping[str, Any]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[Any]] = {}
    for feature in tables.features:
        if feature.node_type not in NODE_TYPES:
            raise ValueError(
                f"Feature de tipo de nodo desconocido {feature.node_type!r} "
                f"({feature.graph_id}, {feature.node_id})."
            )
        grouped.setdefault((feature.graph_id, feature.node_type, feature.node_id), []).append(
            feature
        )
    nodes: list[dict[str, Any]] = []
    for (graph_id, node_type, node_id), features in sorted(grouped.items()):
        if graph_id not in instances:
            raise ValueError(f"Feature de {node_id} en una instancia inexistente {graph_id!r}.")
        if node_type == "host":
            continue  # se construye con el contexto de la instancia
        names = [feature.feature_name for feature in features]
        if len(names) != len(set(names)):
            raise ValueError(f"Feature repetida en {node_type} {node_id} de {graph_id}.")
        attributes = _numeric_attributes(NODE_TYPES[node_type], features)
        if node_type == "taxon":
            attributes["taxonomy_id"] = features[0].raw_id or node_id
            levels = {feature.taxonomy_level for feature in features} - {None}
            if len(levels) > 1:
                raise ValueError(f"Taxón {node_id} de {graph_id} con varios rangos {levels}.")
            attributes["taxonomy_level"] = levels.pop() if levels else None
        nodes.append(_node(graph_id, node_type, node_id, features[0].source_id, attributes))
    return nodes


def _host_node(instance: Any, tables: NormalizedTabularDataset) -> dict[str, Any]:
    node_id = host_node_id(instance.sample_id)
    covariates = {
        feature.feature_name: feature.value
        for feature in tables.features
        if feature.graph_id == instance.graph_id
        and feature.node_type == "host"
        and feature.node_id == node_id
    }
    return _node(
        instance.graph_id,
        "host",
        node_id,
        instance.source_id,
        {
            "species": instance.species,
            "gut_segment": instance.gut_segment,
            "cohort_id": instance.study_id,
            "covariates": dict(sorted(covariates.items())),
        },
    )


def _edge(
    graph_id: str,
    edge_type: EdgeType,
    source_id: str,
    target_id: str,
    *,
    evidence_status: str,
    evidence_method: str,
    evidence_id: str,
    attributes: dict[str, Any],
) -> dict[str, Any]:
    source_type, relation_type, target_type = edge_type
    return {
        "graph_id": graph_id,
        "source_type": source_type,
        "source_id": source_id,
        "relation_type": relation_type,
        "target_type": target_type,
        "target_id": target_id,
        "evidence_id": evidence_id,
        "evidence_status": evidence_status,
        "evidence_method": evidence_method,
        "attributes": attributes,
    }


def _relation(edge_type: EdgeType, schema: Mapping[EdgeType, RelationSpec]) -> RelationSpec:
    spec = schema.get(edge_type)
    if spec is None:
        raise ValueError(
            f"La relación {edge_type} no pertenece al esquema v1 ({GRAPH_SCHEMA_VERSION})."
        )
    return spec


def records_from_tables(
    tables: NormalizedTabularDataset,
    *,
    link_measurements: bool = True,
    relations: Mapping[EdgeType, RelationSpec] = ALLOWED_RELATIONS,
) -> GraphRecords:
    """Traduce las tablas normalizadas a registros DS-01 (ver el docstring del módulo).

    Lanza `ValueError` ante algo que no tiene traducción: un tipo de nodo o una relación fuera
    del esquema v1, una feature o un target de una instancia inexistente, o una feature
    repetida en un nodo.
    """
    instances = {instance.graph_id: instance for instance in tables.instances}
    if len(instances) != len(tables.instances):
        raise ValueError("graph_id repetido en la tabla de instancias.")
    is_synthetic = {instance.is_synthetic for instance in tables.instances}
    if len(is_synthetic) > 1:
        raise ValueError("Las tablas mezclan instancias sintéticas y reales.")

    nodes = _feature_nodes(tables, instances)
    edges: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    for graph_id, instance in sorted(instances.items()):
        nodes.append(_host_node(instance, tables))
        if instance.diet_treatment and instance.diet_treatment != "unknown":
            nodes.append(
                _node(
                    graph_id,
                    "diet",
                    f"{instance.sample_id}:diet",
                    instance.source_id,
                    {"name": instance.diet_treatment, "source_version": instance.source_id},
                )
            )

    metabolites: dict[tuple[str, str], dict[str, Any]] = {}
    for target in tables.targets:
        if target.graph_id not in instances:
            raise ValueError(f"Target de una instancia inexistente {target.graph_id!r}.")
        if target.target_type not in METABOLITE_TARGET_TYPES:
            continue
        key = (target.graph_id, target.target_id)
        if key in metabolites:
            raise ValueError(f"Dos targets para {target.target_id} en {target.graph_id}.")
        metabolites[key] = _node(
            target.graph_id,
            "metabolite",
            target.target_id,
            target.source_id,
            {
                "chemical_id": target.target_id,
                "name": target.target_id,
                "sample_matrix": target.sample_matrix,
                "unit": target.unit,
            },
        )
        outputs.append(
            {
                "graph_id": target.graph_id,
                "target_type": "metabolite",
                "target_id": target.target_id,
                "value": target.value,
                "measured_or_predicted": target.measured_or_predicted,
                "unit": target.unit,
                "sample_matrix": target.sample_matrix,
                "model_version": None,
            }
        )
        if link_measurements:
            instance = instances[target.graph_id]
            edge_type = ("metabolite", "measured_in", "host")
            _relation(edge_type, relations)
            edges.append(
                _edge(
                    target.graph_id,
                    edge_type,
                    target.target_id,
                    host_node_id(instance.sample_id),
                    evidence_status="observed",
                    evidence_method="measurement",
                    evidence_id=f"{target.source_id}:{instance.sample_id}:{target.target_id}",
                    attributes={"sample_matrix": target.sample_matrix},
                )
            )
    nodes.extend(metabolites[key] for key in sorted(metabolites))

    for row in tables.edges:
        if row.graph_id not in instances:
            raise ValueError(f"Arista de una instancia inexistente {row.graph_id!r}.")
        edge_type = (row.src_type, row.relation_type, row.dst_type)
        _relation(edge_type, relations)
        edges.append(
            _edge(
                row.graph_id,
                edge_type,
                row.src_id,
                row.dst_id,
                evidence_status=EVIDENCE_STATUS_MAP.get(row.evidence_status, row.evidence_status),
                evidence_method=f"table:{row.source_id}",
                evidence_id=f"{row.source_id}:{row.src_id}:{row.relation_type}:{row.dst_id}",
                attributes={},
            )
        )

    instance_records = [
        {
            "graph_id": instance.graph_id,
            "species": instance.species,
            "gut_segment": instance.gut_segment,
            "study_id": instance.study_id,
            "sample_id": instance.sample_id,
            "scenario_id": instance.scenario_id,
            "diet_treatment": instance.diet_treatment,
            "timepoint": instance.timepoint,
            "is_synthetic": instance.is_synthetic,
            "schema_version": SCHEMA_VERSION,
            "generator_version": BUILDER_VERSION,
        }
        for _, instance in sorted(instances.items())
    ]
    metadata = {
        "dataset_id": ",".join(sorted({i.source_id for i in tables.instances})),
        "schema_version": SCHEMA_VERSION,
        "graph_schema_version": GRAPH_SCHEMA_VERSION,
        "generator_version": BUILDER_VERSION,
        "is_synthetic": True in is_synthetic,
        "random_seed": None,
        "configuration": {
            "builder": "records_from_tables",
            "link_measurements": link_measurements,
            "tables": dict(tables.metadata.get("pipeline", {}))
            if isinstance(tables.metadata.get("pipeline"), Mapping)
            else {},
        },
        "counts": _counts(nodes, edges, outputs),
    }
    order = {node_type: position for position, node_type in enumerate(NODE_TYPES)}
    nodes.sort(key=lambda n: (n["graph_id"], order[n["node_type"]], n["node_id"]))
    edges.sort(key=lambda e: (e["graph_id"], e["relation_type"], e["source_id"], e["target_id"]))
    outputs.sort(key=lambda o: (o["graph_id"], o["target_id"]))
    return GraphRecords(metadata, instance_records, nodes, edges, outputs)


def _counts(
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    outputs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    counts: dict[str, Any] = {}
    for node in nodes:
        entry = counts.setdefault(node["graph_id"], {"nodes": {}, "edges": {}, "outputs": 0})
        entry["nodes"][node["node_type"]] = entry["nodes"].get(node["node_type"], 0) + 1
    for edge in edges:
        entry = counts.setdefault(edge["graph_id"], {"nodes": {}, "edges": {}, "outputs": 0})
        key = "|".join((edge["source_type"], edge["relation_type"], edge["target_type"]))
        entry["edges"][key] = entry["edges"].get(key, 0) + 1
    for output in outputs:
        entry = counts.setdefault(output["graph_id"], {"nodes": {}, "edges": {}, "outputs": 0})
        entry["outputs"] += 1
    return counts


def build_hetero_graph(
    tables: NormalizedTabularDataset,
    schema: Mapping[EdgeType, RelationSpec] = ALLOWED_RELATIONS,
    *,
    link_measurements: bool = True,
) -> HeteroGraphs:
    """Construye un `HeteroData` por instancia desde las tablas preprocesadas.

    Todas las instancias comparten las columnas de features (`derive_schema` sobre el dataset
    completo), declaradas en `records.metadata` como exige TEN-06. Para la misma entrada el
    resultado es idéntico: nodos, aristas y columnas se ordenan de forma determinista.

    No aplica la compuerta de entrega: valide con `validate_graph(result.records)` y
    `prepare_graphs_for_model` antes de entrenar (ver `docs/graph/graph-builder.md`).
    """
    records = records_from_tables(tables, link_measurements=link_measurements, relations=schema)
    feature_schema = derive_schema(records.nodes, records.edges, records.outputs)
    records.metadata.update(feature_schema.to_metadata())
    graphs = {
        instance["graph_id"]: build_heterodata(records, instance["graph_id"], feature_schema)
        for instance in records.instances
    }
    return HeteroGraphs(records, feature_schema, graphs)


def add_reverse_edges(data: HeteroData) -> HeteroData:
    """Copia de `data` con una relación inversa `rev_<relación>` por cada relación dirigida.

    Para modelos de paso de mensajes que necesitan propagar en ambos sentidos. Se aplica
    después de validar: EDG-01 prohíbe las inversas en los registros, y las reglas `TEN` no
    las reconocen. `edge_attr` y la evidencia se copian en el mismo orden de columnas.
    """
    result = data.clone()
    for edge_type in list(data.edge_types):
        source_type, relation, target_type = edge_type
        if relation.startswith(REVERSE_PREFIX):
            continue
        store = data[edge_type]
        reverse = result[(target_type, f"{REVERSE_PREFIX}{relation}", source_type)]
        reverse.edge_index = store.edge_index.flip(0).contiguous()
        if "edge_attr" in store:
            reverse.edge_attr = store.edge_attr.clone()
        for name in ("evidence_id", "evidence_status", "evidence_method"):
            if name in store:
                reverse[name] = list(store[name])
    result.validate(raise_on_error=True)
    return result


__all__ = [
    "BUILDER_VERSION",
    "GraphRecords",
    "HeteroGraphs",
    "add_reverse_edges",
    "build_hetero_graph",
    "records_from_tables",
]
