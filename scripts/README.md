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

- `count_holofood_assemblies.py` — counts how many D1 animals with SCFA the MGnify assembly
  analyses (`ERZ…`) would add (#141), without changing `data/raw/`. Reuses the
  `fetch_holofood.py` cache and only queries the ENA analysis reports. Writes
  `reports/holofood/assemblies.md` and `.json`. See
  [`docs/data-sources/holofood-source.md`](../docs/data-sources/holofood-source.md).

  ```bash
  python scripts/count_holofood_assemblies.py
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

  With `--dataset d1` it uses only the supervised cohort of `configs/cohorts/d1_holofood.json`
  (#138); `--min-ssu-reads` overrides the read threshold for a sensitivity analysis.

- `report_cohort.py` — reports the supervised D1 cohort (#138): animals with a caecal
  metagenome and the three main SCFA, minus the configured exclusions (duplicated SCFA profiles)
  and the animals below the SSU read threshold. Writes one table per threshold (the official one
  and those in `sensitivity_min_ssu_reads`) to `reports/cohort/d1_holofood.md` and `.json`. It
  reads the full download registered in `configs/sources.json`. See
  [`docs/data-sources/holofood-source.md`](../docs/data-sources/holofood-source.md#cohorte-supervisada-138).

  ```bash
  python scripts/report_cohort.py
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
  `build_graph.py --save-graphs` and loads only the supervised cohort (#138), computed from the
  tables in `--sources`. Requires the `graph` extra. See
  [`docs/models/gnn-training.md`](../docs/models/gnn-training.md).

  ```bash
  python scripts/train_gnn.py --model homo_sage --dataset synthetic
  ```

- `report_gnn.py` — consolida las métricas `val` y `test` de una corrida existente de cada
  variante (`homo_sage`, `hetero_sage`, `hetero_gat`) y las compara con `dummy_mean`. Por defecto
  conserva el modo sintético y escribe en `reports/gnn/synthetic/`, usando
  `reports/baselines/run.json` y `reports/baselines/report.csv`. Con `--dataset d1`, usa por
  defecto los archivos de referencia `reports/baselines/d1/` y escribe en `reports/gnn/d1/`;
  verifica archivo, versión y SHA-256 de `configs/splits/d1_holofood.json`, los conteos con los
  tres AGCC y el `dataset_id`. `--split-config` permite señalar otra partición, por ejemplo el
  split del fixture en pruebas. El reporte D1 incluye conteos por subconjunto, dispositivo,
  duración, commit y estado `dirty` de cada corrida, además de las advertencias metodológicas.
  Copia solo los `run.json`, no checkpoints ni otros archivos pesados. No entrena modelos.
  Requiere el extra `graph`. Véase [`docs/models/gnn-training.md`](../docs/models/gnn-training.md).

  ```bash
  python scripts/report_gnn.py --homo-sage-run runs/<run_id> \
      --hetero-sage-run runs/<run_id> --hetero-gat-run runs/<run_id>
  ```

  Para evaluar las tres variantes en D1 con la configuración de entrenamiento predeterminada
  (semilla 42, CPU), cree primero corridas separadas y, tras el primer commit con el árbol limpio,
  consolídelas:

  ```powershell
  $runsRoot = Join-Path .\runs ("d1-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
  python .\scripts\train_gnn.py --model homo_sage --dataset d1 --seed 42 --runs-dir (Join-Path $runsRoot "homo_sage")
  python .\scripts\train_gnn.py --model hetero_sage --dataset d1 --seed 42 --runs-dir (Join-Path $runsRoot "hetero_sage")
  python .\scripts\train_gnn.py --model hetero_gat --dataset d1 --seed 42 --runs-dir (Join-Path $runsRoot "hetero_gat")

  $homoSageRun = Get-ChildItem (Join-Path $runsRoot "homo_sage") -Directory | Select-Object -ExpandProperty FullName
  $heteroSageRun = Get-ChildItem (Join-Path $runsRoot "hetero_sage") -Directory | Select-Object -ExpandProperty FullName
  $heteroGatRun = Get-ChildItem (Join-Path $runsRoot "hetero_gat") -Directory | Select-Object -ExpandProperty FullName
  python .\scripts\report_gnn.py --dataset d1 --homo-sage-run $homoSageRun --hetero-sage-run $heteroSageRun --hetero-gat-run $heteroGatRun --output .\reports\gnn\d1
  ```

- `tune_gnn.py` — bounded hyperparameter search and seed variability (A45-5): trains a
  `hidden_channels` × `num_layers` grid (32/64/128 × 1/2/3) for one variant with a fixed seed,
  selects the lowest average `val` RMSE (`test` is not used), and repeats the initial
  configuration of the three variants and the selected one with 5 seeds (mean ± standard
  deviation in `val` and `test`). Writes `grid.csv`, `selection.json`, `seeds.csv`,
  `summary.csv`, `report.md` and a copy of each `run.json` to `reports/gnn/tuning/<dataset>/`,
  and the selected configuration to `configs/models/tuned/<dataset>_<variant>.yaml`. Requires
  the `graph` extra. See [`docs/models/gnn-tuning.md`](../docs/models/gnn-tuning.md).

  ```bash
  python scripts/tune_gnn.py --dataset synthetic --model hetero_gat
  python scripts/tune_gnn.py --dataset d1 --model homo_sage
  ```

- `compare_models.py` — tabla comparativa GNN frente a baselines para el avance 2 (A45-6). Lee
  `reports/baselines/` y `reports/gnn/`, verifica con los `run.json` que cada variante GNN use
  las mismas muestras y la misma partición que los baselines de su dataset (cohorte sintética y
  D1) y escribe `reports/comparison/model_comparison.md` y `.csv` con MAE, RMSE, R² y % de
  predicciones negativas por AGCC y promedio, en `val` y `test`. Indica si se cumple el criterio
  de salida de F4 y marca como `pendiente` una variante sin reporte. Termina con código 2 si los
  reportes no están alineados. No entrena modelos ni requiere PyTorch o scikit-learn. Véase
  [`docs/models/gnn-evaluation.md`](../docs/models/gnn-evaluation.md).

  ```bash
  python scripts/compare_models.py
  ```

- `plot_gnn_runs.py` — curvas de aprendizaje y predicho vs. medido de corridas GNN registradas
  (A45-7). Recibe una carpeta de corrida por variante, verifica que sus métricas coincidan con
  `reports/gnn/<dataset>/report.csv` y escribe en `reports/gnn/figures/` la pérdida de `train` y
  `val` y el RMSE de `val` por época con la mejor época marcada, predicho vs. medido por AGCC en
  `test`, y `diagnostics_<dataset>.md`/`.json` con la procedencia y cifras de sobreajuste. No
  reentrena. Requiere el extra `plots` (matplotlib). Véase
  [`docs/models/gnn-evaluation.md`](../docs/models/gnn-evaluation.md).

  ```bash
  python scripts/plot_gnn_runs.py runs/<homo_sage> runs/<hetero_sage> runs/<hetero_gat>
  ```

See [`docs/synthetic-dataset/synthetic-dataset-usage.md`](../docs/synthetic-dataset/synthetic-dataset-usage.md) for the full
usage guide.

- `reproduce_run.py` — reproduce una corrida registrada a partir de su `run.json` (A45-8):
  reentrena con `train_gnn.py` usando solo la configuración, la semilla y la fuente de datos del
  registro y compara la corrida nueva con la original (configuración, datos, escalado, épocas,
  historia, métricas, predicciones y pesos). También recarga los checkpoints con `load_run` y
  verifica que reproducen sus predicciones. Si solo se tiene la copia versionada del `run.json`
  (`reports/gnn/<dataset>/run_<variante>.json`), compara las métricas con
  `reports/gnn/<dataset>/report.csv`. Escribe `reports/gnn/reproducibility/<dataset>_<variante>.md`
  y `.json`. Código de salida `1` si algo difiere fuera de tolerancia. Requiere los extras `graph`
  y, para la cohorte sintética, `baselines`. En D1 recalcula la cohorte supervisada (#138) desde
  `--sources` con el umbral registrado en `source.cohort`; una corrida D1 anterior a #138 no se
  puede reentrenar con este código. Véase
  [`docs/models/gnn-training.md`](../docs/models/gnn-training.md).

  ```bash
  python scripts/reproduce_run.py reports/gnn/synthetic/run_homo_sage.json
  python scripts/reproduce_run.py runs/<run_id>
  ```

- `create_cv_folds.py` — genera la validación cruzada por corral de D1 (D-07, #139):
  `StratifiedGroupKFold` agrupado por `pen_code` y estratificado por dieta, k = 5, semillas 0 a 9
  (o `--seeds N`), sobre la cohorte oficial de `configs/cohorts/d1_holofood.json`. Verifica que
  las tres dietas estén en todos los folds y que ningún corral se reparta entre folds. Escribe la
  asignación en `configs/splits/d1_holofood_cv.json` y la tabla de folds en
  `reports/cv/d1_pen_folds.md` y `.json`. Requiere la descarga de D1 y el extra `baselines`.
  Véase [`docs/models/cross-validation.md`](../docs/models/cross-validation.md).

  ```bash
  python scripts/create_cv_folds.py
  python scripts/create_cv_folds.py --min-ssu-reads 5000 --report-only
  ```

- `compare_baselines_d1_composition.py` — repite los baselines de A45-2 sobre D1 con el
  objetivo composicional de D-03 (dos log-razones más log T, #146) bajo la validación cruzada
  por corral de #139, y agrega `day_only` (solo el día de muestreo) y `ridge_design` (ridge
  sobre los factores del diseño, comparable con la Tabla 5 de la respuesta de Investigación).
  Lee la descarga registrada en `configs/sources.json` y el plan de
  `configs/splits/d1_holofood_cv.json`, y escribe `report.md`, `metrics.csv`,
  `fold_metrics.csv`, `selections.csv` y `run.json` en `--output` (por defecto
  `reports/baselines/d1_composition/`). Requiere el extra `baselines`. Véase
  [`docs/models/baselines-d1-composition.md`](../docs/models/baselines-d1-composition.md).

  ```bash
  python scripts/compare_baselines_d1_composition.py
  ```

- `evaluate_gnn_d1_composition.py` — reevalúa las tres variantes GNN en D1 con el objetivo
  composicional de D-03 (#146) bajo la validación cruzada por corral de #139 (#142): repite la
  grilla de A45-5 sin leer ningún test (val interno por corral), entrena cada variante por fold
  con detención temprana interna al train del fold, compara con los baselines de #140 y
  `day_only`, declara el criterio de F4 con su incertidumbre y ablaciona las aristas
  `inferred`. Escribe `report.md`, `metrics.csv`, `fold_metrics.csv`, `predictions.csv`,
  `folds.csv`, `selection.csv`/`selection.json` y `run.json` en `--output` (por defecto
  `reports/gnn/d1_composition/`), de forma incremental. Requiere los extras `graph` y
  `baselines` y los grafos de `scripts/build_graph.py --save-graphs`. Véase
  [`docs/models/gnn-d1-composition.md`](../docs/models/gnn-d1-composition.md).

  ```bash
  python scripts/evaluate_gnn_d1_composition.py
  ```
