"""Loader especializado para tablas de abundancia microbiana (A34-2).

Lleva al formato intermedio (muestra, taxón, abundancia) dos tipos de fuente:

- Tablas TSV/CSV exportadas desde HoloFood/MGnify (16S o shotgun), con los taxa en filas
  (``orientation="taxa_rows"``, por defecto) o en columnas (``"taxa_cols"``).
- El dataset sintético de la actividad 26 (``format="jsonl"``), leído con
  `nutrigraphdt.data.synthetic.load_dataset` o generado en memoria si la fuente declara
  ``generate_if_missing``.

Comportamiento:
- Normaliza los identificadores de muestra (espacios externos fuera, espacios internos a
  ``_``) y de taxón: un linaje con prefijos de rango (``k__``, ``p__``, …, ``s__``,
  separados por ``;`` o ``|``) se reduce a su rango más profundo con nombre, y ese rango
  queda en ``taxon_level``.
- Los errores de lectura (celdas no numéricas o no finitas, valores negativos, filas
  incompletas, identificadores vacíos o duplicados, archivos ilegibles) se registran en el
  log y en ``payload.extra["errors"]`` sin detener el pipeline. Solo una configuración
  inválida (orientación o nivel taxonómico desconocidos, ruta inexistente) levanta error.
- Normaliza cada muestra a abundancia relativa cuando la opción ``normalize`` es verdadera
  y la suma supera 1 + tolerancia.
- Devuelve un IngestionPayload cuyo raw_data es una lista de dicts con las claves
  ``graph_id``, ``sample_id``, ``taxon_id``, ``taxon_level``, ``value``, ``unit``,
  ``source_id``, ``species`` y ``gut_segment``. ``graph_id`` solo se conoce en el dataset
  sintético; en las tablas reales es ``None`` hasta el preprocesamiento (A34-4).
"""

from __future__ import annotations

import csv
import logging
import math
import re
from pathlib import Path
from typing import Any, Final

from nutrigraphdt.data.loaders.base import BaseLoader, IngestionPayload, parse_bool_option
from nutrigraphdt.data.synthetic.export import (
    DatasetFormatError,
    DatasetValidationError,
    SyntheticDataset,
    generate_scenario_dataset,
    load_dataset,
)

logger = logging.getLogger(__name__)

# Tolerancia para considerar que una muestra ya está normalizada a suma <= 1.
_NORM_TOLERANCE: float = 1e-6

# Niveles taxonómicos admitidos en ``taxon_level``. ``clade`` lo usa el dataset sintético
# para gremios sin rango formal; ``otu`` cubre OTUs/ASVs/MAGs sin linaje.
TAXON_LEVELS: Final[frozenset[str]] = frozenset(
    {
        "domain",
        "kingdom",
        "phylum",
        "class",
        "order",
        "family",
        "genus",
        "species",
        "strain",
        "clade",
        "otu",
        "unknown",
    }
)

# Prefijos de rango de MGnify/QIIME (``sk__``, ``k__``…), GTDB (``d__``) y MetaPhlAn (``t__``).
_RANK_PREFIXES: Final[dict[str, str]] = {
    "sk": "domain",
    "d": "domain",
    "k": "kingdom",
    "p": "phylum",
    "c": "class",
    "o": "order",
    "f": "family",
    "g": "genus",
    "s": "species",
    "t": "strain",
}

_RANK_PATTERN = re.compile(r"([a-z]{1,2})__(.*)")
_LINEAGE_SEPARATOR = re.compile(r"[;|]")
_WHITESPACE = re.compile(r"\s+")

# Clave de muestra en la matriz interna: (graph_id, sample_id).
_SampleKey = tuple[str | None, str]


def _detect_delimiter(path: Path, options: dict[str, Any]) -> str:
    """Devuelve el delimitador a usar: primero el de options, luego la extensión."""
    if "delimiter" in options:
        return str(options["delimiter"])
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


def normalize_sample_id(raw: str) -> str:
    """Normaliza un identificador de muestra: recorta y reemplaza espacios internos por ``_``."""
    return _WHITESPACE.sub("_", raw.strip())


