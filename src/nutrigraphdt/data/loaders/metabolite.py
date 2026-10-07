"""Loader para perfiles de metabolitos en formato MetaboLights (TSV/CSV).

Implementa MetaboliteLoader, que:
- Lee tablas de concentración de metabolitos (filas = metabolitos, columnas = muestras,
  o viceversa según ``orientation``).
- Mapea nombres de metabolitos a identificadores canónicos priorizando los
  SCFA relevantes: acetato, propionato y butirato.
- Unifica las unidades de concentración declaradas por la fuente al conjunto
  canónico de CANONICAL_UNITS definido en schema.py. Una unidad sin equivalente canónico
  levanta ``ValueError``, y µmol/g se convierte a mmol/kg (factor 1).
- Registra los errores de lectura (celdas no numéricas o no finitas, negativos, filas sin
  identificador, archivos ilegibles) en el log y en ``extra["errors"]`` sin detener el
  pipeline.
- Devuelve un IngestionPayload cuyo raw_data es una lista de dicts con las
  claves: ``sample_id``, ``metabolite_id``, ``canonical_id``, ``value``,
  ``unit``, ``source_id``, ``species``, ``gut_segment``.

Formato de entrada esperado (orientación ``metabolite_rows``, por defecto)
--------------------------------------------------------------------------
Ejemplo de archivo TSV (formato MetaboLights m_*_v2_maf.tsv simplificado)::

    database_identifier  chemical_name        S1     S2     S3
    C00033               acetic acid          1.2    0.8    2.1
    C00163               propionic acid       0.5    1.1    0.3
    C00246               butyric acid         0.9    0.6    1.4

Si no hay columna ``database_identifier`` se puede usar el campo
``metabolite_column`` para indicar qué columna contiene el nombre del
metabolito.
"""

from __future__ import annotations

import csv
import logging
import math
from pathlib import Path
from typing import Any

from nutrigraphdt.data.loaders.base import BaseLoader, IngestionPayload
from nutrigraphdt.data.schema import CANONICAL_UNITS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapeo canónico de metabolitos
# ---------------------------------------------------------------------------

# Mapeo de alias → ID canónico (clave minúscula sin espacios para comparación).
# Prioriza SCFA (ácidos grasos de cadena corta) clave para el proyecto.
_CANONICAL_METABOLITE_MAP: dict[str, str] = {
    # Acetato / ácido acético
    "acetate": "acetate",
    "acetic acid": "acetate",
    "acetic_acid": "acetate",
    "aceticacid": "acetate",
    "c00033": "acetate",
    "chebi:30089": "acetate",
    # Propionato / ácido propiónico
    "propionate": "propionate",
    "propionic acid": "propionate",
    "propionic_acid": "propionate",
    "propionicacid": "propionate",
    "c00163": "propionate",
    "chebi:17272": "propionate",
    # Butirato / ácido butírico
    "butyrate": "butyrate",
    "butyric acid": "butyrate",
    "butyric_acid": "butyrate",
    "butyricacid": "butyrate",
    "n-butyrate": "butyrate",
    "n-butyric acid": "butyrate",
    "c00246": "butyrate",
    "chebi:17968": "butyrate",
    # Otros SCFA / metabolitos comunes
    "formate": "formate",
    "formic acid": "formate",
    "formic_acid": "formate",
    "c00058": "formate",
    "lactate": "lactate",
    "lactic acid": "lactate",
    "lactic_acid": "lactate",
    "c00186": "lactate",
    "succinate": "succinate",
    "succinic acid": "succinate",
    "succinic_acid": "succinate",
    "c00042": "succinate",
    "valerate": "valerate",
    "valeric acid": "valerate",
    "valeric_acid": "valerate",
    "pentanoic acid": "valerate",
    "n-valeric acid": "valerate",
    "c00803": "valerate",
    "isobutyrate": "isobutyrate",
    "isobutyric acid": "isobutyrate",
    "i-butyric acid": "isobutyrate",
    "2-methylpropanoic acid": "isobutyrate",
    "c02632": "isobutyrate",
    "isovalerate": "isovalerate",
    "isovaleric acid": "isovalerate",
    "i-valeric acid": "isovalerate",
    "3-methylbutanoic acid": "isovalerate",
    "c11118": "isovalerate",
}

