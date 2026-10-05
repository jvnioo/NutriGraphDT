"""Tests unitarios para AbundanceLoader (A34-2)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from nutrigraphdt.data.loaders.abundance import (
    AbundanceLoader,
    _normalize_column,  # API interna testeada directamente: lógica crítica de normalización
)
from nutrigraphdt.data.loaders.base import IngestionPayload, SourceMetadata

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
