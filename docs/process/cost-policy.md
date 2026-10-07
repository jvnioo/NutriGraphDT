# Zero-Cost Infrastructure Policy

NutriGraphDT is an academic project without a budget for software infrastructure. The project therefore follows a **zero-cost baseline**.

## Mandatory rule

A contributor must be able to develop, test, and reproduce the baseline project without purchasing a subscription, adding a payment method, renting cloud infrastructure, or consuming billable API credits.

## Preferred solutions

Prefer, in order:

1. free and open-source software running locally;
2. tools already available through the team's academic/personal hardware;
3. free services that do not require billing information, only when they are optional and replaceable;
4. documented local alternatives for every external service.

## Not allowed as required infrastructure

The baseline project must not require:

- paid cloud virtual machines or GPU instances;
- paid managed databases;
- paid object storage;
- proprietary hosted experiment tracking that requires a paid tier;
- paid monitoring/observability platforms;
- consumption-based AI/API services;
- paid CI runners;
- services requiring a credit card or billing account to reproduce the project.

## GitHub

The repository may use capabilities available to the project at no additional cost. Workflows must be designed conservatively and should not assume access to paid runners or additional purchased quotas.

Local execution remains the authoritative fallback for linting, tests, experiments, and validation.

## Machine learning experiments

Experiments should run locally whenever practical. If training becomes computationally expensive, the team must first evaluate model/data reduction, CPU execution, existing local GPUs, checkpointing, and reproducible reduced experiments before proposing external compute.

Any optional external free compute used for exploration must not become necessary for reproducing the core repository.

## Dependencies and licensing

Dependencies should have a free/open-source usage path compatible with academic development. Dataset licenses and third-party resource terms must be checked independently; "free to access" does not automatically mean "free to redistribute".

## Exceptions

There is no automatic exception for a service merely because it offers a temporary trial or free credits. A future paid service may only be discussed as an optional alternative and must not be configured as a project requirement unless the project's resource policy formally changes.
