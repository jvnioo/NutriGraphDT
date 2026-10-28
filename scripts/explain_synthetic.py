"""Ejemplo de uso del wrapper de explicadores (A60-P1, #170).

Genera una explicación de la salida `butyrate` del modelo `hetero_sage` sobre la primera
instancia del dataset sintético y la valida contra el contrato `1.0.0` (A55-P3, #156).

El archivo JSON resultante puede servir como referencia de integración con la API y el
módulo de visualización. Los valores de importancia dependen del estado aleatorio de los
pesos iniciales del modelo (sin entrenar): no representan resultados biológicos.

Uso:
    python scripts/explain_synthetic.py
    python scripts/explain_synthetic.py --variant hetero_gat --target log_butyrate_acetate
    python scripts/explain_synthetic.py --output reports/explainability/example.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from nutrigraphdt.data.synthetic import generate_synthetic_dataset
from nutrigraphdt.explainability import HeteroExplainer, validate_explanation
from nutrigraphdt.graph.heterodata import build_synthetic_graphs
from nutrigraphdt.models.gnn.base import GraphMetadata
from nutrigraphdt.models.gnn.factory import build_model, load_model_config

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "explainability" / "explanation_synthetic.json"
VARIANTS = ("homo_sage", "hetero_sage", "hetero_gat")
SEED = 170


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ejemplo de uso del wrapper de explicadores (#170)."
    )
    parser.add_argument(
        "--variant",
        choices=VARIANTS,
        default="hetero_sage",
        help="Variante del modelo GNN (por defecto: hetero_sage).",
    )
    parser.add_argument(
        "--target",
        default="butyrate",
        help="Nombre de la salida del modelo a explicar (por defecto: butyrate).",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=30,
        help="Épocas de GNNExplainer (por defecto: 30).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Número de aristas en el subgrafo top-k (por defecto: 5).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Ruta del JSON de salida (por defecto: {DEFAULT_OUTPUT.relative_to(REPO_ROOT)}).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    print(
        f"[explain_synthetic] variante={args.variant}, target={args.target}, epochs={args.epochs}"
    )

    torch.manual_seed(SEED)

    # Datos sintéticos
    dataset = generate_synthetic_dataset()
    graphs = build_synthetic_graphs(dataset).graphs
    graph_id = dataset.instances[0].graph_id
    data = graphs[graph_id]
    metadata = GraphMetadata.from_graphs([data])
    print(f"[explain_synthetic] grafo: {graph_id}")

    # Modelo
    config = load_model_config(REPO_ROOT / "configs" / "models" / f"{args.variant}.yaml")
    model = build_model(config, metadata).eval()
    print(f"[explain_synthetic] modelo: {model.__class__.__name__}")

    # Wrapper de explicadores
    edge_mask_type: str | None = "object"
    if args.variant == "homo_sage":
        # homo_sage convierte el grafo internamente: las máscaras de aristas por tripleta
        # no llegan a ninguna capa MessagePassing (ver docs/models/explainers-poc.md).
        edge_mask_type = None
        print(
            "[explain_synthetic] NOTA: homo_sage no soporta máscaras de aristas; "
            "se explica solo con nodos y atributos."
        )

    explainer = HeteroExplainer(
        model,
        algorithm="gnn_explainer",
        node_mask_type="attributes",
        edge_mask_type=edge_mask_type,
        epochs=args.epochs,
        seed=SEED,
        top_k=args.top_k,
        unit="1",
    )

    print("[explain_synthetic] ejecutando explicador…")
    explanation = explainer.explain(data, target=args.target)

    # Validar contra el contrato (redunda, pero lo dejamos explícito)
    validated = validate_explanation(explanation.model_dump())
    assert validated.format_version == "1.0.0"

    # Resumen
    print(f"[explain_synthetic] nodos con importancia: {len(explanation.importance.nodes)}")
    print(
        f"[explain_synthetic] atributos con importancia: {len(explanation.importance.attributes)}"
    )
    print(f"[explain_synthetic] aristas con importancia: {len(explanation.importance.edges)}")
    print(f"[explain_synthetic] aristas en top-{args.top_k}: {len(explanation.subgraph.edges)}")
    print(f"[explain_synthetic] predicción del modelo: {explanation.target.model_output}")

    # Serializar
    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(explanation.model_dump(), indent=2, ensure_ascii=False) + "\n"
    out.write_text(payload, encoding="utf-8")
    print(f"[explain_synthetic] guardado en {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
