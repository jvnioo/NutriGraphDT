# Coding Standards for AI-Assisted Development

This document defines the baseline coding practices that human contributors and AI coding agents should follow in NutriGraphDT.

## General principles

- Prefer correctness, clarity, reproducibility, and maintainability over cleverness.
- Implement the smallest complete solution for the current task.
- Keep changes focused and reviewable.
- Avoid speculative abstractions and premature optimization.
- Inspect and reuse existing code before introducing parallel mechanisms.
- Do not silently change public behavior, data contracts, scientific assumptions, or architecture.

## Python baseline

The project targets Python 3.11 or newer.

Use:

- Ruff for linting and formatting;
- mypy with the repository configuration for static type checking;
- pytest for tests;
- pre-commit for configured repository checks.

## Types and interfaces

- Add type annotations to public functions, methods, and non-trivial internal interfaces.
- Prefer explicit domain types or structured objects when they improve correctness.
- Avoid using `Any` to bypass type design unless there is a documented interoperability reason.
- Keep public contracts stable unless the Issue explicitly requires a breaking change.
- Validate external or untrusted input at system boundaries.

## Functions and classes

Prefer small, cohesive units with one clear responsibility.

Use a class when state, invariants, lifecycle, or a meaningful domain abstraction justify it. Do not create a class when a small function or simple data structure is clearer.

Avoid:

- deeply nested control flow;
- very large functions with unrelated responsibilities;
- hidden mutable global state;
- duplicated business/scientific logic across modules;
- generic utility modules that accumulate unrelated helpers.

## Errors

- Raise specific exceptions for expected invalid states.
- Do not use broad `except Exception` blocks to suppress errors.
- Preserve useful context when wrapping exceptions.
- Fail early when required configuration, schema, or scientific inputs are invalid.
- Error messages should help a contributor identify the failing contract or input.

## Configuration

Research and application parameters should be explicit and versionable.

Do not hard-code:

- local filesystem paths;
- machine-specific settings;
- dataset-specific constants inside reusable logic;
- model or experiment parameters that should be configuration;
- secrets or credentials.

Place reusable configuration under `configs/` when the relevant project phase introduces it.

## Data and graph code

- Keep provenance metadata available through ingestion and preprocessing when practical.
- Keep graph node/edge schemas explicit and documented.
- Validate graph integrity rather than relying on downstream model failures.
- Do not mix data loading, preprocessing, graph construction, and model training in a single opaque pipeline.
- Synthetic data must be clearly distinguishable from real data.

## ML and research code

When stochastic behavior is involved:

- set and record seeds where practical;
- record relevant configuration;
- distinguish training, validation, and test data correctly;
- avoid data leakage;
- make metrics explicit;
- preserve enough metadata to reproduce important experiments.

Do not optimize for a metric by introducing undocumented changes to the evaluation protocol.

Model architecture selection is a research decision. Do not present one GNN family as final without comparative evidence defined by the project.

## Scientific constraints

Scientific/biochemical constraints should be independently testable when possible.

Do not encode a numerical constant, relation, limit, or transformation as domain truth unless its origin is documented or explicitly provided by the project.

Provisional assumptions must be marked as provisional.

## Dependencies

Before adding a dependency, confirm:

1. the repository does not already provide the required capability;
2. the standard library is not a reasonable solution;
3. the dependency has a clear technical purpose;
4. its license is compatible with project use;
5. it has a sustainable free/open-source path;
6. it does not make a paid service or hosted platform mandatory.

Pin or constrain versions only when there is a reproducibility or compatibility reason.

## Documentation in code

Use docstrings for public or non-obvious interfaces when they add information not evident from the signature and implementation.

Comments should explain reasons, invariants, scientific assumptions, unusual constraints, or non-obvious trade-offs. Avoid comments that simply translate the next line of code into prose.

## Tests

Changed behavior should normally have corresponding tests.

Prefer deterministic, focused tests. Test contracts and observable behavior rather than internal implementation details unless the internal invariant itself is important.

Use the repository `testing` skill for detailed testing guidance.

## Required local checks

Run all applicable checks before a Pull Request is considered ready:

```bash
ruff check .
ruff format --check .
mypy src
pytest
```

When a check is not applicable or cannot be executed, document the reason accurately.
