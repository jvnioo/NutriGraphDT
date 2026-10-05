"""Loader para metadatos de dieta y fenotipo por muestra.

Implementa MetadataLoader, que:
- Lee tablas de metadatos por muestra en formato TSV/CSV.
- Normaliza columnas clave (diet_treatment, phenotype scores, body metrics)
  al formato intermedio del schema.
- Devuelve un IngestionPayload cuyo raw_data es una lista de dicts con las
  claves: ``sample_id``, ``field``, ``value``, ``unit``, ``field_type``,
  ``source_id``, ``species``, ``gut_segment``.

Formato de entrada esperado
---------------------------
El archivo TSV/CSV debe tener una columna de identificador de muestra
(configurable via ``sample_column``, por defecto ``"sample_id"``) y el
resto de columnas son variables de metadatos.

Ejemplo::

    sample_id  diet_treatment  body_weight_g  feed_conversion_ratio  health_score
    S1         high_fiber      2500           1.8                    3.2
    S2         control         2350           2.1                    2.9
    S3         high_fiber      2480           1.9                    3.0

Los tipos de campo (``field_type``) se infieren automáticamente desde el
nombre de la columna o desde el mapa ``column_types`` en options.

Tipos de campo reconocidos
--------------------------
- ``diet``      — variables relacionadas con el tratamiento dietético.
- ``phenotype`` — variables de fenotipo productivo o clínico.
- ``numeric``   — variables numéricas no clasificadas.
- ``categorical`` — variables categóricas no numéricas.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

from nutrigraphdt.data.loaders.base import BaseLoader, IngestionPayload

# ---------------------------------------------------------------------------
# Clasificación automática de columnas por nombre
# ---------------------------------------------------------------------------

# Palabras clave que indican campo de tipo "diet"
_DIET_KEYWORDS: frozenset[str] = frozenset(
    {
        "diet",
        "treatment",
        "feed",
        "feeding",
        "supplement",
        "additive",
        "diet_treatment",
        "dietary",
        "ration",
        "group",
    }
)

# Palabras clave que indican campo de tipo "phenotype"
_PHENOTYPE_KEYWORDS: frozenset[str] = frozenset(
    {
        "weight",
        "bw",
        "fcr",
        "feed_conversion",
        "adg",
        "daily_gain",
        "health",
        "score",
        "mortality",
        "lesion",
        "villus",
        "crypt",
        "digestibility",
        "efficiency",
        "body",
        "phenotype",
    }
)

# Unidades por defecto para columnas con nombres específicos
_COLUMN_DEFAULT_UNITS: dict[str, str] = {
    "body_weight_g": "g",
    "body_weight": "g",
    "bw": "g",
    "feed_conversion_ratio": "ratio",
    "fcr": "ratio",
    "health_score": "score",
    "daily_gain_g": "g",
    "adg": "g",
    "digestibility": "proportion",
}


def infer_field_type(column_name: str, column_types: dict[str, str] | None = None) -> str:
    """Infiere el tipo de campo a partir del nombre de la columna.

    Parameters
    ----------
    column_name:
        Nombre original de la columna (insensible a mayúsculas).
    column_types:
        Mapa explícito ``{column_name: field_type}`` proveniente de options.
        Tiene prioridad sobre la inferencia automática.

    Returns
    -------
    str
        Uno de: ``"diet"``, ``"phenotype"``, ``"numeric"``, ``"categorical"``.
    """
    if column_types and column_name in column_types:
        return column_types[column_name]

    key = column_name.lower().replace("-", "_").replace(" ", "_")

    # Comprobar primero phenotype para que términos específicos como
    # "feed_conversion_ratio" tengan prioridad sobre la keyword genérica "feed".
    for kw in _PHENOTYPE_KEYWORDS:
        if kw in key:
            return "phenotype"

    for kw in _DIET_KEYWORDS:
        if kw in key:
            return "diet"

    return "numeric"


def _is_numeric(value: str) -> bool:
    """Retorna True si el string puede convertirse a float."""
    try:
        float(value)
        return True
    except ValueError:
        return False


def _detect_delimiter(path: Path, options: dict[str, Any]) -> str:
    """Devuelve el delimitador a usar: primero el de options, luego la extensión."""
    if "delimiter" in options:
        return str(options["delimiter"])
    return "\t" if path.suffix.lower() in {".tsv", ".txt"} else ","


class MetadataLoader(BaseLoader):
    """Carga metadatos de dieta y fenotipo por muestra a un IngestionPayload.

    Opciones reconocidas en ``SourceMetadata.options``
    --------------------------------------------------
    delimiter : str
        Delimitador de columnas. Por defecto ``"\\t"`` para ``.tsv`` y ``","``
        para ``.csv``.
    encoding : str
        Codificación del archivo (por defecto ``"utf-8"``).
    comment_char : str
        Carácter de comentario a ignorar (por defecto ``"#"``).
    sample_column : str
        Nombre de la columna que contiene el ID de muestra.
        Por defecto ``"sample_id"``.
    skip_columns : list[str]
        Lista de columnas a ignorar además de la columna de muestra.
    column_types : dict[str, str]
        Mapa explícito ``{column: field_type}`` que tiene prioridad sobre la
        inferencia automática. Tipos válidos: ``"diet"``, ``"phenotype"``,
        ``"numeric"``, ``"categorical"``.
    column_units : dict[str, str]
        Mapa ``{column: unit}`` para columnas con unidad conocida.
        Complementa el mapa interno ``_COLUMN_DEFAULT_UNITS``.
    default_unit : str
        Unidad a usar cuando no hay mapeo específico para una columna
        numérica (por defecto ``"dimensionless"``).
    """

    def load(self, source_path: Path | str | None = None) -> IngestionPayload:
        """Lee la tabla de metadatos y devuelve un IngestionPayload."""
        path = self.resolve_path(source_path)
        opts = self.metadata.options

        encoding: str = opts.get("encoding", "utf-8")
        comment_char: str = opts.get("comment_char", "#")
        sample_col: str = opts.get("sample_column", "sample_id")
        skip_cols: list[str] = list(opts.get("skip_columns", []))
        column_types: dict[str, str] = dict(opts.get("column_types", {}))
        column_units: dict[str, str] = dict(opts.get("column_units", {}))
        default_unit: str = opts.get("default_unit", "dimensionless")

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
                extra={"source_path": str(path)},
            )

        # Resolver la columna de muestra
        header = list(rows[0].keys())
        actual_sample_col = sample_col if sample_col in header else header[0]

        # Columnas de datos (excluir muestra y skip_columns)
        excluded = {actual_sample_col} | set(skip_cols)
        data_cols = [c for c in header if c not in excluded]

        records = self._parse_rows(
            rows,
            actual_sample_col,
            data_cols,
            column_types,
            column_units,
            default_unit,
        )

        # Contabilizar tipos de campo encontrados
        field_types_found = sorted({r["field_type"] for r in records})

        return IngestionPayload(
            metadata=self.metadata,
            raw_data=records,
            records_count=len(records),
            extra={
                "source_path": str(path),
                "sample_column": actual_sample_col,
                "data_columns": data_cols,
                "field_types_found": field_types_found,
            },
        )

    # ------------------------------------------------------------------
    # Métodos internos
    # ------------------------------------------------------------------

    def _parse_rows(
        self,
        rows: list[dict[str, str]],
        sample_col: str,
        data_cols: list[str],
        column_types: dict[str, str],
        column_units: dict[str, str],
        default_unit: str,
    ) -> list[dict[str, Any]]:
        """Convierte filas de la tabla a registros normalizados."""
        records: list[dict[str, Any]] = []

        for row in rows:
            sample_id = row.get(sample_col, "").strip()
            if not sample_id:
                continue

            for col in data_cols:
                raw_value = row.get(col, "").strip()
                if raw_value == "":
                    continue

                field_type = infer_field_type(col, column_types)

                if _is_numeric(raw_value):
                    parsed_val: float | str = float(raw_value)
                    # Las métricas de fenotipo no pueden ser negativas
                    if field_type in ("phenotype", "numeric") and isinstance(parsed_val, float):
                        parsed_val = max(0.0, parsed_val)
                    if isinstance(parsed_val, float) and not math.isfinite(parsed_val):
                        continue
                    unit = self._resolve_unit(col, column_units, default_unit)
                else:
                    # Valor categórico
                    parsed_val = raw_value
                    field_type = column_types.get(col, "categorical")
                    unit = "dimensionless"

                records.append(
                    {
                        "sample_id": sample_id,
                        "field": col,
                        "value": parsed_val,
                        "unit": unit,
                        "field_type": field_type,
                        "source_id": self.metadata.source_id,
                        "species": self.metadata.species,
                        "gut_segment": self.metadata.gut_segment,
                    }
                )

        return records

    def _resolve_unit(
        self,
        column_name: str,
        column_units: dict[str, str],
        default_unit: str,
    ) -> str:
        """Devuelve la unidad para una columna numérica."""
        if column_name in column_units:
            return column_units[column_name]
        col_key = column_name.lower().replace("-", "_").replace(" ", "_")
        if col_key in _COLUMN_DEFAULT_UNITS:
            return _COLUMN_DEFAULT_UNITS[col_key]
        return default_unit
