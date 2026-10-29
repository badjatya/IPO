---
description: Fix and respond to Claude's code review findings
agent: build
---

Task $ARGUMENTS: respond to the code review.

1. **Check the status.** Check out `task/$ARGUMENTS-*` and read the latest round of `docs/tasks/$ARGUMENTS-*/code-review.md`. Continue only if `plan.md` has `status: code-changes`.
2. **Answer every finding.**
   - **Blockers and Majors:** fix every one.
   - **Minors:** fix them, or explain why they can wait.
   - **Nits:** optional.
   - **Disagreeing:** if you think a finding is wrong, don't change the code for it. Explain why.
3. **Respond in the table.** Fill one row per finding in "Responses (DeepSeek)": "Fixed" with the commit, or "Disagree: <reason>". Never edit Claude's text.
4. **Verify.** Rerun the tests and update "Verification" with the real output.
5. **Hand it back.** Set `status: code-review`. Commit with the trailer `AI-Agent: DeepSeek (opencode)`. Stop.
