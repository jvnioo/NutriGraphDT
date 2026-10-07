"""Generador de aristas sintéticas para NutriGraphDT (DS-03).

Implementa el contrato de arista y el catálogo de relaciones permitidas definidos en
`docs/synthetic-dataset/synthetic-dataset-spec.md` (secciones "Contrato de arista" y "Relaciones
permitidas").

Todas las aristas producidas aquí son sintéticas: existen para probar la estructura del grafo
heterogéneo y se etiquetan con `evidence_status = "synthetic"`. No representan evidencia
biológica, relaciones causales ni actividad metabólica demostrada.

Convenciones del generador (no son decisiones científicas):

- Cada par candidato `(origen, destino)` de una relación permitida se conecta con una
  probabilidad configurable por relación. Una relación ausente de la configuración no se
  genera. No se añaden aristas para forzar conectividad: un nodo aislado es preferible a una
  relación no sustentada.
- Los atributos obligatorios de arista se copian desde el nodo correspondiente cuando ese nodo
  ya contiene la magnitud (por ejemplo, `sample_matrix` del metabolito o `timepoint` del
  fenotipo). Así no se introduce una segunda magnitud independiente que pueda contradecir al
  nodo. Si el atributo de origen está ausente, la arista no se genera.
- Las aristas solo conectan nodos del mismo `graph_id`; una instancia nunca se mezcla con otra.
- Cada combinación `(semilla, graph_id, relación)` usa su propio generador aleatorio. Así, las
  aristas de una instancia no cambian por generarla junto con otras, y activar, desactivar o
  modificar una relación no altera las demás (importante para comparar escenarios basal e
  intervención).
- `proportion` de `diet -provides-> substrate` copia la cantidad del sustrato, por lo que es
  idéntica para todas las dietas de una misma instancia. Es coherente con una dieta por
  instancia; con varias dietas, esa magnitud no las distingue.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal

from nutrigraphdt.data.synthetic.nodes import Node, NodeType

EdgeType = tuple[str, str, str]
"""Tupla `(source_type, relation_type, target_type)`, igual que en `HeteroData`."""

AttributeKind = Literal["number", "str"]

EVIDENCE_STATUSES: frozenset[str] = frozenset(
    {"synthetic", "observed", "annotated", "inferred", "hypothetical"}
)
"""Valores admitidos para `evidence_status` según el contrato de arista."""

SYNTHETIC_EVIDENCE_STATUS = "synthetic"

_DIET = NodeType.DIET.value
_ADDITIVE = NodeType.ADDITIVE.value
_SUBSTRATE = NodeType.SUBSTRATE.value
_TAXON = NodeType.TAXON.value
_FUNCTION = NodeType.FUNCTION.value
_METABOLITE = NodeType.METABOLITE.value
_HOST = NodeType.HOST.value
_PHENOTYPE = NodeType.PHENOTYPE.value

DIET_PROVIDES_SUBSTRATE: EdgeType = (_DIET, "provides", _SUBSTRATE)
SUBSTRATE_AVAILABLE_TO_TAXON: EdgeType = (_SUBSTRATE, "available_to", _TAXON)
TAXON_HAS_CAPACITY_FUNCTION: EdgeType = (_TAXON, "has_capacity", _FUNCTION)
FUNCTION_PRODUCES_METABOLITE: EdgeType = (_FUNCTION, "produces", _METABOLITE)
METABOLITE_MEASURED_IN_HOST: EdgeType = (_METABOLITE, "measured_in", _HOST)
ADDITIVE_MODULATES_TAXON: EdgeType = (_ADDITIVE, "modulates", _TAXON)
ADDITIVE_MODULATES_FUNCTION: EdgeType = (_ADDITIVE, "modulates", _FUNCTION)
METABOLITE_ASSOCIATED_WITH_PHENOTYPE: EdgeType = (_METABOLITE, "associated_with", _PHENOTYPE)
HOST_EXHIBITS_PHENOTYPE: EdgeType = (_HOST, "exhibits", _PHENOTYPE)
TAXON_INTERACTS_WITH_TAXON: EdgeType = (_TAXON, "interacts_with", _TAXON)
FUNCTION_CROSS_FEEDS_FUNCTION: EdgeType = (_FUNCTION, "cross_feeds", _FUNCTION)


@dataclass(frozen=True)
class RelationSpec:
    """Entrada del catálogo de relaciones permitidas.

    `required_attributes` enumera los atributos obligatorios además de los campos comunes del
    contrato de arista. `structural_status` reproduce la columna "Estado estructural" de la
    especificación y describe la semántica prevista; no convierte una arista en evidencia.
    """

    edge_type: EdgeType
    semantics: str
    required_attributes: Mapping[str, AttributeKind]
    structural_status: str


def _relation(
    edge_type: EdgeType,
    semantics: str,
    structural_status: str,
    required_attributes: Mapping[str, AttributeKind] | None = None,
) -> RelationSpec:
    return RelationSpec(
        edge_type=edge_type,
        semantics=semantics,
        required_attributes=MappingProxyType(dict(required_attributes or {})),
        structural_status=structural_status,
    )


ALLOWED_RELATIONS: Mapping[EdgeType, RelationSpec] = MappingProxyType(
    {
        spec.edge_type: spec
        for spec in (
            _relation(
                DIET_PROVIDES_SUBSTRATE,
                "Composición documentada de dieta.",
                "approved_structure",
                {"proportion": "number", "unit": "str"},
            ),
            _relation(
                SUBSTRATE_AVAILABLE_TO_TAXON,
                "Recurso potencialmente disponible.",
                "provisional",
            ),
            _relation(
                TAXON_HAS_CAPACITY_FUNCTION,
                "Capacidad anotada, no actividad demostrada.",
                "provisional",
                {"annotation_source": "str"},
            ),
            _relation(
                FUNCTION_PRODUCES_METABOLITE,
                "Transformación candidata.",
                "provisional",
            ),
            _relation(
                METABOLITE_MEASURED_IN_HOST,
                "Medición o exposición contextual.",
                "provisional",
                {"sample_matrix": "str"},
            ),
            _relation(
                ADDITIVE_MODULATES_TAXON,
                "Hipótesis de modulación.",
                "hypothetical",
            ),
            _relation(
                ADDITIVE_MODULATES_FUNCTION,
                "Hipótesis de modulación.",
                "hypothetical",
            ),
            _relation(
                METABOLITE_ASSOCIATED_WITH_PHENOTYPE,
                "Asociación, no efecto causal.",
                "hypothetical",
            ),
            _relation(
                HOST_EXHIBITS_PHENOTYPE,
                "Correspondencia observacional.",
                "provisional",
                {"timepoint": "str"},
            ),
            _relation(
                TAXON_INTERACTS_WITH_TAXON,
                "Interacción ecológica candidata.",
                "hypothetical",
                {"interaction_type": "str"},
            ),
            _relation(
                FUNCTION_CROSS_FEEDS_FUNCTION,
                "Sustrato cruzado candidato entre funciones.",
                "hypothetical",
                {"substrate_id": "str"},
            ),
        )
    }
)
"""Catálogo cerrado de las once relaciones permitidas por `synthetic-v1`.

