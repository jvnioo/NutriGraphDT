"""Explicación del escenario con el modelo congelado (A104, #334), sin Streamlit.

`explain_scenario` ejecuta GNNExplainer (`nutrigraphdt.explainability.HeteroExplainer`) sobre la
instancia del escenario tal como la recibe el modelo de la corrida (`ScenarioEngine.model_input`:
alineada, codificada y escalada con el `FeatureScaler` guardado). La explicación se valida con el
contrato de explicaciones (`validate_explanation`) y lleva la referencia real de la corrida
(`out_of_fold.run_ref`).

**Qué se explica con `homo_sage`.** La corrida de la plataforma es `homo_sage`, que convierte el
grafo a homogéneo antes de pasar mensajes: las máscaras de aristas por tripleta no llegan a
ninguna capa (`docs/models/explainers-poc.md`). Por eso se explican **nodos y atributos**
(`node_mask_type="attributes"`, `edge_mask_type=None`) y las aristas no reciben importancia
propia. El «subgrafo explicativo» que se dibuja son los `k` nodos más importantes con las aristas
del grafo que los unen, rotuladas como del grafo y no como importantes.

**Interpretación.** Una importancia es una asociación que el modelo usa, no una causa; en datos
sintéticos describe al modelo y no un mecanismo biológico (A71-P3, #280).
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Final

from nutrigraphdt.demo.graph_viewer import Records

TARGETS: Final[dict[str, str]] = {
    "log_propionate_acetate": "ln(propionato / acetato)",
    "log_butyrate_acetate": "ln(n-butirato / acetato)",
    "log_total": "ln T (total de AGCC)",
}
DEFAULT_EPOCHS: Final[int] = 30
"""Épocas de GNNExplainer: las de `scripts/explain_synthetic.py` (A60-P1)."""
DEFAULT_TOP_K: Final[int] = 10
DEFAULT_SEED: Final[int] = 0
SYNTHETIC_PREFIX: Final[str] = "synthetic:"

INTERPRETATION: Final[tuple[str, ...]] = (
    "Asociación no es causalidad: una importancia dice qué partes del grafo usa el modelo para "
    "esta predicción, no qué las causa (A71-P3).",
    "Datos sintéticos: la importancia describe al modelo entrenado con la cohorte sintética, no un "
    "mecanismo biológico.",
    "Evidencia: cada arista conserva su estado de evidencia; en el grafo sintético todas son "
    "«sintéticas» y las relaciones hipotéticas no tienen respaldo empírico (C-03). Una arista "
    "importante no está mejor respaldada.",
    "Estabilidad: GNNExplainer depende de su semilla. A71-P2 midió la estabilidad del top-k entre "
    "semillas del explicador y del plan; una importancia que cambia con la semilla no debe leerse "
    "como un hallazgo.",
    "Este modelo (homo_sage) no admite máscaras de aristas: se explican nodos y atributos; las "
    "aristas del subgrafo son las del grafo entre los nodos más importantes.",
)


@dataclass(frozen=True)
class ScenarioExplanation:
    """Explicación validada, con lo que necesita la página."""

    explanation: Any
    """`nutrigraphdt.explainability.Explanation`."""
    elapsed_seconds: float
    by_node_type: list[dict[str, Any]]
    top_nodes: list[dict[str, Any]]


def _feature_names(engine: Any, graph: Any) -> dict[str, list[str]]:
    names: dict[str, list[str]] = {}
    for node_type in graph.node_types:
        columns = engine.base.schema.node.get(node_type, ())
        width = int(graph[node_type].x.size(1)) if "x" in graph[node_type] else 0
        if columns and len(columns) == width:
            names[node_type] = [str(c.name) for c in columns]
    return names


def explain_scenario(
    engine: Any,
    request: Any,
    *,
    target: str = "log_total",
    epochs: int = DEFAULT_EPOCHS,
    top_k: int = DEFAULT_TOP_K,
    seed: int = DEFAULT_SEED,
) -> ScenarioExplanation:
    """Explicación GNNExplainer de `target` para el escenario, con el modelo de `engine`.

    Raises:
        ValueError: si `target` no es una salida del modelo.
        ExplanationContractError: si la explicación no cumple el contrato.
    """
    from nutrigraphdt.api.engine import REPO_ROOT
    from nutrigraphdt.explainability import HeteroExplainer, validate_explanation
    from nutrigraphdt.explainability.out_of_fold import run_ref

    if target not in TARGETS:
        raise ValueError(f"{target!r} no es una salida del modelo; use una de {list(TARGETS)}.")
    graph = engine.model_input(request)
    # El contrato exige el prefijo `synthetic:` en el graph_id de una instancia sintética
    # (EXP-09); toda instancia derivada lo es.
    if engine.base.is_synthetic and not str(graph.graph_id).startswith(SYNTHETIC_PREFIX):
        graph.graph_id = SYNTHETIC_PREFIX + str(graph.graph_id)
    loaded = engine.loaded
    edge_mask = None if loaded.info["variant"] == "homo_sage" else "object"
    start = time.perf_counter()
    explainer = HeteroExplainer(
        loaded.model,
        algorithm="gnn_explainer",
        node_mask_type="attributes",
        edge_mask_type=edge_mask,  # type: ignore[arg-type]
        epochs=epochs,
        seed=seed,
        top_k=top_k,
        run=run_ref(loaded, REPO_ROOT),
        node_feature_names=_feature_names(engine, graph),
    )
    explanation = explainer.explain(graph, target=target)
    elapsed = time.perf_counter() - start
    validate_explanation(explanation.model_dump())
    return ScenarioExplanation(
        explanation=explanation,
        elapsed_seconds=elapsed,
        by_node_type=importance_by_type(explanation),
        top_nodes=top_nodes(explanation, top_k),
    )


def importance_by_type(explanation: Any) -> list[dict[str, Any]]:
    """Suma y máximo de la importancia de los nodos por tipo, de mayor a menor suma."""
    total: dict[str, float] = defaultdict(float)
    peak: dict[str, float] = defaultdict(float)
    count: dict[str, int] = defaultdict(int)
    for node in explanation.importance.nodes:
        total[node.node_type] += node.importance
        peak[node.node_type] = max(peak[node.node_type], node.importance)
        count[node.node_type] += 1
    return sorted(
        (
            {"tipo": t, "nodos": count[t], "importancia total": total[t], "máxima": peak[t]}
            for t in total
        ),
        key=lambda r: (-r["importancia total"], r["tipo"]),
    )


def top_nodes(explanation: Any, k: int) -> list[dict[str, Any]]:
    """Los `k` nodos de mayor importancia (empate por tipo e id)."""
    ranked = sorted(
        explanation.importance.nodes, key=lambda n: (-n.importance, n.node_type, n.node_id)
    )
    return [
        {"tipo": n.node_type, "nodo": n.node_id, "importancia": n.importance} for n in ranked[:k]
    ]


def subgraph_records(records: Records, explanation: ScenarioExplanation) -> Records:
    """Los nodos más importantes y las aristas del grafo entre ellos, para el visualizador."""
    keep = {(n["tipo"], n["nodo"]) for n in explanation.top_nodes}
    nodes = [n for n in records.nodes if (n["node_type"], str(n["node_id"])) in keep]
    edges = [
        e
        for e in records.edges
        if (e["source_type"], str(e["source_id"])) in keep
        and (e["target_type"], str(e["target_id"])) in keep
    ]
    return Records(records.graph_id, nodes, edges)


__all__ = [
    "DEFAULT_EPOCHS",
    "DEFAULT_SEED",
    "DEFAULT_TOP_K",
    "INTERPRETATION",
    "TARGETS",
    "ScenarioExplanation",
    "explain_scenario",
    "importance_by_type",
    "subgraph_records",
    "top_nodes",
]
