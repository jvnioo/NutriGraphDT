"""Target por grafo de las GNN (A41-5, #81; §2.1 del diseño de A41-1, #77).

`add_graph_target` lleva los AGCC de los nodos `metabolite` a atributos del grafo:

| Atributo | Forma | Contenido |
|---|---|---|
| `data.y_graph` | `[1, 3]`, `float32` | Acetato, propionato y butirato; `0.0` donde falta. |
| `data.y_graph_mask` | `[1, 3]`, `bool` | `True` donde el AGCC tiene valor. |

Al agrupar en lotes, PyG concatena ambos en `[B, 3]`. `masked_mse_loss` es la pérdida que solo
cuenta las celdas con `y_graph_mask = True`.

Objetivo composicional (contrato de datos v2, sección 1; #146): `compositional_graph_target`
deriva de `y_graph` e `y_graph_mask` la salida `[B, 3]` = `(z_1, z_2, ln T)` y una máscara
`[B, 1]` por animal, con las definiciones de `nutrigraphdt.models.composition`. No se guarda
una segunda copia del objetivo en el grafo: el valor medido sigue siendo `y_graph`.
`concentrations_from_graph_output` es la inversa, a mmol/kg.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import torch
from torch import Tensor
from torch_geometric.data import HeteroData

from nutrigraphdt.models.composition import CompositionalReconstructionError
from nutrigraphdt.models.metrics import DEFAULT_SCFA_TARGETS
from nutrigraphdt.models.tabular import CHEMICAL_ID_TO_CANONICAL

TARGET_NODE_TYPE = "metabolite"


def canonical_scfa_name(chemical_id: str) -> str | None:
    """Nombre canónico del AGCC de un `chemical_id`, o `None` si no es uno de los objetivos.

    Usa la tabla `CHEMICAL_ID_TO_CANONICAL` de A40-3 con coincidencia **exacta**: con
    coincidencia por subcadena, `isobutyrate` se confundiría con `butyrate`.
    """
    return CHEMICAL_ID_TO_CANONICAL.get(chemical_id.lower().strip())


def _chemical_id(node_id: str, attributes: Mapping[str, Any] | None) -> str:
    # En el sintético el node_id es opaco (`synthetic:metabolite:0001`) y el nombre está en
    # `chemical_id`; en D1 ambos son el nombre canónico (`acetate`).
    if attributes is not None:
        value = attributes.get("chemical_id")
        if isinstance(value, str) and value:
            return value
    return node_id


def add_graph_target(data: HeteroData, targets: Sequence[str] = DEFAULT_SCFA_TARGETS) -> HeteroData:
    """Agrega `y_graph` y `y_graph_mask` (`[1, len(targets)]`) a `data` y lo devuelve.

    Modifica `data` en su lugar, como las transformaciones de PyG. Lee `y` e `y_mask` de los
    nodos `metabolite`. Los metabolitos que no son objetivo (lactato, valerato…) se ignoran. Un
    grafo sin nodos `metabolite`, o sin `y`, queda con la máscara en `False`.

    Raises
    ------
    ValueError
        Si dos nodos con valor se asignan al mismo AGCC, o si `y`/`y_mask` no tienen forma
        `[N, 1]`.
    """
    names = tuple(targets)
    if isinstance(targets, str) or not names or len(set(names)) != len(names):
        raise ValueError("targets debe ser una secuencia no vacía de nombres distintos.")
    values = torch.zeros((1, len(names)), dtype=torch.float32)
    mask = torch.zeros((1, len(names)), dtype=torch.bool)
    column = {name: position for position, name in enumerate(names)}

    if TARGET_NODE_TYPE in data.node_types:
        store = data[TARGET_NODE_TYPE]
        if "y" in store and "y_mask" in store:
            y: Tensor = store.y
            y_mask: Tensor = store.y_mask
            node_ids = list(store.node_id) if "node_id" in store else []
            attributes = list(store.raw_attributes) if "raw_attributes" in store else []
            size = len(node_ids)
            if tuple(y.shape) != (size, 1) or tuple(y_mask.shape) != (size, 1):
                raise ValueError(
                    f"y e y_mask de '{TARGET_NODE_TYPE}' deben tener forma [{size}, 1]; "
                    f"tienen {list(y.shape)} y {list(y_mask.shape)}."
                )
            for row, node_id in enumerate(node_ids):
                if not bool(y_mask[row, 0]):
                    continue
                record = attributes[row] if row < len(attributes) else None
                canonical = canonical_scfa_name(_chemical_id(str(node_id), record))
                position = column.get(canonical) if canonical is not None else None
                if position is None:
                    continue
                if mask[0, position]:
                    raise ValueError(
                        f"Más de un nodo '{TARGET_NODE_TYPE}' con valor para '{canonical}'."
                    )
                values[0, position] = y[row, 0].to(torch.float32)
                mask[0, position] = True

    data.y_graph = values
    data.y_graph_mask = mask
    return data


def masked_mse_loss(prediction: Tensor, target: Tensor, mask: Tensor) -> Tensor:
    """Error cuadrático medio sobre las celdas con `mask = True`.

    Con todas las celdas enmascaradas devuelve `0.0` conectado al grafo de cómputo, para que
    un lote sin targets no rompa `backward()`.
    """
    if prediction.shape != target.shape or prediction.shape != mask.shape:
        raise ValueError(
            "prediction, target y mask deben tener la misma forma; tienen "
            f"{list(prediction.shape)}, {list(target.shape)} y {list(mask.shape)}."
        )
    if mask.dtype != torch.bool:
        raise ValueError(f"mask debe ser booleana; es {mask.dtype}.")
    if not bool(mask.any()):
        return prediction.sum() * 0.0
    difference = prediction[mask] - target[mask]
    return (difference**2).mean()


def compositional_graph_target(y_graph: Tensor, y_graph_mask: Tensor) -> tuple[Tensor, Tensor]:
    """`y_graph` (`[B, 3]`, mmol/kg) → objetivo `(z_1, z_2, ln T)` `[B, 3]` y máscara `[B, 1]`.

    Las columnas de `y_graph` siguen `DEFAULT_SCFA_TARGETS` (acetato, propionato, butirato). La
    máscara de un animal es `True` solo si los tres AGCC tienen valor finito y estrictamente
    positivo; si no, sus tres salidas son `0.0` y no entran a la pérdida (sin pseudoconteo).
    Misma definición que `nutrigraphdt.models.composition.compositional_target`.
    """
    if y_graph.dim() != 2 or y_graph.shape[1] != len(DEFAULT_SCFA_TARGETS):
        raise ValueError(f"y_graph debe tener forma [B, 3]; tiene {list(y_graph.shape)}.")
    if y_graph_mask.shape != y_graph.shape or y_graph_mask.dtype != torch.bool:
        raise ValueError("y_graph_mask debe ser booleana y con la forma de y_graph.")
    values = y_graph.to(torch.float64)
    valid = (y_graph_mask & torch.isfinite(values) & (values > 0)).all(dim=1, keepdim=True)
    safe = torch.where(valid, values, torch.ones_like(values))
    log_values = safe.log()
    z = log_values[:, 1:] - log_values[:, :1]
    log_total = safe.sum(dim=1, keepdim=True).log()
    target = torch.cat([z, log_total], dim=1)
    target = torch.where(valid, target, torch.zeros_like(target))
    return target.to(y_graph.dtype), valid


def concentrations_from_graph_output(output: Tensor) -> Tensor:
    """Salida `(z_1, z_2, ln T)` `[B, 3]` → concentraciones reconstruidas `[B, 3]` en mmol/kg.

    Softmax de `(0, z_1, z_2)` por `exp(ln T)`; inversa de `compositional_graph_target`.
    """
    if output.dim() != 2 or output.shape[1] != 3:
        raise ValueError(f"output debe tener forma [B, 3]; tiene {list(output.shape)}.")
    if not bool(torch.isfinite(output).all()):
        raise CompositionalReconstructionError("La salida composicional contiene NaN o infinito.")
    logits = torch.cat([torch.zeros_like(output[:, :1]), output[:, :2]], dim=1)
    concentrations = torch.softmax(logits, dim=1) * output[:, 2:].exp()
    if not bool(torch.isfinite(concentrations).all()):
        raise CompositionalReconstructionError(
            "La salida composicional produjo concentraciones no finitas."
        )
    return concentrations


__all__ = [
    "TARGET_NODE_TYPE",
    "add_graph_target",
    "canonical_scfa_name",
    "compositional_graph_target",
    "concentrations_from_graph_output",
    "masked_mse_loss",
]
