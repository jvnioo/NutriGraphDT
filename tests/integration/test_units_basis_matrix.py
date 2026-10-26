"""Unidades, base de medición y matriz de la muestra del contrato de datos v2 §4 (#148).

- Notación canónica de máquina (`mmol_kg`, `g_kg`…) en registros y metadatos; la forma con barra
  es solo una etiqueta de presentación.
- `basis` (`wet` o `dry`) en los nodos `metabolite` y en las salidas; D1 declara `wet`.
- `sample_matrix` con vocabulario cerrado en F4: solo `caecum_content`; `caecum_tissue` se
  informa como hallazgo (NOD-11).

Usa el fixture real de D1 (`tests/fixtures/holofood/`) y el generador sintético.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

import pytest

from nutrigraphdt.data.config import load_sources
from nutrigraphdt.data.integration import attach_sample_context
from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader
from nutrigraphdt.data.pipeline import DataPipeline
from nutrigraphdt.data.schema import (
    CANONICAL_UNITS,
    UNIT_LABELS,
    NormalizedTabularDataset,
    NormalizedTargetRecord,
    unit_label,
)
from nutrigraphdt.data.synthetic import generate_synthetic_dataset
from nutrigraphdt.data.synthetic.export import OutputRecord
from nutrigraphdt.graph.builder import records_from_tables
from nutrigraphdt.graph.validation import find_node_findings, find_output_findings

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "holofood"
SOURCES = load_sources(REPO_ROOT / "configs" / "sources.json")
SAMPLE = "SAMEA112904764"


def _source(source_id: str, file_name: str):  # type: ignore[no-untyped-def]
    return dataclasses.replace(SOURCES[source_id], path_or_url=str(FIXTURES / file_name))


@pytest.fixture(scope="module")
def tables() -> NormalizedTabularDataset:
    abundance = _source("D1_holofood", "abundance_ssu_caecum.tsv")
    base = DataPipeline({"D1_holofood": abundance}).run(["D1_holofood"]).dataset
    integrated, _ = attach_sample_context(
        base,
        metadata=MetadataLoader(_source("D1_holofood_metadata", "metadata.tsv")).load(),
        metabolites=MetaboliteLoader(
            _source("D1_holofood_scfa_content", "scfa_caecum_content.tsv")
        ).load(),
    )
    return integrated


def _with_targets(tables: NormalizedTabularDataset, **changes: object) -> NormalizedTabularDataset:
    targets = [
        dataclasses.replace(t, **changes) if t.graph_id.endswith(SAMPLE) else t
        for t in tables.targets
    ]
    return dataclasses.replace(tables, targets=targets)


# ---------------------------------------------------------------------------
# D1: base húmeda y matriz `caecum_content`
# ---------------------------------------------------------------------------


def test_d1_targets_declare_wet_basis_and_caecum_content(
    tables: NormalizedTabularDataset,
) -> None:
    assert tables.targets
    assert {t.basis for t in tables.targets} == {"wet"}
    assert {t.sample_matrix for t in tables.targets} == {"caecum_content"}
    assert {t.unit for t in tables.targets} == {"mmol_kg"}


def test_d1_metabolites_and_outputs_carry_basis(tables: NormalizedTabularDataset) -> None:
    records = records_from_tables(tables)
    metabolites = [n for n in records.nodes if n["node_type"] == "metabolite"]
    assert metabolites
    assert {n["attributes"]["basis"] for n in metabolites} == {"wet"}
    assert {o["basis"] for o in records.outputs} == {"wet"}
    assert records.metadata["vocabularies"]["sample_matrix"] == ["caecum_content"]
    findings = find_node_findings(records.instances, records.nodes, metadata=records.metadata)
    assert not [f for f in findings if f.rule_id == "NOD-11"]


def test_caecum_tissue_sample_is_reported_in_f4(tables: NormalizedTabularDataset) -> None:
    records = records_from_tables(_with_targets(tables, sample_matrix="caecum_tissue"))
    findings = find_node_findings(records.instances, records.nodes, metadata=records.metadata)
    nod11 = [f for f in findings if f.rule_id == "NOD-11"]
    assert nod11
    assert {f.location["attribute"] for f in nod11} == {"sample_matrix"}
    assert {f.graph_id for f in nod11} == {f"D1_holofood:{SAMPLE}"}
    assert all("caecum_tissue" in f.observed for f in nod11)


def test_undeclared_basis_is_missing_not_invented(tables: NormalizedTabularDataset) -> None:
    records = records_from_tables(_with_targets(tables, basis=None))
    node = next(
        n
        for n in records.nodes
        if n["node_type"] == "metabolite" and n["graph_id"].endswith(SAMPLE)
    )
    assert node["attributes"]["basis"] is None
    assert node["missing_mask"]["basis"] is True


def test_basis_vocabulary_is_closed() -> None:
    record = dict(
        graph_id="g",
        target_type="scfa_concentration",
        target_id="acetate",
        value=1.0,
        unit="mmol_kg",
        sample_matrix="caecum_content",
        measured_or_predicted="measured",
    )
    assert NormalizedTargetRecord(**record, basis="dry").basis == "dry"  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="basis"):
        NormalizedTargetRecord(**record, basis="fresh")  # type: ignore[arg-type]

    output = {
        "graph_id": "g",
        "target_type": "metabolite",
        "target_id": "m",
        "value": 1.0,
        "measured_or_predicted": "measured",
        "unit": "mmol_kg",
        "sample_matrix": "caecum_content",
        "model_version": None,
        "basis": "fresh",
    }
    findings = find_output_findings([output], [], [])
    assert [f.location.get("field") for f in findings if f.rule_id == "OUT-04"] == ["basis"]


def test_outputs_without_basis_still_load() -> None:
    """Las salidas escritas antes de #148 no tienen `basis`."""
    legacy = {
        "graph_id": "g",
        "target_type": "metabolite",
        "target_id": "m",
        "value": 1.0,
        "measured_or_predicted": "synthetic",
        "unit": "mmol_kg",
        "sample_matrix": "cecal_content",
        "model_version": None,
    }
    assert OutputRecord.from_dict(legacy).basis is None


