"""Estilo de las aristas del subgrafo explicativo por estado de evidencia (C-03, #243)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nutrigraphdt.explainability.contract import EVIDENCE_METHOD_STATUS
from nutrigraphdt.explainability.style import (
    EVIDENCE_STYLES,
    HYPOTHETICAL_LABEL,
    evidence_legend,
    evidence_style,
)
from nutrigraphdt.explainability.subgraph import (
    ExplanatorySubgraphView,
    extract_subgraph_view,
    load_explanation,
)
from nutrigraphdt.graph.contracts import _ALLOWED_EVIDENCE_STATUSES

EXAMPLE = Path(__file__).resolve().parents[2] / "docs/models/examples/explanation-synthetic.json"


def test_one_style_per_ds01_status() -> None:
    assert set(EVIDENCE_STYLES) == set(_ALLOWED_EVIDENCE_STATUSES)
    assert set(EVIDENCE_METHOD_STATUS.values()) <= set(EVIDENCE_STYLES)
    assert [style.status for style in evidence_legend()] == list(EVIDENCE_STYLES)


def test_states_are_distinguishable_without_color() -> None:
    styles = evidence_legend()
    assert len({style.dash for style in styles}) == len(styles)
    assert len({style.color for style in styles}) == len(styles)
    assert len({style.label for style in styles}) == len(styles)


def test_hypothetical_label() -> None:
    assert HYPOTHETICAL_LABEL == "hipotética: sin respaldo empírico"
    assert evidence_style("hypothetical").label == HYPOTHETICAL_LABEL


def test_unknown_status_is_rejected() -> None:
    with pytest.raises(ValueError, match="DS-01"):
        evidence_style("provisional")


def _view_with_hypothetical() -> ExplanatorySubgraphView:
    view = extract_subgraph_view(load_explanation(EXAMPLE))
    data = view.model_dump()
    # La arista menos importante del top-k pasa a hipotética: no debe ocultarse.
    weakest = min(range(len(data["edges"])), key=lambda i: abs(data["edges"][i]["importance"]))
    data["edges"][weakest]["evidence"] = {
        "evidence_status": "hypothetical",
        "evidence_method": "expert_hypothesis",
        "evidence_source": None,
    }
    return ExplanatorySubgraphView.model_validate(data)


def test_figure_draws_every_edge_with_its_style_and_the_five_state_legend() -> None:
    pytest.importorskip("plotly")
    pytest.importorskip("streamlit")
    pytest.importorskip("torch")
    from nutrigraphdt.demo import plots

    view = _view_with_hypothetical()
    figure = plots.subgraph_figure(view)
    edges = [t for t in figure.data if isinstance(t.meta, dict) and "evidence_status" in t.meta]
    assert len(edges) == len(view.edges)
    for trace, edge in zip(edges, view.edges, strict=True):
        style = evidence_style(edge.evidence.evidence_status)
        assert trace.meta["evidence_status"] == style.status
        assert (trace.line.dash, trace.line.color) == (style.dash, style.color)
    assert any(t.meta["evidence_status"] == "hypothetical" for t in edges)

    legend = [t.name for t in figure.data if t.showlegend is not False and t.name]
    assert legend == [style.label for style in evidence_legend()]
    json.loads(figure.to_json())  # serializable para Streamlit


def test_demo_page_renders_the_example() -> None:
    pytest.importorskip("plotly")
    pytest.importorskip("streamlit")
    pytest.importorskip("torch")
    from streamlit.testing.v1 import AppTest

    def app() -> None:
        from nutrigraphdt.demo.pages import explanation

        explanation.render()

    page = AppTest.from_function(app, default_timeout=60).run()
    assert not page.exception and not page.error
    assert {w.value.split(".**")[0].strip("*") for w in page.warning} >= {
        "association_not_causation",
        "importance_is_not_evidence",
    }
