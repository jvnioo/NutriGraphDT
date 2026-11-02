"""Barrido acotado de λ con selección solo por validación interna (A68-P1, #178).

El protocolo de A55-P1 (`docs/models/constraints-evaluation-protocol.md` §1.3) exige que λ se
elija **solo** con el val interno del train de los folds de las semillas de selección, sin que
el test de ningún fold intervenga. Este módulo:

1. lee la configuración versionada del barrido (`LambdaSweepConfig`, por ejemplo
   `configs/constraints/lambda_sweep_d1.json`), fijada **antes** de correr: grilla, términos de
   la pérdida, semillas de selección, variantes, épocas, presupuesto, criterio y desempate;
2. comprueba el presupuesto antes de entrenar (`trainings_needed`);
3. entrena cada `(variante, λ, semilla, fold)` con `train_compositional_model` sobre el train
   interno y el val interno del **train** del fold (`run_lambda_sweep`), y registra cada
   configuración, también las fallidas (`SweepRow`);
4. elige λ del brazo restringido por variante (`select_lambdas`). Las candidatas son las
   λ > 0 de la grilla; λ = 0 es el brazo libre $M_0$ del protocolo y se entrena como referencia
   en los mismos folds, pero no se elige. El criterio tiene tres pasos:
   - **factibilidad:** se descartan las λ con alguna violación de `feasibility_constraint` en el
     val interno (VR > 0) en la mejor época de algún fold, como en el paso 1 de §5 reescrito
     por P-07; si ninguna es factible, se informa y se sigue con todas;
   - **calidad predictiva:** menor media de `val_data_loss` (MSE estandarizado del objetivo, sin
     la penalización) entre los folds; solo cuentan las λ que entrenaron en todos los folds;
   - **desempate:** a igual media, la menor λ (la que menos interviene).

`run_lambda_sweep` recibe del plan solo el train de cada fold: el test no se le entrega.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from torch_geometric.data import HeteroData

from nutrigraphdt.constraints import constraint_catalog
from nutrigraphdt.models.composition import MODEL_OUTPUT_NAMES
from nutrigraphdt.models.cross_validation import PenFoldPlan
from nutrigraphdt.models.gnn.base import GraphMetadata
from nutrigraphdt.models.gnn.factory import MODEL_VARIANTS, GNNModelConfig, build_model
from nutrigraphdt.models.training.compositional import (
    VAL_SUBSET,
    CompositionalTargetTransform,
    split_inner_validation,
    train_compositional_model,
)
from nutrigraphdt.models.training.config import TrainingConfig, set_seed
from nutrigraphdt.models.training.scaling import FeatureScaler

SWEEP_FORMAT_VERSION: Final[str] = "1.0.0"
CRITERION: Final[str] = "val_data_loss_mean"
TIE_BREAK: Final[str] = "smallest_lambda"


class LambdaSweepConfigError(ValueError):
    """Configuración del barrido inválida; el mensaje nombra el origen y los campos."""


class LambdaSweepConfig(BaseModel):
    """Configuración versionada del barrido, fijada antes de correrlo."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    version: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    grid: tuple[float, ...] = Field(min_length=2)
    constraint_terms: tuple[str, ...] = Field(min_length=1)
    feasibility_constraint: str = Field(min_length=1)
    selection_seeds: tuple[int, ...] = Field(min_length=1)
    variants: tuple[str, ...] = Field(min_length=1)
    inner_folds: int = Field(ge=2)
    max_epochs: int = Field(ge=1)
    patience: int = Field(ge=1)
    train_seed_base: int = Field(ge=0)
    max_trainings: int = Field(ge=1)
    criterion: Literal["val_data_loss_mean"]
    tie_break: Literal["smallest_lambda"]

    @field_validator("grid", "constraint_terms", "selection_seeds", "variants", mode="before")
    @classmethod
    def _tuple(cls, value: object) -> tuple[Any, ...]:
        if isinstance(value, (list, tuple)):
            return tuple(value)
        raise ValueError("debe ser una lista.")

    @model_validator(mode="after")
    def _consistent(self) -> LambdaSweepConfig:
        if any(not math.isfinite(v) or v < 0 for v in self.grid):
            raise ValueError("grid solo admite λ finitos y no negativos.")
        if list(self.grid) != sorted(set(self.grid)):
            raise ValueError("grid debe estar ordenada de menor a mayor y sin repetidos.")
        if self.grid[0] != 0.0:
            raise ValueError("grid debe incluir λ = 0 (el brazo libre).")
        catalog = constraint_catalog()
        unknown = sorted({*self.constraint_terms, self.feasibility_constraint} - set(catalog))
        if unknown:
            raise ValueError(f"restricciones desconocidas: {unknown}.")
        bad = sorted(set(self.variants) - set(MODEL_VARIANTS))
        if bad:
            raise ValueError(f"variantes desconocidas: {bad}.")
        if len(set(self.selection_seeds)) != len(self.selection_seeds):
            raise ValueError("selection_seeds no puede repetir semillas.")
        return self


