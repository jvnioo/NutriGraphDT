# Instructions for automated agents

NutriGraphDT is an academic research prototype (graph-based nutritional digital twin). Before
changing code, Issues, Pull Requests, or the GitHub Project, read:

1. [`docs/process/project-board-guide.md`](docs/process/project-board-guide.md): the operating
   procedure to take an Issue, validate locally, open a Pull Request, hand it to review, and
   close it.
2. [`docs/process/workflow.md`](docs/process/workflow.md): Scrumban policy, Definition of Ready
   and Done.
3. [`CONTRIBUTING.md`](CONTRIBUTING.md): branch names, commit convention, local checks.
4. The selected Issue in full, including its dependencies and closing note.

## Rules that are easy to get wrong

- Take only `Ready` Issues whose `blocked by` dependencies are closed; assign yourself and move
  the item to `In Progress` before coding.
- Branch from `main` as `<type>/<issue-number>-<short-description>` and open the Pull Request
  against `main`. Never stack a PR on another feature branch: merged branches are not deleted
  automatically, so the work would never reach `main`.
- There is no remote CI. Run `ruff check .`, `ruff format --check .`, `mypy src`, and
  `pytest` on the final state of the branch and paste the results in the PR. An Issue that
  asks for "CI en verde" means these local checks.
- `Closes #<issue-number>` goes in the PR description. The Issue stays in `Review` until an
  approving review by someone other than the author is recorded and the PR is merged.
- Merge only when the user explicitly asks you to merge that PR, then delete the branch
  (`gh pr merge <n> --merge --delete-branch`) and verify the Issue closed.
- Do not commit `data/raw/`, `artifacts/`, credentials, or local AI configuration such as
  `.claude/`. Real data sources are regenerated with their scripts.
- Do not invent scientific values; record open questions in the Issue or PR.

Code lives in `src/nutrigraphdt/`; thin entry points live in `scripts/`. Write documentation in
the language of the surrounding file.
