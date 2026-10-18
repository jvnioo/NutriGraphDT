"""Cohorte supervisada oficial de D1 HoloFood (#138).

La partición de `configs/splits/` reparte los 530 animales con metadatos, pero solo una parte
tiene a la vez metagenoma y los tres AGCC principales. Este módulo fija qué animales entran a
cualquier análisis supervisado de AGCC, según la respuesta de Investigación a la solicitud de
revisión v1.1 (D-03, S-05 y Tabla 6):

1. **Metagenoma y AGCC.** Animales con columna en la tabla de abundancias SSU y con los tres
   AGCC objetivo medidos en el contenido cecal.
2. **Exclusiones.** Animales con perfiles de AGCC repetidos, listados con su motivo en
   `configs/cohorts/<dataset>.json`, hasta que el portal lo aclare.
3. **Profundidad.** Animales con al menos `min_ssu_reads` lecturas SSU (1000 por defecto).

Los baselines (`scripts/compare_baselines.py`) y la GNN (`scripts/train_gnn.py`,
`scripts/tune_gnn.py`) usan `load_cohort`, así que ambos entrenan y evalúan con los mismos
animales.
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final

from nutrigraphdt.data.loaders import MetaboliteLoader
from nutrigraphdt.data.loaders.base import SourceMetadata
from nutrigraphdt.data.split import _find_repo_root

DEFAULT_DATASET_ID: Final[str] = "D1_holofood"
DEFAULT_ABUNDANCE_SOURCE: Final[str] = "D1_holofood"
DEFAULT_METABOLITE_SOURCE: Final[str] = "D1_holofood_scfa_content"
STEP_PAIRED: Final[str] = "metagenoma_y_agcc"
STEP_EXCLUDED: Final[str] = "exclusiones"
STEP_DEPTH: Final[str] = "profundidad"


class CohortConfigError(ValueError):
    """La configuración de la cohorte no es válida."""


@dataclass(frozen=True)
class CohortExclusion:
    """Un animal excluido de la cohorte, con su motivo y su referencia."""

    sample_id: str
    reason: str
    note: str = ""
    reference: str = ""


@dataclass(frozen=True)
class CohortConfig:
    """Criterios versionados de la cohorte supervisada de un dataset."""

    dataset_id: str
    version: str
    targets: tuple[str, ...]
    min_ssu_reads: int
    exclusions: tuple[CohortExclusion, ...] = ()
    sensitivity_min_ssu_reads: tuple[int, ...] = ()
    matrix: str = "caecum_content"
    description: str = ""
    reference: str = ""

    def __post_init__(self) -> None:
        if not self.dataset_id or not self.version:
            raise CohortConfigError("dataset_id y version son obligatorios.")
        if not self.targets or len(set(self.targets)) != len(self.targets):
            raise CohortConfigError("targets debe tener al menos un AGCC y sin repetidos.")
        for value in (self.min_ssu_reads, *self.sensitivity_min_ssu_reads):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise CohortConfigError(
                    f"Los umbrales de lecturas deben ser enteros >= 0; recibido: {value!r}."
                )
        excluded = [item.sample_id for item in self.exclusions]
        if any(not sample_id for sample_id in excluded):
            raise CohortConfigError("Cada exclusión necesita un sample_id.")
        if len(set(excluded)) != len(excluded):
            raise CohortConfigError("Hay sample_id repetidos en exclusions.")
        if any(not item.reason for item in self.exclusions):
            raise CohortConfigError("Cada exclusión necesita un motivo (reason).")

    @property
    def excluded_ids(self) -> frozenset[str]:
        return frozenset(item.sample_id for item in self.exclusions)

    def with_min_ssu_reads(self, min_ssu_reads: int) -> CohortConfig:
        """Copia con otro umbral de lecturas, por ejemplo para un análisis de sensibilidad."""
        return replace(self, min_ssu_reads=min_ssu_reads)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CohortConfig:
        try:
            exclusions = tuple(
                CohortExclusion(
                    sample_id=str(item["sample_id"]),
                    reason=str(item["reason"]),
                    note=str(item.get("note", "")),
                    reference=str(item.get("reference", "")),
                )
                for item in data.get("exclusions", ())
            )
            return cls(
                dataset_id=str(data["dataset_id"]),
                version=str(data["version"]),
                targets=tuple(str(name) for name in data["targets"]),
                min_ssu_reads=data["min_ssu_reads"],
                exclusions=exclusions,
                sensitivity_min_ssu_reads=tuple(data.get("sensitivity_min_ssu_reads", ())),
                matrix=str(data.get("matrix", "caecum_content")),
                description=str(data.get("description", "")),
                reference=str(data.get("reference", "")),
            )
        except (KeyError, TypeError) as error:
            raise CohortConfigError(f"Configuración de cohorte incompleta: {error}") from error

    @classmethod
    def load(cls, path: str | Path) -> CohortConfig:
        path = Path(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CohortConfigError(f"No se pudo leer {path}: {error}") from error
        return cls.from_dict(data)


@dataclass(frozen=True)
class CohortStep:
    """Un paso de selección: los animales que quedan y los que quitó."""

    name: str
    description: str
    remaining: tuple[str, ...]
    removed: tuple[str, ...] = ()

    @property
    def count(self) -> int:
        return len(self.remaining)


@dataclass(frozen=True)
class Cohort:
    """Resultado de `select_cohort`: los pasos aplicados y los animales que quedan."""

    config: CohortConfig
    steps: tuple[CohortStep, ...]
    read_depths: Mapping[str, float] = field(default_factory=dict, repr=False)

    @property
    def sample_ids(self) -> frozenset[str]:
        return frozenset(self.steps[-1].remaining)

    @property
    def min_ssu_reads(self) -> int:
        return self.config.min_ssu_reads

    def __contains__(self, sample_id: object) -> bool:
        return sample_id in self.sample_ids

    def __len__(self) -> int:
        return len(self.steps[-1].remaining)

    def summary(self) -> dict[str, Any]:
        """Resumen corto para `run.json`: versión, umbral, conteos por paso y animales quitados."""
        return {
            "dataset_id": self.config.dataset_id,
            "version": self.config.version,
            "min_ssu_reads": self.config.min_ssu_reads,
            "size": len(self),
            "steps": [
                {"name": step.name, "count": step.count, "removed": list(step.removed)}
                for step in self.steps
            ],
        }

    def to_dict(self) -> dict[str, Any]:
        """Resumen más la lista de animales de la cohorte."""
        return {**self.summary(), "sample_ids": sorted(self.sample_ids)}


def select_cohort(
    complete_targets: Iterable[str],
    read_depths: Mapping[str, float],
    config: CohortConfig,
) -> Cohort:
    """Aplica los tres pasos de la cohorte.

    Args:
        complete_targets: animales con los AGCC de `config.targets` medidos (valores finitos).
        read_depths: lecturas SSU por animal con metagenoma (`ssu_read_depths`).
        config: criterios de la cohorte.
    """
    paired = sorted(set(complete_targets) & set(read_depths))
    steps = [
        CohortStep(
            name=STEP_PAIRED,
            description="Metagenoma y los AGCC objetivo medidos en el contenido cecal",
            remaining=tuple(paired),
        )
    ]

    excluded = config.excluded_ids
    after_exclusions = tuple(s for s in paired if s not in excluded)
    steps.append(
        CohortStep(
            name=STEP_EXCLUDED,
            description="Sin los animales excluidos por configuración (perfiles repetidos)",
            remaining=after_exclusions,
            removed=tuple(s for s in paired if s in excluded),
        )
    )

    threshold = config.min_ssu_reads
    steps.append(
        CohortStep(
            name=STEP_DEPTH,
            description=f"Con al menos {threshold} lecturas SSU",
            remaining=tuple(s for s in after_exclusions if read_depths[s] >= threshold),
            removed=tuple(s for s in after_exclusions if read_depths[s] < threshold),
        )
    )
    return Cohort(config=config, steps=tuple(steps), read_depths=dict(read_depths))


def ssu_read_depths(
    path: str | Path, *, delimiter: str = "\t", taxon_column: str = "taxon_lineage"
) -> dict[str, float]:
    """Suma los conteos SSU de cada animal de una tabla con linajes en filas.

    Usa los conteos crudos del archivo; `AbundanceLoader` los normaliza a abundancia relativa y
    pierde la profundidad. Una ruta relativa se resuelve, como en los loaders, desde el
    directorio de trabajo.
    """
    path = Path(path)
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        try:
            header = next(reader)
        except StopIteration as error:
            raise ValueError(f"{path}: tabla de abundancias vacía.") from error
        if not header or header[0] != taxon_column:
            raise ValueError(f"{path}: se esperaba la columna {taxon_column!r} en primer lugar.")
        samples = header[1:]
        totals = dict.fromkeys(samples, 0.0)
        for line_number, row in enumerate(reader, start=2):
            for sample_id, raw in zip(samples, row[1:], strict=False):
                if not raw.strip():
                    continue
                try:
                    value = float(raw)
                except ValueError as error:
                    raise ValueError(
                        f"{path}:{line_number}: conteo no numérico para {sample_id}: {raw!r}."
                    ) from error
                if not math.isfinite(value) or value < 0:
                    raise ValueError(
                        f"{path}:{line_number}: conteo inválido para {sample_id}: {raw!r}."
                    )
                totals[sample_id] += value
    return totals


def complete_target_samples(
    records: Iterable[Mapping[str, Any]], targets: Sequence[str]
) -> set[str]:
    """Animales con todos los `targets` medidos, desde los registros de `MetaboliteLoader`."""
    measured: dict[str, set[str]] = defaultdict(set)
    for record in records:
        value = record.get("value")
        if isinstance(value, bool) or not isinstance(value, int | float):
            continue
        if math.isfinite(float(value)) and record.get("canonical_id") in targets:
            measured[str(record["sample_id"])].add(str(record["canonical_id"]))
    return {sample_id for sample_id, names in measured.items() if set(targets) <= names}


def get_cohort_config(
    dataset_id: str = DEFAULT_DATASET_ID, *, cohort_file: str | Path | None = None
) -> CohortConfig:
    """Lee `configs/cohorts/<dataset_id en minúsculas>.json` o el archivo indicado."""
    root = _find_repo_root()
    if cohort_file is None:
        path = root / "configs" / "cohorts" / f"{dataset_id.lower()}.json"
    else:
        path = Path(cohort_file)
        if not path.is_absolute():
            path = root / path
    config = CohortConfig.load(path)
    if config.dataset_id != dataset_id:
        raise CohortConfigError(
            f"{path}: dataset_id {config.dataset_id!r}; se esperaba {dataset_id!r}."
        )
    return config


def load_cohort(
    sources: Mapping[str, SourceMetadata],
    config: CohortConfig | None = None,
    *,
    abundance_source: str = DEFAULT_ABUNDANCE_SOURCE,
    metabolite_source: str = DEFAULT_METABOLITE_SOURCE,
    min_ssu_reads: int | None = None,
) -> Cohort:
    """Selecciona la cohorte leyendo las fuentes registradas en `configs/sources.json`.

    Args:
        sources: fuentes de `load_sources`.
        config: criterios; por defecto, `get_cohort_config()`.
        abundance_source: fuente con los conteos SSU (linajes en filas).
        metabolite_source: fuente con los AGCC del contenido cecal.
        min_ssu_reads: reemplaza el umbral de la configuración (análisis de sensibilidad).
    """
    config = config or get_cohort_config()
    if min_ssu_reads is not None:
        config = config.with_min_ssu_reads(min_ssu_reads)

    missing = [name for name in (abundance_source, metabolite_source) if name not in sources]
    if missing:
        raise ValueError(f"Faltan fuentes en el registro: {missing}.")
    abundance = sources[abundance_source]
    if abundance.path_or_url is None:
        raise ValueError(f"La fuente {abundance_source!r} no define path_or_url.")
    options = abundance.options or {}
    depths = ssu_read_depths(
        abundance.path_or_url,
        delimiter=str(options.get("delimiter", "\t")),
        taxon_column=str(options.get("taxon_column", "taxon_lineage")),
    )
    payload = MetaboliteLoader(sources[metabolite_source]).load()
    complete = complete_target_samples(payload.raw_data, config.targets)
    return select_cohort(complete, depths, config)


def describe_cohort(
    cohort: Cohort, metadata: Mapping[str, Mapping[str, str]]
) -> list[dict[str, Any]]:
    """Por paso: animales por tratamiento y corrales por tratamiento.

    `metadata` va de `sample_id` a su fila de `metadata.tsv` (`diet_treatment_code`,
    `pen_code`). Un animal sin metadatos cuenta en `sin_metadatos`.
    """
    rows: list[dict[str, Any]] = []
    for step in cohort.steps:
        animals: Counter[str] = Counter()
        pens: dict[str, set[str]] = defaultdict(set)
        missing = 0
        for sample_id in step.remaining:
            row = metadata.get(sample_id)
            if row is None:
                missing += 1
                continue
            diet = row.get("diet_treatment_code", "")
            animals[diet] += 1
            pens[diet].add(row.get("pen_code", ""))
        rows.append(
            {
                "step": step.name,
                "description": step.description,
                "count": step.count,
                "removed": list(step.removed),
                "animals_by_diet": dict(sorted(animals.items())),
                "pens_by_diet": {diet: len(pens[diet]) for diet in sorted(pens)},
                "sin_metadatos": missing,
            }
        )
    return rows


__all__ = [
    "Cohort",
    "CohortConfig",
    "CohortConfigError",
    "CohortExclusion",
    "CohortStep",
    "complete_target_samples",
    "describe_cohort",
    "get_cohort_config",
    "load_cohort",
    "select_cohort",
    "ssu_read_depths",
]
