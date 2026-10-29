---
name: run-task
description: Run a task through the whole loop with DeepSeek on OpenRouter. DeepSeek plans, Claude reviews the plan, DeepSeek revises and builds, Claude reviews the code, until the task is merge-ready or needs the human. Use when the human asks to start, continue or run a task (e.g. "run task 005").
argument-hint: <task number, e.g. 005> [the task in the human's words, if it isn't in the roadmap]
---

# Run a task with DeepSeek

DeepSeek plans and builds through `.claude/deepseek/deepseek.py`, and you review each step ([ADR-0021](../../../docs/adr/0021-deepseek-on-openrouter.md)). The task number is the first word of `$ARGUMENTS`.

## Running a DeepSeek step

- **Command.** From the main checkout: `python3 .claude/deepseek/deepseek.py <plan|revise|build|respond> NNN`.
- **In the background.** Always run it with `run_in_background: true`, because a build outlasts the Bash timeout. Wait for the notification instead of polling, then read the output.
- **Exit codes.**
  - **0:** handed off; the status has moved on.
  - **1:** couldn't start. The message says why, usually a status mismatch.
  - **2:** stopped early (turn or cost limit, API error). Rerun the same step once; it carries on from the commits and uncommitted work already in the worktree. If it stops again, stop and tell the human.
  - **3:** the step changed a path it may not write, rewrote the approved plan or your review text, or wrote the API key into a file; nothing was handed off. Look at the worktree (`git -C .worktrees/NNN-* status`, `git diff`), tell the human what it did, and leave it as it is.
- **Keep the models independent.** DeepSeek works from the files only. Never put your fixes or code into its prompt; the review files are how you talk to it.
- **Options.** Don't pass `--max-cost`, `--max-turns` or `--model` unless the human asks.

## The loop

Read the `status:` line in `.worktrees/NNN-*/docs/tasks/NNN-*/plan.md`, do the step for it, and repeat until a stop below.

| Status | Next step |
| --- | --- |
| No worktree yet | `plan NNN` for a roadmap task. For any other task: `plan NNN --slug NNN-short-slug --task "<the human's words>"`, with the next unused number ([docs/tasks/README.md](../../../docs/tasks/README.md)) |
| `planning` | `plan NNN` again: an interrupted plan step |
| `plan-review` | The `/review-plan NNN` skill's steps |
| `plan-changes` | `revise NNN` |
| `approved` | `build NNN` |
| `code-review` | The `/review-code NNN` skill's steps |
| `code-changes` | `respond NNN` |
| `merge-ready` | Stop |

## Stops: hand back to the human

- **Decisions needed.** If the plan lists a decision the human hasn't made, don't approve it.
  - Ask the human with AskUserQuestion, one question per decision, putting the plan's recommended option first.
  - Record each answer in your plan-review round under "Decisions (human)", request the change so DeepSeek writes it into the plan, and carry on.
  - Never pick an option yourself.
- **Setup steps.** If the build needs a setup step (`H..`) that isn't done, stop before `build` and say which one.
- **Packages.** If DeepSeek's summary says a package must be installed, stop and give the human the command. Don't install it.
- **Three rounds.** After a third plan-review or code-review round without approval, stop and summarise what is still open.
- **Exit 3,** or exit 2 twice in a row.
- **`merge-ready`.** The human merges and pushes. After the merge, update the roadmap on `main` as `CLAUDE.md` says.

## Report

At each stop, tell the human:

- the task and its status
- the rounds so far, with the main findings
- DeepSeek's cost, summed from each step's output
- what the human needs to do next
