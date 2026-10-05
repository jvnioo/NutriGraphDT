"""Tests unitarios para AbundanceLoader (A34-2)."""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

import pytest

from nutrigraphdt.data.config import load_sources
from nutrigraphdt.data.loaders.abundance import (
    TAXON_LEVELS,
    AbundanceLoader,
    _normalize_column,  # API interna testeada directamente: lógica crítica de normalización
    normalize_sample_id,
    normalize_taxon,
)
from nutrigraphdt.data.loaders.base import IngestionPayload, SourceMetadata, parse_bool_option
from nutrigraphdt.data.synthetic import export_dataset, generate_scenario_dataset

# ---------------------------------------------------------------------------
# Fixtures de SourceMetadata
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent.parent / "fixtures" / "abundance"


def _meta(
    fmt: str = "tsv",
    path: str | None = None,
    options: dict | None = None,
) -> SourceMetadata:
    return SourceMetadata(
        source_id="test_abundance",
        name="Test Abundance Dataset",
        species="chicken",
        gut_segment="cecum",
        data_types=("microbiome",),
        format=fmt,
        path_or_url=path,
        is_synthetic=True,
        options=options or {},
    )


# ---------------------------------------------------------------------------
# Tests de _normalize_column
# ---------------------------------------------------------------------------


def test_normalize_column_normalizes_to_one() -> None:
    values = [400.0, 100.0, 500.0]
    result = _normalize_column(values)
    assert abs(sum(result) - 1.0) < 1e-9
    assert all(math.isfinite(v) for v in result)


def test_normalize_column_already_normalized_unchanged() -> None:
    values = [0.4, 0.1, 0.5]
    result = _normalize_column(values)
    assert result is values  # misma referencia, no se copió


def test_normalize_column_all_zeros_returns_zeros() -> None:
    result = _normalize_column([0.0, 0.0, 0.0])
    assert result == [0.0, 0.0, 0.0]


# ---------------------------------------------------------------------------
# Tests de AbundanceLoader con archivos de fixture
# ---------------------------------------------------------------------------


class TestAbundanceLoaderTaxaRows:
    """Fixture: taxa-en-filas (orientación por defecto)."""

    def setup_method(self) -> None:
        path = str(FIXTURES / "taxa_rows.tsv")
        self.loader = AbundanceLoader(_meta(path=path))

    def test_load_returns_ingestion_payload(self) -> None:
        payload = self.loader.load()
        assert isinstance(payload, IngestionPayload)

    def test_records_count_matches_raw_data(self) -> None:
        payload = self.loader.load()
        assert payload.records_count == len(payload.raw_data)

    def test_records_count_is_taxa_times_samples(self) -> None:
        # 3 taxa x 3 muestras
        payload = self.loader.load()
        assert payload.records_count == 9

    def test_each_sample_sums_to_one(self) -> None:
        payload = self.loader.load()
        from collections import defaultdict

        sums: dict[str, float] = defaultdict(float)
        for rec in payload.raw_data:
            sums[rec["sample_id"]] += rec["value"]
        for sample, total in sums.items():
            assert abs(total - 1.0) < 1e-9, f"Muestra {sample} no suma 1.0: {total}"

    def test_unit_is_relative_abundance(self) -> None:
        payload = self.loader.load()
        units = {rec["unit"] for rec in payload.raw_data}
        assert units == {"relative_abundance"}

    def test_all_values_finite_and_nonnegative(self) -> None:
        payload = self.loader.load()
        for rec in payload.raw_data:
            assert math.isfinite(rec["value"])
            assert rec["value"] >= 0.0

    def test_metadata_preserved(self) -> None:
        payload = self.loader.load()
        assert payload.metadata.source_id == "test_abundance"
        assert payload.metadata.species == "chicken"

    def test_extra_contains_source_path(self) -> None:
        payload = self.loader.load()
        assert "source_path" in payload.extra

    def test_source_id_in_every_record(self) -> None:
        payload = self.loader.load()
        for rec in payload.raw_data:
            assert rec["source_id"] == "test_abundance"


