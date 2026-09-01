# Contributing to NutriGraphDT

NutriGraphDT is a collaborative academic research project. Contributions should remain reviewable, reproducible, and traceable to the project plan.

## Workflow

1. Update your local `main` branch.
2. Create a short-lived branch from `main`.
3. Make one focused change.
4. Run the local quality checks.
5. Commit using the project convention.
6. Push the branch and open a Pull Request.
7. Request review before merging.

Do not develop directly on `main` unless an exceptional maintenance situation requires it.

## Branch naming

Use one of the following prefixes:

- `feat/<short-description>` — new functionality
- `fix/<short-description>` — bug fix
- `docs/<short-description>` — documentation
- `test/<short-description>` — tests
- `refactor/<short-description>` — internal restructuring
- `chore/<short-description>` — tooling or repository maintenance
- `research/<short-description>` — exploratory/research work not yet part of production code

Examples:

```text
feat/heterogeneous-graph-builder
research/pyg-heterodata-spike
docs/data-contract
fix/graph-integrity-validation
```

## Commit convention

Use concise Conventional Commit-style messages:

```text
feat: add heterogeneous graph schema
fix: prevent invalid metabolite edges
test: cover graph integrity validation
docs: document data contract assumptions
research: compare heterogeneous convolution layers
chore: update development tooling
```

A commit should describe one logical change. Avoid messages such as `changes`, `update`, `stuff`, or `final`.

## Pull Requests

A Pull Request should explain:

- what changed;
- why the change is needed;
- how it was validated;
- scientific assumptions or limitations, when applicable;
- related issue/task, when available.

Keep PRs small enough to review. Exploratory work should not silently become part of the stable architecture.

## Local checks

Before opening a PR:

```bash
ruff check .
ruff format --check .
mypy src
pytest
```

Or run configured hooks:

```bash
pre-commit run --all-files
```

All baseline tooling is free/open source and runs locally.

## Research and scientific data

- Record the source and license of external datasets.
- Do not commit restricted, private, or confidential data.
- Clearly label synthetic or simulated data.
- Document assumptions used to transform biological information into computational structures.
- Avoid presenting preliminary computational outputs as validated biological conclusions.

## Dependencies

Do not add a dependency only because it is convenient. A new dependency should have a clear technical purpose, a compatible license, and a sustainable free/open-source usage path.

Any service requiring a payment method, paid subscription, paid compute, proprietary hosted tracking, or consumption-based billing must not become a required project dependency.

## Architecture

Follow the boundaries described in `docs/architecture.md`. Architectural changes should be discussed through an issue or Pull Request and documented before they become implicit conventions.
