"""Motor de escenarios detrás del contrato de `nutrigraphdt.api` (A81-P1, #287).

`predict_scenario` responde un `ScenarioRequest` con una corrida composicional congelada
(`load_compositional_run`, #180) y el soporte empírico de su train (`support_from_run`, #245).
No tiene lógica de la interfaz: recibe y devuelve los modelos del contrato.

**Base de escenarios.** `ScenarioBase` reúne los registros DS-01 (instancias, nodos, aristas y
salidas) del conjunto con que se entrenó la corrida y el `FeatureSchema` derivado de **todo** ese
conjunto, como lo hacen el constructor de D1 (`build_hetero_graph`) y la cohorte sintética
(`build_synthetic_graphs`). Así el grafo de un escenario tiene las mismas columnas que los del
entrenamiento; si no, el motor se niega a predecir. `synthetic_cohort_base` y `d1_base` las
construyen.

**Cómo se arma un escenario.** Se copia la observación del animal base y se le aplican las
variables declaradas (contrato de datos v2 §7, `nutrigraphdt.data.derived`): la instancia es
sintética, declara `derived_from` e `intervention` y conserva nodos, identificadores y aristas
de su origen. Con un origen real, INS-05 a INS-07 la comparan con él; cualquier hallazgo detiene
la predicción, porque significaría que cambió algo no declarado. Las salidas medidas del origen
no se copian: no son mediciones del escenario.

**Qué se puede intervenir.** Solo las entradas del modelo en nodos `diet`, `additive` y `host`
(`INTERVENABLE_NODE_TYPES`): composición de la dieta, tratamiento dietario, dosis del aditivo y
covariables de entrada del huésped. Los nodos del microbioma (taxones, funciones, sustratos) no
se fijan a mano: una variable se aplica a todos los nodos de su tipo (#151), y darles a todos los
taxones la misma abundancia no describe ningún escenario.

**Límites.** Una arista `hypothetical` no entra a ningún grafo real ni derivado (#256, sección
3): si la instancia base tiene una, el motor la rechaza. El soporte es global (mínimo y máximo de
cada fracción en el train de la corrida), no por día: con pocos animales por día el intervalo
diario sería casi un punto. No se calcula intervalo predictivo; el campo queda para A75.
"""

from __future__ import annotations

import contextlib
import copy
import dataclasses
import hashlib
import io
import json
import warnings
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any, Final

from nutrigraphdt.api.contract import (
    API_CONTRACT_VERSION,
    CAUSAL_WARNING,
    ESTIMABLE,
    SCFA_COMPONENTS,
    SYNTHETIC_WARNING,
    Bounds,
    ModelRef,
    ScenarioContractError,
    ScenarioRequest,
    ScenarioResponse,
    ScenarioVariable,
    SCFAFractions,
    SupportRef,
)
from nutrigraphdt.data.covariates import HOST_COVARIATES_BY_NAME
from nutrigraphdt.data.derived import DIET_COMPOSITION_PREFIX, DerivedVariable

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]

INTERVENABLE_NODE_TYPES: Final[tuple[str, ...]] = ("diet", "additive", "host")
HYPOTHETICAL_STATUS: Final[str] = "hypothetical"
WITHOUT_INFERRED_ARM: Final[str] = "without_inferred"
OBSERVED_SCENARIO_ID: Final[str] = "observed"

D1_DATASET_ID: Final[str] = "D1_holofood"
D1_FIXTURE_DATASET_ID: Final[str] = "D1_holofood_fixture"
D1_FIXTURE_DIR: Final[Path] = REPO_ROOT / "tests" / "fixtures" / "holofood"
D1_PARTIAL_WARNING: Final[str] = (
    "Grafo de D1 parcial: tiene 3 de las 11 relaciones del esquema v1 (has_capacity, produces y "
    "measured_in); no describe el ecosistema completo."
)
D1_FIXTURE_WARNING: Final[str] = (
    "Fixture de 6 animales reales de D1: el modelo es de demostración y sus predicciones no "
    "tienen valor científico."
)
BASAL_WARNING: Final[str] = (
    "Escenario basal: no cambia ninguna variable; sirve de control de calidad del simulador."
)
IN_TRAIN_WARNING: Final[str] = (
    "El animal base está en el train de la corrida: la predicción no es una evaluación fuera de "
    "muestra."
)

