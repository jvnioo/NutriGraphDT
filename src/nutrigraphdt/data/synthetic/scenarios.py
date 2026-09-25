"""Escenarios basal e intervenido para NutriGraphDT (DS-05).

Este modulo define dos instancias identificables del grafo sintetico:

* **Basal** (``SCENARIO_BASAL_GRAPH_ID``): genera nodos y aristas con la
  configuracion estandar por defecto.
* **Intervenido** (``SCENARIO_INTERVENED_GRAPH_ID``): modifica *unicamente* el
  valor de ``crude_protein`` (proteina bruta) en la composicion de la dieta,
  manteniendo constantes todas las demas variables.

La intervencion es *artificial*: su unica finalidad es ejercitar los contratos
de entrada y verificar que la comparacion entre escenarios detecta la variable
modificada.  Los valores no representan rangos biologicos ni resultados
experimentales reales.

Intervencion documentada
------------------------
* **Variable modificada:** ``crude_protein`` (componente de la composicion del
  nodo ``diet``).
* **Valor basal:** ``215.0 g/kg`` (extraido del catalogo ``_DIET_CATALOG``).
* **Valor intervenido:** ``270.0 g/kg`` (incremento sintetico del 25 %).
* **Razon:** valor elegido unicamente para producir un cambio identificable y
  verificable en los tests; no refleja ninguna fuente bibliografica.
* **Variables constantes:** todos los demas atributos de la composicion de la
  dieta, los ingredientes, el ``source_version``, y la totalidad de los nodos
  ``additive``, ``substrate``, ``taxon``, ``function``, ``metabolite``,
  ``host`` y ``phenotype``.

Los efectos producidos por esta intervencion son *sinteticos* y no deben
presentarse como resultados biologicos.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nutrigraphdt.data.synthetic.edges import (
    Edge,
    SyntheticEdgeConfig,
    SyntheticEdgeGenerator,
    find_edge_errors,
    validate_edges,
)
from nutrigraphdt.data.synthetic.nodes import (
    Node,
    NodeCountConfig,
    NodeType,
    SyntheticNodeConfig,
    generate_synthetic_nodes,
)

# ---------------------------------------------------------------------------
# Identificadores de escenario
# ---------------------------------------------------------------------------

SCENARIO_BASAL_GRAPH_ID: str = "synthetic:scenario:basal:0001"
"""``graph_id`` canonico del escenario basal."""

SCENARIO_INTERVENED_GRAPH_ID: str = "synthetic:scenario:intervened:0001"
"""``graph_id`` canonico del escenario intervenido."""

# ---------------------------------------------------------------------------
# Documentacion de la intervencion
# ---------------------------------------------------------------------------

INTERVENTION_VARIABLE: str = "crude_protein"
"""Nombre del componente nutricional modificado (clave ``component_id``)."""

INTERVENTION_COMPONENT_UNIT: str = "g/kg"
"""Unidad de la variable intervenida (convencion sintetica)."""

INTERVENTION_BASAL_VALUE: float = 215.0
"""Valor de ``crude_protein`` en el escenario basal (convencion sintetica)."""

INTERVENTION_INTERVENED_VALUE: float = 270.0
"""Valor de ``crude_protein`` en el escenario intervenido (convencion sintetica, +25 %).

.. warning::
   Este valor es una convencion computacional elegida para producir un cambio
   detectable. No representa un resultado biologico real ni una referencia
   bibliografica verificada.
