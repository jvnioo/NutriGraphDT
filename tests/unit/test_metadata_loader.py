"""Tests unitarios para MetadataLoader e infer_field_type.

Cubre:
- Carga básica de TSV con columnas de dieta y fenotipo.
- Carga de CSV con campos categóricos y numéricos mixtos.
- Inferencia automática de field_type (diet, phenotype, numeric, categorical).
- Override de field_type via column_types en options.
- Unidades por defecto para columnas conocidas (body_weight_g, fcr, etc.).
- Override de unidades via column_units en options.
- Clampeo de valores negativos en campos numéricos/fenotípicos.
- Líneas de comentario ignoradas.
- Columnas en skip_columns excluidas del payload.
- Tabla vacía → records_count == 0.
- extra contiene sample_column, data_columns y field_types_found.
- source_id, species, gut_segment presentes en cada registro.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nutrigraphdt.data.loaders.base import SourceMetadata
from nutrigraphdt.data.loaders.metadata import MetadataLoader, infer_field_type

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent.parent / "fixtures" / "metadata"


def _make_metadata(
    source_id: str = "test-metadata",
    options: dict | None = None,
) -> SourceMetadata:
    return SourceMetadata(
        source_id=source_id,
        name="Test Metadata Source",
        species="chicken",
        gut_segment="ileum",
        data_types=("metadata",),
        format="tsv",
        options=options or {},
    )


# ---------------------------------------------------------------------------
# Tests de infer_field_type
# ---------------------------------------------------------------------------


class TestInferFieldType:
    def test_diet_treatment_inferred(self) -> None:
        assert infer_field_type("diet_treatment") == "diet"
        assert infer_field_type("treatment") == "diet"
        assert infer_field_type("feed") == "diet"
        assert infer_field_type("dietary_group") == "diet"

    def test_phenotype_columns_inferred(self) -> None:
        assert infer_field_type("body_weight_g") == "phenotype"
        assert infer_field_type("feed_conversion_ratio") == "phenotype"
        assert infer_field_type("health_score") == "phenotype"
        assert infer_field_type("mortality_rate") == "phenotype"
        assert infer_field_type("fcr") == "phenotype"

    def test_unknown_defaults_to_numeric(self) -> None:
        assert infer_field_type("age_days") == "numeric"
        assert infer_field_type("some_custom_field") == "numeric"

    def test_column_types_override(self) -> None:
        overrides = {"my_col": "categorical"}
        assert infer_field_type("my_col", overrides) == "categorical"

    def test_case_insensitive_inference(self) -> None:
        assert infer_field_type("Diet_Treatment") == "diet"
        assert infer_field_type("BODY_WEIGHT") == "phenotype"


# ---------------------------------------------------------------------------
# Tests de MetadataLoader — carga TSV básica
# ---------------------------------------------------------------------------


class TestMetadataLoaderTSV:
    def test_basic_load_count(self) -> None:
        """4 muestras × 4 campos de datos = 16 registros."""
        meta = _make_metadata()
        loader = MetadataLoader(meta)
        payload = loader.load(FIXTURES / "sample_metadata.tsv")

        assert payload.records_count == 16

    def test_required_fields_present(self) -> None:
        meta = _make_metadata()
        loader = MetadataLoader(meta)
        payload = loader.load(FIXTURES / "sample_metadata.tsv")

        rec = payload.raw_data[0]
        assert "sample_id" in rec
        assert "field" in rec
        assert "value" in rec
        assert "unit" in rec
        assert "field_type" in rec
        assert "source_id" in rec
        assert "species" in rec
        assert "gut_segment" in rec

    def test_provenance_metadata(self) -> None:
        meta = _make_metadata(source_id="holofood-meta")
        loader = MetadataLoader(meta)
        payload = loader.load(FIXTURES / "sample_metadata.tsv")

        for rec in payload.raw_data:
            assert rec["source_id"] == "holofood-meta"
            assert rec["species"] == "chicken"
            assert rec["gut_segment"] == "ileum"

    def test_diet_treatment_is_categorical(self) -> None:
        meta = _make_metadata()
        loader = MetadataLoader(meta)
        payload = loader.load(FIXTURES / "sample_metadata.tsv")

        diet_recs = [r for r in payload.raw_data if r["field"] == "diet_treatment"]
        assert len(diet_recs) == 4
        for rec in diet_recs:
            assert rec["field_type"] == "categorical"
            assert isinstance(rec["value"], str)

    def test_body_weight_unit_resolved(self) -> None:
        meta = _make_metadata()
        loader = MetadataLoader(meta)
        payload = loader.load(FIXTURES / "sample_metadata.tsv")

        bw_recs = [r for r in payload.raw_data if r["field"] == "body_weight_g"]
        assert len(bw_recs) == 4
        for rec in bw_recs:
            assert rec["unit"] == "g"
            assert rec["field_type"] == "phenotype"

    def test_fcr_unit_resolved(self) -> None:
        meta = _make_metadata()
        loader = MetadataLoader(meta)
        payload = loader.load(FIXTURES / "sample_metadata.tsv")

        fcr_recs = [r for r in payload.raw_data if r["field"] == "feed_conversion_ratio"]
        for rec in fcr_recs:
            assert rec["unit"] == "ratio"

    def test_health_score_unit_resolved(self) -> None:
        meta = _make_metadata()
        loader = MetadataLoader(meta)
        payload = loader.load(FIXTURES / "sample_metadata.tsv")

        hs_recs = [r for r in payload.raw_data if r["field"] == "health_score"]
        for rec in hs_recs:
            assert rec["unit"] == "score"

    def test_values_non_negative(self) -> None:
        meta = _make_metadata()
        loader = MetadataLoader(meta)
        payload = loader.load(FIXTURES / "sample_metadata.tsv")

        for rec in payload.raw_data:
            if isinstance(rec["value"], float):
                assert rec["value"] >= 0.0

    def test_extra_contains_field_types_found(self) -> None:
        meta = _make_metadata()
        loader = MetadataLoader(meta)
        payload = loader.load(FIXTURES / "sample_metadata.tsv")

        assert "field_types_found" in payload.extra
        assert "categorical" in payload.extra["field_types_found"]
        assert "phenotype" in payload.extra["field_types_found"]


# ---------------------------------------------------------------------------
# Tests de MetadataLoader — CSV con campos mixtos
# ---------------------------------------------------------------------------


class TestMetadataLoaderCSV:
    def test_csv_load(self) -> None:
        """3 muestras × 4 campos = 12 registros."""
        meta = _make_metadata(options={"delimiter": ","})
        loader = MetadataLoader(meta)
        payload = loader.load(FIXTURES / "sample_metadata.csv")

        assert payload.records_count == 12

    def test_categorical_group_detected(self) -> None:
        meta = _make_metadata(options={"delimiter": ","})
        loader = MetadataLoader(meta)
        payload = loader.load(FIXTURES / "sample_metadata.csv")

        group_recs = [r for r in payload.raw_data if r["field"] == "group"]
        for rec in group_recs:
            assert isinstance(rec["value"], str)
            assert rec["field_type"] == "categorical"

    def test_numeric_fields_parsed(self) -> None:
        meta = _make_metadata(options={"delimiter": ","})
        loader = MetadataLoader(meta)
        payload = loader.load(FIXTURES / "sample_metadata.csv")

        numeric_recs = [r for r in payload.raw_data if r["field"] == "age_days"]
        assert len(numeric_recs) == 3
        for rec in numeric_recs:
            assert isinstance(rec["value"], float)


# ---------------------------------------------------------------------------
# Tests de MetadataLoader — opciones avanzadas y casos límite
# ---------------------------------------------------------------------------


class TestMetadataLoaderOptions:
    def test_skip_columns_excluded(self) -> None:
        meta = _make_metadata(options={"skip_columns": ["health_score"]})
        loader = MetadataLoader(meta)
        payload = loader.load(FIXTURES / "sample_metadata.tsv")

        fields = {r["field"] for r in payload.raw_data}
        assert "health_score" not in fields

    def test_column_units_override(self) -> None:
        meta = _make_metadata(options={"column_units": {"body_weight_g": "dimensionless"}})
        loader = MetadataLoader(meta)
        payload = loader.load(FIXTURES / "sample_metadata.tsv")

        bw_recs = [r for r in payload.raw_data if r["field"] == "body_weight_g"]
        for rec in bw_recs:
            assert rec["unit"] == "dimensionless"

    def test_column_types_override(self) -> None:
        meta = _make_metadata(options={"column_types": {"body_weight_g": "categorical"}})
        loader = MetadataLoader(meta)
        payload = loader.load(FIXTURES / "sample_metadata.tsv")

        bw_recs = [r for r in payload.raw_data if r["field"] == "body_weight_g"]
        for rec in bw_recs:
            assert rec["field_type"] == "categorical"

    def test_negative_values_clamped(self, tmp_path: Path) -> None:
        content = "sample_id\tbody_weight_g\nS1\t-100.0\nS2\t2500\n"
        tsv_file = tmp_path / "neg.tsv"
        tsv_file.write_text(content, encoding="utf-8")
        meta = _make_metadata()
        loader = MetadataLoader(meta)
        payload = loader.load(tsv_file)

        bw_recs = [r for r in payload.raw_data if r["field"] == "body_weight_g"]
        for rec in bw_recs:
            assert isinstance(rec["value"], float)
            assert rec["value"] >= 0.0

    def test_empty_file_returns_empty_payload(self, tmp_path: Path) -> None:
        empty_file = tmp_path / "empty.tsv"
        empty_file.write_text("sample_id\tbody_weight_g\n", encoding="utf-8")
        meta = _make_metadata()
        loader = MetadataLoader(meta)
        payload = loader.load(empty_file)

        assert payload.records_count == 0
        assert payload.raw_data == []

    def test_comment_lines_ignored(self, tmp_path: Path) -> None:
        content = "# Metadata file\n# Study: test\nsample_id\tbody_weight_g\nS1\t2500\nS2\t2350\n"
        tsv_file = tmp_path / "with_comments.tsv"
        tsv_file.write_text(content, encoding="utf-8")
        meta = _make_metadata()
        loader = MetadataLoader(meta)
        payload = loader.load(tsv_file)

        assert payload.records_count == 2

    def test_missing_file_raises(self) -> None:
        meta = _make_metadata()
        loader = MetadataLoader(meta)

        with pytest.raises(FileNotFoundError):
            loader.load(Path("/nonexistent/metadata.tsv"))

    def test_custom_sample_column(self, tmp_path: Path) -> None:
        content = "animal_id\tbody_weight_g\nA1\t2500\nA2\t2350\n"
        tsv_file = tmp_path / "custom_col.tsv"
        tsv_file.write_text(content, encoding="utf-8")
        meta = _make_metadata(options={"sample_column": "animal_id"})
        loader = MetadataLoader(meta)
        payload = loader.load(tsv_file)

        sample_ids = {r["sample_id"] for r in payload.raw_data}
        assert "A1" in sample_ids
        assert "A2" in sample_ids
