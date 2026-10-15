# Scripts

Reproducible command-line utilities and experiment entry points will live here when required by the development phases.

Reusable domain logic belongs under `src/nutrigraphdt/`; scripts should remain thin orchestration layers.

## Available scripts

- `generate_synthetic_dataset.py` — exports the DS-04 basal and intervention scenarios as JSON
  Lines plus `metadata.json` (DS-05). Default output: `artifacts/synthetic/v1` (ignored by Git).
  Use `--seed N` to export a single instance generated with a custom seed instead. Since A35-1,
  `outputs.jsonl` holds the synthetic SCFA targets. `--graphs` also builds the HeteroData
  prototype of each instance, validates it with every integrity rule, declares the feature and
  target schema in `metadata.json`, and saves the deliverable graphs under `graphs/` (requires
  the `graph` extra; see [`docs/graph/heterodata-prototype.md`](../docs/graph/heterodata-prototype.md)).

  ```bash
  python scripts/generate_synthetic_dataset.py
  python scripts/generate_synthetic_dataset.py --seed 7 --output artifacts/synthetic/seed-7
  python scripts/generate_synthetic_dataset.py --graphs --overwrite
  ```

- `explore_synthetic_dataset.py` — loads an exported synthetic dataset through the public
  `nutrigraphdt.data.synthetic` interface, validates it, and prints a summary per instance
  (DS-07). Default input: `artifacts/synthetic/v1`.

  ```bash
  python scripts/explore_synthetic_dataset.py
  python scripts/explore_synthetic_dataset.py --input artifacts/synthetic/seed-7
  ```

- `validate_graph.py` — validates an exported dataset against every record-level rule of
  [`docs/graph/graph-integrity-rules.md`](../docs/graph/graph-integrity-rules.md) and prints which graphs
  can be delivered to a model (VG-07). Exit code `0` means no `ERROR` findings, `1` means
  there are `ERROR` findings, and `2` means the dataset or the graphs could not be read. Use
  `--graphs` to also load the HeteroData prototype (safe load) and run the tensor rules, and
  `--report` to write the full JSON report. See
  [`docs/graph/graph-validation-usage.md`](../docs/graph/graph-validation-usage.md).

  ```bash
  python scripts/validate_graph.py
  python scripts/validate_graph.py --input artifacts/synthetic/v1 --graphs --report artifacts/validation/report.json
  ```

- `graph_stats.py` — descriptive statistics for any directory of HeteroData graphs written by
  `save_graphs` (A35-4). For each graph it prints node and edge counts per type, the mean
  degree (overall and per node type) and the connected components, and writes
  `stats.json` plus one Mermaid sample subgraph per graph (`sample_NNNN.md`, numbered like
  the `.pt` files) to `--output` (default: `artifacts/graph-stats`). Requires the `graph`
  extra. Degree treats every stored edge as undirected, components are weakly connected,
  and the sample is deterministic: by default the highest-degree node and its neighbors up
  to `--hops` hops and `--max-nodes` nodes; `--seed-node type:node_id` (or `type:row`)
  picks another start. `--graph-id` limits the run to one graph. Exit code `0` means the
  summary was written; `2` means the graphs could not be read or are inconsistent. The
  statistics are structural and say nothing about biological validity. The reusable logic
  lives in `nutrigraphdt.graph.stats`, so it can be called on any `HeteroData` from Python.

  ```bash
  python scripts/generate_synthetic_dataset.py --graphs
  python scripts/graph_stats.py
  python scripts/graph_stats.py --graph-id synthetic:scenario:basal:0001 --seed-node taxon:synthetic:taxon:0001 --hops 2 --max-nodes 40
  ```

- `fetch_holofood.py` — downloads the first real source, D1 HoloFood (chicken), from the
  HoloFood Data Portal, MGnify and ENA, and writes the caecal SSU abundances, caecal SCFA
  (content and tissue, separately), diet and individual phenotype metadata, a sample map and
  `manifest.json` (checksums and coverage counts) to `data/raw/D1_holofood/` (ignored by Git).
  No credentials are needed. The first run takes 30–60 minutes; responses are cached in
  `_cache/`, so an interrupted run resumes and a second run takes seconds. `--refresh`
  ignores the cache. The transformations live in `nutrigraphdt.data.acquisition.holofood`.
  See [`docs/data-sources/holofood-source.md`](../docs/data-sources/holofood-source.md).

  ```bash
  python scripts/fetch_holofood.py
  ```

- `build_graph.py` — builds and audits the heterogeneous graphs of a real source (A39-1,
  A39-2). It runs `DataPipeline` on the abundance source, attaches the metadata and
  metabolite sources with `attach_sample_context`, builds one `HeteroData` per instance with
  `build_hetero_graph`, and audits them (record and tensor rules plus the Pydantic
  contracts). Writes `report.json` to `--output` (default: `artifacts/graphs/D1_holofood`)
  and, with `--save-graphs`, the `.pt` files under `graphs/`, including non-deliverable
  graphs; the report says which are deliverable. Exit code `0` means the graphs were built;
  `2` means the sources could not be read or translated. Requires the `graph` extra. See
  [`docs/graph/graph-builder.md`](../docs/graph/graph-builder.md) and
  [`docs/graph/real-graph-validation-report.md`](../docs/graph/real-graph-validation-report.md).

  ```bash
  python scripts/fetch_holofood.py
  python scripts/build_graph.py --save-graphs --overwrite
  ```

