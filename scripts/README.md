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
  there are `ERROR` findings, and `2` means the dataset could not be read. Use `--report` to
  write the full JSON report. See
  [`docs/graph-validation-usage.md`](../docs/graph-validation-usage.md).

  ```bash
  python scripts/validate_graph.py
  python scripts/validate_graph.py --input artifacts/synthetic/v1 --report artifacts/validation/report.json
  ```

See [`docs/synthetic-dataset-usage.md`](../docs/synthetic-dataset-usage.md) for the full
usage guide.
