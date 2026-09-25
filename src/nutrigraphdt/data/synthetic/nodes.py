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
        values: dict[str, str] = {}
        for name in ("graph_id", "node_id", "node_type", "source_id"):
            value = data[name]
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"El campo '{name}' debe ser una cadena no vacía; se recibió {value!r}."
                )
            values[name] = value

        attributes = data["attributes"]
        if not isinstance(attributes, dict):
            raise ValueError(
                f"El campo 'attributes' debe ser un objeto; se recibió {attributes!r}."
            )

        missing_mask = data.get("missing_mask", {})
        if not isinstance(missing_mask, dict):
            raise ValueError(
                f"El campo 'missing_mask' debe ser un objeto; se recibió {missing_mask!r}."
            )

        return cls(
            **values,
            attributes=dict(attributes),
            missing_mask=dict(missing_mask),
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
class SyntheticRangeConfig:
    """Rangos absolutos para los valores generados por tipo de nodo.

    Todos los límites son convenciones sintéticas; no representan valores
    fisiológicos ni experimentales reales.  Modifique estos campos para
    ajustar la escala de los datos generados sin tocar el código del generador.
    """

    # Sustratos (g/kg, convención sintética)
    substrate_quantity_low: float = 1.0
    substrate_quantity_high: float = 50.0

    # Funciones / rutas — abundancia (CPM, convención sintética)
    function_abundance_low: float = 1.0
    function_abundance_high: float = 300.0

    # Metabolitos — concentración (mmol/kg, convención sintética)
    metabolite_conc_low: float = 0.1
    metabolite_conc_high: float = 100.0

    # Fenotipos — valor numérico (escala adimensional, convención sintética)
    phenotype_value_low: float = 0.0
    phenotype_value_high: float = 1.0

    # Huésped — peso corporal (g, convención sintética)
    host_body_weight_low: float = 500.0
    host_body_weight_high: float = 3500.0

    # Taxones — parámetros de la distribución Gamma para abundancias relativas
    # (convención sintética; alpha > 1 produce distribución unimodal)
    taxon_gamma_alpha: float = 2.0
    taxon_gamma_beta: float = 1.0


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
    timepoint_days: int = 42
    ranges: SyntheticRangeConfig = field(default_factory=SyntheticRangeConfig)


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
        # Nombre sintético — no corresponde a ninguna cepa comercial registrada.
        "substance": "Bacillus sp. SYN-PRO-001",
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

# quantity_range: rango relativo [0, 1] que se escala con SyntheticRangeConfig.
# Los extremos marcan la posición proporcional dentro del rango absoluto configurado.
_SUBSTRATE_CATALOG: list[_SubstrateTemplate] = [
    {
        "chemical_id": "synthetic:substrate:arabinoxylan",
        "name": "Arabinoxilano",
        "quantity_range": (0.28, 0.69),
        "unit": "g/kg",
    },
    {
        "chemical_id": "synthetic:substrate:resistant_starch",
        "name": "Almidón resistente",
        "quantity_range": (0.18, 0.49),
        "unit": "g/kg",
    },
    {
        "chemical_id": "synthetic:substrate:beta_glucan",
        "name": "Beta-glucano",
        "quantity_range": (0.08, 0.35),
        "unit": "g/kg",
    },
    {
        "chemical_id": "synthetic:substrate:cellulose",
        "name": "Celulosa",
        "quantity_range": (0.38, 0.88),
        "unit": "g/kg",
    },
    {
        "chemical_id": "synthetic:substrate:pectin",
        "name": "Pectina",
        "quantity_range": (0.06, 0.22),
        "unit": "g/kg",
    },
    {
        "chemical_id": "synthetic:substrate:mucin_glycans",
        "name": "O-glicanos de mucina",
        "quantity_range": (0.02, 0.14),
        "unit": "g/kg",
    },
    {
        "chemical_id": "synthetic:substrate:inulin",
        "name": "Inulina",
        "quantity_range": (0.04, 0.29),
        "unit": "g/kg",
    },
    {
        "chemical_id": "synthetic:substrate:xylooligosaccharides",
        "name": "Xilooligosacáridos",
        "quantity_range": (0.02, 0.18),
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
        # Género sintético: «Alaricibacter» no pudo verificarse como género válido.
        "taxonomy_id": "synthetic:taxon:syntheticobacter_a",
        "taxonomy_level": "genus",
        "name": "Syntheticobacter sp. A",
        "abundance_weight": 0.01,
    },
    {
        "taxonomy_id": "synthetic:taxon:streptococcus",
        "taxonomy_level": "genus",
        "name": "Streptococcus",
        "abundance_weight": 0.01,
    },
]

# Nota: todos los annotation_source, function_id y nombres de esta sección son
# puramente sintéticos y no corresponden a ninguna entrada real en bases de datos
# como KEGG, MetaCyc, CAZy o EggNOG.
# val_range: rango relativo [0, 1] escalado con SyntheticRangeConfig.function_abundance_*.
# Las entradas con val_type="presence" usan siempre val_range=(1.0, 1.0) (valor fijo).
_FUNCTION_CATALOG: list[_FunctionTemplate] = [
    {
        "function_id": "synthetic:annotation:pathway_a",
        "function_type": "pathway",
        "annotation_source": "synthetic:annotation:source_a",
        "name": "Metabolismo del piruvato (sintético)",
        "val_range": (0.26, 0.80),
        "val_type": "abundance",
        "unit": "CPM",
    },
    {
        "function_id": "synthetic:annotation:pathway_b",
        "function_type": "pathway",
        "annotation_source": "synthetic:annotation:source_a",
        "name": "Metabolismo del propanoato (sintético)",
        "val_range": (0.20, 0.63),
        "val_type": "abundance",
        "unit": "CPM",
    },
    {
        "function_id": "synthetic:annotation:pathway_c",
        "function_type": "pathway",
        "annotation_source": "synthetic:annotation:source_a",
        "name": "Metabolismo del butanoato (sintético)",
        "val_range": (0.25, 0.70),
        "val_type": "abundance",
        "unit": "CPM",
    },
    {
        "function_id": "synthetic:annotation:enzyme_a",
        "function_type": "enzyme",
        "annotation_source": "synthetic:annotation:source_b",
        "name": "Enzima sintética A (butirato quinasa)",
        "val_range": (0.06, 0.31),
        "val_type": "abundance",
        "unit": "CPM",
    },
    {
        "function_id": "synthetic:annotation:enzyme_b",
        "function_type": "enzyme",
        "annotation_source": "synthetic:annotation:source_b",
        "name": "Enzima sintética B (CoA-transferasa)",
        "val_range": (0.10, 0.37),
        "val_type": "abundance",
        "unit": "CPM",
    },
    {
        "function_id": "synthetic:annotation:gh_family_a",
        "function_type": "gh_family",
        "annotation_source": "synthetic:annotation:source_c",
        "name": "Familia glicósido hidrolasa A (sintética, endoxilanasa)",
        "val_range": (0.05, 0.23),
        "val_type": "abundance",
        "unit": "CPM",
    },
    {
        "function_id": "synthetic:annotation:gh_family_b",
        "function_type": "gh_family",
        "annotation_source": "synthetic:annotation:source_c",
        "name": "Familia glicósido hidrolasa B (sintética, alfa-amilasa)",
        "val_range": (0.08, 0.28),
        "val_type": "abundance",
        "unit": "CPM",
    },
    {
        "function_id": "synthetic:annotation:gene_a",
        "function_type": "gene",
        "annotation_source": "synthetic:annotation:source_d",
        "name": "Gen sintético A (butirato quinasa)",
        "val_range": (1.0, 1.0),
        "val_type": "presence",
        "unit": "binary",
    },
    {
        "function_id": "synthetic:annotation:gene_b",
        "function_type": "gene",
        "annotation_source": "synthetic:annotation:source_d",
        "name": "Gen sintético B (fosfotransbutirilasa)",
        "val_range": (1.0, 1.0),
        "val_type": "presence",
        "unit": "binary",
    },
]

# conc_range: rango relativo [0, 1] escalado con SyntheticRangeConfig.metabolite_conc_*.
_METABOLITE_CATALOG: list[_MetaboliteTemplate] = [
    {
        "chemical_id": "synthetic:metabolite:acetate",
        "name": "Acetato",
        "sample_matrix": "cecal_content",
        "conc_range": (0.44, 0.85),
        "unit": "mmol/kg",
    },
    {
        "chemical_id": "synthetic:metabolite:propionate",
        "name": "Propionato",
        "sample_matrix": "cecal_content",
        "conc_range": (0.10, 0.30),
        "unit": "mmol/kg",
    },
    {
        "chemical_id": "synthetic:metabolite:butyrate",
        "name": "Butirato",
        "sample_matrix": "cecal_content",
        "conc_range": (0.08, 0.25),
        "unit": "mmol/kg",
    },
    {
        "chemical_id": "synthetic:metabolite:lactate",
        "name": "Lactato",
        "sample_matrix": "cecal_content",
        "conc_range": (0.02, 0.12),
        "unit": "mmol/kg",
    },
    {
        "chemical_id": "synthetic:metabolite:succinate",
        "name": "Succinato",
        "sample_matrix": "cecal_content",
        "conc_range": (0.01, 0.08),
        "unit": "mmol/kg",
    },
    {
        "chemical_id": "synthetic:metabolite:valerate",
        "name": "Valerato",
        "sample_matrix": "cecal_content",
        "conc_range": (0.005, 0.04),
        "unit": "mmol/kg",
    },
]

# val_range: rango relativo [0, 1] escalado con SyntheticRangeConfig.phenotype_value_*.
# Los límites absolutos son convención sintética; no representan umbrales clínicos.
_PHENOTYPE_CATALOG: list[_PhenotypeTemplate] = [
    {
        "trait": "feed_conversion_ratio",
        "timepoint": "day_42",
        "val_range": (0.35, 0.65),
        "unit": "ratio",
    },
    {
        "trait": "body_weight_gain",
        "timepoint": "day_42",
        "val_range": (0.50, 0.85),
        "unit": "g",
    },
    {
        "trait": "cecal_scfa_total",
        "timepoint": "day_42",
        "val_range": (0.20, 0.60),
        "unit": "mmol/kg",
    },
    {
        "trait": "gut_permeability_fitc",
        "timepoint": "day_42",
        "val_range": (0.10, 0.45),
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
        seed_str = f"{self.config.random_seed}|{self.config.graph_id}|{NodeType.SUBSTRATE.value}"
        rng = random.Random(seed_str)
        r = self.config.ranges
        nodes: list[Node] = []
        for i in range(n):
            node_id = f"synthetic:substrate:{i + 1:04d}"
            entry = _SUBSTRATE_CATALOG[i % len(_SUBSTRATE_CATALOG)]
            # Escalar el rango relativo al rango absoluto configurado
            rel_low, rel_high = entry["quantity_range"]
            abs_span = r.substrate_quantity_high - r.substrate_quantity_low
            low = r.substrate_quantity_low + rel_low * abs_span
            high = r.substrate_quantity_low + rel_high * abs_span
            quantity = round(rng.uniform(low, high), 3)
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

        seed_str = f"{self.config.random_seed}|{self.config.graph_id}|{NodeType.TAXON.value}"
        rng = random.Random(seed_str)
        # Genera abundancias Dirichlet/gamma normalizadas para sumar 1.0.
        # Los parámetros alpha y beta son convención sintética configurables.
        alpha = self.config.ranges.taxon_gamma_alpha
        beta = self.config.ranges.taxon_gamma_beta
        raw_abundances = [rng.gammavariate(alpha, beta) for _ in range(n)]
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
        seed_str = f"{self.config.random_seed}|{self.config.graph_id}|{NodeType.FUNCTION.value}"
        rng = random.Random(seed_str)
        r = self.config.ranges
        nodes: list[Node] = []
        for i in range(n):
            node_id = f"synthetic:function:{i + 1:04d}"
            entry = _FUNCTION_CATALOG[i % len(_FUNCTION_CATALOG)]
            rel_low, rel_high = entry["val_range"]
            val_type = str(entry["val_type"])
            if val_type == "presence":
                annotation_val = 1.0
            else:
                # Escalar el rango relativo al rango absoluto configurado
                abs_span = r.function_abundance_high - r.function_abundance_low
                low = r.function_abundance_low + rel_low * abs_span
                high = r.function_abundance_low + rel_high * abs_span
                annotation_val = round(rng.uniform(low, high), 3)
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
        seed_str = f"{self.config.random_seed}|{self.config.graph_id}|{NodeType.METABOLITE.value}"
        rng = random.Random(seed_str)
        r = self.config.ranges
        nodes: list[Node] = []
        for i in range(n):
            node_id = f"synthetic:metabolite:{i + 1:04d}"
            entry = _METABOLITE_CATALOG[i % len(_METABOLITE_CATALOG)]
            # Escalar el rango relativo al rango absoluto configurado
            rel_low, rel_high = entry["conc_range"]
            abs_span = r.metabolite_conc_high - r.metabolite_conc_low
            low = r.metabolite_conc_low + rel_low * abs_span
            high = r.metabolite_conc_low + rel_high * abs_span
            conc = round(rng.uniform(low, high), 3)
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
        seed_str = f"{self.config.random_seed}|{self.config.graph_id}|{NodeType.HOST.value}"
        rng = random.Random(seed_str)
        nodes: list[Node] = []
        for i in range(n):
            node_id = f"synthetic:host:{i + 1:04d}"
            age = self.config.timepoint_days
            sex = rng.choice(["male", "female", "mixed"])
            r = self.config.ranges
            weight = round(rng.uniform(r.host_body_weight_low, r.host_body_weight_high), 1)
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
        seed_str = f"{self.config.random_seed}|{self.config.graph_id}|{NodeType.PHENOTYPE.value}"
        rng = random.Random(seed_str)
        nodes: list[Node] = []
        for i in range(n):
            node_id = f"synthetic:phenotype:{i + 1:04d}"
            entry = _PHENOTYPE_CATALOG[i % len(_PHENOTYPE_CATALOG)]
            # Escalar el rango relativo al rango absoluto configurado
            rel_low, rel_high = entry["val_range"]
            r = self.config.ranges
            abs_span = r.phenotype_value_high - r.phenotype_value_low
            low = r.phenotype_value_low + rel_low * abs_span
            high = r.phenotype_value_low + rel_high * abs_span
            val = round(rng.uniform(low, high), 3)
            trait = (
                f"{entry['trait']}_{i + 1:02d}"
                if i >= len(_PHENOTYPE_CATALOG)
                else str(entry["trait"])
            )
            attrs = PhenotypeAttributes(
                trait=trait,
                timepoint=f"day_{self.config.timepoint_days}",
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
