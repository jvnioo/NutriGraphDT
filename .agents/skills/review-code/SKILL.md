---
name: review-code
description: Review NutriGraphDT code, diffs, or Pull Requests for correctness, acceptance criteria, architecture, tests, scientific integrity, documentation, security, and cost-policy compliance. Use for code review; do not use as a formatting-only lint pass.
---

# Review Code

Review changes against the actual task and repository rules. Prioritize defects and risks that a contributor should act on before merge.

## Required context

Before reviewing:

1. read `AGENTS.md`;
2. read the related Issue/task and acceptance criteria;
3. read `docs/workflow.md` and `CONTRIBUTING.md`;
4. inspect the changed files and relevant surrounding code/tests;
5. consult `docs/architecture.md`, `docs/cost-policy.md`, `docs/documentation-policy.md`, and `docs/ai/` when applicable.

## Review priorities

Review in this order:

1. correctness and regressions;
2. acceptance-criteria coverage;
3. data/scientific validity and unsupported assumptions;
4. security, privacy, secrets, and restricted data;
5. architecture and contract violations;
6. reproducibility and experiment integrity;
7. missing or inadequate tests;
8. error handling and edge cases;
9. documentation/traceability gaps;
10. unnecessary dependencies or paid infrastructure;
11. maintainability when it materially affects the change.

Do not spend review attention on style issues already handled reliably by Ruff unless the issue affects semantics or configured checks are not being run.

## Issue alignment

Ask:

- Does the change solve the Issue that was requested?
- Does it satisfy each applicable acceptance criterion?
- Did it silently expand scope?
- Did it change public/data/scientific contracts not requested by the Issue?
- Is newly discovered work better represented as a follow-up Issue?

## Architecture review

Flag changes that:

- mix data ingestion, graph construction, training, and application/API concerns without justification;
- hide graph schema or scientific constraints inside unrelated implementation details;
- leak domain/model internals directly through API handlers;
- introduce circular or inverted dependencies against documented boundaries;
- add speculative architecture not required by current work.

## Scientific review

Flag:

- invented biological relations, constants, limits, or citations;
- unsupported causal claims;
- synthetic data presented as real observations;
- predictions presented as validated biological conclusions;
- undocumented scientific assumptions;
- source evidence applied outside its organism/condition/scope without qualification;
- explainability output interpreted as causal mechanism without independent evidence;
- changes to evaluation protocols that invalidate comparisons.

If a scientific claim requires verification, use or recommend the `research-reference` skill.

## Testing review

Check whether tests cover the behavior changed and likely failure modes.

For data/graph/model/constraint/API changes, use the guidance in the `testing` skill.

Do not accept "tests pass" as sufficient if important acceptance criteria are not tested or manually validated where necessary.

## Documentation review

Use `docs/documentation-policy.md` to determine whether the change should preserve:

- technical contracts;
- experiment metadata/results;
- scientific evidence;
- setup/user behavior;
- academic-report evidence;
- potential paper material.

A missing durable record is a review finding when the information would otherwise be difficult to reconstruct.

## Cost and dependency review

Flag any required dependency on:

- paid APIs;
- paid cloud/compute/storage;
- paid CI runners;
- commercial hosted experiment trackers;
- subscriptions/payment methods;
- temporary free credits or trials that are necessary for normal operation.

Also flag dependencies added without a clear technical reason or compatible licensing path.

## Finding format

For each actionable finding, include:

- severity: `blocking`, `high`, `medium`, or `low`;
- precise file/area;
- what is wrong;
- why it matters;
- a safe correction direction when useful.

Keep findings specific and evidence-based. Do not manufacture hypothetical defects without a plausible execution or requirement path.

## Review conclusion

Conclude with:

- whether the change appears ready for merge;
- unresolved blocking/high findings;
- validation or documentation still required;
- any follow-up work that should become a separate Issue.
