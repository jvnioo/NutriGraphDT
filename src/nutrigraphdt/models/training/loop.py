"""Bucle de entrenamiento y evaluación con detención temprana (A44-3, #97).

`train_model` entrena cualquier `SCFAGraphModel` con Adam y `masked_mse_loss` en la escala
estandarizada del target. Al final de cada época predice `val`, invierte la escala y calcula
`evaluate_predictions` sobre las muestras con los tres AGCC; conserva los pesos de la época con
menor RMSE promedio de `val` (§6 de `docs/models/gnn-architecture.md`). `test` no participa.

Los `DataLoader` entregan el target en las unidades de la fuente (`y_graph`): el bucle lo
estandariza con `target_scaler` (`TargetScaler` de A44-2, #96). Las features se escalan antes de
construir los `DataLoader`. Con `IdentityTargetScaler` el bucle funciona sin escalado.
"""

from __future__ import annotations

import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import torch
from torch import Tensor
from torch.nn.parameter import is_lazy
from torch_geometric.data import HeteroData
from torch_geometric.loader import DataLoader

from nutrigraphdt.models.gnn.base import SCFAGraphModel
from nutrigraphdt.models.gnn.initialization import initialize_lazy_parameters
from nutrigraphdt.models.gnn.target import masked_mse_loss
from nutrigraphdt.models.metrics import EvaluationReport, evaluate_predictions
from nutrigraphdt.models.training.config import TrainingConfig

SELECTION_METRIC = "rmse_average"
"""Clave de `EpochRecord.val_metrics` que decide la mejor época (menor es mejor)."""


class NonFiniteError(RuntimeError):
    """La pérdida o las predicciones tienen NaN o infinitos; el entrenamiento se detiene."""


class TargetTransform(Protocol):
    """Escalado del target: `TargetScaler` (A44-2) o `IdentityTargetScaler`."""

    def transform(self, y: Tensor, mask: Tensor | None = None) -> Tensor: ...

    def inverse_transform(self, y: Tensor, mask: Tensor | None = None) -> Tensor: ...


class IdentityTargetScaler:
    """Escalado identidad: el modelo predice en las unidades de la fuente.

    Como `TargetScaler`, deja en `0.0` las celdas con `mask = False`.
    """

    def transform(self, y: Tensor, mask: Tensor | None = None) -> Tensor:
        return y if mask is None else torch.where(mask, y, torch.zeros_like(y))

    def inverse_transform(self, y: Tensor, mask: Tensor | None = None) -> Tensor:
        return self.transform(y, mask)


class SubsetLoaders(Protocol):
    """Los `DataLoader` que usa el bucle; `PreparedDataLoaders` (A44-1) lo cumple."""

    @property
    def train(self) -> DataLoader: ...

    @property
    def val(self) -> DataLoader: ...


@dataclass(frozen=True)
class Predictions:
    """Valores medidos y predichos de un subconjunto, en las unidades de la fuente.

    `measured`, `mask` y `predicted` tienen forma `[N, len(targets)]`; `measured` vale `0.0`
    donde `mask` es `False`. Las filas siguen el orden del `DataLoader`.
    """

    sample_ids: tuple[str, ...]
    graph_ids: tuple[str, ...]
    targets: tuple[str, ...]
    measured: Tensor
    mask: Tensor
    predicted: Tensor

    def __len__(self) -> int:
        return len(self.sample_ids)

    @property
    def complete(self) -> Tensor:
        """`[N]` booleano: filas con todos los AGCC medidos."""
        return self.mask.all(dim=1)

    def evaluate(self, model_name: str, split: str | None = None) -> EvaluationReport:
        """`evaluate_predictions` sobre las filas con todos los AGCC, como los baselines.

        Raises:
            ValueError: si ninguna fila tiene todos los AGCC.
        """
        rows = self.complete
        if not bool(rows.any()):
            raise ValueError(
                f"Ninguna muestra de '{split or 'el subconjunto'}' tiene los "
                f"{len(self.targets)} AGCC; no se pueden calcular métricas."
            )
        return evaluate_predictions(
            self.measured[rows].tolist(),
            self.predicted[rows].tolist(),
            model_name,
            targets=self.targets,
            split=split,
        )

    def to_records(self, subset: str | None = None) -> list[dict[str, Any]]:
        """Una fila por grafo: `sample_id`, `graph_id`, subconjunto y `measured_<agcc>` /
        `predicted_<agcc>`. Un AGCC sin medir queda como `None` en `measured_<agcc>`.
        """
        records: list[dict[str, Any]] = []
        measured = self.measured.tolist()
        mask = self.mask.tolist()
        predicted = self.predicted.tolist()
        for row, (sample_id, graph_id) in enumerate(
            zip(self.sample_ids, self.graph_ids, strict=True)
        ):
            record: dict[str, Any] = {"sample_id": sample_id, "graph_id": graph_id}
            if subset is not None:
                record["subset"] = subset
            for column, target in enumerate(self.targets):
                record[f"measured_{target}"] = measured[row][column] if mask[row][column] else None
            for column, target in enumerate(self.targets):
                record[f"predicted_{target}"] = predicted[row][column]
            records.append(record)
        return records


