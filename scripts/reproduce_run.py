"""Reproduce una corrida registrada a partir de su `run.json` y la compara (A45-8, #108).

1. Lee la configuración de entrenamiento, la del modelo, la semilla y la fuente de datos del
   `run.json` original, y reentrena con `scripts/train_gnn.py` en un proceso aparte, como lo haría
   una persona.
2. Compara la corrida nueva con la original (`nutrigraphdt.models.training.reproducibility`):
   configuración, datos, escalado, épocas, historia, métricas y predicciones. Si la carpeta
   original no está disponible (por ejemplo, solo se versionó la copia de su `run.json`), las
   métricas se comparan con las filas de la variante en `reports/gnn/<dataset>/report.csv`.
3. Recarga el checkpoint nuevo con `load_run` (y el original, si está) y verifica que reproduce
   sus `predictions.csv`.
4. Escribe `reports/gnn/reproducibility/<dataset>_<variante>.md` y `.json`.

Uso:

    python scripts/reproduce_run.py reports/gnn/synthetic/run_homo_sage.json
    python scripts/reproduce_run.py runs/<run_id>

Requiere los extras `graph` y, para la cohorte sintética, `baselines`. Código de salida: `0` si se
reproduce, `1` si alguna comparación difiere y `2` si la entrada no es válida.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from nutrigraphdt.models.training.reproducibility import (
    DIFFERS,
    HISTORY_FILE,
    METRICS_FILE,
    METRICS_TOLERANCE,
    OK,
    PREDICTIONS_FILE,
    PREDICTIONS_TOLERANCE,
    RELOAD_TOLERANCE,
    UNAVAILABLE,
    WEIGHTS_TOLERANCE,
    Check,
    ReproductionError,
    ReproductionReport,
    compare_info,
    compare_rows,
    only_splits,
    read_csv,
    read_run_info,
    report_rows,
    sibling,
    split_file_digests,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
TRAIN_SCRIPT = REPO_ROOT / "scripts" / "train_gnn.py"
DEFAULT_RUNS_DIR = REPO_ROOT / "runs" / "reproduce"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "gnn" / "reproducibility"
COMMAND = "python scripts/reproduce_run.py <run.json>"
EXIT_OK, EXIT_DIFFERS, EXIT_INPUT = 0, 1, 2
PREDICTION_KEY = ("sample_id", "subset")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("original", type=Path, help="Carpeta de la corrida o su run.json.")
    parser.add_argument(
        "--reproduced",
        type=Path,
        default=None,
        help="Corrida ya reproducida: compara sin reentrenar.",
    )
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="report.csv para comparar métricas si falta el metrics.csv original "
        "(por defecto, reports/gnn/<dataset>/report.csv).",
    )
    parser.add_argument(
        "--graphs-dir",
        type=Path,
        default=None,
        help="Grafos de D1 (por defecto, los de `source.graphs` del run.json).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        original_dir, original = read_run_info(args.original)
        dataset = str(original["source"].get("dataset"))
        if dataset not in {"synthetic", "d1"}:
            raise ReproductionError(f"source.dataset desconocido: {dataset!r}.")
        new_dir = args.reproduced or retrain(original, args)
        _, new = read_run_info(new_dir)
    except (ReproductionError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return EXIT_INPUT

    report_csv = args.report or REPO_ROOT / "reports" / "gnn" / dataset / "report.csv"
    checks = compare_info(original, new, split_digests=_split_digests(original))
    checks += compare_files(original_dir, original, new_dir, new, report_csv)
    checks.append(
        reload_check(
            "Recarga del checkpoint reproducido (load_run)", new_dir, new, args, RELOAD_TOLERANCE
        )
    )
    original_checkpoint = sibling(original_dir, original, "checkpoint", "checkpoint.pt")
    if original_dir is not None and original_checkpoint is not None:
        checks.append(weights_check(original_checkpoint, new_dir / "checkpoint.pt"))
        # Las predicciones originales se calcularon en el otro equipo: tolerancia entre equipos.
        checks.append(
            reload_check(
                "Recarga del checkpoint original (load_run)",
                original_dir,
                original,
                args,
                PREDICTIONS_TOLERANCE,
            )
        )
    else:
        for name in ("Pesos del checkpoint", "Recarga del checkpoint original (load_run)"):
            checks.append(Check(name, UNAVAILABLE, "falta el checkpoint.pt original"))
    notes = []
    if original_dir is None:
        notes.append(
            f"Solo se dispuso de `{_display(args.original)}`: la carpeta original (historia, "
            "predicciones y checkpoint) no está versionada. Las métricas se compararon con "
            f"`{_display(report_csv)}`, que copia `val` y `test` de su `metrics.csv`."
        )
    report = ReproductionReport(original, new, tuple(checks), tuple(notes))

    args.output.mkdir(parents=True, exist_ok=True)
    stem = f"{dataset}_{original['variant']}"
    (args.output / f"{stem}.md").write_text(report.to_markdown(COMMAND), encoding="utf-8")
    (args.output / f"{stem}.json").write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for check in report.checks:
        print(f"[{check.status}] {check.name}" + (f": {check.detail}" if check.detail else ""))
    verdict = "se reproduce" if report.reproduced_ok else "NO se reproduce"
    print(f"{original['run_id']} {verdict}. Reporte en {_display(args.output / stem)}.md/.json")
    return EXIT_OK if report.reproduced_ok else EXIT_DIFFERS


# ---------------------------------------------------------------------------
# Reentrenamiento
# ---------------------------------------------------------------------------


def train_arguments(original: Mapping[str, Any], config: Path, model_config: Path) -> list[str]:
    """Argumentos de `train_gnn.py` que reproducen la corrida; todo sale de `run.json`."""
    source = original["source"]
    argv = [
        "--model",
        str(original["variant"]),
        "--dataset",
        str(source["dataset"]),
        "--config",
        str(config),
        "--model-config",
        str(model_config),
    ]
    if source["dataset"] == "synthetic":
        for key in ("n_samples", "first_seed", "split_seed"):
            argv += [f"--{key.replace('_', '-')}", str(source[key])]
    return argv


def retrain(original: Mapping[str, Any], args: argparse.Namespace) -> Path:
    runs_dir = Path(args.runs_dir) / str(original["run_id"])
    before = set(runs_dir.iterdir()) if runs_dir.is_dir() else set()
    with tempfile.TemporaryDirectory() as tmp:
        config = Path(tmp) / "training.json"
        config.write_text(json.dumps(original["training_config"]), encoding="utf-8")
        model_config = Path(tmp) / "model.yaml"
        # JSON es YAML válido: no hace falta PyYAML para escribirlo.
        model_config.write_text(json.dumps(original["model_config"]), encoding="utf-8")
        argv = train_arguments(original, config, model_config) + ["--runs-dir", str(runs_dir)]
        if original["source"]["dataset"] == "d1":
            argv += ["--graphs-dir", str(_graphs_dir(original, args))]
        print("Reentrenando: python scripts/train_gnn.py " + " ".join(_short(a) for a in argv))
        completed = subprocess.run(
            [sys.executable, str(TRAIN_SCRIPT), *argv], cwd=REPO_ROOT, check=False
        )
    if completed.returncode != 0:
        raise ReproductionError(f"train_gnn.py terminó con código {completed.returncode}.")
    created = sorted(set(runs_dir.iterdir()) - before)
    if len(created) != 1:
        raise ReproductionError(f"Se esperaba una corrida nueva en {runs_dir}.")
    return created[0]


# ---------------------------------------------------------------------------
# Comparación de archivos y recarga
# ---------------------------------------------------------------------------


def compare_files(
    original_dir: Path | None,
    original: Mapping[str, Any],
    new_dir: Path,
    new: Mapping[str, Any],
    report_csv: Path,
) -> list[Check]:
    def rows(directory: Path | None, info: Mapping[str, Any], key: str, default: str) -> Any:
        path = sibling(directory, info, key, default)
        return read_csv(path) if path is not None else None

    new_history = rows(new_dir, new, "history", HISTORY_FILE)
    new_metrics = rows(new_dir, new, "metrics", METRICS_FILE)
    new_predictions = rows(new_dir, new, "predictions", PREDICTIONS_FILE)
    if new_history is None or new_metrics is None or new_predictions is None:
        raise ReproductionError(f"{new_dir}: faltan archivos de la corrida reproducida.")

    checks = [
        compare_rows(
            "Historia por época (history.csv)",
            rows(original_dir, original, "history", HISTORY_FILE),
            new_history,
            ("epoch",),
            PREDICTIONS_TOLERANCE,
        )
    ]
    original_metrics = rows(original_dir, original, "metrics", METRICS_FILE)
    if original_metrics is not None:
        checks.append(
            compare_rows(
                "Métricas (metrics.csv)",
                original_metrics,
                new_metrics,
                ("model", "split", "metric"),
                METRICS_TOLERANCE,
            )
        )
    else:
        checks.append(
            compare_rows(
                f"Métricas val y test ({_display(report_csv)})",
                report_rows(report_csv, str(original["variant"])),
                only_splits(new_metrics, {"val", "test"}),
                ("split", "metric"),
                METRICS_TOLERANCE,
                missing_reason=f"falta metrics.csv y {_display(report_csv)} no tiene la variante",
            )
        )
    checks.append(
        compare_rows(
            "Predicciones (predictions.csv)",
            rows(original_dir, original, "predictions", PREDICTIONS_FILE),
            new_predictions,
            PREDICTION_KEY,
            PREDICTIONS_TOLERANCE,
        )
    )
    return checks


def reload_check(
    name: str,
    run_dir: Path,
    info: Mapping[str, Any],
    args: argparse.Namespace,
    tolerance: float,
) -> Check:
    """Recarga el checkpoint con `load_run`, predice de nuevo y compara con `predictions.csv`."""
    try:
        records = reload_predictions(run_dir, info, args)
    except (ImportError, OSError, ValueError, KeyError) as error:
        return Check(name, UNAVAILABLE, f"no se pudo recargar: {error}")
    saved = read_csv(run_dir / PREDICTIONS_FILE)
    return compare_rows(name, saved, records, PREDICTION_KEY, tolerance)


def weights_check(original: Path, new: Path) -> Check:
    """Diferencia máxima entre los pesos guardados de ambas corridas (mismos nombres y formas)."""
    import torch

    name = "Pesos del checkpoint"
    a = torch.load(original, map_location="cpu", weights_only=True)
    b = torch.load(new, map_location="cpu", weights_only=True)
    if a.keys() != b.keys() or any(a[k].shape != b[k].shape for k in a):
        return Check(name, DIFFERS, "parámetros distintos", tolerance=WEIGHTS_TOLERANCE)
    diffs = [float((a[k].double() - b[k].double()).abs().max()) for k in a if a[k].numel()]
    worst = max(diffs, default=0.0)
    status = OK if worst <= WEIGHTS_TOLERANCE else DIFFERS
    return Check(name, status, f"{len(a)} tensores", worst, WEIGHTS_TOLERANCE)


def _split_digests(info: Mapping[str, Any]) -> frozenset[str] | None:
    split = info.get("split")
    file = split.get("file") if isinstance(split, Mapping) else None
    if not isinstance(file, str):
        return None
    path = REPO_ROOT / file
    return split_file_digests(path) if path.is_file() else None


def reload_predictions(
    run_dir: Path, info: Mapping[str, Any], args: argparse.Namespace
) -> list[dict[str, str]]:
    from torch_geometric.loader import DataLoader

    from nutrigraphdt.models.training import load_run, predict
    from nutrigraphdt.models.training.pipeline import scale_loaders

    run = load_run(run_dir)
    config = run.training_config
    prepared = load_prepared(info, args, config)
    scaled = scale_loaders(
        prepared, run.feature_scaler, batch_size=config.batch_size, seed=config.seed
    )
    records: list[dict[str, str]] = []
    for subset in ("train", "val", "test"):
        graphs = list(scaled.graphs[subset])
        if not graphs:
            continue
        loader = DataLoader(graphs, batch_size=config.batch_size)
        for record in predict(run.model, loader, run.target_scaler).to_records(subset):
            records.append({k: "" if v is None else str(v) for k, v in record.items()})
    return records


def load_prepared(info: Mapping[str, Any], args: argparse.Namespace, config: Any) -> Any:
    """Los mismos grafos y partición que `train_gnn.py`, a partir de `source` del run.json."""
    from nutrigraphdt.data.split import create_split, get_split
    from nutrigraphdt.graph.heterodata import build_synthetic_graphs, load_graphs
    from nutrigraphdt.models.training import prepare_training_graphs

    source = info["source"]
    if source["dataset"] == "synthetic":
        # scikit-learn solo se necesita para la cohorte sintética.
        from nutrigraphdt.models.baselines import SYNTHETIC_COHORT_ID, build_synthetic_cohort

        cohort = build_synthetic_cohort(int(source["n_samples"]), int(source["first_seed"]))
        split = create_split(
            [
                {"sample_id": inst.sample_id, "diet_treatment": inst.diet_treatment}
                for inst in cohort.instances
            ],
            group_key=None,
            stratify_key="diet_treatment",
            seed=int(source["split_seed"]),
            dataset_id=SYNTHETIC_COHORT_ID,
        )
        built = build_synthetic_graphs(cohort)
        return prepare_training_graphs(
            built.dataset, built.graphs, split, batch_size=config.batch_size, seed=config.seed
        )
    graphs_dir = _graphs_dir(info, args)
    report = json.loads((graphs_dir / "report.json").read_text(encoding="utf-8"))
    status = report["validation"]["graphs"]
    graphs = {
        graph_id: graph
        for graph_id, graph in load_graphs(graphs_dir / "graphs").items()
        if status.get(graph_id, {}).get("deliverable", False)
    }
    split = get_split(split_file=config.split_file)
    return prepare_training_graphs(
        None, graphs, split, validated=True, batch_size=config.batch_size, seed=config.seed
    )


def _graphs_dir(info: Mapping[str, Any], args: argparse.Namespace) -> Path:
    if args.graphs_dir is not None:
        return Path(args.graphs_dir)
    return REPO_ROOT / str(info["source"].get("graphs", "artifacts/graphs/D1_holofood"))


def _display(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _short(value: str) -> str:
    return Path(value).name if Path(value).is_absolute() else value


if __name__ == "__main__":
    raise SystemExit(main())
