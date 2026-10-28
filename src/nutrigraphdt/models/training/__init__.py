"""Pipeline de entrenamiento de las GNN de la actividad 44 (requiere el extra `graph`).

No se importa desde `nutrigraphdt.models`, para que los baselines funcionen sin PyTorch.
Diseño: `docs/models/gnn-architecture.md` (A41-1, #77; §6.2); uso: `docs/models/gnn-training.md` y
`docs/models/gnn-scaling.md`.
"""

from nutrigraphdt.models.training.compositional import (
    CompositionalEpochRecord,
    CompositionalTargetTransform,
    CompositionalTrainingError,
    CompositionalTrainingResult,
    FoldEvaluation,
    drop_inferred_edges,
    run_compositional_fold,
    split_inner_validation,
    train_compositional_model,
)
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
from nutrigraphdt.models.training.filtering import (
    TaxonFilter,
    TaxonFilterConfig,
    TaxonStats,
    apply_taxon_filter_to_loaders,
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
from nutrigraphdt.models.training.tracking import (
    LoadedRun,
    RunRecord,
    load_run,
    make_run_id,
    save_run,
)

__all__ = [
    "MAX_SEED",
    "SELECTION_METRIC",
    "CompositionalEpochRecord",
    "CompositionalTargetTransform",
    "CompositionalTrainingError",
    "CompositionalTrainingResult",
    "EpochRecord",
    "FeatureScaler",
    "FoldEvaluation",
    "IdentityTargetScaler",
    "LoadedRun",
    "NodeFeatureStats",
    "NonFiniteError",
    "PreparedDataLoaders",
    "Predictions",
    "RunRecord",
    "SubsetLoaders",
    "SubsetSummary",
    "TargetScaler",
    "TargetTransform",
    "TaxonFilter",
    "TaxonFilterConfig",
    "TaxonStats",
    "TrainingConfig",
    "TrainingConfigError",
    "TrainingResult",
    "add_override_arguments",
    "apply_overrides",
    "apply_taxon_filter_to_loaders",
    "drop_inferred_edges",
    "load_run",
    "load_training_config",
    "make_run_id",
    "overrides_from_args",
    "parse_training_config",
    "predict",
    "prepare_training_graphs",
    "report_metrics",
    "run_compositional_fold",
    "save_run",
    "scalers_from_dict",
    "scalers_to_dict",
    "set_seed",
    "split_inner_validation",
    "train_compositional_model",
    "train_model",
]