No incluye aristas `taxon -> metabolite` ni relaciones inversas implícitas: ambas requieren
una actualización versionada de la especificación.
"""

_DEFAULT_RELATION_PROBABILITIES: Mapping[EdgeType, float] = MappingProxyType(
    {
        DIET_PROVIDES_SUBSTRATE: 0.75,
        SUBSTRATE_AVAILABLE_TO_TAXON: 0.3,
        TAXON_HAS_CAPACITY_FUNCTION: 0.3,
        FUNCTION_PRODUCES_METABOLITE: 0.3,
        METABOLITE_MEASURED_IN_HOST: 1.0,
        ADDITIVE_MODULATES_TAXON: 0.2,
        ADDITIVE_MODULATES_FUNCTION: 0.2,
        METABOLITE_ASSOCIATED_WITH_PHENOTYPE: 0.3,
        HOST_EXHIBITS_PHENOTYPE: 1.0,
        TAXON_INTERACTS_WITH_TAXON: 0.1,
        FUNCTION_CROSS_FEEDS_FUNCTION: 0.1,
    }
)
"""Densidades por defecto. Son convenciones computacionales para obtener fixtures con
estructura variada; no estiman la frecuencia real de ninguna relación biológica."""

_DEFAULT_INTERACTION_TYPES: tuple[str, ...] = ("competition", "cooperation", "inhibition")
"""Vocabulario provisional de `interaction_type`. Debe declararse en `metadata.json` al
exportar el dataset (DS-05) y confirmarse con Investigación antes de usar datos reales."""


def _default_relation_probabilities() -> dict[EdgeType, float]:
    return dict(_DEFAULT_RELATION_PROBABILITIES)


@dataclass(frozen=True)
class SyntheticEdgeConfig:
    """Configuración del generador de aristas sintéticas.

    `relation_probabilities` reemplaza por completo a los valores por defecto: una relación
    que no aparece en el diccionario tiene probabilidad cero y no se genera.
    """

    random_seed: int = 42
    evidence_id: str = "SYNTHETIC_V1"
    evidence_method: str = "synthetic_generator"
    relation_probabilities: Mapping[EdgeType, float] = field(
        default_factory=_default_relation_probabilities
    )
    interaction_types: tuple[str, ...] = _DEFAULT_INTERACTION_TYPES
    non_modulating_control_labels: tuple[str, ...] = ("control_basal",)
    """Aditivos con estas etiquetas de control no reciben aristas `modulates`."""

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raise ValueError("evidence_id no puede estar vacío.")
        if not self.evidence_method:
            raise ValueError("evidence_method no puede estar vacío.")
        for edge_type, probability in self.relation_probabilities.items():
            if edge_type not in ALLOWED_RELATIONS:
                raise ValueError(f"Relación no permitida por la especificación: {edge_type}")
            if (
                isinstance(probability, bool)
                or not isinstance(probability, int | float)
                or not math.isfinite(probability)
                or not 0.0 <= probability <= 1.0
            ):
                raise ValueError(
                    f"La probabilidad de {edge_type} debe ser un número en [0, 1]; "
                    f"se recibió {probability!r}."
                )
        if not self.interaction_types or not all(
            isinstance(value, str) and value for value in self.interaction_types
        ):
            raise ValueError("interaction_types debe contener al menos una cadena no vacía.")

    def probability_for(self, edge_type: EdgeType) -> float:
        """Probabilidad configurada para una relación; cero si no está configurada."""
        return float(self.relation_probabilities.get(edge_type, 0.0))


_COMMON_STRING_FIELDS: tuple[str, ...] = (
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


@dataclass(frozen=True)
class Edge:
    """Registro de `edges.jsonl` según el contrato de arista."""

    graph_id: str
    source_type: str
    source_id: str
    relation_type: str
    target_type: str
    target_id: str
    evidence_id: str
    evidence_status: str
    evidence_method: str
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def edge_type(self) -> EdgeType:
        """Tupla `(source_type, relation_type, target_type)` de la arista."""
        return (self.source_type, self.relation_type, self.target_type)

    def to_dict(self) -> dict[str, Any]:
        """Serializa la arista a un diccionario compatible con JSON/JSONL."""
        return {
            "graph_id": self.graph_id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "relation_type": self.relation_type,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "evidence_id": self.evidence_id,
            "evidence_status": self.evidence_status,
            "evidence_method": self.evidence_method,
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Edge:
        """Construye una arista desde un diccionario.

        Todos los campos son obligatorios. Los campos de texto deben ser cadenas no vacías y
        `attributes` un objeto: un `null` u otro tipo se rechaza en lugar de convertirse en
        texto (por ejemplo, `None` no se transforma en `"None"`).
        """
        values: dict[str, str] = {}
        for name in _COMMON_STRING_FIELDS:
            value = data[name]
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"El campo '{name}' debe ser una cadena no vacía; se recibió {value!r}."
                )
            values[name] = value
        attributes = data["attributes"]
        if not isinstance(attributes, dict):
            raise ValueError(
                f"El campo 'attributes' debe ser un objeto; se recibió {attributes!r}."
            )
        return cls(**values, attributes=dict(attributes))


def edge_sort_key(edge: Edge) -> tuple[str, str, str, str, str, str]:
    """Orden determinista de exportación definido en la especificación."""
    return (
        edge.graph_id,
        edge.source_type,
        edge.relation_type,
        edge.target_type,
        edge.source_id,
        edge.target_id,
    )


_NodeIndex = dict[str, list[Node]]


def _index_nodes(nodes: Iterable[Node]) -> dict[str, _NodeIndex]:
    """Agrupa nodos por `graph_id` y tipo, ordenados por `node_id`.

    Falla si hay tipos desconocidos o IDs repetidos dentro de `(graph_id, node_type)`, porque
    una arista no podría resolver a qué nodo apunta.
    """
    known_types = {node_type.value for node_type in NodeType}
    by_graph: dict[str, _NodeIndex] = {}
    seen: set[tuple[str, str, str]] = set()
    for node in nodes:
        if node.node_type not in known_types:
            raise ValueError(f"Tipo de nodo desconocido: {node.node_type!r} ({node.node_id}).")
        key = (node.graph_id, node.node_type, node.node_id)
        if key in seen:
            raise ValueError(
                f"node_id repetido en {node.graph_id}/{node.node_type}: {node.node_id}"
            )
        seen.add(key)
        by_graph.setdefault(node.graph_id, {}).setdefault(node.node_type, []).append(node)
    for index in by_graph.values():
        for node_list in index.values():
            node_list.sort(key=lambda node: node.node_id)
    return by_graph


def _is_missing(node: Node, key: str) -> bool:
    return node.missing_mask.get(key, False) or node.attributes.get(key) is None


def _number_attribute(node: Node, key: str) -> float | None:
    if _is_missing(node, key):
        return None
    value = node.attributes[key]
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        return None
    return float(value)


def _str_attribute(node: Node, key: str) -> str | None:
    if _is_missing(node, key):
        return None
    value = node.attributes[key]
    return value if isinstance(value, str) and value else None


class SyntheticEdgeGenerator:
    """Generador determinista de aristas sintéticas entre nodos existentes."""

    def __init__(self, config: SyntheticEdgeConfig | None = None) -> None:
        """Inicializa el generador con la configuración suministrada."""
        self.config = config or SyntheticEdgeConfig()

    def generate_edges(self, nodes: Iterable[Node]) -> list[Edge]:
        """Genera las aristas de todas las instancias presentes en `nodes`.

        El resultado depende solo de los nodos y de la configuración: llamar dos veces con la
        misma entrada, o con los mismos nodos en otro orden, produce las mismas aristas. Cada
        instancia y cada relación se generan de forma independiente (ver `_relation_rng`).
        """
        edges: list[Edge] = []
        for graph_id, index in sorted(_index_nodes(nodes).items()):
            for edge_type in ALLOWED_RELATIONS:
                rng = self._relation_rng(graph_id, edge_type)
                edges.extend(self._generate_relation(graph_id, edge_type, index, rng))
        edges.sort(key=edge_sort_key)
        return edges

    def _relation_rng(self, graph_id: str, edge_type: EdgeType) -> random.Random:
        """Generador aleatorio propio de `(semilla, graph_id, relación)`.

        Sembrar con una cadena es determinista entre ejecuciones y no depende de
        `PYTHONHASHSEED` (Python la convierte a entero mediante SHA-512).
        """
        source_type, relation_type, target_type = edge_type
        return random.Random(
            f"{self.config.random_seed}|{graph_id}|{source_type}|{relation_type}|{target_type}"
        )

    def _generate_relation(
        self,
        graph_id: str,
        edge_type: EdgeType,
        index: _NodeIndex,
        rng: random.Random,
    ) -> list[Edge]:
        probability = self.config.probability_for(edge_type)
        if probability == 0.0:
            return []
        source_type, relation_type, target_type = edge_type
        sources = index.get(source_type, [])
        targets = index.get(target_type, [])
        if relation_type == "modulates":
            sources = [
                node
                for node in sources
                if node.attributes.get("control_label")
                not in self.config.non_modulating_control_labels
            ]

        edges: list[Edge] = []
        for source in sources:
            for target in targets:
                if source_type == target_type and source.node_id == target.node_id:
                    continue
                if rng.random() >= probability:
                    continue
                attributes = self._edge_attributes(edge_type, source, target, index, rng)
                if attributes is None:
                    continue
                edges.append(
                    Edge(
                        graph_id=graph_id,
                        source_type=source_type,
                        source_id=source.node_id,
                        relation_type=relation_type,
                        target_type=target_type,
                        target_id=target.node_id,
                        evidence_id=self.config.evidence_id,
                        evidence_status=SYNTHETIC_EVIDENCE_STATUS,
                        evidence_method=self.config.evidence_method,
                        attributes=attributes,
                    )
                )
        return edges

    def _edge_attributes(
        self,
        edge_type: EdgeType,
        source: Node,
        target: Node,
        index: _NodeIndex,
        rng: random.Random,
    ) -> dict[str, Any] | None:
        """Atributos obligatorios de la relación, o `None` si no pueden completarse."""
        if edge_type == DIET_PROVIDES_SUBSTRATE:
            # La proporción reutiliza la cantidad del sustrato para no crear una segunda
            # magnitud independiente que contradiga al nodo.
            quantity = _number_attribute(target, "quantity")
            unit = _str_attribute(target, "unit")
            if quantity is None or unit is None:
                return None
            return {"proportion": quantity, "unit": unit}
        if edge_type == TAXON_HAS_CAPACITY_FUNCTION:
            annotation_source = _str_attribute(target, "annotation_source")
            return None if annotation_source is None else {"annotation_source": annotation_source}
        if edge_type == METABOLITE_MEASURED_IN_HOST:
            sample_matrix = _str_attribute(source, "sample_matrix")
            return None if sample_matrix is None else {"sample_matrix": sample_matrix}
        if edge_type == HOST_EXHIBITS_PHENOTYPE:
            timepoint = _str_attribute(target, "timepoint")
            return None if timepoint is None else {"timepoint": timepoint}
        if edge_type == TAXON_INTERACTS_WITH_TAXON:
            return {"interaction_type": rng.choice(self.config.interaction_types)}
        if edge_type == FUNCTION_CROSS_FEEDS_FUNCTION:
            substrates = index.get(_SUBSTRATE, [])
            if not substrates:
                return None
            return {"substrate_id": rng.choice(substrates).node_id}
        return {}


def generate_synthetic_edges(
    nodes: Iterable[Node], config: SyntheticEdgeConfig | None = None
) -> list[Edge]:
    """Función utilitaria de alto nivel para generar aristas sintéticas."""
    return SyntheticEdgeGenerator(config).generate_edges(nodes)


class EdgeValidationError(ValueError):
    """Una o más aristas no cumplen el contrato de arista."""


def _matches_kind(value: Any, kind: AttributeKind) -> bool:
    if kind == "str":
        return isinstance(value, str) and bool(value)
    return not isinstance(value, bool) and isinstance(value, int | float) and math.isfinite(value)


def find_edge_errors(
    nodes: Iterable[Node], edges: Iterable[Edge], *, require_synthetic: bool = True
) -> list[str]:
    """Devuelve los incumplimientos del contrato de arista; lista vacía si todo es válido.

    Comprueba que cada arista use una tupla permitida, que sus extremos existan con el tipo
    declarado dentro del mismo `graph_id`, que los campos comunes estén completos y que los
    atributos obligatorios de su relación estén presentes con el tipo correcto.

    Con `require_synthetic=True` (por defecto) aplica además la regla 6 de la especificación:
    mientras Investigación no apruebe criterios de evidencia, toda arista debe declarar
    `evidence_status = "synthetic"`. Usar `False` solo cuando exista un criterio aprobado.
    """
    known = {(node.graph_id, node.node_type, node.node_id) for node in nodes}
    errors: list[str] = []
    for position, edge in enumerate(edges):
        label = (
            f"arista {position} [{edge.graph_id}] "
            f"{edge.source_id} -{edge.relation_type}-> {edge.target_id}"
        )
        for name in _COMMON_STRING_FIELDS:
            value = getattr(edge, name)
            if not isinstance(value, str) or not value:
                errors.append(f"{label}: el campo obligatorio '{name}' está vacío o no es str.")
        if edge.evidence_status not in EVIDENCE_STATUSES:
            errors.append(f"{label}: evidence_status no válido: {edge.evidence_status!r}.")
        elif require_synthetic and edge.evidence_status != SYNTHETIC_EVIDENCE_STATUS:
            errors.append(
                f"{label}: evidence_status debe ser 'synthetic' mientras no exista un criterio "
                f"de evidencia aprobado; se recibió {edge.evidence_status!r}."
            )

        spec = ALLOWED_RELATIONS.get(edge.edge_type)
        if spec is None:
            errors.append(f"{label}: la tupla {edge.edge_type} no es una relación permitida.")
            continue
        if (edge.graph_id, edge.source_type, edge.source_id) not in known:
            errors.append(
                f"{label}: el origen no existe como nodo '{edge.source_type}' en la instancia."
            )
        if (edge.graph_id, edge.target_type, edge.target_id) not in known:
            errors.append(
                f"{label}: el destino no existe como nodo '{edge.target_type}' en la instancia."
            )

        if not isinstance(edge.attributes, dict):
            errors.append(f"{label}: 'attributes' debe ser un objeto.")
            continue
        for attribute, kind in spec.required_attributes.items():
            if attribute not in edge.attributes:
                errors.append(f"{label}: falta el atributo obligatorio '{attribute}'.")
            elif not _matches_kind(edge.attributes[attribute], kind):
                errors.append(f"{label}: el atributo '{attribute}' debe ser de tipo {kind}.")

        if edge.edge_type == FUNCTION_CROSS_FEEDS_FUNCTION:
            substrate_id = edge.attributes.get("substrate_id")
            if (
                isinstance(substrate_id, str)
                and (edge.graph_id, _SUBSTRATE, substrate_id) not in known
            ):
                errors.append(
                    f"{label}: substrate_id {substrate_id!r} no es un nodo 'substrate' "
                    "de la misma instancia."
                )
    return errors


def validate_edges(
    nodes: Iterable[Node], edges: Iterable[Edge], *, require_synthetic: bool = True
) -> None:
    """Lanza `EdgeValidationError` con todos los incumplimientos encontrados."""
    errors = find_edge_errors(nodes, edges, require_synthetic=require_synthetic)
    if errors:
        raise EdgeValidationError("\n".join(errors))
