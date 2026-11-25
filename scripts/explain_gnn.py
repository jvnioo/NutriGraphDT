"""Script explain_gnn.py integrado al pipeline de evaluación de explicabilidad (A71-P1, #278).

Genera las explicaciones fuera de fold (C-05, #241) para cada animal de D1 o cohorte sintética,
mide su estabilidad entre semillas (C-07, A71-P2, #279) y produce los reportes técnicos y
artefactos validados contra el contrato 2.0.0 (A71-P3, #280).

Uso:
    python scripts/explain_gnn.py --dataset d1 --runs-dir runs/constraints/d1
    python scripts/explain_gnn.py --dataset synthetic --runs-dir runs/test_runs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from nutrigraphdt.explainability import (
    EXPLANATION_FORMAT_VERSION,
    HeteroExplainer,
    validate_explanation,
)
from nutrigraphdt.explainability.analysis import (
    build_stability_rows,
    collect_top_k_elements,
    generate_explainability_report,
    write_stability_csv,
    write_top_k_csv,
)
from nutrigraphdt.explainability.contract import Explanation, RunRef
from nutrigraphdt.explainability.criteria import (
    MIN_EXPLAINER_SEEDS,
    explainable_outputs,
    read_fold_metric,
)
from nutrigraphdt.explainability.out_of_fold import (
    AnimalExplanations,
    OutOfFoldError,
    explain_out_of_fold,
    index_runs,
    plan_out_of_fold,
)
from nutrigraphdt.models.composition import MODEL_OUTPUT_NAMES
from nutrigraphdt.models.gnn.base import SCFAGraphModel
from nutrigraphdt.models.training.cv_inputs import (
    load_d1_cv_inputs,
    load_synthetic_cv_inputs,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS_DIR = REPO_ROOT / "runs" / "constraints" / "d1"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "reports" / "explainability" / "d1"
DEFAULT_ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "explanations" / "d1"
DEFAULT_SOURCES = REPO_ROOT / "configs" / "sources.json"
DEFAULT_GRAPHS_DIR = REPO_ROOT / "artifacts" / "graphs" / "D1_holofood"
DEFAULT_PLAN_D1 = REPO_ROOT / "configs" / "splits" / "d1_holofood_cv.json"
DEFAULT_PLAN_SYN = REPO_ROOT / "configs" / "splits" / "synthetic_cohort_cv.json"

DEFAULT_DIAGNOSIS_METRICS = (
    REPO_ROOT / "reports" / "gnn" / "d1_microbiome_diagnosis" / "fold_metrics.csv"
)
DEFAULT_BASELINE_METRICS = (
    REPO_ROOT / "reports" / "baselines" / "d1_composition" / "fold_metrics.csv"
)

EXIT_OK = 0
EXIT_INPUT = 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generación de explicaciones fuera de fold para modelos GNN (#278)."
    )
    parser.add_argument(
        "--dataset",
        choices=("d1", "synthetic"),
        default="d1",
        help="Dataset a evaluar: 'd1' o 'synthetic' (por defecto: d1).",
    )
    rel_runs_dir = DEFAULT_RUNS_DIR.relative_to(REPO_ROOT)
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=DEFAULT_RUNS_DIR,
        help=f"Directorio de corridas entrenadas (por defecto: {rel_runs_dir}).",
    )
    parser.add_argument(
        "--variant",
        default="hetero_sage",
        help="Variante de GNN a explicar (por defecto: hetero_sage).",
    )
    parser.add_argument(
        "--edges-arm",
        default="free",
        help="Brazo de entrenamiento: 'free' o 'constrained' (por defecto: free).",
    )
    parser.add_argument(
        "--algorithm",
        default="edge_saliency",
        help="Algoritmo de explicabilidad: 'edge_saliency' (por defecto) o 'gnn_explainer'.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Número de aristas seleccionadas en el subgrafo top-k (por defecto: 5).",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=None,
        help="Semillas del plan de CV a explicar (por defecto: todas las encontradas en corridas).",
    )
    parser.add_argument(
        "--explainer-seeds",
        type=int,
        nargs="+",
        default=tuple(range(5)),
        help="Semillas del explicador para estabilidad C-07 (mínimo 5; por defecto: 0 1 2 3 4).",
    )
    parser.add_argument(
        "--outputs",
        nargs="+",
        default=None,
        help="Salidas a explicar (por defecto: autorizadas por C-04).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directorio de reportes (por defecto: reports/explainability/d1).",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=DEFAULT_ARTIFACTS_DIR,
        help="Directorio para JSONs detallados (por defecto: artifacts/explanations/d1).",
    )
    parser.add_argument(
        "--sources",
        type=Path,
        default=DEFAULT_SOURCES,
        help="Ruta de fuentes de datos (configs/sources.json).",
    )
    parser.add_argument(
        "--graphs-dir",
        type=Path,
        default=DEFAULT_GRAPHS_DIR,
        help="Directorio con grafos preconstruidos.",
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=None,
        help="Ruta al plan de validación cruzada JSON.",
    )
    parser.add_argument(
        "--limit-animals",
        type=int,
        default=None,
        help="Límite de animales a explicar (útil para pruebas rápidas).",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Dispositivo para inferencia y gradientes: 'cpu' o 'cuda' (por defecto: cpu).",
    )
    return parser.parse_args(argv)


def resolve_explainable_outputs(
    args: argparse.Namespace,
    model_fold_metrics: Path | None = None,
    dummy_fold_metrics: Path | None = None,
) -> tuple[str, ...]:
    """Determina las salidas autorizadas por C-04 o las especificadas por CLI."""
    if args.outputs:
        return tuple(args.outputs)

    # Intentar resolver dinámicamente con criterios C-04 si existen tablas de métricas
    m_path = model_fold_metrics or (
        DEFAULT_DIAGNOSIS_METRICS if DEFAULT_DIAGNOSIS_METRICS.exists() else None
    )
    d_path = dummy_fold_metrics or (
        DEFAULT_BASELINE_METRICS if DEFAULT_BASELINE_METRICS.exists() else None
    )

    if m_path is not None and d_path is not None:
        try:
            m_metrics = {
                metric: read_fold_metric(m_path, args.variant, metric, edges_arm=args.edges_arm)
                for metric in ("fraction_mae_pp", "log_total_mae")
            }
            d_metrics = {
                metric: read_fold_metric(d_path, "dummy_mean", metric)
                for metric in ("fraction_mae_pp", "log_total_mae")
            }
            allowed = explainable_outputs(m_metrics, d_metrics, test_train_ratio=0.25)
            if allowed:
                return allowed
        except Exception as err:
            print(f"[explain_gnn] Advertencia al resolver C-04: {err}", file=sys.stderr)

    # Por defecto según C-04 y out-of-fold-explanations.md
    return MODEL_OUTPUT_NAMES[:2]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if len(args.explainer_seeds) < MIN_EXPLAINER_SEEDS:
        print(
            f"Error: C-07 exige al menos {MIN_EXPLAINER_SEEDS} semillas del explicador.",
            file=sys.stderr,
        )
        return EXIT_INPUT

    # 1. Indexar corridas fuera de fold
    if not args.runs_dir.exists():
        print(
            f"Error: El directorio de corridas '{args.runs_dir}' no existe.\n"
            f"Genera corridas primero con: python scripts/evaluate_constraints.py "
            f"--dataset {args.dataset} --variants {args.variant} --runs-dir {args.runs_dir}",
            file=sys.stderr,
        )
        return EXIT_INPUT

    runs = index_runs(args.runs_dir, variant=args.variant, edges_arm=args.edges_arm)
    if not runs:
        print(
            f"Error: No se encontraron corridas para variante='{args.variant}' "
            f"y brazo='{args.edges_arm}' en '{args.runs_dir}'.",
            file=sys.stderr,
        )
        return EXIT_INPUT

    available_seeds = sorted({r.seed for r in runs})
    plan_seeds = tuple(args.seeds if args.seeds is not None else available_seeds)
    print(
        f"[explain_gnn] Corridas encontradas: {len(runs)} "
        f"(semillas plan: {list(plan_seeds)}, variante: {args.variant}, brazo: {args.edges_arm})"
    )

    # 2. Cargar grafos de entrada
    plan_path = args.plan or (DEFAULT_PLAN_D1 if args.dataset == "d1" else DEFAULT_PLAN_SYN)
    if args.dataset == "d1":
        cv_inputs = load_d1_cv_inputs(args.sources, args.graphs_dir, plan_path)
    else:
        cv_inputs = load_synthetic_cv_inputs(plan_path)

    graphs = cv_inputs.graphs
    if args.limit_animals is not None:
        selected_ids = sorted(graphs.keys())[: args.limit_animals]
        graphs = {s: graphs[s] for s in selected_ids}
        print(f"[explain_gnn] Limitando evaluación a {len(graphs)} animales.")

    # 3. Planificar fuera de fold
    try:
        plan = plan_out_of_fold(runs, graphs.keys(), plan_seeds)
    except OutOfFoldError as err:
        print(f"Error al planificar fuera de fold: {err}", file=sys.stderr)
        return EXIT_INPUT

    counts = plan.explanation_counts()
    print(f"[explain_gnn] Total animales planificados: {len(counts)}")
    missing = {s: m for s, m in plan.missing.items() if m}
    if missing:
        print(
            f"[explain_gnn] Advertencia: {len(missing)} animales tienen semillas faltantes: "
            f"{missing}"
        )

    # 4. Resolver salidas explicables (C-04)
    target_outputs = resolve_explainable_outputs(args)
    print(f"[explain_gnn] Salidas a explicar: {list(target_outputs)}")

    # 5. Definir función de explicador
    def explain_fn(
        model: SCFAGraphModel,
        graph: Any,
        run: RunRef,
        output: str,
        seed: int,
    ) -> Explanation:
        node_mask_type = None if args.algorithm == "edge_saliency" else "attributes"
        edge_mask_type = "object" if args.algorithm == "edge_saliency" else None
        explainer = HeteroExplainer(
            model,
            algorithm=args.algorithm,
            node_mask_type=node_mask_type,
            edge_mask_type=edge_mask_type,
            top_k=args.top_k,
            seed=seed,
            explainable_outputs=MODEL_OUTPUT_NAMES[:2],
        )
        return explainer.explain(graph, run=run, target=output)

    # 6. Ejecutar explicaciones fuera de fold
    print(
        f"[explain_gnn] Ejecutando explicaciones sobre {len(graphs)} animales "
        f"× {len(target_outputs)} salidas × {len(args.explainer_seeds)} semillas..."
    )
    results: list[AnimalExplanations] = explain_out_of_fold(
        plan,
        graphs,
        explain_fn,
        outputs=target_outputs,
        explainer_seeds=args.explainer_seeds,
        repo_root=REPO_ROOT,
        device=args.device,
    )
    print(f"[explain_gnn] Explicaciones completadas para {len(results)} instancias animal-salida.")

    # 7. Guardar JSONs detallados en artifacts
    args.artifacts_dir.mkdir(parents=True, exist_ok=True)
    saved_json_count = 0
    for animal in results:
        sample_dir = args.artifacts_dir / animal.sample_id / animal.output
        sample_dir.mkdir(parents=True, exist_ok=True)
        for seed, report in animal.by_seed.items():
            for exp_idx, exp in enumerate(report.explanations):
                # Validar contra el contrato 2.0.0
                validate_explanation(exp.model_dump())
                exp_file = sample_dir / f"seed_{seed}_exp_{args.explainer_seeds[exp_idx]}.json"
                exp_file.write_text(
                    json.dumps(exp.model_dump(), indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                saved_json_count += 1
    print(
        f"[explain_gnn] {saved_json_count} artefactos JSON validados y guardados en "
        f"{args.artifacts_dir}"
    )

    # 8. Escribir reportes y métricas
    args.output_dir.mkdir(parents=True, exist_ok=True)

    stability_rows = build_stability_rows(results)
    write_stability_csv(args.output_dir / "stability.csv", stability_rows)
    print(f"[explain_gnn] Estabilidad guardada en {args.output_dir / 'stability.csv'}")

    top_k_rows = collect_top_k_elements(results)
    write_top_k_csv(args.output_dir / "top_k_elements.csv", top_k_rows)
    print(f"[explain_gnn] Elementos top-k guardados en {args.output_dir / 'top_k_elements.csv'}")

    report_md = generate_explainability_report(
        results,
        plan,
        variant=args.variant,
        edges_arm=args.edges_arm,
        top_k=args.top_k,
    )
    (args.output_dir / "report.md").write_text(report_md, encoding="utf-8")
    print(f"[explain_gnn] Reporte final generado en {args.output_dir / 'report.md'}")

    # Resumen estructurado
    summary = {
        "dataset": args.dataset,
        "variant": args.variant,
        "edges_arm": args.edges_arm,
        "algorithm": args.algorithm,
        "top_k": args.top_k,
        "plan_seeds": list(plan_seeds),
        "explainer_seeds": list(args.explainer_seeds),
        "total_animals": len(plan.assignments),
        "missing_animals": [s for s, m in plan.missing.items() if len(m) == len(plan_seeds)],
        "target_outputs": list(target_outputs),
        "saved_json_count": saved_json_count,
        "format_version": EXPLANATION_FORMAT_VERSION,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("[explain_gnn] Ejecución completada exitosamente.")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
