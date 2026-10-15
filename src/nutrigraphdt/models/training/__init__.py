"""Pipeline de entrenamiento de las GNN de la actividad 44 (requiere el extra `graph`).

No se importa desde `nutrigraphdt.models`, para que los baselines funcionen sin PyTorch.
Diseño: `docs/models/gnn-architecture.md` (A41-1, #77; §6.2); uso: `docs/models/gnn-training.md` y
`docs/models/gnn-scaling.md`.
"""

from nutrigraphdt.models.training.config import (
    MAX_SEED,
    TrainingConfig,
    TrainingConfigError,
    add_override_arguments,
    apply_overrides,
    load_training_config,
    overrides_from_args,
    parse_training_config,
    set_seed,
)
from nutrigraphdt.models.training.dataloaders import (
    PreparedDataLoaders,
    SubsetSummary,
    prepare_training_graphs,
)
from nutrigraphdt.models.training.loop import (
    SELECTION_METRIC,
    EpochRecord,
    IdentityTargetScaler,
    NonFiniteError,
    Predictions,
    SubsetLoaders,
    TargetTransform,
    TrainingResult,
    predict,
    report_metrics,
    train_model,
)
from nutrigraphdt.models.training.scaling import (
    FeatureScaler,
    NodeFeatureStats,
    TargetScaler,
    scalers_from_dict,
    scalers_to_dict,
)

__all__ = [
    "MAX_SEED",
    "SELECTION_METRIC",
    "EpochRecord",
    "FeatureScaler",
    "IdentityTargetScaler",
    "NodeFeatureStats",
    "NonFiniteError",
    "PreparedDataLoaders",
    "Predictions",
    "SubsetLoaders",
    "SubsetSummary",
    "TargetScaler",
    "TargetTransform",
    "TrainingConfig",
    "TrainingConfigError",
    "TrainingResult",
    "add_override_arguments",
    "apply_overrides",
    "load_training_config",
    "overrides_from_args",
    "parse_training_config",
    "predict",
    "prepare_training_graphs",
    "report_metrics",
    "scalers_from_dict",
    "scalers_to_dict",
    "set_seed",
    "train_model",
]
