"""Pipeline de entrenamiento de las GNN de la actividad 44 (requiere el extra `graph`).

No se importa desde `nutrigraphdt.models`, para que los baselines funcionen sin PyTorch.
Diseño: `docs/models/gnn-architecture.md` (A41-1, #77; §6.2); uso: `docs/models/gnn-training.md` y `docs/models/gnn-scaling.md`.
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
from nutrigraphdt.models.training.scaling import (
    FeatureScaler,
    NodeFeatureStats,
    TargetScaler,
    scalers_from_dict,
    scalers_to_dict,
)

__all__ = [
    "MAX_SEED",
    "FeatureScaler",
    "NodeFeatureStats",
    "PreparedDataLoaders",
    "SubsetSummary",
    "TargetScaler",
    "TrainingConfig",
    "TrainingConfigError",
    "add_override_arguments",
    "apply_overrides",
    "load_training_config",
    "overrides_from_args",
    "parse_training_config",
    "prepare_training_graphs",
    "scalers_from_dict",
    "scalers_to_dict",
    "set_seed",
]
