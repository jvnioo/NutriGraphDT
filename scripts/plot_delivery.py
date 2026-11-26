"""Figuras de la entrega desde el código del repositorio (A115-P3, #346).

Escribe en `--output` (por defecto `reports/delivery/figures/`):

- `scenarios.png`: fracción molar de AGCC basal frente a intervenido para cada escenario del
  catálogo con la corrida de entrega (`synthetic`), con el intervalo MC-dropout sin calibrar;
  los escenarios no estimables se marcan sin barras.
- `metrics.png`: métricas de test de la entrega frente a A68-P2, leídas de
  `reports/delivery/results.json`.
- `figures.json`: procedencia de cada figura (comando, commit, entorno y fuentes).

Datos sintéticos: las figuras muestran el comportamiento del modelo, no efectos biológicos.
Requiere los extras `graph`, `baselines`, `demo` y `plots`. Uso:

    python scripts/plot_delivery.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from nutrigraphdt import api  # noqa: E402
from nutrigraphdt.delivery import REPO_ROOT, _git, environment  # noqa: E402
from nutrigraphdt.demo import service  # noqa: E402
from nutrigraphdt.simulation import load_catalog  # noqa: E402

COMMAND = "python scripts/plot_delivery.py"
COMPONENTS = ("acetate", "propionate", "butyrate")
LABELS = {"acetate": "Acetato", "propionate": "Propionato", "butyrate": "n-Butirato"}
SYNTHETIC_NOTE = "Datos sintéticos: comportamiento del modelo, no efectos biológicos."


def scenarios_figure(output: Path) -> dict[str, Any]:
    engine = api.DEMO_RUNS["synthetic"].engine()
    catalog = load_catalog()
    fig, axes = plt.subplots(1, len(catalog), figsize=(3.2 * len(catalog), 3.6), sharey=True)
    for ax, scenario in zip(axes, catalog, strict=True):
        comparison = service.simulate(engine, "synthetic", scenario.request()).comparison
        for offset, (response, color, name) in enumerate(
            (
                (comparison.basal, "#032E54", "basal"),
                (comparison.intervened, "#087F9E", "escenario"),
            )
        ):
            if response.fractions is None:
                continue
            values = [getattr(response.fractions, c) for c in COMPONENTS]
            errors = None
            if response.interval is not None:
                errors = [
                    [
                        v - response.interval.fractions[c].lower
                        for v, c in zip(values, COMPONENTS, strict=True)
                    ],
                    [
                        response.interval.fractions[c].upper - v
                        for v, c in zip(values, COMPONENTS, strict=True)
                    ],
                ]
            ax.bar(
                [i + offset * 0.38 for i in range(3)],
                values,
                width=0.36,
                color=color,
                yerr=errors,
                capsize=2,
                label=name,
            )
        ax.set_title(f"{scenario.id}\n{comparison.status}", fontsize=8)
        ax.set_xticks([i + 0.19 for i in range(3)], [LABELS[c] for c in COMPONENTS], fontsize=7)
    axes[0].set_ylabel("fracción molar")
    axes[0].legend(fontsize=7)
    fig.suptitle(
        "Basal frente a escenario por AGCC (corrida synthetic, intervalo MC-dropout sin calibrar). "
        + SYNTHETIC_NOTE,
        fontsize=8,
    )
    fig.tight_layout()
    path = output / "scenarios.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return {
        "file": path.name,
        "sources": ["configs/scenarios/", "tests/fixtures/api/frozen_runs/synthetic/"],
        "run_id": engine.model_ref.run_id,
    }


def metrics_figure(output: Path) -> dict[str, Any]:
    source = REPO_ROOT / "reports" / "delivery" / "results.json"
    record = json.loads(source.read_text(encoding="utf-8"))
    rows = [(f"entrega {name}", run["metrics"]) for name, run in record["runs"].items()]
    rows += [(p["source"], p["metrics"]) for p in record["previous"] if "A68" in p["source"]]
    metrics = ("fraction_mae_pp", "log_total_mae")
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4))
    for ax, metric in zip(axes, metrics, strict=True):
        names = [name for name, values in rows if values.get(metric) is not None]
        ax.barh(names, [values[metric] for _, values in rows if values.get(metric) is not None])
        ax.set_title(metric, fontsize=9)
        ax.tick_params(labelsize=7)
    fig.suptitle("Métricas de test: entrega frente a A68-P2. " + SYNTHETIC_NOTE, fontsize=8)
    fig.tight_layout()
    path = output / "metrics.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return {"file": path.name, "sources": ["reports/delivery/results.json"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--output", type=Path, default=REPO_ROOT / "reports" / "delivery" / "figures"
    )
    args = parser.parse_args(argv)
    # El estado de git se lee antes de escribir: las figuras nuevas no cuentan como cambios.
    git = {"commit": _git("rev-parse", "HEAD"), "dirty": bool(_git("status", "--porcelain"))}
    args.output.mkdir(parents=True, exist_ok=True)
    figures = [scenarios_figure(args.output), metrics_figure(args.output)]
    provenance = {
        "command": COMMAND,
        "git": git,
        "environment": environment(),
        "figures": figures,
    }
    (args.output / "figures.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Figuras: {[f['file'] for f in figures]} -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
