---
name: document-project
description: Decide what NutriGraphDT knowledge must be preserved and create or update technical docs, user docs, experiment records, scientific evidence, academic report notes, or paper notes. Use when a change produces durable knowledge; do not create documentation that only restates obvious code.
---

# Document Project

Preserve useful, traceable project knowledge at the moment it is created so it can support maintenance, reproducibility, user guidance, course evaluation, and possible scientific publication later.

## Start with documentation impact

Read `AGENTS.md` and `docs/documentation-policy.md`.

Ask:

> What information produced by this task would be difficult to reconstruct accurately later?

Classify the impact before writing anything.

## Documentation routing

Use this guide:

```text
Code/API/contract behavior
    -> technical documentation

Setup/developer workflow
    -> docs/development.md

User-visible simulator behavior
    -> user manual/documentation

Meaningful computational experiment
    -> experiment record

Scientific claim/relation/constraint/source
    -> scientific evidence record

Lasting architecture choice with alternatives
    -> architecture docs / future ADR

Project execution/result important to course evaluation
    -> academic report notes

Methods/results/comparisons/limitations useful for publication
    -> research paper notes
```

One task may require more than one category.

Do not create empty folder trees or placeholder pages solely because the documentation policy shows a future structure.

## Technical documentation

Document contracts, decisions, setup, and non-obvious behavior rather than translating code line by line.

Useful technical content includes:

- component responsibility;
- inputs/outputs;
- schemas and invariants;
- configuration;
- failure behavior;
- dependencies;
- important assumptions;
- reproducibility procedures;
- limitations.

Keep documentation synchronized with implemented behavior. Do not describe planned functionality as if it already exists.

## Experiment records

For meaningful experiments, preserve:

- identifier/date;
- question/objective;
- dataset/version/provenance;
- preprocessing;
- model/baseline;
- configuration/hyperparameters;
- random seed where practical;
- split/evaluation protocol;
- metrics;
- code commit/version;
- results;
- interpretation;
- failures/anomalies;
- limitations.

Do not rewrite a historical experiment record to hide a failed or invalid run. Mark invalidation and create a new record when needed.

## Scientific evidence

When a scientific source influences implementation or interpretation, record:

- claim/relation;
- stable source identifier;
- evidence type;
- organism/condition/context;
- relevant finding;
- how NutriGraphDT uses it;
- limitations/conflicts;
- status: provisional, accepted, superseded, or rejected.

Use the `research-reference` skill first when evidence still needs verification.

## Academic report notes

Preserve concise factual evidence useful for later course reporting:

- what problem/task was addressed;
- relevant planning or methodology;
- decision and rationale;
- implementation/result;
- validation performed;
- blocker/risk/change in plan;
- limitation or lesson learned;
- related Issue/PR/commit when practical.

Do not draft inflated narrative merely to create report material. Preserve facts that can later be synthesized.

## Potential paper notes

Capture publication-relevant material when it emerges:

- research question/hypothesis;
- methods that materially affect results;
- dataset/cohort definition;
- comparison/ablation design;
- meaningful quantitative result;
- negative/inconclusive result that affects interpretation;
- uncertainty;
- limitation;
- observation requiring later scientific discussion.

Separate result from interpretation. Do not turn preliminary observations into conclusions.

## User documentation

Document only implemented features.

For the simulator, eventually cover:

- purpose and scope;
- inputs and scenario setup;
- basal/intervention comparison;
- result interpretation;
- uncertainty/explainability;
- common errors;
- limitations;
- warning that the prototype does not replace in vivo/in vitro validation or provide commercial nutritional advice.

## Traceability

Link documentation to durable identifiers when practical:

- Issue;
- PR;
- commit;
- experiment ID;
- dataset/accession;
- DOI/PMID/source URL.

Do not rely on chat history as the only record of a consequential decision.

## Accuracy check

Before finishing:

- verify that every factual claim is supported by repository evidence or a verified source;
- distinguish implemented behavior from planned work;
- distinguish synthetic/simulated data from real observations;
- distinguish model predictions from scientific conclusions;
- do not invent missing dates, results, settings, decisions, or citations.

## Completion output

Report:

- documentation categories affected;
- files created/updated;
- important traceability links/identifiers recorded;
- any documentation intentionally deferred and why.
