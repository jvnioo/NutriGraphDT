"""Preprocesamiento y control de calidad de abundancias microbianas (A34-4).

`AbundancePreprocessor` recibe el `IngestionPayload` de `AbundanceLoader` y produce las filas
``taxon`` de la tabla ``features`` y las filas de ``instances``. Las etapas, en orden, son:

1. **Validación y valores faltantes.** Un valor ausente (``None`` o ``NaN``) se descarta o se
   imputa como 0 según ``missing_strategy``; el valor imputado se marca con
   ``quality_flag="imputed"``. Se descartan los registros sin muestra o taxón, con valor no
   numérico, infinito o negativo, o con una unidad que no es de abundancia. Los conflictos se
   resuelven sin depender del orden: si un taxón tiene más de un valor en un grafo, o un
   ``graph_id`` aparece con más de una muestra, se descartan todos los registros implicados.
2. **Identificador de grafo.** Cada muestra es una instancia. Si el loader no conoce el
   ``graph_id`` (tablas reales), se asigna ``"<source_id>:<sample_id>"``.
3. **Abundancia relativa** por muestra (``relative_abundance``). Una muestra que mezcla
   unidades o sin abundancia total positiva se descarta.
4. **Filtro de taxa.** Un taxón está *presente* en una muestra si su abundancia relativa es
   mayor que 0 y al menos ``min_abundance``. Se conserva si está presente en una fracción de
   muestras mayor o igual que ``min_prevalence``.
5. **Transformación de salida.** ``"relative"`` entrega la abundancia relativa; ``"clr"``
   entrega la razón logarítmica centrada (``clr_transform``) calculada sobre el conjunto común
   de taxa conservados de la fuente, contando como 0 un taxón sin valor en la muestra.

Cada registro descartado queda en el informe con su posición y su motivo, y en el log
(``nutrigraphdt.data.preprocessors.abundance``). La salida no depende del orden de los
registros de entrada: las sumas usan `math.fsum`, los conflictos no eligen un registro y las
tablas se ordenan.

Los umbrales por defecto no eliminan ningún taxón y CLR exige un pseudoconteo explícito: los
valores adecuados son decisiones metodológicas que la configuración debe declarar. Las reglas
marcadas como provisionales en ``docs/data-pipeline-design.md`` (sección 4.4) son decisiones de
implementación pendientes de revisión por Investigación.
"""

from __future__ import annotations

import logging
import math
import numbers
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, fields
from typing import Any, Final

from nutrigraphdt.data.loaders.base import IngestionPayload
from nutrigraphdt.data.preprocessors.base import (
    DUPLICATE_RECORD,
    EMPTY_SAMPLE,
    FILTERED_TAXON,
    INVALID_RECORD,
    MISSING_VALUE,
    BasePreprocessor,
    DiscardedRecord,
    PreprocessedData,
    PreprocessingReport,
)
from nutrigraphdt.data.schema import NormalizedFeatureRecord, NormalizedInstanceRecord

logger = logging.getLogger(__name__)

NORMALIZATION_METHODS: Final[frozenset[str]] = frozenset({"relative", "clr"})
MISSING_STRATEGIES: Final[frozenset[str]] = frozenset({"drop", "zero"})

# Unidades canónicas que admiten normalización composicional por muestra.
ABUNDANCE_UNITS: Final[frozenset[str]] = frozenset(
    {"relative_abundance", "reads_per_million", "copies_per_gram"}
)

# Valor de `study_id`, `scenario_id` y `diet_treatment` cuando la fuente no lo informa.
UNKNOWN_CONTEXT: Final = "unknown"

# Misma tolerancia que usa `AbundanceLoader` para considerar una muestra ya normalizada.
RELATIVE_SUM_TOLERANCE: Final = 1e-6

_FEATURE_NAMES: Final[dict[str, tuple[str, str]]] = {
    "relative": ("abundance", "relative_abundance"),
    "clr": ("abundance_clr", "dimensionless"),
}


