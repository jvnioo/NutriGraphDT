"""Módulo de métricas de evaluación para modelos de NutriGraphDT.

Define métricas comunes para modelos de referencia (baselines) y redes neuronales de
grafos (GNN), evaluadas por cada AGCC (acetato, propionato, butirato) y en forma agregada:
- MAE (Mean Absolute Error)
- RMSE (Root Mean Squared Error)
- R² (Coeficiente de determinación)
- Porcentaje de predicciones negativas (violación de no-negatividad biológica para F5)

Proporciona además un formato de salida común estandarizado (una fila por modelo y métrica)
para consolidar benchmarks y comparaciones reproducibles.
"""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

# Nombres canónicos de los tres AGCC principales en NutriGraphDT (D1 HoloFood / sintético)
DEFAULT_SCFA_TARGETS: tuple[str, ...] = ("acetate", "propionate", "butyrate")

METRIC_NAMES: tuple[str, ...] = ("mae", "rmse", "r2", "negative_pct")


def _validate_1d_vectors(
    y_true: Sequence[float],
    y_pred: Sequence[float],
) -> tuple[list[float], list[float]]:
    """Valida y convierte dos vectores unidimensionales a listas de flotantes finitos."""
    if len(y_true) != len(y_pred):
        raise ValueError(
            f"Longitud incompatible entre y_true ({len(y_true)}) y y_pred ({len(y_pred)})."
        )
    if len(y_true) == 0:
        raise ValueError("Los vectores de evaluación no pueden estar vacíos.")

    clean_true: list[float] = []
    clean_pred: list[float] = []
    for i, (yt, yp) in enumerate(zip(y_true, y_pred, strict=True)):
        yt_f = float(yt)
        yp_f = float(yp)
        if not math.isfinite(yt_f):
            raise ValueError(f"Valor no finito en y_true en el índice {i}: {yt}")
        if not math.isfinite(yp_f):
            raise ValueError(f"Valor no finito en y_pred en el índice {i}: {yp}")
        clean_true.append(yt_f)
        clean_pred.append(yp_f)

    return clean_true, clean_pred


