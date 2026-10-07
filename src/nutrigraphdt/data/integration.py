"""Integración del contexto por muestra en el formato tabular normalizado (A39-1, #35).

`DataPipeline` produce instancias y features de taxón desde las abundancias, pero deja el
contexto experimental en `"unknown"` y las tablas `targets` vacías. `attach_sample_context`
completa esas tablas con lo que entregan `MetadataLoader` y `MetaboliteLoader` para las mismas
muestras:

- **instancias**: `study_id`, `diet_treatment` y `timepoint` desde campos de metadatos;
- **features del nodo `host`**: los campos numéricos de fenotipo individual (por ejemplo,
  `body_weight_g`), con su unidad;
- **targets**: las concentraciones de metabolitos, medidas, con su matriz.

Solo se completa lo que pertenece a una instancia existente; las muestras de los payloads sin
instancia se informan en `IntegrationReport` y no se agregan. No inventa valores: un campo
ausente conserva el valor original de la instancia.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Final

from nutrigraphdt.data.loaders.base import IngestionPayload
from nutrigraphdt.data.schema import (
    NormalizedFeatureRecord,
    NormalizedTabularDataset,
    NormalizedTargetRecord,
)

HOST_NODE_SUFFIX: Final = ":host"
"""Sufijo del `node_id` del huésped de cada instancia: `<sample_id>:host`. Derivarlo del
`sample_id` conserva el prefijo `synthetic:` (NOD-04) y da el mismo ID a los escenarios de una
misma muestra (INS-05)."""

DEFAULT_CONTEXT_FIELDS: Final[Mapping[str, str]] = {
    "study_id": "trial_code",
    "diet_treatment": "diet_treatment_name",
    "timepoint": "sampling_day",
}
"""Campo de instancia → campo de `MetadataLoader` (nombres de la fuente D1 HoloFood)."""


def _text(value: Any) -> str:
    """Texto de un valor de metadatos; `35.0` → `"35"` para que el día no arrastre decimales."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def host_node_id(sample_id: str) -> str:
    """`node_id` del nodo `host` de la instancia de `sample_id`."""
    return f"{sample_id}{HOST_NODE_SUFFIX}"


@dataclass(frozen=True)
class IntegrationReport:
    """Qué se integró y qué quedó fuera por no tener instancia."""

    instances_with_context: int = 0
    host_features: int = 0
    targets: int = 0
    unmatched_metadata_samples: tuple[str, ...] = ()
    unmatched_metabolite_samples: tuple[str, ...] = ()
    skipped_metadata_fields: tuple[str, ...] = field(default_factory=tuple)


def attach_sample_context(
    dataset: NormalizedTabularDataset,
    *,
    metadata: IngestionPayload | None = None,
    metabolites: IngestionPayload | None = None,
    context_fields: Mapping[str, str] = DEFAULT_CONTEXT_FIELDS,
    host_fields: tuple[str, ...] = ("body_weight_g",),
    target_type: str = "scfa_concentration",
    sample_matrix: str = "cecal_content",
) -> tuple[NormalizedTabularDataset, IntegrationReport]:
    """Devuelve una copia de `dataset` con el contexto, el huésped y los targets integrados.

    Las muestras se emparejan por `sample_id`. `context_fields` dice qué campo de metadatos
    llena cada campo de instancia; `host_fields`, qué campos numéricos pasan a features del
    huésped. Los registros de `metabolites` pasan a `targets` con `target_type`,
    `sample_matrix` y `measured_or_predicted="measured"`; el `target_id` es el `canonical_id`
    del loader.
    """
    by_sample = {instance.sample_id: instance for instance in dataset.instances}
    meta_by_sample: dict[str, dict[str, Mapping[str, Any]]] = {}
    for record in metadata.raw_data if metadata is not None else []:
        meta_by_sample.setdefault(str(record["sample_id"]), {})[str(record["field"])] = record

    instances = []
    with_context = 0
    for instance in dataset.instances:
        fields = meta_by_sample.get(instance.sample_id, {})
        updates: dict[str, Any] = {
            target: _text(fields[source]["value"])
            for target, source in context_fields.items()
            if source in fields and fields[source]["value"] not in (None, "")
        }
        if updates:
            with_context += 1
            instance = replace(instance, **updates)
        instances.append(instance)

    features = list(dataset.features)
    host_count = 0
    skipped: set[str] = set()
    for sample_id, fields in sorted(meta_by_sample.items()):
        owner = by_sample.get(sample_id)
        if owner is None:
            continue
        for name in host_fields:
            record = fields.get(name)
            if record is None:
                continue
            value = record["value"]
            if isinstance(value, bool) or not isinstance(value, int | float):
                skipped.add(name)
                continue
            features.append(
                NormalizedFeatureRecord(
                    graph_id=owner.graph_id,
                    node_id=host_node_id(sample_id),
                    node_type="host",
                    feature_name=name,
                    value=float(value),
                    unit=str(record["unit"]),
                    source_id=str(record.get("source_id", "unknown")),
                )
            )
            host_count += 1

    targets = list(dataset.targets)
    unmatched_metabolites: set[str] = set()
    for record in metabolites.raw_data if metabolites is not None else []:
        sample_id = str(record["sample_id"])
        target_owner = by_sample.get(sample_id)
        if target_owner is None:
            unmatched_metabolites.add(sample_id)
            continue
        targets.append(
            NormalizedTargetRecord(
                graph_id=target_owner.graph_id,
                target_type=target_type,
                target_id=str(record["canonical_id"]),
                value=float(record["value"]),
                unit=str(record["unit"]),
                sample_matrix=sample_matrix,
                measured_or_predicted="measured",
                source_id=str(record.get("source_id", "unknown")),
            )
        )

    integrated = replace(
        dataset,
        instances=instances,
        features=features,
        targets=sorted(targets, key=lambda t: (t.graph_id, t.target_type, t.target_id)),
    )
    report = IntegrationReport(
        instances_with_context=with_context,
        host_features=host_count,
        targets=len(targets) - len(dataset.targets),
        unmatched_metadata_samples=tuple(sorted(set(meta_by_sample) - set(by_sample))),
        unmatched_metabolite_samples=tuple(sorted(unmatched_metabolites)),
        skipped_metadata_fields=tuple(sorted(skipped)),
    )
    return integrated, report
