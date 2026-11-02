"""Costo en CPU de explicar D1 fuera de fold (C-05, #241).

La respuesta de Investigación a A55 (C-05) pide explicar cada animal con el modelo del fold en
que estuvo en test, en las semillas del plan, para dos salidas y con al menos 5 semillas del
explicador (C-07): 56 × 10 × 2 × 5 = 5600 ejecuciones por variante. Este script mide cuánto
tarda una ejecución de `GNNExplainer` sobre un grafo real de D1, con varias épocas, y
extrapola el total antes de fijar las épocas.

El tiempo de una ejecución no depende de los pesos: se mide con el modelo **sin entrenar** de
cada variante, sobre el grafo de D1 escalado con todos los animales. No entrena nada en D1. En
D1 se explican solo atributos (C-06): `node_mask_type="attributes"` y sin máscara de aristas.

Uso:
    python scripts/estimate_explanation_cost.py
    python scripts/estimate_explanation_cost.py --variants hetero_sage --epochs 100 200
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import time
from pathlib import Path
from typing import Any

import torch

from nutrigraphdt.explainability import HeteroExplainer, RunRef, SplitRef
from nutrigraphdt.explainability.criteria import MIN_EXPLAINER_SEEDS
from nutrigraphdt.models.composition import MODEL_OUTPUT_NAMES
from nutrigraphdt.models.gnn import load_model_config
from nutrigraphdt.models.gnn.factory import build_model
from nutrigraphdt.models.training.compositional_tracking import plan_content_sha256
from nutrigraphdt.models.training.cv_inputs import load_d1_cv_inputs
from nutrigraphdt.models.training.scaling import FeatureScaler

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = REPO_ROOT / "configs" / "sources.json"
DEFAULT_GRAPHS = REPO_ROOT / "artifacts" / "graphs" / "D1_holofood"
DEFAULT_PLAN = REPO_ROOT / "configs" / "splits" / "d1_holofood_cv.json"
DEFAULT_MODEL_CONFIGS = REPO_ROOT / "configs" / "models"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "explainability" / "explanation_cost"
VARIANTS = ("hetero_sage", "hetero_gat", "homo_sage")
EXPLAINED_OUTPUTS = 2
"""z1 y z2: las salidas que hoy superan a `dummy_mean` en D1 (C-04)."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--graphs-dir", type=Path, default=DEFAULT_GRAPHS)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS))
    parser.add_argument("--epochs", nargs="+", type=int, default=[100, 200])
    parser.add_argument("--repeats", type=int, default=3, help="Ejecuciones medidas por caso.")
    parser.add_argument("--threads", type=int, default=1, help="Hilos de torch por ejecución.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def _relative(path: Path) -> str:
    # Sin resolver enlaces: `artifacts/` puede ser un enlace simbólico fuera del repositorio.
    try:
        return Path(os.path.abspath(path)).relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _cpu_name() -> str:
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor() or platform.machine()


def measure(args: argparse.Namespace) -> dict[str, Any]:
    torch.set_num_threads(args.threads)
    inputs = load_d1_cv_inputs(args.sources, args.graphs_dir, args.plan)
    sample_id = sorted(inputs.graphs)[0]
    graph = FeatureScaler.fit(list(inputs.graphs.values())).transform([inputs.graphs[sample_id]])
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    run = RunRef(
        run_id="cost_estimate",
        run_json="runs/cost_estimate/run.json",
        format_version="1.0.0",
        variant="cost_estimate",
        seed=0,
        dataset_id=inputs.dataset_id,
        split=SplitRef(version=str(plan["version"]), sha256=plan_content_sha256(plan)),
        git_commit=None,
    )
    animals = len(inputs.graphs)
    plan_seeds = len(plan["seeds"])
    executions = animals * plan_seeds * EXPLAINED_OUTPUTS * MIN_EXPLAINER_SEEDS
    cases = []
    for variant in args.variants:
        torch.manual_seed(0)
        config = load_model_config(DEFAULT_MODEL_CONFIGS / f"{variant}.yaml")
        model = build_model(config, inputs.metadata, target_names=MODEL_OUTPUT_NAMES).eval()
        for epochs in args.epochs:
            seconds = []
            for seed in range(args.repeats + 1):
                explainer = HeteroExplainer(
                    model,
                    node_mask_type="attributes",
                    edge_mask_type=None,
                    epochs=epochs,
                    seed=seed,
                )
                start = time.perf_counter()
                explainer.explain(graph[0], run=run, target=MODEL_OUTPUT_NAMES[0])
                if seed > 0:  # la primera ejecución calienta cachés y no se cuenta
                    seconds.append(time.perf_counter() - start)
            median = statistics.median(seconds)
            cases.append(
                {
                    "variant": variant,
                    "epochs": epochs,
                    "seconds_per_execution": round(median, 3),
                    "seconds_min": round(min(seconds), 3),
                    "seconds_max": round(max(seconds), 3),
                    "hours_one_process": round(median * executions / 3600, 2),
                }
            )
            print(f"[cost] {variant} epochs={epochs}: {median:.3f} s por ejecución")
    return {
        "dataset_id": inputs.dataset_id,
        "sample_id": sample_id,
        "graph_nodes": {t: int(graph[0][t].num_nodes) for t in graph[0].node_types},
        "animals": animals,
        "plan_seeds": plan_seeds,
        "explained_outputs": EXPLAINED_OUTPUTS,
        "explainer_seeds": MIN_EXPLAINER_SEEDS,
        "executions_per_variant": executions,
        "repeats": args.repeats,
        "torch_threads": args.threads,
        "cpu": _cpu_name(),
        "cpu_count": os.cpu_count(),
        "torch": torch.__version__,
        "cases": cases,
        "command": "python scripts/estimate_explanation_cost.py "
        + " ".join(
            [
                f"--variants {' '.join(args.variants)}",
                f"--epochs {' '.join(map(str, args.epochs))}",
                f"--repeats {args.repeats}",
                f"--threads {args.threads}",
                f"--graphs-dir {_relative(args.graphs_dir)}",
            ]
        ),
    }


def to_markdown(result: dict[str, Any]) -> str:
    processes = max(1, (result["cpu_count"] or 1) // max(1, result["torch_threads"]))
    lines = [
        "# Costo en CPU de las explicaciones fuera de fold (C-05, #241)",
        "",
        f"- **Comando:** `{result['command']}`",
        f"- **Equipo:** {result['cpu']}, {result['cpu_count']} hilos lógicos; torch "
        f"{result['torch']}, {result['torch_threads']} hilo(s) por ejecución.",
        f"- **Grafo medido:** `{result['sample_id']}` de {result['dataset_id']} "
        f"({', '.join(f'{t}: {n}' for t, n in result['graph_nodes'].items())} nodos).",
        f"- **Ejecuciones por variante:** {result['animals']} animales × {result['plan_seeds']} "
        f"semillas del plan × {result['explained_outputs']} salidas × "
        f"{result['explainer_seeds']} semillas del explicador = "
        f"**{result['executions_per_variant']}**.",
        "- **Medición:** `GNNExplainer` con máscara de atributos y sin máscara de aristas (C-06), "
        f"modelo sin entrenar, mediana de {result['repeats']} ejecuciones tras una de "
        "calentamiento.",
        "",
        f"| Variante | Épocas | s por ejecución (mín.–máx.) | Horas, 1 proceso | "
        f"Horas, {processes} procesos |",
        "|---|---:|---:|---:|---:|",
    ]
    for case in result["cases"]:
        hours = case["hours_one_process"]
        lines.append(
            f"| `{case['variant']}` | {case['epochs']} | {case['seconds_per_execution']:.3f} "
            f"({case['seconds_min']:.3f}–{case['seconds_max']:.3f}) | {hours:.2f} | "
            f"{hours / processes:.2f} |"
        )
    lines += [
        "",
        f"La columna de {processes} procesos supone ejecuciones independientes repartidas en "
        "los hilos lógicos del equipo, sin contar la carga de cada checkpoint (una vez por "
        "corrida, 50 por variante).",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = measure(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix(".json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    args.output.with_suffix(".md").write_text(to_markdown(result), encoding="utf-8")
    print(f"[cost] guardado en {_relative(args.output.with_suffix('.md'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
