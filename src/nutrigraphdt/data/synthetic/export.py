"""Exportación y carga reproducible del dataset sintético para NutriGraphDT (DS-05).

Implementa el formato de intercambio y auditoría definido en
`docs/synthetic-dataset/synthetic-dataset-spec.md` (sección "Serialización y organización de
archivos"):

```text
<directorio>/
├── metadata.json
└── raw/
    ├── nodes.jsonl
    ├── edges.jsonl
    ├── instances.jsonl
    └── outputs.jsonl
```

Alcance de esta versión:

- Exporta los escenarios basal e intervenido de DS-04 (`generate_scenario_dataset`) o una
  instancia construida con configuraciones propias (`generate_synthetic_dataset`).
- Exporta a JSON Lines en UTF-8, con un objeto por línea, saltos de línea `\\n` en todos los
  sistemas operativos y el orden determinista exigido por la especificación.
- Carga los archivos de vuelta sin pérdida: `load_dataset(export_dataset(ds))` es igual a `ds`.
- Misma versión del generador, configuración y semilla producen archivos idénticos byte a byte.
- Por defecto, `outputs.jsonl` contiene los targets sintéticos de AGCC (`targets.py`, A35-1):
  una salida `synthetic` por metabolito objetivo. Con `target_config=None` queda vacío.
- La conversión a `HeteroData` y la serialización `.pt` están en la capa `graph`
  (`nutrigraphdt.graph.heterodata`), porque requieren PyTorch. Este módulo exporta
  `node_feature_schema` y `edge_feature_schema` vacíos; quien construye los grafos los declara.

Todo el contenido es sintético (`is_synthetic = true`). No representa observaciones reales.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from nutrigraphdt import __version__
from nutrigraphdt.data.synthetic.edges import (
    Edge,
    SyntheticEdgeConfig,
    edge_sort_key,
    find_edge_errors,
    generate_synthetic_edges,
)
from nutrigraphdt.data.synthetic.nodes import (
    Node,
    NodeType,
    SyntheticNodeConfig,
    generate_synthetic_nodes,
)

# DS-04 no expone públicamente su semilla ni sus configuraciones; se leen de sus nombres
# internos para que metadata.json registre exactamente lo que se usó. Si DS-04 las publica,
# basta con cambiar estas importaciones.
from nutrigraphdt.data.synthetic.scenarios import (
    _SHARED_EDGE_CONFIG as SCENARIO_EDGE_CONFIG,
)
from nutrigraphdt.data.synthetic.scenarios import (
    ScenarioInstance,
    build_basal_scenario,
    build_intervened_scenario,
)
from nutrigraphdt.data.synthetic.scenarios import (
    _base_node_config as scenario_node_config,
)
from nutrigraphdt.data.synthetic.targets import (
    DEFAULT_TARGET_CONFIG,
    SyntheticTargetConfig,
    generate_synthetic_targets,
)

SCHEMA_VERSION = "1.0.0"
"""Versión del contrato de `docs/synthetic-dataset/synthetic-dataset-spec.md` que implementa este
módulo."""

GENERATOR_VERSION = __version__
"""Versión del paquete que genera el dataset."""

DEFAULT_DATASET_ID = "synthetic-v1"
DEFAULT_SCENARIO_DATASET_ID = "synthetic-scenarios-v1"
DEFAULT_SCENARIO_SAMPLE_ID = "synthetic:sample:0001"
DEFAULT_STUDY_ID = "SYNTHETIC_V1"
DEFAULT_SCENARIO_ID = "basal"
DEFAULT_DIET_TREATMENT = "synthetic_basal_diet"

METADATA_FILE = "metadata.json"
RAW_DIR = "raw"
NODES_FILE = "nodes.jsonl"
EDGES_FILE = "edges.jsonl"
INSTANCES_FILE = "instances.jsonl"
OUTPUTS_FILE = "outputs.jsonl"

SCENARIO_IDS: frozenset[str] = frozenset({"basal", "intervention"})
MEASUREMENT_KINDS: frozenset[str] = frozenset({"measured", "predicted", "synthetic"})

_NODE_FIELDS: tuple[str, ...] = (
    "graph_id",
    "node_id",
    "node_type",
    "source_id",
    "attributes",
    "missing_mask",
)


class DatasetFormatError(ValueError):
    """Un archivo del dataset no tiene el formato o los campos que exige el contrato."""


class DatasetValidationError(ValueError):
    """El dataset no cumple las reglas de integridad de la especificación."""


# ---------------------------------------------------------------------------
# Utilidades de tipos estrictos
# ---------------------------------------------------------------------------


def _require_str(data: Mapping[str, Any], name: str) -> str:
    value = data[name]
    if not isinstance(value, str) or not value:
        raise ValueError(f"El campo '{name}' debe ser una cadena no vacía; se recibió {value!r}.")
    return value


def _require_optional_str(data: Mapping[str, Any], name: str) -> str | None:
    value = data[name]
    if value is None:
        return None
    return _require_str(data, name)


def _require_number(data: Mapping[str, Any], name: str) -> float | int:
    value = data[name]
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ValueError(f"El campo '{name}' debe ser un número finito; se recibió {value!r}.")
    return value


def _require_bool(data: Mapping[str, Any], name: str) -> bool:
    value = data[name]
    if not isinstance(value, bool):
        raise ValueError(f"El campo '{name}' debe ser booleano; se recibió {value!r}.")
    return value


def _require_object(data: Mapping[str, Any], name: str) -> dict[str, Any]:
    value = data[name]
    if not isinstance(value, dict):
        raise ValueError(f"El campo '{name}' debe ser un objeto; se recibió {value!r}.")
    return dict(value)


# ---------------------------------------------------------------------------
# Registros de instancia y salida
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InstanceRecord:
    """Registro de `instances.jsonl` según el contrato de instancia."""

    graph_id: str
    species: str
    gut_segment: str
    study_id: str
    sample_id: str
    scenario_id: str
    diet_treatment: str
    timepoint: str | None = None
    is_synthetic: bool = True
    schema_version: str = SCHEMA_VERSION
    generator_version: str = GENERATOR_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Serializa la instancia a un diccionario compatible con JSON/JSONL."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> InstanceRecord:
        """Construye una instancia validando la presencia y el tipo de cada campo."""
        return cls(
            graph_id=_require_str(data, "graph_id"),
            species=_require_str(data, "species"),
            gut_segment=_require_str(data, "gut_segment"),
            study_id=_require_str(data, "study_id"),
            sample_id=_require_str(data, "sample_id"),
            scenario_id=_require_str(data, "scenario_id"),
            diet_treatment=_require_str(data, "diet_treatment"),
            timepoint=_require_optional_str(data, "timepoint"),
            is_synthetic=_require_bool(data, "is_synthetic"),
            schema_version=_require_str(data, "schema_version"),
            generator_version=_require_str(data, "generator_version"),
        )


@dataclass(frozen=True)
class OutputRecord:
    """Registro de `outputs.jsonl` según el contrato de salida.

    El generador actual no produce salidas; el tipo existe para que `outputs.jsonl` conserve
    su estructura y pueda cargarse sin pérdida cuando una tarea posterior genere targets.
    """

    graph_id: str
    target_type: str
    target_id: str
    value: float | int
    measured_or_predicted: str
    unit: str
    sample_matrix: str
    model_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serializa la salida a un diccionario compatible con JSON/JSONL."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> OutputRecord:
        """Construye una salida validando la presencia y el tipo de cada campo."""
        return cls(
            graph_id=_require_str(data, "graph_id"),
            target_type=_require_str(data, "target_type"),
            target_id=_require_str(data, "target_id"),
            value=_require_number(data, "value"),
            measured_or_predicted=_require_str(data, "measured_or_predicted"),
            unit=_require_str(data, "unit"),
            sample_matrix=_require_str(data, "sample_matrix"),
            model_version=_require_optional_str(data, "model_version"),
        )


def _node_from_dict(data: Mapping[str, Any]) -> Node:
    """Construye un nodo sin convertir silenciosamente valores inválidos a texto."""
    for name in ("graph_id", "node_id", "node_type", "source_id"):
        _require_str(data, name)
    _require_object(data, "attributes")
    mask = _require_object(data, "missing_mask")
    if not all(isinstance(value, bool) for value in mask.values()):
        raise ValueError("Los valores de 'missing_mask' deben ser booleanos.")
    return Node.from_dict(dict(data))


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------


def _instance_sort_key(instance: InstanceRecord) -> str:
    return instance.graph_id


def _node_sort_key(node: Node) -> tuple[str, str, str]:
    return (node.graph_id, node.node_type, node.node_id)


def _output_sort_key(output: OutputRecord) -> tuple[str, str, str]:
    return (output.graph_id, output.target_type, output.target_id)


@dataclass(frozen=True)
class SyntheticDataset:
    """Contenido completo de un dataset sintético exportable.

    Las listas se guardan en el orden determinista de la especificación, de modo que dos
    datasets con el mismo contenido son iguales aunque sus registros se hayan entregado en
    otro orden.
    """

    metadata: dict[str, Any]
    instances: list[InstanceRecord]
    nodes: list[Node]
    edges: list[Edge]
    outputs: list[OutputRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "instances", sorted(self.instances, key=_instance_sort_key))
        object.__setattr__(self, "nodes", sorted(self.nodes, key=_node_sort_key))
        object.__setattr__(self, "edges", sorted(self.edges, key=edge_sort_key))
        object.__setattr__(self, "outputs", sorted(self.outputs, key=_output_sort_key))


def _edge_type_key(source_type: str, relation_type: str, target_type: str) -> str:
    """Clave de texto para una tupla de relación; JSON no admite tuplas como claves."""
    return f"{source_type}|{relation_type}|{target_type}"


def _edge_config_to_dict(config: SyntheticEdgeConfig) -> dict[str, Any]:
    return {
        "random_seed": config.random_seed,
        "evidence_id": config.evidence_id,
        "evidence_method": config.evidence_method,
        "relation_probabilities": {
            _edge_type_key(*edge_type): float(probability)
            for edge_type, probability in sorted(config.relation_probabilities.items())
        },
        "interaction_types": list(config.interaction_types),
        "non_modulating_control_labels": list(config.non_modulating_control_labels),
    }


def _sorted_values(nodes: Iterable[Node], node_type: str, attribute: str) -> list[str]:
    return sorted(
        {
            str(node.attributes[attribute])
            for node in nodes
            if node.node_type == node_type and node.attributes.get(attribute) is not None
        }
    )


def _counts(
    instances: Sequence[InstanceRecord],
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    outputs: Sequence[OutputRecord],
) -> dict[str, Any]:
    node_counts = Counter((node.graph_id, node.node_type) for node in nodes)
    edge_counts = Counter((edge.graph_id, _edge_type_key(*edge.edge_type)) for edge in edges)
    output_counts = Counter(output.graph_id for output in outputs)
    counts: dict[str, Any] = {}
    for instance in sorted(instances, key=_instance_sort_key):
        graph_id = instance.graph_id
        counts[graph_id] = {
            "nodes": {
                node_type.value: node_counts[(graph_id, node_type.value)] for node_type in NodeType
            },
            "edges": {
                key: count for (gid, key), count in sorted(edge_counts.items()) if gid == graph_id
            },
            "outputs": output_counts[graph_id],
        }
    return counts


def build_metadata(
    *,
    dataset_id: str,
    random_seed: int,
    configuration: Mapping[str, Any],
    instances: Sequence[InstanceRecord],
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    outputs: Sequence[OutputRecord],
    interaction_types: Sequence[str] = (),
) -> dict[str, Any]:
    """Construye `metadata.json` con los campos mínimos de la especificación.

    Además de los campos mínimos, declara los vocabularios provisionales que la especificación
    pide registrar (`function_type`, `annotation_value_type` e `interaction_type`). No contiene
    fechas, rutas locales ni otros valores no deterministas.
    """
    return {
        "dataset_id": dataset_id,
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "is_synthetic": True,
        "random_seed": random_seed,
        "configuration": json.loads(json.dumps(configuration)),
        "node_feature_schema": {},
        "edge_feature_schema": {},
        "vocabularies": {
            "function_type": _sorted_values(nodes, NodeType.FUNCTION.value, "function_type"),
            "annotation_value_type": _sorted_values(
                nodes, NodeType.FUNCTION.value, "annotation_value_type"
            ),
            "interaction_type": sorted(set(interaction_types)),
        },
        "counts": _counts(instances, nodes, edges, outputs),
    }


def _default_sample_id(graph_id: str) -> str:
    """Deriva un `sample_id` sintético determinista desde el `graph_id`."""
    return f"synthetic:sample:{graph_id.rsplit(':', 1)[-1]}"


def generate_synthetic_dataset(
    node_config: SyntheticNodeConfig | None = None,
    edge_config: SyntheticEdgeConfig | None = None,
    *,
    dataset_id: str = DEFAULT_DATASET_ID,
    scenario_id: str = DEFAULT_SCENARIO_ID,
    diet_treatment: str = DEFAULT_DIET_TREATMENT,
    sample_id: str | None = None,
    target_config: SyntheticTargetConfig | None = DEFAULT_TARGET_CONFIG,
) -> SyntheticDataset:
    """Genera una instancia sintética completa (nodos, aristas e instancia) lista para exportar.

    Hasta que exista el generador de escenarios (DS-04), produce una sola instancia por
    configuración de nodos. La semilla de nodos y la de aristas deben coincidir para que el
    dataset quede identificado por una única `random_seed` en `metadata.json`.

    `target_config` define los targets sintéticos de AGCC (`outputs`); con `None` no se generan.
    """
    node_config = node_config or SyntheticNodeConfig()
    edge_config = edge_config or SyntheticEdgeConfig()
    if node_config.random_seed != edge_config.random_seed:
        raise ValueError(
            "La semilla de nodos y la de aristas deben coincidir para identificar el dataset "
            f"con una sola semilla; se recibieron {node_config.random_seed} y "
            f"{edge_config.random_seed}."
        )
    if scenario_id not in SCENARIO_IDS:
        raise ValueError(f"scenario_id debe ser uno de {sorted(SCENARIO_IDS)}: {scenario_id!r}.")

    nodes = generate_synthetic_nodes(node_config)
    edges = generate_synthetic_edges(nodes, edge_config)
    instance = InstanceRecord(
        graph_id=node_config.graph_id,
        species=node_config.species,
        gut_segment=node_config.gut_segment,
        study_id=DEFAULT_STUDY_ID,
        sample_id=sample_id or _default_sample_id(node_config.graph_id),
        scenario_id=scenario_id,
        diet_treatment=diet_treatment,
    )
    outputs = generate_synthetic_targets(nodes, target_config) if target_config else []
    configuration = {
        "nodes": asdict(node_config),
        "edges": _edge_config_to_dict(edge_config),
        "instance": {"scenario_id": scenario_id, "diet_treatment": diet_treatment},
        "targets": target_config.to_dict() if target_config else None,
    }
    metadata = build_metadata(
        dataset_id=dataset_id,
        random_seed=node_config.random_seed,
        configuration=configuration,
        instances=[instance],
        nodes=nodes,
        edges=edges,
        outputs=outputs,
        interaction_types=edge_config.interaction_types,
    )
    return SyntheticDataset(
        metadata=metadata, instances=[instance], nodes=nodes, edges=edges, outputs=outputs
    )


def _host_attribute(nodes: Sequence[Node], name: str) -> str:
    """Lee un atributo de texto común a los nodos `host` de una instancia."""
    values = {node.attributes.get(name) for node in nodes if node.node_type == NodeType.HOST.value}
    if len(values) != 1:
        raise ValueError(f"Los nodos host deben declarar un único '{name}'; se encontró {values}.")
    value = values.pop()
    if not isinstance(value, str) or not value:
        raise ValueError(f"El atributo '{name}' del host debe ser una cadena no vacía.")
    return value


def instance_from_scenario(
    scenario: ScenarioInstance,
    *,
    sample_id: str = DEFAULT_SCENARIO_SAMPLE_ID,
    study_id: str = DEFAULT_STUDY_ID,
    basal_diet_treatment: str = DEFAULT_DIET_TREATMENT,
) -> InstanceRecord:
    """Construye el registro de `instances.jsonl` de un escenario de DS-04.

    `species` y `gut_segment` se leen de los nodos `host` del escenario. Los dos escenarios
    comparten `sample_id` porque la especificación los define como instancias comparables de
    una misma muestra. `diet_treatment` identifica la intervención sin afirmar ningún efecto.
    """
    if scenario.intervention_variable is None:
        scenario_id = "basal"
        diet_treatment = basal_diet_treatment
    else:
        scenario_id = "intervention"
        diet_treatment = (
            f"{basal_diet_treatment}:{scenario.intervention_variable}={scenario.intervention_value}"
        )
    return InstanceRecord(
        graph_id=scenario.graph_id,
        species=_host_attribute(scenario.nodes, "species"),
        gut_segment=_host_attribute(scenario.nodes, "gut_segment"),
        study_id=study_id,
        sample_id=sample_id,
        scenario_id=scenario_id,
        diet_treatment=diet_treatment,
    )


def generate_scenario_dataset(
    *,
    dataset_id: str = DEFAULT_SCENARIO_DATASET_ID,
    target_config: SyntheticTargetConfig | None = DEFAULT_TARGET_CONFIG,
) -> SyntheticDataset:
    """Genera el dataset con los escenarios basal e intervenido de DS-04.

    La semilla y las configuraciones se toman del módulo `scenarios`, de modo que el dataset
    exportado refleja exactamente lo que construyen `build_basal_scenario` y
    `build_intervened_scenario`. `target_config` define los targets sintéticos de AGCC de cada
    escenario; con `None` no se generan.
    """
    scenarios = [build_basal_scenario(), build_intervened_scenario()]
    instances = [instance_from_scenario(scenario) for scenario in scenarios]
    nodes = [node for scenario in scenarios for node in scenario.nodes]
    edges = [edge for scenario in scenarios for edge in scenario.edges]
    outputs = generate_synthetic_targets(nodes, target_config) if target_config else []
    configuration = {
        "source": "nutrigraphdt.data.synthetic.scenarios",
        "edges": _edge_config_to_dict(SCENARIO_EDGE_CONFIG),
        "scenarios": [
            {
                "graph_id": scenario.graph_id,
                "intervention_label": scenario.intervention_label,
                "intervention_variable": scenario.intervention_variable,
                "intervention_value": scenario.intervention_value,
                "nodes": asdict(scenario_node_config(scenario.graph_id)),
            }
            for scenario in scenarios
        ],
        "targets": target_config.to_dict() if target_config else None,
    }
    metadata = build_metadata(
        dataset_id=dataset_id,
        random_seed=SCENARIO_EDGE_CONFIG.random_seed,
        configuration=configuration,
        instances=instances,
        nodes=nodes,
        edges=edges,
        outputs=outputs,
        interaction_types=SCENARIO_EDGE_CONFIG.interaction_types,
    )
    return SyntheticDataset(
        metadata=metadata, instances=instances, nodes=nodes, edges=edges, outputs=outputs
    )


# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------


def find_dataset_errors(dataset: SyntheticDataset) -> list[str]:
    """Devuelve los incumplimientos de integridad del dataset; lista vacía si es válido."""
    errors: list[str] = []
    metadata = dataset.metadata
    for name in (
        "dataset_id",
        "schema_version",
        "generator_version",
        "is_synthetic",
        "random_seed",
        "configuration",
        "node_feature_schema",
        "edge_feature_schema",
        "counts",
    ):
        if name not in metadata:
            errors.append(f"metadata: falta el campo obligatorio '{name}'.")
    if metadata.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"metadata: schema_version {metadata.get('schema_version')!r} no es compatible "
            f"con {SCHEMA_VERSION!r}."
        )
    if metadata.get("is_synthetic") is not True:
        errors.append("metadata: is_synthetic debe ser true.")
    seed = metadata.get("random_seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        errors.append("metadata: random_seed debe ser un entero.")

    graph_ids: set[str] = set()
    for instance in dataset.instances:
        if instance.graph_id in graph_ids:
            errors.append(f"instancia repetida: {instance.graph_id}.")
        graph_ids.add(instance.graph_id)
        if not instance.is_synthetic:
            errors.append(f"instancia {instance.graph_id}: is_synthetic debe ser true.")
        if instance.schema_version != SCHEMA_VERSION:
            errors.append(f"instancia {instance.graph_id}: schema_version no compatible.")
        if instance.scenario_id not in SCENARIO_IDS:
            errors.append(
                f"instancia {instance.graph_id}: scenario_id no válido: {instance.scenario_id!r}."
            )

    known_types = {node_type.value for node_type in NodeType}
    seen_nodes: set[tuple[str, str, str]] = set()
    for node in dataset.nodes:
        key = _node_sort_key(node)
        if key in seen_nodes:
            errors.append(f"nodo repetido en {node.graph_id}/{node.node_type}: {node.node_id}.")
        seen_nodes.add(key)
        if node.graph_id not in graph_ids:
            errors.append(f"nodo {node.node_id}: graph_id {node.graph_id!r} sin instancia.")
        if node.node_type not in known_types:
            errors.append(f"nodo {node.node_id}: tipo desconocido {node.node_type!r}.")

    for edge in dataset.edges:
        if edge.graph_id not in graph_ids:
            errors.append(
                f"arista {edge.source_id}->{edge.target_id}: graph_id {edge.graph_id!r} "
                "sin instancia."
            )
    errors.extend(find_edge_errors(dataset.nodes, dataset.edges))

    for output in dataset.outputs:
        label = f"salida {output.graph_id}/{output.target_type}/{output.target_id}"
        if (output.graph_id, output.target_type, output.target_id) not in seen_nodes:
            errors.append(f"{label}: el nodo objetivo no existe en la instancia.")
        if output.measured_or_predicted not in MEASUREMENT_KINDS:
            errors.append(
                f"{label}: measured_or_predicted no válido: {output.measured_or_predicted!r}."
            )
        elif output.measured_or_predicted == "predicted" and output.model_version is None:
            errors.append(f"{label}: una predicción debe declarar model_version.")
        elif output.measured_or_predicted != "predicted" and output.model_version is not None:
            errors.append(f"{label}: model_version debe ser null si no es una predicción.")
    return errors


def validate_dataset(dataset: SyntheticDataset) -> None:
    """Lanza `DatasetValidationError` con todos los incumplimientos encontrados."""
    errors = find_dataset_errors(dataset)
    if errors:
        raise DatasetValidationError("\n".join(errors))


# ---------------------------------------------------------------------------
# Escritura y lectura
# ---------------------------------------------------------------------------


def _dumps(record: Mapping[str, Any], *, indent: int | None = None) -> str:
    """Serialización JSON determinista; rechaza `NaN` e infinitos."""
    separators = (",", ": ") if indent is not None else (",", ":")
    return json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        allow_nan=False,
        indent=indent,
        separators=separators,
    )


def _write_text(path: Path, text: str) -> None:
    # newline="\n" evita que Windows escriba "\r\n" y rompa la igualdad byte a byte.
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    _write_text(path, "".join(f"{_dumps(record)}\n" for record in records))


def export_dataset(
    dataset: SyntheticDataset, output_dir: str | Path, *, overwrite: bool = False
) -> Path:
    """Valida el dataset y lo escribe en `output_dir` con el formato de la especificación.

    Por seguridad no reemplaza un `metadata.json` existente salvo que `overwrite=True`.
    Devuelve la ruta del directorio exportado.
    """
    validate_dataset(dataset)
    root = Path(output_dir)
    metadata_path = root / METADATA_FILE
    if metadata_path.exists() and not overwrite:
        raise FileExistsError(
            f"Ya existe un dataset en {root}. Usa overwrite=True para reemplazarlo."
        )
    raw = root / RAW_DIR
    raw.mkdir(parents=True, exist_ok=True)

    _write_jsonl(raw / INSTANCES_FILE, (instance.to_dict() for instance in dataset.instances))
    _write_jsonl(raw / NODES_FILE, (node.to_dict() for node in dataset.nodes))
    _write_jsonl(raw / EDGES_FILE, (edge.to_dict() for edge in dataset.edges))
    _write_jsonl(raw / OUTPUTS_FILE, (output.to_dict() for output in dataset.outputs))
    # metadata.json se escribe al final: su presencia indica una exportación completa.
    _write_text(metadata_path, _dumps(dataset.metadata, indent=2) + "\n")
    return root


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise DatasetFormatError(f"No existe el archivo obligatorio {path}.")
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                raise DatasetFormatError(f"{path}:{line_number}: línea vacía no permitida.")
            try:
                record = json.loads(line, parse_constant=_reject_constant)
            except json.JSONDecodeError as error:
                raise DatasetFormatError(
                    f"{path}:{line_number}: JSON no válido: {error}"
                ) from error
            if not isinstance(record, dict):
                raise DatasetFormatError(f"{path}:{line_number}: cada línea debe ser un objeto.")
            records.append(record)
    return records


def _reject_constant(name: str) -> Any:
    raise DatasetFormatError(f"Valor numérico no finito no permitido en JSON: {name}.")


def _parse_records(path: Path, parse: Any) -> list[Any]:
    parsed: list[Any] = []
    for line_number, record in enumerate(_read_jsonl(path), start=1):
        try:
            parsed.append(parse(record))
        except (KeyError, TypeError, ValueError) as error:
            raise DatasetFormatError(
                f"{path}:{line_number}: registro no válido: {error}"
            ) from error
    return parsed


def load_dataset(input_dir: str | Path) -> SyntheticDataset:
    """Carga un dataset exportado con `export_dataset` y comprueba su integridad."""
    root = Path(input_dir)
    metadata_path = root / METADATA_FILE
    if not metadata_path.is_file():
        raise DatasetFormatError(f"No existe {metadata_path}.")
    try:
        metadata = json.loads(
            metadata_path.read_text(encoding="utf-8"), parse_constant=_reject_constant
        )
    except json.JSONDecodeError as error:
        raise DatasetFormatError(f"{metadata_path}: JSON no válido: {error}") from error
    if not isinstance(metadata, dict):
        raise DatasetFormatError(f"{metadata_path}: debe contener un objeto JSON.")
    if metadata.get("schema_version") != SCHEMA_VERSION:
        raise DatasetFormatError(
            f"{metadata_path}: schema_version {metadata.get('schema_version')!r} no es "
            f"compatible con {SCHEMA_VERSION!r}."
        )

    raw = root / RAW_DIR
    dataset = SyntheticDataset(
        metadata=metadata,
        instances=_parse_records(raw / INSTANCES_FILE, InstanceRecord.from_dict),
        nodes=_parse_records(raw / NODES_FILE, _node_from_dict),
        edges=_parse_records(raw / EDGES_FILE, Edge.from_dict),
        outputs=_parse_records(raw / OUTPUTS_FILE, OutputRecord.from_dict),
    )
    validate_dataset(dataset)
    return dataset
