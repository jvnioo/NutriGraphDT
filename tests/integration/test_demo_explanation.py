"""Visualizador de explicabilidad (A104, #334): contrato, importancias, subgrafo y textos.

Usa la corrida sintética congelada y `AppTest`, sin navegador ni red. Requiere los extras
`graph`, `baselines` y `demo`.
"""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")
pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from streamlit.testing.v1 import AppTest  # noqa: E402

from nutrigraphdt import api  # noqa: E402
from nutrigraphdt.demo import explanation as explain  # noqa: E402
from nutrigraphdt.demo import graph_viewer as viewer  # noqa: E402
from nutrigraphdt.explainability import validate_explanation  # noqa: E402
from nutrigraphdt.simulation import scenario_by_id  # noqa: E402

TIMEOUT = 300


@pytest.fixture(scope="module")
def engine() -> Any:
    return api.DEMO_RUNS["synthetic"].engine()


@pytest.fixture(scope="module")
def request_() -> api.ScenarioRequest:
    return scenario_by_id("crude-protein-270").request()


@pytest.fixture(scope="module")
def result(engine: Any, request_: api.ScenarioRequest) -> explain.ScenarioExplanation:
    return explain.explain_scenario(engine, request_)


def test_explanation_meets_the_contract(result: explain.ScenarioExplanation, engine: Any) -> None:
    explanation = result.explanation
    again = validate_explanation(explanation.model_dump(mode="json"))
    assert again == explanation
    assert explanation.target.is_synthetic
    assert explanation.target.output == "log_total"
    assert explanation.run.run_id == engine.model_ref.run_id
    assert explanation.run.dataset_id == "synthetic_cohort"


def test_explanation_uses_the_scenario_instance(
    result: explain.ScenarioExplanation, request_: api.ScenarioRequest
) -> None:
    assert result.explanation.target.sample_id == request_.base_instance
    assert result.explanation.target.graph_id.startswith("synthetic:scenario:")


def test_homo_sage_explains_nodes_and_attributes(result: explain.ScenarioExplanation) -> None:
    importance = result.explanation.importance
    assert importance.nodes and importance.attributes
    assert not importance.edges
    assert {a.attribute for a in importance.attributes if a.node_type == "diet"} >= {
        "composition.crude_protein (g_kg)"
    }


def test_importance_by_type_sums_the_node_importances(
    result: explain.ScenarioExplanation,
) -> None:
    total = sum(n.importance for n in result.explanation.importance.nodes)
    assert sum(r["importancia total"] for r in result.by_node_type) == pytest.approx(total)
    assert len(result.top_nodes) == explain.DEFAULT_TOP_K


def test_explanation_is_deterministic_for_a_seed(
    engine: Any, request_: api.ScenarioRequest, result: explain.ScenarioExplanation
) -> None:
    again = explain.explain_scenario(engine, request_)
    assert again.explanation.importance == result.explanation.importance


def test_subgraph_has_the_top_nodes_and_graph_edges(
    engine: Any, request_: api.ScenarioRequest, result: explain.ScenarioExplanation
) -> None:
    records = viewer.scenario_graph(engine, request_)
    sub = explain.subgraph_records(records, result)
    keep = {(n["tipo"], n["nodo"]) for n in result.top_nodes}
    assert {(n["node_type"], n["node_id"]) for n in sub.nodes} == keep
    for edge in sub.edges:
        assert (edge["source_type"], edge["source_id"]) in keep
        assert (edge["target_type"], edge["target_id"]) in keep


def test_unknown_target_is_rejected(engine: Any, request_: api.ScenarioRequest) -> None:
    with pytest.raises(ValueError, match="no es una salida"):
        explain.explain_scenario(engine, request_, target="butyrate")


def _page() -> None:
    from nutrigraphdt.demo.pages import explanation

    explanation.render()


def test_page_shows_warnings_next_to_the_explanation() -> None:
    at = AppTest.from_function(_page, default_timeout=TIMEOUT)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    warnings = " ".join(w.value for w in at.warning)
    for text in explain.INTERPRETATION:
        assert text in warnings
    assert any("GNNExplainer" in c.value and " s " in c.value for c in at.caption)
    assert any("no disponible" in c.value for c in at.caption)
    assert at.dataframe

    at.selectbox(key="ng_explain_target").set_value("log_propionate_acetate").run()
    assert not at.exception
