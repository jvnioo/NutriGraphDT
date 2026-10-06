"""Orquestador del módulo de datos: ingesta → preprocesamiento → salida tabular (A34-4).

`DataPipeline` encadena, para cada fuente de microbioma registrada en ``configs/sources.json``,
tres etapas independientes y reemplazables:

1. **Ingesta:** el loader que un `LoaderRegistry` asigna a la fuente (por defecto
   `AbundanceLoader` para ``jsonl``, ``tsv`` y ``csv``) produce un `IngestionPayload`.
2. **Preprocesamiento:** `AbundancePreprocessor` normaliza, filtra y controla la calidad, con
   la configuración del pipeline o la de ``options["preprocessing"]`` de la fuente.
3. **Salida:** las tablas de todas las fuentes se reúnen en un `NormalizedTabularDataset`, se
   validan y, si se indica un directorio, se exportan con
   `NormalizedTabularDataset.export_tables` junto con ``preprocessing_report.json``.

Alcance actual: el pipeline produce las tablas ``instances`` y ``features`` (nodos ``taxon``).
Las tablas ``edges`` y ``targets`` quedan vacías: las concentraciones de metabolitos son
variables objetivo y no atributos de nodo (``docs/data-pipeline-design.md``, sección 6.4), y
las relaciones entre entidades no provienen de estas fuentes.

Para el dataset sintético (``format="jsonl"``), el contexto de cada instancia (estudio,
escenario, dieta) se toma del propio dataset; en las fuentes reales queda ``"unknown"`` hasta
que se integren sus metadatos de muestra. Esta lectura del contexto es provisional: depende del
marcador ``"generated"`` que `AbundanceLoader` deja en ``extra["source_path"]``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final

from nutrigraphdt.data.loaders.abundance import AbundanceLoader
from nutrigraphdt.data.loaders.base import IngestionPayload, LoaderRegistry, SourceMetadata
from nutrigraphdt.data.preprocessors.abundance import (
    UNKNOWN_CONTEXT,
    AbundancePreprocessingConfig,
    AbundancePreprocessor,
)
from nutrigraphdt.data.preprocessors.base import PreprocessedData, PreprocessingReport
from nutrigraphdt.data.schema import (
    NormalizedFeatureRecord,
    NormalizedInstanceRecord,
    NormalizedTabularDataset,
)
from nutrigraphdt.data.synthetic.export import (
    InstanceRecord,
    generate_scenario_dataset,
    load_dataset,
)

logger = logging.getLogger(__name__)

REPORT_FILENAME: Final = "preprocessing_report.json"
TABLE_FORMATS: Final[frozenset[str]] = frozenset({"tsv", "csv"})

# Archivos que escribe `run`: se eliminan antes de reescribir con ``overwrite=True`` para no
# dejar tablas de una ejecución anterior en otro formato.
_OUTPUT_FILES: Final[tuple[str, ...]] = (
    *(
        f"{table}.{ext}"
        for table in ("instances", "features", "edges", "targets")
        for ext in TABLE_FORMATS
    ),
    "metadata.json",
    REPORT_FILENAME,
)

# Marcador con que `AbundanceLoader` indica en ``extra["source_path"]`` que generó el dataset
# sintético en memoria en lugar de leerlo de disco.
_GENERATED_ORIGIN: Final = "generated"


def default_loader_registry() -> LoaderRegistry:
    """Registro de loaders del pipeline: `AbundanceLoader` para jsonl, tsv y csv."""
    registry = LoaderRegistry()
    for fmt in ("jsonl", "tsv", "csv"):
        registry.register_format(fmt, AbundanceLoader)
    return registry


@dataclass
class PipelineResult:
    """Resultado de `DataPipeline.run`."""

    dataset: NormalizedTabularDataset
    reports: dict[str, PreprocessingReport]
    exported: dict[str, Path] = field(default_factory=dict)


def _synthetic_instances(payload: IngestionPayload) -> dict[str, InstanceRecord]:
    """Obtiene las instancias del dataset sintético del que proviene el payload."""
    origin = payload.extra.get("source_path")
    if origin == _GENERATED_ORIGIN:
        dataset = generate_scenario_dataset()
    elif isinstance(origin, str):
        dataset = load_dataset(origin)
    else:
        return {}
    return {instance.graph_id: instance for instance in dataset.instances}


def _with_context(
    instance: NormalizedInstanceRecord, context: InstanceRecord
) -> NormalizedInstanceRecord:
    """Completa una instancia normalizada con el contexto de su instancia sintética."""
    return replace(
        instance,
        species=context.species,
        gut_segment=context.gut_segment,
        study_id=context.study_id,
        scenario_id=context.scenario_id,
        diet_treatment=context.diet_treatment,
        timepoint=context.timepoint,
        is_synthetic=context.is_synthetic,
    )


def _provenance(metadata: SourceMetadata) -> dict[str, Any]:
    """Procedencia de una fuente que se conserva en los metadatos del dataset."""
    return {
        "source_id": metadata.source_id,
        "name": metadata.name,
        "version": metadata.version,
        "format": metadata.format,
        "species": metadata.species,
        "gut_segment": metadata.gut_segment,
        "is_synthetic": metadata.is_synthetic,
        "citation_or_url": metadata.citation_or_url,
    }


class DataPipeline:
    """Ejecuta ingesta, preprocesamiento y salida tabular para fuentes de microbioma."""

    def __init__(
        self,
        sources: Mapping[str, SourceMetadata],
        *,
        config: AbundancePreprocessingConfig | None = None,
        registry: LoaderRegistry | None = None,
    ) -> None:
        """Inicializa el pipeline.

        Parameters
        ----------
        sources:
            Registro de fuentes por ``source_id``, normalmente el de `load_sources`.
        config:
            Configuración de preprocesamiento común. Cada fuente puede sobrescribir parámetros
            con ``options["preprocessing"]``.
        registry:
            Asigna el loader de cada fuente; por defecto `default_loader_registry`.
        """
        self._sources = dict(sources)
        self._config = config or AbundancePreprocessingConfig()
        self._registry = registry or default_loader_registry()

    def preprocessing_config(self, metadata: SourceMetadata) -> AbundancePreprocessingConfig:
        """Configuración efectiva de una fuente: la común más ``options["preprocessing"]``."""
        overrides = metadata.options.get("preprocessing")
        if overrides is None:
            return self._config
        if not isinstance(overrides, Mapping):
            raise TypeError(
                f"options['preprocessing'] de '{metadata.source_id}' debe ser un objeto."
            )
        try:
            return AbundancePreprocessingConfig.from_mapping(
                {**self._config.to_dict(), **overrides}
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"options['preprocessing'] de '{metadata.source_id}' no es válida: {exc}"
            ) from exc

    def process_source(self, source_id: str) -> PreprocessedData:
        """Ejecuta la ingesta y el preprocesamiento de una fuente."""
        metadata = self._sources.get(source_id)
        if metadata is None:
            raise ValueError(
                f"La fuente '{source_id}' no está registrada. Disponibles: {sorted(self._sources)}"
            )
        if "microbiome" not in metadata.data_types:
            raise ValueError(
                f"La fuente '{source_id}' no declara datos de microbioma (data_types="
                f"{list(metadata.data_types)}); el pipeline procesa abundancias microbianas."
            )
        config = self.preprocessing_config(metadata)
        try:
            loader = self._registry.get_loader(metadata)
        except KeyError as exc:
            raise ValueError(
                f"No hay loader para la fuente '{source_id}' (formato '{metadata.format}')."
            ) from exc
        payload = loader.load()
        data = AbundancePreprocessor(config).process(payload)
        if not data.instances:
            report = data.report
            raise ValueError(
                f"La fuente '{source_id}' no produjo instancias: {report.input_records} "
                f"registros leídos, descartes por motivo {report.discarded_counts()}, "
                f"{len(report.removed_taxa)} taxa eliminados por el filtro. "
                f"Errores del loader: {report.loader_errors[:3]}"
            )
        if metadata.format == "jsonl":
            contexts = _synthetic_instances(payload)
            missing = [inst.graph_id for inst in data.instances if inst.graph_id not in contexts]
            if missing:
                logger.warning(
                    "[%s] sin contexto sintético para %s; quedan con contexto '%s'.",
                    source_id,
                    missing,
                    UNKNOWN_CONTEXT,
                )
            data.instances = [
                _with_context(instance, contexts[instance.graph_id])
                if instance.graph_id in contexts
                else instance
                for instance in data.instances
            ]
        return data

    def run(
        self,
        source_ids: Sequence[str],
        *,
        output_dir: Path | str | None = None,
        overwrite: bool = False,
        table_format: str = "tsv",
    ) -> PipelineResult:
        """Procesa las fuentes indicadas y, opcionalmente, exporta las tablas.

        Raises
        ------
        ValueError
            Si no se indican fuentes, se repiten, alguna no es válida o no produce instancias,
            dos fuentes producen el mismo ``graph_id`` o el dataset resultante no supera su
            validación.
        FileExistsError
            Si ``output_dir`` ya tiene contenido y ``overwrite`` es falso. Se comprueba antes de
            procesar. Con ``overwrite=True`` se eliminan las tablas e informes de una ejecución
            anterior (en ambos formatos) y se conservan los demás archivos.
        """
        if isinstance(source_ids, str):
            raise TypeError("source_ids debe ser una secuencia de identificadores, no un texto.")
        if not source_ids:
            raise ValueError("Debe indicarse al menos una fuente.")
        repeated = sorted({sid for sid in source_ids if list(source_ids).count(sid) > 1})
        if repeated:
            raise ValueError(f"Fuentes repetidas: {repeated}")
        if table_format not in TABLE_FORMATS:
            raise ValueError(
                f"table_format {table_format!r} no válido. Permitidos: {sorted(TABLE_FORMATS)}"
            )
        out = Path(output_dir) if output_dir is not None else None
        if out is not None and out.exists() and any(out.iterdir()) and not overwrite:
            raise FileExistsError(
                f"{out} ya tiene contenido; use overwrite=True para reemplazar las tablas."
            )

        reports: dict[str, PreprocessingReport] = {}
        instances: dict[str, NormalizedInstanceRecord] = {}
        features: list[NormalizedFeatureRecord] = []
        for source_id in source_ids:
            data = self.process_source(source_id)
            reports[source_id] = data.report
            for instance in data.instances:
                previous = instances.get(instance.graph_id)
                if previous is not None:
                    raise ValueError(
                        f"El graph_id '{instance.graph_id}' aparece en '{previous.source_id}' "
                        f"y en '{source_id}'."
                    )
                instances[instance.graph_id] = instance
            features.extend(data.features)
        features.sort(
            key=lambda item: (item.graph_id, item.node_type, item.node_id, item.feature_name)
        )

        dataset = NormalizedTabularDataset(
            metadata=self._dataset_metadata(source_ids, reports, len(instances), len(features)),
            instances=[instances[graph_id] for graph_id in sorted(instances)],
            features=features,
        )
        errors = dataset.validate()
        if errors:
            raise ValueError(f"El dataset normalizado no es consistente: {errors}")

        exported: dict[str, Path] = {}
        if out is not None:
            for name in _OUTPUT_FILES:
                (out / name).unlink(missing_ok=True)
            exported = dataset.export_tables(out, format=table_format)
            report_path = out / REPORT_FILENAME
            report_doc = {"reports": [reports[sid].to_dict() for sid in source_ids]}
            report_path.write_text(
                json.dumps(report_doc, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            exported["preprocessing_report"] = report_path
        return PipelineResult(dataset=dataset, reports=reports, exported=exported)

    def _dataset_metadata(
        self,
        source_ids: Sequence[str],
        reports: Mapping[str, PreprocessingReport],
        n_instances: int,
        n_features: int,
    ) -> dict[str, Any]:
        """Metadatos deterministas del dataset: procedencia, parámetros y control de calidad."""
        return {
            "pipeline": f"{__name__}.DataPipeline",
            "sources": [_provenance(self._sources[sid]) for sid in source_ids],
            "preprocessing": {sid: dict(reports[sid].parameters) for sid in source_ids},
            "quality_control": {sid: reports[sid].summary() for sid in source_ids},
            "counts": {
                "instances": n_instances,
                "features": n_features,
                "edges": 0,
                "targets": 0,
            },
        }
