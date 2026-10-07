"""Transformaciones de la fuente D1 (HoloFood, pollo) al formato de los loaders.

HoloFood distribuye sus datos entre el portal (metadatos por animal y AGCC por muestra),
MGnify (abundancias taxonómicas por estudio) y ENA (correspondencia corrida → BioSample).
Estas funciones reciben las respuestas ya descargadas y producen cuatro tablas, todas con
la accesión BioSample del **animal** como `sample_id`, que es la clave común entre ómicas:

- abundancias SSU del contenido cecal (`AbundanceLoader`, taxa en filas, conteos crudos);
- AGCC del ciego, una tabla por matriz (`MetaboliteLoader`, metabolitos en columnas);
- metadatos de dieta y fenotipo individuales (`MetadataLoader`);
- correspondencia entre accesiones, para auditar cada fila hasta su origen.

No se fusionan matrices distintas: el portal rotula parte de las muestras de AGCC del ciego
como `caecum content` y parte como `caecum tissue`, y cada matriz va a su propia tabla.
Tampoco se mezclan los marcadores de corral (`PEN`) con los individuales: solo se exportan
los individuales. Ver `docs/holofood-source.md`.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

SCFA_MARKER_TYPE: Final = "FATTY ACIDS"
SCFA_UNIT: Final = "umol/g digesta"

SCFA_MARKERS: Final[tuple[str, ...]] = (
    "Acetic acid",
    "Propionic acid",
    "n-Butyric acid",
    "i-Butyric acid",
    "n-Valeric acid",
    "i-Valeric acid",
    "D-Lactate",
    "L-Lactate",
)
"""Concentraciones individuales exportadas. Se omiten los totales y las razones, que se
derivan de estas columnas y no tienen la misma unidad."""

CAECUM_MATRICES: Final[Mapping[str, str]] = {
    "caecum content": "content",
    "caecum tissue": "tissue",
}
"""`Body site` del portal → sufijo de la tabla de AGCC."""

METAGENOME_BODY_SITE_SUFFIX: Final = "F1a"
"""Sufijo del título de las muestras de metagenoma de contenido cecal en HoloFood."""

METADATA_COLUMNS: Final[tuple[str, ...]] = (
    "sample_id",
    "animal_code",
    "trial_code",
    "pen_code",
    "diet_treatment_code",
    "diet_treatment_name",
    "sex",
    "breed",
    "sampling_day",
    "body_weight_g",
)

_ANIMAL_MARKERS: Final[Mapping[str, str]] = {
    "Animal code": "animal_code",
    "Trial code": "trial_code",
    "Pen code": "pen_code",
    "Treatment code": "diet_treatment_code",
    "Treatment name": "diet_treatment_name",
    "Sex": "sex",
    "Breed": "breed",
    "Sampling time": "sampling_day",
    "Chicken body weight": "body_weight_g",
}

_INDIVIDUAL_MARKER_TYPES: Final = frozenset({"SAMPLE", "TREATMENT", "TRIAL"})
"""Tipos de marcador del animal que describen al individuo o su tratamiento. Los de tipo
`PEN` son promedios del corral y no se exportan como fenotipo individual."""


@dataclass(frozen=True)
class RunLink:
    """Corrida de ENA cuyo perfil SSU aparece como columna en una tabla de MGnify."""

    run_accession: str
    sample_accession: str
    animal_accession: str
    sample_title: str
    mgnify_study: str


def markers(detail: Mapping[str, Any]) -> list[tuple[str, str, str, str | None]]:
    """Devuelve `(tipo, nombre, medición, unidad)` de cada marcador de una ficha del portal.

    Los nombres del portal traen a veces espacios finales (`"Feather cortisol "`); se
    recortan para que la búsqueda por nombre sea estable.
    """
    out: list[tuple[str, str, str, str | None]] = []
    for item in detail.get("structured_metadata") or []:
        marker = item.get("marker") or {}
        name = str(marker.get("name", "")).strip()
        if not name:
            continue
        units = item.get("units")
        out.append(
            (
                str(marker.get("type", "")),
                name,
                str(item.get("measurement", "")).strip(),
                str(units).strip() if units is not None else None,
            )
        )
    return out


def body_site(detail: Mapping[str, Any]) -> str | None:
    """`Body site` declarado por la muestra, en minúsculas, o `None` si falta."""
    for marker_type, name, value, _ in markers(detail):
        if marker_type == "SAMPLE" and name == "Body site":
            return value.lower()
    return None


def scfa_row(detail: Mapping[str, Any]) -> dict[str, str]:
    """Concentraciones de AGCC de una muestra `metabolomic_targeted`.

    Solo toma los marcadores de `SCFA_MARKERS` con tipo `FATTY ACIDS` y unidad
    `umol/g digesta`; una unidad distinta se rechaza en lugar de convertirse en silencio.
    Los marcadores ausentes quedan vacíos, que el loader interpreta como dato faltante.
    """
    found: dict[str, str] = {}
    for marker_type, name, value, unit in markers(detail):
        if marker_type != SCFA_MARKER_TYPE or name not in SCFA_MARKERS:
            continue
        if unit != SCFA_UNIT:
            raise ValueError(
                f"{detail.get('accession')}: '{name}' en '{unit}', se esperaba '{SCFA_UNIT}'."
            )
        found[name] = value
    return {name: found.get(name, "") for name in SCFA_MARKERS}


def _sampling_day(value: str) -> str:
    """`"Day 21"` → `"21"`; deja el valor original si no tiene ese formato."""
    text = value.strip()
    if text.lower().startswith("day "):
        day = text[4:].strip()
        if day.isdigit():
            return str(int(day))
    return text


def animal_metadata_row(detail: Mapping[str, Any]) -> dict[str, str]:
    """Fila de metadatos individuales de un animal del portal.

    Toma un marcador individual (`SAMPLE`, `TREATMENT`, `TRIAL`) o el código de corral,
    que identifica al grupo experimental sin ser un fenotipo.
    """
    row = dict.fromkeys(METADATA_COLUMNS, "")
    row["sample_id"] = str(detail["accession"])
    for marker_type, name, value, unit in markers(detail):
        column = _ANIMAL_MARKERS.get(name)
        if column is None:
            continue
        if marker_type not in _INDIVIDUAL_MARKER_TYPES and name != "Pen code":
            continue
        if column == "body_weight_g" and unit not in (None, "g"):
            raise ValueError(f"{row['sample_id']}: peso en '{unit}', se esperaba 'g'.")
        row[column] = _sampling_day(value) if column == "sampling_day" else value
    if row["sex"]:
        row["sex"] = row["sex"].lower()
    return row


def parse_mgnify_taxonomy(text: str) -> tuple[list[str], dict[str, dict[str, float]]]:
    """Lee una tabla `*_taxonomy_abundances_*.tsv` de MGnify.

    Devuelve las columnas en su orden y, por columna, los conteos no nulos por linaje.
    """
    reader = csv.reader(io.StringIO(text), delimiter="\t")
    header = next(reader)
    if not header or header[0] != "#SampleID":
        raise ValueError("La tabla de MGnify debe comenzar con la columna '#SampleID'.")
    columns = header[1:]
    counts: dict[str, dict[str, float]] = {column: {} for column in columns}
    for line_no, row in enumerate(reader, start=2):
        if not row:
            continue
        if len(row) != len(header):
            raise ValueError(f"fila {line_no}: {len(row)} columnas, se esperaban {len(header)}.")
        lineage = row[0]
        for column, raw in zip(columns, row[1:], strict=True):
            value = float(raw)
            if value:
                counts[column][lineage] = counts[column].get(lineage, 0.0) + value
    return columns, counts


def caecal_run_links(
    run_rows: Iterable[Mapping[str, str]],
    samples: Mapping[str, Mapping[str, str]],
    run_to_study: Mapping[str, str],
) -> list[RunLink]:
    """Corridas de lectura (`ERR…`) de contenido cecal que se pueden atribuir a un animal.

    `run_rows` es el reporte de ENA (`run_accession`, `sample_accession`); `samples` es la
    exportación del portal indexada por accesión; `run_to_study` dice en qué tabla de MGnify
    aparece cada corrida. Los análisis de ensamblajes (`ERZ…`) no se incluyen: sus conteos
    no son comparables con los de lecturas.
    """
    links: list[RunLink] = []
    for row in run_rows:
        run = row["run_accession"]
        study = run_to_study.get(run)
        sample = samples.get(row["sample_accession"])
        if study is None or sample is None or not run.startswith("ERR"):
            continue
        if not sample["title"].endswith(METAGENOME_BODY_SITE_SUFFIX):
            continue
        links.append(
            RunLink(
                run_accession=run,
                sample_accession=row["sample_accession"],
                animal_accession=sample["animal"],
                sample_title=sample["title"],
                mgnify_study=study,
            )
        )
    return sorted(links, key=lambda link: link.run_accession)


def merge_by_animal(
    tables: Mapping[str, Mapping[str, Mapping[str, float]]], links: Sequence[RunLink]
) -> dict[str, dict[str, float]]:
    """Suma, por animal, los conteos de sus corridas de contenido cecal.

    `tables` es `{estudio: {corrida: {linaje: conteo}}}`. Varias corridas del mismo animal
    son resecuenciaciones de la misma muestra, por lo que sus conteos se suman.
    """
    merged: dict[str, dict[str, float]] = {}
    for link in links:
        profile = tables[link.mgnify_study][link.run_accession]
        target = merged.setdefault(link.animal_accession, {})
        for lineage, value in profile.items():
            target[lineage] = target.get(lineage, 0.0) + value
    return merged


def _number(value: float) -> str:
    return str(int(value)) if value.is_integer() else repr(value)


def abundance_table(merged: Mapping[str, Mapping[str, float]]) -> str:
    """TSV con linajes en filas y animales en columnas, ordenado para ser reproducible."""
    animals = sorted(merged)
    lineages = sorted({lineage for profile in merged.values() for lineage in profile})
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\n")
    writer.writerow(["taxon_lineage", *animals])
    for lineage in lineages:
        writer.writerow(
            [lineage, *(_number(merged[animal].get(lineage, 0.0)) for animal in animals)]
        )
    return buffer.getvalue()


def rows_table(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> str:
    """TSV con las columnas indicadas, en el orden recibido."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), delimiter="\t", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return buffer.getvalue()
