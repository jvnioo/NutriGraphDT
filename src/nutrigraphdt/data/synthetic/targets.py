"""Targets sintéticos de ácidos grasos de cadena corta (AGCC) para el prototipo (A35-1, #28).

Produce los registros de `outputs.jsonl` que el prototipo `HeteroData` usa como variable
objetivo: la concentración de los metabolitos AGCC de cada instancia. Sigue el contrato de
Salida de `docs/synthetic-dataset/synthetic-dataset-spec.md`:

- `measured_or_predicted = "synthetic"`: un target artificial nunca es una medición.
- `unit` y `sample_matrix` se copian del metabolito, para no mezclar unidades ni matrices.
- `model_version = null`, porque no es una predicción.

La elección de la variable objetivo sigue pendiente de Investigación (§6.1-iii del Esquema
General). DS-01 admite IDs sintéticos de AGCC como ejemplo, y la lista por defecto (acetato,
propionato y butirato) es la que priorizan el Esquema General (Figura 1) y el loader de
metaboloma (A34-3). Es configurable y no afirma que otros metabolitos no sean AGCC: el valerato
del catálogo, por ejemplo, queda fuera solo porque no está en esa lista priorizada.

Un metabolito objetivo se reconoce por su `chemical_id` exacto. Las copias que el generador crea
más allá del catálogo (`synthetic:metabolite:acetate_07`) no coinciden: son etiquetas
sintéticas, y la configuración debe listarlas explícitamente si se quieren incluir.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from nutrigraphdt.data.synthetic.nodes import Node, NodeType

if TYPE_CHECKING:
    from nutrigraphdt.data.synthetic.export import OutputRecord

DEFAULT_TARGET_CHEMICAL_IDS: tuple[str, ...] = (
    "synthetic:metabolite:acetate",
    "synthetic:metabolite:propionate",
    "synthetic:metabolite:butyrate",
)
"""AGCC priorizados como variable objetivo del prototipo (configurable)."""

TARGET_KIND = "synthetic"
"""Origen de todo target generado aquí (contrato de Salida)."""


@dataclass(frozen=True)
class SyntheticTargetConfig:
    """Metabolitos cuya concentración se exporta como target sintético."""

    chemical_ids: tuple[str, ...] = DEFAULT_TARGET_CHEMICAL_IDS

    def __post_init__(self) -> None:
        if not self.chemical_ids:
            raise ValueError("chemical_ids debe contener al menos un identificador.")
        if not all(isinstance(value, str) and value for value in self.chemical_ids):
            raise ValueError("chemical_ids solo admite cadenas no vacías.")
        if len(set(self.chemical_ids)) != len(self.chemical_ids):
            raise ValueError("chemical_ids no admite identificadores repetidos.")

    def to_dict(self) -> dict[str, list[str]]:
        """Configuración efectiva para `metadata.json`."""
        return {"chemical_ids": list(self.chemical_ids)}


DEFAULT_TARGET_CONFIG = SyntheticTargetConfig()


def _text(node: Node, name: str) -> str | None:
    if node.missing_mask.get(name, False):
        return None
    value = node.attributes.get(name)
    return value if isinstance(value, str) and value else None


def generate_synthetic_targets(
    nodes: Iterable[Node], config: SyntheticTargetConfig | None = None
) -> list[OutputRecord]:
    """Una salida sintética por cada metabolito objetivo con concentración conocida.

    Un metabolito con la concentración, la unidad o la matriz ausentes no produce target:
    inventar el valor contradiría DS-01. El resultado está en el orden determinista de
    exportación (`graph_id`, `target_type`, `target_id`).
    """
    # Importación diferida: `export` usa este módulo para generar los datasets.
    from nutrigraphdt.data.synthetic.export import OutputRecord

    config = config or DEFAULT_TARGET_CONFIG
    wanted = set(config.chemical_ids)
    outputs: list[OutputRecord] = []
    for node in nodes:
        if node.node_type != NodeType.METABOLITE.value:
            continue
        if _text(node, "chemical_id") not in wanted:
            continue
        concentration = node.attributes.get("concentration")
        unit = _text(node, "unit")
        sample_matrix = _text(node, "sample_matrix")
        if (
            node.missing_mask.get("concentration", False)
            or isinstance(concentration, bool)
            or not isinstance(concentration, int | float)
            or not math.isfinite(concentration)
            or unit is None
            or sample_matrix is None
        ):
            continue
        outputs.append(
            OutputRecord(
                graph_id=node.graph_id,
                target_type=NodeType.METABOLITE.value,
                target_id=node.node_id,
                value=concentration,
                measured_or_predicted=TARGET_KIND,
                unit=unit,
                sample_matrix=sample_matrix,
                model_version=None,
            )
        )
    outputs.sort(key=lambda output: (output.graph_id, output.target_type, output.target_id))
    return outputs
