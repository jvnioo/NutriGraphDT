"""Pruebas unitarias de agregación y normalización de importancias (A60-P2, #171).

Verifica:
1. Agregación manual con tensores pequeños conocidos.
2. Identificación explícita de tipos de nodo, relaciones, índices/IDs y valores.
3. Determinismo de cálculo.
4. Manejo correcto de tipos ausentes (importancia 0.0, EXP-05).
5. Rango [0, 1] y valores absolutos (sin signos residuales).
6. Conformidad con el contrato A55-P3 (validate_explanation).
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from torch_geometric.data import HeteroData  # noqa: E402

from nutrigraphdt.explainability.contract import (  # noqa: E402
    EXPLANATION_FORMAT,
    EXPLANATION_FORMAT_VERSION,
    ExplainerRef,
    Explanation,
    Importance,
    RunRef,
    Scale,
    SplitRef,
    Subgraph,
    TargetRef,
    validate_explanation,
)
from nutrigraphdt.explainability.importance import (  # noqa: E402
    compute_attribute_importance,
    compute_edge_importance,
    compute_node_importance,
    compute_norm_factor,
)


def _build_test_graph() -> HeteroData:
    """Crea un grafo sintético mínimo con 2 tipos de nodo y 1 tipo de arista del esquema."""
    data = HeteroData()
    data.graph_id = "synthetic:test_graph_001"
    data.is_synthetic = True

    # 2 taxones con 3 características cada uno
    data["taxon"].x = torch.tensor([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=torch.float32)
    data["taxon"].node_id = ["taxon_0", "taxon_1"]

    # 3 funciones con 1 característica cada una
    data["function"].x = torch.tensor([[10.0], [20.0], [30.0]], dtype=torch.float32)
    data["function"].node_id = ["function_0", "function_1", "function_2"]

    # 2 aristas (taxon -> has_capacity -> function)
    # (0 -> 1) y (1 -> 2)
    data["taxon", "has_capacity", "function"].edge_index = torch.tensor(
        [[0, 1], [1, 2]], dtype=torch.long
    )
    data["taxon", "has_capacity", "function"].evidence_status = ["synthetic", "synthetic"]
    data["taxon", "has_capacity", "function"].evidence_method = [
        "synthetic_generator",
        "synthetic_generator",
    ]
    return data


# ---------------------------------------------------------------------------
# 1. Prueba de verificación manual con tensores pequeños
# ---------------------------------------------------------------------------


def test_manual_aggregation_small_tensors() -> None:
    """Verifica manualmente la agregación y normalización con tensores pequeños precalculados.

    Configuración:
    * taxon_mask: [[-0.2, 0.4, -0.6], [0.8, -1.0, 0.0]] (máximo abs = 1.0)
    * function_mask: [[0.5], [-0.25], [0.1]] (máximo abs = 0.5)
    * edge_mask: [0.5, -0.75] (máximo abs = 0.75)

    Máximo absoluto global = 1.0 (en taxon_mask[1, 1]).
    Por tanto, norm_factor = 1.0.

    Cálculos esperados:
    - taxon_0 node imp: sum(abs([-0.2, 0.4, -0.6])) / (1.0 * 3) = 1.2 / 3.0 = 0.4
    - taxon_1 node imp: sum(abs([0.8, -1.0, 0.0])) / (1.0 * 3) = 1.8 / 3.0 = 0.6
    - function_0 node imp: sum(abs([0.5])) / (1.0 * 1) = 0.5
    - function_1 node imp: sum(abs([-0.25])) / (1.0 * 1) = 0.25
    - function_2 node imp: sum(abs([0.1])) / (1.0 * 1) = 0.1

    - edge_0 imp: abs(0.5) / 1.0 = 0.5
    - edge_1 imp: abs(-0.75) / 1.0 = 0.75
    """
    data = _build_test_graph()

    node_masks = {
        "taxon": torch.tensor([[-0.2, 0.4, -0.6], [0.8, -1.0, 0.0]], dtype=torch.float32),
        "function": torch.tensor([[0.5], [-0.25], [0.1]], dtype=torch.float32),
    }
    edge_masks = {
        ("taxon", "has_capacity", "function"): torch.tensor([0.5, -0.75], dtype=torch.float32),
    }

    norm_factor = compute_norm_factor(node_masks, edge_masks)
    assert norm_factor == 1.0

    # 1. Nodos
    nodes = compute_node_importance(
        data,
        node_masks,
        norm_factor,
        node_mask_type="attributes",
        is_synthetic=True,
    )
    node_map = {(n.node_type, n.node_id): n.importance for n in nodes}

    assert node_map[("taxon", "taxon_0")] == pytest.approx(0.4, abs=1e-5)
    assert node_map[("taxon", "taxon_1")] == pytest.approx(0.6, abs=1e-5)
    assert node_map[("function", "function_0")] == pytest.approx(0.5, abs=1e-5)
    assert node_map[("function", "function_1")] == pytest.approx(0.25, abs=1e-5)
    assert node_map[("function", "function_2")] == pytest.approx(0.1, abs=1e-5)

    # 2. Atributos
    attributes = compute_attribute_importance(
        data,
        node_masks,
        norm_factor,
        feature_names_map={
            "taxon": ["f0", "f1", "f2"],
            "function": ["m0"],
        },
        is_synthetic=True,
    )
    attr_map = {(a.node_type, a.node_id, a.attribute): a.importance for a in attributes}

    # Taxon 0
    assert attr_map[("taxon", "taxon_0", "f0")] == pytest.approx(0.2, abs=1e-5)
    assert attr_map[("taxon", "taxon_0", "f1")] == pytest.approx(0.4, abs=1e-5)
    assert attr_map[("taxon", "taxon_0", "f2")] == pytest.approx(0.6, abs=1e-5)
    # Taxon 1
    assert attr_map[("taxon", "taxon_1", "f0")] == pytest.approx(0.8, abs=1e-5)
    assert attr_map[("taxon", "taxon_1", "f1")] == pytest.approx(1.0, abs=1e-5)
    assert attr_map[("taxon", "taxon_1", "f2")] == pytest.approx(0.0, abs=1e-5)
    # Functions
    assert attr_map[("function", "function_0", "m0")] == pytest.approx(0.5, abs=1e-5)
    assert attr_map[("function", "function_1", "m0")] == pytest.approx(0.25, abs=1e-5)
    assert attr_map[("function", "function_2", "m0")] == pytest.approx(0.1, abs=1e-5)

    # 3. Aristas
    edges = compute_edge_importance(
        data,
        nodes,
        edge_masks,
        norm_factor,
        is_synthetic=True,
    )
    assert len(edges) == 2
    assert edges[0].source_id == "taxon_0"
    assert edges[0].target_id == "function_1"
    assert edges[0].relation_type == "has_capacity"
    assert edges[0].importance == pytest.approx(0.5, abs=1e-5)

    assert edges[1].source_id == "taxon_1"
    assert edges[1].target_id == "function_2"
    assert edges[1].relation_type == "has_capacity"
    assert edges[1].importance == pytest.approx(0.75, abs=1e-5)


# ---------------------------------------------------------------------------
# 2. Identificación explícita de tipos, índices y valores
# ---------------------------------------------------------------------------


def test_outputs_identify_node_type_relation_and_index() -> None:
    """Verifica que las salidas preservan node_type, relation_type, source/target y valores."""
    data = _build_test_graph()
    node_masks = {"taxon": torch.tensor([[0.5, 0.5, 0.5], [1.0, 1.0, 1.0]])}
    edge_masks = {("taxon", "has_capacity", "function"): torch.tensor([0.4, 0.8])}

    norm_factor = compute_norm_factor(node_masks, edge_masks)
    nodes = compute_node_importance(data, node_masks, norm_factor, node_mask_type="attributes")
    attrs = compute_attribute_importance(data, node_masks, norm_factor)
    edges = compute_edge_importance(data, nodes, edge_masks, norm_factor)

    for n in nodes:
        assert isinstance(n.node_type, str) and len(n.node_type) > 0
        assert isinstance(n.node_id, str) and len(n.node_id) > 0
        assert isinstance(n.importance, float)

    for a in attrs:
        assert isinstance(a.node_type, str) and len(a.node_type) > 0
        assert isinstance(a.node_id, str) and len(a.node_id) > 0
        assert isinstance(a.attribute, str) and len(a.attribute) > 0
        assert isinstance(a.importance, float)

    for e in edges:
        assert e.source_type == "taxon"
        assert e.relation_type == "has_capacity"
        assert e.target_type == "function"
        assert e.source_id in ["taxon_0", "taxon_1"]
        assert e.target_id in ["function_0", "function_1", "function_2"]
        assert isinstance(e.importance, float)


# ---------------------------------------------------------------------------
# 3. Determinismo
# ---------------------------------------------------------------------------


def test_determinism() -> None:
    """Verifica que múltiples ejecuciones con idénticos inputs producen salidas idénticas."""
    data = _build_test_graph()
    node_masks = {
        "taxon": torch.tensor([[0.123, -0.456, 0.789], [-0.321, 0.654, -0.987]]),
    }
    edge_masks = {
        ("taxon", "has_capacity", "function"): torch.tensor([0.444, -0.888]),
    }

    norm1 = compute_norm_factor(node_masks, edge_masks)
    norm2 = compute_norm_factor(node_masks, edge_masks)
    assert norm1 == norm2

    nodes1 = compute_node_importance(data, node_masks, norm1, node_mask_type="attributes")
    nodes2 = compute_node_importance(data, node_masks, norm2, node_mask_type="attributes")
    assert [n.model_dump() for n in nodes1] == [n.model_dump() for n in nodes2]

    attrs1 = compute_attribute_importance(data, node_masks, norm1)
    attrs2 = compute_attribute_importance(data, node_masks, norm2)
    assert [a.model_dump() for a in attrs1] == [a.model_dump() for a in attrs2]

    edges1 = compute_edge_importance(data, nodes1, edge_masks, norm1)
    edges2 = compute_edge_importance(data, nodes2, edge_masks, norm2)
    assert [e.model_dump() for e in edges1] == [e.model_dump() for e in edges2]


# ---------------------------------------------------------------------------
# 4. Manejo de tipos ausentes (EXP-05)
# ---------------------------------------------------------------------------


def test_absent_types_handled_gracefully() -> None:
    """Un tipo de nodo o relación sin máscara debe figurar con importancia 0.0 (EXP-05)."""
    data = _build_test_graph()
    # Solo máscara para taxon, ninguna para function
    node_masks = {"taxon": torch.tensor([[0.5, 0.5, 0.5], [1.0, 1.0, 1.0]])}
    # Ninguna máscara de arista
    edge_masks: dict = {}

    norm_factor = compute_norm_factor(node_masks, edge_masks)
    nodes = compute_node_importance(data, node_masks, norm_factor, node_mask_type="attributes")

    # Funciones deben aparecer con importancia 0.0
    function_nodes = [n for n in nodes if n.node_type == "function"]
    assert len(function_nodes) == 3
    for n in function_nodes:
        assert n.importance == 0.0

    # Aristas sin máscara deben figurar con importancia 0.0
    edges = compute_edge_importance(data, nodes, edge_masks, norm_factor)
    assert len(edges) == 2
    for e in edges:
        assert e.importance == 0.0


# ---------------------------------------------------------------------------
# 5. Valores absolutos y rango [0.0, 1.0]
# ---------------------------------------------------------------------------


def test_values_are_absolute_and_bounded() -> None:
    """Verifica que ningún valor sea negativo y todos queden estrictamente en [0.0, 1.0]."""
    data = _build_test_graph()
    # Valores con magnitudes extremas y signos negativos
    node_masks = {
        "taxon": torch.tensor([[-500.0, -1000.0, -10.0], [200.0, -1000.0, 0.0]]),
    }
    edge_masks = {
        ("taxon", "has_capacity", "function"): torch.tensor([-1000.0, 500.0]),
    }

    norm_factor = compute_norm_factor(node_masks, edge_masks)
    assert norm_factor == 1000.0

    nodes = compute_node_importance(data, node_masks, norm_factor, node_mask_type="attributes")
    attrs = compute_attribute_importance(data, node_masks, norm_factor)
    edges = compute_edge_importance(data, nodes, edge_masks, norm_factor)

    for n in nodes:
        assert 0.0 <= n.importance <= 1.0
    for a in attrs:
        assert 0.0 <= a.importance <= 1.0
    for e in edges:
        assert 0.0 <= e.importance <= 1.0


# ---------------------------------------------------------------------------
# 6. Integración con contrato A55-P3 (validate_explanation)
# ---------------------------------------------------------------------------


def test_contract_validation_with_aggregated_outputs() -> None:
    """Verifica que las salidas ensambladas en una Explanation pasen validate_explanation."""
    data = _build_test_graph()
    node_masks = {
        "taxon": torch.tensor([[0.2, 0.4, 0.6], [0.8, 1.0, 0.0]]),
        "function": torch.tensor([[0.5], [0.2], [0.1]]),
    }
    edge_masks = {
        ("taxon", "has_capacity", "function"): torch.tensor([0.7, 0.3]),
    }

    norm_factor = compute_norm_factor(node_masks, edge_masks)
    nodes = compute_node_importance(
        data, node_masks, norm_factor, node_mask_type="attributes", is_synthetic=True
    )
    attrs = compute_attribute_importance(data, node_masks, norm_factor, is_synthetic=True)
    edges = compute_edge_importance(data, nodes, edge_masks, norm_factor, is_synthetic=True)

    payload = {
        "format": EXPLANATION_FORMAT,
        "format_version": EXPLANATION_FORMAT_VERSION,
        "created_at": "2026-10-28T18:00:00Z",
        "run": RunRef(
            run_id="run_test",
            run_json="runs/run_test/run.json",
            format_version="1.0.0",
            variant="hetero_sage",
            seed=42,
            dataset_id="synthetic-v1",
            split=SplitRef(version="synthetic", sha256="0" * 64),
            git_commit=None,
        ).model_dump(),
        "explainer": ExplainerRef(
            name="GNNExplainer",
            library="torch_geometric",
            library_version="2.8.1",
            algorithm="torch_geometric.explain.algorithm.GNNExplainer",
            explanation_type="model",
            node_mask_type="attributes",
            edge_mask_type="object",
            seed=42,
            config={"epochs": 10},
            uses_attention=False,
        ).model_dump(),
        "target": TargetRef(
            graph_id="synthetic:test_graph_001",
            sample_id=None,
            is_synthetic=True,
            output="butyrate",
            output_index=0,
            unit="mmol/L",
            model_output=1.2345,
        ).model_dump(),
        "importance": Importance(
            scale=Scale(
                kind="normalized",
                range=(0.0, 1.0),
                normalization="max_abs",
                aggregation="sum_over_feature_mask",
            ),
            nodes=nodes,
            attributes=attrs,
            edges=edges,
        ).model_dump(),
        "subgraph": Subgraph(
            k=2,
            selection="top_k_edges_by_importance",
            tie_break="lexicographic_edge_key",
            nodes=[
                {"node_type": "taxon", "node_id": "taxon_0"},
                {"node_type": "function", "node_id": "function_1"},
                {"node_type": "taxon", "node_id": "taxon_1"},
                {"node_type": "function", "node_id": "function_2"},
            ],
            edges=[
                {
                    "source_type": "taxon",
                    "relation_type": "has_capacity",
                    "target_type": "function",
                    "source_id": "taxon_0",
                    "target_id": "function_1",
                },
                {
                    "source_type": "taxon",
                    "relation_type": "has_capacity",
                    "target_type": "function",
                    "source_id": "taxon_1",
                    "target_id": "function_2",
                },
            ],
        ).model_dump(),
        "warnings": [
            {
                "code": "association_not_causation",
                "message": "La importancia calculada refleja asociacion dentro del modelo.",
            },
            {
                "code": "importance_is_not_evidence",
                "message": "La importancia es del modelo; la evidencia del grafo.",
            },
            {
                "code": "synthetic_data",
                "message": "Instancia sintetica.",
            },
        ],
    }

    explanation = validate_explanation(payload)
    assert isinstance(explanation, Explanation)
    assert len(explanation.importance.nodes) == 5
    assert len(explanation.importance.edges) == 2


def test_edge_without_declared_evidence_fails_instead_of_inventing_it() -> None:
    data = _build_test_graph()
    store = data["taxon", "has_capacity", "function"]
    del store.evidence_status
    nodes = compute_node_importance(data, {}, 1.0, node_mask_type="attributes")

    with pytest.raises(ValueError, match="no declara evidence_status"):
        compute_edge_importance(data, nodes, {}, 1.0, is_synthetic=True)


def test_edge_pointing_to_a_missing_node_fails() -> None:
    data = _build_test_graph()
    data["taxon", "has_capacity", "function"].edge_index = torch.tensor([[0, 1], [1, 5]])
    nodes = compute_node_importance(data, {}, 1.0, node_mask_type="attributes")

    with pytest.raises(ValueError, match="nodos inexistentes"):
        compute_edge_importance(data, nodes, {}, 1.0)
