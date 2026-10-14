"""Pipeline de entrenamiento de las GNN de la actividad 44 (requiere el extra `graph`).

No se importa desde `nutrigraphdt.models`, para que los baselines funcionen sin PyTorch.
Diseño: `docs/models/gnn-architecture.md` (A41-1, #77); uso: `docs/models/gnn-training.md`.
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

__all__ = [
    "MAX_SEED",
    "PreparedDataLoaders",
    "SubsetSummary",
    "TrainingConfig",
    "TrainingConfigError",
    "add_override_arguments",
    "apply_overrides",
    "load_training_config",
    "overrides_from_args",
    "parse_training_config",
    "prepare_training_graphs",
    "set_seed",
]