def load_lambda_sweep_config(path: str | Path) -> LambdaSweepConfig:
    """Lee y valida la configuración versionada del barrido.

    Raises:
        LambdaSweepConfigError: si el JSON no se puede leer o la configuración es inválida.
    """
    config_path = Path(path)
    try:
        return LambdaSweepConfig.model_validate(json.loads(config_path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValidationError) as error:
        raise LambdaSweepConfigError(f"{config_path}: {error}") from error


def trainings_needed(config: LambdaSweepConfig, plan: PenFoldPlan) -> int:
    """Entrenamientos del barrido: variantes × grilla × semillas de selección × k."""
    return len(config.variants) * len(config.grid) * len(config.selection_seeds) * plan.k


@dataclass(frozen=True)
class SweepRow:
    """Una configuración `(variante, λ)` entrenada en un fold de una semilla de selección."""

    variant: str
    constraint_lambda: float
    seed: int
    fold: int
    train_seed: int
    status: str
    best_epoch: int | None
    epochs_run: int | None
    val_data_loss: float | None
    val_bio_loss: float | None
    val_total_loss: float | None
    feasibility_violation_rate_percent: float | None
    n_train: int
    n_inner_val: int
    duration_seconds: float | None
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SWEEP_COLUMNS: Final[tuple[str, ...]] = tuple(SweepRow.__dataclass_fields__)


def run_lambda_sweep(
    *,
    config: LambdaSweepConfig,
    plan: PenFoldPlan,
    graphs: Mapping[str, HeteroData],
    pens: Mapping[str, str],
    diets: Mapping[str, str],
    model_configs: Mapping[str, GNNModelConfig],
    metadata: GraphMetadata,
    base_training: TrainingConfig,
    on_row: Callable[[SweepRow], None] | None = None,
) -> list[SweepRow]:
    """Entrena cada `(variante, λ, semilla, fold)` de selección con su val interno.

    De cada fold solo se usa el train: se reparte en train interno y val interno por corral
    (`split_inner_validation`), y el test del fold nunca se lee. Un fold que falla queda en la
    fila con `status = "error"`; no se reemplaza ni se omite.

    Raises:
        LambdaSweepConfigError: si el barrido supera `max_trainings`, si una semilla de
            selección no está en el plan o si falta la configuración de una variante.
    """
    needed = trainings_needed(config, plan)
    if needed > config.max_trainings:
        raise LambdaSweepConfigError(
            f"El barrido necesita {needed} entrenamientos y el presupuesto es "
            f"{config.max_trainings}."
        )
    unknown = sorted(set(config.selection_seeds) - set(plan.seeds))
    if unknown:
        raise LambdaSweepConfigError(f"Semillas de selección que no están en el plan: {unknown}.")
    missing = sorted(set(config.variants) - set(model_configs))
    if missing:
        raise LambdaSweepConfigError(f"Falta la configuración de modelo de {missing}.")
    feasibility = constraint_catalog()[config.feasibility_constraint]
    rows: list[SweepRow] = []
    for variant in config.variants:
        for constraint_lambda in config.grid:
            for seed in config.selection_seeds:
                for fold, (train_ids, _test_ids) in enumerate(plan.folds(seed)):
                    del _test_ids  # el test del fold nunca participa en la selección
                    train_seed = config.train_seed_base + seed * 100 + fold
                    training = base_training.model_copy(
                        update={
                            "seed": train_seed,
                            "max_epochs": config.max_epochs,
                            "patience": config.patience,
                            "constraint_lambda": constraint_lambda,
                            "constraint_terms": (
                                config.constraint_terms if constraint_lambda > 0 else ()
                            ),
                        }
                    )
                    row = _sweep_fold(
                        variant=variant,
                        constraint_lambda=constraint_lambda,
                        seed=seed,
                        fold=fold,
                        train_ids=train_ids,
                        graphs=graphs,
                        pens=pens,
                        diets=diets,
                        model_config=model_configs[variant],
                        metadata=metadata,
                        training=training,
                        inner_folds=config.inner_folds,
                        feasibility_name=feasibility.metadata.name,
                        monitor=(feasibility,),
                    )
                    rows.append(row)
                    if on_row is not None:
                        on_row(row)
    return rows


def _sweep_fold(
    *,
    variant: str,
    constraint_lambda: float,
    seed: int,
    fold: int,
    train_ids: Sequence[str],
    graphs: Mapping[str, HeteroData],
    pens: Mapping[str, str],
    diets: Mapping[str, str],
    model_config: GNNModelConfig,
    metadata: GraphMetadata,
    training: TrainingConfig,
    inner_folds: int,
    feasibility_name: str,
    monitor: Sequence[Any],
) -> SweepRow:
    inner_train: tuple[str, ...] = ()
    inner_val: tuple[str, ...] = ()
    try:
        set_seed(training.seed)
        inner_train, inner_val = split_inner_validation(
            train_ids, pens, diets, seed=training.seed, inner_folds=inner_folds
        )
        train_graphs = [graphs[s] for s in inner_train]
        val_graphs = [graphs[s] for s in inner_val]
        scaler = FeatureScaler.fit(train_graphs)
        transform = CompositionalTargetTransform.fit(train_graphs)
        model = build_model(model_config, metadata, target_names=MODEL_OUTPUT_NAMES)
        result = train_compositional_model(
            model,
            scaler.transform(train_graphs),
            scaler.transform(val_graphs),
            training,
            transform,
            monitor_constraints=monitor,
        )
    except (ValueError, RuntimeError) as error:
        return SweepRow(
            variant=variant,
            constraint_lambda=constraint_lambda,
            seed=seed,
            fold=fold,
            train_seed=training.seed,
            status="error",
            best_epoch=None,
            epochs_run=None,
            val_data_loss=None,
            val_bio_loss=None,
            val_total_loss=None,
            feasibility_violation_rate_percent=None,
            n_train=len(inner_train),
            n_inner_val=len(inner_val),
            duration_seconds=None,
            error=str(error).replace("\n", " "),
        )
    best = result.history[result.best_epoch - 1]
    (vr_row,) = [
        row
        for row in result.violations
        if row.subset == VAL_SUBSET
        and row.epoch == result.best_epoch
        and row.constraint == feasibility_name
    ]
    return SweepRow(
        variant=variant,
        constraint_lambda=constraint_lambda,
        seed=seed,
        fold=fold,
        train_seed=training.seed,
        status="ok",
        best_epoch=result.best_epoch,
        epochs_run=result.epochs_run,
        val_data_loss=best.val_data_loss,
        val_bio_loss=best.val_bio_loss,
        val_total_loss=best.val_total_loss,
        feasibility_violation_rate_percent=vr_row.violation_rate_percent,
        n_train=len(inner_train),
        n_inner_val=len(inner_val),
        duration_seconds=result.duration_seconds,
    )


@dataclass(frozen=True)
class LambdaCandidate:
    """Resumen de una λ de una variante entre los folds de selección."""

    constraint_lambda: float
    folds_ok: int
    folds_total: int
    mean_val_data_loss: float | None
    std_val_data_loss: float | None
    mean_feasibility_violation_rate_percent: float | None
    feasible: bool
    complete: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LambdaSelection:
    """λ elegida para una variante y la razón, con todas las candidatas."""

    variant: str
    selected_lambda: float
    reason: str
    any_feasible: bool
    candidates: tuple[LambdaCandidate, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant": self.variant,
            "selected_lambda": self.selected_lambda,
            "reason": self.reason,
            "any_feasible": self.any_feasible,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


def _candidates(rows: Sequence[SweepRow], grid: Sequence[float]) -> list[LambdaCandidate]:
    candidates = []
    for value in grid:
        selected = [row for row in rows if row.constraint_lambda == value]
        ok = [row for row in selected if row.status == "ok"]
        losses = [float(row.val_data_loss) for row in ok if row.val_data_loss is not None]
        rates = [
            float(row.feasibility_violation_rate_percent)
            for row in ok
            if row.feasibility_violation_rate_percent is not None
        ]
        candidates.append(
            LambdaCandidate(
                constraint_lambda=value,
                folds_ok=len(ok),
                folds_total=len(selected),
                mean_val_data_loss=statistics.fmean(losses) if losses else None,
                std_val_data_loss=statistics.stdev(losses) if len(losses) > 1 else None,
                mean_feasibility_violation_rate_percent=statistics.fmean(rates) if rates else None,
                feasible=bool(rates) and max(rates) == 0.0,
                complete=bool(selected) and len(ok) == len(selected),
            )
        )
    return candidates


def select_lambdas(
    rows: Sequence[SweepRow], config: LambdaSweepConfig
) -> dict[str, LambdaSelection]:
    """λ > 0 elegida por variante: factibilidad, menor `val_data_loss` media y menor λ si empatan.

    `candidates` incluye λ = 0 (el brazo libre) como referencia, pero no se elige.

    Raises:
        LambdaSweepConfigError: si ninguna λ > 0 de una variante entrenó en todos sus folds.
    """
    selections: dict[str, LambdaSelection] = {}
    for variant in config.variants:
        candidates = _candidates([r for r in rows if r.variant == variant], config.grid)
        complete = [c for c in candidates if c.complete and c.constraint_lambda > 0]
        if not complete:
            raise LambdaSweepConfigError(
                f"Ninguna λ > 0 de {variant} entrenó en todos los folds de selección."
            )
        feasible = [c for c in complete if c.feasible]
        pool = feasible or complete
        best = min(
            pool,
            key=lambda c: (
                c.mean_val_data_loss if c.mean_val_data_loss is not None else math.inf,
                c.constraint_lambda,
            ),
        )
        ties = [
            c.constraint_lambda for c in pool if c.mean_val_data_loss == best.mean_val_data_loss
        ]
        reason = (
            f"menor val_data_loss media ({best.mean_val_data_loss!r}) entre "
            f"{'las λ > 0 factibles' if feasible else 'todas las λ > 0 (ninguna factible)'}"
        )
        if len(ties) > 1:
            reason += f"; empate exacto entre λ = {ties}, se elige la menor"
        selections[variant] = LambdaSelection(
            variant=variant,
            selected_lambda=best.constraint_lambda,
            reason=reason,
            any_feasible=bool(feasible),
            candidates=tuple(candidates),
        )
    return selections


def read_sweep_rows(path: str | Path) -> list[SweepRow]:
    """Filas de un `sweep.csv` escrito por el barrido, para volver a elegir sin reentrenar."""

    def number(value: str, kind: type) -> Any:
        return None if value == "" else kind(value)

    rows = []
    with Path(path).open(encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            rows.append(
                SweepRow(
                    variant=raw["variant"],
                    constraint_lambda=float(raw["constraint_lambda"]),
                    seed=int(raw["seed"]),
                    fold=int(raw["fold"]),
                    train_seed=int(raw["train_seed"]),
                    status=raw["status"],
                    best_epoch=number(raw["best_epoch"], int),
                    epochs_run=number(raw["epochs_run"], int),
                    val_data_loss=number(raw["val_data_loss"], float),
                    val_bio_loss=number(raw["val_bio_loss"], float),
                    val_total_loss=number(raw["val_total_loss"], float),
                    feasibility_violation_rate_percent=number(
                        raw["feasibility_violation_rate_percent"], float
                    ),
                    n_train=int(raw["n_train"]),
                    n_inner_val=int(raw["n_inner_val"]),
                    duration_seconds=number(raw["duration_seconds"], float),
                    error=raw["error"],
                )
            )
    return rows


__all__ = [
    "CRITERION",
    "SWEEP_COLUMNS",
    "SWEEP_FORMAT_VERSION",
    "TIE_BREAK",
    "LambdaCandidate",
    "LambdaSelection",
    "LambdaSweepConfig",
    "LambdaSweepConfigError",
    "SweepRow",
    "load_lambda_sweep_config",
    "read_sweep_rows",
    "run_lambda_sweep",
    "select_lambdas",
    "trainings_needed",
]
