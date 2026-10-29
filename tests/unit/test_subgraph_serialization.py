"""Pruebas unitarias de extracción y serialización del subgrafo explicativo top-k (A60-P3, #169).

Verifica:
1. Validación de k inválido (k < 1, tipos no enteros).
2. Selección top-k determinista con conservación exacta de extremos (EXP-07).
3. Política documentada de desempate lexicográfico ante idéntica importancia.
4. Política de relaciones inversas (inclusión por omisión y filtrado opcional).
5. Casos límite (k mayor que número de aristas, aristas vacías).
6. Serialización y deserialización JSON de ida y vuelta (round-trip) de Explanation.
7. Generación y serialización de la vista enriquecida ExplanatorySubgraphView (sin datos crudos).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nutrigraphdt.explainability.contract import (
    EdgeImportance,
    Evidence,
    Subgraph,
    validate_explanation,
)
from nutrigraphdt.explainability.subgraph import (
    DEFAULT_SELECTION,
    DEFAULT_TIE_BREAK,
    FORWARD_ONLY_SELECTION,
    ExplanatorySubgraphView,
    extract_subgraph_view,
    extract_top_k_subgraph,
    load_explanation,
    load_subgraph_view,
    serialize_explanation,
    serialize_subgraph_view,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_PATH = REPO_ROOT / "docs" / "models" / "examples" / "explanation-synthetic.json"


def _sample_edges() -> list[EdgeImportance]:
    """Crea una lista de aristas de prueba con importancias y evidencias variadas."""
    return [
        EdgeImportance(
            source_type="diet",
            relation_type="provides",
            target_type="substrate",
            source_id="synthetic:diet:0001",
            target_id="synthetic:substrate:0003",
            importance=0.29,
            evidence=Evidence(
                evidence_status="synthetic",
                evidence_method="synthetic_generator",
                evidence_source=None,
            ),
        ),
        EdgeImportance(
            source_type="substrate",
            relation_type="available_to",
            target_type="taxon",
            source_id="synthetic:substrate:0003",
            target_id="synthetic:taxon:0001",
            importance=0.47,
            evidence=Evidence(
                evidence_status="synthetic",
                evidence_method="synthetic_generator",
                evidence_source=None,
            ),
        ),
        EdgeImportance(
            source_type="taxon",
            relation_type="has_capacity",
            target_type="function",
            source_id="synthetic:taxon:0001",
            target_id="synthetic:function:0002",
            importance=0.81,
            evidence=Evidence(
                evidence_status="synthetic",
                evidence_method="synthetic_generator",
                evidence_source=None,
            ),
        ),
        EdgeImportance(
            source_type="function",
            relation_type="produces",
            target_type="metabolite",
            source_id="synthetic:function:0002",
            target_id="synthetic:metabolite:0003",
            importance=1.00,
            evidence=Evidence(
                evidence_status="synthetic",
                evidence_method="synthetic_generator",
                evidence_source=None,
            ),
        ),
        EdgeImportance(
            source_type="metabolite",
            relation_type="rev_produces",
            target_type="function",
            source_id="synthetic:metabolite:0003",
            target_id="synthetic:function:0002",
            importance=0.95,
            evidence=None,  # Relación inversa no lleva evidencia
        ),
    ]


# ---------------------------------------------------------------------------
# 1. Validación de k inválido
# ---------------------------------------------------------------------------


def test_invalid_k_raises_error() -> None:
    edges = _sample_edges()
    with pytest.raises(ValueError, match="k debe ser un entero mayor o igual a 1"):
        extract_top_k_subgraph(edges, k=0)

    with pytest.raises(ValueError, match="k debe ser un entero mayor o igual a 1"):
        extract_top_k_subgraph(edges, k=-3)

    with pytest.raises(TypeError, match="k debe ser un entero"):
        extract_top_k_subgraph(edges, k="2")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="k debe ser un entero"):
        extract_top_k_subgraph(edges, k=True)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 2. Selección top-k determinista y conservación de extremos
# ---------------------------------------------------------------------------


def test_subgraph_top_k_selection_and_endpoints() -> None:
    edges = _sample_edges()
    # Con k=2 y filter_reverse=False, las aristas de mayor importancia son:
    # 1. function -> produces -> metabolite (1.00)
    # 2. metabolite -> rev_produces -> function (0.95)
    subgraph = extract_top_k_subgraph(edges, k=2)

    assert isinstance(subgraph, Subgraph)
    assert subgraph.k == 2
    assert len(subgraph.edges) == 2
    assert subgraph.selection == DEFAULT_SELECTION
    assert subgraph.tie_break == DEFAULT_TIE_BREAK

    assert subgraph.edges[0].source_id == "synthetic:function:0002"
    assert subgraph.edges[0].target_id == "synthetic:metabolite:0003"
    assert subgraph.edges[1].source_id == "synthetic:metabolite:0003"
    assert subgraph.edges[1].target_id == "synthetic:function:0002"

    # Extremos exactos: { (function, ...:0002), (metabolite, ...:0003) }
    endpoints = {(e.source_type, e.source_id) for e in subgraph.edges} | {
        (e.target_type, e.target_id) for e in subgraph.edges
    }
    node_set = {(n.node_type, n.node_id) for n in subgraph.nodes}
    assert endpoints == node_set
    assert len(subgraph.nodes) == 2


def test_determinism_same_output() -> None:
    edges = _sample_edges()
    sub1 = extract_top_k_subgraph(edges, k=3)
    sub2 = extract_top_k_subgraph(edges, k=3)
    assert sub1.model_dump() == sub2.model_dump()


# ---------------------------------------------------------------------------
# 3. Política de desempates (tie-breaking)
# ---------------------------------------------------------------------------


def test_tie_breaking_policy_lexicographic() -> None:
    """Verifica que a igual importancia, se desempata lexicográficamente por clave de arista."""
    # Ambas aristas tienen importancia idéntica = 0.50
    edge_a = EdgeImportance(
        source_type="taxon",
        relation_type="has_capacity",
        target_type="function",
        source_id="synthetic:taxon:0001",
        target_id="synthetic:function:0002",
        importance=0.50,
        evidence=None,
    )
    edge_b = EdgeImportance(
        source_type="diet",
        relation_type="provides",
        target_type="substrate",
        source_id="synthetic:diet:0001",
        target_id="synthetic:substrate:0003",
        importance=0.50,
        evidence=None,
    )

    # Clave de edge_a: ('taxon', 'has_capacity', 'function', ...)
    # Clave de edge_b: ('diet', 'provides', 'substrate', ...)
    # Lexicográficamente 'diet' < 'taxon', por lo que edge_b debe rankear primero
    subgraph = extract_top_k_subgraph([edge_a, edge_b], k=1)
    assert len(subgraph.edges) == 1
    assert subgraph.edges[0].source_type == "diet"
    assert subgraph.edges[0].relation_type == "provides"


# ---------------------------------------------------------------------------
# 4. Política de relaciones inversas
# ---------------------------------------------------------------------------


def test_reverse_relations_policy() -> None:
    """Verifica el comportamiento de relaciones inversas con filter_reverse."""
    edges = _sample_edges()

    # 1. Por omisión: incluye reversas
    sub_all = extract_top_k_subgraph(edges, k=2, filter_reverse=False)
    rel_types_all = [e.relation_type for e in sub_all.edges]
    assert "rev_produces" in rel_types_all
    assert sub_all.selection == DEFAULT_SELECTION

    # 2. Con filter_reverse=True: omite reversas
    sub_forward = extract_top_k_subgraph(edges, k=2, filter_reverse=True)
    rel_types_forward = [e.relation_type for e in sub_forward.edges]
    assert "rev_produces" not in rel_types_forward
    # Aristas directas de mayor importancia: produces (1.00) y has_capacity (0.81)
    assert rel_types_forward == ["produces", "has_capacity"]
    assert sub_forward.selection == FORWARD_ONLY_SELECTION


# ---------------------------------------------------------------------------
# 5. Casos límite
# ---------------------------------------------------------------------------


def test_k_greater_than_edge_count() -> None:
    edges = _sample_edges()[:2]
    subgraph = extract_top_k_subgraph(edges, k=10)
    assert subgraph.k == 10
    assert len(subgraph.edges) == 2


def test_empty_edges_list() -> None:
    subgraph = extract_top_k_subgraph([], k=5)
    assert subgraph.k == 5
    assert len(subgraph.edges) == 0
    assert len(subgraph.nodes) == 0


# ---------------------------------------------------------------------------
# 6. Serialización y deserialización JSON de Explanation (Round-trip)
# ---------------------------------------------------------------------------


def test_roundtrip_explanation_serialization(tmp_path: Path) -> None:
    """Verifica que una Explanation serializada a JSON se recupere idéntica y válida."""
    raw_data = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    explanation = validate_explanation(raw_data)

    out_file = tmp_path / "explanation.json"
    json_text = serialize_explanation(explanation, path=out_file)

    assert out_file.exists()
    assert json_text == out_file.read_text(encoding="utf-8")

    # Carga desde archivo
    loaded_from_file = load_explanation(out_file)
    assert loaded_from_file.model_dump() == explanation.model_dump()

    # Carga desde cadena
    loaded_from_str = load_explanation(json_text)
    assert loaded_from_str.model_dump() == explanation.model_dump()

    # Verificación de ausencia de campos crudos
    for forbidden in ("raw_attributes", '"x"', "/home/", "C:\\\\"):
        assert forbidden not in json_text


# ---------------------------------------------------------------------------
# 7. Generación y serialización de ExplanatorySubgraphView
# ---------------------------------------------------------------------------


def test_subgraph_view_extraction_and_roundtrip(tmp_path: Path) -> None:
    """Verifica la vista enriquecida del subgrafo para interfaces web y reportes."""
    raw_data = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    explanation = validate_explanation(raw_data)

    view = extract_subgraph_view(explanation)
    assert isinstance(view, ExplanatorySubgraphView)
    assert view.k == explanation.subgraph.k
    assert len(view.edges) == len(explanation.subgraph.edges)
    assert len(view.nodes) == len(explanation.subgraph.nodes)

    # Cada nodo en la vista tiene su importancia correcta
    sub_node_ids = {n.node_id for n in view.nodes}
    assert len(sub_node_ids) == len(view.nodes)
    for n in view.nodes:
        assert isinstance(n.importance, float)
        assert 0.0 <= n.importance <= 1.0

    # Cada arista en la vista tiene su importancia y evidencia
    for e in view.edges:
        assert isinstance(e.importance, float)
        assert 0.0 <= e.importance <= 1.0
        if not e.relation_type.startswith("rev_"):
            assert e.evidence is not None

    # Serialización y roundtrip de la vista
    view_file = tmp_path / "subgraph_view.json"
    view_json = serialize_subgraph_view(view, path=view_file)

    loaded_view = load_subgraph_view(view_file)
    assert loaded_view.model_dump() == view.model_dump()

    loaded_from_str = load_subgraph_view(view_json)
    assert loaded_from_str.model_dump() == view.model_dump()

    # Comprobación de que no se filtran tensores ni datos crudos
    assert "tensor" not in view_json.lower()
    assert "requires_grad" not in view_json
