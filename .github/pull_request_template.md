## Related task

Closes #

## Summary

Describe what changed and why this change is needed.

## Type of change

- [ ] Research / exploration
- [ ] Feature
- [ ] Fix
- [ ] Refactor
- [ ] Test
- [ ] Documentation
- [ ] Tooling / maintenance

## Acceptance criteria

Confirm that the linked Issue acceptance criteria are satisfied, or explain any exception.

- [ ] All applicable acceptance criteria are satisfied.

## Validation

There is no remote CI: run these locally on the final state of the branch and paste the
results (for example `pytest: 1396 passed`). Mention any check that already failed on `main`.

- [ ] `ruff check .`
- [ ] `ruff format --check .`
- [ ] `mypy src`
- [ ] `pytest` (with `NUTRIGRAPHDT_REQUIRE_GRAPH=1` if the change touches graphs or tensors)
- [ ] Not applicable (explain below)

```text
<paste the results here>
```

## Scientific / data considerations

- [ ] No new scientific assumptions or external data
- [ ] Assumptions and limitations are documented
- [ ] External data source and licensing/provenance are documented
- [ ] Synthetic/simulated data are clearly identified
- [ ] Not applicable

## Cost / infrastructure check

- [ ] This change introduces no required paid service, paid API, paid compute, subscription, payment method, or billing dependency.

## Review readiness

- [ ] The base branch is `main` and the branch is up to date with it.
- [ ] The change is focused on one coherent task.
- [ ] Required documentation has been updated.
- [ ] No secrets, credentials, private data, or temporary artefacts are included.
- [ ] The linked Issue should be in **Review** while this PR is open.
- [ ] A reviewer other than the author has been requested; merge only after their approving review.

## Notes for reviewers

Add context, open questions, limitations, or follow-up work.