class TestAbundanceLoaderTaxaCols:
    """Fixture: taxa-en-columnas."""

    def setup_method(self) -> None:
        path = str(FIXTURES / "taxa_cols.tsv")
        self.loader = AbundanceLoader(_meta(path=path, options={"orientation": "taxa_cols"}))

    def test_records_count_is_samples_times_taxa(self) -> None:
        # 2 muestras x 3 taxa
        payload = self.loader.load()
        assert payload.records_count == 6

    def test_values_already_normalized_unchanged(self) -> None:
        # Los valores del fixture ya suman 1.0 por muestra
        payload = self.loader.load()
        from collections import defaultdict

        sums: dict[str, float] = defaultdict(float)
        for rec in payload.raw_data:
            sums[rec["sample_id"]] += rec["value"]
        for _s, total in sums.items():
            assert abs(total - 1.0) < 1e-6, f"{_s}: {total}"


class TestAbundanceLoaderComments:
    """Fixture CSV con líneas de comentario."""

    def setup_method(self) -> None:
        path = str(FIXTURES / "with_comments.csv")
        self.loader = AbundanceLoader(_meta(fmt="csv", path=path))

    def test_comments_are_skipped(self) -> None:
        payload = self.loader.load()
        # 2 taxa x 2 muestras
        assert payload.records_count == 4

    def test_each_sample_sums_to_one_after_normalization(self) -> None:
        payload = self.loader.load()
        from collections import defaultdict

        sums: dict[str, float] = defaultdict(float)
        for rec in payload.raw_data:
            sums[rec["sample_id"]] += rec["value"]
        for _s, total in sums.items():
            assert abs(total - 1.0) < 1e-9


class TestAbundanceLoaderNoNormalize:
    """Verificar que normalize=False conserva valores originales."""

    def setup_method(self) -> None:
        path = str(FIXTURES / "taxa_rows.tsv")
        self.loader = AbundanceLoader(
            _meta(path=path, options={"normalize": False, "unit": "reads_per_million"})
        )

    def test_values_not_normalized(self) -> None:
        payload = self.loader.load()
        # Con normalize=False los valores absolutos no deben sumar 1
        from collections import defaultdict

        sums: dict[str, float] = defaultdict(float)
        for rec in payload.raw_data:
            sums[rec["sample_id"]] += rec["value"]
        # S1: 400+100+500=1000, S2: 200+300+500=1000, S3: 100+200+700=1000
        for total in sums.values():
            assert total > 1.0 + 1e-6

    def test_unit_from_options(self) -> None:
        payload = self.loader.load()
        units = {rec["unit"] for rec in payload.raw_data}
        assert units == {"reads_per_million"}


class TestAbundanceLoaderEdgeCases:
    """Casos límite."""

    def test_invalid_orientation_raises(self, tmp_path: Path) -> None:
        tsv = tmp_path / "dummy.tsv"
        tsv.write_text("taxon_id\tS1\nOTU_A\t1.0\n", encoding="utf-8")
        loader = AbundanceLoader(_meta(path=str(tsv), options={"orientation": "invalid_value"}))
        with pytest.raises(ValueError, match="orientation"):
            loader.load()

    def test_missing_file_raises(self) -> None:
        loader = AbundanceLoader(_meta(path="/nonexistent/path/data.tsv"))
        with pytest.raises(FileNotFoundError):
            loader.load()

    def test_empty_file_returns_zero_records(self, tmp_path: Path) -> None:
        tsv = tmp_path / "empty.tsv"
        tsv.write_text("taxon_id\tS1\n", encoding="utf-8")  # solo encabezado
        loader = AbundanceLoader(_meta(path=str(tsv)))
        payload = loader.load()
        assert payload.records_count == 0
        assert payload.raw_data == []

    def test_negative_values_clamped_to_zero(self, tmp_path: Path) -> None:
        """Valores negativos en el archivo deben clampear a 0.0, nunca aparecer negativos."""
        tsv = tmp_path / "negative.tsv"
        tsv.write_text("taxon_id\tS1\nOTU_A\t-50.0\nOTU_B\t100.0\n", encoding="utf-8")
        loader = AbundanceLoader(_meta(path=str(tsv), options={"normalize": False}))
        payload = loader.load()
        for rec in payload.raw_data:
            assert rec["value"] >= 0.0, f"Valor negativo inesperado: {rec}"

    def test_normalize_string_true_treated_as_true(self, tmp_path: Path) -> None:
        """options['normalize'] como string '1' debe tratarse como True."""
        tsv = tmp_path / "data.tsv"
        tsv.write_text("taxon_id\tS1\nOTU_A\t300.0\nOTU_B\t700.0\n", encoding="utf-8")
        loader = AbundanceLoader(_meta(path=str(tsv), options={"normalize": "1"}))
        payload = loader.load()
        total = sum(rec["value"] for rec in payload.raw_data)
        assert abs(total - 1.0) < 1e-9


