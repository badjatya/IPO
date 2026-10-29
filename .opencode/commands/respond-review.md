---
description: Fix and respond to Claude's code review findings
agent: build
---

Task $ARGUMENTS: respond to the code review.

1. **Check you're in the task's worktree.**
   - `git rev-parse --show-toplevel` must end in `/.worktrees/$ARGUMENTS-<slug>`, and `git branch --show-current` must be `task/$ARGUMENTS-<slug>`.
   - If not, stop and tell the human to run `cd .worktrees/$ARGUMENTS-* && opencode`, then run this command again.
   - Never check out the task branch anywhere else, and never edit files outside this worktree.
2. **Check the status.** Read the latest round of `docs/tasks/$ARGUMENTS-*/code-review.md`. Continue only if `plan.md` has `status: code-changes`.
3. **Answer every finding.**
   - **Blockers and Majors:** fix every one.
   - **Minors:** fix them, or explain why they can wait.
   - **Nits:** optional.
   - **Disagreeing:** if you think a finding is wrong, don't change the code for it. Explain why.
4. **Respond in the table.** Fill one row per finding in "Responses (DeepSeek)": "Fixed" with the commit, or "Disagree: <reason>". Never edit Claude's text.
5. **Verify.** Rerun the tests and update "Verification" with the real output.
6. **Hand it back.** Set `status: code-review`. Commit with the trailer `AI-Agent: DeepSeek (opencode)`. Stop.
