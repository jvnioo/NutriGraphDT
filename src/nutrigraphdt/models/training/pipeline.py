"""Entrenamiento de principio a fin de una variante GNN (A44-6, #100).

Integra la preparación de grafos (A44-1), el escalado (A44-2), el bucle (A44-3), la
configuración y las semillas (A44-4), la trazabilidad (A44-5) y la fábrica de modelos (A41-8).
`scripts/train_gnn.py` es la entrada de línea de comandos; `run_training` es la misma secuencia
para usarla desde Python o desde tests.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import torch
from torch_geometric.loader import DataLoader

from nutrigraphdt.data.split import DatasetSplit
from nutrigraphdt.models.gnn.factory import GNNModelConfig, build_model
from nutrigraphdt.models.metrics import EvaluationReport, combine_reports
from nutrigraphdt.models.training.config import TrainingConfig, set_seed
from nutrigraphdt.models.training.dataloaders import PreparedDataLoaders
from nutrigraphdt.models.training.loop import TrainingResult, predict, train_model
from nutrigraphdt.models.training.scaling import FeatureScaler, TargetScaler
from nutrigraphdt.models.training.tracking import DEFAULT_RUNS_DIR, RunRecord, save_run

SUBSETS: Final[tuple[str, ...]] = ("train", "val", "test")


@dataclass(frozen=True)
class TrainingRun:
    """Resultado de `run_training`: directorio de la corrida, entrenamiento y métricas."""

    run_dir: Path
    result: TrainingResult
    report: EvaluationReport
    loaders: PreparedDataLoaders
    feature_scaler: FeatureScaler
    target_scaler: TargetScaler


def scale_loaders(
    prepared: PreparedDataLoaders, feature_scaler: FeatureScaler, *, batch_size: int, seed: int
) -> PreparedDataLoaders:
    """Aplica `feature_scaler` a los grafos de los tres subconjuntos y rehace los `DataLoader`.

    `train` se baraja con un `torch.Generator` sembrado con `seed`, como en
    `prepare_training_graphs`; `val` y `test` no se barajan. El target queda en las unidades de
    la fuente: lo estandariza el bucle con `TargetScaler`.
    """
    scaled = {subset: feature_scaler.transform(prepared.graphs[subset]) for subset in SUBSETS}
    return dataclasses.replace(
        prepared,
        train=DataLoader(
            scaled["train"],
            batch_size=batch_size,
            shuffle=bool(scaled["train"]),
            generator=torch.Generator().manual_seed(seed) if scaled["train"] else None,
        ),
        val=DataLoader(scaled["val"], batch_size=batch_size, shuffle=False),
        test=DataLoader(scaled["test"], batch_size=batch_size, shuffle=False),
        graphs={subset: tuple(graphs) for subset, graphs in scaled.items()},
    )


def run_training(
    prepared: PreparedDataLoaders,
    model_config: GNNModelConfig,
    config: TrainingConfig,
    split: DatasetSplit,
    *,
    split_file: str | Path | None,
    runs_dir: str | Path = DEFAULT_RUNS_DIR,
    repo_root: str | Path | None = None,
    source: Mapping[str, Any] | None = None,
) -> TrainingRun:
    """Escala con `train`, entrena, evalúa los tres subconjuntos y registra la corrida.

    `prepared` sale de `prepare_training_graphs` con features y target sin escalar. Fija la
    semilla de `config` antes de construir los `DataLoader` y el modelo.

    Raises:
        ValueError: si `train` o `val` no tienen grafos o AGCC suficientes (ver `train_model`).
    """
    if config.constraint_lambda > 0:
        raise ValueError(
            "El pipeline de entrenamiento GNN clásico no admite constraint_lambda > 0; "
            "use el pipeline con objetivo composicional."
        )
    if not prepared.graphs.get("train"):
        raise ValueError("train no tiene grafos con AGCC; no se puede entrenar.")
    set_seed(config.seed)
    feature_scaler = FeatureScaler.fit(prepared.graphs["train"])
    target_scaler = TargetScaler.fit(list(prepared.graphs["train"]))
    loaders = scale_loaders(
        prepared, feature_scaler, batch_size=config.batch_size, seed=config.seed
    )
    model = build_model(model_config, loaders.metadata)
    variant = model_config.variant
    result = train_model(model, loaders, config, target_scaler, model_name=variant)

    reports: list[EvaluationReport] = []
    predictions: list[dict[str, Any]] = []
    for subset in SUBSETS:
        if not loaders.graphs[subset]:
            continue
        # Sin barajar, también train: predictions.csv sigue el orden de los grafos.
        loader = DataLoader(list(loaders.graphs[subset]), batch_size=config.batch_size)
        subset_predictions = predict(result.model, loader, target_scaler)
        predictions.extend(subset_predictions.to_records(subset))
        if bool(subset_predictions.complete.any()):
            reports.append(subset_predictions.evaluate(variant, split=subset))
    report = combine_reports(reports)

    run_dir = save_run(
        RunRecord(
            model=result.model,
            model_config=model_config,
            training_config=config,
            feature_scaler=feature_scaler,
            target_scaler=target_scaler,
            split=split,
            split_file=split_file,
            summary=prepared.summary,
            history=[record.to_dict() for record in result.history],
            metrics=report,
            predictions=predictions,
            best_epoch=result.best_epoch,
            stopped_early=result.stopped_early,
            duration_seconds=result.duration_seconds,
            source=dict(source or {}),
        ),
        runs_dir,
        repo_root=repo_root,
    )
    return TrainingRun(
        run_dir=run_dir,
        result=result,
        report=report,
        loaders=loaders,
        feature_scaler=feature_scaler,
        target_scaler=target_scaler,
    )


__all__ = ["SUBSETS", "TrainingRun", "run_training", "scale_loaders"]
