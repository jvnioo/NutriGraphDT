# Scientific Integrity for AI-Assisted Work

NutriGraphDT is an academic research prototype. Scientific claims, data transformations, model outputs, and biochemical constraints must remain traceable and appropriately qualified.

## Separate evidence from implementation

Always distinguish between:

- a project requirement;
- a scientific observation supported by a source;
- a modeling assumption;
- a software engineering choice;
- a synthetic-data convention;
- a model prediction;
- an experimentally validated biological conclusion.

Do not blur these categories in code, documentation, reports, or user-facing output.

## No invented scientific facts

AI agents and contributors must not invent or infer as established truth:

- metabolic pathways or microorganism interactions;
- nutrient-microbiome relations;
- stoichiometric coefficients;
- mass-balance parameters;
- physiological bounds;
- concentration ranges;
- effect sizes;
- causal relations;
- experimental measurements;
- literature consensus.

When a required value or relation is unavailable, mark the gap explicitly and keep the implementation provisional, blocked, or synthetic according to the approved task.

## Scientific assumptions

Every consequential assumption should be:

1. identifiable;
2. justified by a source or explicitly marked as provisional;
3. scoped to the relevant organism, condition, dataset, or experimental context;
4. documented where it influences model behavior or interpretation;
5. revisable without silently changing historical experiment records.

## Data integrity

External data must preserve provenance through acquisition and preprocessing documentation.

Clearly label:

- real observations;
- derived variables;
- imputed values;
- synthetic examples;
- simulated outputs.

Do not mix synthetic and real observations in evaluation without explicitly documenting the protocol and purpose.

Do not commit restricted or confidential data.

## Experimental integrity

For meaningful computational experiments, preserve enough information to reconstruct what was run:

- research question or purpose;
- dataset and version/provenance;
- preprocessing;
- train/validation/test protocol when applicable;
- model/baseline identity;
- configuration and hyperparameters;
- random seed when practical;
- code version or commit;
- metrics;
- results;
- known limitations and anomalies.

Do not retrospectively alter an experiment record to make results appear cleaner. If an experiment is invalidated, record why and run a new experiment.

## Evaluation discipline

- Avoid data leakage.
- Do not tune on held-out test data.
- Keep metric definitions stable within a comparison or document changes explicitly.
- Compare models under sufficiently comparable conditions.
- Do not select only favorable runs without reporting the selection rule.
- Report failed or inconclusive experiments when they materially affect interpretation.

## Biochemical and physics-informed constraints

A constraint is not scientifically valid merely because it improves optimization or predictive metrics.

For every consequential constraint, preserve:

- the mathematical form;
- scientific rationale;
- supporting source or approved project definition;
- units and variable definitions;
- valid scope/conditions;
- whether it is hard, soft, heuristic, provisional, or validated;
- tests that demonstrate expected behavior.

Constraints should be independently testable from the predictive model when practical.

## Explainability

Explainability output describes how a computational model behaves; it does not automatically reveal a biological mechanism.

When presenting node, edge, attention, attribution, or subgraph importance:

- describe the method used;
- avoid causal language unless supported independently;
- report relevant limitations;
- distinguish explanatory model artifacts from validated biological evidence.

## User-facing interpretation

The experimental simulator must not present its outputs as commercial nutritional advice or as a replacement for in vivo/in vitro validation.

Where relevant, user documentation and interfaces should communicate:

- model uncertainty;
- scientific scope;
- unsupported extrapolation risks;
- provisional assumptions;
- that predictions require independent validation.

## Academic and publication material

Content preserved for the course report or a potential paper must reflect what actually happened in the project.

Do not reconstruct missing methods, results, dates, or decisions from memory or AI inference when evidence is absent. Mark unavailable information explicitly.

Follow `docs/documentation-policy.md` and the `document-project` skill to preserve evidence throughout development.
