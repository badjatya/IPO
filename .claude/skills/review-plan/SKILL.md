---
name: review-plan
description: Review a task plan written by DeepSeek in docs/tasks/NNN-*/plan.md and record the verdict in plan-review.md. Use when the human asks to review a task's plan, or a plan's status is plan-review.
argument-hint: <task number, e.g. 001>
---

# Review a task plan

You are the plan reviewer in the DeepSeek → Claude workflow ([ADR-0021](../../../docs/adr/0021-deepseek-on-openrouter.md)). The task number is `$ARGUMENTS`.

1. **Find the task's worktree.**
   - It's `.worktrees/$ARGUMENTS-*/`, on branch `task/<folder name>`. The task folder is `.worktrees/<folder>/docs/tasks/<folder>/`.
   - If the branch exists but the worktree doesn't, create it: `git worktree add .worktrees/<folder> task/<folder>`.
   - Never check out the task branch in the main checkout; it stays on `main`, so several tasks can be in review at once.
   - If the `status:` line in `plan.md` isn't `plan-review`, stop and tell the human what it is.
2. **Read, inside the worktree:**
   - `AGENTS.md` (project rules)
   - `docs/tasks/README.md` § Reviewer guide
   - the task's `plan.md` and any earlier rounds in `plan-review.md`
   - every doc and ADR the plan touches, opened rather than recalled
3. **Check each row of the plan-review table** in the reviewer guide: goal, fit, rules, decisions, steps, tests, risks. For each problem, note the rule, doc or ADR it breaks.
4. **Write the round.** Append it to `plan-review.md`, created from `docs/tasks/templates/plan-review.md` if missing, and number it after the last round. Never edit an earlier round.
   - **Changes requested:** numbered, specific items, each saying what to change and why.
   - **Approved:** only if nothing in "Changes requested" remains.
   - **Open choices:** if the plan needs a human decision (an Open or Proposed item), list it for the human; don't decide it. Under `/run-task`, ask the human first and record the answers under "Decisions (human)".
5. **Set the status** in `plan.md`: `approved` or `plan-changes`.
6. **Commit** only `plan-review.md` and the status line, in the worktree, with `git -C .worktrees/<folder> add …` and `git -C .worktrees/<folder> commit` and a message like `Plan review NNN round N: <verdict>`. Don't push.
7. **Report** to the human in a few lines: the verdict, the main items, and who goes next.
