"""Módulo de taxonomía y agregación a género con la tabla de equivalencias S-04 (A50 / F4).

Implementa la sección 6 del contrato de datos v2 (``docs/graph/data-contract-v2.md``, #136, #150):
- Rango de trabajo: género.
- Tabla de equivalencias SILVA 132 → GTDB r207 (S-04).
- `taxon_id` lleva prefijo de rango (p. ej. `g__Lactobacillus`, `p__Actinobacteria`).
- Lecturas sin género se agregan en nodos residuales por el rango más profundo alcanzado
  (p. ej. `f__Lachnospiraceae;g__`, `o__X;f__`, `p__Actinobacteria;c__`), preservando la suma = 1.
- Los nodos residuales no reciben aristas funcionales (has_capacity).
"""

from __future__ import annotations

import csv
import logging
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

logger = logging.getLogger(__name__)

# Niveles taxonómicos canónicos en orden jerárquico ascendente
RANK_ORDER: Final[tuple[str, ...]] = (
    "species",
    "genus",
    "family",
    "order",
    "class",
    "phylum",
    "kingdom",
    "domain",
)

# Prefijos de rango
PREFIX_TO_RANK: Final[dict[str, str]] = {
    "s": "species",
    "g": "genus",
    "f": "family",
    "o": "order",
    "c": "class",
    "p": "phylum",
    "k": "kingdom",
    "d": "domain",
    "sk": "domain",
    "t": "strain",
}

RANK_TO_PREFIX: Final[dict[str, str]] = {
    "species": "s",
    "genus": "g",
    "family": "f",
    "order": "o",
    "class": "c",
    "phylum": "p",
    "kingdom": "k",
    "domain": "d",
    "strain": "t",
}

# Sub-rango siguiente para indicar residual (p. ej. familia sin género -> ';g__')
RESIDUAL_SUFFIX_MAP: Final[dict[str, str]] = {
    "family": ";g__",
    "order": ";f__",
    "class": ";o__",
    "phylum": ";c__",
    "kingdom": ";p__",
    "domain": ";p__",
}

_RANK_PATTERN = re.compile(r"([a-z]{1,2})__(.*)")
_LINEAGE_SPLIT = re.compile(r"[;|]")
_WHITESPACE = re.compile(r"\s+")
_NORM_TOLERANCE = 1e-6


@dataclass(frozen=True)
class SilvaGtdbEntry:
    """Entrada en la tabla de equivalencias SILVA 132 → GTDB r207 (S-04)."""

    silva_taxon_id: str
    gtdb_taxon_id: str | None
    relationship: str  # "1:1", "1:N", "sin par"
    notes: str = ""

    def is_one_to_one(self) -> bool:
        """Indica si el mapeo es unívoco 1:1."""
        return self.relationship == "1:1" and bool(self.gtdb_taxon_id)


