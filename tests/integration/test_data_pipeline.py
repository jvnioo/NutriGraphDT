"""Tests de integración de `DataPipeline`: ingesta → preprocesamiento → tablas (A34-4)."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from nutrigraphdt.data.config import load_sources
from nutrigraphdt.data.loaders.abundance import AbundanceLoader
from nutrigraphdt.data.loaders.base import IngestionPayload, LoaderRegistry, SourceMetadata
from nutrigraphdt.data.pipeline import REPORT_FILENAME, DataPipeline, default_loader_registry
from nutrigraphdt.data.preprocessors import (
    UNKNOWN_CONTEXT,
    AbundancePreprocessingConfig,
)
from nutrigraphdt.data.synthetic import export_dataset, generate_scenario_dataset

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "abundance"
TABLE_FILES = ("instances.tsv", "features.tsv", "edges.tsv", "targets.tsv", "metadata.json")


def _synthetic_source(path: Path, **options: Any) -> SourceMetadata:
    """Fuente sintética registrada, con la ruta apuntando a ``path``."""
    registered = load_sources(REPO_ROOT / "configs" / "sources.json")["synthetic-v1"]
    return replace(
        registered,
        path_or_url=str(path),
        options={**registered.options, **options},
    )


def _fixture_source(source_id: str = "fixture_rows", **options: Any) -> SourceMetadata:
    return SourceMetadata(
        source_id=source_id,
        name="Tabla de abundancias de prueba",
        species="chicken",
        gut_segment="cecum",
        data_types=("microbiome",),
        format="tsv",
        path_or_url=str(FIXTURES / "taxa_rows.tsv"),
        is_synthetic=False,
        options=options,
    )


@pytest.fixture
def sources(tmp_path: Path) -> dict[str, SourceMetadata]:
    # La ruta no existe: la fuente sintética se genera en memoria (generate_if_missing).
    return {
        "synthetic-v1": _synthetic_source(tmp_path / "absent"),
        "fixture_rows": _fixture_source(),
    }


class SpyLoader(AbundanceLoader):
    """`AbundanceLoader` que anota las fuentes que carga."""

    calls: list[str] = []

    def load(self, source_path: Path | str | None = None) -> IngestionPayload:
        SpyLoader.calls.append(self.metadata.source_id)
        return super().load(source_path)


def _spy_registry() -> LoaderRegistry:
    SpyLoader.calls = []
    registry = LoaderRegistry()
    for fmt in ("jsonl", "tsv", "csv"):
        registry.register_format(fmt, SpyLoader)
    return registry


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _digest(directory: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.iterdir())
    }


# ---------------------------------------------------------------------------
# Dataset sintético
# ---------------------------------------------------------------------------


class TestSyntheticSource:
    def test_generated_dataset_keeps_scenario_context(
        self, sources: dict[str, SourceMetadata]
    ) -> None:
        result = DataPipeline(sources).run(["synthetic-v1"])
        expected = {inst.graph_id: inst for inst in generate_scenario_dataset().instances}

        assert [inst.graph_id for inst in result.dataset.instances] == sorted(expected)
        for instance in result.dataset.instances:
            context = expected[instance.graph_id]
            assert instance.sample_id == context.sample_id
            assert instance.study_id == context.study_id
            assert instance.scenario_id == context.scenario_id
            assert instance.diet_treatment == context.diet_treatment
            assert instance.is_synthetic is True
            assert instance.source_id == "synthetic-v1"
        assert {inst.scenario_id for inst in result.dataset.instances} == {"basal", "intervention"}

    def test_features_match_loader_output(self, sources: dict[str, SourceMetadata]) -> None:
        payload = AbundanceLoader(sources["synthetic-v1"]).load()
        result = DataPipeline(sources).run(["synthetic-v1"])
        values = {(f.graph_id, f.node_id): f.value for f in result.dataset.features}
        assert values == {(r["graph_id"], r["taxon_id"]): r["value"] for r in payload.raw_data}
        assert result.dataset.validate() == []
        assert result.reports["synthetic-v1"].discarded == []

    def test_dataset_on_disk_gives_same_tables(
        self, tmp_path: Path, sources: dict[str, SourceMetadata]
    ) -> None:
        directory = tmp_path / "synthetic_v1"
        export_dataset(generate_scenario_dataset(), directory)
        on_disk = {"synthetic-v1": _synthetic_source(directory)}

        generated = DataPipeline(sources).run(["synthetic-v1"]).dataset
        loaded = DataPipeline(on_disk).run(["synthetic-v1"]).dataset
        assert loaded.instances == generated.instances
        assert loaded.features == generated.features

    def test_registered_sources_file(self, tmp_path: Path) -> None:
        registry = load_sources(REPO_ROOT / "configs" / "sources.json")
        registry["synthetic-v1"] = replace(
            registry["synthetic-v1"], path_or_url=str(tmp_path / "absent")
        )
        result = DataPipeline(registry).run(["synthetic-v1"])
        assert result.dataset.metadata["counts"] == {
            "instances": 2,
            "features": 20,
            "edges": 0,
            "targets": 0,
        }


class UnknownGraphLoader(AbundanceLoader):
    """Devuelve un grafo sintético que no existe en el dataset de escenarios."""

    def load(self, source_path: Path | str | None = None) -> IngestionPayload:
        record = {
            "graph_id": "synthetic:scenario:other:0001",
            "sample_id": "synthetic:sample:0001",
            "taxon_id": "synthetic:taxon:a",
            "taxon_level": "genus",
            "value": 1.0,
            "unit": "relative_abundance",
        }
        return IngestionPayload(
            metadata=self.metadata,
            raw_data=[record],
            records_count=1,
            extra={"source_path": "generated", "errors": []},
        )


def test_synthetic_graph_without_context_is_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    registry = LoaderRegistry()
    registry.register_format("jsonl", UnknownGraphLoader)
    sources = {"synthetic-v1": _synthetic_source(tmp_path / "absent")}
    with caplog.at_level(logging.WARNING, logger="nutrigraphdt.data.pipeline"):
        result = DataPipeline(sources, registry=registry).run(["synthetic-v1"])
    (instance,) = result.dataset.instances
    assert instance.scenario_id == UNKNOWN_CONTEXT
    assert any("synthetic:scenario:other:0001" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# Fuente tabular
# ---------------------------------------------------------------------------


class TestTabularSource:
    def test_table_source_gets_graph_ids_and_unknown_context(
        self, sources: dict[str, SourceMetadata]
    ) -> None:
        result = DataPipeline(sources).run(["fixture_rows"])
        instances = result.dataset.instances
        assert [inst.graph_id for inst in instances] == [
            "fixture_rows:S1",
            "fixture_rows:S2",
            "fixture_rows:S3",
        ]
        for instance in instances:
            assert instance.is_synthetic is False
            assert instance.scenario_id == UNKNOWN_CONTEXT
            assert instance.diet_treatment == UNKNOWN_CONTEXT
            assert instance.study_id == UNKNOWN_CONTEXT

    def test_table_values_are_relative_abundances(self, sources: dict[str, SourceMetadata]) -> None:
        result = DataPipeline(sources).run(["fixture_rows"])
        values = {(f.graph_id, f.node_id): f.value for f in result.dataset.features}
        # S1 en la tabla: 400, 100 y 500 lecturas.
        assert values[("fixture_rows:S1", "Lactobacillus_johnsonii")] == pytest.approx(0.4)
        assert values[("fixture_rows:S1", "Ruminococcus_gnavus")] == pytest.approx(0.1)
        assert values[("fixture_rows:S1", "Faecalibacterium_prausnitzii")] == pytest.approx(0.5)

    def test_several_sources_are_merged(self, sources: dict[str, SourceMetadata]) -> None:
        result = DataPipeline(sources).run(["synthetic-v1", "fixture_rows"])
        dataset = result.dataset
        assert len(dataset.instances) == 5
        assert [inst.graph_id for inst in dataset.instances] == sorted(
            inst.graph_id for inst in dataset.instances
        )
        assert {f.source_id for f in dataset.features} == {"synthetic-v1", "fixture_rows"}
        assert list(result.reports) == ["synthetic-v1", "fixture_rows"]
        assert [s["source_id"] for s in dataset.metadata["sources"]] == [
            "synthetic-v1",
            "fixture_rows",
        ]
        assert dataset.validate() == []


# ---------------------------------------------------------------------------
# Configuración del preprocesamiento
# ---------------------------------------------------------------------------


class TestConfiguration:
    def test_pipeline_config_applies_to_every_source(
        self, sources: dict[str, SourceMetadata]
    ) -> None:
        config = AbundancePreprocessingConfig(normalization="clr", clr_pseudocount=1e-6)
        result = DataPipeline(sources, config=config).run(["synthetic-v1", "fixture_rows"])
        assert {f.feature_name for f in result.dataset.features} == {"abundance_clr"}
        assert result.dataset.metadata["preprocessing"]["fixture_rows"] == config.to_dict()

    def test_source_options_override_pipeline_config(self, tmp_path: Path) -> None:
        override = {"normalization": "clr", "clr_pseudocount": 1e-6}
        sources = {
            "synthetic-v1": _synthetic_source(tmp_path / "absent"),
            "fixture_rows": _fixture_source(preprocessing=override),
        }
        base = AbundancePreprocessingConfig(min_prevalence=0.5)
        result = DataPipeline(sources, config=base).run(["synthetic-v1", "fixture_rows"])
        names = {(f.source_id, f.feature_name) for f in result.dataset.features}
        assert names == {("synthetic-v1", "abundance"), ("fixture_rows", "abundance_clr")}
        # Los parámetros no sobrescritos se heredan de la configuración común.
        assert result.reports["fixture_rows"].parameters["min_prevalence"] == 0.5

    def test_invalid_source_override_names_the_source(self) -> None:
        sources = {"bad": _fixture_source("bad", preprocessing={"normalization": "clr"})}
        with pytest.raises(ValueError, match="'bad'"):
            DataPipeline(sources).run(["bad"])

    def test_unknown_override_key_is_rejected(self) -> None:
        sources = {"bad": _fixture_source("bad", preprocessing={"min_prevalance": 0.5})}
        with pytest.raises(ValueError, match="min_prevalance"):
            DataPipeline(sources).run(["bad"])

    def test_override_must_be_an_object(self) -> None:
        sources = {"bad": _fixture_source("bad", preprocessing=[0.5])}
        with pytest.raises(TypeError):
            DataPipeline(sources).run(["bad"])

    def test_custom_loader_registry_is_used(self, sources: dict[str, SourceMetadata]) -> None:
        DataPipeline(sources, registry=_spy_registry()).run(["fixture_rows"])
        assert SpyLoader.calls == ["fixture_rows"]

    def test_default_registry_covers_registered_formats(self) -> None:
        registry = default_loader_registry()
        for fmt in ("jsonl", "tsv", "csv"):
            source = replace(_fixture_source(), format=fmt)
            assert isinstance(registry.get_loader(source), AbundanceLoader)


# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------


class TestErrors:
    @pytest.mark.parametrize(
        ("source_ids", "error", "message"),
        [
            ([], ValueError, "al menos una fuente"),
            ("synthetic-v1", TypeError, "secuencia"),
            (["fixture_rows", "fixture_rows"], ValueError, "repetidas"),
            (["missing"], ValueError, "no está registrada"),
        ],
    )
    def test_invalid_source_selection(
        self,
        sources: dict[str, SourceMetadata],
        source_ids: Any,
        error: type[Exception],
        message: str,
    ) -> None:
        with pytest.raises(error, match=message):
            DataPipeline(sources).run(source_ids)

    def test_non_microbiome_source_is_rejected(self) -> None:
        registry = load_sources(REPO_ROOT / "configs" / "sources.json")
        with pytest.raises(ValueError, match="microbioma"):
            DataPipeline(registry).run(["D4_mtbls560_beauclercq"])

    def test_graph_id_collision_between_sources(self, tmp_path: Path) -> None:
        sources = {
            "synthetic-v1": _synthetic_source(tmp_path / "absent"),
            "synthetic-copy": replace(
                _synthetic_source(tmp_path / "absent"), source_id="synthetic-copy"
            ),
        }
        with pytest.raises(ValueError, match="graph_id"):
            DataPipeline(sources).run(["synthetic-v1", "synthetic-copy"])

    def test_source_without_loader_for_its_format(self) -> None:
        sources = {"biom_source": replace(_fixture_source("biom_source"), format="biom")}
        with pytest.raises(ValueError, match="No hay loader"):
            DataPipeline(sources).run(["biom_source"])

    def test_unreadable_source_fails_instead_of_exporting_empty_tables(
        self, tmp_path: Path
    ) -> None:
        broken = tmp_path / "broken"
        broken.mkdir()  # directorio sin los archivos JSONL del dataset sintético
        sources = {"synthetic-v1": _synthetic_source(broken)}
        out = tmp_path / "out"
        with pytest.raises(ValueError, match="no produjo instancias"):
            DataPipeline(sources).run(["synthetic-v1"], output_dir=out)
        assert not out.exists()

    def test_filter_that_removes_everything_fails(self) -> None:
        # Ningún taxón de la tabla de prueba llega a 0.9 de abundancia relativa.
        options = {"preprocessing": {"min_prevalence": 1.0, "min_abundance": 0.9}}
        sources = {"fixture_rows": _fixture_source(**options)}
        with pytest.raises(ValueError, match="no produjo instancias") as error:
            DataPipeline(sources).run(["fixture_rows"])
        assert "filtered_taxon" in str(error.value)
        assert "3 taxa eliminados" in str(error.value)

    def test_unknown_table_format(self, sources: dict[str, SourceMetadata]) -> None:
        with pytest.raises(ValueError, match="table_format"):
            DataPipeline(sources).run(["fixture_rows"], table_format="xlsx")


# ---------------------------------------------------------------------------
# Exportación y reproducibilidad
# ---------------------------------------------------------------------------


class TestExport:
    def test_exports_tables_and_report(
        self, tmp_path: Path, sources: dict[str, SourceMetadata]
    ) -> None:
        out = tmp_path / "out"
        result = DataPipeline(sources).run(["synthetic-v1", "fixture_rows"], output_dir=out)

        assert sorted(path.name for path in out.iterdir()) == sorted(
            [*TABLE_FILES, REPORT_FILENAME]
        )
        assert set(result.exported) == {
            "instances",
            "features",
            "edges",
            "targets",
            "metadata",
            "preprocessing_report",
        }
        instances = _read_tsv(out / "instances.tsv")
        features = _read_tsv(out / "features.tsv")
        assert [row["graph_id"] for row in instances] == [
            inst.graph_id for inst in result.dataset.instances
        ]
        assert len(features) == len(result.dataset.features)
        assert (out / "edges.tsv").read_text(encoding="utf-8") == ""
        metadata = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
        assert metadata == result.dataset.metadata

    def test_report_file_lists_discarded_rows(self, tmp_path: Path) -> None:
        sources = {"fixture_rows": _fixture_source(preprocessing={"min_prevalence": 1.0})}
        broken = tmp_path / "broken.tsv"
        broken.write_text(
            "taxon_id\tS1\tS2\nA\t10\t0\nB\t5\t5\n",
            encoding="utf-8",
        )
        sources["fixture_rows"] = replace(sources["fixture_rows"], path_or_url=str(broken))
        out = tmp_path / "out"
        DataPipeline(sources).run(["fixture_rows"], output_dir=out)

        report = json.loads((out / REPORT_FILENAME).read_text(encoding="utf-8"))
        (source_report,) = report["reports"]
        assert source_report["removed_taxa"] == {"A": 0.5}
        assert [row["reason"] for row in source_report["discarded"]] == ["filtered_taxon"] * 2
        assert {row["record"]["taxon_id"] for row in source_report["discarded"]} == {"A"}
        assert (
            source_report["input_records"]
            == source_report["output_records"] + source_report["discarded_records"]
        )

    def test_exported_files_are_reproducible(
        self, tmp_path: Path, sources: dict[str, SourceMetadata]
    ) -> None:
        pipeline = DataPipeline(sources)
        pipeline.run(["synthetic-v1", "fixture_rows"], output_dir=tmp_path / "a")
        pipeline.run(["synthetic-v1", "fixture_rows"], output_dir=tmp_path / "b")
        assert _digest(tmp_path / "a") == _digest(tmp_path / "b")

    def test_metadata_has_no_local_paths(
        self, tmp_path: Path, sources: dict[str, SourceMetadata]
    ) -> None:
        out = tmp_path / "out"
        DataPipeline(sources).run(["synthetic-v1", "fixture_rows"], output_dir=out)
        for name in ("metadata.json", REPORT_FILENAME):
            assert str(tmp_path) not in (out / name).read_text(encoding="utf-8")

    def test_existing_output_is_not_overwritten(
        self, tmp_path: Path, sources: dict[str, SourceMetadata]
    ) -> None:
        out = tmp_path / "out"
        out.mkdir()
        (out / "keep.txt").write_text("previo", encoding="utf-8")
        with pytest.raises(FileExistsError):
            DataPipeline(sources, registry=_spy_registry()).run(["fixture_rows"], output_dir=out)
        assert SpyLoader.calls == []
        assert sorted(path.name for path in out.iterdir()) == ["keep.txt"]

    def test_overwrite_replaces_tables(
        self, tmp_path: Path, sources: dict[str, SourceMetadata]
    ) -> None:
        out = tmp_path / "out"
        pipeline = DataPipeline(sources)
        pipeline.run(["synthetic-v1"], output_dir=out)
        pipeline.run(["fixture_rows"], output_dir=out, overwrite=True)
        graph_ids = [row["graph_id"] for row in _read_tsv(out / "instances.tsv")]
        assert graph_ids == ["fixture_rows:S1", "fixture_rows:S2", "fixture_rows:S3"]

    def test_overwrite_removes_tables_in_the_other_format(
        self, tmp_path: Path, sources: dict[str, SourceMetadata]
    ) -> None:
        out = tmp_path / "out"
        pipeline = DataPipeline(sources)
        pipeline.run(["fixture_rows"], output_dir=out, table_format="csv")
        (out / "notes.txt").write_text("conservar", encoding="utf-8")
        pipeline.run(["fixture_rows"], output_dir=out, overwrite=True)
        assert sorted(path.name for path in out.iterdir()) == sorted(
            [*TABLE_FILES, REPORT_FILENAME, "notes.txt"]
        )

    def test_loader_errors_reach_the_report_file(self, tmp_path: Path) -> None:
        table = tmp_path / "cells.tsv"
        table.write_text("taxon_id\tS1\tS2\nA\t10\tNA\nB\t5\t5\n", encoding="utf-8")
        sources = {"cells": replace(_fixture_source("cells"), path_or_url=str(table))}
        out = tmp_path / "out"
        DataPipeline(sources).run(["cells"], output_dir=out)

        report = json.loads((out / REPORT_FILENAME).read_text(encoding="utf-8"))
        (source_report,) = report["reports"]
        assert any("'NA'" in error for error in source_report["loader_errors"])
        assert str(tmp_path) not in (out / REPORT_FILENAME).read_text(encoding="utf-8")

    def test_csv_export(self, tmp_path: Path, sources: dict[str, SourceMetadata]) -> None:
        out = tmp_path / "out"
        result = DataPipeline(sources).run(["fixture_rows"], output_dir=out, table_format="csv")
        assert result.exported["features"].name == "features.csv"
        assert (out / "features.csv").read_text(encoding="utf-8").startswith("graph_id,node_id")

    def test_runs_are_reproducible_in_memory(self, sources: dict[str, SourceMetadata]) -> None:
        pipeline = DataPipeline(sources)
        first = pipeline.run(["synthetic-v1", "fixture_rows"])
        second = pipeline.run(["synthetic-v1", "fixture_rows"])
        assert first.dataset.to_dict() == second.dataset.to_dict()
        assert {k: r.to_dict() for k, r in first.reports.items()} == {
            k: r.to_dict() for k, r in second.reports.items()
        }