# Conjunto de IDs canónicos SCFA (para etiquetar en extra)
SCFA_CANONICAL_IDS: frozenset[str] = frozenset(
    {
        "acetate",
        "propionate",
        "butyrate",
        "formate",
        "lactate",
        "succinate",
        "valerate",
        "isobutyrate",
        "isovalerate",
    }
)

# ---------------------------------------------------------------------------
# Mapeo de unidades de fuente → unidad canónica
# ---------------------------------------------------------------------------

_UNIT_NORMALIZATION_MAP: dict[str, str] = {
    # mmol/kg y variantes
    "mmol/kg": "mmol_kg",
    "mmol kg-1": "mmol_kg",
    "mmol·kg-1": "mmol_kg",
    "mmol·kg⁻¹": "mmol_kg",
    "mmol_kg": "mmol_kg",
    # µmol/g y variantes
    "umol/g": "umol_g",
    "µmol/g": "umol_g",
    "umol g-1": "umol_g",
    "µmol g-1": "umol_g",
    "umol_g": "umol_g",
    # mM (milimolar)
    "mm": "mM",
    "mm ": "mM",
    "mmol/l": "mM",
    "mmol l-1": "mM",
    "mmol/l ": "mM",
    "mM": "mM",
    # mg/kg
    "mg/kg": "mg_kg",
    "mg kg-1": "mg_kg",
    "mg·kg-1": "mg_kg",
    "mg_kg": "mg_kg",
    # g/kg
    "g/kg": "g_kg",
    "g kg-1": "g_kg",
    "g_kg": "g_kg",
    # proporción / fracción
    "proportion": "proportion",
    "fraction": "proportion",
    "relative": "proportion",
    # adimensional / score
    "dimensionless": "dimensionless",
    "score": "score",
    "au": "dimensionless",
    "arbitrary unit": "dimensionless",
    "arbitrary units": "dimensionless",
}


# Conversiones numéricas entre unidades canónicas. 1 µmol/g = 1 mmol/kg, de modo que los
# perfiles en µmol/g se unifican a mmol/kg (unidad estándar de AGCC) sin cambiar el valor.
# mM (por litro) y mg/kg no se convierten: requieren densidad o masa molar.
_UNIT_CONVERSIONS: dict[str, tuple[str, float]] = {
    "umol_g": ("mmol_kg", 1.0),
}


def map_metabolite_name(raw_name: str) -> str:
    """Devuelve el ID canónico para un nombre de metabolito.

    La búsqueda es insensible a mayúsculas y espacios extra.
    Si no hay coincidencia, devuelve el nombre original en minúsculas con
    espacios internos convertidos a guiones bajos (slug).

    Parameters
    ----------
    raw_name:
        Nombre original tal como aparece en el archivo fuente
        (p. ej. ``"Acetic Acid"``, ``"C00033"``, ``"butyrate"``).

    Returns
    -------
    str
        ID canónico (p. ej. ``"acetate"``) o slug del nombre original.
    """
    key = raw_name.strip().lower()
    if key in _CANONICAL_METABOLITE_MAP:
        return _CANONICAL_METABOLITE_MAP[key]
    return key.replace(" ", "_")


def normalize_unit(raw_unit: str) -> str:
    """Devuelve la unidad canónica correspondiente a la unidad de la fuente.

    Parameters
    ----------
    raw_unit:
        Unidad tal como aparece en el archivo fuente (p. ej. ``"mmol/kg"``,
        ``"µmol/g"``, ``"mM"``).

    Returns
    -------
    str
        Unidad canónica si existe mapeo; de lo contrario la unidad original
        en minúsculas (para no perder información).
    """
    key = raw_unit.strip().lower()
    canonical = _UNIT_NORMALIZATION_MAP.get(key)
    if canonical is not None and canonical in CANONICAL_UNITS:
        return canonical
    # Intentar matchear la unidad original exacta (case-sensitive) en CANONICAL_UNITS
    if raw_unit.strip() in CANONICAL_UNITS:
        return raw_unit.strip()
    # Devolver lowercase como fallback; el preprocesador puede revisar después
    return key


def _detect_delimiter(path: Path, options: dict[str, Any]) -> str:
    """Devuelve el delimitador a usar: primero el de options, luego la extensión."""
    if "delimiter" in options:
        return str(options["delimiter"])
    return "\t" if path.suffix.lower() in {".tsv", ".txt", ".maf"} else ","