def _check_fraction(name: str, value: Any) -> None:
    """Exige un número finito en el intervalo [0, 1]."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"'{name}' debe ser numérico; se recibió {value!r}.")
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"'{name}' debe estar en el intervalo [0, 1]; se recibió {value!r}.")


@dataclass(frozen=True)
class AbundancePreprocessingConfig:
    """Parámetros del preprocesamiento de abundancias.

    Attributes
    ----------
    normalization:
        ``"relative"`` (por defecto) o ``"clr"``.
    clr_pseudocount:
        Constante positiva que se suma a cada abundancia relativa antes del logaritmo. Es
        obligatoria con ``normalization="clr"`` porque el logaritmo de 0 no existe; no tiene
        valor por defecto porque su elección afecta al resultado.
    min_prevalence:
        Fracción mínima de instancias (muestras), en [0, 1], en que un taxón debe estar presente.
    min_abundance:
        Abundancia relativa mínima, en [0, 1], para contar un taxón como presente.
    missing_strategy:
        ``"drop"`` (por defecto) descarta los valores faltantes; ``"zero"`` los imputa como 0.
    """

    normalization: str = "relative"
    clr_pseudocount: float | None = None
    min_prevalence: float = 0.0
    min_abundance: float = 0.0
    missing_strategy: str = "drop"

    def __post_init__(self) -> None:
        if not isinstance(self.normalization, str) or (
            self.normalization not in NORMALIZATION_METHODS
        ):
            raise ValueError(
                f"normalization {self.normalization!r} no válida. "
                f"Permitidas: {sorted(NORMALIZATION_METHODS)}"
            )
        if not isinstance(self.missing_strategy, str) or (
            self.missing_strategy not in MISSING_STRATEGIES
        ):
            raise ValueError(
                f"missing_strategy {self.missing_strategy!r} no válida. "
                f"Permitidas: {sorted(MISSING_STRATEGIES)}"
            )
        _check_fraction("min_prevalence", self.min_prevalence)
        _check_fraction("min_abundance", self.min_abundance)
        pseudocount = self.clr_pseudocount
        if pseudocount is not None:
            if isinstance(pseudocount, bool) or not isinstance(pseudocount, (int, float)):
                raise TypeError(f"'clr_pseudocount' debe ser numérico; se recibió {pseudocount!r}.")
            if not math.isfinite(pseudocount) or pseudocount <= 0.0:
                raise ValueError(
                    f"'clr_pseudocount' debe ser un número finito mayor que 0; "
                    f"se recibió {pseudocount!r}."
                )
        if self.normalization == "clr" and pseudocount is None:
            raise ValueError("normalization='clr' requiere declarar 'clr_pseudocount'.")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> AbundancePreprocessingConfig:
        """Crea la configuración desde un diccionario (p. ej. ``options["preprocessing"]``).

        Rechaza claves desconocidas para que un parámetro mal escrito no se ignore en silencio.
        """
        if not isinstance(data, Mapping):
            raise TypeError("La configuración de preprocesamiento debe ser un objeto.")
        allowed = {item.name for item in fields(cls)}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ValueError(
                f"Parámetros de preprocesamiento desconocidos: {unknown}. "
                f"Permitidos: {sorted(allowed)}"
            )
        return cls(**dict(data))

    def to_dict(self) -> dict[str, Any]:
        """Serializa la configuración a un diccionario compatible con JSON."""
        return asdict(self)


def relative_abundance(values: Sequence[float], unit: str) -> list[float]:
    """Expresa los valores de una muestra como abundancia relativa.

    Si la unidad ya es ``relative_abundance`` y la suma no supera 1 (con la tolerancia de
    `AbundanceLoader`), los valores se conservan: una suma menor que 1 indica una fracción no
    asignada que no se reparte entre los taxa. En otro caso, cada valor se divide por el total
    de la muestra.

    Raises
    ------
    ValueError
        Si la muestra no tiene abundancia total positiva.
    """
    total = math.fsum(values)
    if total <= 0.0:
        raise ValueError("La muestra no tiene abundancia total positiva.")
    if unit == "relative_abundance" and total <= 1.0 + RELATIVE_SUM_TOLERANCE:
        return [float(value) for value in values]
    return [value / total for value in values]


def clr_transform(values: Sequence[float], pseudocount: float) -> list[float]:
    """Razón logarítmica centrada (CLR) de una composición.

    ``clr(x)_i = ln(x_i + p) - (1/D) * sum_j ln(x_j + p)``, con ``p`` el pseudoconteo y ``D``
    el número de componentes. Los valores de una muestra suman 0.

    Raises
    ------
    ValueError
        Si no hay componentes o algún ``x_i + p`` no es positivo.
    """
    if not values:
        raise ValueError("CLR requiere al menos un componente.")
    shifted = [value + pseudocount for value in values]
    if any(not item > 0.0 for item in shifted):
        raise ValueError("CLR requiere que cada valor más el pseudoconteo sea positivo.")
    logs = [math.log(item) for item in shifted]
    mean = math.fsum(logs) / len(logs)
    return [item - mean for item in logs]


def taxon_prevalence(
    samples: Mapping[str, Mapping[str, float]], min_abundance: float
) -> dict[str, float]:
    """Fracción de muestras en que cada taxón está presente.

    ``samples`` asocia cada muestra a sus abundancias relativas por taxón. Un taxón está
    presente si su abundancia es mayor que 0 y al menos ``min_abundance``; un taxón sin
    registro en una muestra cuenta como ausente en ella.
    """
    if not samples:
        return {}
    counts: dict[str, int] = {}
    for taxa in samples.values():
        for taxon, value in taxa.items():
            present = value > 0.0 and value >= min_abundance
            counts[taxon] = counts.get(taxon, 0) + int(present)
    total = len(samples)
    return {taxon: count / total for taxon, count in sorted(counts.items())}


@dataclass(frozen=True)
class _Entry:
    """Registro validado, listo para normalizar."""

    index: int
    graph_id: str
    sample_id: str
    taxon_id: str
    value: float
    unit: str
    imputed: bool
    record: dict[str, Any]


# Campos que se conservan de un registro eliminado por el filtro de taxa: en tablas reales esos
# descartes pueden ser numerosos y el resto del registro repite la procedencia de la fuente.
_FILTERED_RECORD_FIELDS: Final = ("graph_id", "sample_id", "taxon_id", "value", "unit")


def _non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_number(value: Any) -> bool:
    return isinstance(value, numbers.Real) and not isinstance(value, bool)


def _is_missing(value: Any) -> bool:
    """``None`` o ``NaN`` (de Python o de cualquier tipo numérico real)."""
    if value is None:
        return True
    if not _is_number(value):
        return False
    try:
        return math.isnan(float(value))
    except OverflowError:
        return False


class AbundancePreprocessor(BasePreprocessor):
    """Normaliza, filtra y controla la calidad de las abundancias de un `AbundanceLoader`."""

    def __init__(self, config: AbundancePreprocessingConfig | None = None) -> None:
        """Inicializa el preprocesador; sin configuración usa los valores por defecto."""
        self._config = config or AbundancePreprocessingConfig()

    @property
    def config(self) -> AbundancePreprocessingConfig:
        """Parámetros del preprocesamiento."""
        return self._config

    def process(self, payload: IngestionPayload) -> PreprocessedData:
        """Preprocesa las abundancias del payload sin modificarlo."""
        raw = payload.raw_data
        if not isinstance(raw, (list, tuple)):
            raise TypeError(
                f"raw_data debe ser una lista de registros; se recibió {type(raw).__name__}."
            )
        source_id = payload.metadata.source_id
        discarded: list[DiscardedRecord] = []

        candidates, samples_of_graph = self._validate(raw, source_id, discarded)
        entries = self._resolve_conflicts(candidates, samples_of_graph, source_id, discarded)
        samples = self._normalize_samples(entries, source_id, discarded)
        prevalence = taxon_prevalence(
            {
                graph_id: {entry.taxon_id: value for entry, value in pairs}
                for graph_id, pairs in samples.items()
            },
            self._config.min_abundance,
        )
        removed = {
            taxon: share
            for taxon, share in prevalence.items()
            if share < self._config.min_prevalence
        }
        features, sample_ids = self._build_features(samples, removed, source_id, discarded)

        metadata = payload.metadata
        instances = [
            NormalizedInstanceRecord(
                graph_id=graph_id,
                sample_id=sample_ids[graph_id],
                species=metadata.species,
                gut_segment=metadata.gut_segment,
                study_id=UNKNOWN_CONTEXT,
                scenario_id=UNKNOWN_CONTEXT,
                diet_treatment=UNKNOWN_CONTEXT,
                timepoint=None,
                is_synthetic=metadata.is_synthetic,
                source_id=source_id,
            )
            for graph_id in sorted(sample_ids)
        ]
        errors = payload.extra.get("errors", [])
        loader_errors = (
            [str(error) for error in errors] if isinstance(errors, (list, tuple)) else [str(errors)]
        )
        report = PreprocessingReport(
            source_id=source_id,
            parameters=self._config.to_dict(),
            input_records=len(raw),
            output_records=len(features),
            imputed_records=sum(1 for item in features if item.quality_flag == "imputed"),
            discarded=sorted(discarded, key=lambda item: item.index),
            removed_taxa=removed,
            loader_errors=loader_errors,
        )
        logger.info(
            "[%s] preprocesamiento: %d registros de entrada, %d de salida, %d descartados, "
            "%d imputados.",
            source_id,
            report.input_records,
            report.output_records,
            len(report.discarded),
            report.imputed_records,
        )
        return PreprocessedData(instances=instances, features=features, report=report)

    # ------------------------------------------------------------------
    # Etapas
    # ------------------------------------------------------------------

    def _discard(
        self,
        discarded: list[DiscardedRecord],
        source_id: str,
        index: int,
        reason: str,
        detail: str,
        record: dict[str, Any],
        *,
        log: bool = True,
    ) -> None:
        """Registra un descarte en el informe y, salvo ``log=False``, en el log."""
        discarded.append(DiscardedRecord(index=index, reason=reason, detail=detail, record=record))
        if log:
            logger.warning("[%s] registro %d descartado (%s): %s", source_id, index, reason, detail)

    def _validate(
        self, raw: Sequence[Any], source_id: str, discarded: list[DiscardedRecord]
    ) -> tuple[list[_Entry], dict[str, set[str]]]:
        """Valida cada registro por separado y aplica la estrategia de valores faltantes.

        Devuelve también las muestras declaradas por cada ``graph_id`` en todos los registros
        con identificadores válidos, aunque su valor se haya descartado, para detectar un
        ``graph_id`` ambiguo sin depender de qué registros sobrevivieron.
        """
        entries: list[_Entry] = []
        samples_of_graph: dict[str, set[str]] = {}
        for index, item in enumerate(raw):
            if not isinstance(item, Mapping):
                self._discard(
                    discarded,
                    source_id,
                    index,
                    INVALID_RECORD,
                    "el registro no es un diccionario",
                    {"record": repr(item)},
                )
                continue
            record = dict(item)
            problem = self._structural_problem(record)
            if problem:
                self._discard(discarded, source_id, index, INVALID_RECORD, problem, record)
                continue
            sample_id: str = record["sample_id"]
            graph_id: str = record.get("graph_id") or f"{source_id}:{sample_id}"
            samples_of_graph.setdefault(graph_id, set()).add(sample_id)

            value = record.get("value")
            imputed = False
            if _is_missing(value):
                if self._config.missing_strategy == "drop":
                    self._discard(
                        discarded, source_id, index, MISSING_VALUE, "valor faltante", record
                    )
                    continue
                number, imputed = 0.0, True
            else:
                number_or_problem = self._parse_value(value)
                if isinstance(number_or_problem, str):
                    self._discard(
                        discarded, source_id, index, INVALID_RECORD, number_or_problem, record
                    )
                    continue
                number = number_or_problem

            entries.append(
                _Entry(
                    index=index,
                    graph_id=graph_id,
                    sample_id=sample_id,
                    taxon_id=record["taxon_id"],
                    value=number,
                    unit=record["unit"],
                    imputed=imputed,
                    record=record,
                )
            )
        return entries, samples_of_graph

    def _resolve_conflicts(
        self,
        entries: list[_Entry],
        samples_of_graph: Mapping[str, set[str]],
        source_id: str,
        discarded: list[DiscardedRecord],
    ) -> list[_Entry]:
        """Descarta los registros en conflicto sin elegir uno según el orden.

        - Un ``graph_id`` declarado con más de una muestra invalida todos sus registros.
        - Un valor imputado no compite con un valor medido del mismo taxón y grafo: se descarta
          como faltante.
        - Si quedan varios valores del mismo taxón en el mismo grafo, se descartan todos: no hay
          regla para saber cuál es el correcto.
        """
        ambiguous = {graph: ids for graph, ids in samples_of_graph.items() if len(ids) > 1}
        measured: dict[tuple[str, str], int] = {}
        imputed: dict[tuple[str, str], int] = {}
        for entry in entries:
            counter = imputed if entry.imputed else measured
            key = (entry.graph_id, entry.taxon_id)
            counter[key] = counter.get(key, 0) + 1

        kept: list[_Entry] = []
        for entry in entries:
            key = (entry.graph_id, entry.taxon_id)
            if entry.graph_id in ambiguous:
                self._discard(
                    discarded,
                    source_id,
                    entry.index,
                    INVALID_RECORD,
                    f"graph_id '{entry.graph_id}' corresponde a varias muestras "
                    f"{sorted(ambiguous[entry.graph_id])}",
                    entry.record,
                )
                continue
            if entry.imputed and measured.get(key, 0) > 0:
                self._discard(
                    discarded,
                    source_id,
                    entry.index,
                    MISSING_VALUE,
                    f"valor faltante; el taxón '{entry.taxon_id}' tiene un valor medido en "
                    f"'{entry.graph_id}'",
                    entry.record,
                )
                continue
            count = measured.get(key, 0) if not entry.imputed else imputed[key]
            if count > 1:
                self._discard(
                    discarded,
                    source_id,
                    entry.index,
                    DUPLICATE_RECORD,
                    f"el taxón '{entry.taxon_id}' tiene {count} valores en '{entry.graph_id}'; "
                    "se descartan todos",
                    entry.record,
                )
                continue
            kept.append(entry)
        return kept

    @staticmethod
    def _structural_problem(record: Mapping[str, Any]) -> str | None:
        """Describe el primer problema de identificadores o unidad, o ``None`` si no hay."""
        if not _non_empty_str(record.get("sample_id")):
            return "sample_id vacío o ausente"
        if not _non_empty_str(record.get("taxon_id")):
            return "taxon_id vacío o ausente"
        graph_id = record.get("graph_id")
        if graph_id is not None and not _non_empty_str(graph_id):
            return "graph_id debe ser None o un texto no vacío"
        unit = record.get("unit")
        if not isinstance(unit, str) or unit not in ABUNDANCE_UNITS:
            return f"unidad {unit!r} no admitida; se esperaba una de {sorted(ABUNDANCE_UNITS)}"
        return None

    @staticmethod
    def _parse_value(value: Any) -> float | str:
        """Devuelve la abundancia como ``float`` o un texto que explica por qué no es válida."""
        if not _is_number(value):
            return f"valor no numérico {value!r}"
        try:
            number = float(value)
        except OverflowError:
            return f"valor no representable como número de punto flotante {value!r}"
        if not math.isfinite(number):
            return f"valor no finito {value!r}"
        if number < 0.0:
            return f"valor negativo {value!r}"
        return number

    def _normalize_samples(
        self, entries: list[_Entry], source_id: str, discarded: list[DiscardedRecord]
    ) -> dict[str, list[tuple[_Entry, float]]]:
        """Calcula la abundancia relativa de cada muestra, con sus registros ordenados por taxón."""
        groups: dict[str, list[_Entry]] = {}
        for entry in entries:
            groups.setdefault(entry.graph_id, []).append(entry)

        samples: dict[str, list[tuple[_Entry, float]]] = {}
        for graph_id in sorted(groups):
            group = sorted(groups[graph_id], key=lambda entry: entry.taxon_id)
            units = sorted({entry.unit for entry in group})
            if len(units) > 1:
                reason, detail = INVALID_RECORD, f"la muestra '{graph_id}' mezcla unidades {units}"
            else:
                try:
                    relative = relative_abundance([entry.value for entry in group], units[0])
                except OverflowError:
                    reason = INVALID_RECORD
                    detail = f"la suma de la muestra '{graph_id}' no es representable"
                except ValueError:
                    reason = EMPTY_SAMPLE
                    detail = f"la muestra '{graph_id}' no tiene abundancia total positiva"
                else:
                    samples[graph_id] = list(zip(group, relative, strict=True))
                    continue
            for entry in group:
                self._discard(discarded, source_id, entry.index, reason, detail, entry.record)
        return samples

    def _build_features(
        self,
        samples: Mapping[str, list[tuple[_Entry, float]]],
        removed: Mapping[str, float],
        source_id: str,
        discarded: list[DiscardedRecord],
    ) -> tuple[list[NormalizedFeatureRecord], dict[str, str]]:
        """Aplica el filtro de taxa y la transformación de salida."""
        config = self._config
        for taxon in sorted(removed):
            logger.info(
                "[%s] taxón '%s' eliminado: presente en una fracción %.6g de las instancias "
                "(mínimo %s, abundancia relativa mínima %s).",
                source_id,
                taxon,
                removed[taxon],
                config.min_prevalence,
                config.min_abundance,
            )
        # Conjunto común de taxa de la fuente: CLR usa el mismo denominador en todas las
        # muestras para que el valor de un taxón sea comparable entre ellas.
        shared_taxa = sorted(
            {entry.taxon_id for pairs in samples.values() for entry, _ in pairs} - set(removed)
        )
        if config.normalization == "clr" and len(shared_taxa) == 1:
            logger.warning(
                "[%s] CLR con un solo taxón conservado ('%s'): todos los valores son 0.",
                source_id,
                shared_taxa[0],
            )
        feature_name, unit = _FEATURE_NAMES[config.normalization]
        features: list[NormalizedFeatureRecord] = []
        sample_ids: dict[str, str] = {}
        for graph_id in sorted(samples):
            kept: list[tuple[_Entry, float]] = []
            for entry, value in samples[graph_id]:
                if entry.taxon_id in removed:
                    self._discard(
                        discarded,
                        source_id,
                        entry.index,
                        FILTERED_TAXON,
                        f"taxón '{entry.taxon_id}' presente en una fracción "
                        f"{removed[entry.taxon_id]:.6g} de las instancias (presencia: abundancia "
                        f"relativa > 0 y >= {config.min_abundance}); mínimo "
                        f"{config.min_prevalence}",
                        {key: entry.record.get(key) for key in _FILTERED_RECORD_FIELDS},
                        log=False,
                    )
                    continue
                kept.append((entry, value))
            if not kept:
                continue
            values = [value for _, value in kept]
            if config.normalization == "clr":
                assert config.clr_pseudocount is not None  # garantizado por la configuración
                observed = {entry.taxon_id: value for entry, value in kept}
                composition = [observed.get(taxon, 0.0) for taxon in shared_taxa]
                clr = dict(
                    zip(
                        shared_taxa,
                        clr_transform(composition, config.clr_pseudocount),
                        strict=True,
                    )
                )
                values = [clr[entry.taxon_id] for entry, _ in kept]
            sample_ids[graph_id] = kept[0][0].sample_id
            for (entry, _), value in zip(kept, values, strict=True):
                features.append(
                    NormalizedFeatureRecord(
                        graph_id=graph_id,
                        node_id=entry.taxon_id,
                        node_type="taxon",
                        feature_name=feature_name,
                        value=value,
                        unit=unit,
                        quality_flag="imputed" if entry.imputed else "valid",
                        raw_id=None,
                        source_id=source_id,
                    )
                )
        return features, sample_ids