class SilvaGtdbMapping:
    """Tabla de equivalencias taxonómicas SILVA 132 → GTDB r207 (S-04)."""

    def __init__(
        self,
        entries: Sequence[SilvaGtdbEntry] | None = None,
        source: str = "S-04",
        version: str = "1.0.0",
    ) -> None:
        self.source = source
        self.version = version
        self._entries_by_silva: dict[str, SilvaGtdbEntry] = {}
        if entries:
            for entry in entries:
                self._entries_by_silva[entry.silva_taxon_id] = entry

    @classmethod
    def load_tsv(cls, path: Path | str, version: str = "1.0.0") -> SilvaGtdbMapping:
        """Carga la tabla de equivalencias desde un archivo TSV.

        Columnas esperadas: silva_taxon_id, gtdb_taxon_id, relationship, notes (opcional).
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Archivo de equivalencias S-04 no encontrado: {path}")

        entries: list[SilvaGtdbEntry] = []
        with open(p, encoding="utf-8", newline="") as fh:
            reader = csv.reader(fh, delimiter="\t")
            for row in reader:
                if not row or row[0].startswith("#") or not row[0].strip():
                    continue
                # Descartar posible encabezado
                if row[0].lower() in {"silva_taxon_id", "silva_id", "silva"}:
                    continue
                silva_id = row[0].strip()
                gtdb_id = row[1].strip() if len(row) > 1 and row[1].strip() else None
                rel = row[2].strip() if len(row) > 2 and row[2].strip() else "sin par"
                notes = row[3].strip() if len(row) > 3 else ""
                entries.append(
                    SilvaGtdbEntry(
                        silva_taxon_id=silva_id,
                        gtdb_taxon_id=gtdb_id,
                        relationship=rel,
                        notes=notes,
                    )
                )
        return cls(entries=entries, source="S-04", version=version)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SilvaGtdbMapping:
        """Crea el mapeo a partir de un diccionario de metadatos."""
        source = str(data.get("source", "S-04"))
        version = str(data.get("version", "1.0.0"))
        entries: list[SilvaGtdbEntry] = []

        # Si viene en formato simple 'one_to_one': [list of ids]
        if "one_to_one" in data and isinstance(data["one_to_one"], (list, tuple)):
            for tid in data["one_to_one"]:
                entries.append(
                    SilvaGtdbEntry(
                        silva_taxon_id=str(tid),
                        gtdb_taxon_id=str(tid),
                        relationship="1:1",
                    )
                )

        # Si viene en formato completo 'mappings': [{'silva': ..., 'gtdb': ..., 'rel': ...}]
        if "mappings" in data and isinstance(data["mappings"], (list, tuple)):
            for item in data["mappings"]:
                if isinstance(item, Mapping):
                    entries.append(
                        SilvaGtdbEntry(
                            silva_taxon_id=str(item.get("silva_taxon_id", item.get("silva", ""))),
                            gtdb_taxon_id=str(item["gtdb_taxon_id"])
                            if item.get("gtdb_taxon_id")
                            else None,
                            relationship=str(item.get("relationship", item.get("rel", "sin par"))),
                            notes=str(item.get("notes", "")),
                        )
                    )
        return cls(entries=entries, source=source, version=version)

    def get_entry(self, silva_taxon_id: str) -> SilvaGtdbEntry | None:
        """Obtiene la entrada para un taxon SILVA."""
        clean_id = silva_taxon_id.strip()
        if clean_id in self._entries_by_silva:
            return self._entries_by_silva[clean_id]
        # Probar sin o con prefijo 'g__'
        if clean_id.startswith("g__"):
            bare = clean_id[3:]
            if bare in self._entries_by_silva:
                return self._entries_by_silva[bare]
        else:
            with_pfx = f"g__{clean_id}"
            if with_pfx in self._entries_by_silva:
                return self._entries_by_silva[with_pfx]
        return None

    def map_silva_to_gtdb(self, silva_taxon_id: str) -> str | None:
        """Mapea silva_taxon_id a GTDB si es 1:1; devuelve None en otro caso."""
        entry = self.get_entry(silva_taxon_id)
        if entry and entry.is_one_to_one():
            return entry.gtdb_taxon_id
        return None

    def one_to_one_taxa(self) -> frozenset[str]:
        """Conjunto de taxones con relación 1:1 garantizada."""
        return frozenset(
            entry.silva_taxon_id
            for entry in self._entries_by_silva.values()
            if entry.is_one_to_one()
        )

    def to_metadata_dict(self) -> dict[str, Any]:
        """Genera el diccionario para metadata.json compatible con EDG-04 y GraphBuilder."""
        return {
            "source": self.source,
            "version": self.version,
            "one_to_one": sorted(self.one_to_one_taxa()),
        }


def parse_lineage_ranks(lineage_or_id: str) -> dict[str, str]:
    """Extrae todos los rangos presentes en un linaje o identificador taxonómico.

    Devuelve un diccionario {nivel: nombre_con_prefijo}, por ejemplo:
    {"phylum": "p__Actinobacteria", "genus": "g__Bifidobacterium"}.
    """
    text = lineage_or_id.strip()
    parts = [part.strip() for part in _LINEAGE_SPLIT.split(text) if part.strip()]
    ranks: dict[str, str] = {}
    for part in parts:
        m = _RANK_PATTERN.fullmatch(part)
        if m is not None and m.group(1) in PREFIX_TO_RANK:
            pfx = m.group(1)
            name = m.group(2).strip()
            if name:
                rank = PREFIX_TO_RANK[pfx]
                clean = _WHITESPACE.sub("_", name)
                ranks[rank] = f"{pfx}__{clean}"
    return ranks


def resolve_genus_and_residual(
    taxon_id: str,
    taxon_level: str | None = None,
    lineage: str | None = None,
) -> tuple[str, str, bool]:
    """Determina el género o el nodo residual generalizado según contrato v2 §6.

    Devuelve una tupla ``(target_taxon_id, target_taxon_level, is_residual)``:
    - Si la entidad tiene género o es a nivel de género: se asigna al género
      (``g__<Nombre>``, nivel ``genus``, ``is_residual=False``).
    - Si es más profunda que género (especie, cepa): se agrega a su género
      (``g__<Nombre>``, nivel ``genus``, ``is_residual=False``).
    - Si no alcanza género (familia, orden, clase, filo, dominio/reino): se agrega en un
      **nodo residual del rango más profundo que alcance**, por ejemplo:
      ``f__Lachnospiraceae;g__``, ``o__X;f__``, ``c__Actinobacteria;o__``,
      ``p__Actinobacteria;c__`` (``target_taxon_level=rango_alcanzado``, ``is_residual=True``).
    """
    clean_id = taxon_id.strip()
    source_text = lineage.strip() if lineage and lineage.strip() else clean_id
    ranks = parse_lineage_ranks(source_text)

    # 1. ¿Hay género explícito en los rangos?
    if "genus" in ranks:
        return ranks["genus"], "genus", False

    # 2. Si no hay linaje completo pero taxon_id empieza por g__ o nivel es genus
    if clean_id.startswith("g__"):
        return clean_id, "genus", False
    if taxon_level == "genus":
        name = clean_id if clean_id.startswith("g__") else f"g__{clean_id}"
        return name, "genus", False

    # 3. Si es especie (s__) o cepa (t__)
    is_spec = (
        "species" in ranks
        or clean_id.startswith(("s__", "t__"))
        or taxon_level in {"species", "strain"}
    )
    if is_spec:
        spec_id = ranks.get("species", clean_id)
        # Extraer nombre binominal si es posible (s__L_johnsonii -> g__L)
        bare = spec_id[3:] if spec_id.startswith(("s__", "t__")) else spec_id
        genus_part = bare.split("_")[0]
        if genus_part:
            return f"g__{genus_part}", "genus", False

    # 4. Lecturas que NO alcanzan género: nodo residual del rango más profundo alcanzado
    # Revisamos rangos en orden de mayor a menor profundidad
    for rank in ("family", "order", "class", "phylum", "kingdom", "domain"):
        if rank in ranks:
            rank_id = ranks[rank]
            suffix = RESIDUAL_SUFFIX_MAP.get(rank, ";residual")
            residual_id = f"{rank_id}{suffix}"
            return residual_id, rank, True

    # Si taxon_id tiene prefijo conocido pero no vino en ranks
    m = _RANK_PATTERN.fullmatch(clean_id)
    if m is not None and m.group(1) in PREFIX_TO_RANK:
        rank = PREFIX_TO_RANK[m.group(1)]
        suffix = RESIDUAL_SUFFIX_MAP.get(rank, ";residual")
        return f"{clean_id}{suffix}", rank, True

    # Si se conoce taxon_level
    if taxon_level and taxon_level in RESIDUAL_SUFFIX_MAP:
        pfx = RANK_TO_PREFIX.get(taxon_level, "")
        pfx_str = f"{pfx}__" if pfx and not clean_id.startswith(f"{pfx}__") else ""
        suffix = RESIDUAL_SUFFIX_MAP[taxon_level]
        return f"{pfx_str}{clean_id}{suffix}", taxon_level, True

    # Caso desconocido / OTU sin linaje
    return f"{clean_id};residual", taxon_level or "unknown", True


def aggregate_to_genus(
    records: Sequence[Mapping[str, Any]],
    mapping_table: SilvaGtdbMapping | None = None,
    normalize: bool = True,
) -> list[dict[str, Any]]:
    """Agrega registros de abundancia microbiana a nivel de género y nodos residuales.

    Aplica las reglas del Contrato v2 §6:
    1. Agregación a género de lecturas a nivel de género o especie.
    2. Puente de nombres con la tabla de equivalencias SILVA 132 → GTDB r207 (S-04) si se provee.
    3. Toda lectura sin género va a un nodo residual del rango más profundo que alcance
       (p. ej. ``f__Lachnospiraceae;g__``, ``c__Actinobacteria;o__``, ``p__Actinobacteria;c__``).
    4. Las abundancias relativas por muestra siguen sumando exactamente 1.0.
    5. Las colisiones de nombres (p. ej. filo vs clase Actinobacteria / Deferribacteres)
       quedan como nodos residuales distintos.
    6. Los nodos residuales quedan marcados con ``is_residual=True`` (sin aristas funcionales).
    """
    if not records:
        return []

    # Agrupar por muestra: (graph_id, sample_id)
    # y acumular {target_id: (valor, nivel, is_residual, metadata_base)}
    samples: dict[tuple[str | None, str], dict[str, float]] = {}
    levels: dict[str, str] = {}
    residuals: dict[str, bool] = {}
    sample_contexts: dict[tuple[str | None, str], dict[str, Any]] = {}

    for rec in records:
        graph_id = rec.get("graph_id")
        sample_id = str(rec["sample_id"])
        taxon_id = str(rec["taxon_id"])
        taxon_level = str(rec.get("taxon_level", "unknown"))
        lineage = rec.get("lineage") or rec.get("raw_lineage")
        value = float(rec["value"])

        key = (graph_id, sample_id)
        if key not in sample_contexts:
            sample_contexts[key] = {
                "source_id": rec.get("source_id", "unknown"),
                "species": rec.get("species", "chicken"),
                "gut_segment": rec.get("gut_segment", "cecum"),
                "unit": rec.get("unit", "relative_abundance"),
            }

        target_id, target_level, is_residual = resolve_genus_and_residual(
            taxon_id, taxon_level=taxon_level, lineage=lineage
        )

        # Si no es residual y se provee la tabla S-04, traducir SILVA -> GTDB
        if not is_residual and mapping_table is not None:
            gtdb_id = mapping_table.map_silva_to_gtdb(target_id)
            if gtdb_id:
                target_id = gtdb_id if gtdb_id.startswith("g__") else f"g__{gtdb_id}"

        levels[target_id] = target_level
        residuals[target_id] = is_residual

        cell = samples.setdefault(key, {})
        cell[target_id] = cell.get(target_id, 0.0) + value

    output_records: list[dict[str, Any]] = []

    for (graph_id, sample_id), taxa_vals in samples.items():
        ctx = sample_contexts[(graph_id, sample_id)]
        taxa = list(taxa_vals.keys())
        values = [taxa_vals[t] for t in taxa]

        # Normalizar a 1.0 si normalize es True
        if normalize:
            total = math.fsum(values)
            if total > 0.0 and abs(total - 1.0) > _NORM_TOLERANCE:
                values = [v / total for v in values]
            elif total > 0.0:
                values = [float(v) for v in values]
            else:
                values = [0.0] * len(values)

        for tid, val in zip(taxa, values, strict=True):
            output_records.append(
                {
                    "graph_id": graph_id,
                    "sample_id": sample_id,
                    "taxon_id": tid,
                    "taxon_level": levels[tid],
                    "value": val,
                    "unit": "relative_abundance",
                    "source_id": ctx["source_id"],
                    "species": ctx["species"],
                    "gut_segment": ctx["gut_segment"],
                    "is_residual": residuals[tid],
                }
            )

    return output_records