def normalize_taxon(raw: str, default_level: str = "unknown") -> tuple[str, str]:
    """Normaliza un identificador de taxón y devuelve ``(taxon_id, taxon_level)``.

    Un linaje con prefijos de rango (``sk__Bacteria;p__Bacillota;g__Lactobacillus`` o el
    formato ``k__…|p__…`` de MetaPhlAn) se reduce a su rango más profundo con nombre. Un
    linaje sin prefijos (``Bacteria;Bacillota``) se reduce a su último elemento, con
    ``default_level``. Devuelve ``("", default_level)`` si no queda ningún nombre.
    """
    text = raw.strip()
    parts = [part.strip() for part in _LINEAGE_SEPARATOR.split(text) if part.strip()]
    if not parts:
        return "", default_level

    name, level = "", default_level
    ranked = False
    for part in parts:
        match = _RANK_PATTERN.fullmatch(part)
        if match is None or match.group(1) not in _RANK_PREFIXES:
            continue
        ranked = True
        rank_name = match.group(2).strip()
        if rank_name:
            name, level = rank_name, _RANK_PREFIXES[match.group(1)]
    if not ranked:
        name = parts[-1]
    return _WHITESPACE.sub("_", name), level


class AbundanceLoader(BaseLoader):
    """Carga tablas de abundancia microbiana (TSV/CSV o sintéticas) a un IngestionPayload.

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
        Por defecto ``"taxon_id"``; si no existe se usa la primera columna.
    orientation : str
        ``"taxa_rows"`` (default): filas = taxa, columnas = muestras.
        ``"taxa_cols"``: columnas = taxa, filas = muestras.
    taxon_level : str
        Nivel taxonómico de los identificadores sin prefijo de rango (por defecto
        ``"unknown"``). Debe pertenecer a `TAXON_LEVELS`.
    normalize : bool
        Si es verdadera (default), normaliza cada muestra a abundancia relativa.
        Acepta booleanos JSON o textos como ``"true"``/``"false"``/``"1"``/``"0"``.
    unit : str
        Unidad de los valores cuando ``normalize`` es falsa (default ``"relative_abundance"``).
    generate_if_missing : bool
        Solo para ``format="jsonl"``: si la ruta del dataset sintético no existe, lo genera
        en memoria con `generate_scenario_dataset` en lugar de fallar.
    """

    def load(self, source_path: Path | str | None = None) -> IngestionPayload:
        """Lee la fuente de abundancia y devuelve un IngestionPayload normalizado."""
        opts = self.metadata.options
        should_normalize = parse_bool_option(opts.get("normalize", True), "normalize")
        default_level = str(opts.get("taxon_level", "unknown"))
        if default_level not in TAXON_LEVELS:
            raise ValueError(
                f"taxon_level '{default_level}' no reconocido. Permitidos: {sorted(TAXON_LEVELS)}"
            )

        if self.metadata.format == "jsonl":
            return self._load_synthetic(source_path, should_normalize)

        path = self.resolve_path(source_path)
        orientation = str(opts.get("orientation", "taxa_rows"))
        if orientation not in {"taxa_rows", "taxa_cols"}:
            raise ValueError(
                f"orientation '{orientation}' no reconocida. Usar 'taxa_rows' o 'taxa_cols'."
            )
        taxon_col = str(opts.get("taxon_column", "taxon_id"))
        errors: list[str] = []
        extra: dict[str, Any] = {
            "source_path": str(path),
            "normalized": should_normalize,
            "orientation": orientation,
            "taxon_column": taxon_col,
            "errors": errors,
        }

        table = self._read_table(path, errors)
        if not table or len(table) < 2:
            return IngestionPayload(
                metadata=self.metadata, raw_data=[], records_count=0, extra=extra
            )

        header, body = table[0], table[1:]
        if orientation == "taxa_rows":
            matrix, levels = self._parse_taxa_rows(header, body, taxon_col, default_level, errors)
        else:
            matrix, levels = self._parse_taxa_cols(header, body, default_level, errors)

        records = self._matrix_to_records(matrix, levels, should_normalize)
        return IngestionPayload(
            metadata=self.metadata, raw_data=records, records_count=len(records), extra=extra
        )

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------

    def _record_error(self, errors: list[str], message: str) -> None:
        """Registra un error de lectura en el log y en la lista del payload."""
        text = f"[{self.metadata.source_id}] {message}"
        logger.warning(text)
        errors.append(text)

    def _read_table(self, path: Path, errors: list[str]) -> list[list[str]]:
        """Lee el archivo delimitado sin comentarios ni filas vacías.

        Un archivo ilegible (permisos, codificación, CSV malformado) se registra como error y
        devuelve una tabla vacía para que el pipeline continúe con las demás fuentes.
        """
        opts = self.metadata.options
        encoding = str(opts.get("encoding", "utf-8"))
        comment_char = str(opts.get("comment_char", "#"))
        delimiter = _detect_delimiter(path, opts)
        try:
            with open(path, encoding=encoding, newline="") as fh:
                lines = (ln for ln in fh if not (comment_char and ln.startswith(comment_char)))
                rows = [
                    [cell.strip() for cell in row] for row in csv.reader(lines, delimiter=delimiter)
                ]
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            text = f"[{self.metadata.source_id}] No se pudo leer {path}: {exc}"
            logger.error(text)
            errors.append(text)
            return []
        return [row for row in rows if any(row)]

    def _parse_value(self, raw: str, where: str, errors: list[str]) -> float | None:
        """Convierte una celda a abundancia; ``None`` si la celda es inválida."""
        if raw == "":
            return 0.0
        try:
            value = float(raw)
        except ValueError:
            self._record_error(errors, f"{where}: valor no numérico '{raw}'; se omite.")
            return None
        if not math.isfinite(value):
            self._record_error(errors, f"{where}: valor no finito '{raw}'; se omite.")
            return None
        if value < 0.0:
            # La abundancia microbiana nunca puede ser negativa; se clampa a 0.
            self._record_error(errors, f"{where}: valor negativo {value}; se usa 0.0.")
            return 0.0
        return value

    def _add_value(
        self,
        matrix: dict[_SampleKey, dict[str, float]],
        key: _SampleKey,
        taxon_id: str,
        value: float,
        errors: list[str],
    ) -> None:
        """Suma el valor al taxón de la muestra; un taxón repetido se agrega con aviso."""
        cell = matrix.setdefault(key, {})
        if taxon_id in cell:
            self._record_error(
                errors,
                f"muestra '{key[1]}': el taxón '{taxon_id}' aparece más de una vez; "
                "se suman sus valores.",
            )
            cell[taxon_id] += value
        else:
            cell[taxon_id] = value

    def _sample_columns(
        self, header: list[str], skip: int, errors: list[str]
    ) -> list[tuple[int, str]]:
        """Devuelve ``(índice, sample_id)`` de las columnas de muestra, sin duplicados."""
        columns: list[tuple[int, str]] = []
        seen: set[str] = set()
        for index, raw in enumerate(header):
            if index == skip:
                continue
            sample_id = normalize_sample_id(raw)
            if not sample_id:
                self._record_error(errors, f"columna {index + 1}: encabezado vacío; se omite.")
                continue
            if sample_id in seen:
                self._record_error(
                    errors, f"columna {index + 1}: muestra '{sample_id}' duplicada; se omite."
                )
                continue
            seen.add(sample_id)
            columns.append((index, sample_id))
        return columns

    # ------------------------------------------------------------------
    # Métodos de parsing internos
    # ------------------------------------------------------------------

    def _parse_taxa_rows(
        self,
        header: list[str],
        body: list[list[str]],
        taxon_col: str,
        default_level: str,
        errors: list[str],
    ) -> tuple[dict[_SampleKey, dict[str, float]], dict[str, str]]:
        """Procesa tabla donde filas=taxa, columnas=muestras."""
        taxon_index = header.index(taxon_col) if taxon_col in header else 0
        samples = self._sample_columns(header, taxon_index, errors)
        matrix: dict[_SampleKey, dict[str, float]] = {(None, s): {} for _, s in samples}
        levels: dict[str, str] = {}

        for line_no, row in enumerate(body, start=2):
            if len(row) != len(header):
                self._record_error(
                    errors,
                    f"fila {line_no}: {len(row)} columnas, se esperaban {len(header)}; se omite.",
                )
                continue
            taxon_id, level = normalize_taxon(row[taxon_index], default_level)
            if not taxon_id:
                self._record_error(errors, f"fila {line_no}: identificador de taxón vacío.")
                continue
            levels[taxon_id] = level
            for index, sample_id in samples:
                value = self._parse_value(
                    row[index], f"fila {line_no}, muestra '{sample_id}'", errors
                )
                if value is not None:
                    self._add_value(matrix, (None, sample_id), taxon_id, value, errors)

        return matrix, levels

    def _parse_taxa_cols(
        self,
        header: list[str],
        body: list[list[str]],
        default_level: str,
        errors: list[str],
    ) -> tuple[dict[_SampleKey, dict[str, float]], dict[str, str]]:
        """Procesa tabla donde filas=muestras, columnas=taxa."""
        taxa: list[tuple[int, str]] = []
        levels: dict[str, str] = {}
        for index, raw in enumerate(header[1:], start=1):
            taxon_id, level = normalize_taxon(raw, default_level)
            if not taxon_id:
                self._record_error(errors, f"columna {index + 1}: taxón vacío; se omite.")
                continue
            taxa.append((index, taxon_id))
            levels[taxon_id] = level

        matrix: dict[_SampleKey, dict[str, float]] = {}
        for line_no, row in enumerate(body, start=2):
            if len(row) != len(header):
                self._record_error(
                    errors,
                    f"fila {line_no}: {len(row)} columnas, se esperaban {len(header)}; se omite.",
                )
                continue
            sample_id = normalize_sample_id(row[0])
            if not sample_id:
                self._record_error(errors, f"fila {line_no}: identificador de muestra vacío.")
                continue
            if (None, sample_id) in matrix:
                self._record_error(
                    errors, f"fila {line_no}: muestra '{sample_id}' duplicada; se omite."
                )
                continue
            matrix[(None, sample_id)] = {}
            for index, taxon_id in taxa:
                value = self._parse_value(row[index], f"fila {line_no}, taxón '{taxon_id}'", errors)
                if value is not None:
                    self._add_value(matrix, (None, sample_id), taxon_id, value, errors)

        return matrix, levels

    def _load_synthetic(
        self, source_path: Path | str | None, should_normalize: bool
    ) -> IngestionPayload:
        """Lee las abundancias de los nodos ``taxon`` del dataset sintético (act. 26)."""
        target = source_path if source_path is not None else self.metadata.path_or_url
        generate = parse_bool_option(
            self.metadata.options.get("generate_if_missing", False), "generate_if_missing"
        )
        errors: list[str] = []
        dataset: SyntheticDataset
        if generate and (target is None or not Path(target).exists()):
            logger.info(
                "[%s] %s no existe; se genera el dataset sintético en memoria.",
                self.metadata.source_id,
                target,
            )
            dataset = generate_scenario_dataset()
            origin = "generated"
        else:
            path = self.resolve_path(source_path)
            origin = str(path)
            try:
                dataset = load_dataset(path)
            except (OSError, DatasetFormatError, DatasetValidationError) as exc:
                text = f"[{self.metadata.source_id}] No se pudo leer {path}: {exc}"
                logger.error(text)
                errors.append(text)
                return IngestionPayload(
                    metadata=self.metadata,
                    raw_data=[],
                    records_count=0,
                    extra={"source_path": origin, "normalized": should_normalize, "errors": errors},
                )

        sample_ids = {inst.graph_id: inst.sample_id for inst in dataset.instances}
        matrix: dict[_SampleKey, dict[str, float]] = {}
        levels: dict[str, str] = {}
        for node in dataset.nodes:
            if node.node_type != "taxon":
                continue
            attrs = node.attributes
            taxon_id, level = normalize_taxon(
                str(attrs.get("taxonomy_id", node.node_id)),
                str(attrs.get("taxonomy_level", "unknown")),
            )
            if level not in TAXON_LEVELS:
                self._record_error(
                    errors, f"nodo '{node.node_id}': nivel '{level}' desconocido; usa 'unknown'."
                )
                level = "unknown"
            value = self._parse_value(
                str(attrs.get("abundance", "")), f"nodo '{node.node_id}'", errors
            )
            if value is None:
                continue
            levels[taxon_id] = level
            key = (node.graph_id, normalize_sample_id(sample_ids[node.graph_id]))
            self._add_value(matrix, key, taxon_id, value, errors)

        records = self._matrix_to_records(matrix, levels, should_normalize)
        return IngestionPayload(
            metadata=self.metadata,
            raw_data=records,
            records_count=len(records),
            extra={"source_path": origin, "normalized": should_normalize, "errors": errors},
        )

    def _matrix_to_records(
        self,
        matrix: dict[_SampleKey, dict[str, float]],
        levels: dict[str, str],
        normalize: bool,
    ) -> list[dict[str, Any]]:
        """Convierte la matriz {(graph_id, sample) -> {taxon -> value}} a lista de registros."""
        records: list[dict[str, Any]] = []
        for (graph_id, sample_id), taxon_values in matrix.items():
            if not taxon_values:
                continue
            taxa = list(taxon_values.keys())
            values = [taxon_values[t] for t in taxa]

            if normalize:
                values = _normalize_column(values)
                unit = "relative_abundance"
            else:
                unit = str(self.metadata.options.get("unit", "relative_abundance"))

            for taxon_id, value in zip(taxa, values, strict=True):
                records.append(
                    {
                        "graph_id": graph_id,
                        "sample_id": sample_id,
                        "taxon_id": taxon_id,
                        "taxon_level": levels[taxon_id],
                        "value": value,
                        "unit": unit,
                        "source_id": self.metadata.source_id,
                        "species": self.metadata.species,
                        "gut_segment": self.metadata.gut_segment,
                    }
                )
        return records
