"""Construcción de tablas de atributos para modelos no basados en grafos (A40-3, #73).

Transforma la información del grafo (abundancias taxonómicas, dieta, aditivos y
covariables del huésped) y sus salidas objetivo (acetato, propionato y butirato)
a formato tabular homogéneo (una fila por animal o muestra).

Garantías:
1. **Sin fuga de objetivo (no target leakage)**: Se audita estrictamente que ninguna columna
   objetivo ni derivada de ella se filtre al espacio de atributos ($X$).
2. **Partición versionada (A40-1)**: Aplica exactamente la partición train/val/test de
   `get_split()`, asegurando que no haya mezcla entre subconjuntos ni corrales.
3. **Compatibilidad multifuente**: Admite tanto el dataset sintético (`SyntheticDataset`)
   como la fuente real D1 HoloFood (`NormalizedTabularDataset`).
"""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from nutrigraphdt.data.covariates import INPUT_COVARIATES, NON_INPUT_COVARIATES
from nutrigraphdt.data.schema import NormalizedTabularDataset
from nutrigraphdt.data.split import DatasetSplit, get_split

# Nombres canónicos de los tres AGCC objetivo
CANONICAL_TARGETS: Final[tuple[str, ...]] = ("acetate", "propionate", "butyrate")

# Mapeo de identificadores químicos / sintéticos a nombres canónicos
CHEMICAL_ID_TO_CANONICAL: Final[Mapping[str, str]] = {
    "acetate": "acetate",
    "acetic_acid": "acetate",
    "synthetic:metabolite:acetate": "acetate",
    "propionate": "propionate",
    "propionic_acid": "propionate",
    "synthetic:metabolite:propionate": "propionate",
    "butyrate": "butyrate",
    "butyric_acid": "butyrate",
    "synthetic:metabolite:butyrate": "butyrate",
}

# Prefijos prohibidos en atributos para evitar fuga del target
FORBIDDEN_FEATURE_STEMS: Final[frozenset[str]] = frozenset(
    {"acetate", "propionate", "butyrate", "scfa", "metabolite"}
)


def _canonicalize_target_name(raw_name: str) -> str | None:
    """Traduce un nombre o identificador de metabolito al nombre canónico si es AGCC.

    Usa coincidencia exacta sobre `CHEMICAL_ID_TO_CANONICAL` para evitar falsos positivos
    por subcadena y asegurar consistencia con `canonical_scfa_name` / `add_graph_target` (§3.2).
    """
    return CHEMICAL_ID_TO_CANONICAL.get(raw_name.lower().strip())


@dataclass(frozen=True)
class TabularSample:
    """Representación tabular de un animal o muestra individual."""

    sample_id: str
    graph_id: str
    features: dict[str, float | str | None]
    targets: dict[str, float]
    split: str | None = None
    group: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def acetate(self) -> float | None:
        """Concentración de acetato si está presente."""
        return self.targets.get("acetate")

    @property
    def propionate(self) -> float | None:
        """Concentración de propionato si está presente."""
        return self.targets.get("propionate")

    @property
    def butyrate(self) -> float | None:
        """Concentración de butirato si está presente."""
        return self.targets.get("butyrate")


