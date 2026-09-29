"""Pruebas del prototipo `HeteroData` desde el dataset sintético (A35-1, #28).

Verifican el criterio de aceptación (el `HeteroData` se instancia y `validate()` devuelve
`True`), la correspondencia con DS-01, que ninguna columna mezcla unidades, que `x` no contiene
el target, el round-trip JSONL -> `HeteroData` -> JSONL, la compuerta de integridad y la carga
segura de los `.pt`.

Requieren el extra `graph`.
"""

from __future__ import annotations

import copy
import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from nutrigraphdt.data.synthetic import (  # noqa: E402
    NodeCountConfig,
    NodeType,
    OutputRecord,
    SyntheticDataset,
    SyntheticEdgeConfig,
    SyntheticNodeConfig,
    generate_scenario_dataset,
    generate_synthetic_dataset,
)
from nutrigraphdt.data.synthetic.targets import DEFAULT_TARGET_CHEMICAL_IDS  # noqa: E402
from nutrigraphdt.graph.heterodata import (  # noqa: E402
    MANIFEST_FILE,
    build_heterodata,
    build_synthetic_graphs,
    derive_schema,
    heterodata_to_records,
    load_graphs,
    save_graphs,
)
from nutrigraphdt.graph.validation import Severity  # noqa: E402

BEYOND_CATALOG = NodeCountConfig(
    diet=3, additive=6, substrate=10, taxon=14, function=11, metabolite=8, host=2, phenotype=5
)


def _graph(dataset: SyntheticDataset, position: int = 0) -> Any:
    return build_heterodata(dataset, dataset.instances[position].graph_id)


def _nodes(dataset: SyntheticDataset, graph_id: str, node_type: str) -> list[Any]:
    return sorted(
        (
            node
            for node in dataset.nodes
            if node.graph_id == graph_id and node.node_type == node_type
        ),
        key=lambda node: node.node_id,
    )


# ---------------------------------------------------------------------------
# Criterio de aceptación y correspondencia con DS-01
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "dataset",
    [
        generate_scenario_dataset(),
        generate_synthetic_dataset(),
        generate_synthetic_dataset(SyntheticNodeConfig(counts=BEYOND_CATALOG)),
        generate_synthetic_dataset(
            SyntheticNodeConfig(random_seed=7, counts=NodeCountConfig(1, 1, 1, 1, 1, 1, 1, 1)),
            SyntheticEdgeConfig(random_seed=7),
        ),
    ],
    ids=["scenarios", "default", "beyond-catalog", "minimal"],
)
# PyG advierte tipos sin aristas (CON-03); en el perfil mínimo un aditivo queda aislado.
@pytest.mark.filterwarnings("ignore:The node types .* are isolated:UserWarning")
def test_every_instance_builds_and_passes_pyg_validation(dataset: SyntheticDataset) -> None:
    for instance in dataset.instances:
        data = build_heterodata(dataset, instance.graph_id)

        assert data.validate(raise_on_error=False) is True
        assert set(data.node_types) == {node_type.value for node_type in NodeType}
        for node_type, store in data.node_items():
            assert store.num_nodes == len(_nodes(dataset, instance.graph_id, node_type))
        edges = [edge for edge in dataset.edges if edge.graph_id == instance.graph_id]
        for edge_type, store in data.edge_items():
            assert store.edge_index.dtype == torch.long
            assert store.edge_index.size(1) == sum(edge.edge_type == edge_type for edge in edges)


def test_node_rows_follow_node_id_order_and_keep_traceability() -> None:
    dataset = generate_synthetic_dataset()
    data = _graph(dataset)
    taxa = _nodes(dataset, dataset.instances[0].graph_id, "taxon")

    store = data["taxon"]
    assert store.node_id == [node.node_id for node in taxa]
    assert store.source_id == [node.source_id for node in taxa]
    assert store.raw_attributes == [node.attributes for node in taxa]
    assert store.x[:, 0].tolist() == pytest.approx([node.attributes["abundance"] for node in taxa])


