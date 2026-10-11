"""Módulo de modelos y evaluación de referencia para NutriGraphDT."""

from nutrigraphdt.models.metrics import (
    DEFAULT_SCFA_TARGETS,
    EvaluationReport,
    MetricRow,
    combine_reports,
    evaluate_predictions,
    mean_absolute_error,
    negative_prediction_percentage,
    r2_score,
    root_mean_squared_error,
)
from nutrigraphdt.models.split import (
    DatasetSplit,
    create_split,
    get_split,
    load_split,
    save_split,
)

__all__ = [
    "DEFAULT_SCFA_TARGETS",
    "DatasetSplit",
    "EvaluationReport",
    "MetricRow",
    "combine_reports",
    "create_split",
    "evaluate_predictions",
    "get_split",
    "load_split",
    "mean_absolute_error",
    "negative_prediction_percentage",
    "r2_score",
    "root_mean_squared_error",
    "save_split",
]
