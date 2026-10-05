"""Definición del formato tabular intermedio común para NutriGraphDT.

Este módulo formaliza la salida normalizada del módulo de datos (ingesta → preprocesamiento
→ salida tabular normalizada), estableciendo las columnas, tipos estrictos, unidades canónicas
y reglas de validación que unifican tanto el dataset sintético (actividad 26) como las fuentes
reales priorizadas por Investigación (HoloFood, Utkina et al., Plata et al., Beauclercq et al.).
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final

# ---------------------------------------------------------------------------
# Conjuntos canónicos de valores permitidos
# ---------------------------------------------------------------------------

ALLOWED_SPECIES: Final[frozenset[str]] = frozenset({"chicken", "pig"})

ALLOWED_GUT_SEGMENTS: Final[frozenset[str]] = frozenset(
    {"ileum", "jejunum", "cecum", "colon", "serum", "feces", "multi"}
)

ALLOWED_NODE_TYPES: Final[frozenset[str]] = frozenset(
    {
        "taxon",
        "metabolite",
        "substrate",
        "additive",
        "diet",
        "phenotype",
        "function",
        "host",
    }
)

ALLOWED_RELATION_TYPES: Final[frozenset[str]] = frozenset(
    {
        "produces",
        "consumes",
        "ferments",
        "modulates",
        "affects",
        "associated_with",
        "interacts_with",
        "cross_feeds",
        "provides",
        "has_capacity",
        "targets",
        "available_to",
        "measured_in",
        "participates_in",
        "exhibits",
    }
)

ALLOWED_EVIDENCE_STATUSES: Final[frozenset[str]] = frozenset(
    {"experimental", "observed", "inferred", "literature", "hypothetical", "annotated", "synthetic"}
)

ALLOWED_QUALITY_FLAGS: Final[frozenset[str]] = frozenset(
    {"valid", "below_lod", "missing", "imputed"}
)

ALLOWED_TARGET_TYPES: Final[frozenset[str]] = frozenset(
    {
        "metabolite",
        "phenotype",
        "scfa_concentration",
        "metabolite_concentration",
        "feed_conversion_ratio",
        "body_weight_gain",
        "digestive_efficiency",
        "synthetic",
    }
)

ALLOWED_MEASUREMENT_KINDS: Final[frozenset[str]] = frozenset({"measured", "predicted", "synthetic"})

CANONICAL_UNITS: Final[frozenset[str]] = frozenset(
    {
        # Microbioma
        "relative_abundance",
        "reads_per_million",
        "copies_per_gram",
        "presence_absence",
        # Metaboloma / Quimico
        "mmol_kg",
        "umol_g",
        "mM",
        "mg_kg",
        "g_kg",
        "proportion",
        "CFU_kg",
        # Fenotipico / Productivo
        "g",
        "ratio",
        "dimensionless",
        "score",
    }
)


# ---------------------------------------------------------------------------
# Dataclasses de registros normalizados
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalizedInstanceRecord:
    """Fila normalizada de la tabla de instancias y muestras (`instances.tsv`)."""

    graph_id: str
    sample_id: str
    species: str
    gut_segment: str
    study_id: str
    scenario_id: str
    diet_treatment: str
    timepoint: str | None = None
    is_synthetic: bool = False
    source_id: str = "unknown"

    def __post_init__(self) -> None:
        if not self.graph_id:
            raise ValueError("graph_id no puede estar vacio.")
        if not self.sample_id:
            raise ValueError("sample_id no puede estar vacio.")
        if self.species not in ALLOWED_SPECIES:
            raise ValueError(
                f"Especie '{self.species}' no valida. Permitidas: {ALLOWED_SPECIES}"
            )
        if self.gut_segment not in ALLOWED_GUT_SEGMENTS:
            raise ValueError(
                f"Segmento '{self.gut_segment}' no valido. Permitidos: {ALLOWED_GUT_SEGMENTS}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serializa a diccionario."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> NormalizedInstanceRecord:
        """Crea el registro validando los campos obligatorios."""
        return cls(
            graph_id=data["graph_id"],
            sample_id=data["sample_id"],
            species=data["species"],
            gut_segment=data["gut_segment"],
            study_id=data["study_id"],
            scenario_id=data["scenario_id"],
            diet_treatment=data["diet_treatment"],
            timepoint=data.get("timepoint", None),
            is_synthetic=data.get("is_synthetic", False),
            source_id=data.get("source_id", "unknown"),
        )


@dataclass(frozen=True)
class NormalizedFeatureRecord:
    """Fila normalizada de la tabla de entidades y atributos (`features.tsv`).

    Representa la medicion numerica de una variable asociada a un nodo para
    un grafo/muestra concreto.
    """

    graph_id: str
    node_id: str
    node_type: str
    feature_name: str
    value: float
    unit: str
    quality_flag: str = "valid"
    raw_id: str | None = None
    source_id: str = "unknown"

    def __post_init__(self) -> None:
        if not self.graph_id:
            raise ValueError("graph_id no puede estar vacio.")
        if not self.node_id:
            raise ValueError("node_id no puede estar vacio.")
        if self.node_type not in ALLOWED_NODE_TYPES:
            raise ValueError(
                f"node_type '{self.node_type}' no valido. Permitidos: {ALLOWED_NODE_TYPES}"
            )
        if not math.isfinite(self.value):
            raise ValueError(f"El valor '{self.value}' debe ser un numero finito.")
        if self.unit not in CANONICAL_UNITS:
            raise ValueError(f"unit '{self.unit}' no es una unidad canonica. Permitidas: {CANONICAL_UNITS}")
        if self.quality_flag not in ALLOWED_QUALITY_FLAGS:
            raise ValueError(
                f"quality_flag '{self.quality_flag}' no permitido. Permitidos: {ALLOWED_QUALITY_FLAGS}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serializa a diccionario."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> NormalizedFeatureRecord:
        """Crea el registro validando tipos y numeros finitos."""
        value = data["value"]
        if not isinstance(value, (int, float)):
            raise TypeError("value debe ser numerico.")
        return cls(
            graph_id=data["graph_id"],
            node_id=data["node_id"],
            node_type=data["node_type"],
            feature_name=data["feature_name"],
            value=float(value),
            unit=data["unit"],
            quality_flag=data.get("quality_flag", "valid"),
            raw_id=data.get("raw_id", None),
            source_id=data.get("source_id", "unknown"),
        )


@dataclass(frozen=True)
class NormalizedEdgeRecord:
    """Fila normalizada de la tabla de aristas e interacciones (`edges.tsv`)."""

    graph_id: str
    src_id: str
    src_type: str
    relation_type: str
    dst_id: str
    dst_type: str
    weight: float = 1.0
    evidence_status: str = "inferred"
    source_id: str = "unknown"

    def __post_init__(self) -> None:
        if not self.graph_id:
            raise ValueError("graph_id no puede estar vacio.")
        if not self.src_id or not self.dst_id:
            raise ValueError("src_id y dst_id no pueden estar vacios.")
        if self.src_type not in ALLOWED_NODE_TYPES:
            raise ValueError(f"src_type '{self.src_type}' no es un tipo de nodo permitido.")
        if self.dst_type not in ALLOWED_NODE_TYPES:
            raise ValueError(f"dst_type '{self.dst_type}' no es un tipo de nodo permitido.")
        if self.relation_type not in ALLOWED_RELATION_TYPES:
            raise ValueError(f"relation_type '{self.relation_type}' no permitido.")
        if self.evidence_status not in ALLOWED_EVIDENCE_STATUSES:
            raise ValueError(f"evidence_status '{self.evidence_status}' no permitido.")
        if not math.isfinite(self.weight):
            raise ValueError(f"weight '{self.weight}' debe ser un numero finito.")

    def to_dict(self) -> dict[str, Any]:
        """Serializa a diccionario."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> NormalizedEdgeRecord:
        """Crea el registro validando los extremos y el peso."""
        weight = data.get("weight", 1.0)
        return cls(
            graph_id=data["graph_id"],
            src_id=data["src_id"],
            src_type=data["src_type"],
            relation_type=data["relation_type"],
            dst_id=data["dst_id"],
            dst_type=data["dst_type"],
            weight=float(weight),
            evidence_status=data.get("evidence_status", "inferred"),
            source_id=data.get("source_id", "unknown"),
        )


