# Documentation and Traceability Policy

Documentation in NutriGraphDT is produced progressively during development. It must preserve enough information to understand what was built, why decisions were made, how results were obtained, and what evidence supports scientific or technical claims.

Documentation is not limited to code comments and is not deferred until the end of the project.

## Documentation principle

At the end of every meaningful task, ask:

> Does this change create knowledge that must be preserved as technical documentation, user documentation, an experiment record, a scientific reference, an architectural decision, academic-report evidence, or potential publication material?

If yes, update the appropriate durable project documentation before the task is considered complete.

Do not create documentation only to satisfy a checkbox. Preserve information that would otherwise be difficult, costly, or impossible to reconstruct later.

## Documentation categories

### Technical documentation

Technical documentation should allow another contributor to understand, maintain, and reproduce the software.

Document when relevant:

- architecture and module responsibilities;
- public/internal interfaces that form stable contracts;
- data contracts and schemas;
- heterogeneous graph node/edge definitions;
- configuration conventions;
- dependency decisions;
- installation and execution procedures;
- API contracts;
- training, inference, simulation, and evaluation procedures;
- non-obvious algorithms, invariants, and limitations;
- important architectural decisions and trade-offs.

Code comments should explain reasons, assumptions, invariants, or non-obvious behavior rather than restating obvious code.

### Development manual

`docs/development.md` is the baseline development guide and should evolve as the repository becomes executable.

It should eventually enable a contributor to:

```text
clone -> configure environment -> install dependencies -> prepare data -> run -> test -> reproduce an experiment
```

Update it whenever setup or ordinary contributor workflows materially change.

### User manual

User documentation should be created when the experimental simulator or other user-facing interfaces exist.

It should describe implemented behavior, not planned functionality.

Relevant topics may include:

- purpose and scope;
- requirements and access;
- inputs;
- basal and intervention scenarios;
- simulation execution;
- result visualizations;
- uncertainty;
- explainability;
- common errors;
- limitations and scientific interpretation warnings.

User documentation must not imply that the prototype replaces in vivo/in vitro validation or provides commercial nutritional advice.

### Experiment records

Meaningful experiments must preserve enough information for interpretation and practical reproduction.

A useful experiment record includes:

- experiment identifier;
- date;
- objective or research question;
- dataset/source/version;
- preprocessing;
- model or baseline;
- configuration and hyperparameters;
- random seed when practical;
- evaluation protocol and metrics;
- relevant code commit/version;
- results;
- interpretation;
- anomalies/failures;
- limitations;
- links to related Issues/PRs when useful.

A future convention may use directories such as:

```text
experiments/
└── EXP-001/
    ├── README.md
    ├── config.yaml
    └── metrics.json
```

Do not commit large checkpoints or generated datasets merely to satisfy reproducibility. Follow `.gitignore`, data licensing, and the cost policy.

### Scientific evidence records

When scientific evidence materially affects the graph schema, a biochemical constraint, data transformation, experiment design, or interpretation, preserve the supporting reference and its scope.

A useful evidence record contains:

- claim or relation;
- source identifier (DOI, PMID, accession, official URL, etc.);
- evidence type;
- organism/condition/context;
- how NutriGraphDT uses the evidence;
- limitations or conflicting evidence;
- status such as provisional, accepted, superseded, or rejected.

The project may organize these records under `docs/research/evidence/` as the research base grows.

### Architectural decisions

When a decision has lasting architectural consequences and meaningful alternatives existed, record:

- context;
- alternatives;
- decision;
- rationale;
- consequences.

Architecture Decision Records may be introduced under `docs/adr/` when the project reaches a level of complexity that benefits from them.

### Academic report evidence

During development, preserve factual material that can later support the course report/evaluation, including:

- problem addressed;
- planning and methodology;
- important technical decisions;
- architecture evolution;
- implementation milestones;
- tests and validation;
- risks and blockers;
- deviations from the original plan;
- results;
- limitations;
- lessons learned.

Do not write the final academic report inside every Issue. Preserve concise, traceable evidence that can later be synthesized accurately.

When a task produces particularly relevant material, record it under `docs/academic/report-notes/` once that structure is introduced.

### Potential paper material

Preserve information that may later support a scientific paper when it would be difficult to reconstruct accurately after the fact.

Examples include:

- research questions/hypotheses;
- dataset and cohort definitions;
- preprocessing decisions;
- model and baseline definitions;
- training/evaluation protocols;
- ablation/comparison designs;
- important quantitative results;
- negative or inconclusive results that affect interpretation;
- limitations;
- scientifically relevant observations;
- reproducibility information.

When appropriate, this material may be summarized under `docs/research/paper-notes/`.

These notes are evidence for later writing; they are not automatically publication-ready conclusions.

## Documentation structure

The repository may evolve toward the following structure as content becomes necessary:

```text
docs/
├── documentation-policy.md
├── technical/
│   ├── architecture/
│   ├── data/
│   ├── models/
│   ├── experiments/
│   └── api/
├── user/
├── research/
│   ├── evidence/
│   ├── experiments/
│   ├── decisions/
│   └── paper-notes/
└── academic/
    └── report-notes/
```

Do not create empty directories or artificial placeholder documents solely to match this tree. Introduce them when real content exists.

## Issue documentation-impact check

Every planned task should consider whether it affects:

- technical documentation;
- architecture;
- data/contracts;
- experiments;
- scientific evidence/references;
- development manual;
- user manual;
- academic report evidence;
- potential paper material.

The Issue template contains a checklist for this purpose.

## Pull Request documentation check

Before review, confirm either:

- no durable documentation is affected; or
- all applicable documentation/evidence has been updated.

The PR should not be marked complete merely because implementation works if information necessary for future understanding or reproduction would be lost.

## Traceability

Where practical, durable records should link to the relevant:

- Issue;
- Pull Request;
- commit/version;
- dataset identifier;
- experiment identifier;
- scientific source.

The goal is to make the path from requirement or scientific evidence to implementation and result inspectable later.

## Accuracy

Never reconstruct missing documentation by inventing facts.

If a historical detail, experimental condition, result, source, or decision cannot be verified, state that it is unavailable or uncertain rather than filling the gap with an AI-generated assumption.
