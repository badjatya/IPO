---
description: Build an approved task plan on its task branch
agent: build
---

Task $ARGUMENTS: build the approved plan.

1. **Check it's approved.** Check out `task/$ARGUMENTS-*`. Continue only if `plan.md` has `status: approved` and the latest round of `plan-review.md` says **Approved**. Otherwise stop and say why.
2. **Build the steps in order,** following AGENTS.md § Project rules and § Building.
   - **Small commits.** Each commit message ends with `AI-Agent: DeepSeek (opencode)`.
   - **Tests.** Each step has the test the plan names. No live sites or AI APIs in tests.
   - **Docs.** Doc and status-label updates go in the same change.
3. **Record deviations.** If something has to differ from the plan, write it in "Changes during build" with the reason. Don't widen the scope.
4. **Verify.** Run the tests and paste the commands and their output into "Verification".
5. **Hand it over.** Set `status: code-review`, commit, and stop. Print a summary and "Ready for Claude's code review".