@dataclass(frozen=True)
class TabularDataset:
    """Tabla consolidada de atributos y objetivos para modelos no basados en grafos.

    Contiene una fila por animal o muestra, separando limpiamente $X$ de $y$
    con la partición de A40-1 aplicada.
    """

    samples: tuple[TabularSample, ...]
    feature_names: tuple[str, ...]
    target_names: tuple[str, ...] = CANONICAL_TARGETS
    split: DatasetSplit | None = None
    dataset_id: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.verify_no_target_leakage()

    def __len__(self) -> int:
        return len(self.samples)

    @property
    def sample_ids(self) -> tuple[str, ...]:
        """Identificadores de todas las muestras en la tabla."""
        return tuple(s.sample_id for s in self.samples)

    @property
    def X(self) -> list[list[float | str | None]]:
        """Matriz cruda de atributos (N muestras x M atributos)."""
        return [[s.features.get(fname) for fname in self.feature_names] for s in self.samples]

    @property
    def y(self) -> list[list[float]]:
        """Matriz objetivo (N muestras x K objetivos canónicos)."""
        return [
            [s.targets.get(tname, float("nan")) for tname in self.target_names]
            for s in self.samples
        ]

    def verify_no_target_leakage(self) -> None:
        """Audita estrictamente que ninguna columna objetivo o derivada esté en los atributos."""
        target_set = set(self.target_names)
        feature_set = set(self.feature_names)

        overlap = target_set & feature_set
        if overlap:
            raise ValueError(f"Fuga detectada: columnas objetivo presentes en atributos: {overlap}")

        for fname in self.feature_names:
            fname_lower = fname.lower()
            if fname_lower.startswith(("metabolite:", "target:")):
                raise ValueError(
                    f"Fuga detectada: el atributo '{fname}' proviene de una entidad metabolito "
                    f"o variable objetivo."
                )

            # Para atributos no taxonómicos (huésped, dieta, aditivos, etc.), ningún término
            # de los AGCC ni SCFA puede aparecer
            if not fname_lower.startswith("taxon:"):
                for stem in FORBIDDEN_FEATURE_STEMS:
                    if stem in fname_lower:
                        raise ValueError(
                            f"Fuga potencial detectada: el atributo no taxonómico '{fname}' "
                            f"contiene el término prohibido '{stem}' asociado al target."
                        )
            else:
                # En taxones, verificar que no termine exactamente en un metabolito aislado
                for tname in self.target_names:
                    if fname_lower == f"taxon:{tname}":
                        raise ValueError(
                            f"Fuga detectada: el atributo taxonómico '{fname}' coincide con el "
                            f"objetivo '{tname}'."
                        )

    def to_records(
        self,
        include_targets: bool = True,
        include_split: bool = True,
    ) -> list[dict[str, Any]]:
        """Convierte la tabla a una lista de diccionarios planos (una fila por muestra)."""
        records: list[dict[str, Any]] = []
        for s in self.samples:
            row: dict[str, Any] = {
                "sample_id": s.sample_id,
                "graph_id": s.graph_id,
            }
            if include_split and s.split is not None:
                row["split"] = s.split
            if s.group is not None:
                row["group"] = s.group
            for fname in self.feature_names:
                row[fname] = s.features.get(fname)
            if include_targets:
                for tname in self.target_names:
                    row[f"target_{tname}"] = s.targets.get(tname)
            records.append(row)
        return records

    def to_csv(self, include_targets: bool = True, include_split: bool = True) -> str:
        """Exporta la tabla a formato CSV."""
        records = self.to_records(include_targets=include_targets, include_split=include_split)
        if not records:
            return ""
        output = io.StringIO()
        fieldnames = list(records[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
        return output.getvalue()

    def categorical_vocabulary(self) -> dict[str, list[str]]:
        """Determina el vocabulario de categorías ordenadas para cada variable categórica."""
        vocab: dict[str, list[str]] = {}
        for fname in self.feature_names:
            values = [s.features.get(fname) for s in self.samples]
            is_cat = any(isinstance(v, str) for v in values if v is not None)
            if is_cat:
                unique_cats = sorted({str(v) for v in values if v is not None and str(v).strip()})
                vocab[fname] = unique_cats
        return vocab

    def to_numeric_matrix(
        self,
        one_hot: bool = True,
        fill_value: float = 0.0,
        categorical_vocab: Mapping[str, Sequence[str]] | None = None,
    ) -> tuple[tuple[str, ...], list[list[float]]]:
        """Convierte $X$ a una matriz numérica pura de flotantes para baselines lineales/árboles.

        Expande variables categóricas (ej. tratamiento dietario) mediante One-Hot Encoding
        determinista y rellena valores ausentes con `fill_value`.
        """
        if categorical_vocab is None:
            cat_vocab = self.categorical_vocabulary()
        else:
            cat_vocab = {k: list(v) for k, v in categorical_vocab.items()}

        numeric_cols: list[str] = [fname for fname in self.feature_names if fname not in cat_vocab]

        out_col_names: list[str] = list(numeric_cols)
        if one_hot:
            for cat_col, cats in sorted(cat_vocab.items()):
                for cat in cats:
                    out_col_names.append(f"{cat_col}={cat}")

        matrix: list[list[float]] = []
        for s in self.samples:
            row: list[float] = []
            for num_col in numeric_cols:
                val = s.features.get(num_col)
                if val is None or not isinstance(val, int | float) or not math.isfinite(val):
                    row.append(fill_value)
                else:
                    row.append(float(val))

            if one_hot:
                for cat_col, cats in sorted(cat_vocab.items()):
                    val_cat = s.features.get(cat_col)
                    val_str = str(val_cat) if val_cat is not None else ""
                    for cat in cats:
                        row.append(1.0 if val_str == cat else 0.0)

            matrix.append(row)

        return tuple(out_col_names), matrix

    def get_subset(self, split_name: str) -> TabularDataset:
        """Devuelve un nuevo TabularDataset filtrado por subconjunto ('train', 'val', 'test')."""
        filtered = tuple(s for s in self.samples if s.split == split_name)
        return TabularDataset(
            samples=filtered,
            feature_names=self.feature_names,
            target_names=self.target_names,
            split=self.split,
            dataset_id=self.dataset_id,
            metadata={**self.metadata, "subset": split_name},
        )

    def filter_complete_targets(self) -> TabularDataset:
        """Devuelve las muestras que poseen todos los objetivos finitos."""
        filtered = tuple(
            s
            for s in self.samples
            if all(
                t in s.targets
                and isinstance(s.targets[t], int | float)
                and math.isfinite(s.targets[t])
                for t in self.target_names
            )
        )
        return TabularDataset(
            samples=filtered,
            feature_names=self.feature_names,
            target_names=self.target_names,
            split=self.split,
            dataset_id=self.dataset_id,
            metadata={**self.metadata, "num_instances": len(filtered)},
        )

    def filter_samples(self, sample_ids: Collection[str]) -> TabularDataset:
        """Muestras cuyo `sample_id` está en `sample_ids` (por ejemplo, una cohorte)."""
        allowed = frozenset(sample_ids)
        filtered = tuple(s for s in self.samples if s.sample_id in allowed)
        return TabularDataset(
            samples=filtered,
            feature_names=self.feature_names,
            target_names=self.target_names,
            split=self.split,
            dataset_id=self.dataset_id,
            metadata={**self.metadata, "num_instances": len(filtered)},
        )

    @property
    def train_dataset(self) -> TabularDataset:
        return self.get_subset("train")

    @property
    def val_dataset(self) -> TabularDataset:
        return self.get_subset("val")

    @property
    def test_dataset(self) -> TabularDataset:
        return self.get_subset("test")

    def get_split_matrices(
        self,
        split_name: str,
        numeric: bool = True,
        one_hot: bool = True,
        fill_value: float = 0.0,
    ) -> tuple[list[list[Any]], list[list[float]]]:
        """Obtiene las matrices (X, y) para un subconjunto específico ('train', 'val', 'test').

        Usa el vocabulario de categorías del dataset completo para asegurar
        dimensiones idénticas en todas las particiones.
        """
        subset = self.get_subset(split_name)
        if numeric:
            vocab = self.categorical_vocabulary() if one_hot else None
            _, X_mat = subset.to_numeric_matrix(
                one_hot=one_hot,
                fill_value=fill_value,
                categorical_vocab=vocab,
            )
            return X_mat, subset.y
        return subset.X, subset.y


def build_tabular_from_holofood(
    tables: NormalizedTabularDataset,
    split: DatasetSplit | None = None,
    targets: Sequence[str] = CANONICAL_TARGETS,
) -> TabularDataset:
    """Construye la tabla de atributos desde un NormalizedTabularDataset de D1 HoloFood.

    Extrae:
    - Abundancias taxonómicas (`taxon:<node_id>`)
    - Tratamiento dietario (`diet:treatment`)
    - Covariables de entrada del huésped (contrato v2 §3, #147): `host:trial_code`,
      `host:sampling_day`, `host:sex` y `host:breed`, como categorías (texto), desde
      `host_covariates` de la instancia. `host:pen_code` y `host:body_weight_g` nunca entran:
      el corral solo agrupa la partición y el peso depende del tratamiento y del día.
    - Objetivos canónicos (`acetate`, `propionate`, `butyrate`) desde la tabla `targets`.
    """
    if split is None:
        split = get_split(dataset_id="D1_holofood")

    # Mapear targets por graph_id
    targets_by_graph: dict[str, dict[str, float]] = {}
    for t in tables.targets:
        canon_name = _canonicalize_target_name(t.target_id)
        if canon_name is not None and canon_name in targets:
            targets_by_graph.setdefault(t.graph_id, {})[canon_name] = float(t.value)

    # Identificar todas las features de interés
    feature_names_set: set[str] = set()
    features_by_graph: dict[str, dict[str, float | str]] = {}

    for f in tables.features:
        if f.node_type == "taxon":
            fname = f"taxon:{f.node_id}"
            feature_names_set.add(fname)
            features_by_graph.setdefault(f.graph_id, {})[fname] = float(f.value)
        elif f.node_type == "host":
            if f.feature_name in NON_INPUT_COVARIATES:
                continue  # contrato v2 §3: se informa, no es entrada
            fname = f"host:{f.feature_name}"
            feature_names_set.add(fname)
            features_by_graph.setdefault(f.graph_id, {})[fname] = float(f.value)
        elif f.node_type == "additive":
            fname = f"additive:{f.node_id}:{f.feature_name}"
            feature_names_set.add(fname)
            features_by_graph.setdefault(f.graph_id, {})[fname] = float(f.value)
        elif f.node_type == "diet":
            fname = f"diet:{f.node_id}:{f.feature_name}"
            feature_names_set.add(fname)
            features_by_graph.setdefault(f.graph_id, {})[fname] = float(f.value)
        # Nodos metabolite quedan explícitamente excluidos

    # Covariables categóricas de entrada del huésped (contrato v2 §3), como texto.
    for inst in tables.instances:
        for covariate in INPUT_COVARIATES:
            value = inst.host_covariates.get(covariate.name)
            if value is not None:
                fname = f"host:{covariate.name}"
                feature_names_set.add(fname)
                features_by_graph.setdefault(inst.graph_id, {})[fname] = str(value)

    # Añadir tratamiento dietario de la instancia
    diet_col = "diet:treatment"
    feature_names_set.add(diet_col)

    ordered_features = tuple(sorted(feature_names_set))
    samples: list[TabularSample] = []

    for inst in tables.instances:
        sample_feats: dict[str, float | str | None] = dict(features_by_graph.get(inst.graph_id, {}))
        if inst.diet_treatment and inst.diet_treatment != "unknown":
            sample_feats[diet_col] = inst.diet_treatment

        sample_targets = targets_by_graph.get(inst.graph_id, {})
        subset_name = split.subset_of(inst.sample_id) if split else None

        samples.append(
            TabularSample(
                sample_id=inst.sample_id,
                graph_id=inst.graph_id,
                features=sample_feats,
                targets=sample_targets,
                split=subset_name,
                metadata={"species": inst.species, "gut_segment": inst.gut_segment},
            )
        )

    return TabularDataset(
        samples=tuple(samples),
        feature_names=ordered_features,
        target_names=tuple(targets),
        split=split,
        dataset_id="D1_holofood",
        metadata={"num_instances": len(tables.instances)},
    )


def build_tabular_from_synthetic(
    dataset: Any,
    split: DatasetSplit | None = None,
    targets: Sequence[str] = CANONICAL_TARGETS,
) -> TabularDataset:
    """Construye la tabla de atributos desde un SyntheticDataset.

    Extrae:
    - Abundancias taxonómicas de nodos `taxon` (`taxon:<node_id>`)
    - Covariables del huésped de nodos `host` (`host:<covariate_name>`)
    - Aditivos de nodos `additive` (`additive:<node_id>:dose`, etc.)
    - Dieta de nodos `diet` y de la instancia (`diet:treatment`, composición)
    - Objetivos canónicos (`acetate`, `propionate`, `butyrate`) desde la tabla `outputs`.
    """
    # Mapeo de nodos metabolito a nombres canónicos
    metabolite_to_canon: dict[str, str] = {}
    for node in dataset.nodes:
        if node.node_type == "metabolite":
            chem_id = node.attributes.get("chemical_id", "")
            canon = _canonicalize_target_name(str(chem_id))
            if canon:
                metabolite_to_canon[node.node_id] = canon

    # Mapear targets por graph_id desde outputs
    targets_by_graph: dict[str, dict[str, float]] = {}
    for out in dataset.outputs:
        canon_name = metabolite_to_canon.get(out.target_id) or _canonicalize_target_name(
            out.target_id
        )
        if canon_name is not None and canon_name in targets:
            targets_by_graph.setdefault(out.graph_id, {})[canon_name] = float(out.value)

    # Agrupar atributos por graph_id
    feature_names_set: set[str] = set()
    features_by_graph: dict[str, dict[str, float | str]] = {}

    for node in dataset.nodes:
        gid = node.graph_id
        if node.node_type == "taxon":
            abd = node.attributes.get("abundance")
            if abd is not None and isinstance(abd, int | float):
                fname = f"taxon:{node.node_id}"
                feature_names_set.add(fname)
                features_by_graph.setdefault(gid, {})[fname] = float(abd)

        elif node.node_type == "host":
            covariates = node.attributes.get("covariates", {})
            if isinstance(covariates, Mapping):
                for cov_name, cov_val in covariates.items():
                    if isinstance(cov_val, int | float):
                        fname = f"host:{cov_name}"
                        feature_names_set.add(fname)
                        features_by_graph.setdefault(gid, {})[fname] = float(cov_val)
                    elif isinstance(cov_val, str) and cov_val:
                        fname = f"host:{cov_name}"
                        feature_names_set.add(fname)
                        features_by_graph.setdefault(gid, {})[fname] = str(cov_val)

        elif node.node_type == "additive":
            dose = node.attributes.get("dose")
            if dose is not None and isinstance(dose, int | float):
                fname = f"additive:{node.node_id}:dose"
                feature_names_set.add(fname)
                features_by_graph.setdefault(gid, {})[fname] = float(dose)
            category = node.attributes.get("category")
            if category and isinstance(category, str):
                fname = f"additive:{node.node_id}:category"
                feature_names_set.add(fname)
                features_by_graph.setdefault(gid, {})[fname] = str(category)

        elif node.node_type == "diet":
            composition = node.attributes.get("composition", [])
            if isinstance(composition, Sequence):
                for comp in composition:
                    if isinstance(comp, Mapping):
                        comp_id = comp.get("component_id")
                        val = comp.get("value")
                        if comp_id and isinstance(val, int | float):
                            fname = f"diet:composition:{comp_id}"
                            feature_names_set.add(fname)
                            features_by_graph.setdefault(gid, {})[fname] = float(val)

    diet_col = "diet:treatment"
    feature_names_set.add(diet_col)

    ordered_features = tuple(sorted(feature_names_set))
    samples: list[TabularSample] = []

    for inst in dataset.instances:
        sample_feats: dict[str, float | str | None] = dict(features_by_graph.get(inst.graph_id, {}))
        if inst.diet_treatment:
            sample_feats[diet_col] = inst.diet_treatment

        sample_targets = targets_by_graph.get(inst.graph_id, {})
        subset_name = split.subset_of(inst.sample_id) if split else None

        samples.append(
            TabularSample(
                sample_id=inst.sample_id,
                graph_id=inst.graph_id,
                features=sample_feats,
                targets=sample_targets,
                split=subset_name,
                metadata={"species": inst.species, "gut_segment": inst.gut_segment},
            )
        )

    return TabularDataset(
        samples=tuple(samples),
        feature_names=ordered_features,
        target_names=tuple(targets),
        split=split,
        dataset_id=getattr(dataset, "metadata", {}).get("dataset_id", "synthetic"),
        metadata={"num_instances": len(dataset.instances)},
    )


def build_tabular_dataset(
    source: Any,
    split: DatasetSplit | None = None,
    targets: Sequence[str] = CANONICAL_TARGETS,
) -> TabularDataset:
    """Función de entrada unificada para construir tablas de atributos.

    Detecta automáticamente si la fuente es un `NormalizedTabularDataset` (fuente real D1)
    o un `SyntheticDataset` (fuente sintética) y produce la tabla homogénea.
    """
    if isinstance(source, NormalizedTabularDataset):
        return build_tabular_from_holofood(source, split=split, targets=targets)
    if hasattr(source, "instances") and hasattr(source, "nodes") and hasattr(source, "outputs"):
        return build_tabular_from_synthetic(source, split=split, targets=targets)
    raise TypeError(
        f"Tipo de fuente no admitido para construcción tabular: {type(source).__name__}. "
        f"Se esperaba NormalizedTabularDataset o SyntheticDataset."
    )
