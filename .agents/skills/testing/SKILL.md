---
name: testing
description: Design, implement, and evaluate tests for NutriGraphDT code, data pipelines, graph construction, models, scientific constraints, simulation, explainability, or API behavior. Use when changed behavior needs validation or a task is specifically about testing.
---

# Testing

Choose tests based on the contract and risks of the changed component. Favor deterministic, focused tests that demonstrate observable behavior and important invariants.

## General workflow

1. Read `AGENTS.md`, the Issue, and relevant code/tests.
2. Identify the behavior or invariant that must be protected.
3. Identify valid, boundary, invalid, and failure cases.
4. Add the smallest useful test set with clear failure messages.
5. Run targeted tests first.
6. Run the full applicable local quality suite.
7. Report exactly what was executed.

Do not write tests that merely reproduce implementation details without protecting meaningful behavior.

## Pure functions and utilities

Test:

- representative valid inputs;
- boundary values;
- invalid input when the function owns validation;
- deterministic output/invariants;
- numerical tolerance when floating-point behavior is expected.

## Data loaders and preprocessing

Test:

- valid minimal input;
- required/missing fields;
- invalid types/units/schema values;
- normalization/preprocessing invariants;
- provenance metadata preservation when applicable;
- clear distinction between real, synthetic, and simulated data;
- predictable failure for malformed inputs.

Use small fixtures rather than large real datasets in ordinary unit tests.

## Heterogeneous graph construction

Test:

- expected node types;
- expected edge relation types;
- feature/attribute shapes and required metadata;
- valid source/target type combinations;
- missing references and invalid relations;
- graph integrity after construction;
- deterministic synthetic reference cases where practical.

A graph object existing in memory is not sufficient validation; test schema and integrity explicitly.

## Models

Before expensive training tests, prefer small deterministic checks:

- model construction;
- forward-pass compatibility;
- input/output dimensions;
- handling of relevant node/edge types;
- finite outputs for valid inputs;
- predictable failure for incompatible shapes/contracts;
- serialization/loading when that becomes part of the contract.

Do not make ordinary tests depend on GPU/CUDA unless the project explicitly introduces such a requirement and retains a no-cost local alternative.

## Scientific / biochemical constraints

Test independently from the predictive model when practical.

Use cases with known expected behavior:

- valid state -> low/zero penalty or accepted condition;
- deliberate violation -> positive/expected penalty or rejection;
- non-negativity boundaries;
- mass-balance/stoichiometric examples only when their values are scientifically approved or explicitly synthetic test fixtures;
- differentiability/gradient flow when the constraint participates in optimization.

Label synthetic numerical examples clearly. A passing synthetic test does not validate the biological assumption itself.

## Training and evaluation

For pipeline tests, use tiny controlled data/configurations.

Validate:

- train/evaluation split behavior;
- metric calculation;
- no accidental test-set use in training/tuning;
- seed/config propagation where applicable;
- experiment metadata output;
- expected checkpoint/result contract if introduced.

Full research experiments are not substitutes for unit/integration tests, and unit tests are not evidence of predictive performance.

## Simulation

Test:

- basal scenario construction;
- intervention scenario changes;
- comparison contracts;
- uncertainty/result serialization when implemented;
- invalid scenario inputs;
- deterministic behavior when a deterministic test configuration is requested.

## Explainability

Test API/contract behavior rather than asserting that an explanation is biologically correct.

Validate:

- expected node/edge identifiers;
- output shapes/structures;
- ranking/subgraph contract;
- compatibility with the selected model;
- graceful handling of unsupported methods.

Scientific interpretation belongs to validation/documentation, not to a unit-test assertion unless an explicit validated invariant exists.

## API

Test:

- request validation;
- successful response contract;
- status/error codes;
- malformed/unsupported inputs;
- serialization;
- separation between API contract and domain internals.

Prefer local test clients; do not require paid hosted infrastructure.

## Regression tests

When fixing a bug, first create or identify a test that fails for the reported behavior when practical, then verify the fix makes it pass without breaking existing tests.

## Required quality checks

Run applicable repository checks:

```bash
ruff check .
ruff format --check .
mypy src
pytest
```

Use targeted pytest commands during iteration, but run the relevant complete suite before reporting completion.

Never report a check as passed unless it was executed successfully. If an environment limitation prevents execution, state the command and limitation.
