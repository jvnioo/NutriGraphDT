"""Pruebas del constructor del grafo desde tablas preprocesadas (A39-1 #35, A39-3 #37).

Las tablas se escriben a mano para que los conteos y valores esperados no se recalculen desde
el código bajo prueba. Cubren la traducción a DS-01, los casos borde que pide A39-3 (nodos sin
aristas, atributos faltantes, relaciones o tipos fuera del esquema, referencias a instancias
inexistentes) y la reproducibilidad. Requieren el extra `graph`.
"""

from __future__ import annotations

import random
from dataclasses import replace

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from nutrigraphdt.data.schema import (  # noqa: E402
    NormalizedEdgeRecord,
    NormalizedFeatureRecord,
    NormalizedInstanceRecord,
    NormalizedTabularDataset,
    NormalizedTargetRecord,
)
from nutrigraphdt.graph.audit import audit_built_graphs  # noqa: E402
from nutrigraphdt.graph.builder import (  # noqa: E402
    add_reverse_edges,
    build_hetero_graph,
    records_from_tables,
)


def _instance(sample: str, **overrides: object) -> NormalizedInstanceRecord:
    values: dict[str, object] = {
        "graph_id": f"real:{sample}",
        "sample_id": sample,
        "species": "chicken",
        "gut_segment": "cecum",
        "study_id": "CA",
        "scenario_id": "observed",
        "diet_treatment": "Control",
        "timepoint": "21",
        "source_id": "real",
    }
    values.update(overrides)
    return NormalizedInstanceRecord(**values)  # type: ignore[arg-type]


def _taxon(
    sample: str, taxon: str, value: float, level: str | None = None
) -> NormalizedFeatureRecord:
    return NormalizedFeatureRecord(
        graph_id=f"real:{sample}",
        node_id=taxon,
        node_type="taxon",
        feature_name="abundance",
        value=value,
        unit="relative_abundance",
        source_id="real",
        taxonomy_level=level,
    )


def _weight(sample: str, value: float) -> NormalizedFeatureRecord:
    return NormalizedFeatureRecord(
        graph_id=f"real:{sample}",
        node_id=f"{sample}:host",
        node_type="host",
        feature_name="body_weight_g",
        value=value,
        unit="g",
        source_id="real",
    )


def _target(sample: str, metabolite: str, value: float) -> NormalizedTargetRecord:
    return NormalizedTargetRecord(
        graph_id=f"real:{sample}",
        target_type="scfa_concentration",
        target_id=metabolite,
        value=value,
        unit="mmol_kg",
        sample_matrix="cecal_content",
        measured_or_predicted="measured",
        source_id="real",
    )


def _tables() -> NormalizedTabularDataset:
    """Dos animales: A1 con peso y dos AGCC; A2 sin peso ni AGCC (atributos faltantes)."""
    return NormalizedTabularDataset(
        instances=[_instance("A1"), _instance("A2", diet_treatment="Probiotic")],
        features=[
            _taxon("A1", "Lactobacillus", 0.75),
            _taxon("A1", "Bacteroides", 0.25),
            _taxon("A2", "Lactobacillus", 1.0),
            _weight("A1", 920.8),
        ],
        targets=[_target("A1", "acetate", 51.5), _target("A1", "butyrate", 13.4)],
    )


def test_tables_translate_to_ds01_records() -> None:
    records = records_from_tables(_tables())
    by_type: dict[str, list[str]] = {}
    for node in records.nodes:
        if node["graph_id"] == "real:A1":
            by_type.setdefault(node["node_type"], []).append(node["node_id"])
    assert by_type == {
        "diet": ["A1:diet"],
        "taxon": ["Bacteroides", "Lactobacillus"],
        "metabolite": ["acetate", "butyrate"],
        "host": ["A1:host"],
    }
    host = next(node for node in records.nodes if node["node_id"] == "A1:host")
    assert host["attributes"]["covariates"] == {"body_weight_g": 920.8}
    assert host["attributes"]["cohort_id"] == "CA"
    assert [(o["target_id"], o["value"]) for o in records.outputs] == [
        ("acetate", 51.5),
        ("butyrate", 13.4),
    ]
    assert {e["relation_type"] for e in records.edges} == {"measured_in"}
    assert {e["evidence_status"] for e in records.edges} == {"observed"}
    assert records.metadata["counts"]["real:A1"]["outputs"] == 2


def test_missing_attributes_are_null_with_mask_never_invented() -> None:
    records = records_from_tables(_tables())
    taxon = next(node for node in records.nodes if node["node_type"] == "taxon")
    assert taxon["attributes"]["taxonomy_level"] is None
    assert taxon["missing_mask"]["taxonomy_level"] is True
    assert taxon["attributes"]["taxonomy_id"] == taxon["node_id"]
    assert taxon["missing_mask"]["abundance"] is False
    metabolite = next(node for node in records.nodes if node["node_type"] == "metabolite")
    assert metabolite["attributes"]["concentration"] is None  # el valor solo vive en y


def test_taxonomy_level_reaches_the_taxon_node() -> None:
    tables = replace(_tables(), features=[_taxon("A1", "Lactobacillus", 1.0, "genus")])
    (taxon,) = [node for node in records_from_tables(tables).nodes if node["node_type"] == "taxon"]
    assert taxon["attributes"]["taxonomy_level"] == "genus"
    assert taxon["missing_mask"]["taxonomy_level"] is False


def test_taxonomy_level_is_rejected_outside_taxon_rows() -> None:
    with pytest.raises(ValueError, match="taxonomy_level"):
        replace(_weight("A1", 900.0), taxonomy_level="genus")