@dataclass(frozen=True)
class EpochRecord:
    """Una época del historial.

    `train_loss` y `val_loss` son `masked_mse_loss` en la escala estandarizada, promediadas
    sobre las celdas con valor. `val_metrics` tiene las métricas de `val` en las unidades de la
    fuente sobre las muestras con todos los AGCC, con claves `<métrica>_<agcc>` y
    `<métrica>_average` (por ejemplo `rmse_acetate`, `rmse_average`).
    """

    epoch: int
    train_loss: float
    val_loss: float
    val_metrics: Mapping[str, float]
    improved: bool

    @property
    def val_rmse(self) -> float:
        """RMSE promedio de `val`: el criterio de detención temprana."""
        return self.val_metrics[SELECTION_METRIC]

    def to_dict(self) -> dict[str, float | int | bool]:
        """Fila plana para `history.csv` (A44-5); las métricas llevan el prefijo `val_`."""
        return {
            "epoch": self.epoch,
            "train_loss": self.train_loss,
            "val_loss": self.val_loss,
            **{f"val_{name}": value for name, value in self.val_metrics.items()},
            "improved": self.improved,
        }


@dataclass(frozen=True)
class TrainingResult:
    """Resultado de `train_model`. `model` queda con los pesos de `best_epoch`."""

    model: SCFAGraphModel
    history: tuple[EpochRecord, ...]
    best_epoch: int
    best_val_rmse: float
    stopped_early: bool
    duration_seconds: float

    @property
    def epochs_run(self) -> int:
        return len(self.history)


def train_model(
    model: SCFAGraphModel,
    loaders: SubsetLoaders,
    config: TrainingConfig,
    target_scaler: TargetTransform | None = None,
    *,
    model_name: str = "gnn",
) -> TrainingResult:
    """Entrena `model` con `loaders.train` y detiene con el RMSE promedio de `loaders.val`.

    Usa `lr`, `weight_decay`, `max_epochs`, `patience` y `device` de `config`. No fija la
    semilla: llame a `set_seed(config.seed)` antes de construir el modelo y los `DataLoader`.
    Las capas perezosas que sigan sin inicializar se inicializan antes de crear el optimizador.
    La detención ocurre tras `patience` épocas seguidas sin bajar el mejor RMSE; al terminar se
    restauran los pesos de la mejor época.

    Raises:
        ValueError: si `train` no tiene AGCC medidos o ninguna muestra de `val` tiene todos.
        NonFiniteError: si la pérdida o las predicciones tienen NaN o infinitos.
    """
    scaler = target_scaler if target_scaler is not None else IdentityTargetScaler()
    device = torch.device(config.device)
    _check_subsets(loaders)
    model.to(device)
    if any(is_lazy(parameter) for parameter in model.parameters()):
        initialize_lazy_parameters(model)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)

    start = time.perf_counter()
    history: list[EpochRecord] = []
    best_state = _copy_state(model)
    best_rmse = math.inf
    best_epoch = 0
    epochs_without_improvement = 0
    stopped_early = False
    for epoch in range(1, config.max_epochs + 1):
        train_loss = _train_epoch(model, loaders.train, optimizer, scaler, device, epoch)
        outputs = _forward_all(model, loaders.val, device, f"val (época {epoch})")
        val_loss = _masked_loss(outputs, scaler)
        val_report = _to_predictions(outputs, model, scaler).evaluate(model_name, split="val")
        metrics = report_metrics(val_report)
        rmse = metrics[SELECTION_METRIC]
        improved = rmse < best_rmse
        if improved:
            best_rmse, best_epoch, best_state = rmse, epoch, _copy_state(model)
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
        history.append(EpochRecord(epoch, train_loss, val_loss, metrics, improved))
        if epochs_without_improvement >= config.patience:
            stopped_early = True
            break

    model.load_state_dict(best_state)
    return TrainingResult(
        model=model,
        history=tuple(history),
        best_epoch=best_epoch,
        best_val_rmse=best_rmse,
        stopped_early=stopped_early,
        duration_seconds=time.perf_counter() - start,
    )


def predict(
    model: SCFAGraphModel,
    loader: DataLoader,
    target_scaler: TargetTransform | None = None,
) -> Predictions:
    """Predice cada grafo de `loader` en modo `eval` e invierte la escala del target.

    Devuelve `sample_id`, valores medidos y predichos en las unidades de la fuente. Restaura el
    modo `train`/`eval` previo del modelo.

    Raises:
        NonFiniteError: si alguna predicción es NaN o infinita.
    """
    scaler = target_scaler if target_scaler is not None else IdentityTargetScaler()
    device = next(model.parameters()).device
    outputs = _forward_all(model, loader, device, "predict")
    return _to_predictions(outputs, model, scaler)