def test_global_attributes_mirror_the_instance_record() -> None:
    dataset = generate_scenario_dataset()
    instance = dataset.instances[1]

    data = build_heterodata(dataset, instance.graph_id)

    for name, value in instance.to_dict().items():
        if value is None:
            assert not hasattr(data, name)  # PyG no almacena None (timepoint)
        else:
            assert getattr(data, name) == value


# ---------------------------------------------------------------------------
# Codificación: columnas declaradas, sin mezclar unidades
# ---------------------------------------------------------------------------


def test_every_tensor_width_matches_the_declared_schema() -> None:
    build = build_synthetic_graphs(generate_scenario_dataset())
    metadata = build.dataset.metadata

    for data in build.graphs.values():
        for node_type, store in data.node_items():
            assert store.x.shape[1] == len(metadata["node_feature_schema"][node_type])
        for edge_type, store in data.edge_items():
            columns = metadata["edge_feature_schema"]["|".join(edge_type)]
            assert store.edge_attr.shape == (store.edge_index.size(1), len(columns))
    assert metadata["feature_encoding"] == "prototype-0.1"


def test_each_column_has_a_single_unit_and_magnitude() -> None:
    dataset = generate_synthetic_dataset(SyntheticNodeConfig(counts=BEYOND_CATALOG))
    schema = derive_schema(dataset.nodes, dataset.edges, dataset.outputs)
    data = _graph(dataset)

    dose = [column for column in schema.node["additive"] if column.source == "attributes.dose"]
    assert {column.unit for column in dose} == {"CFU/kg", "mg/kg"}
    annotation = schema.node["function"]
    assert {column.qualifier for column in annotation} == {"presence", "abundance"}

    additives = _nodes(dataset, dataset.instances[0].graph_id, "additive")
    for row, node in enumerate(additives):
        for position, column in enumerate(dose):
            same_unit = node.attributes["dose_unit"] == column.unit
            assert bool(data["additive"].missing_mask[row, position]) is not same_unit
            if same_unit:
                assert data["additive"].x[row, position].item() == pytest.approx(
                    node.attributes["dose"]
                )


def test_missing_values_are_masked_not_invented() -> None:
    dataset = generate_synthetic_dataset()
    graph_id = dataset.instances[0].graph_id
    taxon = _nodes(dataset, graph_id, "taxon")[2]
    missing = replace(
        taxon,
        attributes={**taxon.attributes, "abundance": None},
        missing_mask={"abundance": True},
    )
    dataset = replace(dataset, nodes=[missing if node is taxon else node for node in dataset.nodes])

    data = _graph(dataset)

    assert data["taxon"].x[2, 0].item() == 0.0
    assert bool(data["taxon"].missing_mask[2, 0]) is True
    assert int(data["taxon"].missing_mask.sum()) == 1


def test_non_finite_values_are_rejected_instead_of_masked() -> None:
    dataset = generate_synthetic_dataset()
    taxon = next(node for node in dataset.nodes if node.node_type == "taxon")
    broken = replace(taxon, attributes={**taxon.attributes, "abundance": math.nan})
    dataset = replace(dataset, nodes=[broken if node is taxon else node for node in dataset.nodes])

    with pytest.raises(ValueError, match="no finito"):
        _graph(dataset)


# ---------------------------------------------------------------------------
# Target AGCC sin fuga
# ---------------------------------------------------------------------------


def test_target_is_the_scfa_concentration_from_the_outputs() -> None:
    dataset = generate_scenario_dataset()
    for instance in dataset.instances:
        data = build_heterodata(dataset, instance.graph_id)
        metabolites = _nodes(dataset, instance.graph_id, "metabolite")
        store = data["metabolite"]

        expected_mask = [
            node.attributes["chemical_id"] in DEFAULT_TARGET_CHEMICAL_IDS for node in metabolites
        ]
        assert store.y.shape == (len(metabolites), 1)
        assert store.y_mask[:, 0].tolist() == expected_mask
        for row, node in enumerate(metabolites):
            if expected_mask[row]:
                assert store.y[row, 0].item() == pytest.approx(
                    node.attributes["concentration"], rel=1e-6
                )
            else:
                assert store.y[row, 0].item() == 0.0
        assert data.output_records == [
            output.to_dict() for output in dataset.outputs if output.graph_id == instance.graph_id
        ]


