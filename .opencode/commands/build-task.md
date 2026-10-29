---
description: Build an approved task plan on its task branch
agent: build
---

Task $ARGUMENTS: build the approved plan.

1. **Check you're in the task's worktree.**
   - `git rev-parse --show-toplevel` must end in `/.worktrees/$ARGUMENTS-<slug>`, and `git branch --show-current` must be `task/$ARGUMENTS-<slug>`.
   - If not, stop and tell the human to run `cd .worktrees/$ARGUMENTS-* && opencode`, then run this command again.
   - Never check out the task branch anywhere else, and never edit files outside this worktree.
2. **Check it's approved.** Continue only if `plan.md` has `status: approved` and the latest round of `plan-review.md` says **Approved**. Otherwise stop and say why.
3. **Build the steps in order,** following AGENTS.md § Project rules and § Building.
   - **Small commits.** Each commit message ends with `AI-Agent: DeepSeek (opencode)`.
   - **Tests.** Each step has the test the plan names. No live sites or AI APIs in tests.
   - **Docs.** Doc and status-label updates go in the same change.
4. **Record deviations.** If something has to differ from the plan, write it in "Changes during build" with the reason. Don't widen the scope.
5. **Verify.** Run the tests and paste the commands and their output into "Verification".
6. **Hand it over.** Set `status: code-review`, commit, and stop. Print a summary and "Ready for Claude's code review".
