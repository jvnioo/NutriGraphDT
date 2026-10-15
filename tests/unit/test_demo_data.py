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
    return data.d1_records(prefer_full=False)


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
    built = d1
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
    built = d1
    real = data.targets_of(built.records, data.graph_ids(built.records)[0])

    assert set(synthetic) == {"Acetato", "Propionato", "Butirato"}
    assert {"acetate", "propionate", "butyrate"} <= set(real)


def test_baseline_table_has_one_row_per_model() -> None:
    report = data.baseline_report(data.REPORTS_DIR / "baselines" / "d1")

    table = data.baseline_table(report["rows"], "rmse", "test")

    assert [row["clave"] for row in table] == [
        "dummy_mean",
        "ridge",
        "elasticnet",
        "random_forest",
        "hist_gradient_boosting",
    ]
    assert report["header"].startswith("# Tabla comparativa")


def test_relations_read_as_sentences() -> None:
    assert data.relation_text("taxon", "has_capacity", "function") == "Taxón realiza función"
    assert data.relation_text("substrate", "available_to", "taxon") == ("Sustrato alimenta a taxón")


def test_d1_records_fall_back_to_the_fixture(d1) -> None:  # type: ignore[no-untyped-def]
    assert d1.full is False
    assert len(data.graph_ids(d1.records)) == 6


def test_agcc_by_animal_keeps_animals_with_the_three_scfa(d1) -> None:  # type: ignore[no-untyped-def]
    rows = data.agcc_by_animal(d1.records)

    assert len(rows) == 6
    assert all(row[name] >= 0 for row in rows for name in data.SCFA_NAMES)
    assert {"animal", "dieta", "día"} <= set(rows[0])


def test_baseline_table_uses_friendly_names_and_keeps_the_key() -> None:
    report = data.baseline_report(data.REPORTS_DIR / "baselines" / "d1")

    first = data.baseline_table(report["rows"], "rmse", "test")[0]

    assert first["clave"] == "dummy_mean"
    assert first["modelo"] == "Media (referencia)"


def test_rule_catalog_describes_the_d1_warnings() -> None:
    catalog = data.rule_catalog()

    assert len(catalog) >= 50
    assert catalog["CON-01"].startswith("Un nodo tiene grado 0")


def test_d1_graph_report_keeps_only_the_summary(tmp_path: Path) -> None:
    report = {
        "integration": {"instances_with_context": 2, "targets": 6},
        "graphs": {"instances": 2, "nodes_per_type": {}, "edges_per_relation": {}},
        "contracts": {
            "checked_nodes": 10,
            "checked_edges": 6,
            "invalid_nodes": 0,
            "invalid_edges": 0,
            "groups": {},
        },
        "validation": {
            "status": "valid",
            "rules_version": "1.2.0",
            "summary": {"ERROR": 0, "ADVERTENCIA": 2, "INFO": 0},
            "graphs": {"a": {"deliverable": True}, "b": {"deliverable": True}},
            "rules": {"CON-01": {"severity": "ADVERTENCIA", "count": 2}},
            "evaluated": ["CON-01", "NOD-08"],
            "findings": [{"rule_id": "CON-01"}, {"rule_id": "CON-01"}],
        },
    }
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    summary = data.d1_graph_report(path)

    assert summary is not None
    assert summary["deliverable"] == 2
    assert summary["evaluated"] == 2
    assert summary["contracts"] == {
        "checked_nodes": 10,
        "checked_edges": 6,
        "invalid_nodes": 0,
        "invalid_edges": 0,
    }
    assert summary["rules"][0]["regla"] == "CON-01"
    assert summary["rules"][0]["descripción"]
    assert "findings" not in summary
    assert data.d1_graph_report(tmp_path / "missing.json") is None


def test_gnn_synthetic_rows_share_the_baseline_format(tmp_path: Path) -> None:
    rows = data.gnn_synthetic_rows()

    assert rows is not None
    table = data.baseline_table(rows, "rmse", "test")
    assert [row["clave"] for row in table] == ["homo_sage", "hetero_sage", "hetero_gat"]
    assert table[0]["modelo"] == "GNN simple"
    assert data.gnn_synthetic_rows(tmp_path) is None