def test_features_do_not_contain_the_target_or_observed_outcomes() -> None:
    dataset = generate_synthetic_dataset(SyntheticNodeConfig(counts=BEYOND_CATALOG))
    schema = derive_schema(dataset.nodes, dataset.edges, dataset.outputs)

    assert schema.node["metabolite"] == ()
    assert schema.node["phenotype"] == ()  # incluye cecal_scfa_total, derivado de los AGCC
    sources = {column.source for columns in schema.node.values() for column in columns}
    assert "attributes.concentration" not in sources
    assert "attributes.value" not in sources


def test_predictions_are_kept_but_never_used_as_target() -> None:
    dataset = generate_synthetic_dataset()
    target = dataset.outputs[0]
    prediction = replace(target, measured_or_predicted="predicted", model_version="gnn-0.1")
    dataset = replace(dataset, outputs=[prediction, *dataset.outputs[1:]])

    data = _graph(dataset)

    row = data["metabolite"].node_id.index(target.target_id)
    assert bool(data["metabolite"].y_mask[row, 0]) is False
    assert prediction.to_dict() in data.output_records


def test_targets_with_mixed_units_are_rejected() -> None:
    dataset = generate_synthetic_dataset()
    first = dataset.outputs[0]
    dataset = replace(dataset, outputs=[replace(first, unit="umol/g"), *dataset.outputs[1:]])

    with pytest.raises(ValueError, match="mezclan"):
        derive_schema(dataset.nodes, dataset.edges, dataset.outputs)


def test_datasets_without_targets_build_without_y() -> None:
    dataset = generate_synthetic_dataset(target_config=None)

    data = _graph(dataset)

    assert dataset.outputs == []
    assert "y" not in data["metabolite"]
    assert data.output_records == []


# ---------------------------------------------------------------------------
# Round-trip, compuerta de integridad y serialización
# ---------------------------------------------------------------------------


def test_round_trip_jsonl_heterodata_jsonl_loses_nothing() -> None:
    dataset = generate_scenario_dataset()
    taxon = next(node for node in dataset.nodes if node.node_type == "taxon")
    explicit = replace(taxon, missing_mask={"abundance": False})
    dataset = replace(
        dataset, nodes=[explicit if node is taxon else node for node in dataset.nodes]
    )

    for instance in dataset.instances:
        records = heterodata_to_records(build_heterodata(dataset, instance.graph_id))

        assert records["instance"] == instance.to_dict()
        assert records["nodes"] == [
            node.to_dict() for node in dataset.nodes if node.graph_id == instance.graph_id
        ]
        assert records["edges"] == [
            edge.to_dict() for edge in dataset.edges if edge.graph_id == instance.graph_id
        ]
        assert records["outputs"] == [
            output.to_dict() for output in dataset.outputs if output.graph_id == instance.graph_id
        ]


def test_built_graphs_pass_every_integrity_rule() -> None:
    build = build_synthetic_graphs(generate_scenario_dataset())

    assert set(build.graphs) == {instance.graph_id for instance in build.dataset.instances}
    assert "TEN" in build.report.evaluated and not build.report.not_evaluated
    assert [f for f in build.report.findings if f.severity is Severity.ERROR] == []
    assert not any(f.rule_id.startswith("TEN") for f in build.report.findings)