def report_metrics(report: EvaluationReport) -> dict[str, float]:
    """Aplana un `EvaluationReport` de un modelo en `{<métrica>_<agcc>: valor}`.

    Incluye `<métrica>_average` (promedio sin ponderar entre AGCC, como en los baselines).
    """
    metrics: dict[str, float] = {}
    for row in report.rows:
        for target, value in row.targets.items():
            metrics[f"{row.metric}_{target}"] = value
        metrics[f"{row.metric}_average"] = row.average
    return metrics


@dataclass(frozen=True)
class _Outputs:
    """Salida del modelo en la escala estandarizada y target en las unidades de la fuente."""

    sample_ids: tuple[str, ...]
    graph_ids: tuple[str, ...]
    scaled: Tensor
    measured: Tensor
    mask: Tensor


def _check_subsets(loaders: SubsetLoaders) -> None:
    train_graphs = _graphs(loaders.train)
    if not any(bool(graph.y_graph_mask.any()) for graph in train_graphs):
        raise ValueError("train no tiene ningún AGCC medido; no hay target que ajustar.")
    if not any(bool(graph.y_graph_mask.all()) for graph in _graphs(loaders.val)):
        raise ValueError(
            "Ninguna muestra de val tiene los tres AGCC; no se puede aplicar la detención temprana."
        )


def _graphs(loader: DataLoader) -> Sequence[HeteroData]:
    dataset: Sequence[HeteroData] = loader.dataset
    return dataset


def _train_epoch(
    model: SCFAGraphModel,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    scaler: TargetTransform,
    device: torch.device,
    epoch: int,
) -> float:
    model.train()
    total = 0.0
    cells = 0
    for batch in loader:
        batch = batch.to(device)
        mask: Tensor = batch.y_graph_mask
        target = scaler.transform(batch.y_graph, mask)
        optimizer.zero_grad()
        output = model(batch)
        _check_finite(output, f"las predicciones de train (época {epoch})")
        loss = masked_mse_loss(output, target, mask)
        _check_finite(loss, f"la pérdida de train (época {epoch})")
        loss.backward()  # type: ignore[no-untyped-call]
        optimizer.step()
        observed = int(mask.sum())
        total += float(loss.detach()) * observed
        cells += observed
    return total / cells


def _forward_all(
    model: SCFAGraphModel, loader: DataLoader, device: torch.device, context: str
) -> _Outputs:
    was_training = model.training
    model.eval()
    sample_ids: list[str] = []
    graph_ids: list[str] = []
    scaled: list[Tensor] = []
    measured: list[Tensor] = []
    mask: list[Tensor] = []
    try:
        with torch.no_grad():
            for batch in loader:
                batch = batch.to(device)
                output = model(batch)
                _check_finite(output, f"las predicciones de {context}")
                scaled.append(output.cpu())
                measured.append(batch.y_graph.cpu())
                mask.append(batch.y_graph_mask.cpu())
                sample_ids.extend(_as_list(batch.sample_id))
                graph_ids.extend(_as_list(batch.graph_id))
    finally:
        model.train(was_training)
    width = len(model.target_names)
    return _Outputs(
        sample_ids=tuple(sample_ids),
        graph_ids=tuple(graph_ids),
        scaled=torch.cat(scaled) if scaled else torch.zeros((0, width)),
        measured=torch.cat(measured) if measured else torch.zeros((0, width)),
        mask=torch.cat(mask) if mask else torch.zeros((0, width), dtype=torch.bool),
    )


def _to_predictions(
    outputs: _Outputs, model: SCFAGraphModel, scaler: TargetTransform
) -> Predictions:
    predicted = scaler.inverse_transform(outputs.scaled)
    _check_finite(predicted, "las predicciones tras invertir la escala")
    return Predictions(
        sample_ids=outputs.sample_ids,
        graph_ids=outputs.graph_ids,
        targets=tuple(model.target_names),
        measured=outputs.measured,
        mask=outputs.mask,
        predicted=predicted,
    )


def _masked_loss(outputs: _Outputs, scaler: TargetTransform) -> float:
    target = scaler.transform(outputs.measured, outputs.mask)
    return float(masked_mse_loss(outputs.scaled, target, outputs.mask))


def _check_finite(values: Tensor, what: str) -> None:
    if not bool(torch.isfinite(values).all()):
        raise NonFiniteError(
            f"Hay NaN o infinitos en {what}; se detiene el entrenamiento. Revise el escalado de "
            "features y target, y la tasa de aprendizaje."
        )


def _copy_state(model: SCFAGraphModel) -> dict[str, Tensor]:
    return {name: value.detach().clone() for name, value in model.state_dict().items()}


def _as_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]


__all__ = [
    "SELECTION_METRIC",
    "EpochRecord",
    "IdentityTargetScaler",
    "NonFiniteError",
    "Predictions",
    "SubsetLoaders",
    "TargetTransform",
    "TrainingResult",
    "predict",
    "report_metrics",
    "train_model",
]
