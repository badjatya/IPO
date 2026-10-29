---
description: Start a new task and write its plan for Claude to review
agent: planner
---

New task from the human:

$ARGUMENTS

Follow AGENTS.md § Task workflow, step 1. Run this from the main checkout (the repo root), never from inside `.worktrees/`.

1. **Pick the number.**
   - If the task names a roadmap ID (`Task NNN from docs/tasks/ROADMAP.md`), use that `NNN` and the slug in its entry. Read the entry and the decisions and setup steps it lists.
     - **Stop** only if a task it depends on isn't Done, or it needs gate G1 and G1 isn't ticked. Say what it's waiting on.
     - **Open decisions** (`D..`) don't stop the plan. Put each under "Decisions needed", with options and a recommendation.
     - **Setup steps** (`H..`) that aren't done go under "Risks and rollback" as needed before the build.
   - For a task not in the roadmap, list `docs/tasks/` and take the next three-digit `NNN` not used by a folder or by `ROADMAP.md`. Choose a short slug.
2. **Make the branch and its worktree.** Branch from `main`, without checking anything out in the main checkout:

   ```bash
   git worktree add -b task/NNN-short-slug .worktrees/NNN-short-slug main
   ```

   If the branch or the worktree already exists, stop and say so.
3. **Fill in the plan, inside the worktree.** Copy `docs/tasks/templates/plan.md` to `.worktrees/NNN-short-slug/docs/tasks/NNN-short-slug/plan.md`. Quote the task above under "Task"; for a roadmap task, quote its roadmap entry. Don't edit `ROADMAP.md`.
4. **Hand it over.** Set `status: plan-review`. Commit only that file, in the worktree:

   ```bash
   git -C .worktrees/NNN-short-slug add docs/tasks/NNN-short-slug/plan.md
   git -C .worktrees/NNN-short-slug commit -m "Plan NNN: <title>" -m "AI-Agent: DeepSeek (opencode)"
   ```

5. **Stop.** Print:
   - the task number, the branch and the worktree path
   - a five-line summary of the plan
   - "Ready for Claude's plan review"
   - that the remaining DeepSeek steps for this task run in an opencode session opened in the worktree: `cd .worktrees/NNN-short-slug && opencode`
