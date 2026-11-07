"""Diagnóstico de por qué la GNN no aprovecha el perfil por familia en D1 (#268).

#266 mostró que `ridge` con el perfil por familia mejora a `ridge` sobre el diseño, y que la GNN
con la misma información no. Este script separa las hipótesis sin usar el test para decidir:

1. **`grid`.** Mide la escala de cada bloque en la lectura y las curvas de aprendizaje, y entrena
   una grilla fijada de antemano en las semillas de selección (0 y 1 del plan de #139). Solo lee el
   train de cada fold, repartido en train y val interno. Elige por variante la menor
   `val_data_loss` media, y a igual media, la primera de la grilla (`candidates`, con la
   configuración actual primero).
2. **`evaluate`.** Evalúa una sola vez esa elección en el test de todos los folds y la compara con
   `gnn_functional_lineage`, `ridge_family` y `ridge_design` de `reports/gnn/d1_taxon_identity/`.

Factores de la grilla, uno por hipótesis:

- `profile_block` (escala): el perfil por familia entra estandarizado y directo a la lectura;
- `linear_head` (arquitectura): capa lineal sobre la lectura en lugar del MLP;
- `weight_decay` y `hidden_channels` (ajuste).

Escribe en `--output` (por defecto `reports/gnn/d1_microbiome_diagnosis/`): `diagnostics.json`,
`grid.csv`, `selection.json`, `fold_metrics.csv`, `folds.csv`, `paired.csv`, `report.md` y
`run.json`.

    python scripts/diagnose_gnn_microbiome.py --stage grid --device cuda
    python scripts/diagnose_gnn_microbiome.py --stage evaluate --device cuda

Requiere los extras `graph` y `baselines`. Código de salida: `0` si terminó; `2` si faltan datos.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

import torch

from nutrigraphdt.constraints import D06_PROPIONATE_BOUND_NAME, constraint_catalog
from nutrigraphdt.models.composition import MODEL_OUTPUT_NAMES
from nutrigraphdt.models.cross_validation import aggregate_fold_reports
from nutrigraphdt.models.gnn.batching import for_training
from nutrigraphdt.models.gnn.factory import build_model, load_model_config
from nutrigraphdt.models.metrics import EvaluationReport
from nutrigraphdt.models.paired_comparison import paired_comparison
from nutrigraphdt.models.training import load_training_config, run_compositional_fold
from nutrigraphdt.models.training.compositional import (
    CompositionalTargetTransform,
    split_inner_validation,
    train_compositional_model,
)
from nutrigraphdt.models.training.config import set_seed
from nutrigraphdt.models.training.cv_inputs import CVInputs, load_d1_cv_inputs
from nutrigraphdt.models.training.scaling import FeatureScaler
from nutrigraphdt.models.training.taxon_identity import TaxonIdentityConfig, TaxonLineageEncoder
from nutrigraphdt.models.training.tracking import environment_info, git_info

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = REPO_ROOT / "configs" / "sources.json"
DEFAULT_GRAPHS = REPO_ROOT / "artifacts" / "graphs" / "D1_holofood"
DEFAULT_PLAN = REPO_ROOT / "configs" / "splits" / "d1_holofood_cv.json"
DEFAULT_TRAINING_CONFIG = REPO_ROOT / "configs" / "training" / "default.json"
DEFAULT_MODEL_CONFIGS = REPO_ROOT / "configs" / "models"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "gnn" / "d1_microbiome_diagnosis"
REFERENCE_FOLDS = REPO_ROOT / "reports" / "gnn" / "d1_taxon_identity" / "fold_metrics.csv"

VARIANTS: Final = ("homo_sage", "hetero_sage", "hetero_gat")
SELECTION_SEEDS: Final = (0, 1)
"""Las semillas de selección de #142 y #178."""
TRAIN_SEED_BASE: Final = 42000
INNER_FOLDS: Final = 5
CURVE_EPOCHS: Final = (1, 5, 10, 20, 50, 100, 200)
PRIMARY: Final = "fraction_mae_pp"
METRICS: Final = (PRIMARY, "fraction_r2", "log_total_mae", "reconstructed_mae")
REFERENCES: Final = (
    ("gnn_functional_lineage", "Frente a la configuración actual"),
    ("ridge_family", "Frente a ridge por familia"),
    ("ridge_design", "Frente a ridge sobre el diseño"),
)
GRID_HEADER: Final = [
    "model",
    "candidate",
    "seed",
    "fold",
    "status",
    "best_epoch",
    "epochs_run",
    "val_data_loss",
    "train_data_loss",
    "error",
]
METRIC_COLUMNS: Final = [
    "split",
    "group",
    "metric",
    "acetate",
    "propionate",
    "butyrate",
    "log_total",
    "average",
]
EXIT_OK: Final = 0
EXIT_INPUT: Final = 2


