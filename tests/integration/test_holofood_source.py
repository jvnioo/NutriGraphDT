"""La fuente real D1 (HoloFood) pasa por los loaders y el pipeline del módulo de datos.

Usa `tests/fixtures/holofood/`, un subconjunto de pocos animales extraído con
`scripts/fetch_holofood.py` (ver el README de esa carpeta), con la configuración de
`configs/sources.json` tal como está registrada. Si la descarga completa existe en
`data/raw/D1_holofood/`, también comprueba sus checksums y la procesa entera.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import pytest

from nutrigraphdt.data.config import load_sources
from nutrigraphdt.data.loaders import (
    AbundanceLoader,
    MetaboliteLoader,
    MetadataLoader,
    SourceMetadata,
)
from nutrigraphdt.data.pipeline import DataPipeline

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "holofood"
RAW = REPO_ROOT / "data" / "raw" / "D1_holofood"
SOURCES = load_sources(REPO_ROOT / "configs" / "sources.json")

FIXTURE_FILES = {
    "D1_holofood": "abundance_ssu_caecum.tsv",
    "D1_holofood_scfa_content": "scfa_caecum_content.tsv",
    "D1_holofood_metadata": "metadata.tsv",
}


def _fixture_source(source_id: str) -> SourceMetadata:
    return dataclasses.replace(
        SOURCES[source_id], path_or_url=str(FIXTURES / FIXTURE_FILES[source_id])
    )


def _animals() -> list[str]:
    header = (FIXTURES / FIXTURE_FILES["D1_holofood"]).read_text(encoding="utf-8").split("\n")[0]
    return header.split("\t")[1:]


def test_registered_holofood_sources_point_to_the_fetch_output() -> None:
    for source_id in (*FIXTURE_FILES, "D1_holofood_scfa_tissue"):
        metadata = SOURCES[source_id]
        assert metadata.path_or_url is not None
        assert metadata.path_or_url.startswith("data/raw/D1_holofood/")
        assert not metadata.is_synthetic
        assert (metadata.species, metadata.gut_segment) == ("chicken", "cecum")


KNOWN_NAME_COLLISIONS = ("'Actinobacteria'", "'Deferribacteres'")
"""Filo y clase con el mismo nombre en SILVA: `AbundanceLoader` reduce ambos linajes al mismo
`taxon_id` y suma sus conteos (ver docs/holofood-source.md, "Decisiones y cautelas")."""


def test_abundances_load_as_relative_abundance_per_animal() -> None:
    payload = AbundanceLoader(_fixture_source("D1_holofood")).load()
    for error in payload.extra["errors"]:
        assert "aparece más de una vez" in error
        assert any(name in error for name in KNOWN_NAME_COLLISIONS), error
    totals: dict[str, float] = defaultdict(float)
    for record in payload.raw_data:
        assert record["unit"] == "relative_abundance"
        totals[record["sample_id"]] += record["value"]
    assert sorted(totals) == sorted(_animals())
    assert all(math.isclose(total, 1.0, rel_tol=1e-9) for total in totals.values())


def test_caecal_scfa_map_to_canonical_ids_in_mmol_per_kg() -> None:
    payload = MetaboliteLoader(_fixture_source("D1_holofood_scfa_content")).load()
    assert not payload.extra["errors"]
    canonical = {record["canonical_id"] for record in payload.raw_data}
    assert {"acetate", "propionate", "butyrate", "isobutyrate", "valerate", "isovalerate"} <= (
        canonical
    )
    assert {record["unit"] for record in payload.raw_data} == {"mmol_kg"}
    assert {record["sample_id"] for record in payload.raw_data} <= set(_animals())


def test_metadata_declares_diet_and_individual_phenotype() -> None:
    payload = MetadataLoader(_fixture_source("D1_holofood_metadata")).load()
    assert not payload.extra["errors"]
    by_field = {record["field"]: record for record in payload.raw_data}
    assert by_field["diet_treatment_name"]["field_type"] == "diet"
    assert by_field["body_weight_g"]["field_type"] == "phenotype"
    assert by_field["body_weight_g"]["unit"] == "g"
    assert by_field["sex"]["field_type"] == "categorical"
    assert {"animal_code", "pen_code"}.isdisjoint(by_field)
    assert {record["sample_id"] for record in payload.raw_data} == set(_animals())


def test_pipeline_builds_real_instances_from_the_abundances() -> None:
    sources = {"D1_holofood": _fixture_source("D1_holofood")}
    dataset = DataPipeline(sources).run(["D1_holofood"]).dataset
    assert sorted(instance.sample_id for instance in dataset.instances) == sorted(_animals())
    assert all(not instance.is_synthetic for instance in dataset.instances)
    assert {feature.node_type for feature in dataset.features} == {"taxon"}
    assert not dataset.validate()


@pytest.mark.skipif(
    not (RAW / "manifest.json").exists(),
    reason="Descarga completa ausente; ejecute scripts/fetch_holofood.py.",
)
def test_full_download_matches_its_manifest_and_runs_through_the_pipeline() -> None:
    manifest = json.loads((RAW / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        digest = hashlib.sha256((RAW / entry["file"]).read_bytes()).hexdigest()
        assert digest == entry["sha256"], entry["file"]
    sources = {
        "D1_holofood": dataclasses.replace(
            SOURCES["D1_holofood"], path_or_url=str(RAW / "abundance_ssu_caecum.tsv")
        )
    }
    dataset = DataPipeline(sources).run(["D1_holofood"]).dataset
    expected = manifest["counts"]["animals_with_caecal_metagenome"]
    assert len(dataset.instances) == expected