- `create_split.py` — genera y versiona una partición train/val/test estratificada y sin
  fuga de datos (data leakage) para evaluación reproducible (A40-1). Por defecto agrupa por
  corral (`pen_code`), estratifica por tratamiento dietario (`diet_treatment_code`) y usa una
  semilla determinista (`seed=42`). Escribe la partición en formato JSON (por defecto
  `configs/splits/d1_holofood.json`). La lógica reusable vive en `nutrigraphdt.data.split`.

  ```bash
  python scripts/create_split.py
  python scripts/create_split.py --input data/raw/D1_holofood/metadata.tsv --output configs/splits/d1_holofood.json --overwrite
  ```

- `run_linear_baselines.py` — trains the trivial and linear baselines (A40-4):
  `DummyRegressor` (training mean), and multi-output `Ridge` and `ElasticNet` in a `Pipeline`
  whose scaler is fitted on training data only, tuned with `GroupKFold`. It builds a synthetic
  cohort of `--n-samples` instances (consecutive seeds from `--first-seed`), splits it with
  `create_split` (`--split-seed`), and writes `report.csv`, `report.md` and `run.json` to
  `--output` (default: `artifacts/baselines/linear`). The grid lives in
  `configs/baselines/linear.json`. Requires the `baselines` extra. Synthetic SCFA targets do not
  depend on the features, so these metrics check the pipeline, not predictive skill. See
  [`docs/models/baselines.md`](../docs/models/baselines.md).

  ```bash
  pip install -e ".[dev,baselines]"
  python scripts/run_linear_baselines.py
  ```

- `run_tree_baselines.py` — trains the tree baselines (A40-5): `RandomForestRegressor` and
  `HistGradientBoostingRegressor` wrapped in `MultiOutputRegressor`, tuned with `GroupKFold`
  on the same synthetic cohort and split as `run_linear_baselines.py`. Besides `report.csv`,
  `report.md` and `run.json`, it writes `importances.csv` with the permutation importance of
  every feature on `val`, ranked per model. Default output: `artifacts/baselines/trees`; the grid
  lives in `configs/baselines/trees.json`. Requires the `baselines` extra. As with the linear
  baselines, synthetic metrics and importances check the pipeline, not predictive skill or
  feature relevance. See [`docs/models/baselines.md`](../docs/models/baselines.md).

  ```bash
  python scripts/run_tree_baselines.py
  ```

- `compare_baselines.py` — trains all 5 baseline models (A40-6): `dummy_mean`, `ridge`,
  `elasticnet`, `random_forest`, and `hist_gradient_boosting` on the synthetic cohort and split,
  and consolidates them into a unified comparative table. Writes `baseline_comparison.md`,
  `baseline_comparison.csv`, `report.csv`, `report.md`, `importances.csv`, and `run.json` to
  `--output` (default: `reports/baselines`). Requires the `baselines` extra. This
  table feeds directly into progress report 2 (act. 46). See
  [`docs/models/baselines.md`](../docs/models/baselines.md).

  ```bash
  pip install -e ".[dev,baselines]"
  python scripts/compare_baselines.py
  ```

- `overfit_gnn.py` — sanity check of the GNN variants (A41-7): trains `homo_sage`,
  `hetero_sage` and `hetero_gat` on the same small synthetic batch (`--n-graphs`, default 8)
  for `--epochs` Adam steps and checks that the training loss drops below `--threshold`.
  Writes `losses.csv`, `curves.md` (Mermaid curves) and `summary.json` to `--output` (default:
  `artifacts/gnn-overfit`). Exit code `0` means every variant overfits; `1` means at least one
  does not. Requires the `graph` extra. See
  [`docs/models/gnn-overfit-check.md`](../docs/models/gnn-overfit-check.md).

  ```bash
  python scripts/overfit_gnn.py
  ```

- `train_gnn.py` — trains one GNN variant end to end (A44-6): prepares the graphs and split,
  fits feature and target scaling on `train`, trains with early stopping on `val`, evaluates
  `train`, `val` and `test`, and records the run in `runs/<run_id>/` (`run.json`,
  `history.csv`, `metrics.csv`, `predictions.csv`, `checkpoint.pt`). `--dataset synthetic` uses
  the same cohort and split as `compare_baselines.py`; `--dataset d1` reads the graphs saved by
  `build_graph.py --save-graphs`. Requires the `graph` extra. See
  [`docs/models/gnn-training.md`](../docs/models/gnn-training.md).

  ```bash
  python scripts/train_gnn.py --model homo_sage --dataset synthetic
  ```

- `demo_app.py` — local Streamlit demo of the project's progress: data, graph explorer,
  validation, split and baselines, GNN models, training (recorded runs and live training on CPU
  or GPU) and process. Built only from the repository's code and versioned reports; works
  without the full D1 download. Run with `streamlit run scripts/demo_app.py`. Requires the
  `graph` and `demo` extras. See [`docs/demo.md`](../docs/demo.md).

- `export_board_snapshot.py` — exports a snapshot of the GitHub Issues and merged PRs (number,
  title, state, labels and dates only) plus the collected test count to
  `reports/progress/board_snapshot.json`, which the demo's "Proceso" page reads offline.
  Requires an authenticated GitHub CLI (`gh`).

See [`docs/synthetic-dataset/synthetic-dataset-usage.md`](../docs/synthetic-dataset/synthetic-dataset-usage.md) for the full
usage guide.
