---
description: Revise a task plan after Claude's plan review
agent: planner
---

Task $ARGUMENTS: revise the plan after review.

1. **Check the status.** Check out `task/$ARGUMENTS-*` and read `docs/tasks/$ARGUMENTS-*/plan-review.md`, latest round only. If `plan.md`'s status isn't `plan-changes`, stop and say what it is.
2. **Answer every item.** Address each numbered item in "Changes requested" in `plan.md`. If you disagree with one, keep the plan as it is for that item and explain why in the Revisions table. The human decides.
3. **Record the round.** Add one row per review round to "Revisions": what changed, and which item it answers.
4. **Hand it back.** Set `status: plan-review`. Commit only `plan.md`, with the message `Plan NNN revision <round>` and the trailer `AI-Agent: DeepSeek (opencode)`. Stop.