"""

# ---------------------------------------------------------------------------
# Configuracion compartida entre escenarios
# ---------------------------------------------------------------------------

_SHARED_COUNTS = NodeCountConfig(
    diet=1,
    additive=1,
    substrate=4,
    taxon=10,
    function=8,
    metabolite=5,
    host=1,
    phenotype=2,
)
"""Conteo de nodos compartido por ambos escenarios."""

_SHARED_RANDOM_SEED: int = 42
"""Semilla aleatoria compartida para garantizar determinismo entre ejecuciones."""

_SHARED_SOURCE_ID: str = "SYNTHETIC_V1"
_SHARED_SPECIES: str = "chicken"
_SHARED_GUT_SEGMENT: str = "cecum"
_SHARED_COHORT_ID: str = "cohort_01"
_SHARED_TIMEPOINT_DAYS: int = 42


def _base_node_config(graph_id: str) -> SyntheticNodeConfig:
    """Devuelve la configuracion de nodos comun con el ``graph_id`` indicado."""
    return SyntheticNodeConfig(
        graph_id=graph_id,
        source_id=_SHARED_SOURCE_ID,
        species=_SHARED_SPECIES,
        gut_segment=_SHARED_GUT_SEGMENT,
        cohort_id=_SHARED_COHORT_ID,
        counts=_SHARED_COUNTS,
        random_seed=_SHARED_RANDOM_SEED,
        timepoint_days=_SHARED_TIMEPOINT_DAYS,
    )


_SHARED_EDGE_CONFIG = SyntheticEdgeConfig(random_seed=_SHARED_RANDOM_SEED)
"""Configuracion de aristas compartida."""


# ---------------------------------------------------------------------------
# Construccion de nodos por escenario
# ---------------------------------------------------------------------------


def _apply_diet_intervention(nodes: list[Node], new_value: float) -> list[Node]:
    """Sustituye el valor de ``crude_protein`` en la composicion de los nodos de dieta.

    Los demas componentes de la composicion y el resto de atributos del nodo se
    dejan intactos.

    Parameters
    ----------
    nodes:
        Lista de nodos tal como los genero :class:`SyntheticNodeGenerator`.
    new_value:
        Nuevo valor numerico para ``crude_protein`` (misma unidad que la
        configuracion original: ``g/kg``).

    Returns
    -------
    list[Node]
        Nueva lista de nodos con los nodos de dieta actualizados.
    """
    result: list[Node] = []
    for node in nodes:
        if node.node_type != NodeType.DIET.value:
            result.append(node)
            continue

        old_composition: list[dict[str, Any]] = list(node.attributes.get("composition", []))
        new_composition: list[dict[str, Any]] = []
        for item in old_composition:
            if item.get("component_id") == INTERVENTION_VARIABLE:
                new_composition.append(
                    {
                        "component_id": INTERVENTION_VARIABLE,
                        "value": new_value,
                        "unit": INTERVENTION_COMPONENT_UNIT,
                    }
                )
            else:
                new_composition.append(dict(item))

        new_attributes: dict[str, Any] = {**node.attributes, "composition": new_composition}

        result.append(
            Node(
                graph_id=node.graph_id,
                node_id=node.node_id,
                node_type=node.node_type,
                source_id=node.source_id,
                attributes=new_attributes,
                missing_mask=dict(node.missing_mask),
            )
        )
    return result


# ---------------------------------------------------------------------------
# Dataclass de resultado del escenario
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioInstance:
    """Par ``(nodos, aristas)`` de una instancia de escenario validada.

    Attributes
    ----------
    graph_id:
        Identificador unico del escenario.
    nodes:
        Lista de nodos que pasan el contrato de entrada.
    edges:
        Lista de aristas que pasan el contrato de entrada.
    intervention_label:
        Etiqueta legible que describe la intervencion aplicada;
        ``"none"`` para el escenario basal.
    intervention_variable:
        Nombre de la variable modificada, o ``None`` si no hay intervencion.
    intervention_value:
        Valor de la variable modificada, o ``None`` si no hay intervencion.

    Notes
    -----
    Los efectos de la intervencion son *sinteticos*.  No representan resultados
    biologicos ni causalidad demostrada.
    """

    graph_id: str
    nodes: list[Node]
    edges: list[Edge]
    intervention_label: str
    intervention_variable: str | None
    intervention_value: float | None


# ---------------------------------------------------------------------------
# Funciones de construccion publica
# ---------------------------------------------------------------------------


def build_basal_scenario() -> ScenarioInstance:
    """Construye y valida el escenario basal.

    Returns
    -------
    ScenarioInstance
        Instancia basal validada.

    Raises
    ------
    EdgeValidationError
        Si alguna arista incumple el contrato de arista.
    """
    config = _base_node_config(SCENARIO_BASAL_GRAPH_ID)
    nodes = generate_synthetic_nodes(config)
    edges = SyntheticEdgeGenerator(_SHARED_EDGE_CONFIG).generate_edges(nodes)
    validate_edges(nodes, edges)
    return ScenarioInstance(
        graph_id=SCENARIO_BASAL_GRAPH_ID,
        nodes=nodes,
        edges=edges,
        intervention_label="none",
        intervention_variable=None,
        intervention_value=None,
    )


def build_intervened_scenario() -> ScenarioInstance:
    """Construye y valida el escenario intervenido.

    Modifica unicamente el valor de ``crude_protein`` en la composicion de la
    dieta.  Todas las demas variables permanecen constantes respecto al basal.

    La intervencion es artificial y no representa evidencia biologica.

    Returns
    -------
    ScenarioInstance
        Instancia intervenida validada.

    Raises
    ------
    EdgeValidationError
        Si alguna arista incumple el contrato de arista.
    """
    config = _base_node_config(SCENARIO_INTERVENED_GRAPH_ID)
    raw_nodes = generate_synthetic_nodes(config)
    nodes = _apply_diet_intervention(raw_nodes, INTERVENTION_INTERVENED_VALUE)
    edges = SyntheticEdgeGenerator(_SHARED_EDGE_CONFIG).generate_edges(nodes)
    validate_edges(nodes, edges)
    return ScenarioInstance(
        graph_id=SCENARIO_INTERVENED_GRAPH_ID,
        nodes=nodes,
        edges=edges,
        intervention_label=(
            f"{INTERVENTION_VARIABLE}: "
            f"{INTERVENTION_BASAL_VALUE} -> {INTERVENTION_INTERVENED_VALUE} "
            f"{INTERVENTION_COMPONENT_UNIT} [synthetic]"
        ),
        intervention_variable=INTERVENTION_VARIABLE,
        intervention_value=INTERVENTION_INTERVENED_VALUE,
    )


# ---------------------------------------------------------------------------
# Validacion de contratos de entrada
# ---------------------------------------------------------------------------


def validate_scenario_node_contract(instance: ScenarioInstance) -> list[str]:
    """Valida el contrato de nodo de una instancia de escenario.

    Comprueba los campos obligatorios del envoltorio de nodo segun DS-01.

    Returns
    -------
    list[str]
        Lista de incumplimientos; vacia si todo es valido.
    """
    known_types = {nt.value for nt in NodeType}
    errors: list[str] = []
    seen_ids: set[tuple[str, str]] = set()

    for i, node in enumerate(instance.nodes):
        label = f"nodo {i} [{node.node_id}]"

        if node.graph_id != instance.graph_id:
            errors.append(f"{label}: graph_id {node.graph_id!r} != {instance.graph_id!r}.")

        for field_name in ("graph_id", "node_id", "node_type", "source_id"):
            value = getattr(node, field_name)
            if not isinstance(value, str) or not value:
                errors.append(
                    f"{label}: el campo obligatorio '{field_name}' esta vacio o no es str."
                )

        if node.node_type not in known_types:
            errors.append(f"{label}: node_type desconocido {node.node_type!r}.")

        key = (node.node_type, node.node_id)
        if key in seen_ids:
            errors.append(f"{label}: node_id duplicado dentro del tipo {node.node_type!r}.")
        seen_ids.add(key)

        if not isinstance(node.attributes, dict):
            errors.append(f"{label}: 'attributes' debe ser un objeto.")

        if not isinstance(node.missing_mask, dict):
            errors.append(f"{label}: 'missing_mask' debe ser un objeto.")

    return errors


def validate_scenario_contracts(instance: ScenarioInstance) -> list[str]:
    """Valida tanto el contrato de nodo como el contrato de arista de la instancia.

    Returns
    -------
    list[str]
        Lista acumulada de incumplimientos; vacia si todo es valido.
    """
    errors = validate_scenario_node_contract(instance)
    errors.extend(find_edge_errors(instance.nodes, instance.edges))
    return errors


__all__ = [
    "INTERVENTION_BASAL_VALUE",
    "INTERVENTION_COMPONENT_UNIT",
    "INTERVENTION_INTERVENED_VALUE",
    "INTERVENTION_VARIABLE",
    "SCENARIO_BASAL_GRAPH_ID",
    "SCENARIO_INTERVENED_GRAPH_ID",
    "ScenarioInstance",
    "build_basal_scenario",
    "build_intervened_scenario",
    "validate_scenario_contracts",
    "validate_scenario_node_contract",
]
