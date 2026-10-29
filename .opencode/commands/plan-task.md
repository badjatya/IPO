---
description: Start a new task and write its plan for Claude to review
agent: planner
---

New task from the human:

$ARGUMENTS

Follow AGENTS.md § Task workflow, step 1:

1. **Pick the number.** List `docs/tasks/` and take the next free three-digit `NNN`. Choose a short slug.
2. **Make the branch.** From an up-to-date `main`, create `task/NNN-short-slug`.
3. **Fill in the plan.** Copy `docs/tasks/templates/plan.md` to `docs/tasks/NNN-short-slug/plan.md`. Quote the task above under "Task".
4. **Hand it over.** Set `status: plan-review`. Commit only that file, with the message `Plan NNN: <title>` and the trailer `AI-Agent: DeepSeek (opencode)`.
5. **Stop.** Print the task number, a five-line summary of the plan, and "Ready for Claude's plan review".
