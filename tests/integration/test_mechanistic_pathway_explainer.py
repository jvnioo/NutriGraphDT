"""Explicaciones sobre un escenario sintético con ruta plantada y sus variantes (A60-P4, #168).

Qué comprueba
-------------
Sobre un grafo sintético con una cadena `diet -> substrate -> taxon -> function -> metabolite`
y una cadena distractora, y sobre dos variantes (arista `taxon:1 -> function:1` eliminada o
desviada a `function:2`), comprueba el comportamiento estructural del wrapper:

1. Con la misma semilla, el explicador devuelve exactamente la misma explicación.
2. La explicación lista exactamente las aristas del grafo explicado (directas e inversas), con
   sus identificadores: una arista eliminada no aparece y una desviada aparece con sus nuevos
   extremos. El explicador no inventa ni conserva estructura que el grafo no tiene.
3. Cada explicación cumple el contrato `1.0.0` y declara las advertencias obligatorias.

Qué no comprueba
----------------
El modelo **no está entrenado** (pesos iniciales con semilla fija) y el grafo no tiene target,
así que la ruta plantada no tiene ningún papel predictivo: estas pruebas no miden si el explicador
recupera una ruta. Ese criterio de #168 sigue abierto (ver §7 de
`docs/models/explainer-wrapper-compatibility.md`). Ninguna de estas pruebas demuestra causalidad
ni validez biológica en D1; todos los datos son sintéticos (`is_synthetic=True`) y sus valores no
representan cantidades biológicas.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from torch_geometric.data import HeteroData  # noqa: E402

from nutrigraphdt.explainability import (  # noqa: E402
    ATTENTION_WARNING,
    EXPLANATION_FORMAT_VERSION,
    REQUIRED_WARNINGS,
    SYNTHETIC_WARNING,
    HeteroExplainer,
    validate_explanation,
)
from nutrigraphdt.models.gnn.base import GraphMetadata  # noqa: E402
from nutrigraphdt.models.gnn.factory import build_model, load_model_config  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]

SCENARIOS = ("intact", "broken", "permuted")
EdgeKey = tuple[str, str, str, str, str]


def build_pathway_scenario(variant: str = "intact") -> HeteroData:
    """Grafo sintético con una ruta plantada (`...:0001`) y una cadena distractora (`...:0002`).

    Ruta plantada: `diet:1 -> substrate:1 -> taxon:1 -> function:1 -> metabolite:1`.

    Variantes de `taxon -> has_capacity -> function`:
    * `intact`: `taxon:1 -> function:1` y la distractora `taxon:2 -> function:2`.
    * `broken`: solo la distractora; la ruta plantada queda cortada.
    * `permuted`: `taxon:1 -> function:2` y `taxon:2 -> function:1`.

    Los atributos son valores arbitrarios del escenario, sin unidad ni significado biológico.
    """
    data = HeteroData()
    data.graph_id = f"synthetic:pathway_validation:{variant}"
    data.is_synthetic = True

    features = {
        "diet": [[1.0, 0.5], [0.1, 0.05]],
        "substrate": [[2.0, 1.0], [0.1, 0.1]],
        "taxon": [[5.0, 3.0], [0.05, 0.02]],
        "function": [[4.0], [0.2]],
        "metabolite": [[1.5], [0.1]],
    }
    for node_type, rows in features.items():
        data[node_type].x = torch.tensor(rows, dtype=torch.float32)
        data[node_type].missing_mask = torch.zeros_like(data[node_type].x, dtype=torch.bool)
        data[node_type].node_id = [f"synthetic:{node_type}:{i + 1:04d}" for i in range(len(rows))]

    has_capacity = {
        "intact": [[0, 1], [0, 1]],
        "broken": [[1], [1]],
        "permuted": [[0, 1], [1, 0]],
    }[variant]
    edges = {
        ("diet", "provides", "substrate"): [[0, 1], [0, 1]],
        ("substrate", "available_to", "taxon"): [[0, 1], [0, 1]],
        ("taxon", "has_capacity", "function"): has_capacity,
        ("function", "produces", "metabolite"): [[0, 1], [0, 1]],
    }
    for (source, relation, target), index in edges.items():
        edge_index = torch.tensor(index, dtype=torch.long)
        data[source, relation, target].edge_index = edge_index
        data[target, f"rev_{relation}", source].edge_index = edge_index.flip(0)

    # Evidencia declarada (EXP-06): sintética en las directas, ausente en las inversas.
    for edge_type in data.edge_types:
        count = data[edge_type].edge_index.shape[1]
        reverse = edge_type[1].startswith("rev_")
        data[edge_type].evidence_status = [None if reverse else "synthetic"] * count
        data[edge_type].evidence_method = [None if reverse else "synthetic_generator"] * count
        data[edge_type].evidence_source = [None] * count

    return data


def graph_edge_keys(data: HeteroData) -> set[EdgeKey]:
    """Claves `(source_type, relation, target_type, source_id, target_id)` de todas las aristas."""
    keys: set[EdgeKey] = set()
    for source, relation, target in data.edge_types:
        edge_index = data[source, relation, target].edge_index
        for i, j in edge_index.t().tolist():
            keys.add((source, relation, target, data[source].node_id[i], data[target].node_id[j]))
    return keys


@pytest.fixture(scope="module")
def untrained_model() -> Any:
    """`hetero_sage` con pesos iniciales (semilla fija): no aprendió ninguna ruta."""
    torch.manual_seed(168)
    metadata = GraphMetadata.from_graphs([build_pathway_scenario()])
    config = load_model_config(REPO_ROOT / "configs" / "models" / "hetero_sage.yaml")
    return build_model(config, metadata).eval()


def _explainer(model: Any) -> HeteroExplainer:
    return HeteroExplainer(model, algorithm="gnn_explainer", epochs=5, seed=42, top_k=4)


def test_explanation_is_deterministic(untrained_model: Any) -> None:
    graph = build_pathway_scenario()

    first = _explainer(untrained_model).explain(graph, target=0)
    second = _explainer(untrained_model).explain(graph, target=0)

    assert first.importance == second.importance
    assert first.subgraph == second.subgraph


@pytest.mark.parametrize("variant", SCENARIOS)
def test_explanation_lists_exactly_the_graph_edges(untrained_model: Any, variant: str) -> None:
    graph = build_pathway_scenario(variant)

    explanation = _explainer(untrained_model).explain(graph, target=0)

    explained = [
        (e.source_type, e.relation_type, e.target_type, e.source_id, e.target_id)
        for e in explanation.importance.edges
    ]
    assert len(explained) == len(set(explained))
    assert set(explained) == graph_edge_keys(graph)

    planted = ("taxon", "has_capacity", "function", "synthetic:taxon:0001")
    planted_targets = {key[4] for key in explained if key[:4] == planted}
    assert (
        planted_targets
        == {
            "intact": {"synthetic:function:0001"},
            "broken": set(),
            "permuted": {"synthetic:function:0002"},
        }[variant]
    )


@pytest.mark.parametrize("variant", SCENARIOS)
def test_explanation_meets_contract_and_warnings(untrained_model: Any, variant: str) -> None:
    explanation = _explainer(untrained_model).explain(build_pathway_scenario(variant), target=0)

    validated = validate_explanation(explanation.model_dump(mode="json"))

    assert validated.format_version == EXPLANATION_FORMAT_VERSION
    assert validated.target.is_synthetic
    codes = {warning.code for warning in validated.warnings}
    assert set(REQUIRED_WARNINGS) | {SYNTHETIC_WARNING} <= codes
    assert ATTENTION_WARNING not in codes
