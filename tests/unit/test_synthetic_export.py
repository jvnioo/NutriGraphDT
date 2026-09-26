"""Pruebas de exportación, carga y reproducibilidad del dataset sintético (DS-05)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from nutrigraphdt.data.synthetic import (
    INTERVENTION_INTERVENED_VALUE,
    INTERVENTION_VARIABLE,
    SCENARIO_BASAL_GRAPH_ID,
    SCENARIO_INTERVENED_GRAPH_ID,
    SCHEMA_VERSION,
    DatasetFormatError,
    DatasetValidationError,
    OutputRecord,
    SyntheticDataset,
    SyntheticEdgeConfig,
    SyntheticNodeConfig,
    build_basal_scenario,
    build_intervened_scenario,
    export_dataset,
    generate_scenario_dataset,
    generate_synthetic_dataset,
    load_dataset,
)

RAW_FILES = ("instances.jsonl", "nodes.jsonl", "edges.jsonl", "outputs.jsonl")


def _read_all_bytes(root: Path) -> dict[str, bytes]:
    files = ["metadata.json", *(f"raw/{name}" for name in RAW_FILES)]
    return {name: (root / name).read_bytes() for name in files}


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# ---------------------------------------------------------------------------
# Criterio 1: los archivos se generan correctamente
# ---------------------------------------------------------------------------


def test_export_creates_expected_layout(tmp_path: Path) -> None:
    root = export_dataset(generate_synthetic_dataset(), tmp_path / "v1")

    assert (root / "metadata.json").is_file()
    for name in RAW_FILES:
        assert (root / "raw" / name).is_file()


def test_exported_files_follow_the_contract(tmp_path: Path) -> None:
    dataset = generate_synthetic_dataset()
    root = export_dataset(dataset, tmp_path / "v1")

    nodes = _jsonl(root / "raw" / "nodes.jsonl")
    edges = _jsonl(root / "raw" / "edges.jsonl")
    instances = _jsonl(root / "raw" / "instances.jsonl")

    assert len(nodes) == len(dataset.nodes)
    assert len(edges) == len(dataset.edges) > 0
    assert {node["node_type"] for node in nodes} == {
        "diet",
        "additive",
        "substrate",
        "taxon",
        "function",
        "metabolite",
        "host",
        "phenotype",
    }
    assert set(nodes[0]) == {
        "graph_id",
        "node_id",
        "node_type",
        "source_id",
        "attributes",
        "missing_mask",
    }
    assert all(edge["evidence_status"] == "synthetic" for edge in edges)
    assert instances == [
        {
            "graph_id": "synthetic:graph:0001",
            "species": "chicken",
            "gut_segment": "cecum",
            "study_id": "SYNTHETIC_V1",
            "sample_id": "synthetic:sample:0001",
            "scenario_id": "basal",
            "diet_treatment": "synthetic_basal_diet",
            "timepoint": None,
            "is_synthetic": True,
            "schema_version": SCHEMA_VERSION,
            "generator_version": dataset.instances[0].generator_version,
        }
    ]
    assert (root / "raw" / "outputs.jsonl").read_text(encoding="utf-8") == ""


def test_metadata_contains_required_fields(tmp_path: Path) -> None:
    root = export_dataset(generate_synthetic_dataset(), tmp_path / "v1")
    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))

    for name in (
        "dataset_id",
        "schema_version",
        "generator_version",
        "is_synthetic",
        "random_seed",
        "configuration",
        "node_feature_schema",
        "edge_feature_schema",
        "counts",
    ):
        assert name in metadata
    assert metadata["is_synthetic"] is True
    assert metadata["random_seed"] == 42
    assert metadata["schema_version"] == SCHEMA_VERSION
    assert "interaction_type" in metadata["vocabularies"]

    counts = metadata["counts"]["synthetic:graph:0001"]
    nodes = _jsonl(root / "raw" / "nodes.jsonl")
    edges = _jsonl(root / "raw" / "edges.jsonl")
    assert sum(counts["nodes"].values()) == len(nodes)
    assert sum(counts["edges"].values()) == len(edges)


def test_records_are_sorted_as_specified(tmp_path: Path) -> None:
    root = export_dataset(generate_synthetic_dataset(), tmp_path / "v1")
    nodes = _jsonl(root / "raw" / "nodes.jsonl")
    edges = _jsonl(root / "raw" / "edges.jsonl")

    node_keys = [(n["graph_id"], n["node_type"], n["node_id"]) for n in nodes]
    edge_keys = [
        (
            e["graph_id"],
            e["source_type"],
            e["relation_type"],
            e["target_type"],
            e["source_id"],
            e["target_id"],
        )
        for e in edges
    ]
    assert node_keys == sorted(node_keys)
    assert edge_keys == sorted(edge_keys)


def test_files_use_utf8_and_unix_newlines(tmp_path: Path) -> None:
    root = export_dataset(generate_synthetic_dataset(), tmp_path / "v1")
    content = (root / "raw" / "nodes.jsonl").read_bytes()

    assert b"\r\n" not in content
    # Los nombres en español se guardan como UTF-8 legible, no como escapes \\u.
    assert "estándar".encode() in content
    assert b"\\u00" not in content


def test_export_refuses_to_overwrite_by_default(tmp_path: Path) -> None:
    dataset = generate_synthetic_dataset()
    export_dataset(dataset, tmp_path / "v1")

    with pytest.raises(FileExistsError):
        export_dataset(dataset, tmp_path / "v1")
    export_dataset(dataset, tmp_path / "v1", overwrite=True)


# ---------------------------------------------------------------------------
# Criterio 2: misma configuración y semilla producen el mismo resultado
# ---------------------------------------------------------------------------


def test_same_config_and_seed_produce_identical_files(tmp_path: Path) -> None:
    first = export_dataset(generate_synthetic_dataset(), tmp_path / "a")
    second = export_dataset(generate_synthetic_dataset(), tmp_path / "b")

    assert _read_all_bytes(first) == _read_all_bytes(second)


def test_different_seed_produces_different_content(tmp_path: Path) -> None:
    base = export_dataset(generate_synthetic_dataset(), tmp_path / "a")
    other = export_dataset(
        generate_synthetic_dataset(
            SyntheticNodeConfig(random_seed=7), SyntheticEdgeConfig(random_seed=7)
        ),
        tmp_path / "b",
    )

    assert _read_all_bytes(base)["raw/nodes.jsonl"] != _read_all_bytes(other)["raw/nodes.jsonl"]
    metadata = json.loads((other / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["random_seed"] == 7


def test_mismatched_node_and_edge_seeds_are_rejected() -> None:
    with pytest.raises(ValueError, match="semilla"):
        generate_synthetic_dataset(
            SyntheticNodeConfig(random_seed=1), SyntheticEdgeConfig(random_seed=2)
        )


def test_regenerating_from_exported_metadata_reproduces_the_dataset(tmp_path: Path) -> None:
    root = export_dataset(generate_synthetic_dataset(), tmp_path / "a")
    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))

    seed = metadata["random_seed"]
    graph_id = metadata["configuration"]["nodes"]["graph_id"]
    again = export_dataset(
        generate_synthetic_dataset(
            SyntheticNodeConfig(graph_id=graph_id, random_seed=seed),
            SyntheticEdgeConfig(random_seed=seed),
        ),
        tmp_path / "b",
    )
    assert _read_all_bytes(root) == _read_all_bytes(again)


# ---------------------------------------------------------------------------
# Criterio 3: los datos pueden cargarse nuevamente sin pérdida de información
# ---------------------------------------------------------------------------


def test_round_trip_preserves_all_information(tmp_path: Path) -> None:
    dataset = generate_synthetic_dataset()
    loaded = load_dataset(export_dataset(dataset, tmp_path / "v1"))

    assert loaded == dataset


def test_round_trip_export_load_export_is_byte_identical(tmp_path: Path) -> None:
    first = export_dataset(generate_synthetic_dataset(), tmp_path / "a")
    second = export_dataset(load_dataset(first), tmp_path / "b")

    assert _read_all_bytes(first) == _read_all_bytes(second)


def test_round_trip_preserves_outputs_and_missing_values(tmp_path: Path) -> None:
    dataset = generate_synthetic_dataset()
    taxon = next(node for node in dataset.nodes if node.node_type == "taxon")
    missing_taxon = replace(
        taxon,
        attributes={**taxon.attributes, "abundance": None},
        missing_mask={"abundance": True},
    )
    metabolite = next(node for node in dataset.nodes if node.node_type == "metabolite")
    output = OutputRecord(
        graph_id=metabolite.graph_id,
        target_type="metabolite",
        target_id=metabolite.node_id,
        value=12.5,
        measured_or_predicted="synthetic",
        unit="mmol/kg",
        sample_matrix="cecal_content",
    )
    nodes = [missing_taxon if node == taxon else node for node in dataset.nodes]
    modified = SyntheticDataset(
        metadata=dataset.metadata,
        instances=dataset.instances,
        nodes=nodes,
        edges=dataset.edges,
        outputs=[output],
    )

    loaded = load_dataset(export_dataset(modified, tmp_path / "v1"))

    assert loaded == modified
    assert loaded.outputs == [output]
    reloaded_taxon = next(node for node in loaded.nodes if node.node_id == taxon.node_id)
    assert reloaded_taxon.attributes["abundance"] is None
    assert reloaded_taxon.missing_mask == {"abundance": True}


# ---------------------------------------------------------------------------
# Rechazo de datos inválidos
# ---------------------------------------------------------------------------


def test_export_rejects_output_pointing_to_missing_node(tmp_path: Path) -> None:
    dataset = generate_synthetic_dataset()
    bad = replace(
        dataset,
        outputs=[
            OutputRecord(
                graph_id="synthetic:graph:0001",
                target_type="metabolite",
                target_id="synthetic:metabolite:9999",
                value=1.0,
                measured_or_predicted="synthetic",
                unit="mmol/kg",
                sample_matrix="cecal_content",
            )
        ],
    )
    with pytest.raises(DatasetValidationError, match="no existe"):
        export_dataset(bad, tmp_path / "v1")


def test_export_rejects_prediction_without_model_version(tmp_path: Path) -> None:
    dataset = generate_synthetic_dataset()
    metabolite = next(node for node in dataset.nodes if node.node_type == "metabolite")
    bad = replace(
        dataset,
        outputs=[
            OutputRecord(
                graph_id=metabolite.graph_id,
                target_type="metabolite",
                target_id=metabolite.node_id,
                value=1.0,
                measured_or_predicted="predicted",
                unit="mmol/kg",
                sample_matrix="cecal_content",
            )
        ],
    )
    with pytest.raises(DatasetValidationError, match="model_version"):
        export_dataset(bad, tmp_path / "v1")


def test_export_rejects_non_finite_numbers(tmp_path: Path) -> None:
    dataset = generate_synthetic_dataset()
    node = dataset.nodes[0]
    bad_node = replace(node, attributes={**node.attributes, "extra": float("nan")})
    bad = replace(dataset, nodes=[bad_node, *dataset.nodes[1:]])

    with pytest.raises(ValueError):
        export_dataset(bad, tmp_path / "v1")


def test_load_rejects_incompatible_schema_version(tmp_path: Path) -> None:
    root = export_dataset(generate_synthetic_dataset(), tmp_path / "v1")
    metadata_path = root / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["schema_version"] = "9.9.9"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(DatasetFormatError, match="schema_version"):
        load_dataset(root)


def test_load_rejects_missing_file(tmp_path: Path) -> None:
    root = export_dataset(generate_synthetic_dataset(), tmp_path / "v1")
    (root / "raw" / "edges.jsonl").unlink()

    with pytest.raises(DatasetFormatError, match="edges.jsonl"):
        load_dataset(root)


def test_load_rejects_null_identifier(tmp_path: Path) -> None:
    root = export_dataset(generate_synthetic_dataset(), tmp_path / "v1")
    nodes_path = root / "raw" / "nodes.jsonl"
    lines = nodes_path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["node_id"] = None
    lines[0] = json.dumps(first)
    nodes_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(DatasetFormatError, match="node_id"):
        load_dataset(root)


def test_load_rejects_edge_to_unknown_node(tmp_path: Path) -> None:
    root = export_dataset(generate_synthetic_dataset(), tmp_path / "v1")
    edges_path = root / "raw" / "edges.jsonl"
    lines = edges_path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["target_id"] = "synthetic:unknown:0001"
    lines[0] = json.dumps(first)
    edges_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(DatasetValidationError, match="destino no existe"):
        load_dataset(root)


# ---------------------------------------------------------------------------
# Escenarios de DS-04
# ---------------------------------------------------------------------------


def test_scenario_dataset_exports_both_scenarios(tmp_path: Path) -> None:
    root = export_dataset(generate_scenario_dataset(), tmp_path / "v1")
    instances = _jsonl(root / "raw" / "instances.jsonl")

    assert [instance["graph_id"] for instance in instances] == [
        SCENARIO_BASAL_GRAPH_ID,
        SCENARIO_INTERVENED_GRAPH_ID,
    ]
    assert [instance["scenario_id"] for instance in instances] == ["basal", "intervention"]
    assert instances[0]["sample_id"] == instances[1]["sample_id"]
    assert instances[1]["diet_treatment"].endswith(
        f"{INTERVENTION_VARIABLE}={INTERVENTION_INTERVENED_VALUE}"
    )
    assert all(instance["species"] == "chicken" for instance in instances)

    nodes = _jsonl(root / "raw" / "nodes.jsonl")
    assert {node["graph_id"] for node in nodes} == {
        SCENARIO_BASAL_GRAPH_ID,
        SCENARIO_INTERVENED_GRAPH_ID,
    }


def test_scenario_dataset_matches_scenario_builders() -> None:
    dataset = generate_scenario_dataset()
    basal = build_basal_scenario()
    intervened = build_intervened_scenario()

    assert len(dataset.nodes) == len(basal.nodes) + len(intervened.nodes)
    assert len(dataset.edges) == len(basal.edges) + len(intervened.edges)
    scenarios = dataset.metadata["configuration"]["scenarios"]
    assert [entry["intervention_variable"] for entry in scenarios] == [None, INTERVENTION_VARIABLE]
    assert dataset.metadata["counts"].keys() == {
        SCENARIO_BASAL_GRAPH_ID,
        SCENARIO_INTERVENED_GRAPH_ID,
    }


def test_scenario_dataset_is_reproducible(tmp_path: Path) -> None:
    first = export_dataset(generate_scenario_dataset(), tmp_path / "a")
    second = export_dataset(generate_scenario_dataset(), tmp_path / "b")

    assert _read_all_bytes(first) == _read_all_bytes(second)


def test_scenario_dataset_round_trip(tmp_path: Path) -> None:
    dataset = generate_scenario_dataset()

    assert load_dataset(export_dataset(dataset, tmp_path / "v1")) == dataset
