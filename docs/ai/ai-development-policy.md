# AI-Assisted Development Policy

AI tools are allowed and expected to support NutriGraphDT development, but they do not replace contributor responsibility, project governance, scientific judgment, testing, or human review.

## Purpose

AI may assist with:

- implementation;
- code review;
- test design;
- technical research;
- scientific-reference discovery and synthesis;
- documentation;
- experiment analysis;
- issue refinement;
- debugging and refactoring within approved scope.

The same quality and traceability requirements apply regardless of whether code or documentation was written manually or with AI assistance.

## Human ownership

The contributor submitting a change must be able to explain:

- what changed;
- why the change is required;
- how it works at the relevant level;
- how it was validated;
- what assumptions or limitations remain.

Generated output must be reviewed before it is proposed for merge.

Do not merge AI-generated code solely because it compiles, appears plausible, or was produced by a strong model.

## Repository authority

Repository instructions and the current Issue take precedence over generic AI suggestions.

Agents should consult `AGENTS.md` and the referenced project documentation before making changes.

When the repository does not define an answer, an agent should distinguish external evidence or its own proposal from established project decisions.

## Scope control

AI agents must not silently:

- redesign architecture outside the current task;
- add unrelated refactors;
- introduce dependencies or services not required by the task;
- create new scientific requirements;
- change evaluation protocols;
- expand user-facing scope;
- resolve scientific uncertainty by inventing a value or assumption.

Meaningful additional work should become a separate Issue.

## Verification

AI-generated changes must pass the same checks as human-generated changes.

At minimum, run applicable repository checks and verify the acceptance criteria.

Agents must report validation truthfully. If a test, command, external lookup, or experiment could not be run, state that limitation explicitly.

## Research and citations

Do not accept citations produced by an AI model without verifying that the source exists and supports the claim.

Consequential technical and scientific references should be preserved in repository documentation according to `docs/ai/source-policy.md` and `docs/documentation-policy.md`.

## Privacy and secrets

Do not paste or expose secrets, private credentials, restricted data, or confidential material to an AI tool unless the tool and project explicitly permit that data handling.

Repository agents must never commit secrets or private data.

## Cost policy

AI-assisted workflows must respect `docs/cost-policy.md`.

Do not configure the repository so ordinary contributors must purchase AI credits, commercial APIs, hosted agent services, cloud compute, or another billable tool to develop or reproduce NutriGraphDT.

A contributor may personally use an AI product they already have access to, but the repository workflow must remain usable without requiring that paid product as project infrastructure.

## Documentation duty

AI assistance often accelerates implementation but can make decisions harder to reconstruct later. Therefore, consequential decisions, experiments, assumptions, and sources must be written into the repository rather than remaining only inside chat histories.

Use `docs/documentation-policy.md` to determine what should be preserved.

## Recommended agent workflow

```text
Read Issue and AGENTS.md
        ↓
Inspect relevant docs/code/tests
        ↓
Identify uncertainty and required sources
        ↓
Implement the smallest complete change
        ↓
Add/update tests
        ↓
Run local quality checks
        ↓
Review the diff against the Issue
        ↓
Update required documentation/evidence
        ↓
Open PR for human review
```

## Tool neutrality

`AGENTS.md` and the files under `docs/ai/` define the repository's canonical AI-development expectations.

Vendor-specific instruction files may mirror or point to these rules, but they must not create a conflicting development policy.
