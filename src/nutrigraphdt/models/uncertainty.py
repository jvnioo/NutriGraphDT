"""Incertidumbre de las predicciones composicionales de D1 (A75-P1 y A75-P2; #283 y #284).

Dos métodos producen, para cada animal, una distribución predictiva de la salida del modelo
`(z_1, z_2, ln T)`:

- **Ensamble** (`ensemble`): `ensemble_size` modelos por fold, entrenados con el **mismo** train
  interno, el mismo val interno para la detención temprana y el mismo escalado, que solo difieren
  en la semilla de inicialización y del orden de los lotes. No se confunde con las 10 semillas del
  plan de #139, que cambian la partición.
- **MC-dropout** (`mc_dropout`): `mc_passes` pasadas con el dropout activo sobre el modelo del
  fold (el primer miembro del ensamble, que es el mismo modelo de la evaluación de #266).

**Forma de los intervalos.** Cada método resume sus muestras con la media y la desviación por
salida, y el intervalo de nivel `q` es `media ± s · z_q · desviación`, con `z_q` el cuantil normal
de `(1 + q) / 2` y `s` un factor de escala (1 sin calibrar). En fracciones se toman muestras de
la normal de `(z_1, z_2)`, se transforman con la softmax de `(0, z_1, z_2)` y se usan sus
cuantiles empíricos. La fracción puntual es la softmax de la media de `(z_1, z_2)`: **nunca se
promedian fracciones** (#283).

**Sin fuga.** El factor de escala (`fit_scale`) y la elección del método (`select_method`) usan
solo el **val interno** del fold. El test del fold se predice una sola vez, al final, con el método
elegido y el factor ya fijado (#284). Ningún dato de otro fold interviene: el val interno de otro
fold puede contener animales del test de este.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Final

import torch
from torch import Tensor, nn
from torch_geometric.data import HeteroData
from torch_geometric.loader import DataLoader

from nutrigraphdt.models.composition import MODEL_OUTPUT_NAMES
from nutrigraphdt.models.gnn.base import GraphMetadata, SCFAGraphModel
from nutrigraphdt.models.gnn.batching import for_training
from nutrigraphdt.models.gnn.factory import GNNModelConfig, build_model
from nutrigraphdt.models.gnn.target import compositional_graph_target
from nutrigraphdt.models.training.compositional import (
    DEFAULT_INNER_FOLDS,
    CompositionalTargetTransform,
    CompositionalTrainingError,
    split_inner_validation,
    train_compositional_model,
)
from nutrigraphdt.models.training.config import MAX_SEED, TrainingConfig, set_seed
from nutrigraphdt.models.training.scaling import FeatureScaler
from nutrigraphdt.models.training.taxon_identity import TaxonIdentityConfig, TaxonLineageEncoder

UNCERTAINTY_FORMAT_VERSION: Final[str] = "1.0.0"

ENSEMBLE: Final[str] = "ensemble"
MC_DROPOUT: Final[str] = "mc_dropout"
METHODS: Final[tuple[str, str]] = (ENSEMBLE, MC_DROPOUT)
"""Métodos en orden de preferencia ante un empate en `select_method`."""

DEFAULT_ENSEMBLE_SIZE: Final[int] = 5
DEFAULT_MC_PASSES: Final[int] = 30
DEFAULT_LEVELS: Final[tuple[float, ...]] = (0.5, 0.8, 0.9)
CALIBRATION_LEVEL: Final[float] = 0.8
"""Nivel con el que `fit_scale` ajusta el factor de escala en el val interno."""
DEFAULT_FRACTION_DRAWS: Final[int] = 2000
MEMBER_SEED_STRIDE: Final[int] = 1_000_000
"""Distancia entre las semillas de los miembros: `semilla_fold + m · MEMBER_SEED_STRIDE`.

