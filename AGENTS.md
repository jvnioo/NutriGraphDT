# NutriGraphDT Agent Instructions

These instructions apply to AI-assisted work across the repository. Human contributors remain responsible for reviewing, validating, and approving all generated changes.

## 1. Read before changing anything

Before implementing or reviewing a task, read the relevant repository guidance in this order:

1. the current GitHub Issue or explicit task request;
2. `docs/workflow.md`;
3. `CONTRIBUTING.md`;
4. `docs/architecture.md` when architecture or module boundaries are involved;
5. `docs/development.md` when setup, dependencies, tests, or tooling are involved;
6. `docs/cost-policy.md` for any dependency, service, compute, storage, CI, API, or infrastructure decision;
7. `docs/documentation-policy.md` when the work produces knowledge, evidence, experiments, user-facing behavior, or material useful for academic reporting;
8. the relevant files under `docs/ai/`.

Inspect the existing code and tests before proposing a new abstraction or architecture.

## 2. Respect the Scrumban workflow

Normal development starts from an Issue in **Ready**.

Before coding:

- verify that the task objective and acceptance criteria are clear;
- verify that critical dependencies are available;
- do not silently expand the Issue scope;
- do not take over an Issue already assigned to another contributor;
- use a short-lived branch from current `main`;
- never treat direct development on `main` as the normal workflow.

If meaningful additional work is discovered, propose a separate Issue instead of hiding the extra scope inside the current change.

AI assistance does not bypass review. The normal path remains:

```text
Issue -> branch -> implementation -> tests -> Pull Request -> review -> merge -> Done
```

## 3. Implement the smallest complete solution

Prefer the smallest change that fully satisfies the acceptance criteria.

- Reuse existing abstractions when they are appropriate.
- Do not perform unrelated refactors.
- Do not create speculative infrastructure for hypothetical future requirements.
- Do not introduce placeholder modules merely to make the repository look complete.
- Do not hard-code local paths, dataset-specific assumptions, secrets, credentials, or experiment parameters inside reusable code.
- Keep I/O, domain logic, graph construction, model logic, constraints, simulation, explainability, and API boundaries separated according to `docs/architecture.md`.

When the correct behavior cannot be determined from the Issue, repository documentation, code, or approved scientific inputs, state the uncertainty instead of inventing a requirement.

## 4. Coding standards

Follow `docs/ai/coding-standards.md`.

At minimum:

- target Python 3.11+;
- use type hints for public and non-trivial interfaces;
- prefer clear, cohesive functions and modules;
- avoid unnecessary classes and abstractions;
- handle expected failures explicitly;
- keep research configuration explicit and versionable;
- make stochastic experiments reproducible where practical;
- add or update tests for changed behavior.

Do not add a dependency merely for convenience. New dependencies require a clear technical purpose, compatible licensing, and a sustainable free/open-source path.

## 5. Validation is mandatory

Run all applicable local checks before claiming a task is complete:

```bash
ruff check .
ruff format --check .
mypy src
pytest
```

Use `pre-commit run --all-files` when appropriate.

If a check cannot be executed, say exactly which check was not run and why. Never claim that tests passed when they were not executed.

Use the `testing` skill for substantial testing work.

## 6. Scientific and research integrity

Follow `docs/ai/source-policy.md` and `docs/ai/scientific-integrity.md`.

Never invent:

- biochemical constants;
- metabolic relations;
- physiological limits;
- dataset provenance;
- experimental results;
- citations;
- scientific consensus.

Separate clearly:

- established project requirements;
- sourced scientific evidence;
- implementation choices;
- provisional assumptions;
- synthetic or simulated data;
- model predictions;
- validated biological conclusions.

When scientific evidence is required, prefer original peer-reviewed research, authoritative databases, and official technical documentation. Record source, version/date, and limitations when the information influences implementation or interpretation.

A computationally successful result is not automatically a scientifically valid conclusion.

## 7. Source quality

For technical questions, prefer primary sources such as official language, library, framework, and dataset documentation.

For scientific questions, prefer original peer-reviewed papers, authoritative scientific databases, and recognized institutional sources.

Secondary sources, tutorials, forums, and community discussions may help discover or understand material but should not be the sole authority for consequential scientific or architectural decisions when a primary source exists.

Use the `research-reference` skill when external evidence or technical references materially affect the change.

## 8. Documentation and traceability

Documentation is part of development, not an end-of-project cleanup activity.

At the end of every meaningful task, ask:

> Does this change create knowledge that must be preserved as technical documentation, a user manual update, an experiment record, a scientific reference, an architectural decision, academic-report evidence, or potential paper material?

If yes, update the appropriate documentation according to `docs/documentation-policy.md`.

Document what is useful and durable. Do not add comments or documents that merely restate obvious code.

Particularly important material includes:

- data contracts and graph schemas;
- architecture and interface decisions;
- installation and reproducibility procedures;
- experiment configuration, metrics, seeds, datasets, commit/version, results, and limitations;
- scientific assumptions and supporting sources;
- user-visible simulator behavior and limitations;
- evidence useful for the course report/evaluation;
- methods, results, comparisons, limitations, or observations potentially useful for a future paper.

Use the `document-project` skill when determining or producing this documentation.

## 9. Cost constraint

NutriGraphDT has a zero-cost baseline.

Do not make ordinary development, testing, reproduction, experimentation, or project operation depend on:

- paid cloud compute or rented GPUs;
- paid APIs or consumption-based credits;
- managed paid databases or storage;
- paid CI runners;
- commercial hosted experiment tracking;
- a subscription, payment method, temporary trial, or free credit that may later incur charges.

Prefer local execution and free/open-source tooling. Optional external services must have a complete local, no-billing alternative and must not become required infrastructure.

## 10. Security and repository hygiene

Never commit:

- passwords, API keys, tokens, credentials, or private keys;
- restricted/private/confidential datasets;
- `.env` files containing secrets;
- large generated artifacts, checkpoints, or raw datasets unless explicitly approved and appropriate for Git;
- fabricated provenance or licenses.

Follow `.gitignore` and repository data-provenance rules.

## 11. Review rules

When reviewing code, prioritize findings that can affect correctness, reproducibility, scientific validity, security, maintainability, architecture, or acceptance criteria.

Do not flood reviews with formatting issues already handled by Ruff unless the tooling failed or the issue is semantically important.

Review against the Issue, not against imagined requirements. Flag scope expansion, unsupported scientific assumptions, missing tests, missing provenance, misleading interpretation, and required paid dependencies.

Use the `review-code` skill for structured reviews.

## 12. Available repository skills

Repository skills live under `.agents/skills/`:

- `implement-issue` — implement a Scrumban Issue with minimal scope and full validation;
- `review-code` — review a change or Pull Request against project standards;
- `research-reference` — obtain and record high-quality technical/scientific references;
- `testing` — design and execute appropriate tests;
- `document-project` — preserve technical, user, experimental, academic, and publication-relevant knowledge.

Use the relevant skill when the task matches its purpose. Multiple skills may be combined when necessary.

## 13. Human responsibility

AI output is a draft contribution until a human contributor has inspected it.

The contributor opening a Pull Request is responsible for understanding the change, confirming that it satisfies the task, and accurately reporting what was and was not validated.
