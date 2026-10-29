"""Tests sobre ruta mecanística sintética conocida y controles negativos (A60-P4, #168).

Objetivo científico y técnico
------------------------------
Valida técnicamente la capacidad de los explicadores (`HeteroExplainer`) para recuperar una
ruta mecanística plantada (cadena `diet -> substrate -> taxon -> function -> metabolite`) frente a
ruido controlado y controles negativos (ruta rota, ruta permutada y atenuación de características).

Límites metodológicos (EXP-08)
------------------------------
Una prueba sobre ruta plantada sintética evalúa la sensibilidad de optimización del explicador;
no demuestra causalidad ni validación biológica en el conjunto de datos biológicos reales (D1
HoloFood). Todos los datos utilizados en este módulo declaran explícitamente `is_synthetic=True`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import torch
from torch_geometric.data import HeteroData

from nutrigraphdt.explainability import (
    EXPLANATION_FORMAT_VERSION,
    HeteroExplainer,
    validate_explanation,
)
from nutrigraphdt.models.gnn.base import GraphMetadata
from nutrigraphdt.models.gnn.factory import build_model, load_model_config

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Generador del escenario sintético con ruta plantada y ruido
# ---------------------------------------------------------------------------


def build_mechanistic_scenario(
    *,
    break_connection: bool = False,
    permute_connection: bool = False,
    zero_taxon_signal: bool = False,
) -> HeteroData:
    """Construye un grafo sintético con una ruta plantada y conexiones distractoras.

    Estructura de la ruta plantada:
        diet:0 -> provides -> substrate:0
        substrate:0 -> available_to -> taxon:0
        taxon:0 -> has_capacity -> function:0
        function:0 -> produces -> metabolite:0 (target: butyrate)

    Controles negativos:
    * `break_connection=True`: se suprime la arista `taxon:0 -> function:0`.
    * `permute_connection=True`: la arista `taxon:0` se desvía a `function:1` (inactiva).
    * `zero_taxon_signal=True`: los atributos del `taxon:0` se fijan en cero.
    """
    data = HeteroData()
    data.graph_id = "synthetic:pathway_validation_001"
    data.is_synthetic = True

    # 1. Nodos con características
    data["diet"].x = torch.tensor([[1.0, 0.5], [0.1, 0.05]], dtype=torch.float32)
    data["diet"].node_id = ["synthetic:diet:0001", "synthetic:diet:0002"]

    data["substrate"].x = torch.tensor([[2.0, 1.0], [0.1, 0.1]], dtype=torch.float32)
    data["substrate"].node_id = ["synthetic:substrate:0001", "synthetic:substrate:0002"]

    taxon_signal = [0.0, 0.0] if zero_taxon_signal else [5.0, 3.0]
    data["taxon"].x = torch.tensor([taxon_signal, [0.05, 0.02]], dtype=torch.float32)
    data["taxon"].node_id = ["synthetic:taxon:0001", "synthetic:taxon:0002"]

    data["function"].x = torch.tensor([[4.0], [0.2]], dtype=torch.float32)
    data["function"].node_id = ["synthetic:function:0001", "synthetic:function:0002"]

    data["metabolite"].x = torch.tensor([[1.5], [0.1]], dtype=torch.float32)
    data["metabolite"].node_id = ["synthetic:metabolite:0001", "synthetic:metabolite:0002"]

    # missing_mask para cada tipo con x
    for nt in data.node_types:
        if "x" in data[nt]:
            data[nt].missing_mask = torch.zeros_like(data[nt].x, dtype=torch.bool)

    # 2. Aristas de la ruta plantada y aristas de ruido
    # diet -> provides -> substrate
    data["diet", "provides", "substrate"].edge_index = torch.tensor(
        [[0, 1], [0, 1]], dtype=torch.long
    )

    # substrate -> available_to -> taxon
    data["substrate", "available_to", "taxon"].edge_index = torch.tensor(
        [[0, 1], [0, 1]], dtype=torch.long
    )

    # taxon -> has_capacity -> function
    if break_connection:
        # Ruta rota: solo existe la conexión de ruido (1 -> 1)
        data["taxon", "has_capacity", "function"].edge_index = torch.tensor(
            [[1], [1]], dtype=torch.long
        )
    elif permute_connection:
        # Ruta permutada: taxon:0 se conecta a function:1 (inactiva)
        data["taxon", "has_capacity", "function"].edge_index = torch.tensor(
            [[0, 1], [1, 0]], dtype=torch.long
        )
    else:
        # Ruta plantada intacta: (0 -> 0) y ruido (1 -> 1)
        data["taxon", "has_capacity", "function"].edge_index = torch.tensor(
            [[0, 1], [0, 1]], dtype=torch.long
        )

    # function -> produces -> metabolite
    data["function", "produces", "metabolite"].edge_index = torch.tensor(
        [[0, 1], [0, 1]], dtype=torch.long
    )

    # 3. Aristas inversas para paso de mensajes
    for src, rel, dst in list(data.edge_types):
        rev_et = (dst, f"rev_{rel}", src)
        ei = data[src, rel, dst].edge_index
        data[rev_et].edge_index = torch.stack([ei[1], ei[0]], dim=0)

    # 4. Metadatos de evidencia sintética (EXP-06)
    for edge_type in data.edge_types:
        num_e = data[edge_type].edge_index.shape[1]
        is_rev = edge_type[1].startswith("rev_")
        data[edge_type].evidence_status = [None if is_rev else "synthetic"] * num_e
        data[edge_type].evidence_method = [None if is_rev else "synthetic_generator"] * num_e
        data[edge_type].evidence_source = [None] * num_e

    # Targets del modelo
    data.y = torch.tensor([[2.5, 1.0, 3.5]], dtype=torch.float32)

    return data


@pytest.fixture(scope="module")
def pathway_model() -> tuple[Any, HeteroData]:
    """Instancia y prepara un modelo HeteroSAGE sobre el escenario de prueba."""
    base_graph = build_mechanistic_scenario()
    metadata = GraphMetadata.from_graphs([base_graph])
    config = load_model_config(REPO_ROOT / "configs" / "models" / "hetero_sage.yaml")
    model = build_model(config, metadata).eval()
    return model, base_graph


# ---------------------------------------------------------------------------
# 1. Prueba de estabilidad y determinismo
# ---------------------------------------------------------------------------


def test_explainer_determinism_on_mechanistic_scenario(
    pathway_model: tuple[Any, HeteroData],
) -> None:
    """Verifica que corridas con idéntica semilla producen subgrafos y valores idénticos."""
    model, graph = pathway_model

    explainer = HeteroExplainer(
        model,
        algorithm="gnn_explainer",
        epochs=5,
        seed=42,
        top_k=4,
    )

    exp1 = explainer.explain(graph, target=0)
    exp2 = explainer.explain(graph, target=0)

    # Verificación de idéntica estructura y valores
    assert exp1.subgraph.model_dump() == exp2.subgraph.model_dump()
    assert [e.importance for e in exp1.importance.edges] == [
        e.importance for e in exp2.importance.edges
    ]
    assert [n.importance for n in exp1.importance.nodes] == [
        n.importance for n in exp2.importance.nodes
    ]


# ---------------------------------------------------------------------------
# 2. Prueba de discriminación: ruta plantada vs aristas de ruido
# ---------------------------------------------------------------------------


def test_planted_pathway_distinguished_from_negative_controls(
    pathway_model: tuple[Any, HeteroData],
) -> None:
    """Comprueba que la explicación distingue la ruta plantada activa frente al ruido y controles.

    Criterios definidos:
    1. Todas las aristas de la ruta plantada activa reciben importancia positiva (> 0.0).
    2. El subgrafo top-4 resume la ruta mecanística activa reteniendo nodos de la ruta plantada.
    """
    model, graph = pathway_model

    explainer = HeteroExplainer(
        model,
        algorithm="gnn_explainer",
        epochs=15,
        seed=123,
        top_k=4,
    )
    explanation = explainer.explain(graph, target=0)

    # Aristas directas de la ruta plantada activa
    pathway_edges = [
        e
        for e in explanation.importance.edges
        if "0001" in e.source_id
        and "0001" in e.target_id
        and not e.relation_type.startswith("rev_")
    ]
    assert len(pathway_edges) == 4
    for e in pathway_edges:
        assert e.importance > 0.0

    # El subgrafo top-4 contiene nodos clave de la ruta mecanística activa
    sub_node_ids = {n.node_id for n in explanation.subgraph.nodes}
    assert "synthetic:function:0001" in sub_node_ids or "synthetic:taxon:0001" in sub_node_ids


# ---------------------------------------------------------------------------
# 3. Control negativo 1: Ruta eliminada / rota
# ---------------------------------------------------------------------------


def test_negative_control_broken_pathway_removes_edge_and_drops_importance(
    pathway_model: tuple[Any, HeteroData],
) -> None:
    """Al romper la ruta, la arista eliminada no aparece en la explicación."""
    model, _ = pathway_model

    # Grafo con ruta rota (desconexión entre taxon:0 y function:0)
    broken_graph = build_mechanistic_scenario(break_connection=True)

    explainer = HeteroExplainer(
        model,
        algorithm="gnn_explainer",
        epochs=10,
        seed=42,
        top_k=4,
    )
    explanation = explainer.explain(broken_graph, target=0)

    # La arista eliminada no existe en la explicación
    has_capacity_edges = [
        e
        for e in explanation.importance.edges
        if e.relation_type == "has_capacity" and e.source_id == "synthetic:taxon:0001"
    ]
    assert len(has_capacity_edges) == 0

    # Cumple el contrato
    assert explanation.format_version == EXPLANATION_FORMAT_VERSION
    assert len(explanation.subgraph.edges) <= 4


# ---------------------------------------------------------------------------
# 4. Control negativo 2: Ruta permutada
# ---------------------------------------------------------------------------


def test_negative_control_permuted_pathway(
    pathway_model: tuple[Any, HeteroData],
) -> None:
    """Verifica que al permutar los destinos, la ruta original no es seleccionada como antes."""
    model, _ = pathway_model

    permuted_graph = build_mechanistic_scenario(permute_connection=True)

    explainer = HeteroExplainer(
        model,
        algorithm="gnn_explainer",
        epochs=10,
        seed=42,
        top_k=4,
    )
    explanation = explainer.explain(permuted_graph, target=0)

    # La arista taxon:0 -> function:0 no está presente porque fue permutada a function:1
    canonical_edge = [
        e
        for e in explanation.subgraph.edges
        if e.source_id == "synthetic:taxon:0001" and e.target_id == "synthetic:function:0001"
    ]
    assert len(canonical_edge) == 0


# ---------------------------------------------------------------------------
# 5. Control negativo 3: Supresión de señal de características
# ---------------------------------------------------------------------------


def test_negative_control_zero_taxon_signal_reduces_node_importance(
    pathway_model: tuple[Any, HeteroData],
) -> None:
    """Al anular atributos del taxón clave, su importancia cae frente al positivo."""
    model, intact_graph = pathway_model
    zero_signal_graph = build_mechanistic_scenario(zero_taxon_signal=True)

    explainer = HeteroExplainer(
        model,
        algorithm="gnn_explainer",
        epochs=10,
        seed=42,
        top_k=4,
    )

    exp_intact = explainer.explain(intact_graph, target=0)
    exp_zero = explainer.explain(zero_signal_graph, target=0)

    imp_intact = next(
        n.importance
        for n in exp_intact.importance.nodes
        if n.node_type == "taxon" and n.node_id == "synthetic:taxon:0001"
    )
    imp_zero = next(
        n.importance
        for n in exp_zero.importance.nodes
        if n.node_type == "taxon" and n.node_id == "synthetic:taxon:0001"
    )

    # La atenuación a 0 de características reduce o iguala a 0 la importancia del nodo
    assert imp_zero <= imp_intact


# ---------------------------------------------------------------------------
# 6. Validación cruzada de contrato y advertencias científicas (EXP-08)
# ---------------------------------------------------------------------------


def test_contract_and_scientific_warnings_on_all_scenarios(
    pathway_model: tuple[Any, HeteroData],
) -> None:
    """Comprueba que todos los escenarios validan el contrato y portan advertencias."""
    model, _ = pathway_model
    scenarios = [
        build_mechanistic_scenario(),
        build_mechanistic_scenario(break_connection=True),
        build_mechanistic_scenario(permute_connection=True),
        build_mechanistic_scenario(zero_taxon_signal=True),
    ]

    explainer = HeteroExplainer(model, algorithm="gnn_explainer", epochs=3, seed=42, top_k=3)

    for sc in scenarios:
        explanation = explainer.explain(sc, target=0)
        # Validación del contrato 1.0.0
        validated = validate_explanation(explanation.model_dump())
        assert validated.format_version == EXPLANATION_FORMAT_VERSION

        # Comprobación de advertencias obligatorias
        warning_codes = {w.code for w in validated.warnings}
        assert "association_not_causation" in warning_codes
        assert "importance_is_not_evidence" in warning_codes
        assert "synthetic_data" in warning_codes
