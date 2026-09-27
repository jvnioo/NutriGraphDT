"""Pruebas de integración de exportación, carga y round-trip del dataset sintético (DS-06).

Ejercitan el flujo completo `generar -> exportar -> cargar -> exportar` sobre el disco,
para varias semillas y configuraciones, y verifican que un archivo dañado o incompleto se
rechace con un error explícito en lugar de cargarse en silencio.

Siguen el formato de `docs/synthetic-dataset-spec.md` ("Serialización y organización de
archivos"). La conversión a `HeteroData` y los archivos `.pt` están fuera del alcance actual
de DS-05, por lo que no se prueban aquí.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from nutrigraphdt.data.synthetic import NodeCountConfig, SyntheticEdgeConfig, SyntheticNodeConfig
from nutrigraphdt.data.synthetic.export import (
    DatasetFormatError,
    DatasetValidationError,
    OutputRecord,
    SyntheticDataset,
    export_dataset,
    generate_scenario_dataset,
    generate_synthetic_dataset,
    load_dataset,
)

RAW_FILES = ("instances.jsonl", "nodes.jsonl", "edges.jsonl", "outputs.jsonl")
ALL_FILES = ("metadata.json", *(f"raw/{name}" for name in RAW_FILES))

# Campos exactos de cada línea JSONL según los contratos de la especificación.
NODE_FIELDS = {"graph_id", "node_id", "node_type", "source_id", "attributes", "missing_mask"}
EDGE_FIELDS = {
    "graph_id",
    "source_type",
    "source_id",
    "relation_type",
    "target_type",
    "target_id",
    "evidence_id",
    "evidence_status",
    "evidence_method",
    "attributes",
}
INSTANCE_FIELDS = {
    "graph_id",
    "species",
    "gut_segment",
    "study_id",
    "sample_id",
    "scenario_id",
    "diet_treatment",
    "timepoint",
    "is_synthetic",
    "schema_version",
    "generator_version",
}
METADATA_FIELDS = {
    "dataset_id",
    "schema_version",
    "generator_version",
    "is_synthetic",
    "random_seed",
    "configuration",
    "node_feature_schema",
    "edge_feature_schema",
    "counts",
}

SEEDS = (0, 42, 2026)
PROFILES: dict[str, NodeCountConfig] = {
    "default": NodeCountConfig(),
    "large": NodeCountConfig(
        diet=2, additive=3, substrate=9, taxon=15, function=12, metabolite=7, host=1, phenotype=5
    ),
    "sparse": NodeCountConfig(
        diet=1, additive=0, substrate=3, taxon=4, function=0, metabolite=2, host=1, phenotype=0
    ),
}
MATRIX = [
    pytest.param(seed, profile, id=f"seed{seed}-{profile}")
    for seed in SEEDS
    for profile in PROFILES
]


def make_dataset(seed: int, profile: str) -> SyntheticDataset:
    return generate_synthetic_dataset(
        SyntheticNodeConfig(counts=PROFILES[profile], random_seed=seed),
        SyntheticEdgeConfig(random_seed=seed),
    )


def file_digests(root: Path) -> dict[str, str]:
    """SHA-256 de cada archivo del dataset exportado."""
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in ALL_FILES}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def records(dataset: SyntheticDataset) -> dict[str, Any]:
    return {
        "metadata": dataset.metadata,
        "instances": [i.to_dict() for i in dataset.instances],
        "nodes": [n.to_dict() for n in dataset.nodes],
        "edges": [e.to_dict() for e in dataset.edges],
        "outputs": [o.to_dict() for o in dataset.outputs],
    }


# Atributo obligatorio que se marca como ausente en el primer nodo de cada tipo, para ejercitar
# `null` + `missing_mask` a través del disco.
MASKED_ATTRIBUTE: dict[str, str] = {
    "diet": "source_version",
    "additive": "dose",
    "substrate": "quantity",
    "taxon": "abundance",
    "function": "annotation_value",
    "metabolite": "concentration",
    "host": "covariates",
    "phenotype": "value",
}


def with_missing_values_and_outputs(dataset: SyntheticDataset) -> SyntheticDataset:
    """Agrega valores ausentes enmascarados y salidas sintéticas y predichas.

    El generador no produce ninguno de los dos, pero el contrato los admite. Sin ellos, el
    round-trip de `missing_mask` y de `outputs.jsonl` quedaría sin ejercitar.
    """
    masked_types: set[str] = set()
    nodes = []
    for node in dataset.nodes:
        attribute = MASKED_ATTRIBUTE[node.node_type]
        if node.node_type not in masked_types:
            masked_types.add(node.node_type)
            node = replace(
                node,
                attributes={**node.attributes, attribute: None},
                missing_mask={**node.missing_mask, attribute: True},
            )
        nodes.append(node)
    outputs = [
        OutputRecord(
            graph_id=node.graph_id,
            target_type=node.node_type,
            target_id=node.node_id,
            value=float(index),
            measured_or_predicted="synthetic" if node.node_type == "metabolite" else "predicted",
            unit="synthetic_unit",
            sample_matrix="synthetic_matrix",
            model_version=None if node.node_type == "metabolite" else "synthetic-model-0",
        )
        for index, node in enumerate(nodes)
        if node.node_type in {"metabolite", "phenotype"}
    ]
    return SyntheticDataset(
        metadata=dataset.metadata,
        instances=dataset.instances,
        nodes=nodes,
        edges=dataset.edges,
        outputs=outputs,
    )


@pytest.fixture
def exported(tmp_path: Path) -> Path:
    """Un dataset estándar exportado en un directorio temporal."""
    return export_dataset(make_dataset(42, "default"), tmp_path / "dataset")


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_export_then_load_returns_the_same_dataset(tmp_path: Path, seed: int, profile: str) -> None:
    dataset = make_dataset(seed, profile)

    loaded = load_dataset(export_dataset(dataset, tmp_path / "dataset"))

    assert loaded == dataset
    assert records(loaded) == records(dataset)


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_export_load_export_is_byte_identical(tmp_path: Path, seed: int, profile: str) -> None:
    first = export_dataset(make_dataset(seed, profile), tmp_path / "first")
    second = export_dataset(load_dataset(first), tmp_path / "second")

    assert file_digests(first) == file_digests(second)


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_round_trip_preserves_missing_values_and_outputs(
    tmp_path: Path, seed: int, profile: str
) -> None:
    dataset = with_missing_values_and_outputs(make_dataset(seed, profile))

    first = export_dataset(dataset, tmp_path / "first")
    loaded = load_dataset(first)
    second = export_dataset(loaded, tmp_path / "second")

    assert loaded == dataset
    assert loaded.outputs == dataset.outputs and loaded.outputs
    masked = [(n.node_id, a) for n in loaded.nodes for a, flag in n.missing_mask.items() if flag]
    assert masked == [(n.node_id, a) for n in dataset.nodes for a, f in n.missing_mask.items() if f]
    for node in loaded.nodes:
        for attribute, flag in node.missing_mask.items():
            if flag:
                assert node.attributes[attribute] is None
    assert file_digests(first) == file_digests(second)


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_independent_generations_export_identical_files(
    tmp_path: Path, seed: int, profile: str
) -> None:
    """Regla 12: misma versión, configuración y semilla producen el mismo contenido."""
    first = export_dataset(make_dataset(seed, profile), tmp_path / "first")
    second = export_dataset(make_dataset(seed, profile), tmp_path / "second")

    assert file_digests(first) == file_digests(second)


def test_different_seeds_export_different_node_files(tmp_path: Path) -> None:
    first = file_digests(export_dataset(make_dataset(0, "default"), tmp_path / "a"))
    second = file_digests(export_dataset(make_dataset(42, "default"), tmp_path / "b"))

    assert first["raw/nodes.jsonl"] != second["raw/nodes.jsonl"]
    assert first["raw/instances.jsonl"] == second["raw/instances.jsonl"]


def test_scenario_dataset_round_trip_keeps_both_scenarios(tmp_path: Path) -> None:
    dataset = generate_scenario_dataset()

    first = export_dataset(dataset, tmp_path / "first")
    loaded = load_dataset(first)
    second = export_dataset(loaded, tmp_path / "second")

    assert loaded == dataset
    assert file_digests(first) == file_digests(second)
    assert {i.scenario_id for i in loaded.instances} == {"basal", "intervention"}


# ---------------------------------------------------------------------------
# Formato de los archivos exportados
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_every_jsonl_line_has_exactly_the_contract_fields(
    tmp_path: Path, seed: int, profile: str
) -> None:
    root = export_dataset(make_dataset(seed, profile), tmp_path / "dataset")

    for line in read_jsonl(root / "raw" / "nodes.jsonl"):
        assert set(line) == NODE_FIELDS
    for line in read_jsonl(root / "raw" / "edges.jsonl"):
        assert set(line) == EDGE_FIELDS
    for line in read_jsonl(root / "raw" / "instances.jsonl"):
        assert set(line) == INSTANCE_FIELDS
        assert line["is_synthetic"] is True
    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    assert set(metadata) >= METADATA_FIELDS


def test_exported_counts_match_file_contents(exported: Path) -> None:
    metadata = json.loads((exported / "metadata.json").read_text(encoding="utf-8"))
    nodes = read_jsonl(exported / "raw" / "nodes.jsonl")
    edges = read_jsonl(exported / "raw" / "edges.jsonl")

    for graph_id, counts in metadata["counts"].items():
        assert sum(counts["nodes"].values()) == sum(n["graph_id"] == graph_id for n in nodes)
        assert sum(counts["edges"].values()) == sum(e["graph_id"] == graph_id for e in edges)


@pytest.mark.parametrize(("seed", "profile"), MATRIX)
def test_exported_files_keep_synthetic_labels(tmp_path: Path, seed: int, profile: str) -> None:
    """Las etiquetas sintéticas sobreviven a la serialización, no solo en memoria."""
    root = export_dataset(make_dataset(seed, profile), tmp_path / "dataset")
    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))

    assert metadata["is_synthetic"] is True
    assert {n["source_id"] for n in read_jsonl(root / "raw" / "nodes.jsonl")} == {"SYNTHETIC_V1"}
    for edge in read_jsonl(root / "raw" / "edges.jsonl"):
        assert (edge["evidence_id"], edge["evidence_status"], edge["evidence_method"]) == (
            "SYNTHETIC_V1",
            "synthetic",
            "synthetic_generator",
        )
    loaded = load_dataset(root)
    assert {n.source_id for n in loaded.nodes} == {"SYNTHETIC_V1"}
    assert {e.evidence_status for e in loaded.edges} <= {"synthetic"}


def test_exported_records_follow_the_specified_order(tmp_path: Path) -> None:
    root = export_dataset(
        with_missing_values_and_outputs(make_dataset(42, "large")), tmp_path / "dataset"
    )
    raw = root / "raw"
    node_keys = [
        (n["graph_id"], n["node_type"], n["node_id"]) for n in read_jsonl(raw / "nodes.jsonl")
    ]
    edge_keys = [
        (
            e["graph_id"],
            e["source_type"],
            e["relation_type"],
            e["target_type"],
            e["source_id"],
            e["target_id"],
        )
        for e in read_jsonl(raw / "edges.jsonl")
    ]
    output_keys = [
        (o["graph_id"], o["target_type"], o["target_id"]) for o in read_jsonl(raw / "outputs.jsonl")
    ]
    instance_keys = [i["graph_id"] for i in read_jsonl(raw / "instances.jsonl")]

    assert node_keys == sorted(node_keys)
    assert edge_keys == sorted(edge_keys)
    assert output_keys == sorted(output_keys) and output_keys
    assert instance_keys == sorted(instance_keys)


def test_edges_file_only_references_nodes_in_nodes_file(exported: Path) -> None:
    nodes = {
        (n["graph_id"], n["node_type"], n["node_id"])
        for n in read_jsonl(exported / "raw" / "nodes.jsonl")
    }
    for edge in read_jsonl(exported / "raw" / "edges.jsonl"):
        assert (edge["graph_id"], edge["source_type"], edge["source_id"]) in nodes
        assert (edge["graph_id"], edge["target_type"], edge["target_id"]) in nodes


def test_files_do_not_depend_on_the_output_location(tmp_path: Path) -> None:
    """Exportar a rutas distintas no cambia el contenido: no se guardan rutas locales."""
    near = export_dataset(make_dataset(42, "default"), tmp_path / "a")
    far = export_dataset(make_dataset(42, "default"), tmp_path / "nested" / "deeper" / "b")

    assert file_digests(near) == file_digests(far)
    assert str(tmp_path) not in (near / "metadata.json").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Archivos dañados o incompletos
# ---------------------------------------------------------------------------


def _rewrite_first_line(path: Path, change: dict[str, Any]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    record.update(change)
    lines[0] = json.dumps(record, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


@pytest.mark.parametrize("missing", ALL_FILES)
def test_missing_file_is_rejected(exported: Path, missing: str) -> None:
    (exported / missing).unlink()

    with pytest.raises(DatasetFormatError):
        load_dataset(exported)


def test_malformed_json_line_is_rejected(exported: Path) -> None:
    path = exported / "raw" / "nodes.jsonl"
    path.write_text(path.read_text(encoding="utf-8") + "{no es json\n", encoding="utf-8")

    with pytest.raises(DatasetFormatError, match="JSON"):
        load_dataset(exported)


def test_blank_line_is_rejected(exported: Path) -> None:
    path = exported / "raw" / "edges.jsonl"
    path.write_text("\n" + path.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(DatasetFormatError, match="vacía"):
        load_dataset(exported)


def test_non_finite_number_in_file_is_rejected(exported: Path) -> None:
    path = exported / "raw" / "nodes.jsonl"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace('"abundance":', '"abundance":NaN,"_x":', 1), encoding="utf-8")

    with pytest.raises(DatasetFormatError):
        load_dataset(exported)


@pytest.mark.parametrize(
    ("file_name", "change", "error"),
    [
        ("nodes.jsonl", {"node_id": None}, DatasetFormatError),
        ("nodes.jsonl", {"attributes": None}, DatasetFormatError),
        ("edges.jsonl", {"evidence_id": None}, DatasetFormatError),
        ("edges.jsonl", {"target_id": "synthetic:taxon:9999"}, DatasetValidationError),
        ("edges.jsonl", {"relation_type": "produces"}, DatasetValidationError),
        ("edges.jsonl", {"evidence_status": "observed"}, DatasetValidationError),
        ("instances.jsonl", {"is_synthetic": False}, DatasetValidationError),
        ("instances.jsonl", {"scenario_id": "baseline"}, DatasetValidationError),
    ],
    ids=[
        "null-node-id",
        "null-attributes",
        "null-evidence-id",
        "edge-to-unknown-node",
        "disallowed-relation",
        "non-synthetic-evidence",
        "instance-not-synthetic",
        "unknown-scenario",
    ],
)
def test_tampered_record_is_rejected(
    exported: Path, file_name: str, change: dict[str, Any], error: type[Exception]
) -> None:
    _rewrite_first_line(exported / "raw" / file_name, change)

    with pytest.raises(error):
        load_dataset(exported)


def test_incompatible_schema_version_is_rejected(exported: Path) -> None:
    path = exported / "metadata.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata["schema_version"] = "2.0.0"
    path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(DatasetFormatError, match="schema_version"):
        load_dataset(exported)


def test_existing_export_is_not_overwritten_by_default(exported: Path) -> None:
    before = file_digests(exported)

    with pytest.raises(FileExistsError):
        export_dataset(make_dataset(0, "default"), exported)
    assert file_digests(exported) == before


def test_invalid_dataset_is_not_written(tmp_path: Path) -> None:
    """La validación ocurre antes de escribir: un dataset inválido no deja archivos."""
    invalid = generate_synthetic_dataset(
        SyntheticNodeConfig(graph_id="", random_seed=42), SyntheticEdgeConfig(random_seed=42)
    )
    target = tmp_path / "dataset"

    with pytest.raises(DatasetValidationError):
        export_dataset(invalid, target)
    assert not (target / "metadata.json").exists()
