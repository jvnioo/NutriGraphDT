"""Loader especializado para tablas de abundancia microbiana en formato TSV/CSV.

Soporta cualquier tabla donde las filas son taxa/OTUs/MAGs y las columnas
son muestras (o viceversa), configurada mediante configs/sources.json.

Comportamiento:
- Lee el archivo TSV o CSV indicado en SourceMetadata.path_or_url.
- Detecta automáticamente si la orientación es taxa-en-filas o taxa-en-columnas
  según la opción ``orientation`` (``"taxa_rows"`` por defecto).
- Normaliza cada muestra a abundancia relativa si la columna no está ya
  normalizada (suma <= 1.0 + tolerancia) y la opción ``normalize`` es True.
- Devuelve un IngestionPayload cuyo raw_data es una lista de dicts con las
  claves: ``sample_id``, ``taxon_id``, ``value``, ``unit``.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

from nutrigraphdt.data.loaders.base import BaseLoader, IngestionPayload

# Tolerancia para considerar que una muestra ya está normalizada a suma <= 1.
_NORM_TOLERANCE: float = 1e-6


def _detect_delimiter(path: Path, options: dict[str, Any]) -> str:
    """Devuelve el delimitador a usar: primero el de options, luego la extensión."""
    if "delimiter" in options:
        return options["delimiter"]
    return "\t" if path.suffix.lower() in {".tsv", ".txt"} else ","


def _normalize_column(values: list[float]) -> list[float]:
    """Normaliza una lista de valores a abundancias relativas (suma -> 1.0).

    Si la suma es 0 todos los valores quedan en 0. Si ya están normalizados
    (suma <= 1 + tolerancia) se devuelven sin cambios.
    """
    total = sum(values)
    if total <= 0.0:
        return [0.0] * len(values)
    if total <= 1.0 + _NORM_TOLERANCE:
        return values  # ya normalizados
    return [v / total for v in values]


class AbundanceLoader(BaseLoader):
    """Carga tablas de abundancia microbiana (TSV/CSV) a un IngestionPayload.

    Opciones reconocidas en ``SourceMetadata.options``
    --------------------------------------------------
    delimiter : str
        Delimitador de columnas. Por defecto ``"\\t"`` para ``.tsv`` y ``","``
        para ``.csv``.
    encoding : str
        Codificación del archivo (por defecto ``"utf-8"``).
    comment_char : str
        Carácter que marca líneas de comentario a ignorar (por defecto ``"#"``).
    taxon_column : str
        Nombre de la columna que contiene los identificadores de taxa.
        Por defecto ``"taxon_id"``.
    orientation : str
        ``"taxa_rows"`` (default): filas = taxa, columnas = muestras.
        ``"taxa_cols"``: columnas = taxa, filas = muestras.
    normalize : bool
        Si ``True`` (default), normaliza cada muestra a abundancia relativa.
        Si ``False``, usa los valores tal como están en el archivo.
    """

    def load(self, source_path: Path | str | None = None) -> IngestionPayload:
        """Lee la tabla de abundancia y devuelve un IngestionPayload normalizado."""
        path = self.resolve_path(source_path)
        opts = self.metadata.options

        encoding: str = opts.get("encoding", "utf-8")
        comment_char: str = opts.get("comment_char", "#")
        taxon_col: str = opts.get("taxon_column", "taxon_id")
        orientation: str = opts.get("orientation", "taxa_rows")
        # Cast explícito: tolera que options venga de JSON con string "true"/"false"
        # o que el tipo no sea exactamente bool.
        normalize_raw = opts.get("normalize", True)
        should_normalize: bool = bool(normalize_raw)

        delimiter = _detect_delimiter(path, opts)

        with open(path, encoding=encoding, newline="") as fh:
            lines = (ln for ln in fh if not (comment_char and ln.startswith(comment_char)))
            reader = csv.DictReader(lines, delimiter=delimiter)
            rows: list[dict[str, str]] = [
                {k.strip(): v.strip() for k, v in row.items() if k is not None} for row in reader
            ]

        if not rows:
            return IngestionPayload(
                metadata=self.metadata,
                raw_data=[],
                records_count=0,
                extra={"source_path": str(path), "normalized": False},
            )

        if orientation == "taxa_rows":
            records = self._parse_taxa_rows(rows, taxon_col, should_normalize)
        elif orientation == "taxa_cols":
            records = self._parse_taxa_cols(rows, should_normalize)
        else:
            raise ValueError(
                f"orientation '{orientation}' no reconocida. Usar 'taxa_rows' o 'taxa_cols'."
            )

        return IngestionPayload(
            metadata=self.metadata,
            raw_data=records,
            records_count=len(records),
            extra={
                "source_path": str(path),
                "normalized": should_normalize,
                "orientation": orientation,
                "taxon_column": taxon_col,
            },
        )

    # ------------------------------------------------------------------
    # Métodos de parsing internos
    # ------------------------------------------------------------------

    def _parse_taxa_rows(
        self,
        rows: list[dict[str, str]],
        taxon_col: str,
        normalize: bool,
    ) -> list[dict[str, Any]]:
        """Procesa tabla donde filas=taxa, columnas=muestras."""
        if not rows:
            return []

        # Inferir columna de taxón si no existe exactamente la configurada
        header = list(rows[0].keys())
        actual_taxon_col = taxon_col if taxon_col in header else header[0]
        sample_cols = [c for c in header if c != actual_taxon_col]

        # Construir matriz {sample -> {taxon -> value}}
        matrix: dict[str, dict[str, float]] = {s: {} for s in sample_cols}
        for row in rows:
            taxon_id = row.get(actual_taxon_col, "").strip()
            if not taxon_id:
                continue
            for sample in sample_cols:
                raw = row.get(sample, "").strip()
                try:
                    val = float(raw) if raw else 0.0
                except ValueError:
                    val = 0.0
                # La abundancia microbiana nunca puede ser negativa; clampar a 0.
                val = max(0.0, val)
                if math.isfinite(val):
                    matrix[sample][taxon_id] = val

        return self._matrix_to_records(matrix, normalize)

    def _parse_taxa_cols(
        self,
        rows: list[dict[str, str]],
        normalize: bool,
    ) -> list[dict[str, Any]]:
        """Procesa tabla donde filas=muestras, columnas=taxa."""
        if not rows:
            return []

        header = list(rows[0].keys())
        sample_col = header[0]
        taxon_cols = header[1:]

        matrix: dict[str, dict[str, float]] = {}
        for row in rows:
            sample_id = row.get(sample_col, "").strip()
            if not sample_id:
                continue
            matrix[sample_id] = {}
            for taxon_id in taxon_cols:
                raw = row.get(taxon_id, "").strip()
                try:
                    val = float(raw) if raw else 0.0
                except ValueError:
                    val = 0.0
                # La abundancia microbiana nunca puede ser negativa; clampar a 0.
                val = max(0.0, val)
                if math.isfinite(val):
                    matrix[sample_id][taxon_id] = val

        return self._matrix_to_records(matrix, normalize)

    def _matrix_to_records(
        self,
        matrix: dict[str, dict[str, float]],
        normalize: bool,
    ) -> list[dict[str, Any]]:
        """Convierte la matriz {sample -> {taxon -> value}} a lista de registros."""
        records: list[dict[str, Any]] = []
        for sample_id, taxon_values in matrix.items():
            if not taxon_values:
                continue
            taxa = list(taxon_values.keys())
            values = [taxon_values[t] for t in taxa]

            if normalize:
                values = _normalize_column(values)
                unit = "relative_abundance"
            else:
                unit = self.metadata.options.get("unit", "relative_abundance")

            for taxon_id, value in zip(taxa, values, strict=True):
                records.append(
                    {
                        "sample_id": sample_id,
                        "taxon_id": taxon_id,
                        "value": value,
                        "unit": unit,
                        "source_id": self.metadata.source_id,
                        "species": self.metadata.species,
                        "gut_segment": self.metadata.gut_segment,
                    }
                )
        return records
