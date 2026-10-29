# Tasks

How coding work moves between the human, DeepSeek in opencode, and Claude Code. Each task gets a folder here, so the plan, both reviews and the responses stay together as a record of the AI-assisted process ([ADR-0019](../adr/0019-deepseek-builds-claude-reviews.md)).

Every task, its dependencies and its status are in [ROADMAP.md](ROADMAP.md). Start a roadmap task with `/plan-task Task NNN from docs/tasks/ROADMAP.md`.

## Folder layout

```text
docs/tasks/
  ROADMAP.md            every task in build order: dependencies, decisions, status
  templates/            plan.md, plan-review.md, code-review.md
  NNN-short-slug/
    plan.md             DeepSeek: the plan, revisions, changes during build, verification
    plan-review.md      Claude: one section per review round
    code-review.md      Claude: findings and verdict per round; DeepSeek's responses
```

Each task's branch is `task/NNN-short-slug`, checked out in its own git worktree at `.worktrees/NNN-short-slug/` (gitignored). The task folder above lives in that worktree until the task is merged.

## Worktrees: several tasks at once

The main checkout stays on `main`. Every task gets its own worktree, so DeepSeek can build one task while Claude reviews another and a third waits for a decision. Nobody switches branches.

```text
IPO/                              main checkout, always on main
  .worktrees/
    001-agent-tests/              task/001-agent-tests: opencode session A
    003-nse-stock-spike/          task/003-nse-stock-spike: opencode session B
```

| When | Who | Where | Command |
| --- | --- | --- | --- |
| Start a task | Human → DeepSeek | Main checkout | opencode: `/plan-task Task NNN from docs/tasks/ROADMAP.md` (creates the branch and the worktree) |
| Every later DeepSeek step | Human → DeepSeek | The task's worktree | `cd .worktrees/NNN-slug && opencode`, then the step's command |
| Reviews | Human → Claude | Main checkout | Claude Code: `/review-plan NNN` or `/review-code NNN`. Claude reads, tests and commits inside `.worktrees/NNN-slug/` |
| Merge | Human | Main checkout | `git merge task/NNN-slug` on `main` |
| Clean up | Human | Main checkout | `git worktree remove .worktrees/NNN-slug && git branch -d task/NNN-slug` |
| Worktree lost but branch kept | Human or Claude | Main checkout | `git worktree add .worktrees/NNN-slug task/NNN-slug` |

- **Dependencies still apply.** A task starts from `main`, so it only sees work that has been merged. Start a task only when the roadmap says it's Ready.
- **Parallel tasks can touch the same file,** usually a doc. Whoever merges second resolves the conflict. If it's big, the human asks DeepSeek to merge `main` into the task branch in its worktree.
- **One session per worktree.** Don't point two opencode sessions at the same worktree.

## Status

The `status:` line at the top of `plan.md` says whose turn it is. Each agent sets it at the end of its step.

| Status | Whose turn | Next |
| --- | --- | --- |
| `planning` | DeepSeek | Write the plan → `plan-review` |
| `plan-review` | Claude | Review → `approved` or `plan-changes` |
| `plan-changes` | DeepSeek | Revise → `plan-review` |
| `approved` | DeepSeek | Build → `code-review` |
| `code-review` | Claude | Review → `merge-ready` or `code-changes` |
| `code-changes` | DeepSeek | Fix and respond → `code-review` |
| `merge-ready` | Human | Merge → `done` |
| `done` | — | — |

The human hands each task to the right tool when the status changes:

| Step | Command | Run from |
| --- | --- | --- |
| Start a task | opencode: `/plan-task <what to do>` | Main checkout |
| Review the plan | Claude Code: `/review-plan NNN` | Main checkout |
| Revise the plan | opencode: `/revise-plan NNN` | `.worktrees/NNN-slug/` |
| Build | opencode: `/build-task NNN` | `.worktrees/NNN-slug/` |
| Review the code | Claude Code: `/review-code NNN` | Main checkout |
| Fix and respond | opencode: `/respond-review NNN` | `.worktrees/NNN-slug/` |

## Reviewer guide (Claude Code)

### Plan review

Read the task folder, [AGENTS.md](../../AGENTS.md), and the docs and ADRs the plan touches. Then check:

| Check | Question |
| --- | --- |
| Goal | Does the plan solve the task as the human stated it, no more and no less? |
| Fit | Does it match [arch.md](../arch.md), [db.md](../db.md) and [ai.md](../ai.md)? Does any change to them appear in the plan's doc updates? |
| Rules | Does it keep every rule in AGENTS.md (numbers from code, standard library in `ipo_agent/`, the right AI for the domain, no user identity in prompts, quotas from `settings`, research not advice)? |
| Decisions | Does it pick anything that is Open or Proposed? That must go under "Decisions needed" instead |
| Steps | Are the steps small, ordered, and each one testable? |
| Tests | Does every behaviour have a test, using saved fixtures with no live calls? |
| Risks | Are failure modes, limits (free tiers, NSE blocking) and rollback covered? |

**Verdicts:**
- **Approved:** build as written. Optional notes may follow.
- **Changes requested:** numbered items, each saying what to change and why.

### Code review

1. Diff the task branch against `main` with `git diff main...task/NNN-short-slug`, and read the plan's "Changes during build".
2. Run the tests and paste the result into the review.
3. Check the code against the approved plan, AGENTS.md, and the docs it should have updated. For a deeper pass, Claude's `/code-review` skill can run on the branch.
4. Write each finding with a severity, `file:line`, the concrete failure, and a suggested fix.

| Severity | Meaning |
| --- | --- |
| **Blocker** | Wrong result, data loss, security or privacy issue, or a broken project rule. Must be fixed |
| **Major** | Bug in a less common path, missing test, or doc out of step. Must be fixed |
| **Minor** | Clearer code or a small gap; fix now or record as follow-up |
| **Nit** | Style; optional |

**Verdicts:**
- **Approved:** sets `merge-ready`. Only possible with no open Blocker or Major.
- **Changes requested:** sets `code-changes`.

## Rules of the loop

- **One task, one folder, one branch, one worktree.** The main checkout stays on `main`.
- **Commit only your own step's files**, on the task branch. Nobody but the human pushes or merges.
- **Reviews are never rewritten.** A new round is a new section, so the record shows how the plan and code changed.
- **Disagreements are written down.** If DeepSeek disagrees with a finding, it says why in "Responses". The human settles it.
- **Journal entries.** At the end of a task, the human or Claude adds a short entry to the [AI journal](../plan.md#ai-journal): rounds taken, notable findings, what was learned.
