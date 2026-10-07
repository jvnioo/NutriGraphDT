# Scrumban Workflow

This document defines the working model used by the NutriGraphDT Development Cell.

The project uses **Scrumban**: a weekly planning cadence combined with a continuous Kanban-style flow. Work is represented as GitHub Issues and progresses through a shared board.

The operational procedure for contributors and automated agents is documented in the
[`GitHub Project guide`](project-board-guide.md). It defines how to inspect, take, create,
update, and verify Project items without duplicating Issues or bypassing this workflow.

## Board states

The board uses the following states:

1. **Backlog** — future work that is not yet ready to be started.
2. **Ready** — tasks prepared for the current work cycle and available for self-assignment.
3. **In Progress** — tasks currently being developed.
4. **Review** — tasks with a Pull Request ready for review.
5. **Done** — completed, reviewed, and integrated work.
6. **Blocked** — work that cannot continue because of a dependency, missing information, or a technical/scientific obstacle.

A task should have only one active board state.

## Weekly planning

At the beginning of each week, the Development subleader reviews the project plan, current dependencies, completed work, and information received from other cells.

Tasks that can realistically be worked on during the week are refined and moved to **Ready**.

The weekly planning process is:

```text
Review progress and dependencies
        ↓
Refine upcoming tasks
        ↓
Move executable tasks to Ready
        ↓
Team members self-assign work
        ↓
Development and review
        ↓
Close completed work
        ↓
Prepare the next weekly cycle
```

Scrumban does not require every task selected at the start of the week to be completed within that same week. Work continues through the board until it meets the Definition of Done.

## Self-assignment

Tasks in **Ready** are intentionally left without a developer assigned in advance.

Each team member may choose a task according to their interests, technical preparation, and the available work.

Before starting a task, the contributor must:

1. confirm that the Issue is in **Ready**;
2. verify that no other contributor is already assigned;
3. assign the Issue to themselves;
4. move it to **In Progress**;
5. create a branch from the current `main` branch.

A task that already has an assignee must not be taken by another contributor unless both contributors coordinate first.

If there is no appropriate task in **Ready**, the contributor should communicate this instead of starting untracked work.

## Work-in-progress limit

Each contributor should have **no more than one main task in In Progress at a time**.

This limit applies to active development tasks. Contributors may still review Pull Requests, discuss research questions, or help another team member while their own task is active.

The purpose of the limit is to finish work before starting additional work and to keep the board representative of the real project state.

## Task structure

Development work should be represented by a GitHub Issue containing at least:

- a concrete objective;
- enough context to understand why the task exists;
- expected work;
- acceptance criteria;
- known dependencies;
- relevant technical or scientific notes;
- an approximate size: `S`, `M`, or `L`.

Tasks larger than `L` should normally be split before moving to **Ready**.

### Size guide

- **S** — small, focused change with limited scope.
- **M** — normal development task with several related steps.
- **L** — considerable task that is still independently reviewable.

These sizes are relative planning aids. They are **not estimates of hours** and must not be interpreted as individual workload commitments.

## Priority guide

Tasks may use the following priority convention:

- **P0 — Blocking:** prevents other required work from progressing.
- **P1 — High:** important for the current project phase.
- **P2 — Normal:** default priority for ordinary planned work.
- **P3 — Low:** useful work that can wait without affecting current progress.

`P0` should be exceptional.

## Definition of Ready

An Issue can enter **Ready** when:

- its objective is understandable;
- acceptance criteria are explicit;
- critical dependencies are available;
- required external information is available, or the task explicitly defines an approved fallback;
- the task is small enough to be developed and reviewed independently;
- the work belongs to the Development Cell scope;
- the task does not require a paid service or paid infrastructure.

If one of these conditions is missing, the task should remain in **Backlog** or move to **Blocked**.

## Development flow

Once a contributor takes a task:

```text
Ready
  ↓
Self-assign Issue
  ↓
In Progress
  ↓
Create branch
  ↓
Develop and test
  ↓
Open Pull Request
  ↓
Review
  ↓
Address review comments
  ↓
Merge to main
  ↓
Done
```

## Branch naming

Branches should include the Issue number whenever the work originated from an Issue.

Recommended format:

```text
<type>/<issue-number>-<short-description>
```

Examples:

```text
feat/23-heterogeneous-node-types
fix/41-invalid-edge-validation
docs/18-data-contract
test/32-graph-builder
research/27-pyg-heterodata-spike
```

Supported prefixes are described in [`CONTRIBUTING.md`](../../CONTRIBUTING.md).

## Pull Requests and Review

When implementation is ready for review:

1. push the branch;
2. open a Pull Request against `main`;
3. link the corresponding Issue using `Closes #<issue>` when appropriate;
4. move the Issue to **Review**;
5. complete the PR checklist;
6. address requested changes before merge.

A Pull Request should represent one coherent task whenever practical.

Direct development on `main` is not part of the normal workflow.

## Definition of Done

A task can move to **Done** only when all applicable conditions are satisfied:

- acceptance criteria are met;
- relevant tests exist and pass;
- formatting, linting, type checks, and automated tests pass where applicable;
- the Pull Request has been reviewed;
- the change has been merged into `main`;
- required documentation has been updated;
- no secrets, credentials, private data, or temporary artefacts were committed;
- new scientific assumptions, transformations, or limitations are documented where applicable;
- external data provenance and licensing are recorded where applicable;
- the solution introduces no mandatory paid service, paid API, paid compute, or billing requirement.

## Blocked work

Move an Issue to **Blocked** when work cannot continue because of a concrete dependency.

The Issue should include a short note stating:

- what is blocking progress;
- what information or action is needed;
- who or what the dependency comes from, when relevant.

Typical examples include missing definitions from the Research Cell, unavailable data contracts, unresolved scientific assumptions, or a prerequisite Issue that has not been completed.

Once the blocker is resolved, the task returns to **Ready** or **In Progress**, depending on whether the original contributor is continuing the work.

## Unplanned work

Relevant work discovered during development should not be silently added to the current task if it meaningfully expands scope.

Create a new Issue instead, link it from the current task, and allow it to enter the normal Backlog/Ready process.

Small corrections that are directly necessary to satisfy the current Issue may remain within the same Pull Request when they do not make the review substantially harder.

## Cost constraint

The project has no budget for paid development infrastructure. Any task that proposes new tooling must respect [`cost-policy.md`](cost-policy.md).

No contributor should require a paid subscription, payment method, commercial API credits, rented cloud compute, or proprietary paid development platform to complete an ordinary NutriGraphDT task.
