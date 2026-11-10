"""Comparación del grafo sintético con el reconstruido con datos reales de D1."""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("plotly")
pytest.importorskip("torch_geometric")

from nutrigraphdt.demo import data, plots  # noqa: E402
from nutrigraphdt.demo import graph_comparison as cmp  # noqa: E402

D1_GRAPHS: dict[str, Any] = {
    "instances": 185,
    "nodes_per_type": {"taxon": {"min": 876, "max": 876, "total": 1}},
    "edges_per_relation": {"metabolite|measured_in|host": {"min": 2, "max": 8, "total": 1}},
    "feature_columns": {"taxon": ["abundance (relative_abundance)"], "function": []},
}


@pytest.fixture(scope="module")
def graphs():  # type: ignore[no-untyped-def]
    synthetic = data.synthetic_scenarios()
    real = data.d1_records(prefer_full=False).records
    real_id = data.agcc_by_animal(real)[0]["graph_id"]
    return synthetic, data.graph_ids(synthetic)[0], real, real_id


@pytest.fixture(scope="module")
def counts(graphs):  # type: ignore[no-untyped-def]
    synthetic, synthetic_id, real, real_id = graphs
    return cmp.instance_counts(synthetic, synthetic_id), cmp.instance_counts(real, real_id)


def test_the_synthetic_graph_has_every_relation_and_d1_only_three(counts) -> None:  # type: ignore[no-untyped-def]
    (_, synthetic_edges), (_, real_edges) = counts

    rows = cmp.relation_rows(synthetic_edges, real_edges)

    assert len(rows) == 11
    assert all(row["sintético"] > 0 for row in rows)
    present = {row["relación"] for row in rows if row["estado"] == cmp.PRESENT}
    assert present == {"measured_in", "has_capacity", "produces"}
    limited = {row["relación"] for row in rows if row["estado"] == cmp.LIMITATION}
    assert limited == {"provides", "available_to"}


def test_relation_rows_show_the_evidence_and_the_cohort_range(graphs, counts) -> None:  # type: ignore[no-untyped-def]
    synthetic, synthetic_id, real, real_id = graphs
    (_, synthetic_edges), (_, real_edges) = counts

    rows = {
        row["relación"]: row
        for row in cmp.relation_rows(
            synthetic_edges,
            real_edges,
            synthetic_evidence=cmp.evidence_by_relation(synthetic, synthetic_id),
            real_evidence=cmp.evidence_by_relation(real, real_id),
            d1_graphs=D1_GRAPHS,
        )
    }

    assert rows["measured_in"]["evidencia D1"] == "observed · measurement"
    assert rows["has_capacity"]["evidencia D1"].startswith("annotated · database_annotation · ")
    assert rows["has_capacity"]["evidencia sintético"] == "synthetic · synthetic_generator"
    assert rows["provides"]["evidencia D1"] == "—"
    assert rows["measured_in"]["D1 (185 grafos)"] == "2–8"
    assert rows["provides"]["D1 (185 grafos)"] == "0"


def test_node_rows_follow_the_schema_and_list_the_features(graphs, counts) -> None:  # type: ignore[no-untyped-def]
    synthetic, *_ = graphs
    (synthetic_nodes, _), (real_nodes, _) = counts

    rows = cmp.node_rows(
        synthetic_nodes,
        real_nodes,
        synthetic_features=cmp.feature_columns(synthetic),
        real_features=D1_GRAPHS["feature_columns"],
        d1_graphs=D1_GRAPHS,
    )

    assert [row["tipo"] for row in rows][:2] == ["diet", "additive"]
    assert all(row["sintético"] > 0 for row in rows)
    assert {row["tipo"] for row in rows if row["D1"] == 0} == {"additive", "substrate", "phenotype"}
    by_type = {row["tipo"]: row for row in rows}
    assert by_type["taxon"]["atributos D1"] == "abundance (relative_abundance)"
    assert by_type["function"]["atributos D1"] == "ninguno (solo identidad)"
    assert by_type["additive"]["atributos D1"] == "—"
    assert by_type["taxon"]["D1 (185 grafos)"] == "876"


def test_instance_and_target_rows_compare_both_graphs(graphs) -> None:  # type: ignore[no-untyped-def]
    synthetic, synthetic_id, real, real_id = graphs

    instance = {
        row["campo"]: row
        for row in cmp.instance_rows(
            data.instance_info(synthetic, synthetic_id), data.instance_info(real, real_id)
        )
    }
    targets = cmp.target_rows(
        data.targets_of(synthetic, synthetic_id),
        data.targets_of(real, real_id),
        {"acetate": {"n": 185, "q1": 1.0, "median": 2.0, "q3": 3.0}},
    )

    assert (instance["Sintético"]["sintético"], instance["Sintético"]["D1"]) == ("sí", "no")
    assert [row["AGCC"] for row in targets] == ["Acetato", "Propionato", "Butirato"]
    assert all(row["sintético"] is not None and row["D1"] is not None for row in targets)
    assert targets[0]["D1 mediana (Q1–Q3)"] == "2.0 (1.0–3.0), n=185"
    assert "D1 mediana (Q1–Q3)" not in targets[1]


def test_figures_build(graphs, counts) -> None:  # type: ignore[no-untyped-def]
    synthetic, synthetic_id, real, real_id = graphs
    (synthetic_nodes, synthetic_edges), (real_nodes, real_edges) = counts
    rows = cmp.relation_rows(synthetic_edges, real_edges)

    assert plots.schema_figure(cmp.synthetic_view(rows), set(synthetic_nodes)).data
    assert plots.schema_figure(rows, set(real_nodes)).data
    real_figure = plots.graph_figure(data.graph_view(real, real_id, max_per_type=10))
    statuses = {t.meta["evidence_status"] for t in real_figure.data if isinstance(t.meta, dict)}
    assert statuses == {"observed", "annotated"}
    assert plots.graph_figure(data.graph_view(synthetic, synthetic_id)).data