COVERAGE_WARNING: Final[str] = (
    "{0} = {1} no se observó en el train de la corrida (valores vistos: {2}): el modelo "
    "extrapola en esa entrada."
)
"""Advertencia de entrada fuera de lo observado; no cambia el estado (D-06 §7 lo define por las
fracciones predichas)."""

NONNEGATIVE_UNITS: Final[frozenset[str]] = frozenset({"g_kg", "MJ_kg", "CFU_kg", "d", "g"})
"""Unidades de magnitudes que no pueden ser negativas por definición."""
MASS_FRACTION_UNIT: Final[str] = "g_kg"
MASS_FRACTION_MAX: Final[float] = 1000.0
"""Un componente en g/kg de alimento no supera 1000 g/kg: es una cota de la unidad."""

Record = dict[str, Any]


def _as_dict(item: object) -> Record:
    if isinstance(item, Mapping):
        return copy.deepcopy(dict(item))
    to_dict = getattr(item, "to_dict", None)
    if callable(to_dict):
        return dict(to_dict())
    raise TypeError(f"Se esperaba un registro DS-01; se recibió {type(item).__name__}.")


def _set_path(attributes: Record, path: str, value: Any) -> None:
    parts = path.split(".")
    current = attributes
    for part in parts[:-1]:
        nested = current.get(part)
        if not isinstance(nested, dict):
            nested = {}
            current[part] = nested
        current = nested
    current[parts[-1]] = value


def _get_path(attributes: Record, derived: DerivedVariable) -> Any:
    if derived.component_id is not None:
        for item in attributes.get("composition") or ():
            if isinstance(item, Mapping) and item.get("component_id") == derived.component_id:
                return item.get("value")
        return None
    current: Any = attributes
    for part in derived.path.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


