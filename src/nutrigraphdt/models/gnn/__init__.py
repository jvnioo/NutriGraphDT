"""Piezas comunes de las GNN de A41 (requiere el extra `graph`).

No se importa desde `nutrigraphdt.models`, para que los baselines funcionen sin PyTorch.
Diseño: `docs/models/gnn-architecture.md` (A41-1, #77); uso: `docs/models/gnn-components.md`.
"""

from nutrigraphdt.models.gnn.base import (
    EdgeType,
    GraphMetadata,
    ModelConfig,
    SCFAGraphModel,
    graph_batch,
)
from nutrigraphdt.models.gnn.components import (
    EXCLUDED_FROM_READOUT,
    READOUT_NODE_TYPES,
    NodeTypeEncoder,
    ResidualUpdate,
    ScfaRegressionHead,
    infer_in_channels,
    mean_readout,
)
from nutrigraphdt.models.gnn.hetero_gat import HeteroGAT
from nutrigraphdt.models.gnn.hetero_sage import HETERO_RELATION_AGGREGATIONS, HeteroSAGE
from nutrigraphdt.models.gnn.homo_sage import SAGE_AGGREGATIONS, HomoSAGE
from nutrigraphdt.models.gnn.initialization import initialize_lazy_parameters
from nutrigraphdt.models.gnn.target import (
    add_graph_target,
    canonical_scfa_name,
    masked_mse_loss,
)

__all__ = [
    "EXCLUDED_FROM_READOUT",
    "HETERO_RELATION_AGGREGATIONS",
    "READOUT_NODE_TYPES",
    "SAGE_AGGREGATIONS",
    "EdgeType",
    "GraphMetadata",
    "HeteroGAT",
    "HomoSAGE",
    "HeteroSAGE",
    "ModelConfig",
    "NodeTypeEncoder",
    "ResidualUpdate",
    "SCFAGraphModel",
    "ScfaRegressionHead",
    "add_graph_target",
    "canonical_scfa_name",
    "graph_batch",
    "infer_in_channels",
    "initialize_lazy_parameters",
    "masked_mse_loss",
    "mean_readout",
]
