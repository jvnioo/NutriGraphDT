# Source and Reference Policy

NutriGraphDT combines software engineering with scientific modeling. Sources used to justify technical or scientific decisions must therefore be traceable and appropriate to the claim being made.

## General rule

Use the strongest practical source for the decision at hand. Do not cite a secondary explanation as the authority when an accessible primary source exists.

Never fabricate a citation, DOI, PMID, dataset identifier, benchmark result, version, or quotation.

## Technical source hierarchy

Prefer, in order:

1. repository documentation and approved project contracts for project-specific behavior;
2. official language/library/framework documentation;
3. official specifications, standards, release notes, and upstream repositories;
4. peer-reviewed or authoritative technical publications when relevant;
5. high-quality secondary technical sources;
6. community discussions, forums, blogs, and Q&A sites as supporting material only.

Examples of preferred primary technical references include official Python, PyTorch, PyTorch Geometric, FastAPI, and dependency documentation when those technologies are introduced.

Community material can be useful for discovering an issue or workaround, but consequential behavior should be verified against official documentation or source code when practical.

## Scientific source hierarchy

Prefer, in order:

1. original peer-reviewed research directly supporting the claim;
2. authoritative scientific databases and curated resources;
3. systematic reviews or high-quality review articles for broader context;
4. recognized institutional or professional scientific sources;
5. other secondary material only when stronger evidence is unavailable and the limitation is stated.

A review article may provide context, but when a specific numerical value, relation, mechanism, or experimental observation matters to implementation, locate the underlying primary evidence when practical.

## Dataset sources

For external datasets, record at least:

- canonical source or repository;
- dataset name and identifier/version when available;
- retrieval date when versions are not stable;
- license or usage terms;
- checksum when practical;
- relevant preprocessing or filtering;
- whether the data are real, synthetic, simulated, or derived.

Do not assume that publicly downloadable data are automatically licensed for unrestricted redistribution.

## Claim-to-source matching

The source must support the actual claim being made.

Avoid:

- citing a paper that mentions a topic but does not support the stated relation;
- using results from one species, population, condition, or experimental setup as universal without qualification;
- converting association into causation;
- turning a qualitative observation into an invented quantitative constraint;
- using a software tutorial to justify scientific behavior;
- treating a model prediction as biological evidence.

## Conflicting evidence

If high-quality sources disagree:

- record the disagreement;
- identify differences in species, design, conditions, measurement, or methodology where possible;
- do not silently select the result that is most convenient for the implementation;
- mark the project decision as provisional if the evidence does not support a definitive choice.

## Recency and versions

For software, verify the documentation matches the dependency version used by the repository.

For science, newer is not automatically better. Prefer evidence quality and relevance, while checking whether later work supersedes or materially challenges older findings.

## Recording references

When a reference materially affects code, a data contract, a scientific constraint, interpretation, or experiment design, preserve it in the appropriate project documentation rather than only in an AI conversation.

Use stable identifiers when possible:

- DOI;
- PMID/PMCID;
- dataset accession/identifier;
- official documentation URL and version;
- repository release/tag/commit when source behavior matters.

Follow `docs/documentation-policy.md` for where durable evidence should be recorded.

## AI research behavior

When an AI agent performs research:

1. state the question being answered;
2. distinguish repository requirements from external evidence;
3. prefer primary sources;
4. verify that the source actually supports the claim;
5. report uncertainty and conflicting evidence;
6. preserve consequential references in repository documentation;
7. avoid unsupported synthesis presented as fact.

Use the `research-reference` skill for this workflow.