class TestSourceMetadataValidation:
    """Verifica que SourceMetadata valide species y gut_segment contra el schema."""

    def test_invalid_species_raises(self) -> None:
        with pytest.raises(ValueError, match="Especie"):
            SourceMetadata(
                source_id="x",
                name="X",
                species="mouse",  # no permitida
                gut_segment="cecum",
                data_types=("microbiome",),
                format="tsv",
            )

    def test_invalid_gut_segment_raises(self) -> None:
        with pytest.raises(ValueError, match="Segmento"):
            SourceMetadata(
                source_id="x",
                name="X",
                species="chicken",
                gut_segment="intestine",  # no permitido
                data_types=("microbiome",),
                format="tsv",
            )

    def test_valid_species_and_segment_accepted(self) -> None:
        meta = SourceMetadata(
            source_id="x",
            name="X",
            species="pig",
            gut_segment="multi",
            data_types=("microbiome",),
            format="tsv",
        )
        assert meta.species == "pig"
        assert meta.gut_segment == "multi"


# ---------------------------------------------------------------------------
# Revisión post-merge de #49: tareas pendientes de A34-2 (#25)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]


def _sums_by_sample(records: list[dict[str, Any]]) -> dict[tuple[Any, str], float]:
    sums: dict[tuple[Any, str], float] = {}
    for rec in records:
        key = (rec["graph_id"], rec["sample_id"])
        sums[key] = sums.get(key, 0.0) + rec["value"]
    return sums


class TestParseBoolOption:
    """`normalize` y `generate_if_missing` vienen de JSON y no pueden usar bool()."""

    @pytest.mark.parametrize("value", [True, 1, "true", "TRUE", "1", "yes", "si", "sí"])
    def test_true_values(self, value: object) -> None:
        assert parse_bool_option(value) is True

    @pytest.mark.parametrize("value", [False, 0, "false", "False", "0", "no"])
    def test_false_values(self, value: object) -> None:
        assert parse_bool_option(value) is False

    @pytest.mark.parametrize("value", ["maybe", "", 2, None, 1.0])
    def test_invalid_values_raise(self, value: object) -> None:
        with pytest.raises(ValueError, match="normalize"):
            parse_bool_option(value, "normalize")

    def test_normalize_string_false_keeps_raw_values(self, tmp_path: Path) -> None:
        tsv = tmp_path / "data.tsv"
        tsv.write_text("taxon_id\tS1\nOTU_A\t300\nOTU_B\t700\n", encoding="utf-8")
        loader = AbundanceLoader(_meta(path=str(tsv), options={"normalize": "false"}))
        values = sorted(rec["value"] for rec in loader.load().raw_data)
        assert values == [300.0, 700.0]

    def test_invalid_normalize_raises(self, tmp_path: Path) -> None:
        tsv = tmp_path / "data.tsv"
        tsv.write_text("taxon_id\tS1\nOTU_A\t1\n", encoding="utf-8")
        loader = AbundanceLoader(_meta(path=str(tsv), options={"normalize": "maybe"}))
        with pytest.raises(ValueError, match="normalize"):
            loader.load()