@dataclass(frozen=True)
class Candidate:
    """Una combinación de la grilla; los valores por omisión son la configuración actual."""

    profile_block: bool = False
    linear_head: bool = False
    weight_decay: float = 1e-4
    hidden_channels: int = 64

    @property
    def name(self) -> str:
        return (
            f"profile{int(self.profile_block)}_linear{int(self.linear_head)}"
            f"_wd{self.weight_decay:g}_h{self.hidden_channels}"
        )


def candidates() -> list[Candidate]:
    """La grilla, fijada antes de correr. La primera es la configuración actual."""
    return [
        Candidate(profile_block, linear_head, weight_decay, hidden)
        for profile_block in (False, True)
        for linear_head in (False, True)
        for weight_decay in (1e-4, 1e-2, 1e-1)
        for hidden in (64, 16)
    ]


def _append(path: Path, header: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(header), lineterminator="\n")
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def _train_seed(seed: int, fold: int) -> int:
    return TRAIN_SEED_BASE + seed * 100 + fold


def _inner_split(inputs: CVInputs, seed: int, fold: int) -> tuple[Sequence[str], Sequence[str]]:
    train_ids = inputs.plan.folds(seed)[fold][0]
    return split_inner_validation(
        train_ids, inputs.pens, inputs.diets, seed=_train_seed(seed, fold), inner_folds=INNER_FOLDS
    )


def fit_inner(
    inputs: CVInputs,
    variant: str,
    candidate: Candidate,
    seed: int,
    fold: int,
    training: Any,
) -> Any:
    """Entrena con el train interno de un fold y elige la época con su val interno.

    No lee el test del fold.
    """
    config = training.model_copy(
        update={"seed": _train_seed(seed, fold), "weight_decay": candidate.weight_decay}
    )
    set_seed(config.seed)
    inner_train, inner_val = _inner_split(inputs, seed, fold)
    encoder = TaxonLineageEncoder.fit(
        [inputs.graphs[s] for s in inner_train],
        TaxonIdentityConfig(profile_block=candidate.profile_block),
    )
    train_graphs = encoder.transform([inputs.graphs[s] for s in inner_train])
    val_graphs = encoder.transform([inputs.graphs[s] for s in inner_val])
    scaler = FeatureScaler.fit(train_graphs)
    model = build_model(
        load_model_config(DEFAULT_MODEL_CONFIGS / f"{variant}.yaml").model_copy(
            update={
                "linear_head": candidate.linear_head,
                "hidden_channels": candidate.hidden_channels,
            }
        ),
        encoder.adapt_metadata(inputs.metadata),
        target_names=MODEL_OUTPUT_NAMES,
    )
    return train_compositional_model(
        model,
        scaler.transform([for_training(graph) for graph in train_graphs]),
        scaler.transform([for_training(graph) for graph in val_graphs]),
        config,
        CompositionalTargetTransform.fit(train_graphs),
    )


def readout_scale(inputs: CVInputs, seed: int, fold: int) -> dict[str, float]:
    """Desviación entre animales de la media por grafo de cada bloque, tras escalar."""
    inner_train, _ = _inner_split(inputs, seed, fold)
    train = [inputs.graphs[s] for s in inner_train]
    encoder = TaxonLineageEncoder.fit(train)
    scaled = FeatureScaler.fit(encoder.transform(train)).transform(encoder.transform(train))
    return {
        node_type: float(
            torch.stack([graph[node_type].x.mean(dim=0) for graph in scaled]).std(dim=0).median()
        )
        for node_type in ("taxon", "host", "diet")
    }


