"""Reproduce de forma independiente una corrida composicional por fold y la compara (A68-P4, #182).

Lee el `run.json` de una corrida guardada por `run_compositional_fold` (#180), reconstruye las
entradas desde archivos versionados (plan de folds, fuentes y grafos de D1, o la cohorte
sintética), reentrena el mismo fold con la misma configuración y semilla, y compara configuración,
escalado, épocas, historial, predicciones, métricas, violaciones y la recarga del checkpoint
original (`nutrigraphdt.models.training.compositional_reproduction`).

Escribe en `--output` (por defecto `reports/constraints/reproducibility/`) un `.md` y un `.json`
con el nombre del `run_id` original.

Uso:
    python scripts/reproduce_compositional_run.py runs/constraints/synthetic/<run_id>
    python scripts/reproduce_compositional_run.py runs/constraints/d1/<run_id> --device cuda

Código de salida: `0` si se reproduce, `1` si alguna comparación difiere y `2` si la entrada no es
válida.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from nutrigraphdt.models.training.compositional_reproduction import (
    report_json,
    report_markdown,
    reproduce_compositional_run,
)
from nutrigraphdt.models.training.cv_inputs import (
    SYNTHETIC_DATASET_ID,
    CVInputs,
    load_d1_cv_inputs,
    load_synthetic_cv_inputs,
)
from nutrigraphdt.models.training.reproducibility import ReproductionError

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = REPO_ROOT / "configs" / "sources.json"
DEFAULT_GRAPHS = REPO_ROOT / "artifacts" / "graphs" / "D1_holofood"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "constraints" / "reproducibility"

EXIT_OK = 0
EXIT_DIFFERS = 1
EXIT_INPUT = 2


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--plan", type=Path, default=None)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--graphs-dir", type=Path, default=DEFAULT_GRAPHS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        info = json.loads((args.run_dir / "run.json").read_text(encoding="utf-8"))
        plan_path = args.plan or REPO_ROOT / str(info["plan"]["file"])

        def load(path: Path) -> CVInputs:
            if info["dataset_id"] == SYNTHETIC_DATASET_ID:
                return load_synthetic_cv_inputs(path)
            return load_d1_cv_inputs(args.sources, args.graphs_dir, path)

        reproduction = reproduce_compositional_run(
            args.run_dir,
            load,
            device=args.device,
            plan_path=plan_path,
            output_runs_dir=args.runs_dir,
        )
    except (FileNotFoundError, KeyError, ValueError, ReproductionError) as error:
        print(f"No se pudo reproducir la corrida: {error}", file=sys.stderr)
        return EXIT_INPUT

    command = "python scripts/reproduce_compositional_run.py " + " ".join(
        argv if argv is not None else sys.argv[1:]
    )
    args.output.mkdir(parents=True, exist_ok=True)
    stem = args.run_dir.name
    markdown = report_markdown(reproduction, command)
    (args.output / f"{stem}.md").write_text(markdown, encoding="utf-8", newline="\n")
    (args.output / f"{stem}.json").write_text(
        json.dumps(report_json(reproduction), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(markdown)
    return EXIT_OK if reproduction.report.reproduced_ok else EXIT_DIFFERS


if __name__ == "__main__":
    raise SystemExit(main())
