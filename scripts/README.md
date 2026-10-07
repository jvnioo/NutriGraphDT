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
  the `graph` extra; see [`docs/heterodata-prototype.md`](../docs/heterodata-prototype.md)).

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
  [`docs/graph-integrity-rules.md`](../docs/graph-integrity-rules.md) and prints which graphs
  can be delivered to a model (VG-07). Exit code `0` means no `ERROR` findings, `1` means
  there are `ERROR` findings, and `2` means the dataset or the graphs could not be read. Use
  `--graphs` to also load the HeteroData prototype (safe load) and run the tensor rules, and
  `--report` to write the full JSON report. See
  [`docs/graph-validation-usage.md`](../docs/graph-validation-usage.md).

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
  See [`docs/holofood-source.md`](../docs/holofood-source.md).

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
  [`docs/graph-builder.md`](../docs/graph-builder.md) and
  [`docs/real-graph-validation-report.md`](../docs/real-graph-validation-report.md).

  ```bash
  python scripts/fetch_holofood.py
  python scripts/build_graph.py --save-graphs --overwrite
  ```

See [`docs/synthetic-dataset-usage.md`](../docs/synthetic-dataset-usage.md) for the full
usage guide.