def mean_absolute_error(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """Calcula el error absoluto medio (MAE).

    MAE = (1 / N) * sum(|y_true - y_pred|)
    """
    clean_true, clean_pred = _validate_1d_vectors(y_true, y_pred)
    total_abs_err = sum(abs(yt - yp) for yt, yp in zip(clean_true, clean_pred, strict=True))
    return total_abs_err / len(clean_true)


def root_mean_squared_error(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """Calcula la raíz del error cuadrático medio (RMSE).

    RMSE = sqrt((1 / N) * sum((y_true - y_pred)^2))
    """
    clean_true, clean_pred = _validate_1d_vectors(y_true, y_pred)
    total_sq_err = sum((yt - yp) ** 2 for yt, yp in zip(clean_true, clean_pred, strict=True))
    return math.sqrt(total_sq_err / len(clean_true))


def r2_score(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """Calcula el coeficiente de determinación (R²).

    R² = 1 - (SS_res / SS_tot)
    donde SS_res = sum((y_true - y_pred)^2) y SS_tot = sum((y_true - mean(y_true))^2).

    Manejo de casos borde:
    - Si SS_tot == 0 (valores reales idénticos):
      - Si SS_res == 0 (predicción perfecta), R² = 1.0.
      - Si SS_res > 0, R² = 0.0.
    """
    clean_true, clean_pred = _validate_1d_vectors(y_true, y_pred)
    n = len(clean_true)
    mean_true = sum(clean_true) / n

    ss_res = sum((yt - yp) ** 2 for yt, yp in zip(clean_true, clean_pred, strict=True))
    ss_tot = sum((yt - mean_true) ** 2 for yt in clean_true)

    if ss_tot == 0.0:
        return 1.0 if ss_res == 0.0 else 0.0

    return 1.0 - (ss_res / ss_tot)


def negative_prediction_percentage(y_pred: Sequence[float]) -> float:
    """Calcula el porcentaje de valores predichos estrictamente negativos (< 0).

    Insumo esencial para verificar la violación del espacio bioquímico factible
    (concentraciones molares no-negativas) y alimentar las restricciones de F5.
    Retorna un porcentaje en el rango [0.0, 100.0].
    """
    if len(y_pred) == 0:
        raise ValueError("El vector de predicciones no puede estar vacío.")

    count_neg = 0
    for i, yp in enumerate(y_pred):
        yp_f = float(yp)
        if not math.isfinite(yp_f):
            raise ValueError(f"Valor no finito en y_pred en el índice {i}: {yp}")
        if yp_f < 0.0:
            count_neg += 1

    return (count_neg / len(y_pred)) * 100.0


@dataclass(frozen=True)
class MetricRow:
    """Fila estructurada de evaluación para un modelo y una métrica.

    Cumple con el formato de salida común 'una fila por modelo y métrica' requerido
    por NutriGraphDT (A40-2).
    """

    model: str
    metric: str
    targets: dict[str, float]
    average: float
    split: str | None = None

    @property
    def acetate(self) -> float | None:
        """Valor de la métrica para acetato, si está presente."""
        return self.targets.get("acetate")

    @property
    def propionate(self) -> float | None:
        """Valor de la métrica para propionato, si está presente."""
        return self.targets.get("propionate")

    @property
    def butyrate(self) -> float | None:
        """Valor de la métrica para butirato, si está presente."""
        return self.targets.get("butyrate")

    def to_dict(self) -> dict[str, Any]:
        """Convierte la fila a un diccionario plano adecuado para DataFrames o CSV."""
        record: dict[str, Any] = {"model": self.model}
        if self.split is not None:
            record["split"] = self.split
        record["metric"] = self.metric
        for target_name, val in self.targets.items():
            record[target_name] = val
        record["average"] = self.average
        return record


@dataclass(frozen=True)
class EvaluationReport:
    """Reporte consolidado de métricas de evaluación para uno o más modelos."""

    rows: tuple[MetricRow, ...]

    def to_records(self) -> list[dict[str, Any]]:
        """Retorna una lista de diccionarios planos (una fila por modelo y métrica)."""
        return [row.to_dict() for row in self.rows]

    def to_markdown(self, float_format: str = "{:.4f}") -> str:
        """Genera una tabla en formato Markdown con las columnas del reporte."""
        if not self.rows:
            return ""

        has_split = any(row.split is not None for row in self.rows)
        # Determinar todas las columnas de targets en orden de aparición
        target_keys: list[str] = []
        for row in self.rows:
            for k in row.targets:
                if k not in target_keys:
                    target_keys.append(k)

        headers = ["model"]
        if has_split:
            headers.append("split")
        headers.append("metric")
        headers.extend(target_keys)
        headers.append("average")

        align_left_count = 3 if has_split else 2
        align_center_count = len(headers) - align_left_count
        alignments = [":---"] * align_left_count + [":---:"] * align_center_count
        lines: list[str] = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(alignments) + " |",
        ]

        for row in self.rows:
            row_vals: list[str] = [row.model]
            if has_split:
                row_vals.append(row.split or "-")
            row_vals.append(row.metric)
            for tk in target_keys:
                val = row.targets.get(tk)
                row_vals.append("-" if val is None else float_format.format(val))
            row_vals.append(float_format.format(row.average))
            lines.append("| " + " | ".join(row_vals) + " |")

        return "\n".join(lines)

    def to_csv(self) -> str:
        """Exporta el reporte a formato CSV."""
        records = self.to_records()
        if not records:
            return ""
        output = io.StringIO()
        fieldnames = list(records[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
        return output.getvalue()

    def get_row(
        self,
        metric: str,
        model: str | None = None,
        split: str | None = None,
    ) -> MetricRow | None:
        """Busca una fila específica por métrica y opcionalmente modelo y split."""
        for row in self.rows:
            if row.metric != metric:
                continue
            if model is not None and row.model != model:
                continue
            if split is not None and row.split != split:
                continue
            return row
        return None


def evaluate_predictions(
    y_true: Mapping[str, Sequence[float]] | Sequence[Sequence[float]],
    y_pred: Mapping[str, Sequence[float]] | Sequence[Sequence[float]],
    model_name: str,
    targets: Sequence[str] = DEFAULT_SCFA_TARGETS,
    split: str | None = None,
) -> EvaluationReport:
    """Calcula las métricas estándar para un modelo y produce un EvaluationReport.

    Calcula MAE, RMSE, R² y el porcentaje de predicciones negativas para cada uno
    de los AGCC indicados en `targets`, así como el promedio no ponderado (macro-average).

    Args:
        y_true: Valores reales, ya sea un diccionario {target: [valores]} o una matriz 2D
            (N, num_targets) alineada con `targets`.
        y_pred: Valores predichos con el mismo formato que `y_true`.
        model_name: Nombre o identificador del modelo (ej. 'Ridge', 'ElasticNet', 'GNN').
        targets: Secuencia de nombres de los targets (por defecto los 3 AGCC canónicos).
        split: Nombre opcional de la partición evaluada (ej. 'val', 'test').

    Returns:
        EvaluationReport conteniendo una fila por cada métrica
        ('mae', 'rmse', 'r2', 'negative_pct').
    """
    if len(targets) == 0:
        raise ValueError("Se debe especificar al menos un target en `targets`.")

    dict_true: dict[str, list[float]] = {}
    dict_pred: dict[str, list[float]] = {}

    if isinstance(y_true, Mapping):
        for t in targets:
            if t not in y_true:
                raise KeyError(f"El target '{t}' no se encuentra en y_true.")
            dict_true[t] = [float(v) for v in y_true[t]]
    else:
        # 2D Sequence
        num_targets = len(targets)
        for i, row in enumerate(y_true):
            if len(row) != num_targets:
                raise ValueError(
                    f"Fila {i} de y_true tiene {len(row)} elementos, esperado {num_targets}."
                )
        for target_idx, t in enumerate(targets):
            dict_true[t] = [float(row[target_idx]) for row in y_true]

    if isinstance(y_pred, Mapping):
        for t in targets:
            if t not in y_pred:
                raise KeyError(f"El target '{t}' no se encuentra en y_pred.")
            dict_pred[t] = [float(v) for v in y_pred[t]]
    else:
        # 2D Sequence
        num_targets = len(targets)
        for i, row in enumerate(y_pred):
            if len(row) != num_targets:
                raise ValueError(
                    f"Fila {i} de y_pred tiene {len(row)} elementos, esperado {num_targets}."
                )
        for target_idx, t in enumerate(targets):
            dict_pred[t] = [float(row[target_idx]) for row in y_pred]

    mae_targets: dict[str, float] = {}
    rmse_targets: dict[str, float] = {}
    r2_targets: dict[str, float] = {}
    neg_targets: dict[str, float] = {}

    for t in targets:
        yt = dict_true[t]
        yp = dict_pred[t]
        mae_targets[t] = mean_absolute_error(yt, yp)
        rmse_targets[t] = root_mean_squared_error(yt, yp)
        r2_targets[t] = r2_score(yt, yp)
        neg_targets[t] = negative_prediction_percentage(yp)

    mae_avg = sum(mae_targets.values()) / len(mae_targets)
    rmse_avg = sum(rmse_targets.values()) / len(rmse_targets)
    r2_avg = sum(r2_targets.values()) / len(r2_targets)
    neg_avg = sum(neg_targets.values()) / len(neg_targets)

    rows: list[MetricRow] = [
        MetricRow(
            model=model_name,
            metric="mae",
            targets=mae_targets,
            average=mae_avg,
            split=split,
        ),
        MetricRow(
            model=model_name,
            metric="rmse",
            targets=rmse_targets,
            average=rmse_avg,
            split=split,
        ),
        MetricRow(
            model=model_name,
            metric="r2",
            targets=r2_targets,
            average=r2_avg,
            split=split,
        ),
        MetricRow(
            model=model_name,
            metric="negative_pct",
            targets=neg_targets,
            average=neg_avg,
            split=split,
        ),
    ]

    return EvaluationReport(rows=tuple(rows))


def combine_reports(reports: Sequence[EvaluationReport]) -> EvaluationReport:
    """Combina múltiples reportes de evaluación en un único reporte consolidado."""
    all_rows: list[MetricRow] = []
    for report in reports:
        all_rows.extend(report.rows)
    return EvaluationReport(rows=tuple(all_rows))
