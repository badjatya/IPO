---
name: review-code
description: Final code review of a task DeepSeek built on its task/NNN-* branch, recorded in docs/tasks/NNN-*/code-review.md. Use when the human asks for a task's code review, or a plan's status is code-review.
argument-hint: <task number, e.g. 001>
---

# Review a task's code

You are the final code reviewer in the DeepSeek → Claude workflow ([ADR-0019](../../../docs/adr/0019-deepseek-builds-claude-reviews.md)). The task number is `$ARGUMENTS`.

1. **Find the task's worktree.**
   - It's `.worktrees/$ARGUMENTS-*/`, on branch `task/<folder name>`. The task folder is `.worktrees/<folder>/docs/tasks/<folder>/`.
   - If the branch exists but the worktree doesn't, create it: `git worktree add .worktrees/<folder> task/<folder>`.
   - Never check out the task branch in the main checkout; it stays on `main`, so several tasks can be in review at once.
   - If the `status:` line in `plan.md` isn't `code-review`, stop and tell the human what it is.
2. **Read, inside the worktree:**
   - `AGENTS.md`
   - `docs/tasks/README.md` § Reviewer guide
   - the approved `plan.md`, including "Changes during build" and "Verification"
   - earlier rounds of `code-review.md` and DeepSeek's responses
3. **Diff and test.**
   - Diff with `git diff main...task/<folder>`.
   - Run the tests yourself, from the worktree (`cd .worktrees/<folder>` first): `python3 -m unittest discover -s tests` for Python, the web app's runner for `web/`, and `python3 -m unittest discover -s .claude/hooks` if guards changed.
   - Paste the real output into the review. Never claim tests pass without running them.
4. **Review.**
   - Check the diff against the approved plan, every project rule in `AGENTS.md`, and the docs and status labels it should have updated.
   - For a deeper bug hunt, run the `/code-review` skill on the branch, then verify each of its findings yourself before recording it.
5. **Write the round.** Append it to `code-review.md`, created from `docs/tasks/templates/code-review.md` if missing.
   - **Findings:** each has a severity (Blocker, Major, Minor or Nit), `file:line`, the concrete failure, and a suggested fix.
   - **A broken project rule is a Blocker.**
   - **Never edit an earlier round** or DeepSeek's responses.
   - **Don't fix the code yourself** unless the human asks; findings go in the review.
6. **Set the status** in `plan.md`: `merge-ready` if there's no open Blocker or Major, otherwise `code-changes`.
7. **Commit** only `code-review.md` and the status line, in the worktree, with `git -C .worktrees/<folder> add …` and `git -C .worktrees/<folder> commit` and a message like `Code review NNN round N: <verdict>`. Don't push or merge.
8. **Report** to the human: the verdict, the Blockers and Majors, and who goes next. On `merge-ready`, also list the roadmap changes to make after the merge (the plan's "Doc updates", plus anything it missed).
