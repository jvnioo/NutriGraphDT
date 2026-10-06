"""Estadísticas descriptivas y subgrafo de muestra de un `HeteroData` (A35-4, #31).

Herramienta de inspección rápida para cualquier `HeteroData` del proyecto. Solo usa la
estructura común de PyG (tipos de nodo, `num_nodes` y `edge_index` por relación), así que no
depende de la codificación de features ni del origen de los datos. Requiere el extra `graph`.

Convenciones:

- **Grado no dirigido.** Cada arista almacenada suma 1 al grado de su origen y 1 al de su
  destino, sin importar la relación. Si un grafo guarda también relaciones inversas, cada par
  cuenta dos veces: las estadísticas describen lo que se almacena, no la semántica biológica.
- **Componentes conexas débiles.** Se calculan sobre la unión de todas las relaciones tratadas
  como no dirigidas. Un nodo aislado es una componente de tamaño 1.
- **Subgrafo de muestra.** Se elige de forma determinista (sin azar): por defecto, el nodo de
  mayor grado y sus vecinos a `hops` saltos, hasta `max_nodes` nodos. Se exporta como un
  diagrama Mermaid, que GitHub y los editores habituales renderizan sin dependencias extra.

Las estadísticas son estructurales: no afirman nada sobre la validez biológica del grafo.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Final

from torch_geometric.data import HeteroData

NodeRef = tuple[str, int]
"""Nodo identificado por `(tipo, fila)`."""

EdgeType = tuple[str, str, str]

MERMAID_PALETTE: Final = (
    ("#cfe2f3", "#3d85c6"),
    ("#d9ead3", "#6aa84f"),
    ("#fce5cd", "#e69138"),
    ("#ead1dc", "#a64d79"),
    ("#fff2cc", "#bf9000"),
    ("#d9d2e9", "#674ea7"),
    ("#f4cccc", "#cc0000"),
    ("#d0e0e3", "#45818e"),
)
"""Pares `(relleno, borde)` asignados a los tipos de nodo en orden; se repiten si hay más."""


@dataclass(frozen=True)
class GraphStats:
    """Resumen estructural de un `HeteroData`."""

    graph_id: str | None
    nodes: dict[str, int]
    edges: dict[EdgeType, int]
    mean_degree: float
    mean_degree_by_type: dict[str, float]
    num_components: int
    largest_component: int
    isolated_nodes: int

    @property
    def num_nodes(self) -> int:
        return sum(self.nodes.values())

    @property
    def num_edges(self) -> int:
        return sum(self.edges.values())

    def to_dict(self) -> dict[str, Any]:
        """Representación JSON; cada relación usa la clave `origen|relación|destino`."""
        return {
            "graph_id": self.graph_id,
            "num_nodes": self.num_nodes,
            "num_edges": self.num_edges,
            "nodes": dict(self.nodes),
            "edges": {"|".join(edge_type): count for edge_type, count in self.edges.items()},
            "mean_degree": self.mean_degree,
            "mean_degree_by_type": dict(self.mean_degree_by_type),
            "num_components": self.num_components,
            "largest_component": self.largest_component,
            "isolated_nodes": self.isolated_nodes,
        }


def _node_counts(data: HeteroData) -> dict[str, int]:
    return {str(node_type): int(data[node_type].num_nodes or 0) for node_type in data.node_types}


def _edge_pairs(data: HeteroData, counts: dict[str, int]) -> dict[EdgeType, list[tuple[int, int]]]:
    """Pares `(origen, destino)` de cada relación, verificando que los índices existan."""
    pairs: dict[EdgeType, list[tuple[int, int]]] = {}
    for edge_type in data.edge_types:
        source_type, relation, target_type = (str(part) for part in edge_type)
        key = (source_type, relation, target_type)
        edge_index = getattr(data[edge_type], "edge_index", None)
        if edge_index is None:
            raise ValueError(f"La relación {key} no tiene edge_index.")
        if edge_index.dim() != 2 or edge_index.size(0) != 2:
            raise ValueError(f"edge_index de {key} debe tener forma [2, E].")
        columns: list[list[int]] = edge_index.tolist()
        for kind, indices in ((source_type, columns[0]), (target_type, columns[1])):
            size = counts.get(kind)
            if size is None:
                raise ValueError(f"La relación {key} usa el tipo de nodo inexistente {kind!r}.")
            if any(index < 0 or index >= size for index in indices):
                raise ValueError(f"edge_index de {key} apunta fuera de los {size} nodos de {kind}.")
        pairs[key] = list(zip(columns[0], columns[1], strict=True))
    return pairs


def _adjacency(
    counts: dict[str, int], pairs: dict[EdgeType, list[tuple[int, int]]]
) -> dict[NodeRef, list[NodeRef]]:
    """Lista de adyacencia no dirigida; una entrada por arista almacenada."""
    adjacency: dict[NodeRef, list[NodeRef]] = {
        (node_type, row): [] for node_type, size in counts.items() for row in range(size)
    }
    for edge_type, edge_pairs in pairs.items():
        source_type, _, target_type = edge_type
        for source, target in edge_pairs:
            adjacency[(source_type, source)].append((target_type, target))
            adjacency[(target_type, target)].append((source_type, source))
    return adjacency


def _component_sizes(adjacency: dict[NodeRef, list[NodeRef]]) -> list[int]:
    seen: set[NodeRef] = set()
    sizes: list[int] = []
    for start in adjacency:
        if start in seen:
            continue
        seen.add(start)
        stack = [start]
        size = 0
        while stack:
            node = stack.pop()
            size += 1
            for neighbor in adjacency[node]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        sizes.append(size)
    return sizes


def compute_stats(data: HeteroData) -> GraphStats:
    """Calcula conteos por tipo, grado medio y componentes conexas de `data`.

    Lanza `ValueError` si una relación no tiene `edge_index` válido o apunta a nodos
    inexistentes: las estadísticas de un grafo inconsistente no serían interpretables.
    """
    counts = _node_counts(data)
    pairs = _edge_pairs(data, counts)
    adjacency = _adjacency(counts, pairs)
    degree_by_type = {node_type: 0 for node_type in counts}
    for (node_type, _), neighbors in adjacency.items():
        degree_by_type[node_type] += len(neighbors)
    total_nodes = sum(counts.values())
    total_edges = sum(len(edge_pairs) for edge_pairs in pairs.values())
    sizes = _component_sizes(adjacency)
    graph_id = getattr(data, "graph_id", None)
    return GraphStats(
        graph_id=str(graph_id) if graph_id is not None else None,
        nodes=counts,
        edges={edge_type: len(edge_pairs) for edge_type, edge_pairs in pairs.items()},
        mean_degree=2 * total_edges / total_nodes if total_nodes else 0.0,
        mean_degree_by_type={
            node_type: degree_by_type[node_type] / size if size else 0.0
            for node_type, size in counts.items()
        },
        num_components=len(sizes),
        largest_component=max(sizes, default=0),
        isolated_nodes=sum(1 for neighbors in adjacency.values() if not neighbors),
    )


def format_stats(stats: GraphStats) -> list[str]:
    """Resumen legible de `stats`, una línea por elemento."""
    lines = [
        f"[{stats.graph_id or 'sin graph_id'}]",
        f"  nodos: {stats.num_nodes}  aristas: {stats.num_edges}  "
        f"grado medio: {stats.mean_degree:.3f}",
        f"  componentes conexas: {stats.num_components}  "
        f"mayor: {stats.largest_component} nodos  aislados: {stats.isolated_nodes}",
        "  nodos por tipo (grado medio):",
    ]
    lines.extend(
        f"    {node_type}: {count} ({stats.mean_degree_by_type[node_type]:.3f})"
        for node_type, count in stats.nodes.items()
    )
    lines.append("  aristas por relación:")
    lines.extend(f"    {'|'.join(edge_type)}: {count}" for edge_type, count in stats.edges.items())
    return lines


# ---------------------------------------------------------------------------
# Subgrafo de muestra
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Subgraph:
    """Nodos y aristas de un subgrafo de muestra, en el orden en que se visitaron."""

    seed: NodeRef
    nodes: tuple[NodeRef, ...]
    edges: tuple[tuple[NodeRef, str, NodeRef], ...]


def resolve_node(data: HeteroData, reference: str) -> NodeRef:
    """Traduce `tipo:id` a `(tipo, fila)`.

    `id` es un valor de la lista `node_id` del tipo, si el grafo la tiene, o el número de fila.
    Solo el primer `:` separa el tipo, porque los `node_id` sintéticos contienen `:`.
    """
    node_type, separator, identifier = reference.partition(":")
    if not separator or node_type not in data.node_types:
        raise ValueError(f"{reference!r} no tiene la forma tipo:id con un tipo de nodo del grafo.")
    size = int(data[node_type].num_nodes or 0)
    node_ids = getattr(data[node_type], "node_id", None)
    if isinstance(node_ids, list) and identifier in node_ids:
        return (node_type, node_ids.index(identifier))
    if identifier.isdigit() and int(identifier) < size:
        return (node_type, int(identifier))
    raise ValueError(f"No existe el nodo {identifier!r} en {node_type} ({size} nodos).")


def sample_subgraph(
    data: HeteroData, *, seed: NodeRef | None = None, hops: int = 1, max_nodes: int = 25
) -> Subgraph:
    """Extrae un subgrafo de muestra por búsqueda en anchura desde `seed`.

    Sin `seed`, parte del nodo de mayor grado (desempate: orden de `data.node_types` y fila).
    Visita los vecinos en orden determinista hasta `hops` saltos o `max_nodes` nodos, y
    conserva todas las aristas entre los nodos visitados.
    """
    if hops < 0 or max_nodes < 1:
        raise ValueError("hops debe ser >= 0 y max_nodes >= 1.")
    counts = _node_counts(data)
    pairs = _edge_pairs(data, counts)
    adjacency = _adjacency(counts, pairs)
    if not adjacency:
        raise ValueError("El grafo no tiene nodos.")
    if seed is None:
        seed = max(adjacency, key=lambda node: len(adjacency[node]))
    elif seed not in adjacency:
        raise ValueError(f"El nodo {seed} no existe en el grafo.")

    type_order = {node_type: position for position, node_type in enumerate(counts)}
    selected = {seed: 0}
    queue = deque([seed])
    while queue and len(selected) < max_nodes:
        node = queue.popleft()
        if selected[node] == hops:
            continue
        neighbors = sorted(
            set(adjacency[node]),
            key=lambda ref: (type_order[ref[0]], ref[1]),
        )
        for neighbor in neighbors:
            if neighbor in selected:
                continue
            if len(selected) == max_nodes:
                break
            selected[neighbor] = selected[node] + 1
            queue.append(neighbor)

    edges: list[tuple[NodeRef, str, NodeRef]] = []
    for edge_type, edge_pairs in pairs.items():
        source_type, relation, target_type = edge_type
        for source, target in edge_pairs:
            if (source_type, source) in selected and (target_type, target) in selected:
                edges.append(((source_type, source), relation, (target_type, target)))
    return Subgraph(seed=seed, nodes=tuple(selected), edges=tuple(edges))


def _label(data: HeteroData, node: NodeRef) -> str:
    node_type, row = node
    node_ids = getattr(data[node_type], "node_id", None)
    identifier = str(node_ids[row]) if isinstance(node_ids, list) else f"#{row}"
    return f"{node_type}<br/>{identifier}".replace('"', "#quot;")


def to_mermaid(data: HeteroData, subgraph: Subgraph) -> str:
    """Diagrama Mermaid (`flowchart LR`) del subgrafo, con un color por tipo de nodo."""
    names = {node: f"n{position}" for position, node in enumerate(subgraph.nodes)}
    lines = ["flowchart LR"]
    lines.extend(f'  {names[node]}["{_label(data, node)}"]' for node in subgraph.nodes)
    lines.extend(
        f"  {names[source]} -->|{relation}| {names[target]}"
        for source, relation, target in subgraph.edges
    )
    for position, node_type in enumerate(str(node_type) for node_type in data.node_types):
        members = [names[node] for node in subgraph.nodes if node[0] == node_type]
        if not members:
            continue
        fill, stroke = MERMAID_PALETTE[position % len(MERMAID_PALETTE)]
        lines.append(f"  classDef type{position} fill:{fill},stroke:{stroke},color:#000")
        lines.append(f"  class {','.join(members)} type{position}")
    return "\n".join(lines) + "\n"
