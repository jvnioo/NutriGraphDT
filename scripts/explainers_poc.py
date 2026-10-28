"""Prueba de concepto: explicadores de `torch_geometric.explain` sobre las GNN heterogéneas (#157).

A55-P2 (F7). **Exploración acotada, no arquitectura estable**: todo el código vive en este
script; el wrapper estable es #170. Comprueba, para cada variante (`homo_sage`, `hetero_sage`,
`hetero_gat`) y cada explicador, si produce máscaras sobre `HeteroData` y con qué forma, y
registra versiones, configuración, tiempos y errores.

Qué se explica: la salida `butyrate` (columna 2 de la predicción `[1, 3]`) de un modelo
**sin entrenar** (pesos iniciales con semilla fija) sobre la instancia sintética por omisión
(`generate_synthetic_dataset()`). Con un modelo sin entrenar las importancias no significan
nada: la prueba es solo de **compatibilidad técnica**.

Comprobaciones adicionales, para no aceptar resultados parciales silenciosos:

- **Alcance de las máscaras de aristas**: cuántas capas `MessagePassing` reciben la máscara
  por tipo de arista (`set_hetero_masks`). Si son cero, una máscara de aristas no puede afectar
  la predicción aunque el explicador devuelva valores.
- **Efecto de las máscaras de aristas**: la predicción con todas las máscaras en 1 frente a
  todas en 0; si no cambia, la máscara no se usa.
- **Tipos de arista relevantes**: solo se explican las tripletas que reciben convolución en
  alguna capa (`layer_edge_types`); las demás no influyen en la predicción, y se verifica que
  quitarlas no la cambia.

Uso:
    python scripts/explainers_poc.py                         # reports/explainability/
    python scripts/explainers_poc.py --explainer-epochs 50 --output <carpeta>

Captum (`IntegratedGradients`, `Saliency`) es opcional: `pip install -e ".[explain]"`. Sin él,
esos métodos se registran como `not_available`.

Código de salida: `0` si escribió el reporte.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
import time
import warnings
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
import torch_geometric
from torch import Tensor, nn
from torch_geometric.data import HeteroData
from torch_geometric.explain import Explainer
from torch_geometric.explain.algorithm import (
    AttentionExplainer,
    CaptumExplainer,
    ExplainerAlgorithm,
    GNNExplainer,
    PGExplainer,
)
from torch_geometric.explain.algorithm.utils import clear_masks, set_hetero_masks
from torch_geometric.nn import MessagePassing

from nutrigraphdt.data.synthetic import generate_synthetic_dataset
from nutrigraphdt.graph.heterodata import build_synthetic_graphs
from nutrigraphdt.models.gnn.base import GraphMetadata, SCFAGraphModel, layer_edge_types
from nutrigraphdt.models.gnn.factory import build_model, load_model_config

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "explainability"
VARIANTS = ("homo_sage", "hetero_sage", "hetero_gat")
TARGET_NAME = "butyrate"
SEED = 157
MODEL_CONFIG = {"mode": "regression", "return_type": "raw", "task_level": "graph"}
EdgeType = tuple[str, str, str]


# ---------------------------------------------------------------------------
# Adaptador: PyG llama al modelo con (x_dict, edge_index_dict); los modelos reciben HeteroData
# ---------------------------------------------------------------------------


class HeteroAdapter(nn.Module):
    """Reconstruye el `HeteroData` que esperan los modelos y devuelve una sola salida `[1, 1]`.

    Los tipos de nodo sin columnas (`metabolite`, `phenotype`) no se pasan al explicador: una
    máscara sobre `x` de ancho 0 no recibe gradiente. Se toman del grafo de plantilla, igual que
    `missing_mask`.
    """

    def __init__(self, model: SCFAGraphModel, template: HeteroData, output_index: int) -> None:
        super().__init__()
        self.model = model
        self.template = template
        self.output_index = output_index

    def forward(
        self, x_dict: Mapping[str, Tensor], edge_index_dict: Mapping[EdgeType, Tensor], **_: Any
    ) -> Tensor:
        graph = HeteroData()
        for node_type in self.template.node_types:
            store = self.template[node_type]
            graph[node_type].x = x_dict.get(node_type, store.x)
            if "missing_mask" in store:
                graph[node_type].missing_mask = store.missing_mask
        for edge_type, edge_index in edge_index_dict.items():
            graph[edge_type].edge_index = edge_index
        output: Tensor = self.model(graph)
        return output[:, [self.output_index]]


def explained_inputs(
    data: HeteroData, model: SCFAGraphModel
) -> tuple[dict[str, Tensor], dict[EdgeType, Tensor], list[EdgeType]]:
    """`x_dict` con columnas, `edge_index_dict` de las tripletas relevantes y las omitidas."""
    x_dict = {t: data[t].x for t in data.node_types if "x" in data[t] and data[t].x.shape[1] > 0}
    relevant = {
        edge_type
        for layer in layer_edge_types(model.metadata, model.config.num_layers)
        for edge_type in layer
    }
    edges = {et: data[et].edge_index for et in data.edge_types if et in relevant}
    skipped = sorted(et for et in data.edge_types if et not in relevant)
    return x_dict, edges, skipped


# ---------------------------------------------------------------------------
# Comprobaciones
# ---------------------------------------------------------------------------


def edge_mask_reach(adapter: HeteroAdapter, edges: Mapping[EdgeType, Tensor]) -> int:
    """Capas `MessagePassing` que reciben una máscara por tipo de arista."""
    masks = {et: torch.ones(ei.shape[1]) for et, ei in edges.items()}
    set_hetero_masks(adapter, masks, dict(edges))
    reached = sum(1 for m in adapter.modules() if isinstance(m, MessagePassing) and m.explain)
    clear_masks(adapter)
    return reached


def edge_mask_effect(
    adapter: HeteroAdapter, x_dict: Mapping[str, Tensor], edges: Mapping[EdgeType, Tensor]
) -> float:
    """|predicción con máscaras en 1 − con máscaras en 0|; 0 si la máscara no se usa."""
    outputs = []
    for value in (1.0, 0.0):
        masks = {et: torch.full((ei.shape[1],), value) for et, ei in edges.items()}
        set_hetero_masks(adapter, masks, dict(edges), apply_sigmoid=False)
        with torch.no_grad():
            outputs.append(float(adapter(x_dict, edges)[0, 0]))
        clear_masks(adapter)
    return abs(outputs[0] - outputs[1])


def skipped_edges_do_not_matter(
    adapter: HeteroAdapter, data: HeteroData, x_dict: Mapping[str, Tensor], edges: Any
) -> bool:
    with torch.no_grad():
        full = adapter(x_dict, data.edge_index_dict)
        reduced = adapter(x_dict, edges)
    return bool(torch.allclose(full, reduced, atol=1e-6))


# ---------------------------------------------------------------------------
# Métodos
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Method:
    name: str
    algorithm: Callable[[int], ExplainerAlgorithm]
    explanation_type: str
    node_mask_type: str | None
    edge_mask_type: str | None
    requires: str | None = None
    trains: bool = False


def methods(explainer_epochs: int) -> list[Method]:
    return [
        Method("GNNExplainer", lambda e: GNNExplainer(epochs=e), "model", "attributes", "object"),
        Method(
            "GNNExplainer (solo atributos)",
            lambda e: GNNExplainer(epochs=e),
            "model",
            "attributes",
            None,
        ),
        Method(
            "GNNExplainer (solo nodos)",
            lambda e: GNNExplainer(epochs=e),
            "model",
            "object",
            None,
        ),
        Method(
            "Captum IntegratedGradients",
            lambda e: CaptumExplainer("IntegratedGradients"),
            "model",
            "attributes",
            "object",
            requires="captum",
        ),
        Method(
            "Captum Saliency",
            lambda e: CaptumExplainer("Saliency"),
            "model",
            "attributes",
            None,
            requires="captum",
        ),
        Method("AttentionExplainer", lambda e: AttentionExplainer(), "model", None, "object"),
        Method(
            "PGExplainer",
            lambda e: PGExplainer(epochs=e, lr=0.003),
            "phenomenon",
            None,
            "object",
            trains=True,
        ),
    ]


def _collect(explanation: Any, key: str) -> dict[Any, Tensor]:
    """Máscaras `key` por tipo; vacío si el explicador no devolvió ninguna."""
    try:
        return dict(explanation.collect(key))
    except KeyError:
        return {}


def _shapes(masks: Mapping[Any, Tensor]) -> dict[str, list[int]]:
    return {
        "|".join(key) if isinstance(key, tuple) else str(key): list(value.shape)
        for key, value in masks.items()
    }


def _nonzero(masks: Mapping[Any, Tensor]) -> list[int]:
    return [
        sum(int((v.abs() > 0).sum()) for v in masks.values()),
        sum(int(v.numel()) for v in masks.values()),
    ]


def run_method(
    method: Method,
    adapter: HeteroAdapter,
    x_dict: Mapping[str, Tensor],
    edges: Mapping[EdgeType, Tensor],
    *,
    explainer_epochs: int,
    reach: int,
    effect: float,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "method": method.name,
        "explanation_type": method.explanation_type,
        "node_mask_type": method.node_mask_type,
        "edge_mask_type": method.edge_mask_type,
    }
    if method.requires and importlib.util.find_spec(method.requires) is None:
        return {**result, "status": "not_available", "error": f"falta {method.requires}"}
    torch.manual_seed(SEED)
    start = time.perf_counter()
    try:
        algorithm = method.algorithm(explainer_epochs)
        explainer = Explainer(
            adapter,
            algorithm=algorithm,
            explanation_type=method.explanation_type,
            node_mask_type=method.node_mask_type,
            edge_mask_type=method.edge_mask_type,
            model_config=MODEL_CONFIG,
        )
        kwargs: dict[str, Any] = {"index": 0}
        if method.explanation_type == "phenomenon":
            with torch.no_grad():
                kwargs["target"] = adapter(dict(x_dict), dict(edges))
        if method.trains:
            for epoch in range(explainer_epochs):
                algorithm.train(epoch, adapter, dict(x_dict), dict(edges), **kwargs)
        explanation = explainer(dict(x_dict), dict(edges), **kwargs)
    except Exception as error:  # la prueba registra cualquier incompatibilidad
        return {
            **result,
            "status": "error",
            "error": f"{type(error).__name__}: {str(error).splitlines()[0]}",
            "seconds": round(time.perf_counter() - start, 3),
        }
    node_masks = _collect(explanation, "node_mask") if method.node_mask_type else {}
    edge_masks = _collect(explanation, "edge_mask") if method.edge_mask_type else {}
    status = "ok"
    notes = []
    for kind, requested, masks in (
        ("nodos", method.node_mask_type, node_masks),
        ("aristas", method.edge_mask_type, edge_masks),
    ):
        if requested and not masks:
            status = "invalid"
            notes.append(f"se pidió máscara de {kind}, pero la explicación no la contiene.")
    if method.edge_mask_type and edge_masks and (reach == 0 or effect == 0.0):
        # El explicador devolvió valores, pero la máscara no llega al modelo: no se acepta.
        status = "invalid"
        notes.append(
            "las máscaras de aristas no llegan a ninguna capa del modelo (o no cambian la "
            "predicción): los valores devueltos no explican la predicción."
        )
    return {
        **result,
        "status": status,
        "seconds": round(time.perf_counter() - start, 3),
        "node_mask_shapes": _shapes(node_masks),
        "edge_mask_shapes": _shapes(edge_masks),
        "node_mask_nonzero": _nonzero(node_masks),
        "edge_mask_nonzero": _nonzero(edge_masks),
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Reporte
# ---------------------------------------------------------------------------


def fresh_adapter(variant: str, data: HeteroData, metadata: GraphMetadata) -> HeteroAdapter:
    """Modelo nuevo con la misma semilla (pesos idénticos) para cada método.

    Cada método recibe su propia instancia: tras `GNNExplainer` con máscaras de aristas,
    `CaptumExplainer` falla sobre el mismo objeto ("differentiated Tensor ... not used"),
    aunque `clear_masks` deja `explain` y las máscaras en su estado inicial.
    """
    torch.manual_seed(SEED)
    config = load_model_config(REPO_ROOT / "configs" / "models" / f"{variant}.yaml")
    model = build_model(config, metadata).eval()
    output_index = list(model.target_names).index(TARGET_NAME)
    return HeteroAdapter(model, data, output_index).eval()


def run(explainer_epochs: int) -> dict[str, Any]:
    dataset = generate_synthetic_dataset()
    graphs = build_synthetic_graphs(dataset).graphs
    graph_id = dataset.instances[0].graph_id
    data = graphs[graph_id]
    metadata = GraphMetadata.from_graphs([data])
    variants = []
    for variant in VARIANTS:
        adapter = fresh_adapter(variant, data, metadata)
        x_dict, edges, skipped = explained_inputs(data, adapter.model)
        reach = edge_mask_reach(adapter, edges)
        effect = edge_mask_effect(adapter, x_dict, edges)
        variants.append(
            {
                "variant": variant,
                "explained_node_types": sorted(x_dict),
                "explained_edge_types": [list(et) for et in sorted(edges)],
                "skipped_edge_types": [list(et) for et in skipped],
                "skipped_edges_do_not_change_prediction": skipped_edges_do_not_matter(
                    adapter, data, x_dict, edges
                ),
                "edge_mask_layers_reached": reach,
                "edge_mask_effect": effect,
                "results": [
                    run_method(
                        method,
                        fresh_adapter(variant, data, metadata),
                        x_dict,
                        edges,
                        explainer_epochs=explainer_epochs,
                        reach=reach,
                        effect=effect,
                    )
                    for method in methods(explainer_epochs)
                ],
            }
        )
    captum = importlib.util.find_spec("captum")
    return {
        "issue": "#157",
        "purpose": "Prueba de concepto de compatibilidad técnica; no es una validación causal.",
        "target": {"graph_id": graph_id, "output": TARGET_NAME, "model": "sin entrenar"},
        "seed": SEED,
        "explainer_epochs": explainer_epochs,
        "model_config": MODEL_CONFIG,
        "versions": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "torch_geometric": torch_geometric.__version__,
            "captum": __import__("captum").__version__ if captum else None,
            "platform": platform.platform(),
        },
        "variants": variants,
    }


MASK_READING = (
    "## Cómo leer las máscaras",
    "",
    "- **Importancia de atributos** (`node_mask_type = attributes`): un valor por nodo y "
    "columna de `x`, forma `[nodos, columnas]`.",
    "- **Importancia de nodos** (`node_mask_type = object`): un valor por nodo, `[nodos, 1]`. "
    "Se obtiene también sumando la de atributos por fila.",
    "- **Importancia de aristas** (`edge_mask_type = object`): un valor por arista, `[aristas]`, "
    "por tipo de relación.",
    "",
    "**Advertencias.** La importancia mide asociación dentro del modelo, no causalidad, y no es "
    "evidencia del dominio. Los pesos de atención (`AttentionExplainer`) no se interpretan como "
    "explicación por omisión. Aquí los modelos están sin entrenar y los datos son sintéticos: los "
    "valores no tienen significado biológico.",
    "",
)


def to_markdown(report: Mapping[str, Any]) -> str:
    versions = report["versions"]
    compatible = [
        f"`{variant['variant']}` + {result['method']}"
        for variant in report["variants"]
        for result in variant["results"]
        if result["status"] == "ok"
    ]
    lines = [
        "# Prueba de concepto de explicadores de PyG (#157)",
        "",
        "Generado con `python scripts/explainers_poc.py`. **Compatibilidad técnica, no "
        "interpretación**: modelos sin entrenar (semilla "
        f"{report['seed']}), salida `{report['target']['output']}` de la instancia sintética "
        f"`{report['target']['graph_id']}`; {report['explainer_epochs']} épocas por explicador.",
        "",
        f"Versiones: Python {versions['python']}, torch {versions['torch']}, "
        f"torch_geometric {versions['torch_geometric']}, "
        f"captum {versions['captum'] or 'no instalado'}.",
        "",
        "Estados: `ok` (devuelve las máscaras pedidas y, si son de aristas, llegan al modelo), "
        "`error` (falla de forma explícita), `invalid` (devuelve algo, pero no sirve como "
        "explicación), `not_available` (falta una dependencia opcional).",
        "",
        f"Combinaciones compatibles: {len(compatible)}.",
        "",
        *MASK_READING,
    ]
    for variant in report["variants"]:
        lines += [
            f"## `{variant['variant']}`",
            "",
            f"- Capas que reciben máscara de aristas: {variant['edge_mask_layers_reached']}; "
            "la predicción cambia al pasar las máscaras de 1 a 0: "
            f"{'sí' if variant['edge_mask_effect'] > 0 else 'no'}.",
            "- Tripletas sin convolución (no influyen; se omiten): "
            f"{', '.join('`' + '|'.join(et) + '`' for et in variant['skipped_edge_types']) or '—'}"
            "; quitarlas no cambia la predicción: "
            f"{'sí' if variant['skipped_edges_do_not_change_prediction'] else 'NO'}.",
            "",
            "| Método | Estado | Máscara de nodos | Máscara de aristas "
            "| Valores no nulos (nodos · aristas) | Detalle |",
            "|---|---|---|---|---|---|",
        ]
        for result in variant["results"]:
            detail = result.get("error") or "; ".join(result.get("notes", [])) or "—"
            nodes = result.get("node_mask_nonzero")
            edges = result.get("edge_mask_nonzero")
            nonzero = (
                f"{nodes[0]}/{nodes[1]} · {edges[0]}/{edges[1]}"
                if nodes is not None and edges is not None
                else "—"
            )
            lines.append(
                f"| {result['method']} | {result['status']} | {result['node_mask_type'] or '—'} "
                f"| {result['edge_mask_type'] or '—'} | {nonzero} | {detail} |"
            )
        lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--explainer-epochs", type=int, default=30)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # avisos de PyG sobre APIs en cambio
        report = run(args.explainer_epochs)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "explainers_poc.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    markdown = to_markdown(report)
    (args.output / "explainers_poc.md").write_text(markdown + "\n", encoding="utf-8", newline="\n")
    print(markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