class MetaboliteLoader(BaseLoader):
    """Carga perfiles de metabolitos en formato MetaboLights/TSV a un IngestionPayload.

    Opciones reconocidas en ``SourceMetadata.options``
    --------------------------------------------------
    delimiter : str
        Delimitador de columnas. Por defecto ``"\\t"`` para ``.tsv``/``.maf``
        y ``","`` para ``.csv``.
    encoding : str
        Codificación del archivo (por defecto ``"utf-8"``).
    comment_char : str
        Carácter que marca líneas de comentario a ignorar (por defecto ``"#"``).
    metabolite_column : str
        Nombre de la columna que contiene los identificadores de metabolitos.
        Por defecto ``"chemical_name"``. Si no existe, se usa la primera columna.
    id_column : str
        Columna opcional con identificadores de base de datos (p. ej.
        ``"database_identifier"``). Si existe, se usa como clave primaria
        de búsqueda en el mapeo canónico.
    orientation : str
        ``"metabolite_rows"`` (default): filas = metabolitos, columnas = muestras.
        ``"metabolite_cols"``: columnas = metabolitos, filas = muestras.
    unit : str
        Unidad de concentración declarada por la fuente. Se unifica al
        conjunto canónico mediante ``normalize_unit``. Por defecto ``"mmol_kg"``.
    """

    def load(self, source_path: Path | str | None = None) -> IngestionPayload:
        """Lee la tabla de metabolitos y devuelve un IngestionPayload.

        Los errores de lectura se registran en el log y en ``extra["errors"]`` sin detener el
        pipeline; solo una configuración inválida (unidad u orientación desconocidas, ruta
        inexistente) levanta error.
        """
        path = self.resolve_path(source_path)
        opts = self.metadata.options

        encoding = str(opts.get("encoding", "utf-8"))
        comment_char = str(opts.get("comment_char", "#"))
        metabolite_col = str(opts.get("metabolite_column", "chemical_name"))
        raw_id_col = opts.get("id_column", "database_identifier")
        id_col: str | None = str(raw_id_col) if raw_id_col else None
        orientation = str(opts.get("orientation", "metabolite_rows"))
        raw_unit = str(opts.get("unit", "mmol_kg"))

        if orientation not in {"metabolite_rows", "metabolite_cols"}:
            raise ValueError(
                f"orientation '{orientation}' no reconocida. "
                "Usar 'metabolite_rows' o 'metabolite_cols'."
            )
        source_unit = normalize_unit(raw_unit)
        if source_unit not in CANONICAL_UNITS:
            raise ValueError(
                f"Unidad '{raw_unit}' de la fuente '{self.metadata.source_id}' sin equivalente "
                f"canónico. Permitidas: {sorted(CANONICAL_UNITS)}"
            )
        canonical_unit, factor = _UNIT_CONVERSIONS.get(source_unit, (source_unit, 1.0))

        errors: list[str] = []
        extra: dict[str, Any] = {
            "source_path": str(path),
            "source_unit": source_unit,
            "canonical_unit": canonical_unit,
            "orientation": orientation,
            "errors": errors,
        }

        delimiter = _detect_delimiter(path, opts)
        try:
            with open(path, encoding=encoding, newline="") as fh:
                lines = (ln for ln in fh if not (comment_char and ln.startswith(comment_char)))
                reader = csv.DictReader(lines, delimiter=delimiter)
                rows: list[dict[str, str]] = [
                    {k.strip(): (v or "").strip() for k, v in row.items() if k is not None}
                    for row in reader
                ]
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            text = f"[{self.metadata.source_id}] No se pudo leer {path}: {exc}"
            logger.error(text)
            errors.append(text)
            rows = []

        if not rows:
            extra["scfa_found"] = []
            return IngestionPayload(
                metadata=self.metadata, raw_data=[], records_count=0, extra=extra
            )

        if orientation == "metabolite_rows":
            records = self._parse_metabolite_rows(
                rows, metabolite_col, id_col, canonical_unit, factor, errors
            )
        else:
            records = self._parse_metabolite_cols(rows, canonical_unit, factor, errors)

        extra["scfa_found"] = sorted(
            {r["canonical_id"] for r in records if r["canonical_id"] in SCFA_CANONICAL_IDS}
        )
        return IngestionPayload(
            metadata=self.metadata, raw_data=records, records_count=len(records), extra=extra
        )

    # ------------------------------------------------------------------
    # Métodos de parsing internos
    # ------------------------------------------------------------------

    def _parse_metabolite_rows(
        self,
        rows: list[dict[str, str]],
        metabolite_col: str,
        id_col: str | None,
        unit: str,
        factor: float,
        errors: list[str],
    ) -> list[dict[str, Any]]:
        """Procesa tabla donde filas=metabolitos, columnas=muestras."""
        if not rows:
            return []

        header = list(rows[0].keys())

        # Columna del nombre del metabolito: usar la configurada o la primera
        actual_met_col = metabolite_col if metabolite_col in header else header[0]

        # Columna del ID de base de datos (opcional)
        actual_id_col: str | None = id_col if (id_col and id_col in header) else None

        # El resto son columnas de muestras
        non_sample_cols = {actual_met_col}
        if actual_id_col:
            non_sample_cols.add(actual_id_col)
        sample_cols = [c for c in header if c not in non_sample_cols]

        records: list[dict[str, Any]] = []
        for line_no, row in enumerate(rows, start=2):
            name_raw = row.get(actual_met_col, "").strip()
            if not name_raw:
                self._record_error(errors, f"fila {line_no}: nombre de metabolito vacío.")
                continue

            # Determinar clave de búsqueda: ID de BD si existe, sino nombre
            if actual_id_col:
                db_id = row.get(actual_id_col, "").strip()
                lookup_key = db_id if db_id else name_raw
            else:
                lookup_key = name_raw

            canonical_id = map_metabolite_name(lookup_key)

            for sample_id in sample_cols:
                raw = row.get(sample_id, "").strip()
                val = self._parse_value(raw, f"fila {line_no}, muestra '{sample_id}'", errors)
                if val is None:
                    continue
                records.append(
                    self._make_record(sample_id, name_raw, canonical_id, val * factor, unit)
                )

        return records

    def _parse_metabolite_cols(
        self,
        rows: list[dict[str, str]],
        unit: str,
        factor: float,
        errors: list[str],
    ) -> list[dict[str, Any]]:
        """Procesa tabla donde filas=muestras, columnas=metabolitos."""
        if not rows:
            return []

        header = list(rows[0].keys())
        sample_col = header[0]
        met_cols = header[1:]

        records: list[dict[str, Any]] = []
        for line_no, row in enumerate(rows, start=2):
            sample_id = row.get(sample_col, "").strip()
            if not sample_id:
                self._record_error(errors, f"fila {line_no}: identificador de muestra vacío.")
                continue
            for met_name in met_cols:
                raw = row.get(met_name, "").strip()
                val = self._parse_value(raw, f"fila {line_no}, metabolito '{met_name}'", errors)
                if val is None:
                    continue
                canonical_id = map_metabolite_name(met_name)
                records.append(
                    self._make_record(sample_id, met_name, canonical_id, val * factor, unit)
                )

        return records

    def _record_error(self, errors: list[str], message: str) -> None:
        """Registra un error de lectura en el log y en la lista del payload."""
        text = f"[{self.metadata.source_id}] {message}"
        logger.warning(text)
        errors.append(text)

    def _parse_value(self, raw: str, where: str, errors: list[str]) -> float | None:
        """Convierte una celda a concentración; ``None`` si está vacía o es inválida.

        La finitud se comprueba antes de clampar: ``max(0.0, nan)`` devuelve ``0.0`` y
        convertiría un dato faltante en una concentración medida.
        """
        if not raw:
            return None
        try:
            val = float(raw)
        except ValueError:
            self._record_error(errors, f"{where}: valor no numérico '{raw}'; se omite.")
            return None
        if not math.isfinite(val):
            self._record_error(errors, f"{where}: valor no finito '{raw}'; se omite.")
            return None
        if val < 0.0:
            # Las concentraciones no pueden ser negativas; se clampa a 0.
            self._record_error(errors, f"{where}: valor negativo {val}; se usa 0.0.")
            return 0.0
        return val

    def _make_record(
        self,
        sample_id: str,
        metabolite_id: str,
        canonical_id: str,
        value: float,
        unit: str,
    ) -> dict[str, Any]:
        """Construye un registro normalizado."""
        return {
            "sample_id": sample_id,
            "metabolite_id": metabolite_id,
            "canonical_id": canonical_id,
            "value": value,
            "unit": unit,
            "source_id": self.metadata.source_id,
            "species": self.metadata.species,
            "gut_segment": self.metadata.gut_segment,
        }