# ---------------------------------------------------------------------------
# Notación canónica de unidades
# ---------------------------------------------------------------------------


def _units(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"unit", "dose_unit", "abundance_unit"} and isinstance(item, str):
                found.add(item)
            else:
                found |= _units(item)
    elif isinstance(value, list):
        for item in value:
            found |= _units(item)
    return found


def test_synthetic_records_use_machine_notation() -> None:
    dataset = generate_synthetic_dataset()
    records = [
        *(node.to_dict() for node in dataset.nodes),
        *(edge.to_dict() for edge in dataset.edges),
        *(output.to_dict() for output in dataset.outputs),
    ]
    units = _units(records)
    assert units
    assert not {unit for unit in units if "/" in unit}
    # Las unidades de magnitudes físicas son canónicas; `CPM` y `binary` son anotaciones.
    assert units - {"CPM", "binary"} <= CANONICAL_UNITS
    metabolites = [n for n in dataset.nodes if n.node_type == "metabolite"]
    assert {n.attributes["basis"] for n in metabolites} == {"wet"}
    assert {o.basis for o in dataset.outputs} == {"wet"}


def test_presentation_labels_are_separate() -> None:
    assert unit_label("g_kg") == "g/kg"
    assert unit_label("mmol_kg") == "mmol/kg"
    assert unit_label("g") == "g"
    assert set(UNIT_LABELS) <= CANONICAL_UNITS


MACHINE_UNIT = re.compile(r"`(?:g|mg|mmol|CFU|MJ|ug)/(?:kg|mL)`")


@pytest.mark.parametrize(
    "path",
    [
        "docs/synthetic-dataset/synthetic-dataset-dictionary.md",
        "docs/graph/graph-schema-v1.md",
    ],
)
def test_contracts_do_not_use_slash_units_as_machine_values(path: str) -> None:
    """Criterio de #148: ningún contrato usa `g/kg` como valor de máquina (entre comillas de
    código). La etiqueta con barra sigue permitida como texto de presentación."""
    text = (REPO_ROOT / path).read_text(encoding="utf-8")
    assert not MACHINE_UNIT.findall(text)


def test_synthetic_metadata_declares_basis_vocabulary() -> None:
    dataset = generate_synthetic_dataset()
    vocabularies = json.loads(json.dumps(dataset.metadata))["vocabularies"]
    assert vocabularies["basis"] == ["dry", "wet"]
    assert "sample_matrix" not in vocabularies
