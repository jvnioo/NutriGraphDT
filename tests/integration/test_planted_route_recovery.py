"""Recuperación de una ruta plantada frente a un control negativo (A60-P4, #168).

Escenario (sintético, `is_synthetic=True`; sus valores no representan cantidades biológicas)
------------------------------------------------------------------------------------------
Cada grafo tiene tres cadenas paralelas `substrate:i -> available_to -> taxon:i -> has_capacity
-> function:i` (i = 1, 2, 3). Cada sustrato tiene un valor al azar en [-1, 1]; los taxones
tienen un atributo constante y las funciones una marca que vale 1 solo en `function:1`. El
objetivo es el valor de `substrate:1`. Con la lectura media por tipo, la única forma de obtenerlo
es seguir la **ruta plantada** `substrate:1 -> taxon:1 -> function:1`, las dos aristas que
llegan a la función marcada. Las otras cuatro aristas son distractoras.

- **Modelo:** `hetero_sage` (2 capas, 32 canales, sin dropout), entrenado con 256 grafos.
- **Control negativo:** el mismo modelo entrenado con los objetivos permutados entre grafos;
  no puede aprender la dependencia.
- **Explicador:** `EdgeGradientSaliency` (`|∂ salida / ∂ m_e|` con todas las máscaras en 1),
  sobre 50 grafos de evaluación que no se usaron para entrenar.

Criterio fijado antes de correr (01-11-2026)
--------------------------------------------
La ruta se considera **recuperada** en un grafo si sus dos aristas forman exactamente el
subgrafo top-2 de la explicación. Un grafo cuyo modelo no usa las aristas
(`IncompatibleExplainerError`) cuenta como no recuperado.

- modelo entrenado: recuperada en al menos el 90 % de los grafos de evaluación;
- control negativo: recuperada en como máximo el 50 % (el azar daría 1/15 ≈ 7 %).

Requisito del escenario (no del explicador): el modelo entrenado aprende la tarea (MSE de
evaluación < 10 % de la varianza del objetivo) y el control no (MSE ≥ 50 % de la varianza).

Qué no comprueba
----------------
Que el explicador recupere rutas en D1 ni ninguna relación causal o biológica. Con
`GNNExplainer` y sus coeficientes por omisión la ruta no se distinguía del control (#215): esa
observación queda en `docs/models/explainer-wrapper-compatibility.md` §7.
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from torch_geometric.data import HeteroData  # noqa: E402
from torch_geometric.loader import DataLoader  # noqa: E402

from nutrigraphdt.explainability import (  # noqa: E402
    HeteroExplainer,
    IncompatibleExplainerError,
    validate_explanation,
)
from nutrigraphdt.models.gnn.base import GraphMetadata, SCFAGraphModel  # noqa: E402
from nutrigraphdt.models.gnn.factory import build_model, parse_model_config  # noqa: E402

N_CHAINS = 3
N_TRAIN = 256
N_EVAL = 50
EPOCHS = 100
TRAINED_MIN_RECOVERY = 0.9
CONTROL_MAX_RECOVERY = 0.5
AVAILABLE = ("substrate", "available_to", "taxon")
CAPACITY = ("taxon", "has_capacity", "function")
ROUTE = {
    ("available_to", "synthetic:substrate:0001", "synthetic:taxon:0001"),
    ("has_capacity", "synthetic:taxon:0001", "synthetic:function:0001"),
}


def route_graph(values: list[float], index: int) -> HeteroData:
    """Grafo con tres cadenas paralelas; el objetivo es el valor de `substrate:1`."""
    data = HeteroData()
    data.graph_id = f"synthetic:planted_route:{index:04d}"
    data.is_synthetic = True
    data["substrate"].x = torch.tensor([[value] for value in values])
    data["taxon"].x = torch.ones(N_CHAINS, 1)
    data["function"].x = torch.tensor([[1.0]] + [[0.0]] * (N_CHAINS - 1))
    for node_type in ("substrate", "taxon", "function"):
        data[node_type].missing_mask = torch.zeros_like(data[node_type].x, dtype=torch.bool)
        data[node_type].node_id = [f"synthetic:{node_type}:{i + 1:04d}" for i in range(N_CHAINS)]
    pairs = torch.arange(N_CHAINS)
    for edge_type in (AVAILABLE, CAPACITY):
        data[edge_type].edge_index = torch.stack([pairs, pairs])
        data[edge_type].evidence_status = ["synthetic"] * N_CHAINS
        data[edge_type].evidence_method = ["synthetic_generator"] * N_CHAINS
        data[edge_type].evidence_source = [None] * N_CHAINS
    data.target = torch.tensor([[values[0]]])
    return data


def _values() -> list[list[float]]:
    generator = torch.Generator().manual_seed(168)
    return (torch.rand(N_TRAIN + N_EVAL, N_CHAINS, generator=generator) * 2 - 1).tolist()


def _train(targets: list[float]) -> SCFAGraphModel:
    values = _values()[:N_TRAIN]
    graphs = [route_graph(v, i) for i, v in enumerate(values)]
    for graph, target in zip(graphs, targets, strict=True):
        graph.target = torch.tensor([[target]])
    torch.manual_seed(1)
    config = parse_model_config(
        {"variant": "hetero_sage", "hidden_channels": 32, "num_layers": 2, "dropout": 0.0}
    )
    model = build_model(config, GraphMetadata.from_graphs(graphs))
    loader = DataLoader(
        graphs, batch_size=32, shuffle=True, generator=torch.Generator().manual_seed(1)
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    for _ in range(EPOCHS):
        model.train()
        for batch in loader:
            optimizer.zero_grad()
            loss = torch.nn.functional.mse_loss(model(batch)[:, :1], batch.target)
            loss.backward()  # type: ignore[no-untyped-call]
            optimizer.step()
    return model.eval()


@pytest.fixture(scope="module")
def eval_graphs() -> list[HeteroData]:
    return [route_graph(v, N_TRAIN + i) for i, v in enumerate(_values()[N_TRAIN:])]


@pytest.fixture(scope="module")
def trained() -> SCFAGraphModel:
    return _train([v[0] for v in _values()[:N_TRAIN]])


@pytest.fixture(scope="module")
def control() -> SCFAGraphModel:
    targets = [v[0] for v in _values()[:N_TRAIN]]
    order = torch.randperm(N_TRAIN, generator=torch.Generator().manual_seed(7)).tolist()
    return _train([targets[i] for i in order])


def _explainer(model: SCFAGraphModel) -> HeteroExplainer:
    return HeteroExplainer(
        model, algorithm="edge_saliency", node_mask_type=None, edge_mask_type="object", top_k=2
    )


def _recovery(model: SCFAGraphModel, graphs: list[HeteroData]) -> float:
    recovered = 0
    for graph in graphs:
        try:
            explanation = _explainer(model).explain(graph, target=0)
        except IncompatibleExplainerError:
            continue
        top = {(e.relation_type, e.source_id, e.target_id) for e in explanation.subgraph.edges}
        recovered += top == ROUTE
    return recovered / len(graphs)


def _mse(model: SCFAGraphModel, graphs: list[HeteroData]) -> tuple[float, float]:
    with torch.no_grad():
        predictions = torch.cat([model(graph)[:, :1] for graph in graphs])
    targets = torch.cat([graph.target for graph in graphs])
    return float(((predictions - targets) ** 2).mean()), float(targets.var())


def test_the_scenario_is_learnable_only_with_the_true_targets(
    trained: SCFAGraphModel, control: SCFAGraphModel, eval_graphs: list[HeteroData]
) -> None:
    trained_mse, variance = _mse(trained, eval_graphs)
    control_mse, _ = _mse(control, eval_graphs)
    assert trained_mse < 0.1 * variance
    assert control_mse >= 0.5 * variance


def test_trained_model_recovers_the_planted_route(
    trained: SCFAGraphModel, eval_graphs: list[HeteroData]
) -> None:
    assert _recovery(trained, eval_graphs) >= TRAINED_MIN_RECOVERY


def test_negative_control_does_not_recover_the_route(
    control: SCFAGraphModel, eval_graphs: list[HeteroData]
) -> None:
    assert _recovery(control, eval_graphs) <= CONTROL_MAX_RECOVERY


def test_edge_saliency_is_deterministic_and_meets_the_contract(
    trained: SCFAGraphModel, eval_graphs: list[HeteroData]
) -> None:
    first = _explainer(trained).explain(eval_graphs[0], target=0)
    second = _explainer(trained).explain(eval_graphs[0], target=0)
    assert first.model_dump(exclude={"created_at"}) == second.model_dump(exclude={"created_at"})
    validated = validate_explanation(first.model_dump())
    assert validated.explainer.name == "EdgeGradientSaliency"
    assert {e.relation_type for e in validated.importance.edges} == {"available_to", "has_capacity"}


def test_edge_saliency_rejects_node_masks(trained: SCFAGraphModel) -> None:
    graph = route_graph([0.5, -0.5, 0.2], 0)
    explainer = HeteroExplainer(trained, algorithm="edge_saliency", node_mask_type="attributes")
    with pytest.raises((IncompatibleExplainerError, ValueError), match="solo explica aristas"):
        explainer.explain(graph, target=0)
