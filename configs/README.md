# Configuration

Versioned experiment, model, data, and simulation configuration will live here as the corresponding project phases are implemented.

Do not add placeholder configuration merely to populate the directory. Configuration should represent an executable or documented project decision.

## Contents

- `sources.json` — registered data sources (A34-1).
- `splits/` — versioned train/val/test splits (A40-1).
- `baselines/` — hyperparameter grids of the non-graph baselines, JSON (A40-4, A40-5).
- `models/` — one YAML per GNN variant read by `build_model` (A41-8); see
  [`docs/models/gnn-model-config.md`](../docs/models/gnn-model-config.md).
