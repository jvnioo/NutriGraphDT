---
name: research-reference
description: Research and verify technical or scientific references that materially affect NutriGraphDT code, data, experiments, constraints, or interpretation. Use when authoritative external evidence is needed. Do not use to invent missing project requirements.
---

# Research Reference

Find, verify, and preserve high-quality references for consequential technical or scientific decisions.

## Start with the question

State the exact question being answered before searching.

Separate:

- what the repository already defines;
- what external evidence is needed to establish;
- what remains a project decision even after evidence is found.

Do not replace a missing project decision with an arbitrary literature choice.

## Source hierarchy

Follow `docs/ai/source-policy.md`.

For technical questions, prefer:

1. repository contracts and documentation;
2. official language/library/framework documentation;
3. official standards/specifications/releases/upstream source;
4. authoritative technical publications;
5. secondary/community sources only as support.

For scientific questions, prefer:

1. directly relevant original peer-reviewed research;
2. authoritative scientific databases;
3. high-quality systematic/review literature for context;
4. recognized institutional sources;
5. secondary sources only when stronger evidence is unavailable.

## Verification

For every consequential reference:

- confirm the source exists;
- verify that it supports the actual claim;
- capture a stable identifier when possible (DOI, PMID, accession, official URL, version/tag);
- identify organism, condition, dataset, software version, or other scope limitations;
- check whether later evidence materially conflicts with it when relevant.

Never fabricate citations or rely solely on an AI model's remembered bibliography.

## Scientific interpretation

Do not:

- convert association into causation;
- generalize across animal species without evidence;
- convert qualitative findings into invented quantitative constraints;
- apply an experimental relation outside its conditions without qualification;
- treat model predictions or explainability output as biological validation.

When evidence conflicts, report the disagreement and relevant contextual differences rather than silently choosing the convenient result.

## Technical interpretation

Check that documentation matches the software version relevant to the project.

For behavior that affects correctness or compatibility, prefer official documentation or upstream source over tutorials and forum answers.

## Dataset research

When evaluating a dataset, record:

- canonical source;
- identifier/version/retrieval date;
- license/terms;
- organism/cohort/experimental context;
- variables and units relevant to the project;
- known limitations;
- redistribution restrictions;
- whether preprocessing is needed.

Do not assume public availability implies unrestricted licensing.

## Preserve durable evidence

If the reference materially affects implementation, a data contract, graph relation, biochemical constraint, experiment design, or interpretation, write it into durable repository documentation according to `docs/documentation-policy.md`.

A useful evidence entry records:

```text
Claim / question
Source identifier
Evidence type
Scope / organism / conditions
Relevant finding
How NutriGraphDT uses it
Limitations / conflicts
Status: provisional | accepted | superseded | rejected
```

Use the `document-project` skill when creating or updating these records.

## Output

Return a concise research result containing:

- answer to the question;
- strongest supporting sources;
- what each source actually supports;
- limitations/conflicts;
- what can safely be encoded or documented;
- what remains unresolved or requires human/scientific-team decision.
