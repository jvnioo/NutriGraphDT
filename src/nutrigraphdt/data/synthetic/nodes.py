"""Modelos de nodos sintéticos y generador para NutriGraphDT (DS-02).

Este módulo implementa el generador de nodos sintéticos cumpliendo con el contrato
de datos definido en `docs/synthetic-dataset-spec.md` y el Esquema General del
proyecto Microbioma Digital (`Esquema_General_del_proyecto_Microbioma_Digital.md`).
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, TypedDict


class NodeType(StrEnum):
    """Tipos canónicos de nodo para el grafo heterogéneo gastrointestinal."""

    DIET = "diet"
    ADDITIVE = "additive"
    SUBSTRATE = "substrate"
    TAXON = "taxon"
    FUNCTION = "function"
    METABOLITE = "metabolite"
    HOST = "host"
    PHENOTYPE = "phenotype"


@dataclass(frozen=True)
class CompositionItem:
    """Componente nutricional individual en la composición de una dieta."""

    component_id: str
    value: float
    unit: str

    def to_dict(self) -> dict[str, Any]:
        """Convierte el elemento de composición a diccionario."""
        return {
            "component_id": self.component_id,
            "value": self.value,
            "unit": self.unit,
        }


@dataclass(frozen=True)
class DietAttributes:
    """Atributos de dominio para nodos de tipo Dieta (D)."""

    name: str
    ingredients: list[str]
    composition: list[dict[str, Any]]
    source_version: str


@dataclass(frozen=True)
class AdditiveAttributes:
    """Atributos de dominio para nodos de tipo Aditivo (A)."""

    category: str
    substance: str
    dose: float
    dose_unit: str
    control_label: str


@dataclass(frozen=True)
class SubstrateAttributes:
    """Atributos de dominio para nodos de tipo Sustrato (S)."""

    chemical_id: str
    name: str
    quantity: float
    unit: str


@dataclass(frozen=True)
class TaxonAttributes:
    """Atributos de dominio para nodos de tipo Taxón / Gremio (T)."""

    taxonomy_id: str
    taxonomy_level: str
    abundance: float
    abundance_unit: str
    quantification_method: str


@dataclass(frozen=True)
class FunctionAttributes:
    """Atributos de dominio para nodos de tipo Función / Ruta (F)."""

    function_id: str
    function_type: str
    annotation_source: str
    annotation_value: float
    annotation_value_type: str
    unit: str


@dataclass(frozen=True)
class MetaboliteAttributes:
    """Atributos de dominio para nodos de tipo Metabolito (M)."""

    chemical_id: str
    name: str
    sample_matrix: str
    concentration: float
    unit: str


@dataclass(frozen=True)
class HostAttributes:
    """Atributos de dominio para nodos de tipo Huésped (H)."""

    species: str
    gut_segment: str
    cohort_id: str
    covariates: dict[str, Any]


@dataclass(frozen=True)
class PhenotypeAttributes:
    """Atributos de dominio para nodos de tipo Fenotipo (P)."""

    trait: str
    timepoint: str
    value: float
    unit: str


@dataclass(frozen=True)
class Node:
    """Envoltorio común del contrato de nodo."""

    graph_id: str
    node_id: str
    node_type: str
    source_id: str
    attributes: dict[str, Any]
    missing_mask: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serializa el nodo a un diccionario compatible con el contrato JSON/JSONL."""
        return {
            "graph_id": self.graph_id,
            "node_id": self.node_id,
            "node_type": self.node_type,
            "source_id": self.source_id,
            "attributes": self.attributes,
            "missing_mask": self.missing_mask,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Node:
        """Construye una instancia de Node a partir de un diccionario."""
        return cls(
            graph_id=str(data["graph_id"]),
            node_id=str(data["node_id"]),
            node_type=str(data["node_type"]),
            source_id=str(data["source_id"]),
            attributes=dict(data.get("attributes", {})),
            missing_mask=dict(data.get("missing_mask", {})),
        )


@dataclass
class NodeCountConfig:
    """Cantidad configurable de nodos a generar por cada tipo de nodo."""

    diet: int = 1
    additive: int = 1
    substrate: int = 4
    taxon: int = 10
    function: int = 8
    metabolite: int = 5
    host: int = 1
    phenotype: int = 2

    def get_count(self, node_type: NodeType | str) -> int:
        """Obtiene la cantidad configurada para un tipo de nodo específico."""
        key = node_type.value if isinstance(node_type, NodeType) else str(node_type).lower()
        if hasattr(self, key):
            val = getattr(self, key)
            if isinstance(val, int):
                return val
        raise ValueError(f"Clave de conteo de tipo de nodo desconocida: '{key}'")


@dataclass
class SyntheticNodeConfig:
    """Configuración para la generación de nodos sintéticos."""

    graph_id: str = "synthetic:graph:0001"
    source_id: str = "SYNTHETIC_V1"
    species: str = "chicken"
    gut_segment: str = "cecum"
    cohort_id: str = "cohort_01"
    counts: NodeCountConfig = field(default_factory=NodeCountConfig)
    random_seed: int = 42


class _DietTemplate(TypedDict):
    name: str
    ingredients: list[str]
    composition: list[dict[str, Any]]
    source_version: str


class _AdditiveTemplate(TypedDict):
    category: str
    substance: str
    dose: float
    dose_unit: str
    control_label: str


class _SubstrateTemplate(TypedDict):
    chemical_id: str
    name: str
    quantity_range: tuple[float, float]
    unit: str


class _TaxonTemplate(TypedDict):
    taxonomy_id: str
    taxonomy_level: str
    name: str
    abundance_weight: float


class _FunctionTemplate(TypedDict):
    function_id: str
    function_type: str
    annotation_source: str
    name: str
    val_range: tuple[float, float]
    val_type: str
    unit: str


class _MetaboliteTemplate(TypedDict):
    chemical_id: str
    name: str
    sample_matrix: str
    conc_range: tuple[float, float]
    unit: str


class _PhenotypeTemplate(TypedDict):
    trait: str
    timepoint: str
    val_range: tuple[float, float]
    unit: str


# Catálogos de referencia para la generación realista de atributos sintéticos en español
_DIET_CATALOG: list[_DietTemplate] = [
    {
        "name": "Dieta basal estándar de maíz y harina de soya",
        "ingredients": [
            "corn",
            "soybean_meal",
            "wheat_middlings",
            "limestone",
            "salt",
            "vitamin_premix",
        ],
        "composition": [
            {"component_id": "crude_protein", "value": 215.0, "unit": "g/kg"},
            {"component_id": "crude_fiber", "value": 38.0, "unit": "g/kg"},
            {"component_id": "crude_fat", "value": 52.0, "unit": "g/kg"},
            {"component_id": "metabolizable_energy", "value": 12.8, "unit": "MJ/kg"},
            {"component_id": "calcium", "value": 9.5, "unit": "g/kg"},
            {"component_id": "total_phosphorus", "value": 6.8, "unit": "g/kg"},
        ],
        "source_version": "synthetic_diet_v1",
    },
    {
        "name": "Dieta de crecimiento basada en trigo y cebada",
        "ingredients": [
            "wheat",
            "barley",
            "soybean_meal",
            "sunflower_meal",
            "limestone",
            "premix",
        ],
        "composition": [
            {"component_id": "crude_protein", "value": 195.0, "unit": "g/kg"},
            {"component_id": "crude_fiber", "value": 46.0, "unit": "g/kg"},
            {"component_id": "crude_fat", "value": 44.0, "unit": "g/kg"},
            {"component_id": "metabolizable_energy", "value": 12.2, "unit": "MJ/kg"},
            {"component_id": "calcium", "value": 8.8, "unit": "g/kg"},
            {"component_id": "total_phosphorus", "value": 6.2, "unit": "g/kg"},
        ],
        "source_version": "synthetic_diet_v1",
    },
]

_ADDITIVE_CATALOG: list[_AdditiveTemplate] = [
    {
        "category": "probiotic",
        "substance": "Bacillus subtilis DSM 32315",
        "dose": 1.0e9,
        "dose_unit": "CFU/kg",
        "control_label": "supplemented",
    },
    {
        "category": "prebiotic",
        "substance": "Inulina / Fructooligosacáridos",
        "dose": 5000.0,
        "dose_unit": "mg/kg",
        "control_label": "supplemented",
    },
    {
        "category": "phytogenic",
        "substance": "Mezcla de aceites esenciales de timol y carvacrol",
        "dose": 150.0,
        "dose_unit": "mg/kg",
        "control_label": "supplemented",
    },
    {
        "category": "organic_acid",
        "substance": "Butirato de sodio encapsulado",
        "dose": 1000.0,
        "dose_unit": "mg/kg",
        "control_label": "supplemented",
    },
    {
        "category": "control",
        "substance": "Ninguno",
        "dose": 0.0,
        "dose_unit": "mg/kg",
        "control_label": "control_basal",
    },
]

_SUBSTRATE_CATALOG: list[_SubstrateTemplate] = [
    {
        "chemical_id": "synthetic:substrate:arabinoxylan",
        "name": "Arabinoxilano",
        "quantity_range": (15.0, 35.0),
        "unit": "g/kg",
    },
    {
        "chemical_id": "synthetic:substrate:resistant_starch",
        "name": "Almidón resistente",
        "quantity_range": (10.0, 25.0),
        "unit": "g/kg",
    },
    {
        "chemical_id": "synthetic:substrate:beta_glucan",
        "name": "Beta-glucano",
        "quantity_range": (5.0, 18.0),
        "unit": "g/kg",
    },
    {
        "chemical_id": "synthetic:substrate:cellulose",
        "name": "Celulosa",
        "quantity_range": (20.0, 45.0),
        "unit": "g/kg",
    },
    {
        "chemical_id": "synthetic:substrate:pectin",
        "name": "Pectina",
        "quantity_range": (4.0, 12.0),
        "unit": "g/kg",
    },
    {
        "chemical_id": "synthetic:substrate:mucin_glycans",
        "name": "O-glicanos de mucina",
        "quantity_range": (2.0, 8.0),
        "unit": "g/kg",
    },
    {
        "chemical_id": "synthetic:substrate:inulin",
        "name": "Inulina",
        "quantity_range": (3.0, 15.0),
        "unit": "g/kg",
    },
    {
        "chemical_id": "synthetic:substrate:xylooligosaccharides",
        "name": "Xilooligosacáridos",
        "quantity_range": (2.0, 10.0),
        "unit": "g/kg",
    },
]

_TAXON_CATALOG: list[_TaxonTemplate] = [
    {
        "taxonomy_id": "synthetic:taxon:bacteroides",
        "taxonomy_level": "genus",
        "name": "Bacteroides",
        "abundance_weight": 0.22,
    },
    {
        "taxonomy_id": "synthetic:taxon:faecalibacterium",
        "taxonomy_level": "genus",
        "name": "Faecalibacterium",
        "abundance_weight": 0.18,
    },
    {
        "taxonomy_id": "synthetic:taxon:lactobacillus",
        "taxonomy_level": "genus",
        "name": "Lactobacillus",
        "abundance_weight": 0.15,
    },
    {
        "taxonomy_id": "synthetic:taxon:ruminococcus",
        "taxonomy_level": "genus",
        "name": "Ruminococcus",
        "abundance_weight": 0.12,
    },
    {
        "taxonomy_id": "synthetic:taxon:clostridium_cluster_iv",
        "taxonomy_level": "clade",
        "name": "Clostridium cluster IV",
        "abundance_weight": 0.10,
    },
    {
        "taxonomy_id": "synthetic:taxon:akkermansia",
        "taxonomy_level": "genus",
        "name": "Akkermansia",
        "abundance_weight": 0.06,
    },
    {
        "taxonomy_id": "synthetic:taxon:bifidobacterium",
        "taxonomy_level": "genus",
        "name": "Bifidobacterium",
        "abundance_weight": 0.05,
    },
    {
        "taxonomy_id": "synthetic:taxon:prevotella",
        "taxonomy_level": "genus",
        "name": "Prevotella",
        "abundance_weight": 0.04,
    },
    {
        "taxonomy_id": "synthetic:taxon:roseburia",
        "taxonomy_level": "genus",
        "name": "Roseburia",
        "abundance_weight": 0.04,
    },
    {
        "taxonomy_id": "synthetic:taxon:escherichia_shigella",
        "taxonomy_level": "genus",
        "name": "Escherichia-Shigella",
        "abundance_weight": 0.02,
    },
    {
        "taxonomy_id": "synthetic:taxon:alaricibacter",
        "taxonomy_level": "genus",
        "name": "Alaricibacter",
        "abundance_weight": 0.01,
    },
    {
        "taxonomy_id": "synthetic:taxon:streptococcus",
        "taxonomy_level": "genus",
        "name": "Streptococcus",
        "abundance_weight": 0.01,
    },
]

_FUNCTION_CATALOG: list[_FunctionTemplate] = [
    {
        "function_id": "synthetic:function:ko00620",
        "function_type": "pathway",
        "annotation_source": "KEGG",
        "name": "Metabolismo del piruvato",
        "val_range": (80.0, 240.0),
        "val_type": "abundance",
        "unit": "CPM",
    },
    {
        "function_id": "synthetic:function:ko00640",
        "function_type": "pathway",
        "annotation_source": "KEGG",
        "name": "Metabolismo del propanoato",
        "val_range": (60.0, 190.0),
        "val_type": "abundance",
        "unit": "CPM",
    },
    {
        "function_id": "synthetic:function:ko00650",
        "function_type": "pathway",
        "annotation_source": "KEGG",
        "name": "Metabolismo del butanoato",
        "val_range": (75.0, 210.0),
        "val_type": "abundance",
        "unit": "CPM",
    },
    {
        "function_id": "synthetic:function:ec2.7.2.7",
        "function_type": "enzyme",
        "annotation_source": "MetaCyc",
        "name": "Butirato quinasa",
        "val_range": (20.0, 95.0),
        "val_type": "abundance",
        "unit": "CPM",
    },
    {
        "function_id": "synthetic:function:ec2.8.3.8",
        "function_type": "enzyme",
        "annotation_source": "MetaCyc",
        "name": "Acetato CoA-transferasa",
        "val_range": (30.0, 110.0),
        "val_type": "abundance",
        "unit": "CPM",
    },
    {
        "function_id": "synthetic:function:gh10",
        "function_type": "cazy_family",
        "annotation_source": "CAZy",
        "name": "Familia 10 de glicósido hidrolasa (endoxilanasa)",
        "val_range": (15.0, 70.0),
        "val_type": "abundance",
        "unit": "CPM",
    },
    {
        "function_id": "synthetic:function:gh13",
        "function_type": "cazy_family",
        "annotation_source": "CAZy",
        "name": "Familia 13 de glicósido hidrolasa (alfa-amilasa)",
        "val_range": (25.0, 85.0),
        "val_type": "abundance",
        "unit": "CPM",
    },
    {
        "function_id": "synthetic:function:buk",
        "function_type": "gene",
        "annotation_source": "EggNOG",
        "name": "Gen buk (butirato quinasa)",
        "val_range": (1.0, 1.0),
        "val_type": "presence",
        "unit": "binary",
    },
    {
        "function_id": "synthetic:function:ptb",
        "function_type": "gene",
        "annotation_source": "EggNOG",
        "name": "Gen ptb (fosfotransbutirilasa)",
        "val_range": (1.0, 1.0),
        "val_type": "presence",
        "unit": "binary",
    },
]

_METABOLITE_CATALOG: list[_MetaboliteTemplate] = [
    {
        "chemical_id": "synthetic:metabolite:acetate",
        "name": "Acetato",
        "sample_matrix": "cecal_content",
        "conc_range": (45.0, 85.0),
        "unit": "mmol/kg",
    },
    {
        "chemical_id": "synthetic:metabolite:propionate",
        "name": "Propionato",
        "sample_matrix": "cecal_content",
        "conc_range": (10.0, 30.0),
        "unit": "mmol/kg",
    },
    {
        "chemical_id": "synthetic:metabolite:butyrate",
        "name": "Butirato",
        "sample_matrix": "cecal_content",
        "conc_range": (8.0, 25.0),
        "unit": "mmol/kg",
    },
    {
        "chemical_id": "synthetic:metabolite:lactate",
        "name": "Lactato",
        "sample_matrix": "cecal_content",
        "conc_range": (2.0, 12.0),
        "unit": "mmol/kg",
    },
    {
        "chemical_id": "synthetic:metabolite:succinate",
        "name": "Succinato",
        "sample_matrix": "cecal_content",
        "conc_range": (1.0, 8.0),
        "unit": "mmol/kg",
    },
    {
        "chemical_id": "synthetic:metabolite:valerate",
        "name": "Valerato",
        "sample_matrix": "cecal_content",
        "conc_range": (0.5, 4.0),
        "unit": "mmol/kg",
    },
]

_PHENOTYPE_CATALOG: list[_PhenotypeTemplate] = [
    {
        "trait": "feed_conversion_ratio",
        "timepoint": "day_42",
        "val_range": (1.38, 1.65),
        "unit": "ratio",
    },
    {
        "trait": "body_weight_gain",
        "timepoint": "day_42",
        "val_range": (2200.0, 2850.0),
        "unit": "g",
    },
    {
        "trait": "cecal_scfa_total",
        "timepoint": "day_42",
        "val_range": (70.0, 140.0),
        "unit": "mmol/kg",
    },
    {
        "trait": "gut_permeability_fitc",
        "timepoint": "day_42",
        "val_range": (0.12, 0.45),
        "unit": "ug/mL",
    },
]


class SyntheticNodeGenerator:
    """Generador determinista de nodos sintéticos para el grafo."""

    def __init__(self, config: SyntheticNodeConfig | None = None) -> None:
        """Inicializa el generador con la configuración suministrada."""
        self.config = config or SyntheticNodeConfig()
        self.rng = random.Random(self.config.random_seed)

    def generate_diet_nodes(self, count: int | None = None) -> list[Node]:
        """Genera nodos de tipo Dieta (D)."""
        n = self.config.counts.diet if count is None else count
        nodes: list[Node] = []
        for i in range(n):
            node_id = f"synthetic:diet:{i + 1:04d}"
            catalog_entry = _DIET_CATALOG[i % len(_DIET_CATALOG)]
            # Ajuste de composición para varianza controlada si count > tamaño catálogo
            composition: list[dict[str, Any]] = [
                {
                    "component_id": str(item["component_id"]),
                    "value": round(
                        float(item["value"]) * (1.0 + (i // len(_DIET_CATALOG)) * 0.05),
                        3,
                    ),
                    "unit": str(item["unit"]),
                }
                for item in catalog_entry["composition"]
            ]
            variation_suffix = f" Var {i + 1}" if i >= len(_DIET_CATALOG) else ""
            attrs = DietAttributes(
                name=f"{catalog_entry['name']}{variation_suffix}",
                ingredients=list(catalog_entry["ingredients"]),
                composition=composition,
                source_version=str(catalog_entry["source_version"]),
            )
            nodes.append(
                Node(
                    graph_id=self.config.graph_id,
                    node_id=node_id,
                    node_type=NodeType.DIET.value,
                    source_id=self.config.source_id,
                    attributes=asdict(attrs),
                    missing_mask={},
                )
            )
        return nodes

    def generate_additive_nodes(self, count: int | None = None) -> list[Node]:
        """Genera nodos de tipo Aditivo (A)."""
        n = self.config.counts.additive if count is None else count
        nodes: list[Node] = []
        for i in range(n):
            node_id = f"synthetic:additive:{i + 1:04d}"
            entry = _ADDITIVE_CATALOG[i % len(_ADDITIVE_CATALOG)]
            attrs = AdditiveAttributes(
                category=str(entry["category"]),
                substance=str(entry["substance"]),
                dose=float(entry["dose"]),
                dose_unit=str(entry["dose_unit"]),
                control_label=str(entry["control_label"]),
            )
            nodes.append(
                Node(
                    graph_id=self.config.graph_id,
                    node_id=node_id,
                    node_type=NodeType.ADDITIVE.value,
                    source_id=self.config.source_id,
                    attributes=asdict(attrs),
                    missing_mask={},
                )
            )
        return nodes

    def generate_substrate_nodes(self, count: int | None = None) -> list[Node]:
        """Genera nodos de tipo Sustrato (S)."""
        n = self.config.counts.substrate if count is None else count
        nodes: list[Node] = []
        for i in range(n):
            node_id = f"synthetic:substrate:{i + 1:04d}"
            entry = _SUBSTRATE_CATALOG[i % len(_SUBSTRATE_CATALOG)]
            low, high = entry["quantity_range"]
            quantity = round(self.rng.uniform(low, high), 3)
            chemical_id = (
                f"{entry['chemical_id']}_{i + 1:02d}"
                if i >= len(_SUBSTRATE_CATALOG)
                else str(entry["chemical_id"])
            )
            attrs = SubstrateAttributes(
                chemical_id=chemical_id,
                name=str(entry["name"]),
                quantity=quantity,
                unit=str(entry["unit"]),
            )
            nodes.append(
                Node(
                    graph_id=self.config.graph_id,
                    node_id=node_id,
                    node_type=NodeType.SUBSTRATE.value,
                    source_id=self.config.source_id,
                    attributes=asdict(attrs),
                    missing_mask={},
                )
            )
        return nodes

    def generate_taxon_nodes(self, count: int | None = None) -> list[Node]:
        """Genera nodos de tipo Taxón / Gremio (T) con abundancias relativas normalizadas."""
        n = self.config.counts.taxon if count is None else count
        if n == 0:
            return []

        # Genera abundancias Dirichlet/gamma normalizadas para sumar 1.0
        raw_abundances = [self.rng.gammavariate(2.0, 1.0) for _ in range(n)]
        total_abundance = sum(raw_abundances)
        normalized_abundances = [round(a / total_abundance, 6) for a in raw_abundances]

        nodes: list[Node] = []
        for i in range(n):
            node_id = f"synthetic:taxon:{i + 1:04d}"
            entry = _TAXON_CATALOG[i % len(_TAXON_CATALOG)]
            taxonomy_id = (
                f"{entry['taxonomy_id']}_{i + 1:02d}"
                if i >= len(_TAXON_CATALOG)
                else str(entry["taxonomy_id"])
            )
            attrs = TaxonAttributes(
                taxonomy_id=taxonomy_id,
                taxonomy_level=str(entry["taxonomy_level"]),
                abundance=normalized_abundances[i],
                abundance_unit="relative_abundance",
                quantification_method="16S_amplicon",
            )
            nodes.append(
                Node(
                    graph_id=self.config.graph_id,
                    node_id=node_id,
                    node_type=NodeType.TAXON.value,
                    source_id=self.config.source_id,
                    attributes=asdict(attrs),
                    missing_mask={},
                )
            )
        return nodes

    def generate_function_nodes(self, count: int | None = None) -> list[Node]:
        """Genera nodos de tipo Función / Ruta (F)."""
        n = self.config.counts.function if count is None else count
        nodes: list[Node] = []
        for i in range(n):
            node_id = f"synthetic:function:{i + 1:04d}"
            entry = _FUNCTION_CATALOG[i % len(_FUNCTION_CATALOG)]
            low, high = entry["val_range"]
            val_type = str(entry["val_type"])
            annotation_val = (
                1.0 if val_type == "presence" else round(self.rng.uniform(low, high), 3)
            )
            function_id = (
                f"{entry['function_id']}_{i + 1:02d}"
                if i >= len(_FUNCTION_CATALOG)
                else str(entry["function_id"])
            )
            attrs = FunctionAttributes(
                function_id=function_id,
                function_type=str(entry["function_type"]),
                annotation_source=str(entry["annotation_source"]),
                annotation_value=annotation_val,
                annotation_value_type=val_type,
                unit=str(entry["unit"]),
            )
            nodes.append(
                Node(
                    graph_id=self.config.graph_id,
                    node_id=node_id,
                    node_type=NodeType.FUNCTION.value,
                    source_id=self.config.source_id,
                    attributes=asdict(attrs),
                    missing_mask={},
                )
            )
        return nodes

    def generate_metabolite_nodes(self, count: int | None = None) -> list[Node]:
        """Genera nodos de tipo Metabolito (M)."""
        n = self.config.counts.metabolite if count is None else count
        nodes: list[Node] = []
        for i in range(n):
            node_id = f"synthetic:metabolite:{i + 1:04d}"
            entry = _METABOLITE_CATALOG[i % len(_METABOLITE_CATALOG)]
            low, high = entry["conc_range"]
            conc = round(self.rng.uniform(low, high), 3)
            chemical_id = (
                f"{entry['chemical_id']}_{i + 1:02d}"
                if i >= len(_METABOLITE_CATALOG)
                else str(entry["chemical_id"])
            )
            attrs = MetaboliteAttributes(
                chemical_id=chemical_id,
                name=str(entry["name"]),
                sample_matrix=str(entry["sample_matrix"]),
                concentration=conc,
                unit=str(entry["unit"]),
            )
            nodes.append(
                Node(
                    graph_id=self.config.graph_id,
                    node_id=node_id,
                    node_type=NodeType.METABOLITE.value,
                    source_id=self.config.source_id,
                    attributes=asdict(attrs),
                    missing_mask={},
                )
            )
        return nodes

    def generate_host_nodes(self, count: int | None = None) -> list[Node]:
        """Genera nodos de tipo Huésped (H)."""
        n = self.config.counts.host if count is None else count
        nodes: list[Node] = []
        for i in range(n):
            node_id = f"synthetic:host:{i + 1:04d}"
            age = self.rng.choice([21, 28, 35, 42])
            sex = self.rng.choice(["male", "female", "mixed"])
            weight = round(self.rng.uniform(1200.0, 2600.0), 1)
            cohort_suffix = f"_{i + 1:02d}" if n > 1 else ""
            attrs = HostAttributes(
                species=self.config.species,
                gut_segment=self.config.gut_segment,
                cohort_id=f"{self.config.cohort_id}{cohort_suffix}",
                covariates={
                    "age_days": age,
                    "sex": sex,
                    "body_weight_g": weight,
                },
            )
            nodes.append(
                Node(
                    graph_id=self.config.graph_id,
                    node_id=node_id,
                    node_type=NodeType.HOST.value,
                    source_id=self.config.source_id,
                    attributes=asdict(attrs),
                    missing_mask={},
                )
            )
        return nodes

    def generate_phenotype_nodes(self, count: int | None = None) -> list[Node]:
        """Genera nodos de tipo Fenotipo (P)."""
        n = self.config.counts.phenotype if count is None else count
        nodes: list[Node] = []
        for i in range(n):
            node_id = f"synthetic:phenotype:{i + 1:04d}"
            entry = _PHENOTYPE_CATALOG[i % len(_PHENOTYPE_CATALOG)]
            low, high = entry["val_range"]
            val = round(self.rng.uniform(low, high), 3)
            trait = (
                f"{entry['trait']}_{i + 1:02d}"
                if i >= len(_PHENOTYPE_CATALOG)
                else str(entry["trait"])
            )
            attrs = PhenotypeAttributes(
                trait=trait,
                timepoint=str(entry["timepoint"]),
                value=val,
                unit=str(entry["unit"]),
            )
            nodes.append(
                Node(
                    graph_id=self.config.graph_id,
                    node_id=node_id,
                    node_type=NodeType.PHENOTYPE.value,
                    source_id=self.config.source_id,
                    attributes=asdict(attrs),
                    missing_mask={},
                )
            )
        return nodes

    def generate_all_nodes(self) -> list[Node]:
        """Genera todos los nodos sintéticos configurados para la instancia del grafo."""
        all_nodes: list[Node] = []
        all_nodes.extend(self.generate_diet_nodes())
        all_nodes.extend(self.generate_additive_nodes())
        all_nodes.extend(self.generate_substrate_nodes())
        all_nodes.extend(self.generate_taxon_nodes())
        all_nodes.extend(self.generate_function_nodes())
        all_nodes.extend(self.generate_metabolite_nodes())
        all_nodes.extend(self.generate_host_nodes())
        all_nodes.extend(self.generate_phenotype_nodes())
        return all_nodes

    def generate_nodes_by_type(self) -> dict[str, list[Node]]:
        """Genera todos los nodos sintéticos configurados agrupados por tipo de nodo."""
        return {
            NodeType.DIET.value: self.generate_diet_nodes(),
            NodeType.ADDITIVE.value: self.generate_additive_nodes(),
            NodeType.SUBSTRATE.value: self.generate_substrate_nodes(),
            NodeType.TAXON.value: self.generate_taxon_nodes(),
            NodeType.FUNCTION.value: self.generate_function_nodes(),
            NodeType.METABOLITE.value: self.generate_metabolite_nodes(),
            NodeType.HOST.value: self.generate_host_nodes(),
            NodeType.PHENOTYPE.value: self.generate_phenotype_nodes(),
        }


def generate_synthetic_nodes(config: SyntheticNodeConfig | None = None) -> list[Node]:
    """Función utilitaria de alto nivel para generar nodos sintéticos."""
    generator = SyntheticNodeGenerator(config)
    return generator.generate_all_nodes()
