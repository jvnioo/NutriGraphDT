# Contributing to NutriGraphDT

NutriGraphDT is a collaborative academic research project. Contributions should remain reviewable, reproducible, traceable to the project plan, and compatible with the project's zero-cost infrastructure policy.

The Development Cell uses a **Scrumban workflow**. Read [`docs/process/workflow.md`](docs/process/workflow.md)
and the [`GitHub Project guide`](docs/process/project-board-guide.md) before taking or updating a
task.

## Taking a task

Normal development starts from a GitHub Issue in the **Ready** column of the project board.

1. Choose an unassigned Issue from **Ready**.
2. Confirm that its dependencies are available.
3. Assign the Issue to yourself.
4. Move it to **In Progress**.
5. Update your local `main` branch.
6. Create a short-lived branch from `main` (never from another unmerged feature branch).
7. Make one focused change that satisfies the Issue.
8. Run the local quality checks on the final state of the branch; there is no remote CI.
9. Push the branch and open a Pull Request against `main`, citing the check results.
10. Link the Issue, move it to **Review**, and request a review from another team member.
11. Address review comments and re-run the checks.
12. Merge only after an approving review and once the change satisfies the Definition of Done;
    delete the branch when merging.
13. Verify that the Issue closed and move it to **Done**.

The commands for each step, and the additional rules for automated agents, are in the
[`GitHub Project guide`](docs/process/project-board-guide.md).

Do not develop directly on `main` unless an exceptional repository-maintenance situation requires it.

Each contributor should normally keep **one main task in In Progress at a time**. Reviewing another contributor's PR does not count against this limit.

If there is no appropriate task in **Ready**, communicate that instead of starting untracked work.

## Branch naming

Use this format whenever work is linked to an Issue:

```text
<type>/<issue-number>-<short-description>
```

Supported prefixes:

- `feat` — new functionality
- `fix` — bug fix
- `docs` — documentation
- `test` — tests
- `refactor` — internal restructuring
- `chore` — tooling or repository maintenance
- `research` — exploratory/research work not yet part of stable implementation

Examples:

```text
feat/23-heterogeneous-graph-builder
research/27-pyg-heterodata-spike
docs/18-data-contract
fix/41-graph-integrity-validation
```

When no Issue exists for exceptional maintenance work, the issue-number component may be omitted.

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
- the related Issue/task.

Use `Closes #<issue-number>` in the PR description when merging the PR should close the Issue automatically.

Keep PRs small enough to review. Exploratory work should not silently become part of the stable architecture.

Once the PR is ready, the corresponding Issue belongs in **Review**, not **Done**. It moves to **Done** only after review, merge, and all applicable completion criteria are satisfied.

## Local checks

The repository has no remote CI: GitHub Actions is disabled because the project cannot pay for
Actions minutes. The author of each Pull Request is responsible for running these checks before
pushing and for citing the results in the PR description.

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

## Definition of Ready and Done

The canonical Definition of Ready, Definition of Done, board states, priorities, relative task sizes, self-assignment rules, blocked-work policy, and weekly planning process are defined in [`docs/process/workflow.md`](docs/process/workflow.md).

Do not move an Issue to **Ready** if it lacks critical information or cannot be completed without a paid dependency.

Do not consider a task **Done** merely because implementation appears complete. Review, integration, required testing, documentation, scientific traceability, and cost-policy compliance are part of completion where applicable.

## Research and scientific data

- Record the source and license of external datasets.
- Do not commit restricted, private, or confidential data.
- Clearly label synthetic or simulated data.
- Document assumptions used to transform biological information into computational structures.
- Avoid presenting preliminary computational outputs as validated biological conclusions.
- When a Development task depends on scientific definitions that have not yet been delivered, mark the Issue as blocked or keep it outside Ready unless an approved fallback has been explicitly documented.

## Dependencies

Do not add a dependency only because it is convenient. A new dependency should have a clear technical purpose, a compatible license, and a sustainable free/open-source usage path.

Any service requiring a payment method, paid subscription, paid compute, proprietary hosted tracking, or consumption-based billing must not become a required project dependency.

See [`docs/process/cost-policy.md`](docs/process/cost-policy.md) for the project's cost constraint.

## Architecture

Follow the boundaries described in [`docs/architecture/architecture.md`](docs/architecture/architecture.md). Architectural changes should be discussed through an Issue or Pull Request and documented before they become implicit conventions.