class TestIdentifierNormalization:
    """Identificadores de muestra y nivel taxonómico."""

    def test_sample_id_strips_and_replaces_spaces(self) -> None:
        assert normalize_sample_id("  chicken 01\tcecum ") == "chicken_01_cecum"

    def test_mgnify_lineage_uses_deepest_named_rank(self) -> None:
        lineage = "sk__Bacteria;k__;p__Bacillota;c__Bacilli;g__Lactobacillus;s__L johnsonii"
        assert normalize_taxon(lineage) == ("L_johnsonii", "species")

    def test_trailing_empty_ranks_are_ignored(self) -> None:
        assert normalize_taxon("d__Bacteria;p__Bacillota;c__;o__;f__;g__;s__") == (
            "Bacillota",
            "phylum",
        )

    def test_metaphlan_pipe_lineage(self) -> None:
        assert normalize_taxon("k__Bacteria|p__Bacteroidota|g__Bacteroides") == (
            "Bacteroides",
            "genus",
        )

    def test_plain_lineage_without_prefixes_uses_default_level(self) -> None:
        assert normalize_taxon("Bacteria; Bacillota ;Bacilli", "class") == ("Bacilli", "class")

    def test_plain_identifier_keeps_default_level(self) -> None:
        assert normalize_taxon(" OTU 17 ", "otu") == ("OTU_17", "otu")

    def test_empty_identifier(self) -> None:
        assert normalize_taxon(" ; ") == ("", "unknown")

    def test_records_carry_taxon_level(self) -> None:
        loader = AbundanceLoader(_meta(path=str(FIXTURES / "taxa_rows.tsv")))
        assert {rec["taxon_level"] for rec in loader.load().raw_data} == {"unknown"}

    def test_taxon_level_option_applies_to_plain_ids(self) -> None:
        meta = _meta(path=str(FIXTURES / "taxa_rows.tsv"), options={"taxon_level": "species"})
        levels = {rec["taxon_level"] for rec in AbundanceLoader(meta).load().raw_data}
        assert levels == {"species"}

    def test_invalid_taxon_level_option_raises(self) -> None:
        meta = _meta(path=str(FIXTURES / "taxa_rows.tsv"), options={"taxon_level": "tribe"})
        with pytest.raises(ValueError, match="taxon_level"):
            AbundanceLoader(meta).load()

    def test_mgnify_fixture(self) -> None:
        # MGnify exporta el encabezado como '#SampleID': se desactiva el comentario '#'.
        meta = _meta(
            path=str(FIXTURES / "mgnify_lineage.tsv"),
            options={"comment_char": "", "taxon_column": "#SampleID"},
        )
        payload = AbundanceLoader(meta).load()
        assert payload.extra["errors"] == []
        assert payload.records_count == 6
        taxa = {(rec["taxon_id"], rec["taxon_level"]) for rec in payload.raw_data}
        assert taxa == {
            ("Lactobacillus_johnsonii", "species"),
            ("Bacteroides", "genus"),
            ("Bacillota", "phylum"),
        }
        assert {rec["sample_id"] for rec in payload.raw_data} == {"ERR001", "ERR002"}
        for total in _sums_by_sample(payload.raw_data).values():
            assert total == pytest.approx(1.0)