@dataclass(frozen=True)
class NormalizedTargetRecord:
    """Fila normalizada de la tabla de variables objetivo (`targets.tsv`)."""

    graph_id: str
    target_type: str
    target_id: str
    value: float
    unit: str
    sample_matrix: str
    measured_or_predicted: str
    source_id: str = "unknown"

    def __post_init__(self) -> None:
        if not self.graph_id:
            raise ValueError("graph_id no puede estar vacio.")
        if not self.target_id:
            raise ValueError("target_id no puede estar vacio.")
        if self.target_type not in ALLOWED_TARGET_TYPES:
            raise ValueError(f"target_type '{self.target_type}' no permitido.")
        if self.measured_or_predicted not in ALLOWED_MEASUREMENT_KINDS:
            raise ValueError(f"measured_or_predicted '{self.measured_or_predicted}' no permitido.")
        if self.unit not in CANONICAL_UNITS:
            raise ValueError(f"unit '{self.unit}' no es una unidad canonica. Permitidas: {CANONICAL_UNITS}")
        if not math.isfinite(self.value):
            raise ValueError(f"value '{self.value}' debe ser un numero finito.")

    def to_dict(self) -> dict[str, Any]:
        """Serializa a diccionario."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> NormalizedTargetRecord:
        """Crea el registro validando target_type y tipos."""
        return cls(
            graph_id=data["graph_id"],
            target_type=data["target_type"],
            target_id=data["target_id"],
            value=float(data["value"]),
            unit=data["unit"],
            sample_matrix=data["sample_matrix"],
            measured_or_predicted=data["measured_or_predicted"],
            source_id=data.get("source_id", "unknown"),
        )


@dataclass
class NormalizedTabularDataset:
    """Contenedor de salida del modulo de datos en formato tabular normalizado.

    Alberga las tablas de instancias, caracteristicas de nodos, aristas y targets
    garantizando coherencia referencial entre graph_id y entidades.
    """

    metadata: dict[str, Any] = field(default_factory=dict)
    instances: list[NormalizedInstanceRecord] = field(default_factory=list)
    features: list[NormalizedFeatureRecord] = field(default_factory=list)
    edges: list[NormalizedEdgeRecord] = field(default_factory=list)
    targets: list[NormalizedTargetRecord] = field(default_factory=list)

    def validate(self) -> list[str]:
        """Verifica la integridad referencial y detecta inconsistencias."""
        errors: list[str] = []
        known_graph_ids = {inst.graph_id for inst in self.instances}

        for i, feat in enumerate(self.features):
            if feat.graph_id not in known_graph_ids:
                errors.append(
                    f"Feature #{i}: graph_id '{feat.graph_id}' no existe en la tabla de instancias."
                )

        for i, edge in enumerate(self.edges):
            if edge.graph_id not in known_graph_ids:
                errors.append(
                    f"Edge #{i}: graph_id '{edge.graph_id}' no existe en la tabla de instancias."
                )

        for i, target in enumerate(self.targets):
            if target.graph_id not in known_graph_ids:
                errors.append(
                    f"Target #{i}: graph_id '{target.graph_id}' no existe en la tabla de instancias."
                )

        return errors

    def to_dict(self) -> dict[str, Any]:
        """Serializa todas las tablas a un diccionario estructurado."""
        return {
            "metadata": self.metadata,
            "instances": [r.to_dict() for r in self.instances],
            "features": [r.to_dict() for r in self.features],
            "edges": [r.to_dict() for r in self.edges],
            "targets": [r.to_dict() for r in self.targets],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> NormalizedTabularDataset:
        """Reconstruye el dataset desde un diccionario."""
        return cls(
            metadata=dict(data.get("metadata", {})),
            instances=[NormalizedInstanceRecord.from_dict(r) for r in data.get("instances", [])],
            features=[NormalizedFeatureRecord.from_dict(r) for r in data.get("features", [])],
            edges=[NormalizedEdgeRecord.from_dict(r) for r in data.get("edges", [])],
            targets=[NormalizedTargetRecord.from_dict(r) for r in data.get("targets", [])],
        )

    def export_tables(
        self, output_dir: Path | str, format: str = "tsv"
    ) -> dict[str, Path]:
        """Exporta las tablas normalizadas a archivos delimitados (TSV o CSV)."""
        import csv

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        delimiter = "\t" if format == "tsv" else ","
        ext = format if format in ("tsv", "csv") else "csv"
        exported: dict[str, Path] = {}

        meta_path = out / "metadata.json"
        with open(meta_path, mode="w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2)
        exported["metadata"] = meta_path

        table_map = [
            (f"instances.{ext}", self.instances),
            (f"features.{ext}", self.features),
            (f"edges.{ext}", self.edges),
            (f"targets.{ext}", self.targets),
        ]

        for filename, records in table_map:
            path = out / filename
            if not records:
                path.write_text("", encoding="utf-8")
                exported[filename.split(".")[0]] = path
                continue
            rows = [r.to_dict() for r in records]
            with open(path, mode="w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=delimiter)
                writer.writeheader()
                writer.writerows(rows)
            exported[filename.split(".")[0]] = path

        return exported