def test_graph_has_expected_tensors_and_target() -> None:
    graphs = build_hetero_graph(_tables()).graphs
    data = graphs["real:A1"]
    assert data["taxon"].node_id == ["Bacteroides", "Lactobacillus"]
    assert data["taxon"].x.tolist() == [[0.25], [0.75]]
    assert data["host"].x.tolist() == [[pytest.approx(920.8)]]
    assert data["metabolite"].y.squeeze(1).tolist() == pytest.approx([51.5, 13.4])
    assert data["metabolite"].y_mask.all()
    edge_index = data["metabolite", "measured_in", "host"].edge_index
    assert edge_index.tolist() == [[0, 1], [0, 0]]
    assert data.diet_treatment == "Control"


def test_instance_without_weight_or_targets_keeps_shared_columns_masked() -> None:
    data = build_hetero_graph(_tables()).graphs["real:A2"]
    assert data["host"].x.shape == (1, 1)
    assert data["host"].missing_mask.tolist() == [[True]]
    assert "metabolite" not in data.node_types
    assert not data.edge_types


def test_nodes_without_edges_are_built_and_reported_as_isolated() -> None:
    built = build_hetero_graph(_tables(), link_measurements=False)
    assert not built.graphs["real:A1"].edge_types
    rules = {f.rule_id for f in audit_built_graphs(built).report.findings}
    assert {"CON-01", "CON-03"} <= rules


def test_relation_outside_schema_v1_is_rejected() -> None:
    tables = replace(
        _tables(),
        edges=[
            NormalizedEdgeRecord(
                graph_id="real:A1",
                src_id="Lactobacillus",
                src_type="taxon",
                relation_type="produces",
                dst_id="acetate",
                dst_type="metabolite",
                evidence_status="inferred",
                source_id="real",
            )
        ],
    )
    with pytest.raises(ValueError, match="esquema v1"):
        build_hetero_graph(tables)


def test_unknown_node_type_is_rejected_before_reaching_the_builder() -> None:
    with pytest.raises(ValueError):
        replace(_taxon("A1", "x", 1.0), node_type="plasmid")


@pytest.mark.parametrize(
    "tables",
    [
        replace(_tables(), features=[_taxon("Z9", "Lactobacillus", 1.0)]),
        replace(_tables(), targets=[_target("Z9", "acetate", 1.0)]),
        replace(
            _tables(),
            edges=[
                NormalizedEdgeRecord(
                    graph_id="real:Z9",
                    src_id="acetate",
                    src_type="metabolite",
                    relation_type="measured_in",
                    dst_id="Z9:host",
                    dst_type="host",
                    source_id="real",
                )
            ],
        ),
    ],
    ids=["feature", "target", "edge"],
)
def test_references_to_missing_instances_are_rejected(tables: NormalizedTabularDataset) -> None:
    with pytest.raises(ValueError, match="inexistente"):
        records_from_tables(tables)


def test_duplicate_targets_and_features_are_rejected() -> None:
    with pytest.raises(ValueError, match="Dos targets"):
        records_from_tables(
            replace(_tables(), targets=[*_tables().targets, _target("A1", "acetate", 1.0)])
        )
    with pytest.raises(ValueError, match="repetida"):
        records_from_tables(
            replace(_tables(), features=[*_tables().features, _taxon("A1", "Bacteroides", 0.1)])
        )


def test_mixing_synthetic_and_real_instances_is_rejected() -> None:
    tables = replace(_tables(), instances=[_instance("A1"), _instance("A2", is_synthetic=True)])
    with pytest.raises(ValueError, match="mezclan"):
        records_from_tables(tables)


def _signature(tables: NormalizedTabularDataset) -> list[object]:
    graphs = build_hetero_graph(tables).graphs
    signature: list[object] = []
    for graph_id in sorted(graphs):
        data = graphs[graph_id]
        for node_type in sorted(data.node_types):
            signature += [graph_id, node_type, data[node_type].node_id, data[node_type].x.tolist()]
        for edge_type in sorted(data.edge_types):
            signature += [graph_id, edge_type, data[edge_type].edge_index.tolist()]
    return signature


def test_same_input_in_any_order_gives_the_same_graphs() -> None:
    tables = _tables()
    shuffled = list(tables.features)
    random.Random(3).shuffle(shuffled)
    reordered = replace(
        tables,
        instances=list(reversed(tables.instances)),
        features=shuffled,
        targets=list(reversed(tables.targets)),
    )
    assert _signature(tables) == _signature(tables) == _signature(reordered)


def test_reverse_edges_are_added_only_on_a_copy() -> None:
    data = build_hetero_graph(_tables()).graphs["real:A1"]
    both = add_reverse_edges(data)
    forward = ("metabolite", "measured_in", "host")
    reverse = ("host", "rev_measured_in", "metabolite")
    assert reverse in both.edge_types
    assert reverse not in data.edge_types
    assert both[reverse].edge_index.tolist() == data[forward].edge_index.flip(0).tolist()
    assert both[reverse].evidence_status == data[forward].evidence_status


def test_audit_runs_tensor_rules_and_contracts_on_every_graph() -> None:
    audit = audit_built_graphs(build_hetero_graph(_tables()))
    rules = {finding.rule_id for finding in audit.report.findings}
    assert not {rule for rule in rules if rule.startswith("TEN")}
    assert "TEN" in audit.report.evaluated
    assert not audit.report.errors  # reglas 1.2.0: medición observada, escenario observed
    assert audit.contracts.checked_edges == 2
    assert audit.contracts.invalid_edges == 0
    assert audit.contracts.invalid_nodes == 0  # nulos declarados en missing_mask (#65)