class TestReadErrorsAreLogged:
    """Los errores de lectura se registran en el log y en extra['errors'] sin detener."""

    def _load(self, tmp_path: Path, content: str, **options: Any) -> IngestionPayload:
        tsv = tmp_path / "data.tsv"
        tsv.write_text(content, encoding="utf-8")
        return AbundanceLoader(_meta(path=str(tsv), options=options)).load()

    def test_non_numeric_cell_is_skipped_and_logged(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="nutrigraphdt.data.loaders.abundance"):
            payload = self._load(tmp_path, "taxon_id\tS1\nOTU_A\tabc\nOTU_B\t4\nOTU_C\t6\n")
        assert {rec["taxon_id"] for rec in payload.raw_data} == {"OTU_B", "OTU_C"}
        assert len(payload.extra["errors"]) == 1
        assert "no numérico 'abc'" in payload.extra["errors"][0]
        assert "abc" in caplog.text

    @pytest.mark.parametrize("raw", ["nan", "inf", "-inf"])
    def test_non_finite_cell_is_skipped(self, tmp_path: Path, raw: str) -> None:
        payload = self._load(tmp_path, f"taxon_id\tS1\nOTU_A\t{raw}\nOTU_B\t4\n")
        assert [rec["taxon_id"] for rec in payload.raw_data] == ["OTU_B"]
        assert "no finito" in payload.extra["errors"][0]

    def test_negative_value_is_logged(self, tmp_path: Path) -> None:
        payload = self._load(tmp_path, "taxon_id\tS1\nOTU_A\t-5\nOTU_B\t4\n")
        assert "negativo" in payload.extra["errors"][0]

    def test_row_with_wrong_column_count_is_skipped(self, tmp_path: Path) -> None:
        payload = self._load(tmp_path, "taxon_id\tS1\tS2\nOTU_A\t1\nOTU_B\t1\t2\n")
        assert {rec["taxon_id"] for rec in payload.raw_data} == {"OTU_B"}
        assert "fila 2" in payload.extra["errors"][0]

    def test_duplicate_sample_column_is_skipped(self, tmp_path: Path) -> None:
        payload = self._load(tmp_path, "taxon_id\tS1\t S1\nOTU_A\t1\t9\n")
        assert payload.records_count == 1
        assert "duplicada" in payload.extra["errors"][0]

    def test_duplicate_taxon_is_summed(self, tmp_path: Path) -> None:
        content = "taxon_id\tS1\ng__Bacteroides\t2\nk__Bacteria|g__Bacteroides\t3\n"
        payload = self._load(tmp_path, content, normalize=False)
        assert [rec["value"] for rec in payload.raw_data] == [5.0]
        assert "más de una vez" in payload.extra["errors"][0]

    def test_unreadable_file_returns_empty_payload(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        tsv = tmp_path / "latin1.tsv"
        tsv.write_bytes("taxon_id\tS1\nOTU_ñ\t1\n".encode("latin-1"))
        with caplog.at_level(logging.ERROR, logger="nutrigraphdt.data.loaders.abundance"):
            payload = AbundanceLoader(_meta(path=str(tsv))).load()
        assert payload.records_count == 0
        assert "No se pudo leer" in payload.extra["errors"][0]
        assert "No se pudo leer" in caplog.text

    def test_clean_file_has_no_errors(self) -> None:
        payload = AbundanceLoader(_meta(path=str(FIXTURES / "taxa_rows.tsv"))).load()
        assert payload.extra["errors"] == []


class TestSyntheticDataset:
    """Criterio de aceptación de #25: carga el dataset sintético de la act. 26 sin errores."""

    def _assert_synthetic_payload(self, payload: IngestionPayload) -> None:
        assert payload.extra["errors"] == []
        graph_ids = {rec["graph_id"] for rec in payload.raw_data}
        assert graph_ids == {
            "synthetic:scenario:basal:0001",
            "synthetic:scenario:intervened:0001",
        }
        assert all(rec["taxon_level"] in TAXON_LEVELS for rec in payload.raw_data)
        assert all(rec["unit"] == "relative_abundance" for rec in payload.raw_data)
        for total in _sums_by_sample(payload.raw_data).values():
            assert total == pytest.approx(1.0, abs=1e-5)

    def test_loads_exported_dataset(self, tmp_path: Path) -> None:
        dataset = generate_scenario_dataset()
        export_dataset(dataset, tmp_path / "v1")
        payload = AbundanceLoader(_meta(fmt="jsonl", path=str(tmp_path / "v1"))).load()
        self._assert_synthetic_payload(payload)
        taxa = [node for node in dataset.nodes if node.node_type == "taxon"]
        assert payload.records_count == len(taxa)

    def test_generates_dataset_if_missing(self, tmp_path: Path) -> None:
        meta = _meta(
            fmt="jsonl",
            path=str(tmp_path / "absent"),
            options={"generate_if_missing": True},
        )
        payload = AbundanceLoader(meta).load()
        assert payload.extra["source_path"] == "generated"
        self._assert_synthetic_payload(payload)

    def test_missing_dataset_without_generation_raises(self, tmp_path: Path) -> None:
        loader = AbundanceLoader(_meta(fmt="jsonl", path=str(tmp_path / "absent")))
        with pytest.raises(FileNotFoundError):
            loader.load()

    def test_corrupt_dataset_is_logged(self, tmp_path: Path) -> None:
        (tmp_path / "broken").mkdir()
        payload = AbundanceLoader(_meta(fmt="jsonl", path=str(tmp_path / "broken"))).load()
        assert payload.records_count == 0
        assert "No se pudo leer" in payload.extra["errors"][0]

    def test_registered_synthetic_source(self) -> None:
        # data/synthetic/v1 no se versiona: la fuente declara generate_if_missing.
        sources = load_sources(REPO_ROOT / "configs" / "sources.json")
        payload = AbundanceLoader(sources["synthetic-v1"]).load(
            REPO_ROOT / "data" / "synthetic" / "v1"
        )
        self._assert_synthetic_payload(payload)
