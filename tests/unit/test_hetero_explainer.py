"""Tests del wrapper de explicadores para HeteroData (A60-P1, #170)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import torch

from nutrigraphdt.data.synthetic import generate_synthetic_dataset
from nutrigraphdt.explainability import (
    EXPLANATION_FORMAT_VERSION,
    HeteroExplainer,
    IncompatibleExplainerError,
    RunRef,
    SplitRef,
    validate_explanation,
)
from nutrigraphdt.graph.heterodata import build_synthetic_graphs
from nutrigraphdt.models.gnn.base import GraphMetadata
from nutrigraphdt.models.gnn.factory import build_model, load_model_config

pytest.importorskip("torch_geometric")

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def synthetic_graph_and_metadata() -> tuple[Any, GraphMetadata]:
    torch.manual_seed(170)
    dataset = generate_synthetic_dataset()
    graphs = build_synthetic_graphs(dataset).graphs
    data = graphs[dataset.instances[0].graph_id]
    metadata = GraphMetadata.from_graphs([data])
    return data, metadata


def _build_test_model(variant: str, metadata: GraphMetadata):
    config = load_model_config(REPO_ROOT / "configs" / "models" / f"{variant}.yaml")
    return build_model(config, metadata).eval()


def test_hetero_sage_gnn_explainer_produces_valid_contract_output(
    synthetic_graph_and_metadata: tuple[Any, GraphMetadata],
) -> None:
    data, metadata = synthetic_graph_and_metadata
    model = _build_test_model("hetero_sage", metadata)

    explainer = HeteroExplainer(
        model,
        algorithm="gnn_explainer",
        epochs=3,
        seed=42,
        top_k=4,
    )
    explanation = explainer.explain(data, target="butyrate")

    assert explanation.format_version == EXPLANATION_FORMAT_VERSION
    assert explanation.target.output == "butyrate"
    assert explanation.target.is_synthetic is True
    assert explanation.explainer.name == "GNNExplainer"
    assert explanation.explainer.uses_attention is False

    # Valida conforme a A55-P3
    validated = validate_explanation(explanation.model_dump())
    assert validated.format == "nutrigraphdt-explanation"

    # Nodos, atributos y aristas presentes y normalizados
    assert len(explanation.importance.nodes) > 0
    assert len(explanation.importance.attributes) > 0
    assert len(explanation.importance.edges) > 0
    for node in explanation.importance.nodes:
        assert 0.0 <= node.importance <= 1.0
    for attr in explanation.importance.attributes:
        assert 0.0 <= attr.importance <= 1.0
    for edge in explanation.importance.edges:
        assert 0.0 <= edge.importance <= 1.0

    # Subgrafo top-k
    assert explanation.subgraph.k == 4
    assert len(explanation.subgraph.edges) <= 4
    sub_endpoints = {(e.source_type, e.source_id) for e in explanation.subgraph.edges} | {
        (e.target_type, e.target_id) for e in explanation.subgraph.edges
    }
    assert {(n.node_type, n.node_id) for n in explanation.subgraph.nodes} == sub_endpoints

    # Advertencias obligatorias y de datos sintéticos
    codes = {w.code for w in explanation.warnings}
    assert {"association_not_causation", "importance_is_not_evidence", "synthetic_data"} <= codes
    assert "attention_is_not_explanation" not in codes


def test_hetero_gat_gnn_explainer_produces_valid_output(
    synthetic_graph_and_metadata: tuple[Any, GraphMetadata],
) -> None:
    data, metadata = synthetic_graph_and_metadata
    model = _build_test_model("hetero_gat", metadata)

    explainer = HeteroExplainer(
        model,
        algorithm="gnn_explainer",
        epochs=3,
        seed=42,
        top_k=3,
    )
    explanation = explainer.explain(data, target=0)

    assert explanation.target.output_index == 0
    validated = validate_explanation(explanation.model_dump())
    assert validated.format_version == EXPLANATION_FORMAT_VERSION


def test_hetero_gat_attention_explainer_sets_attention_warning(
    synthetic_graph_and_metadata: tuple[Any, GraphMetadata],
) -> None:
    data, metadata = synthetic_graph_and_metadata
    model = _build_test_model("hetero_gat", metadata)

    explainer = HeteroExplainer(model, algorithm="attention", seed=42)
    explanation = explainer.explain(data, target="butyrate")

    assert explanation.explainer.uses_attention is True
    codes = {w.code for w in explanation.warnings}
    assert "attention_is_not_explanation" in codes
    validate_explanation(explanation.model_dump())


def test_homo_sage_with_edge_masks_fails_explicitly(
    synthetic_graph_and_metadata: tuple[Any, GraphMetadata],
) -> None:
    data, metadata = synthetic_graph_and_metadata
    model = _build_test_model("homo_sage", metadata)

    explainer = HeteroExplainer(model, algorithm="gnn_explainer", edge_mask_type="object", epochs=2)
    with pytest.raises(IncompatibleExplainerError) as exc_info:
        explainer.explain(data, target="butyrate")

    assert "homo_sage" in str(exc_info.value)
    assert "reach=0" in str(exc_info.value)


def test_homo_sage_with_only_node_and_attribute_masks_succeeds(
    synthetic_graph_and_metadata: tuple[Any, GraphMetadata],
) -> None:
    data, metadata = synthetic_graph_and_metadata
    model = _build_test_model("homo_sage", metadata)

    explainer = HeteroExplainer(
        model,
        algorithm="gnn_explainer",
        node_mask_type="attributes",
        edge_mask_type=None,
        epochs=2,
    )
    explanation = explainer.explain(data, target="butyrate")

    assert len(explanation.importance.nodes) > 0
    assert len(explanation.importance.attributes) > 0
    assert len(explanation.importance.edges) == 0
    validate_explanation(explanation.model_dump())


def test_attention_explainer_on_hetero_sage_fails_explicitly(
    synthetic_graph_and_metadata: tuple[Any, GraphMetadata],
) -> None:
    data, metadata = synthetic_graph_and_metadata
    model = _build_test_model("hetero_sage", metadata)

    explainer = HeteroExplainer(model, algorithm="attention")
    with pytest.raises(IncompatibleExplainerError) as exc_info:
        explainer.explain(data, target="butyrate")

    assert "AttentionExplainer requiere un modelo con capas de atención" in str(exc_info.value)


def test_target_resolution_and_validation(
    synthetic_graph_and_metadata: tuple[Any, GraphMetadata],
) -> None:
    data, metadata = synthetic_graph_and_metadata
    model = _build_test_model("hetero_sage", metadata)

    explainer = HeteroExplainer(model, epochs=1)

    with pytest.raises(ValueError, match="Target 'inexistente' no encontrado"):
        explainer.explain(data, target="inexistente")

    with pytest.raises(ValueError, match="fuera de rango"):
        explainer.explain(data, target=99)


def test_custom_run_ref_preserved(
    synthetic_graph_and_metadata: tuple[Any, GraphMetadata],
) -> None:
    data, metadata = synthetic_graph_and_metadata
    model = _build_test_model("hetero_sage", metadata)

    custom_run = RunRef(
        run_id="20261028-120000_hetero_sage_s170",
        run_json="runs/20261028-120000_hetero_sage_s170/run.json",
        format_version="1.0.0",
        variant="hetero_sage",
        seed=170,
        dataset_id="synthetic-v1",
        split=SplitRef(version="synthetic", sha256="a" * 64),
        git_commit="b" * 40,
    )

    explainer = HeteroExplainer(model, run=custom_run, epochs=1)
    explanation = explainer.explain(data, target="butyrate")

    assert explanation.run.run_id == "20261028-120000_hetero_sage_s170"
    assert explanation.run.git_commit == "b" * 40
    validate_explanation(explanation.model_dump())


def test_unknown_algorithm_fails_explicitly(
    synthetic_graph_and_metadata: tuple[Any, GraphMetadata],
) -> None:
    data, metadata = synthetic_graph_and_metadata
    model = _build_test_model("hetero_sage", metadata)

    with pytest.raises(IncompatibleExplainerError, match="Algoritmo desconocido"):
        HeteroExplainer(model, algorithm="inexistente_algorithm").explain(data)