def run_grid(
    inputs: CVInputs, variants: Sequence[str], training: Any, output: Path, *, curves: bool = True
) -> None:
    """Corre la grilla y escribe `diagnostics.json`, `grid.csv` y `selection.json`."""
    if curves:
        scales = [readout_scale(inputs, 0, fold) for fold in range(inputs.plan.k)]
        curve_rows = []
        long_run = training.model_copy(update={"patience": training.max_epochs})
        for fold in range(inputs.plan.k):
            result = fit_inner(inputs, "hetero_sage", Candidate(), 0, fold, long_run)
            curve_rows.append(
                {
                    "fold": fold,
                    "best_epoch": result.best_epoch,
                    "epochs": {
                        str(epoch): {
                            "train": result.history[epoch - 1].train_data_loss,
                            "val": result.history[epoch - 1].val_data_loss,
                        }
                        for epoch in CURVE_EPOCHS
                        if epoch <= len(result.history)
                    },
                }
            )
        (output / "diagnostics.json").write_text(
            json.dumps(
                {
                    "readout_scale": {
                        node_type: statistics.median(row[node_type] for row in scales)
                        for node_type in scales[0]
                    },
                    "learning_curves_hetero_sage": curve_rows,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    (output / "grid.csv").unlink(missing_ok=True)
    grid = candidates()
    total = len(variants) * len(grid) * len(SELECTION_SEEDS) * inputs.plan.k
    count = 0
    for variant in variants:
        for candidate in grid:
            for seed in SELECTION_SEEDS:
                for fold in range(inputs.plan.k):
                    count += 1
                    key = {
                        "model": variant,
                        "candidate": candidate.name,
                        "seed": seed,
                        "fold": fold,
                    }
                    try:
                        result = fit_inner(inputs, variant, candidate, seed, fold, training)
                    except (ValueError, RuntimeError) as error:
                        _append(
                            output / "grid.csv",
                            GRID_HEADER,
                            [{**key, "status": "error", "error": str(error).replace("\n", " ")}],
                        )
                        continue
                    best = result.history[result.best_epoch - 1]
                    _append(
                        output / "grid.csv",
                        GRID_HEADER,
                        [
                            {
                                **key,
                                "status": "ok",
                                "best_epoch": result.best_epoch,
                                "epochs_run": result.epochs_run,
                                "val_data_loss": best.val_data_loss,
                                "train_data_loss": best.train_data_loss,
                            }
                        ],
                    )
                    if count % 50 == 0:
                        print(f"[{count}/{total}] {variant} {candidate.name}", flush=True)
    selection = select(_read_csv(output / "grid.csv"), variants)
    (output / "selection.json").write_text(
        json.dumps(selection, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def select(rows: Sequence[Mapping[str, str]], variants: Sequence[str]) -> dict[str, Any]:
    """Menor `val_data_loss` media por variante, solo con los folds que terminaron todos.

    A igual media gana la primera de la grilla. También resume cada factor, promediando sobre los
    demás, para ver qué hipótesis mueve la pérdida de validación.
    """
    order = {candidate.name: position for position, candidate in enumerate(candidates())}
    by_name = {candidate.name: candidate for candidate in candidates()}
    result: dict[str, Any] = {"criterion": "val_data_loss_mean", "selections": {}}
    for variant in variants:
        losses: dict[str, list[float]] = {}
        for row in rows:
            if row["model"] == variant and row["status"] == "ok":
                losses.setdefault(row["candidate"], []).append(float(row["val_data_loss"]))
        complete = {
            name: statistics.fmean(values)
            for name, values in losses.items()
            if len(values) == max(len(v) for v in losses.values())
        }
        chosen = min(complete, key=lambda name: (complete[name], order[name]))
        baseline = Candidate().name
        factors: dict[str, dict[str, float]] = {}
        for factor in ("profile_block", "linear_head", "weight_decay", "hidden_channels"):
            groups: dict[str, list[float]] = {}
            for name, value in complete.items():
                groups.setdefault(str(getattr(by_name[name], factor)), []).append(value)
            factors[factor] = {
                level: statistics.fmean(values) for level, values in sorted(groups.items())
            }
        result["selections"][variant] = {
            "candidate": chosen,
            "config": asdict(by_name[chosen]),
            "val_data_loss": complete[chosen],
            "baseline_val_data_loss": complete.get(baseline),
            "factors": factors,
        }
    return result


def run_evaluate(
    inputs: CVInputs,
    variants: Sequence[str],
    training: Any,
    output: Path,
    selection: Mapping[str, Any],
) -> dict[str, dict[tuple[int, int], EvaluationReport]]:
    """Evalúa la elección de cada variante en el test de todos los folds."""
    for name in ("fold_metrics.csv", "folds.csv"):
        (output / name).unlink(missing_ok=True)
    monitored = (constraint_catalog()[D06_PROPIONATE_BOUND_NAME],)
    reports: dict[str, dict[tuple[int, int], EvaluationReport]] = {}
    for variant in variants:
        candidate = Candidate(**selection["selections"][variant]["config"])
        model_config = load_model_config(DEFAULT_MODEL_CONFIGS / f"{variant}.yaml").model_copy(
            update={
                "linear_head": candidate.linear_head,
                "hidden_channels": candidate.hidden_channels,
            }
        )
        for seed in inputs.plan.seeds:
            for fold, (train_ids, test_ids) in enumerate(inputs.plan.folds(seed)):
                train_seed = _train_seed(seed, fold)
                evaluation = run_compositional_fold(
                    seed=seed,
                    fold=fold,
                    model_name=variant,
                    edges_arm="selected",
                    train_ids=train_ids,
                    test_ids=test_ids,
                    graphs=inputs.graphs,
                    pens=inputs.pens,
                    diets=inputs.diets,
                    days=inputs.days,
                    model_config=model_config,
                    metadata=inputs.metadata,
                    config=training.model_copy(
                        update={"seed": train_seed, "weight_decay": candidate.weight_decay}
                    ),
                    monitor_constraints=monitored,
                    taxon_identity=TaxonIdentityConfig(profile_block=candidate.profile_block),
                )
                reports.setdefault(variant, {})[(seed, fold)] = evaluation.report
                key = {"seed": seed, "fold": fold, "model": variant}
                _append(
                    output / "fold_metrics.csv",
                    ["seed", "fold", "model", *METRIC_COLUMNS],
                    [{**key, **record} for record in evaluation.report.to_records()],
                )
                test_rate = next(
                    row.violation_rate_percent
                    for row in evaluation.violations
                    if row.subset == "test" and row.constraint == D06_PROPIONATE_BOUND_NAME
                )
                _append(
                    output / "folds.csv",
                    [
                        "seed",
                        "fold",
                        "model",
                        "train_seed",
                        "best_epoch",
                        "epochs_run",
                        "n_test",
                        "d06_test_violation_rate_percent",
                    ],
                    [
                        {
                            **key,
                            "train_seed": train_seed,
                            "best_epoch": evaluation.best_epoch,
                            "epochs_run": evaluation.epochs_run,
                            "n_test": evaluation.n_test,
                            "d06_test_violation_rate_percent": test_rate,
                        }
                    ],
                )
            print(f"{variant}: semilla {seed} lista.", flush=True)
    return reports


def _reference_by_fold(path: Path, arm: str, model: str | None, metric: str) -> dict:
    values: dict[tuple[int, int], float] = {}
    for row in _read_csv(path):
        if (
            row["arm"] == arm
            and (model is None or row["model"] == model)
            and row["metric"] == metric
            and row["group"] in ("", "all")
        ):
            values[(int(row["seed"]), int(row["fold"]))] = float(row["average"])
    return values


def _by_fold(reports: Mapping[tuple[int, int], EvaluationReport], metric: str) -> dict:
    return {
        key: float(row.average)
        for key, report in reports.items()
        for row in report.rows
        if row.metric == metric and row.group in (None, "all")
    }


def paired_rows(
    reports: Mapping[str, Mapping[tuple[int, int], EvaluationReport]],
    reference_path: Path,
    ratio: float,
) -> list[dict[str, Any]]:
    """`elegida − referencia` por fold, frente a los brazos de #266."""
    rows: list[dict[str, Any]] = []
    for variant, folds in reports.items():
        for arm, description in REFERENCES:
            model = variant if arm.startswith("gnn") else None
            for metric in METRICS:
                base = _reference_by_fold(reference_path, arm, model, metric)
                values = _by_fold(folds, metric)
                keys = sorted(set(base) & set(values))
                if len(keys) < 2:
                    continue
                result = paired_comparison({k: values[k] - base[k] for k in keys}, ratio)
                rows.append(
                    {
                        "comparison": description,
                        "model": variant,
                        "reference": arm,
                        "metric": metric,
                        "selected_mean": statistics.fmean(values[k] for k in keys),
                        "reference_mean": statistics.fmean(base[k] for k in keys),
                        **result.to_dict(),
                    }
                )
    return rows


def _cell(aggregate: EvaluationReport, metric: str) -> str:
    values = {row.metric: row.average for row in aggregate.rows if row.group in (None, "all")}
    mean, std = values.get(f"{metric}_mean"), values.get(f"{metric}_std")
    return "—" if mean is None or std is None else f"{mean:.2f} ± {std:.2f}"


def _p_value(value: float) -> str:
    """Con los dos brazos idénticos no hay estadístico: la elegida es la configuración actual."""
    return "—" if math.isnan(value) else f"{value:.3f}"


def build_report(context: Mapping[str, Any]) -> str:
    """`report.md` con la selección, la evaluación y las comparaciones pareadas."""
    selection = context["selection"]["selections"]
    diagnostics = context["diagnostics"]
    lines = [
        "# Por qué la GNN no aprovecha el perfil por familia en D1: diagnóstico (#268)",
        "",
        "Generado con `python scripts/diagnose_gnn_microbiome.py`. La interpretación está en "
        "[`gnn-microbiome-diagnosis.md`](../../../docs/models/gnn-microbiome-diagnosis.md).",
        "",
        "## Escala de la lectura (solo train interno)",
        "",
        "Desviación entre animales de la media por grafo de cada columna, tras escalar (mediana):",
        "",
        "| Bloque | Desviación |",
        "|---|---:|",
        *[f"| `{name}` | {value:.3f} |" for name, value in diagnostics["readout_scale"].items()],
        "",
        "## Curvas de `hetero_sage` sin detención temprana (solo train y val interno)",
        "",
        "| Fold | Mejor época | "
        + " | ".join(f"Época {epoch}: train / val" for epoch in CURVE_EPOCHS)
        + " |",
        "|---:|---:|" + "---|" * len(CURVE_EPOCHS),
    ]
    for row in diagnostics["learning_curves_hetero_sage"]:
        cells = " | ".join(
            f"{row['epochs'][str(epoch)]['train']:.2f} / {row['epochs'][str(epoch)]['val']:.2f}"
            for epoch in CURVE_EPOCHS
        )
        lines.append(f"| {row['fold']} | {row['best_epoch']} | {cells} |")
    lines += [
        "",
        "## Grilla: `val_data_loss` media (semillas 0 y 1; el test no interviene)",
        "",
        "| Variante | Configuración actual | Elegida | Pérdida elegida |",
        "|---|---:|---|---:|",
    ]
    for variant, entry in selection.items():
        lines.append(
            f"| `{variant}` | {entry['baseline_val_data_loss']:.4f} | `{entry['candidate']}` | "
            f"{entry['val_data_loss']:.4f} |"
        )
    lines += [
        "",
        "Efecto de cada factor, promediando sobre los demás:",
        "",
        "| Variante | Factor | Nivel y pérdida media |",
        "|---|---|---|",
    ]
    for variant, entry in selection.items():
        for factor, levels in entry["factors"].items():
            text = ", ".join(f"{level}: {value:.4f}" for level, value in levels.items())
            lines.append(f"| `{variant}` | `{factor}` | {text} |")
    lines += [
        "",
        "## Evaluación única en el test de los folds",
        "",
        "| Variante | Configuración | `fraction_mae_pp` | `fraction_r2` | `log_total_mae` | "
        "`reconstructed_mae` |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for variant, aggregate in context["aggregates"].items():
        cells = " | ".join(_cell(aggregate, metric) for metric in METRICS)
        lines.append(f"| `{variant}` | `{selection[variant]['candidate']}` | {cells} |")
    lines += [
        "",
        f"Violaciones de la cota de D-06 en el test: {context['violations']} de "
        f"{context['folds']} folds con VR > 0.",
        "",
        "## Comparaciones pareadas de `fraction_mae_pp`",
        "",
        "`Δ = elegida − referencia`, con el t corregido de Nadeau y Bengio; negativo favorece a la "
        "elegida. Las demás métricas están en `paired.csv`.",
        "",
        "| Comparación | Variante | Elegida | Referencia | Δ | IC 95 % | p |",
        "|---|---|---:|---:|---:|---|---:|",
    ]
    for row in context["paired"]:
        if row["metric"] == PRIMARY:
            lines.append(
                f"| {row['comparison']} | `{row['model']}` | {row['selected_mean']:.2f} | "
                f"{row['reference_mean']:.2f} | {row['mean_delta']:+.2f} | "
                f"[{row['ci_low']:+.2f}; {row['ci_high']:+.2f}] | {_p_value(row['p_value'])} |"
            )
    lines += [
        "",
        "## Limitaciones",
        "",
        "- Es un análisis exploratorio motivado por el resultado de #266: la evaluación es única, "
        "pero no independiente de lo que ya se había visto en ese test.",
        "- La selección usa 10 folds con unos 9 animales de val interno; la pérdida es ruidosa, y "
        "la mejor época de cada fold la vuelve optimista.",
        "- Ninguna evaluación de D1 se llama «mecanística» (#256).",
        "",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--stage", choices=("grid", "evaluate"), required=True)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--graphs-dir", type=Path, default=DEFAULT_GRAPHS)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--training-config", type=Path, default=DEFAULT_TRAINING_CONFIG)
    parser.add_argument("--reference-folds", type=Path, default=REFERENCE_FOLDS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS))
    parser.add_argument("--device", type=str, default=None)
    args = parser.parse_args(argv)

    started = time.monotonic()
    try:
        inputs = load_d1_cv_inputs(args.sources, args.graphs_dir, args.plan)
        training = load_training_config(args.training_config).model_copy(
            update={
                "dataset_id": inputs.dataset_id,
                **({"device": args.device} if args.device else {}),
            }
        )
        args.output.mkdir(parents=True, exist_ok=True)
        selection_path = args.output / "selection.json"
        if args.stage == "evaluate" and not selection_path.exists():
            raise FileNotFoundError(f"Falta {selection_path}: corra antes --stage grid.")
    except (FileNotFoundError, KeyError, ValueError) as error:
        print(f"No se pudo preparar el diagnóstico: {error}", file=sys.stderr)
        return EXIT_INPUT

    if args.stage == "grid":
        run_grid(inputs, args.variants, training, args.output)
        print(selection_path.read_text(encoding="utf-8"))
        return EXIT_OK

    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    reports = run_evaluate(inputs, args.variants, training, args.output, selection)
    aggregates = {variant: aggregate_fold_reports(folds) for variant, folds in reports.items()}
    ratio = statistics.fmean(
        len(test) / len(train)
        for seed in inputs.plan.seeds
        for train, test in inputs.plan.folds(seed)
    )
    paired = paired_rows(reports, args.reference_folds, ratio)
    with (args.output / "paired.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(paired[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(paired)
    fold_rows = _read_csv(args.output / "folds.csv")
    elapsed = time.monotonic() - started
    report = build_report(
        {
            "selection": selection,
            "diagnostics": json.loads((args.output / "diagnostics.json").read_text("utf-8")),
            "aggregates": aggregates,
            "paired": paired,
            "folds": len(fold_rows),
            "violations": sum(
                float(row["d06_test_violation_rate_percent"]) > 0 for row in fold_rows
            ),
        }
    )
    (args.output / "report.md").write_text(report, encoding="utf-8", newline="\n")
    (args.output / "run.json").write_text(
        json.dumps(
            {
                "issue": 268,
                "dataset_id": inputs.dataset_id,
                "command": "python scripts/diagnose_gnn_microbiome.py",
                "grid": [asdict(candidate) for candidate in candidates()],
                "selection_seeds": list(SELECTION_SEEDS),
                "seeds": list(inputs.plan.seeds),
                "k": inputs.plan.k,
                "cohort": dict(inputs.cohort),
                "training_config": training.model_dump(mode="json"),
                "train_seed_base": TRAIN_SEED_BASE,
                "test_train_ratio": ratio,
                "evaluate_elapsed_seconds": round(elapsed, 1),
                "git": git_info(REPO_ROOT),
                "environment": environment_info(training.device),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(report)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
