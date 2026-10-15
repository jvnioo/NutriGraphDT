"""Tests de los datos de la demo (`nutrigraphdt.demo.data`).

Requiere el extra `graph`; no requiere Streamlit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from nutrigraphdt.demo import data  # noqa: E402


@pytest.fixture(scope="module")
def scenarios():  # type: ignore[no-untyped-def]
    return data.synthetic_scenarios()


@pytest.fixture(scope="module")
def d1():  # type: ignore[no-untyped-def]
    return data.d1_fixture()


def test_graph_view_places_each_type_in_its_own_column(scenarios) -> None:  # type: ignore[no-untyped-def]
    graph_id = data.graph_ids(scenarios)[0]

    view = data.graph_view(scenarios, graph_id)

    assert view.node_types == list(data.NODE_TYPE_ORDER)
    columns = {node["node_type"]: node["x"] for node in view.nodes}
    assert [columns[t] for t in view.node_types] == list(range(len(view.node_types)))
    assert len(view.nodes) == 32
    assert view.hidden == {}
    ids = {(n["node_type"], n["node_id"]) for n in view.nodes}
    for edge in view.edges:
        assert (edge["source_type"], edge["source_id"]) in ids
        assert (edge["target_type"], edge["target_id"]) in ids


def test_graph_view_limits_large_types_and_keeps_connected_nodes(d1) -> None:  # type: ignore[no-untyped-def]
    built, _ = d1
    graph_id = data.graph_ids(built.records)[0]

    view = data.graph_view(built.records, graph_id, max_per_type=10)

    taxa = [n for n in view.nodes if n["node_type"] == "taxon"]
    assert len(taxa) == 10
    assert view.hidden["taxon"] == 439 - 10
    metabolites = [n for n in view.nodes if n["node_type"] == "metabolite"]
    assert all(n["degree"] > 0 for n in metabolites)
    assert len(view.edges) == len(metabolites)


def test_targets_use_metabolite_names(scenarios, d1) -> None:  # type: ignore[no-untyped-def]
    synthetic = data.targets_of(scenarios, data.graph_ids(scenarios)[0])
    built, _ = d1
    real = data.targets_of(built.records, data.graph_ids(built.records)[0])

    assert set(synthetic) == {"Acetato", "Propionato", "Butirato"}
    assert {"acetate", "propionate", "butyrate"} <= set(real)


def test_split_summary_counts_animals_and_pens() -> None:
    summary = data.split_summary()

    assert sum(summary["counts"].values()) == 530
    assert all(count > 0 for count in summary["groups"].values())
    assert summary["group_key"] == "pen_code"


def test_baseline_table_has_one_row_per_model() -> None:
    report = data.baseline_report(data.REPORTS_DIR / "baselines" / "d1")

    table = data.baseline_table(report["rows"], "rmse", "test")

    assert [row["modelo"] for row in table] == [
        "dummy_mean",
        "ridge",
        "elasticnet",
        "random_forest",
        "hist_gradient_boosting",
    ]
    assert report["header"].startswith("# Tabla comparativa")


def test_list_runs_reads_recorded_runs(tmp_path: Path) -> None:
    run_dir = tmp_path / "20261015-120000_homo_sage_s42"
    run_dir.mkdir()
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_dir.name,
                "variant": "homo_sage",
                "epochs_run": 5,
                "best_epoch": 3,
                "duration_seconds": 1.23,
                "created_at": "2026-10-15T12:00:00+00:00",
                "source": {"dataset": "synthetic"},
                "environment": {"device": "cpu"},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "metrics.csv").write_text(
        "model,split,metric,acetate,propionate,butyrate,average\nhomo_sage,val,rmse,1,2,3,2.0\n",
        encoding="utf-8",
    )

    (run,) = data.list_runs(tmp_path)

    assert run["variante"] == "homo_sage"
    assert run["rmse_val"] == 2.0
    assert run["dataset"] == "synthetic"
    assert data.list_runs(tmp_path / "missing") == []


def test_relations_read_as_sentences() -> None:
    assert data.relation_text("taxon", "has_capacity", "function") == "Taxón realiza función"
    assert data.relation_text("substrate", "available_to", "taxon") == ("Sustrato alimenta a taxón")


def test_upstream_of_a_target_follows_edges_backwards(scenarios) -> None:  # type: ignore[no-untyped-def]
    view = data.graph_view(scenarios, data.graph_ids(scenarios)[0])
    butyrate = next(node for node in view.nodes if node["label"] == "Butirato")

    nodes, edges = data.upstream(view, "metabolite", butyrate["node_id"])

    types = {node_type for node_type, _ in nodes}
    assert {"diet", "substrate", "taxon", "function"} <= types
    assert "host" not in types and "phenotype" not in types
    for index in edges:
        edge = view.edges[index]
        assert (edge["source_type"], edge["source_id"]) in nodes
        assert (edge["target_type"], edge["target_id"]) in nodes


def test_compare_graphs_shows_d1_taxa_without_connections(scenarios, d1) -> None:  # type: ignore[no-untyped-def]
    built, _ = d1
    comparison = data.compare_graphs(
        scenarios, data.graph_ids(scenarios)[0], built.records, data.graph_ids(built.records)[0]
    )

    taxa = next(row for row in comparison["nodes"] if row["tipo"] == "Taxón")
    assert taxa["D1"] == 439 and taxa["D1 conectados"] == 0
    assert taxa["sintético"] == taxa["sintético conectados"] == 10
    relations = {row["relación"]: row for row in comparison["relations"]}
    assert relations["Metabolito se midió en huésped"]["D1"] == 8
    assert sum(row["D1"] for row in comparison["relations"]) == 8
    assert sum(row["sintético"] for row in comparison["relations"]) == 78
