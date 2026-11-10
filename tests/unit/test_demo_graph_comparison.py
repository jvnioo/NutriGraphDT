"""Comparación del grafo sintético con el reconstruido con datos reales de D1."""

from __future__ import annotations

import pytest

pytest.importorskip("plotly")
pytest.importorskip("torch_geometric")

from nutrigraphdt.demo import data, graph_comparison, plots  # noqa: E402


@pytest.fixture(scope="module")
def counts():  # type: ignore[no-untyped-def]
    synthetic = data.synthetic_scenarios()
    real = data.d1_records(prefer_full=False).records
    return (
        graph_comparison.instance_counts(synthetic, data.graph_ids(synthetic)[0]),
        graph_comparison.instance_counts(real, data.graph_ids(real)[0]),
    )


def test_the_synthetic_graph_has_every_relation_and_d1_only_three(counts) -> None:  # type: ignore[no-untyped-def]
    (_, synthetic_edges), (_, real_edges) = counts

    rows = graph_comparison.relation_rows(synthetic_edges, real_edges)

    assert len(rows) == 11
    assert all(row["sintético"] > 0 for row in rows)
    present = {row["relación"] for row in rows if row["estado"] == graph_comparison.PRESENT}
    assert present == {"measured_in", "has_capacity", "produces"}
    limited = {row["relación"] for row in rows if row["estado"] == graph_comparison.LIMITATION}
    assert limited == {"provides", "available_to"}


def test_node_rows_follow_the_schema(counts) -> None:  # type: ignore[no-untyped-def]
    (synthetic_nodes, _), (real_nodes, _) = counts

    rows = graph_comparison.node_rows(synthetic_nodes, real_nodes)

    assert [row["tipo"] for row in rows][:2] == ["diet", "additive"]
    assert all(row["sintético"] > 0 for row in rows)
    assert {row["tipo"] for row in rows if row["D1"] == 0} == {"additive", "substrate", "phenotype"}


def test_both_schema_figures_build(counts) -> None:  # type: ignore[no-untyped-def]
    (synthetic_nodes, synthetic_edges), (real_nodes, real_edges) = counts
    rows = graph_comparison.relation_rows(synthetic_edges, real_edges)

    assert plots.schema_figure(graph_comparison.synthetic_view(rows), set(synthetic_nodes)).data
    assert plots.schema_figure(rows, set(real_nodes)).data
