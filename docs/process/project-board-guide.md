# GitHub Project guide for contributors and agents

This guide defines how human contributors and automated agents operate the NutriGraphDT
GitHub Project without duplicating tasks, bypassing dependencies, or losing traceability.
The canonical board is
[NutriGraphDT — Development Board](https://github.com/users/jvnioo/projects/2), owned by
`jvnioo` and identified by project number `2`.

Read [`docs/process/workflow.md`](workflow.md), [`CONTRIBUTING.md`](../../CONTRIBUTING.md), and the
selected Issue before changing repository or Project state. `docs/process/workflow.md` remains the
authority for Scrumban policy; this document supplies the operating procedure.

## Sources of truth

Use this precedence when information differs:

1. the current GitHub Issue for objective, scope, acceptance criteria, and dependencies;
2. the GitHub Project for workflow state and current assignee;
3. repository contracts and policies for technical and scientific constraints;
4. the Pull Request for the proposed implementation and its validation evidence.

Chat history, local planning notes, branch names, and agent memory are not durable project
records. Consequential decisions must be copied to the Issue, Pull Request, or repository
documentation.

An Issue is the canonical work item. Do not create a separate draft Project item when an
Issue exists or can be created. A Pull Request that closes an Issue should be linked with
`Closes #<issue-number>`; do not add the PR as a second work item unless the task has no
Issue and a project maintainer explicitly accepts that exception.

## Required access

The baseline command-line client is the free and open-source GitHub CLI. Confirm access
before attempting an external mutation:

```bash
gh auth status
gh repo view jvnioo/NutriGraphDT
gh project view 2 --owner jvnioo
```

The authenticated account needs access to the private repository plus `repo` and `project`
scopes. If required:

```bash
gh auth login --hostname github.com --git-protocol https --web
gh auth refresh --hostname github.com --scopes repo,project
gh auth setup-git
```

Never place a token in a command committed to the repository, a chat message, an Issue, a
Pull Request, or a configuration file. If authentication is unavailable, stop before making
Project changes and report which access is missing.

## Inspect before acting

Always refresh both Git and Project state. Do not rely on a prior agent's summary.

```bash
git fetch origin
gh issue list --repo jvnioo/NutriGraphDT --state open --limit 100
gh project item-list 2 --owner jvnioo --limit 100 --format json \
  --jq '.items[] | {title, status, assignees, url: .content.url}'
```

Then inspect the selected Issue in full:

```bash
gh issue view <issue-number> --repo jvnioo/NutriGraphDT \
  --json number,title,body,state,assignees,labels,projectItems,blockedBy,blocking,url
```

Before taking it, verify that:

- its Project status is `Ready`;
- it has no assignee, or coordination with the assignee is recorded;
- every blocking dependency is complete;
- its objective and acceptance criteria are actionable;
- the contributor has no other main task in `In Progress`;
- the work does not require unapproved paid infrastructure or missing scientific facts.

If any condition fails, do not silently reinterpret the Issue or start coding.

## Take a Ready task

Once the checks pass:

1. assign the Issue to yourself;
2. move its Project item to `In Progress`;
3. update local `main` from `origin/main` using a fast-forward;
4. create a short-lived branch containing the Issue number.

```bash
gh issue edit <issue-number> --repo jvnioo/NutriGraphDT --add-assignee @me
git switch main
git merge --ff-only origin/main
git switch -c <type>/<issue-number>-<short-description>
```

Use the Project UI to change status when practical. For CLI automation, discover IDs at
runtime; do not copy opaque Project IDs into scripts or documentation as permanent
configuration:

```bash
gh project view 2 --owner jvnioo --format json
gh project field-list 2 --owner jvnioo --format json
gh project item-list 2 --owner jvnioo --limit 100 --format json
```

After identifying the Project, item, `Status` field, and desired option IDs from those
responses, update the item:

```bash
gh project item-edit \
  --id <item-id> \
  --project-id <project-id> \
  --field-id <status-field-id> \
  --single-select-option-id <status-option-id>
```

Immediately query the item again and confirm the requested status. An API command returning
success is not a substitute for verifying final state.

## Interpret board states consistently

| State | Use |
|---|---|
| `Backlog` | Future or insufficiently refined work that is not executable now. |
| `Ready` | Unassigned work with explicit criteria and all critical dependencies available. |
| `In Progress` | Assigned work currently being implemented; normally one main item per contributor. |
| `Review` | A linked Pull Request is open and ready for human review. |
| `Done` | The Pull Request is reviewed and merged, checks pass, documentation is complete, and the Issue is closed. |
| `Blocked` | A concrete named dependency or missing decision prevents progress. |

Do not use `Done` for an unmerged branch or `Review` for work without a reviewable Pull
Request. Do not move a task to `Ready` merely because someone wants to begin it when a
listed dependency remains incomplete.

When marking an item `Blocked`, add an Issue comment or body update that names:

- the blocking Issue, decision, data, or external action;
- what must happen to unblock it;
- who or which team owns the dependency, when known.

After a dependency is completed, re-evaluate every dependent task. Move it to `Ready` only
if no other blocker remains.

## Create or refine a task

Use a repository Issue template; do not create a title-only Project card. A development
task must record objective, context, expected work, acceptance criteria, dependencies,
technical/scientific notes, size, priority, phase, cost check, and Ready checklist.

```bash
gh issue create --repo jvnioo/NutriGraphDT --template task.md
```

After creating the Issue, add its URL to the canonical Project:

```bash
gh project item-add 2 --owner jvnioo --url <issue-url>
```

Record every Issue prerequisite as a native GitHub dependency so the blocked indicator is
visible on the repository Issues page and Project board. Keep the dependency list in the
Issue body as readable context, but do not use body text as a substitute for the native
relationship:

```bash
gh issue edit <issue-number> --repo jvnioo/NutriGraphDT \
  --add-blocked-by <blocking-issue-number>

gh issue view <issue-number> --repo jvnioo/NutriGraphDT \
  --json blockedBy,blocking
```

Repeat `--add-blocked-by` for every direct prerequisite. Do not encode indirect
dependencies unless the activity plan explicitly lists them. If a prerequisite has not yet
been created as an Issue, name that missing dependency in the body and keep the item in
`Blocked` until it can be linked.

Set its initial state deliberately:

- `Ready` only when its Ready checklist is complete;
- `Blocked` when a specific dependency prevents execution;
- otherwise `Backlog`.

Before creating a task, search open and closed Issues for the same objective. Prefer
updating or reopening the correct Issue over creating a duplicate. Do not expand an active
Issue with substantial newly discovered work; create and link a separate Issue.

Labels describe the kind of work but do not replace Project state. Assignee placeholders
such as “Integrante 3” do not identify a GitHub account; leave the Issue unassigned until
the responsible person or account is confirmed.

## Push, Pull Request, and review handoff

Before pushing, confirm that the branch contains only the selected Issue's work and that
no dependency or acceptance criterion changed while the task was in progress. Run every
applicable local check and update durable documentation. Then push the task branch and
create a PR against `main`:

```bash
git push --set-upstream origin <branch-name>
gh pr create --repo jvnioo/NutriGraphDT --base main --head <branch-name> \
  --title "<type>: <concise task result>"
```

Use the repository PR template. Its description must include `Closes #<issue-number>`,
validation results, scientific or data limitations, and any deferred work. `Closes` links
the implementation to the canonical task and closes the Issue only when the PR is merged;
do not close the Issue manually while review is pending.

If work must be shared before it is reviewable, open a draft PR and keep the Project item in
`In Progress`:

```bash
gh pr create --draft --repo jvnioo/NutriGraphDT --base main --head <branch-name>
```

Once the PR is genuinely reviewable:

1. confirm the Issue shows the linked PR;
2. move the Issue item to `Review`;
3. mark a draft PR ready, when applicable, with `gh pr ready <pr-number>`;
4. request a human reviewer in the GitHub UI or with
   `gh pr edit <pr-number> --add-reviewer <github-username>`;
5. confirm the requested reviewer appears on the PR;
6. keep requested changes on the same focused branch;
7. do not merge without human review unless repository governance explicitly permits it.

Agents must report the pushed branch and PR URL after creating them. Creating a PR is not
the same as completing the Issue: the task remains in `Review` until review and merge are
finished.

After merge, verify rather than assume:

- the Issue was closed;
- the Project item is `Done`;
- the merge commit is present on `origin/main`;
- dependent Issues have been reconsidered for `Ready`;
- the feature branch can be removed according to repository practice.

If `Closes #<issue-number>` did not close the Issue after merge, first verify that the PR was
merged into the repository's default branch and that the reference targets the correct
Issue. Close it manually only after those checks, and record the merged PR URL in a final
Issue comment.

## Agent mutation rules

Agents may inspect repository, Issue, PR, and Project state when needed for their assigned
task. They may mutate external state only when the user or active task authorizes that
workflow action.

Agents must not:

- take an assigned Issue without recorded coordination;
- change Project fields, options, views, visibility, or automation rules unless explicitly
  requested;
- create duplicate Issues or PR Project items;
- mark acceptance criteria complete without evidence;
- resolve a scientific uncertainty by inventing a value;
- assign a GitHub user based only on a numbered team-member placeholder;
- expose tokens, credentials, private datasets, or local-only AI configuration;
- merge a PR merely because automated checks pass.

After any external mutation, report the affected URLs and verify the resulting assignee,
state, links, and dependency information. If only part of a multi-step mutation succeeds,
stop, audit the resulting state, and repair or clearly report the partial result before
continuing.
