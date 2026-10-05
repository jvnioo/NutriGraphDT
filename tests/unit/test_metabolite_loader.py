"""Tests unitarios para MetaboliteLoader, map_metabolite_name y normalize_unit.

Cubre:
- Carga en orientación metabolite_rows (TSV, con columna database_identifier).
- Carga en orientación metabolite_cols (CSV).
- Omisión de líneas de comentario.
- Mapeo canónico de SCFA (acetato, propionato, butirato).
- Mapeo por database_identifier (C00033, C00163, C00246).
- Mapeo fallback para nombres desconocidos.
- Normalización de unidades (mmol/kg → mmol_kg, µmol/g → umol_g, etc.).
- Unidad fallback para unidades no reconocidas.
- Clampeo de valores negativos a 0.0.
- Valores no numéricos se omiten (None).
- Tabla vacía devuelve IngestionPayload con records_count=0.
- extra contiene scfa_found con los SCFA detectados.
- source_id, species, gut_segment presentes en cada registro.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from nutrigraphdt.data.loaders.base import IngestionPayload, SourceMetadata
from nutrigraphdt.data.loaders.metabolite import (
    MetaboliteLoader,
    map_metabolite_name,
    normalize_unit,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent.parent / "fixtures" / "metabolite"


def _make_metadata(
    source_id: str = "test-metabolite",
    options: dict | None = None,
) -> SourceMetadata:
    return SourceMetadata(
        source_id=source_id,
        name="Test Metabolite Source",
        species="chicken",
        gut_segment="cecum",
        data_types=("metabolome",),
        format="tsv",
        options=options or {},
    )


# ---------------------------------------------------------------------------
# Tests de map_metabolite_name
# ---------------------------------------------------------------------------


class TestMapMetaboliteName:
    def test_acetate_aliases(self) -> None:
        assert map_metabolite_name("acetic acid") == "acetate"
        assert map_metabolite_name("Acetic Acid") == "acetate"
        assert map_metabolite_name("acetate") == "acetate"
        assert map_metabolite_name("C00033") == "acetate"
        assert map_metabolite_name("CHEBI:30089") == "acetate"

    def test_propionate_aliases(self) -> None:
        assert map_metabolite_name("propionic acid") == "propionate"
        assert map_metabolite_name("propionate") == "propionate"
        assert map_metabolite_name("C00163") == "propionate"

    def test_butyrate_aliases(self) -> None:
        assert map_metabolite_name("butyric acid") == "butyrate"
        assert map_metabolite_name("butyrate") == "butyrate"
        assert map_metabolite_name("n-butyrate") == "butyrate"
        assert map_metabolite_name("C00246") == "butyrate"

    def test_lactate_aliases(self) -> None:
        assert map_metabolite_name("lactic acid") == "lactate"
        assert map_metabolite_name("C00186") == "lactate"

    def test_succinate_aliases(self) -> None:
        assert map_metabolite_name("succinic acid") == "succinate"
        assert map_metabolite_name("C00042") == "succinate"

    def test_unknown_returns_slug(self) -> None:
        result = map_metabolite_name("Unknown Compound X")
        assert result == "unknown_compound_x"

    def test_strips_whitespace(self) -> None:
        assert map_metabolite_name("  acetate  ") == "acetate"


# ---------------------------------------------------------------------------
# Tests de normalize_unit
# ---------------------------------------------------------------------------


class TestNormalizeUnit:
    def test_mmol_kg_variants(self) -> None:
        assert normalize_unit("mmol/kg") == "mmol_kg"
        assert normalize_unit("mmol kg-1") == "mmol_kg"
        assert normalize_unit("mmol_kg") == "mmol_kg"

    def test_umol_g_variants(self) -> None:
        assert normalize_unit("umol/g") == "umol_g"
        assert normalize_unit("µmol/g") == "umol_g"
        assert normalize_unit("umol g-1") == "umol_g"

    def test_mM_variants(self) -> None:
        assert normalize_unit("mM") == "mM"
        assert normalize_unit("mmol/l") == "mM"
        assert normalize_unit("mmol/L") == "mM"

    def test_mg_kg_variants(self) -> None:
        assert normalize_unit("mg/kg") == "mg_kg"
        assert normalize_unit("mg kg-1") == "mg_kg"

    def test_g_kg_variants(self) -> None:
        assert normalize_unit("g/kg") == "g_kg"

    def test_proportion(self) -> None:
        assert normalize_unit("proportion") == "proportion"
        assert normalize_unit("fraction") == "proportion"

    def test_dimensionless(self) -> None:
        assert normalize_unit("dimensionless") == "dimensionless"
        assert normalize_unit("AU") == "dimensionless"

    def test_unknown_unit_returns_lowercase(self) -> None:
        result = normalize_unit("ng/mL")
        assert result == "ng/ml"

    def test_strips_whitespace(self) -> None:
        assert normalize_unit("  mmol/kg  ") == "mmol_kg"


# ---------------------------------------------------------------------------
# Tests de MetaboliteLoader — orientación metabolite_rows
# ---------------------------------------------------------------------------


class TestMetaboliteLoaderRows:
    def test_basic_load_returns_correct_count(self) -> None:
        """5 metabolitos × 3 muestras = 15 registros."""
        meta = _make_metadata(
            options={
                "unit": "mmol/kg",
                "id_column": "database_identifier",
                "metabolite_column": "chemical_name",
            }
        )
        loader = MetaboliteLoader(meta)
        payload = loader.load(FIXTURES / "metabolites_rows.tsv")

        assert payload.records_count == 15
        assert len(payload.raw_data) == 15

    def test_scfa_canonical_ids_resolved(self) -> None:
        meta = _make_metadata(options={"unit": "mmol/kg", "id_column": "database_identifier"})
        loader = MetaboliteLoader(meta)
        payload = loader.load(FIXTURES / "metabolites_rows.tsv")

        canonical_ids = {r["canonical_id"] for r in payload.raw_data}
        assert "acetate" in canonical_ids
        assert "propionate" in canonical_ids
        assert "butyrate" in canonical_ids
        assert "lactate" in canonical_ids
        assert "succinate" in canonical_ids

    def test_unit_normalized_correctly(self) -> None:
        meta = _make_metadata(options={"unit": "mmol/kg"})
        loader = MetaboliteLoader(meta)
        payload = loader.load(FIXTURES / "metabolites_rows.tsv")

        units = {r["unit"] for r in payload.raw_data}
        assert units == {"mmol_kg"}

    def test_record_has_required_fields(self) -> None:
        meta = _make_metadata(options={"unit": "mmol/kg"})
        loader = MetaboliteLoader(meta)
        payload = loader.load(FIXTURES / "metabolites_rows.tsv")

        rec = payload.raw_data[0]
        assert "sample_id" in rec
        assert "metabolite_id" in rec
        assert "canonical_id" in rec
        assert "value" in rec
        assert "unit" in rec
        assert "source_id" in rec
        assert "species" in rec
        assert "gut_segment" in rec

    def test_provenance_metadata_present(self) -> None:
        meta = _make_metadata(source_id="holofood-chicken", options={"unit": "mmol/kg"})
        loader = MetaboliteLoader(meta)
        payload = loader.load(FIXTURES / "metabolites_rows.tsv")

        for rec in payload.raw_data:
            assert rec["source_id"] == "holofood-chicken"
            assert rec["species"] == "chicken"
            assert rec["gut_segment"] == "cecum"

    def test_scfa_found_in_extra(self) -> None:
        meta = _make_metadata(options={"unit": "mmol/kg", "id_column": "database_identifier"})
        loader = MetaboliteLoader(meta)
        payload = loader.load(FIXTURES / "metabolites_rows.tsv")

        scfa_found = payload.extra.get("scfa_found", [])
        assert "acetate" in scfa_found
        assert "propionate" in scfa_found
        assert "butyrate" in scfa_found

    def test_values_are_positive(self) -> None:
        meta = _make_metadata(options={"unit": "mmol/kg"})
        loader = MetaboliteLoader(meta)
        payload = loader.load(FIXTURES / "metabolites_rows.tsv")

        for rec in payload.raw_data:
            assert rec["value"] >= 0.0

    def test_comment_lines_ignored(self) -> None:
        """La tabla with_comments.tsv tiene 3 líneas de comentario y 3 metabolitos × 3 muestras."""
        meta = _make_metadata(options={"unit": "mmol/kg"})
        loader = MetaboliteLoader(meta)
        payload = loader.load(FIXTURES / "with_comments.tsv")

        assert payload.records_count == 9  # 3 metabolitos × 3 muestras


# ---------------------------------------------------------------------------
# Tests de MetaboliteLoader — orientación metabolite_cols
# ---------------------------------------------------------------------------


class TestMetaboliteLoaderCols:
    def test_cols_orientation_load(self) -> None:
        """3 muestras × 4 metabolitos = 12 registros."""
        meta = _make_metadata(
            options={"orientation": "metabolite_cols", "format": "csv", "unit": "mmol_kg"}
        )
        loader = MetaboliteLoader(meta)
        payload = loader.load(FIXTURES / "metabolites_cols.csv")

        assert payload.records_count == 12

    def test_cols_scfa_canonical_ids(self) -> None:
        meta = _make_metadata(options={"orientation": "metabolite_cols", "unit": "mmol_kg"})
        loader = MetaboliteLoader(meta)
        payload = loader.load(FIXTURES / "metabolites_cols.csv")

        canonical_ids = {r["canonical_id"] for r in payload.raw_data}
        assert "acetate" in canonical_ids
        assert "propionate" in canonical_ids
        assert "butyrate" in canonical_ids
        assert "lactate" in canonical_ids

    def test_cols_values_non_negative(self) -> None:
        meta = _make_metadata(options={"orientation": "metabolite_cols", "unit": "mmol_kg"})
        loader = MetaboliteLoader(meta)
        payload = loader.load(FIXTURES / "metabolites_cols.csv")

        for rec in payload.raw_data:
            assert rec["value"] >= 0.0


# ---------------------------------------------------------------------------
# Tests de MetaboliteLoader — casos límite
# ---------------------------------------------------------------------------


class TestMetaboliteLoaderEdgeCases:
    def test_empty_file_returns_empty_payload(self, tmp_path: Path) -> None:
        empty_file = tmp_path / "empty.tsv"
        empty_file.write_text("chemical_name\tS1\n", encoding="utf-8")
        meta = _make_metadata(options={"unit": "mmol_kg"})
        loader = MetaboliteLoader(meta)
        payload = loader.load(empty_file)

        assert payload.records_count == 0
        assert payload.raw_data == []

    def test_negative_values_clamped_to_zero(self, tmp_path: Path) -> None:
        content = "chemical_name\tS1\tacetic acid\n-1.5\t\n"
        # Construir fixture correcto
        content = "chemical_name\tS1\nacetic acid\t-1.5\n"
        tsv_file = tmp_path / "neg.tsv"
        tsv_file.write_text(content, encoding="utf-8")
        meta = _make_metadata(options={"unit": "mmol_kg"})
        loader = MetaboliteLoader(meta)
        payload = loader.load(tsv_file)

        for rec in payload.raw_data:
            assert rec["value"] >= 0.0

    def test_invalid_orientation_raises(self, tmp_path: Path) -> None:
        tsv_file = tmp_path / "data.tsv"
        tsv_file.write_text("chemical_name\tS1\nacetic acid\t1.0\n", encoding="utf-8")
        meta = _make_metadata(options={"orientation": "invalid_orientation", "unit": "mmol_kg"})
        loader = MetaboliteLoader(meta)

        with pytest.raises(ValueError, match="orientation"):
            loader.load(tsv_file)

    def test_missing_file_raises(self) -> None:
        meta = _make_metadata()
        loader = MetaboliteLoader(meta)

        with pytest.raises(FileNotFoundError):
            loader.load(Path("/nonexistent/path/metabolites.tsv"))

    def test_non_numeric_values_skipped(self, tmp_path: Path) -> None:
        content = "chemical_name\tS1\tS2\nacetic acid\t1.2\tn/a\npropionic acid\tnd\t0.5\n"
        tsv_file = tmp_path / "mixed.tsv"
        tsv_file.write_text(content, encoding="utf-8")
        meta = _make_metadata(options={"unit": "mmol_kg"})
        loader = MetaboliteLoader(meta)
        payload = loader.load(tsv_file)

        # Solo valores numéricos válidos se incluyen: 1.2 y 0.5
        assert payload.records_count == 2
        for rec in payload.raw_data:
            assert isinstance(rec["value"], float)


# ---------------------------------------------------------------------------
# Revisión de #52: valores no finitos, unidades y registro de errores
# ---------------------------------------------------------------------------


def _load_text(tmp_path: Path, content: str, **options: object) -> IngestionPayload:
    tsv = tmp_path / "metabolites.tsv"
    tsv.write_text(content, encoding="utf-8")
    return MetaboliteLoader(_make_metadata(options=dict(options))).load(tsv)


class TestMetaboliteReadErrors:
    """Los errores de lectura se registran sin detener el pipeline."""

    @pytest.mark.parametrize("raw", ["nan", "NaN", "inf", "-inf"])
    def test_non_finite_value_is_skipped_not_zero(self, tmp_path: Path, raw: str) -> None:
        payload = _load_text(tmp_path, f"chemical_name\tS1\tS2\nAcetic acid\t{raw}\t1.5\n")
        assert [(r["sample_id"], r["value"]) for r in payload.raw_data] == [("S2", 1.5)]
        assert "no finito" in payload.extra["errors"][0]

    def test_non_numeric_value_is_logged(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="nutrigraphdt.data.loaders.metabolite"):
            payload = _load_text(tmp_path, "chemical_name\tS1\tS2\nAcetic acid\tabc\t1.5\n")
        assert payload.records_count == 1
        assert "no numérico 'abc'" in payload.extra["errors"][0]
        assert "abc" in caplog.text

    def test_negative_value_is_logged(self, tmp_path: Path) -> None:
        payload = _load_text(tmp_path, "chemical_name\tS1\nAcetic acid\t-2\n")
        assert payload.raw_data[0]["value"] == 0.0
        assert "negativo" in payload.extra["errors"][0]

    def test_empty_cell_is_missing_without_error(self, tmp_path: Path) -> None:
        payload = _load_text(tmp_path, "chemical_name\tS1\tS2\nAcetic acid\t\t1.5\n")
        assert payload.records_count == 1
        assert payload.extra["errors"] == []

    def test_unreadable_file_returns_empty_payload(self, tmp_path: Path) -> None:
        tsv = tmp_path / "latin1.tsv"
        tsv.write_bytes("chemical_name\tS1\nácido acético\t1\n".encode("latin-1"))
        payload = MetaboliteLoader(_make_metadata()).load(tsv)
        assert payload.records_count == 0
        assert "No se pudo leer" in payload.extra["errors"][0]

    def test_clean_fixture_has_no_errors(self) -> None:
        payload = MetaboliteLoader(_make_metadata()).load(FIXTURES / "metabolites_rows.tsv")
        assert payload.extra["errors"] == []


class TestMetaboliteUnits:
    """Unificación de unidades de concentración."""

    def test_unknown_unit_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="ppm"):
            _load_text(tmp_path, "chemical_name\tS1\nAcetic acid\t1\n", unit="ppm")

    def test_umol_g_is_converted_to_mmol_kg(self, tmp_path: Path) -> None:
        payload = _load_text(tmp_path, "chemical_name\tS1\nAcetic acid\t2.5\n", unit="µmol/g")
        record = payload.raw_data[0]
        assert (record["value"], record["unit"]) == (2.5, "mmol_kg")
        assert payload.extra["source_unit"] == "umol_g"
        assert payload.extra["canonical_unit"] == "mmol_kg"

    def test_mm_is_kept(self, tmp_path: Path) -> None:
        payload = _load_text(tmp_path, "chemical_name\tS1\nAcetic acid\t2.5\n", unit="mmol/L")
        assert payload.raw_data[0]["unit"] == "mM"

    def test_isobutyrate_kegg_id(self) -> None:
        assert map_metabolite_name("C02632") == "isobutyrate"
