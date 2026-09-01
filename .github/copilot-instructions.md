# GitHub Copilot Instructions for NutriGraphDT

The canonical repository-wide AI instructions are in [`../AGENTS.md`](../AGENTS.md). Follow them for every code, review, test, research, or documentation task.

Before making changes:

1. read the current Issue/task and acceptance criteria;
2. read `AGENTS.md`;
3. read `docs/workflow.md` and `CONTRIBUTING.md`;
4. inspect relevant code/tests before proposing new abstractions;
5. consult architecture, cost, documentation, source, and scientific-integrity policies when applicable.

Key rules:

- implement the smallest complete solution for the current task;
- do not silently expand scope or perform unrelated refactors;
- do not invent scientific requirements, constants, relations, experimental results, citations, or provenance;
- prefer primary/official technical and scientific sources;
- preserve consequential decisions, experiments, sources, and report/paper evidence in repository documentation;
- add/update tests for changed behavior and report validation truthfully;
- do not require paid services, paid APIs, paid compute, billing, subscriptions, or temporary credits;
- never commit secrets or restricted/private data;
- human review remains mandatory for AI-assisted changes.

Repository AI skills and detailed workflows are stored under `.agents/skills/`. GitHub Copilot may not automatically load those skills, so use `AGENTS.md` and the files under `docs/ai/` as the authoritative guidance when a skill is not available in the current tool.