Es mayor que cualquier semilla de entrenamiento de un fold (`42000 + 100 · semilla + fold`), así
que dos miembros de folds distintos nunca comparten semilla.
"""
MIN_STD: Final[float] = 1e-8
"""Piso de la desviación, para que un intervalo degenerado no divida por cero."""

FRACTION_NAMES: Final[tuple[str, str, str]] = ("acetate", "propionate", "butyrate")
OUTPUT_NAMES: Final[tuple[str, ...]] = (*MODEL_OUTPUT_NAMES, *FRACTION_NAMES)
"""Salidas con intervalo: las tres del modelo y las tres fracciones."""


class UncertaintyError(ValueError):
    """Configuración o entradas inválidas para estimar la incertidumbre."""


# ---------------------------------------------------------------------------
# Predicción con el modelo
# ---------------------------------------------------------------------------


@contextmanager
def mc_dropout(model: nn.Module) -> Iterator[nn.Module]:
    """Activa solo las capas de dropout y, al salir, restaura el modo de cada módulo.

    El resto del modelo sigue en `eval()`, de modo que solo el dropout es estocástico.
    """
    previous = {name: module.training for name, module in model.named_modules()}
    model.eval()
    dropouts = [m for m in model.modules() if isinstance(m, nn.modules.dropout._DropoutNd)]
    if not dropouts:
        raise UncertaintyError("El modelo no tiene capas de dropout: MC-dropout no aplica.")
    for module in dropouts:
        module.train()
    try:
        yield model
    finally:
        for name, module in model.named_modules():
            module.train(previous.get(name, False))


def _loader(graphs: Sequence[HeteroData], batch_size: int) -> DataLoader:
    return DataLoader([for_training(g) for g in graphs], batch_size=batch_size, shuffle=False)


def predict_outputs(
    model: SCFAGraphModel,
    graphs: Sequence[HeteroData],
    transform: CompositionalTargetTransform,
    *,
    batch_size: int,
) -> Tensor:
    """Salida `(z_1, z_2, ln T)` `[N, 3]` en modo evaluación, en el orden de `graphs`.

    Restaura el modo de entrenamiento que tenía el modelo.
    """
    was_training = model.training
    device = next(model.parameters()).device
    model.eval()
    outputs: list[Tensor] = []
    try:
        with torch.no_grad():
            for batch in _loader(graphs, batch_size):
                outputs.append(transform.inverse_transform(model(batch.to(device)).cpu()))
    finally:
        model.train(was_training)
    return torch.cat(outputs)


def sample_mc_dropout(
    model: SCFAGraphModel,
    graphs: Sequence[HeteroData],
    transform: CompositionalTargetTransform,
    *,
    passes: int,
    seed: int,
    batch_size: int,
) -> Tensor:
    """`passes` pasadas con dropout activo: tensor `[passes, N, 3]` en `(z_1, z_2, ln T)`.

    Es determinista para una misma `seed` y no altera el generador global de PyTorch.
    """
    if passes < 2:
        raise UncertaintyError(f"MC-dropout necesita al menos 2 pasadas; se pidieron {passes}.")
    device = next(model.parameters()).device
    devices = [device] if device.type == "cuda" else []
    samples: list[Tensor] = []
    with torch.random.fork_rng(devices=devices), mc_dropout(model), torch.no_grad():
        torch.manual_seed(seed)
        for _ in range(passes):
            batches = [
                transform.inverse_transform(model(batch.to(device)).cpu())
                for batch in _loader(graphs, batch_size)
            ]
            samples.append(torch.cat(batches))
    return torch.stack(samples)


def observed_outputs(graphs: Sequence[HeteroData]) -> Tensor:
    """Objetivo medido `(z_1, z_2, ln T)` `[N, 3]`; `nan` en los animales sin objetivo válido."""
    target, valid = compositional_graph_target(
        torch.cat([g.y_graph for g in graphs]), torch.cat([g.y_graph_mask for g in graphs])
    )
    return torch.where(valid, target, torch.full_like(target, math.nan))


# ---------------------------------------------------------------------------
# Distribución predictiva e intervalos
# ---------------------------------------------------------------------------


def gaussian_quantile(level: float) -> float:
    """`z` tal que `media ± z · desviación` cubre `level` de una normal."""
    if not 0.0 < level < 1.0:
        raise UncertaintyError(f"El nivel debe estar en (0, 1); se recibió {level!r}.")
    return statistics.NormalDist().inv_cdf((1.0 + level) / 2.0)


def fractions_from_outputs(outputs: Tensor) -> Tensor:
    """Softmax de `(0, z_1, z_2)` sobre la última dimensión: `[..., 3]` → fracciones `[..., 3]`."""
    zeros = torch.zeros_like(outputs[..., :1])
    return torch.softmax(torch.cat([zeros, outputs[..., :2]], dim=-1), dim=-1)


def _scale_tensor(scale: Sequence[float] | None, columns: int) -> Tensor:
    if scale is None:
        return torch.ones(columns, dtype=torch.float64)
    values = torch.as_tensor(list(scale), dtype=torch.float64)
    if (
        values.shape != (columns,)
        or not bool(torch.isfinite(values).all())
        or bool((values <= 0).any())
    ):
        raise UncertaintyError(f"Factor de escala inválido: {list(scale)}.")
    return values


@dataclass(frozen=True)
class PredictiveDistribution:
    """Media y desviación de `(z_1, z_2, ln T)` por animal, resumidas de las muestras."""

    sample_ids: tuple[str, ...]
    mean: Tensor
    """`[N, 3]`, `float64`."""
    std: Tensor
    """`[N, 3]`, `float64`, con piso `MIN_STD`."""
    n_samples: int

    @classmethod
    def from_samples(cls, samples: Tensor, sample_ids: Sequence[str]) -> PredictiveDistribution:
        """`samples` `[S, N, 3]` (miembros o pasadas) → media y desviación muestral (`S − 1`)."""
        if samples.ndim != 3 or samples.shape[-1] != 3:
            raise UncertaintyError(
                f"Se esperaban muestras [S, N, 3]; forma {tuple(samples.shape)}."
            )
        if samples.shape[0] < 2:
            raise UncertaintyError("Hacen falta al menos 2 muestras para estimar la dispersión.")
        if samples.shape[1] != len(sample_ids):
            raise UncertaintyError("El número de animales no coincide con `sample_ids`.")
        values = samples.to(torch.float64)
        if not bool(torch.isfinite(values).all()):
            raise UncertaintyError("Las muestras tienen valores no finitos.")
        std = values.std(dim=0, unbiased=True).clamp_min(MIN_STD)
        return cls(tuple(sample_ids), values.mean(dim=0), std, int(samples.shape[0]))

    def interval(self, level: float, scale: Sequence[float] | None = None) -> tuple[Tensor, Tensor]:
        """Límites `[N, 3]` de `media ± escala · z · desviación` en `(z_1, z_2, ln T)`."""
        half = gaussian_quantile(level) * _scale_tensor(scale, 3) * self.std
        return self.mean - half, self.mean + half

    def point_fractions(self) -> Tensor:
        """Fracción puntual `[N, 3]`: softmax de la media de `(z_1, z_2)`."""
        return fractions_from_outputs(self.mean)

    def fraction_interval(
        self,
        level: float,
        scale: Sequence[float] | None = None,
        *,
        draws: int = DEFAULT_FRACTION_DRAWS,
        seed: int = 0,
    ) -> tuple[Tensor, Tensor]:
        """Cuantiles empíricos `[N, 3]` de las fracciones bajo la normal de `(z_1, z_2)`.

        Las dos log-razones se muestrean como independientes (con la escala de sus columnas).
        """
        if draws < 10:
            raise UncertaintyError(f"Se necesitan al menos 10 muestras; se pidieron {draws}.")
        gaussian_quantile(level)
        generator = torch.Generator().manual_seed(seed)
        std = (_scale_tensor(scale, 3) * self.std)[:, :2]
        noise = torch.randn(
            (draws, *self.mean[:, :2].shape), generator=generator, dtype=torch.float64
        )
        fractions = fractions_from_outputs(self.mean[:, :2] + noise * std)
        tail = (1.0 - level) / 2.0
        bounds = torch.quantile(
            fractions, torch.tensor([tail, 1.0 - tail], dtype=torch.float64), dim=0
        )
        return bounds[0], bounds[1]


def combined_intervals(
    distribution: PredictiveDistribution,
    level: float,
    scale: Sequence[float] | None = None,
    *,
    draws: int = DEFAULT_FRACTION_DRAWS,
    seed: int = 0,
) -> tuple[Tensor, Tensor, Tensor]:
    """Punto, límite inferior y superior `[N, 6]` en el orden de `OUTPUT_NAMES`."""
    lower, upper = distribution.interval(level, scale)
    f_lower, f_upper = distribution.fraction_interval(level, scale, draws=draws, seed=seed)
    point = torch.cat([distribution.mean, distribution.point_fractions()], dim=1)
    return point, torch.cat([lower, f_lower], dim=1), torch.cat([upper, f_upper], dim=1)


def observed_with_fractions(observed: Tensor) -> Tensor:
    """`(z_1, z_2, ln T)` medidos `[N, 3]` → `[N, 6]` con las fracciones medidas."""
    observed = observed.to(torch.float64)
    return torch.cat([observed, fractions_from_outputs(observed)], dim=1)


# ---------------------------------------------------------------------------
# Calibración y elección del método (solo con el val interno)
# ---------------------------------------------------------------------------


def coverage(observed: Tensor, lower: Tensor, upper: Tensor) -> list[float]:
    """Proporción de valores observados dentro de `[lower, upper]`, por columna.

    Ignora las filas `nan` de cada columna; `nan` si una columna no tiene observaciones.
    """
    inside = (observed >= lower) & (observed <= upper)
    valid = torch.isfinite(observed)
    result: list[float] = []
    for column in range(observed.shape[1]):
        n = int(valid[:, column].sum())
        result.append(float(inside[:, column][valid[:, column]].sum()) / n if n else math.nan)
    return result


def fit_scale(
    observed: Tensor,
    distribution: PredictiveDistribution,
    level: float = CALIBRATION_LEVEL,
) -> tuple[float, float, float]:
    """Factor por salida `(z_1, z_2, ln T)` para que el intervalo de `level` cubra `level`.

    Es el cuantil `level` de `|y − media| / desviación` dividido por `z_level`. Un factor mayor
    que 1 ensancha (subcobertura); menor que 1, angosta. Debe ajustarse **solo** con el val
    interno. Sin observaciones válidas en una salida, su factor es 1.
    """
    z = gaussian_quantile(level)
    residual = (observed.to(torch.float64) - distribution.mean).abs() / distribution.std
    factors: list[float] = []
    for column in range(3):
        values = residual[:, column][torch.isfinite(residual[:, column])]
        if values.numel() == 0:
            factors.append(1.0)
            continue
        factors.append(max(float(torch.quantile(values, level)) / z, MIN_STD))
    return (factors[0], factors[1], factors[2])


def gaussian_nll(observed: Tensor, distribution: PredictiveDistribution) -> float:
    """Log-verosimilitud negativa media de la normal predictiva en `(z_1, z_2, ln T)`.

    Es una regla de puntuación propia: premia a la vez calibración y estrechez. Ignora los
    valores `nan`.
    """
    y = observed.to(torch.float64)
    variance = distribution.std.pow(2)
    nll = 0.5 * (torch.log(2 * math.pi * variance) + (y - distribution.mean).pow(2) / variance)
    finite = nll[torch.isfinite(nll)]
    if finite.numel() == 0:
        raise UncertaintyError("No hay observaciones válidas para puntuar el método.")
    return float(finite.mean())


def select_method(scores: Mapping[str, float]) -> str:
    """Método con menor NLL en el val interno; ante empate, el primero de `METHODS`."""
    unknown = sorted(set(scores) - set(METHODS))
    if unknown or not scores:
        raise UncertaintyError(f"Métodos desconocidos o sin puntaje: {unknown or list(scores)}.")
    return min((m for m in METHODS if m in scores), key=lambda m: (scores[m], METHODS.index(m)))


# ---------------------------------------------------------------------------
# Un fold completo
# ---------------------------------------------------------------------------


def member_seed(fold_seed: int, member: int) -> int:
    """Semilla del miembro `member` (0 = la del fold)."""
    seed = fold_seed + member * MEMBER_SEED_STRIDE
    if member < 0 or seed > MAX_SEED:
        raise UncertaintyError(f"Semilla de miembro fuera de rango: {seed}.")
    return seed


@dataclass(frozen=True)
class FoldUncertainty:
    """Distribuciones predictivas del val interno y del test de un fold, y lo ajustado con val."""

    seed: int
    fold: int
    train_seed: int
    inner_val: Mapping[str, PredictiveDistribution]
    test: Mapping[str, PredictiveDistribution]
    observed_inner_val: Tensor
    """`(z_1, z_2, ln T)` medidos del val interno `[N, 3]`."""
    observed_test: Tensor
    scales: Mapping[str, tuple[float, float, float]]
    """Factor por método y salida, ajustado con el val interno."""
    nll: Mapping[str, float]
    """NLL de cada método en el val interno, sin escalar: criterio de `select_method`."""
    selected: str
    member_seeds: tuple[int, ...]
    member_epochs: tuple[int, ...]
    train_fraction_support: tuple[tuple[float, float], ...]
    """`(mínimo, máximo)` de cada fracción medida en el train interno (D-06 §7, como #245)."""
    n_train: int
    n_inner_val: int
    duration_seconds: float
    reference_test: Tensor
    """Predicción del miembro 0 en modo evaluación `[N, 3]`: la de `run_compositional_fold`."""


def _train_support(graphs: Sequence[HeteroData]) -> tuple[tuple[float, float], ...]:
    """Soporte de D-06 §7 con `EmpiricalSupport` (#245): mínimo y máximo del train interno."""
    from nutrigraphdt.scenarios.support import COMPONENTS, EmpiricalSupport

    observed = observed_with_fractions(observed_outputs(graphs))[:, 3:]
    rows = [row.tolist() for row in observed if bool(torch.isfinite(row).all())]
    support = EmpiricalSupport.fit(rows, source="train interno del fold")
    return tuple(support.interval[name] for name in COMPONENTS)


def run_uncertainty_fold(
    *,
    seed: int,
    fold: int,
    train_ids: Sequence[str],
    test_ids: Sequence[str],
    graphs: Mapping[str, HeteroData],
    pens: Mapping[str, str],
    diets: Mapping[str, str],
    model_config: GNNModelConfig,
    metadata: GraphMetadata,
    config: TrainingConfig,
    taxon_identity: TaxonIdentityConfig | None = None,
    ensemble_size: int = DEFAULT_ENSEMBLE_SIZE,
    mc_passes: int = DEFAULT_MC_PASSES,
    calibration_level: float = CALIBRATION_LEVEL,
    inner_folds: int = DEFAULT_INNER_FOLDS,
) -> FoldUncertainty:
    """Entrena el ensamble de un fold, aplica MC-dropout y calibra con el val interno.

    El reparto interno, la codificación de los taxones y el escalado se hacen una vez, igual que
    `run_compositional_fold` con `config.seed`, así que el miembro 0 es el modelo de ese fold. Los
    demás miembros solo cambian la semilla (`member_seed`). El test se predice al final y no
    interviene en `scales`, `nll` ni `selected`.

    Raises:
        UncertaintyError: si `ensemble_size < 2` o un animal de test está en el train.
        CompositionalTrainingError: como `run_compositional_fold`.
    """
    import time

    if ensemble_size < 2:
        raise UncertaintyError(
            f"El ensamble necesita al menos 2 modelos; se pidieron {ensemble_size}."
        )
    if set(train_ids) & set(test_ids):
        raise UncertaintyError("Hay animales a la vez en el train y el test del fold.")
    missing = [s for s in (*train_ids, *test_ids) if s not in graphs]
    if missing:
        raise CompositionalTrainingError(f"Animales del fold sin grafo: {missing}.")
    start = time.perf_counter()
    set_seed(config.seed)
    inner_train_ids, inner_val_ids = split_inner_validation(
        train_ids, pens, diets, seed=config.seed, inner_folds=inner_folds
    )
    train_graphs = [graphs[s] for s in inner_train_ids]
    val_graphs = [graphs[s] for s in inner_val_ids]
    test_graphs = [graphs[s] for s in test_ids]
    if taxon_identity is not None:
        encoder = TaxonLineageEncoder.fit(train_graphs, taxon_identity)
        train_graphs = encoder.transform(train_graphs)
        val_graphs = encoder.transform(val_graphs)
        test_graphs = encoder.transform(test_graphs)
        metadata = encoder.adapt_metadata(metadata)
    scaler = FeatureScaler.fit(train_graphs)
    transform = CompositionalTargetTransform.fit(train_graphs)
    train_scaled = scaler.transform([for_training(g) for g in train_graphs])
    val_scaled = scaler.transform([for_training(g) for g in val_graphs])
    test_scaled = scaler.transform([for_training(g) for g in test_graphs])

    seeds = tuple(member_seed(config.seed, m) for m in range(ensemble_size))
    val_members: list[Tensor] = []
    test_members: list[Tensor] = []
    epochs: list[int] = []
    first_model: SCFAGraphModel | None = None
    for member in seeds:
        set_seed(member)
        model = build_model(model_config, metadata, target_names=MODEL_OUTPUT_NAMES)
        result = train_compositional_model(
            model, train_scaled, val_scaled, config.model_copy(update={"seed": member}), transform
        )
        epochs.append(result.epochs_run)
        val_members.append(
            predict_outputs(model, val_scaled, transform, batch_size=config.batch_size)
        )
        test_members.append(
            predict_outputs(model, test_scaled, transform, batch_size=config.batch_size)
        )
        if first_model is None:
            first_model = model
    assert first_model is not None

    def mc(graphs_scaled: Sequence[HeteroData]) -> Tensor:
        return sample_mc_dropout(
            first_model,
            graphs_scaled,
            transform,
            passes=mc_passes,
            seed=config.seed,
            batch_size=config.batch_size,
        )

    inner_val = {
        ENSEMBLE: PredictiveDistribution.from_samples(torch.stack(val_members), inner_val_ids),
        MC_DROPOUT: PredictiveDistribution.from_samples(mc(val_scaled), inner_val_ids),
    }
    test = {
        ENSEMBLE: PredictiveDistribution.from_samples(torch.stack(test_members), test_ids),
        MC_DROPOUT: PredictiveDistribution.from_samples(mc(test_scaled), test_ids),
    }
    observed_val = observed_outputs(val_graphs)
    scales = {m: fit_scale(observed_val, d, calibration_level) for m, d in inner_val.items()}
    nll = {m: gaussian_nll(observed_val, d) for m, d in inner_val.items()}
    return FoldUncertainty(
        seed=seed,
        fold=fold,
        train_seed=config.seed,
        inner_val=inner_val,
        test=test,
        observed_inner_val=observed_val,
        observed_test=observed_outputs(test_graphs),
        scales=scales,
        nll=nll,
        selected=select_method(nll),
        member_seeds=seeds,
        member_epochs=tuple(epochs),
        train_fraction_support=_train_support(train_graphs),
        n_train=len(inner_train_ids),
        n_inner_val=len(inner_val_ids),
        duration_seconds=time.perf_counter() - start,
        reference_test=test_members[0],
    )


def interval_rows(
    fold: FoldUncertainty,
    subset: str,
    levels: Sequence[float] = DEFAULT_LEVELS,
    *,
    draws: int = DEFAULT_FRACTION_DRAWS,
) -> list[dict[str, Any]]:
    """Filas por animal, método, calibración, nivel y salida, con el valor medido.

    `subset` es `"inner_val"` o `"test"`. `calibrated` indica si se aplicó el factor del val
    interno. Las fracciones usan una semilla de muestreo fija por fold.
    """
    if subset == "inner_val":
        distributions, observed = fold.inner_val, fold.observed_inner_val
    elif subset == "test":
        distributions, observed = fold.test, fold.observed_test
    else:
        raise UncertaintyError(f"Subconjunto desconocido: {subset!r}.")
    measured = observed_with_fractions(observed)
    rows: list[dict[str, Any]] = []
    for method, distribution in distributions.items():
        for calibrated in (False, True):
            scale = fold.scales[method] if calibrated else None
            for level in levels:
                point, lower, upper = combined_intervals(
                    distribution, level, scale, draws=draws, seed=fold.train_seed
                )
                for row, sample_id in enumerate(distribution.sample_ids):
                    for column, output in enumerate(OUTPUT_NAMES):
                        rows.append(
                            {
                                "seed": fold.seed,
                                "fold": fold.fold,
                                "subset": subset,
                                "sample_id": sample_id,
                                "method": method,
                                "selected": method == fold.selected,
                                "calibrated": calibrated,
                                "level": level,
                                "output": output,
                                "observed": float(measured[row, column]),
                                "point": float(point[row, column]),
                                "lower": float(lower[row, column]),
                                "upper": float(upper[row, column]),
                            }
                        )
    return rows


__all__ = [
    "CALIBRATION_LEVEL",
    "DEFAULT_ENSEMBLE_SIZE",
    "DEFAULT_FRACTION_DRAWS",
    "DEFAULT_LEVELS",
    "DEFAULT_MC_PASSES",
    "ENSEMBLE",
    "FRACTION_NAMES",
    "MC_DROPOUT",
    "MEMBER_SEED_STRIDE",
    "METHODS",
    "MIN_STD",
    "OUTPUT_NAMES",
    "UNCERTAINTY_FORMAT_VERSION",
    "FoldUncertainty",
    "PredictiveDistribution",
    "UncertaintyError",
    "combined_intervals",
    "coverage",
    "fit_scale",
    "fractions_from_outputs",
    "gaussian_nll",
    "gaussian_quantile",
    "interval_rows",
    "mc_dropout",
    "member_seed",
    "observed_outputs",
    "observed_with_fractions",
    "predict_outputs",
    "run_uncertainty_fold",
    "sample_mc_dropout",
    "select_method",
]
