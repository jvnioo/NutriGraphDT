"""Codificación del tratamiento dietario en el nodo `diet` (A65-P1, #176).

Las tablas se escriben a mano: tres animales de D1 con contrato v2 (covariables del huésped
declaradas), uno por tratamiento. Los valores esperados del one-hot salen de la tabla de
`nutrigraphdt.data.diet`, no del código bajo prueba. Requieren el extra `graph`.
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from nutrigraphdt.data.schema import (  # noqa: E402
    NormalizedInstanceRecord,
    NormalizedTabularDataset,
)
from nutrigraphdt.data.synthetic import generate_synthetic_dataset  # noqa: E402
from nutrigraphdt.graph.builder import build_hetero_graph  # noqa: E402
from nutrigraphdt.graph.heterodata import build_synthetic_graphs  # noqa: E402
from nutrigraphdt.graph.validation import find_node_findings  # noqa: E402

COVARIATES = {"trial_code": "CA", "pen_code": "CA21", "sampling_day": 7, "sex": "male"}


def _instance(sample: str, diet: str) -> NormalizedInstanceRecord:
    return NormalizedInstanceRecord(
        graph_id=f"real:{sample}",
        sample_id=sample,
        species="chicken",
        gut_segment="cecum",
        study_id="CA",
        scenario_id="observed",
        diet_treatment=diet,
        timepoint="7",
        source_id="real",
        host_covariates={**COVARIATES, "breed": "Ross"},
    )


def _tables(*diets: str) -> NormalizedTabularDataset:
    return NormalizedTabularDataset(
        instances=[_instance(f"A{i}", diet) for i, diet in enumerate(diets, start=1)]
    )


def test_each_treatment_has_its_own_one_hot_row() -> None:
    built = build_hetero_graph(_tables("Control", "Probiotic", "Prebiotic"))

    rows = {graph_id: data["diet"].x.tolist() for graph_id, data in built.graphs.items()}
    assert rows == {
        "real:A1": [[1.0, 0.0, 0.0]],
        "real:A2": [[0.0, 1.0, 0.0]],
        "real:A3": [[0.0, 0.0, 1.0]],
    }
    assert not any(bool(data["diet"].missing_mask.any()) for data in built.graphs.values())


def test_columns_keep_code_source_name_and_project_label() -> None:
    columns = build_hetero_graph(_tables("Prebiotic")).records.metadata["node_feature_schema"][
        "diet"
    ]
    assert [(c["name"], c["qualifier"], c["label"]) for c in columns] == [
        ("diet_treatment=CC", "Control", "Control"),
        ("diet_treatment=CO", "Probiotic", "Probiótico"),
        ("diet_treatment=CE", "Prebiotic", "Fitobiótico"),
    ]
    assert {c["encoding"] for c in columns} == {"one_hot"}
    assert {c["source"] for c in columns} == {"attributes.name"}


def test_diet_node_keeps_the_source_name() -> None:
    records = build_hetero_graph(_tables("Prebiotic")).records
    (diet,) = [node for node in records.nodes if node["node_type"] == "diet"]
    assert diet["attributes"]["name"] == "Prebiotic"


def test_unknown_treatment_is_reported_and_not_encoded() -> None:
    built = build_hetero_graph(_tables("Control", "Synbiotic"))

    data = built.graphs["real:A2"]
    assert data["diet"].x.tolist() == [[0.0, 0.0, 0.0]]
    assert data["diet"].missing_mask.tolist() == [[True, True, True]]
    records = built.records
    findings = find_node_findings(records.instances, records.nodes, metadata=records.metadata)
    nod11 = [f for f in findings if f.rule_id == "NOD-11"]
    assert [(f.graph_id, f.location.get("attribute")) for f in nod11] == [("real:A2", "name")]


def test_treatment_is_not_encoded_without_contract_v2_covariates() -> None:
    tables = _tables("Control")
    v1 = NormalizedTabularDataset(
        instances=[
            NormalizedInstanceRecord(
                **{**instance.__dict__, "host_covariates": {}}  # type: ignore[arg-type]
            )
            for instance in tables.instances
        ]
    )
    assert build_hetero_graph(v1).records.metadata["node_feature_schema"]["diet"] == []


def test_synthetic_diet_columns_do_not_change() -> None:
    metadata = build_synthetic_graphs(generate_synthetic_dataset()).dataset.metadata
    names = [c["name"] for c in metadata["node_feature_schema"]["diet"]]
    assert names
    assert not [name for name in names if name.startswith("diet_treatment=")]
