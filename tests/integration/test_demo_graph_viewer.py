"""Visualizador del grafo heterogéneo (A97, #320): figura, filtros, leyenda y muestreo.

Usa la corrida sintética congelada y `AppTest`, sin navegador ni red. Requiere los extras
`graph`, `baselines` y `demo`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")
pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from streamlit.testing.v1 import AppTest  # noqa: E402

from nutrigraphdt import api  # noqa: E402
from nutrigraphdt.demo import graph_viewer as viewer  # noqa: E402
from nutrigraphdt.demo import plots  # noqa: E402
from nutrigraphdt.explainability.style import EVIDENCE_STYLES  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE = "synthetic:sample:0017"
TIMEOUT = 300


@pytest.fixture(scope="module")
def records() -> viewer.Records:
    engine = api.DEMO_RUNS["synthetic"].engine()
    request = api.ScenarioRequest(contract_version="1.0.0", base_instance=BASE)
    return viewer.scenario_graph(engine, request)


def _node_traces(figure: Any) -> int:
    return sum(1 for trace in figure.data if trace.mode == "markers+text")


def _edge_statuses(figure: Any) -> set[str]:
    return {trace.meta["evidence_status"] for trace in figure.data if trace.mode == "lines"}


def test_figure_has_every_node_type_of_the_instance(records: viewer.Records) -> None:
    result = viewer.viewer_view(records)
    figure = plots.graph_figure(result.view)
    assert result.view.node_types == viewer.node_types(records)
    assert len(viewer.node_types(records)) == 8
    assert _node_traces(figure) == 8


def test_hypothetical_relations_get_their_own_style(records: viewer.Records) -> None:
    result = viewer.viewer_view(records)
    statuses = _edge_statuses(plots.graph_figure(result.view))
    assert statuses == {"synthetic", "hypothetical"}
    modulates = [e for e in result.view.edges if e["relation"] == "modulates"]
    assert modulates and all(e["style_status"] == "hypothetical" for e in modulates)
    assert all(e["evidence_status"] == "synthetic" for e in modulates)


def test_no_second_style_definition() -> None:
    source = (REPO_ROOT / "src" / "nutrigraphdt" / "demo" / "graph_viewer.py").read_text(
        encoding="utf-8"
    )
    for style in EVIDENCE_STYLES.values():
        assert style.color not in source
    assert "#" not in "".join(line for line in source.splitlines() if "color" in line)


def test_node_type_filter_changes_the_figure(records: viewer.Records) -> None:
    full = plots.graph_figure(viewer.viewer_view(records).view)
    filtered = plots.graph_figure(viewer.viewer_view(records, types=["taxon", "function"]).view)
    assert _node_traces(filtered) == 2 < _node_traces(full)


def test_relation_filter_changes_the_figure(records: viewer.Records) -> None:
    result = viewer.viewer_view(records, relation_types=["has_capacity"])
    assert {e["relation"] for e in result.view.edges} == {"has_capacity"}
    assert "hypothetical" not in _edge_statuses(plots.graph_figure(result.view))


def test_legend_distinguishes_hypothetical_relations(records: viewer.Records) -> None:
    rows = {row["relación"]: row for row in viewer.viewer_view(records).legend}
    hypothetical = rows["additive → modulates → taxon"]
    assert hypothetical["estado estructural"] == "hipotética"
    assert hypothetical["trazo"] == viewer.HYPOTHETICAL_LABEL
    assert all("sintética" in row["evidencia"] for row in rows.values())
    assert "Datos sintéticos" in viewer.SYNTHETIC_LEGEND_NOTE


def _many_taxa(n: int) -> viewer.Records:
    nodes = [
        {
            "graph_id": "g",
            "node_type": "taxon",
            "node_id": f"t{i:03d}",
            "attributes": {"abundance": (i * 7) % 11},
        }
        for i in range(n)
    ] + [{"graph_id": "g", "node_type": "function", "node_id": "f1", "attributes": {}}]
    edges = [
        {
            "graph_id": "g",
            "source_type": "taxon",
            "source_id": f"t{i:03d}",
            "relation_type": "has_capacity",
            "target_type": "function",
            "target_id": "f1",
            "evidence_status": "synthetic",
        }
        for i in range(0, n, 3)
    ]
    return viewer.Records("g", nodes, edges)


def test_taxon_sampling_is_deterministic_and_reports_counts() -> None:
    records = _many_taxa(60)
    first = viewer.viewer_view(records, max_taxa=8)
    second = viewer.viewer_view(records, max_taxa=8)
    assert (first.shown_taxa, first.total_taxa) == (8, 60)
    ids = [n["node_id"] for n in first.view.nodes if n["node_type"] == "taxon"]
    assert ids == [n["node_id"] for n in second.view.nodes if n["node_type"] == "taxon"]
    # Primero los taxones con aristas (los múltiplos de 3).
    assert all(int(i[1:]) % 3 == 0 for i in ids)


def test_scenario_graph_does_not_write_to_disk(
    records: viewer.Records, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    engine = api.DEMO_RUNS["synthetic"].engine()
    request = api.ScenarioRequest(
        contract_version="1.0.0",
        base_instance=BASE,
        intervention=[{"variable": "diet.composition.crude_protein", "value": 270.0}],
    )
    viewer.scenario_graph(engine, request)
    assert list(tmp_path.iterdir()) == []


def _page() -> None:
    from nutrigraphdt.demo.pages import graph

    graph.render()


def test_graph_page_reports_how_many_taxa_it_shows() -> None:
    at = AppTest.from_function(_page, default_timeout=TIMEOUT)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert any("de 10 taxones" in m.value for m in at.markdown)
    assert any("basal" in c.value for c in at.caption)

    at.number_input(key="ng_graph_max_taxa").set_value(3).run()
    assert any("3 de 10 taxones" in m.value for m in at.markdown)

    at.multiselect(key="ng_graph_types").set_value(["diet", "additive"]).run()
    assert not at.exception
    assert not any("taxones" in m.value for m in at.markdown)