# ---------------------------------------------------------------------------
# Base de escenarios
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioBase:
    """Registros y esquema de columnas del conjunto con que se entrenó la corrida."""

    dataset_id: str
    instances: tuple[Record, ...]
    nodes: tuple[Record, ...]
    edges: tuple[Record, ...]
    outputs: tuple[Record, ...]
    schema: Any
    """`FeatureSchema` derivado del conjunto completo."""
    is_synthetic: bool
    warnings: tuple[str, ...] = ()
    _by_graph: dict[str, dict[str, list[Record]]] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    @classmethod
    def from_records(
        cls,
        records: Any,
        schema: Any,
        *,
        dataset_id: str,
        is_synthetic: bool,
        warnings: Sequence[str] = (),
    ) -> ScenarioBase:
        """Base desde un objeto con `instances`, `nodes`, `edges` y `outputs`."""
        base = cls(
            dataset_id=dataset_id,
            instances=tuple(_as_dict(i) for i in records.instances),
            nodes=tuple(_as_dict(n) for n in records.nodes),
            edges=tuple(_as_dict(e) for e in records.edges),
            outputs=tuple(_as_dict(o) for o in records.outputs),
            schema=schema,
            is_synthetic=is_synthetic,
            warnings=tuple(warnings),
        )
        grouped: dict[str, dict[str, list[Record]]] = defaultdict(
            lambda: {"nodes": [], "edges": [], "outputs": []}
        )
        for name in ("nodes", "edges", "outputs"):
            for record in getattr(base, name):
                grouped[str(record["graph_id"])][name].append(record)
        base._by_graph.update(grouped)
        return base

    @property
    def sample_ids(self) -> list[str]:
        return sorted({str(i["sample_id"]) for i in self.instances})

    def instance(self, sample_id: str) -> Record:
        """Registro de la instancia del animal `sample_id`.

        Raises:
            ScenarioContractError: si no hay exactamente una instancia con ese `sample_id`.
        """
        found = [i for i in self.instances if i.get("sample_id") == sample_id]
        if len(found) != 1:
            raise ScenarioContractError(
                [
                    f"La instancia base {sample_id!r} no existe en {self.dataset_id}."
                    if not found
                    else f"Hay {len(found)} instancias con sample_id {sample_id!r}."
                ]
            )
        return found[0]

    def records_of(self, graph_id: str) -> dict[str, list[Record]]:
        return self._by_graph.get(graph_id, {"nodes": [], "edges": [], "outputs": []})

    def values_of(self, sample_id: str, variable: str) -> tuple[Any, ...]:
        """Valores observados de `variable` en los nodos de su tipo del animal `sample_id`.

        Vacío si el animal no tiene nodos de ese tipo o el atributo falta; sin repetidos.
        """
        derived = DerivedVariable.parse(variable)
        graph_id = str(self.instance(sample_id)["graph_id"])
        found: list[Any] = []
        for node in self.records_of(graph_id)["nodes"]:
            if node.get("node_type") != derived.node_type:
                continue
            value = _get_path(node.get("attributes") or {}, derived)
            if value is not None and value not in found:
                found.append(value)
        return tuple(found)

    @cached_property
    def variables(self) -> dict[str, ScenarioVariable]:
        """Vocabulario de variables intervenibles: entradas del modelo en `diet`, `additive`
        y `host`, por ruta."""
        found: dict[str, dict[str, Any]] = {}
        for node_type in INTERVENABLE_NODE_TYPES:
            for column in self.schema.node.get(node_type, ()):
                if column.diet_treatment is not None:
                    path = f"{node_type}.name"
                    entry = found.setdefault(
                        path, {"kind": "categorical", "units": ["1"], "categories": []}
                    )
                    entry["categories"].append(column.diet_treatment.source_name)
                    entry["label"] = "Tratamiento dietario"
                elif column.covariate is not None:
                    path = f"{node_type}.covariates.{column.covariate.name}"
                    found[path] = {
                        "kind": "categorical",
                        "units": [column.covariate.unit or "1"],
                        "categories": list(column.covariate.vocabulary),
                        "label": f"Huésped: {column.covariate.name}",
                    }
                elif column.feature is not None:
                    path = f"{node_type}.{column.feature.path}"
                    entry = found.setdefault(path, {"kind": "numeric", "units": []})
                    entry["units"].append(column.unit)
                    entry["label"] = f"{node_type}: {column.feature.path}"
                else:  # componente de la dieta
                    path = f"{node_type}.{DIET_COMPOSITION_PREFIX}{column.qualifier}"
                    entry = found.setdefault(path, {"kind": "numeric", "units": []})
                    entry["units"].append(column.unit)
                    entry["label"] = f"Dieta: {column.qualifier}"
        return {
            path: ScenarioVariable(
                variable=path,
                node_type=path.partition(".")[0],
                kind=entry["kind"],
                unit=" | ".join(dict.fromkeys(entry["units"])),
                categories=tuple(dict.fromkeys(entry.get("categories", []))),
                label=entry["label"],
            )
            for path, entry in sorted(found.items())
        }

    # -- instancia derivada ------------------------------------------------

    def _checked_value(self, variable: ScenarioVariable, value: Any) -> Any:
        if variable.kind == "numeric":
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ScenarioContractError(
                    [f"{variable.variable}: se esperaba un número; se recibió {value!r}."]
                )
            units = {unit.strip() for unit in variable.unit.split("|")}
            if value < 0 and units <= NONNEGATIVE_UNITS:
                raise ScenarioContractError(
                    [f"{variable.variable}: {value!r} {variable.unit} no puede ser negativo."]
                )
            if units == {MASS_FRACTION_UNIT} and value > MASS_FRACTION_MAX:
                raise ScenarioContractError(
                    [
                        f"{variable.variable}: {value!r} g/kg supera {MASS_FRACTION_MAX:g} g/kg, "
                        "el total de un kilogramo de alimento."
                    ]
                )
            return value
        name = variable.variable.rpartition(".")[2]
        covariate = HOST_COVARIATES_BY_NAME.get(name) if variable.node_type == "host" else None
        if str(value) not in variable.categories or isinstance(value, bool):
            raise ScenarioContractError(
                [f"{variable.variable}: {value!r} no está en {list(variable.categories)}."]
            )
        return covariate.normalize(value) if covariate is not None else str(value)

    def derive(self, request: ScenarioRequest) -> tuple[Record, list[Record], list[Record]]:
        """Instancia derivada del escenario: `(instancia, nodos, aristas)`, sin salidas.

        Raises:
            ScenarioContractError: si la base no existe, una variable no está en el vocabulario,
                un valor no es válido, la base no tiene nodos del tipo intervenido o tiene
                aristas `hypothetical`.
        """
        origin = self.instance(request.base_instance)
        records = self.records_of(str(origin["graph_id"]))
        hypothetical = [
            e for e in records["edges"] if e.get("evidence_status") == HYPOTHETICAL_STATUS
        ]
        if hypothetical:
            raise ScenarioContractError(
                [
                    f"La instancia base tiene {len(hypothetical)} aristas hypothetical; no entran "
                    "a un grafo derivado (#256, sección 3)."
                ]
            )
        vocabulary = self.variables
        problems: list[str] = []
        changes: list[tuple[DerivedVariable, Any]] = []
        for item in request.intervention:
            variable = vocabulary.get(item.variable)
            if variable is None:
                problems.append(
                    f"{item.variable!r} no es una variable declarada del contrato para "
                    f"{self.dataset_id}; las admitidas son {sorted(vocabulary)}."
                )
                continue
            try:
                value = self._checked_value(variable, item.value)
            except ScenarioContractError as error:
                problems.extend(error.problems)
                continue
            changes.append((DerivedVariable.parse(item.variable), value))
        if problems:
            raise ScenarioContractError(problems)

        digest = hashlib.sha256(
            json.dumps(request.model_dump(mode="json"), sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        graph_id = f"scenario:{request.base_instance}:{digest}"
        nodes = [{**copy.deepcopy(n), "graph_id": graph_id} for n in records["nodes"]]
        edges = [{**copy.deepcopy(e), "graph_id": graph_id} for e in records["edges"]]
        for derived, value in changes:
            targets = [n for n in nodes if n["node_type"] == derived.node_type]
            if not targets:
                raise ScenarioContractError(
                    [f"La instancia base no tiene nodos {derived.node_type!r} que intervenir."]
                )
            for node in targets:
                self._apply(node, derived, value)
        instance = {
            **copy.deepcopy(origin),
            "graph_id": graph_id,
            "is_synthetic": True,
            "scenario_id": "intervention" if changes else "basal",
            "derived_from": request.base_instance,
            "intervention": [
                {"variable": item.variable, "value": value}
                for item, (_, value) in zip(request.intervention, changes, strict=True)
            ],
        }
        if origin.get("is_synthetic") is False:
            self._check_derived(origin, instance, nodes, edges)
        return instance, nodes, edges

    def _apply(self, node: Record, derived: DerivedVariable, value: Any) -> None:
        attributes = node.setdefault("attributes", {})
        mask = node.get("missing_mask")
        if derived.component_id is not None:
            unit = self.variables[f"diet.{derived.path}"].unit
            items = attributes.get("composition")
            if not isinstance(items, list):
                items = []
                attributes["composition"] = items
            for item in items:
                if isinstance(item, dict) and item.get("component_id") == derived.component_id:
                    item["value"] = value
                    break
            else:
                items.append({"component_id": derived.component_id, "value": value, "unit": unit})
            masked = "composition"
        else:
            _set_path(attributes, derived.path, value)
            masked = derived.path
        if isinstance(mask, dict) and mask.get(masked) is True:
            mask[masked] = False

    def _check_derived(
        self, origin: Record, instance: Record, nodes: list[Record], edges: list[Record]
    ) -> None:
        """INS-05 a INS-07 sobre la derivada frente a su origen real (#151)."""
        from nutrigraphdt.graph.validation import find_scenario_findings

        records = self.records_of(str(origin["graph_id"]))
        findings = find_scenario_findings(
            [origin, instance], [*records["nodes"], *nodes], [*records["edges"], *edges]
        )
        if findings:
            raise ScenarioContractError(
                [f"{finding.rule_id}: {finding.message}" for finding in findings]
            )

    # -- tensores ----------------------------------------------------------

    def graph(self, sample_id: str, request: ScenarioRequest | None = None) -> Any:
        """`HeteroData` con inversas y objetivo: la observación o, con `request`, el escenario."""
        from nutrigraphdt.graph.builder import add_reverse_edges
        from nutrigraphdt.graph.heterodata import build_heterodata
        from nutrigraphdt.models.gnn.target import add_graph_target

        if request is None:
            instance = self.instance(sample_id)
            graph_id = str(instance["graph_id"])
            records = self.records_of(graph_id)
            dataset = _Dataset([instance], records["nodes"], records["edges"], records["outputs"])
        else:
            instance, nodes, edges = self.derive(request)
            graph_id = str(instance["graph_id"])
            dataset = _Dataset([instance], nodes, edges, [])
        graph = add_graph_target(
            add_reverse_edges(build_heterodata(dataset, graph_id, self.schema))
        )
        graph.graph_id = graph_id
        return graph


@dataclass(frozen=True)
class _Dataset:
    instances: list[Record]
    nodes: list[Record]
    edges: list[Record]
    outputs: list[Record]


def synthetic_cohort_base(n_animals: int, first_seed: int) -> ScenarioBase:
    """Base de la cohorte sintética de `build_synthetic_cohort` (datos **sintéticos**)."""
    from nutrigraphdt.graph.heterodata import derive_schema
    from nutrigraphdt.models.baselines import build_synthetic_cohort
    from nutrigraphdt.models.training.cv_inputs import SYNTHETIC_DATASET_ID

    dataset = build_synthetic_cohort(n_animals, first_seed=first_seed)
    schema = derive_schema(dataset.nodes, dataset.edges, dataset.outputs)
    return ScenarioBase.from_records(
        dataset,
        schema,
        dataset_id=SYNTHETIC_DATASET_ID,
        is_synthetic=True,
        warnings=(SYNTHETIC_WARNING,),
    )


def d1_base(
    directory: str | Path = D1_FIXTURE_DIR, *, dataset_id: str = D1_FIXTURE_DATASET_ID
) -> ScenarioBase:
    """Base de animales **reales** de D1, construida como `scripts/build_graph.py`.

    `directory` tiene las tablas de la fuente (`abundance_ssu_caecum.tsv`, `metadata.tsv` y
    `scfa_caecum_content.tsv`); por omisión, el fixture de seis animales. Silencia los avisos de
    ingesta, que ya documenta el constructor.
    """
    from nutrigraphdt.data.config import load_sources
    from nutrigraphdt.data.functions import (
        DEFAULT_CAPACITY_TABLE,
        DEFAULT_PRODUCES_TABLE,
        DEFAULT_S04_TABLE,
        FunctionalAnnotations,
    )
    from nutrigraphdt.data.integration import attach_sample_context
    from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader
    from nutrigraphdt.data.pipeline import DataPipeline
    from nutrigraphdt.graph.builder import build_hetero_graph

    root = Path(directory)
    sources = load_sources(REPO_ROOT / "configs" / "sources.json")

    def source(source_id: str, file_name: str) -> Any:
        return dataclasses.replace(sources[source_id], path_or_url=str(root / file_name))

    with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
        warnings.simplefilter("ignore")
        abundance = source("D1_holofood", "abundance_ssu_caecum.tsv")
        abundance = dataclasses.replace(
            abundance, options={**abundance.options, "aggregate_to_genus": True}
        )
        tables = DataPipeline({"D1_holofood": abundance}).run(["D1_holofood"]).dataset
        tables, _ = attach_sample_context(
            tables,
            metadata=MetadataLoader(source("D1_holofood_metadata", "metadata.tsv")).load(),
            metabolites=MetaboliteLoader(
                source("D1_holofood_scfa_content", "scfa_caecum_content.tsv")
            ).load(),
        )
        built = build_hetero_graph(
            tables,
            annotations=FunctionalAnnotations.load(
                REPO_ROOT / DEFAULT_S04_TABLE,
                REPO_ROOT / DEFAULT_CAPACITY_TABLE,
                REPO_ROOT / DEFAULT_PRODUCES_TABLE,
            ),
        )
    notes = [D1_PARTIAL_WARNING]
    if dataset_id == D1_FIXTURE_DATASET_ID:
        notes.append(D1_FIXTURE_WARNING)
    return ScenarioBase.from_records(
        built.records,
        built.feature_schema,
        dataset_id=dataset_id,
        is_synthetic=False,
        warnings=tuple(notes),
    )


# ---------------------------------------------------------------------------
# Motor
# ---------------------------------------------------------------------------


class ScenarioEngine:
    """Corrida congelada + base de escenarios + soporte de su train.

    Raises:
        ScenarioContractError: si la base no es el conjunto de la corrida, si a algún animal de
            su train le falta la composición medida o si los grafos no tienen las columnas y
            relaciones del entrenamiento.
    """

    def __init__(self, run_dir: str | Path, base: ScenarioBase, *, device: str = "cpu") -> None:
        from nutrigraphdt.models.training.compositional_tracking import load_compositional_run
        from nutrigraphdt.scenarios.support import SupportError, support_from_run

        self.run_dir = Path(run_dir)
        self.base = base
        self.loaded = load_compositional_run(self.run_dir, device=device)
        info = self.loaded.info
        if info["dataset_id"] != base.dataset_id:
            raise ScenarioContractError(
                [
                    f"La corrida {self.loaded.run_id} se entrenó con {info['dataset_id']!r}; la "
                    f"base de escenarios es {base.dataset_id!r}."
                ]
            )
        self.train_ids: tuple[str, ...] = tuple(info["sample_ids"]["train"])
        self._references = [self._prepared(base.graph(s)) for s in self.train_ids]
        try:
            self.support = support_from_run(self.run_dir, self._measured_fractions())
        except SupportError as error:
            raise ScenarioContractError([str(error)]) from error

    def _prepared(self, graph: Any) -> Any:
        from nutrigraphdt.models.training.compositional import drop_inferred_edges

        if self.loaded.info["edges_arm"] == WITHOUT_INFERRED_ARM:
            graph = drop_inferred_edges(graph)
        return graph

    def _measured_fractions(self) -> dict[str, tuple[float, float, float]]:
        from nutrigraphdt.models.composition import compositional_target

        fractions: dict[str, tuple[float, float, float]] = {}
        for sample_id, graph in zip(self.train_ids, self._references, strict=True):
            if bool(graph.y_graph_mask.all()):
                values = [float(v) for v in graph.y_graph[0]]
                target = compositional_target(*values)
                if target.valid:
                    fractions[sample_id] = target.fractions
        return fractions

    def _aligned(self, graph: Any) -> Any:
        from nutrigraphdt.models.gnn.base import GraphMetadata
        from nutrigraphdt.models.gnn.batching import align_graph_types
        from nutrigraphdt.models.training.tracking import metadata_to_dict

        aligned = align_graph_types([graph, *self._references])[0]
        metadata = GraphMetadata.from_graphs([aligned])
        if self.loaded.taxon_encoder is not None:
            metadata = self.loaded.taxon_encoder.adapt_metadata(metadata)
        if metadata_to_dict(metadata) != dict(self.loaded.info["metadata"]):
            raise ScenarioContractError(
                [
                    "El grafo del escenario no tiene las columnas y relaciones con que se entrenó "
                    f"la corrida {self.loaded.run_id}."
                ]
            )
        return aligned

    @property
    def variables(self) -> list[ScenarioVariable]:
        return list(self.base.variables.values())

    def split_of(self, sample_id: str) -> str:
        """Papel del animal en la corrida: `train`, `inner_val`, `test` o `unused`."""
        for split, ids in self.loaded.info["sample_ids"].items():
            if sample_id in ids:
                return str(split)
        return "unused"

    @cached_property
    def train_coverage(self) -> dict[str, tuple[Any, ...]]:
        """Valores de cada variable vistos en el train: `(mín, máx)` si es numérica, o las
        categorías observadas. Una variable sin valores en el train no aparece."""
        coverage: dict[str, tuple[Any, ...]] = {}
        for variable in self.variables:
            seen = [v for s in self.train_ids for v in self.base.values_of(s, variable.variable)]
            if not seen:
                continue
            if variable.kind == "numeric":
                numbers = [float(v) for v in seen if isinstance(v, int | float)]
                if numbers:
                    coverage[variable.variable] = (min(numbers), max(numbers))
            else:
                coverage[variable.variable] = tuple(sorted({str(v) for v in seen}))
        return coverage

    def _coverage_warnings(self, request: ScenarioRequest) -> list[str]:
        notes: list[str] = []
        for item in request.intervention:
            seen = self.train_coverage.get(item.variable)
            if seen is None:
                continue
            kind = self.base.variables[item.variable].kind
            if kind == "numeric":
                lower, upper = seen
                if not lower <= float(item.value) <= upper:
                    observed = f"{lower:g}" if lower == upper else f"[{lower:g}, {upper:g}]"
                    notes.append(COVERAGE_WARNING.format(item.variable, item.value, observed))
            elif str(item.value) not in seen:
                notes.append(COVERAGE_WARNING.format(item.variable, item.value, list(seen)))
        return notes

    @cached_property
    def model_ref(self) -> ModelRef:
        info = self.loaded.info
        return ModelRef(
            run_id=str(info["run_id"]),
            variant=str(info["variant"]),
            edges_arm=str(info["edges_arm"]),
            dataset_id=str(info["dataset_id"]),
            seed=int(info["seed"]),
            fold=int(info["fold"]),
            format_version=str(info["format_version"]),
            compositional_target_version=str(info["compositional_target_version"]),
            git_commit=(info.get("git") or {}).get("commit"),
        )

    @cached_property
    def support_ref(self) -> SupportRef:
        data = self.support.to_dict()
        return SupportRef(
            version=str(data["version"]),
            source=str(data["source"]),
            n_animals=int(data["n_animals"]),
            interval={k: Bounds(lower=v[0], upper=v[1]) for k, v in data["interval"].items()},
            method=str(data["method"]),
        )

    def predict(self, request: ScenarioRequest | Mapping[str, Any]) -> ScenarioResponse:
        """Predicción del escenario, o `no_estimable` si cae fuera del soporte.

        Raises:
            ScenarioContractError: si la petición no cumple el contrato o el escenario no se
                puede construir con la base de la corrida.
        """
        from pydantic import ValidationError

        from nutrigraphdt.models.composition import fractions_from_log_ratios
        from nutrigraphdt.models.training.compositional_tracking import predict_compositional

        if not isinstance(request, ScenarioRequest):
            try:
                request = ScenarioRequest.model_validate(request)
            except ValidationError as error:
                raise ScenarioContractError(
                    [
                        f"{'.'.join(map(str, e['loc'])) or 'petición'}: {e['msg']}"
                        for e in error.errors()
                    ]
                ) from error
        graph = self._aligned(self._prepared(self.base.graph(request.base_instance, request)))
        _, outputs = predict_compositional(self.loaded, [graph])
        z1, z2, log_total = (float(v) for v in outputs[0])
        fractions = fractions_from_log_ratios(z1, z2)
        result = self.support.check([fractions])[0]
        notes = [CAUSAL_WARNING, *self.base.warnings]
        if not request.intervention:
            notes.append(BASAL_WARNING)
        if request.base_instance in self.train_ids:
            notes.append(IN_TRAIN_WARNING)
        notes.extend(self._coverage_warnings(request))
        estimable = result.status == ESTIMABLE
        return ScenarioResponse(
            contract_version=API_CONTRACT_VERSION,
            request=request,
            status=result.status,
            fractions=(
                SCFAFractions(**dict(zip(SCFA_COMPONENTS, fractions, strict=True)))
                if estimable
                else None
            ),
            log_total=log_total if estimable else None,
            reasons=result.reasons,
            interval=None,
            model=self.model_ref,
            support=self.support_ref,
            is_synthetic=self.base.is_synthetic,
            warnings=tuple(notes),
        )


def predict_scenario(
    request: ScenarioRequest | Mapping[str, Any],
    *,
    run_dir: str | Path,
    base: ScenarioBase,
    device: str = "cpu",
) -> ScenarioResponse:
    """Responde un escenario con la corrida de `run_dir`.

    Para varias peticiones con la misma corrida, cree un `ScenarioEngine` y reutilícelo: cargar
    la corrida y calcular el soporte se hace una sola vez.
    """
    return ScenarioEngine(run_dir, base, device=device).predict(request)


__all__ = [
    "BASAL_WARNING",
    "COVERAGE_WARNING",
    "D1_DATASET_ID",
    "D1_FIXTURE_DATASET_ID",
    "D1_FIXTURE_WARNING",
    "D1_PARTIAL_WARNING",
    "IN_TRAIN_WARNING",
    "INTERVENABLE_NODE_TYPES",
    "ScenarioBase",
    "ScenarioEngine",
    "d1_base",
    "predict_scenario",
    "synthetic_cohort_base",
]
