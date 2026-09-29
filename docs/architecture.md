# Architecture

## Status

This document defines **initial module boundaries**, not a frozen implementation. NutriGraphDT is still in its research and technical-foundation stage. Scientific definitions and data contracts provided during later phases may require architectural refinement.

## Architectural goals

The software architecture should support:

- reproducible ingestion of public or explicitly synthetic research data;
- construction and validation of a heterogeneous gastrointestinal graph;
- comparison of classical baselines and graph neural networks;
- integration of scientifically informed biochemical constraints;
- reproducible scenario simulation;
- explainability at node, edge, and subgraph level;
- an API boundary for an experimental web interface;
- local execution without mandatory paid infrastructure.

## Planned modules

### `data`

Responsible for data contracts, loaders, normalization/preprocessing, provenance metadata, and synthetic/reference datasets.

The initial synthetic data contract, including its node and edge schema, serialization format,
and mapping to `HeteroData`, is defined in
[`docs/synthetic-dataset-spec.md`](synthetic-dataset-spec.md).

It must not encode model-specific training logic.

### `graph`

Responsible for heterogeneous node/edge schemas, graph construction, integrity validation, and conversion to graph-learning representations.

The graph schema should remain explicit and documented rather than being hidden inside model code.

The integrity rules that a graph must satisfy before reaching a model, with their severities
and admitted exceptions, are defined in [`docs/graph-integrity-rules.md`](graph-integrity-rules.md).
`nutrigraphdt.graph.validation.validate_graph` runs all of them, and
`prepare_graphs_for_model` is the gate that withholds invalid graphs before they reach a model;
see [`docs/graph-validation-usage.md`](graph-validation-usage.md).

### `models`

Responsible for predictive baselines and GNN implementations, training/evaluation interfaces, and model-level metrics.

Model architecture selection remains a research decision. The repository must not assume that a specific GNN family is final before comparative evaluation.

### `constraints`

Responsible for biochemical/scientific constraints such as mass-balance, non-negativity, stoichiometric, or physiological plausibility terms once validated definitions become available.

Constraints should be testable independently from the predictive model whenever possible.

### `simulation`

Responsible for defining basal/intervention scenarios, invoking trained computational components, comparing outputs, representing uncertainty, and serializing simulation results.

### `explainability`

Responsible for model explanations, node/edge importance, relevant subgraphs, and other interpretable outputs. Explainability methods remain subject to model compatibility and validation.

### `api`

Responsible for exposing stable application-facing contracts. Domain/model internals should not leak directly into HTTP handlers.

## Dependency direction

A target dependency direction is:

```text
data -> graph -> models
                -> constraints
models + constraints -> simulation -> explainability
                               |
                               v
                              api
```

This is a conceptual guide. It should be refined when interfaces and data contracts are formalized.

## Configuration

Research parameters should be explicit and versionable. Configuration files belong under `configs/` when they become necessary. Avoid hard-coded paths, dataset-specific constants, or experiment parameters inside reusable modules.

## Generated artifacts

Large datasets, checkpoints, experiment runs, and generated artifacts are excluded from Git by default. Reproducibility should rely on documented provenance, scripts, configuration, and metadata rather than committing large generated files.

## External services

No architectural component may require paid cloud compute, paid databases, proprietary hosted experiment trackers, or another billable SaaS service for normal project operation. Local files and open-source tooling are the default baseline.

## Evolution

Architectural decisions with lasting consequences should be documented. If the project reaches a point where alternatives must be formally compared, Architecture Decision Records (ADRs) may be introduced under `docs/adr/`.