def test_instances_with_record_errors_are_not_converted() -> None:
    """Orden de VG-01: un registro inválido no se convierte (aquí, la conversión fallaría)."""
    dataset = generate_scenario_dataset()
    basal = dataset.instances[0].graph_id
    position = next(index for index, edge in enumerate(dataset.edges) if edge.graph_id == basal)
    edges = list(dataset.edges)
    edges[position] = replace(edges[position], target_id="synthetic:missing:0001")
    broken = replace(dataset, edges=edges)

    with pytest.raises(ValueError, match="EDG-02"):
        build_heterodata(broken, basal)
    build = build_synthetic_graphs(broken)

    assert basal not in build.graphs
    assert set(build.graphs) == {dataset.instances[1].graph_id}
    assert [f.rule_id for f in build.report.blocking_findings(basal)] == ["EDG-02"]
    assert build.report.not_evaluated[f"TEN:{basal}"].startswith("no se entregó")


def test_schema_is_declared_in_the_exported_metadata() -> None:
    dataset = generate_scenario_dataset()

    build = build_synthetic_graphs(dataset)

    assert dataset.metadata["node_feature_schema"] == {}
    declared = build.dataset.metadata
    assert declared["node_feature_schema"]["metabolite"] == []
    assert declared["target_schema"]["metabolite"]["measured_or_predicted"] == "synthetic"
    assert json.loads(json.dumps(declared, allow_nan=False)) == declared


def test_building_is_deterministic() -> None:
    dataset = generate_scenario_dataset()
    first = build_synthetic_graphs(dataset).graphs
    second = build_synthetic_graphs(dataset).graphs

    for graph_id, data in first.items():
        other = second[graph_id]
        for node_type, store in data.node_items():
            assert torch.equal(store.x, other[node_type].x)
            assert store.node_id == other[node_type].node_id
        for edge_type, store in data.edge_items():
            assert torch.equal(store.edge_index, other[edge_type].edge_index)


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    graphs = build_synthetic_graphs(generate_scenario_dataset()).graphs

    save_graphs(graphs, tmp_path)
    loaded = load_graphs(tmp_path)

    manifest = json.loads((tmp_path / MANIFEST_FILE).read_text(encoding="utf-8"))
    assert [entry["file"] for entry in manifest["graphs"]] == ["graph_0001.pt", "graph_0002.pt"]
    assert set(loaded) == set(graphs)
    for graph_id, data in graphs.items():
        assert heterodata_to_records(loaded[graph_id]) == heterodata_to_records(data)
        assert torch.equal(loaded[graph_id]["taxon"].x, data["taxon"].x)


def test_save_refuses_to_overwrite_and_replaces_on_request(tmp_path: Path) -> None:
    graphs = build_synthetic_graphs(generate_scenario_dataset()).graphs
    save_graphs(graphs, tmp_path)

    with pytest.raises(FileExistsError):
        save_graphs(graphs, tmp_path)
    single = {key: graphs[key] for key in sorted(graphs)[:1]}
    save_graphs(single, tmp_path, overwrite=True)

    assert sorted(path.name for path in tmp_path.glob("*.pt")) == ["graph_0001.pt"]
    assert set(load_graphs(tmp_path)) == set(single)


def test_load_rejects_files_with_arbitrary_objects(tmp_path: Path) -> None:
    graphs = build_synthetic_graphs(generate_synthetic_dataset()).graphs
    save_graphs(graphs, tmp_path)
    tampered = copy.copy(next(iter(graphs.values())))
    tampered.payload = OutputRecord("g", "metabolite", "m", 1.0, "synthetic", "u", "s")
    torch.save(tampered, tmp_path / "graph_0001.pt")

    with pytest.raises(Exception, match="(?i)weights only|unsupported global"):
        load_graphs(tmp_path)


def test_load_checks_the_manifest_graph_ids(tmp_path: Path) -> None:
    graphs = build_synthetic_graphs(generate_scenario_dataset()).graphs
    save_graphs(graphs, tmp_path)
    manifest_path = tmp_path / MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["graphs"][0]["file"], manifest["graphs"][1]["file"] = (
        manifest["graphs"][1]["file"],
        manifest["graphs"][0]["file"],
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="no contiene el grafo"):
        load_graphs(tmp_path)
