---
name: implement-issue
description: Implement a NutriGraphDT GitHub Issue or scoped development task. Use when asked to build, fix, refactor, or complete an Issue. Do not use for broad unscheduled redesigns or research-only questions.
---

# Implement Issue

Implement the smallest complete change that satisfies the current NutriGraphDT task while preserving workflow, architecture, scientific integrity, tests, documentation, and the zero-cost baseline.

## Required context

Before editing:

1. read `AGENTS.md`;
2. read the current Issue/task and its acceptance criteria;
3. read `docs/workflow.md` and `CONTRIBUTING.md`;
4. inspect relevant code, tests, and documentation;
5. read `docs/architecture.md` if module boundaries or interfaces are involved;
6. read `docs/cost-policy.md` before adding dependencies, services, compute, storage, CI, APIs, or infrastructure;
7. read `docs/documentation-policy.md` and relevant `docs/ai/` guidance.

## Pre-implementation check

Confirm:

- the objective is clear;
- acceptance criteria are explicit;
- required dependencies/information exist or an approved fallback is documented;
- the work is within the Issue scope;
- there is no conflicting implementation already present;
- the proposed solution does not require paid infrastructure.

If a critical requirement is ambiguous, do not invent it. State the ambiguity and choose only a clearly safe, reversible implementation when the task permits it.

## Implementation workflow

1. Identify the files and contracts affected.
2. Reuse existing patterns before creating new abstractions.
3. Implement the minimal coherent change.
4. Keep unrelated cleanup out of the change.
5. Add or update tests for changed behavior.
6. Update documentation/evidence when the task creates durable knowledge.
7. Run applicable local checks.
8. Inspect the final diff against the acceptance criteria.
9. Report what changed, what was validated, and any remaining limitations.

## Scope discipline

Do not silently add:

- unrelated refactors;
- future features;
- speculative architecture;
- extra dependencies;
- new scientific assumptions;
- changes to evaluation methodology;
- unrelated documentation rewrites.

When meaningful new work is discovered, propose a separate Issue.

## Architecture

Respect the current conceptual boundaries:

```text
data -> graph -> models
                -> constraints
models + constraints -> simulation -> explainability
                               |
                               v
                              api
```

Do not place domain/model logic directly in API handlers or hide graph/data contracts inside model implementations.

## Scientific behavior

When implementation depends on a biological relation, numerical constraint, dataset interpretation, or scientific assumption:

- verify the project has supplied or approved it;
- otherwise use the `research-reference` skill if external evidence is appropriate;
- preserve the source and limitations when consequential;
- mark provisional/synthetic fallbacks clearly;
- never present a computational convenience as scientific truth.

## Testing

Use the `testing` skill for substantial test design.

Run applicable checks:

```bash
ruff check .
ruff format --check .
mypy src
pytest
```

Never state that a check passed unless it actually ran successfully.

## Documentation check

Before considering implementation complete, ask whether the task affects:

- technical documentation;
- architecture;
- data/graph contracts;
- experiment records;
- scientific evidence;
- development instructions;
- user documentation;
- course-report evidence;
- potential paper material.

Use the `document-project` skill when any category applies.

## Completion output

Summarize:

- files/behavior changed;
- acceptance criteria addressed;
- tests/checks executed and their result;
- documentation/evidence updated;
- assumptions or unresolved limitations;
- follow-up work that should become a separate Issue.

Do not merge the change automatically unless a human explicitly requests and the repository workflow permits it.
