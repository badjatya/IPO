# ADR-0021: DeepSeek runs through OpenRouter, driven by Claude Code

- **Status:** Accepted
- **Decided:** 2026-10-29 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)
- **Supersedes:** [ADR-0019](0019-deepseek-builds-claude-reviews.md)

## Context

[ADR-0019](0019-deepseek-builds-claude-reviews.md) split the coding work this way: DeepSeek in opencode plans and builds, Claude Code reviews, and the human moves each task between the two tools. In practice opencode was often unavailable. Tasks 001, 002 and 003 were finished by Claude alone, so their reviews were not independent. Every hand-off also needed the human to switch tools.

## Options

| Option | For | Against |
| --- | --- | --- |
| Keep opencode | Already set up; opencode's own permission system | Unavailable often enough that three of three tasks fell back to Claude; the human moves every task by hand |
| Claude does everything | One tool | No second model; an agent tends to approve its own reasoning |
| **DeepSeek through the OpenRouter API, run by a small driver that Claude Code calls** | Same two-model split and review gates; no second tool to open; Claude runs the loop and stops for the human only where a person is needed; every step is logged with its cost | Our own driver to maintain; its file rules don't cover code that the task's tests run (see Consequences) |

## Decision

1. **The roles stay as in ADR-0019.** DeepSeek writes each task's plan and, once approved, builds it. Claude Code reviews the plan and the code. The human decides open questions and merges.
2. **DeepSeek runs through OpenRouter.** The model is `OPENROUTER_MODEL_NAME` in `.env.local`, `deepseek/deepseek-v4-flash-0731` at the time of writing. It runs through `.claude/deepseek/deepseek.py`, a standard-library driver with four steps: `plan`, `revise`, `build` and `respond`. These replace opencode's four commands.
3. **Claude runs the loop** with the `/run-task NNN` skill. It runs a DeepSeek step, reviews the result, and repeats. It stops for the human on any open decision, a setup step, a package to install, a third round without approval, a broken write rule, and at `merge-ready`.
4. **opencode is removed.** `opencode.json` and `.opencode/` are deleted.

## Consequences

**The driver owns the workflow state.**
- It checks the status line before each step and sets the next one.
- It makes the hand-off commit.
- It restores plan.md's frontmatter if DeepSeek changes it.

**Write rules are enforced in two places.**
- **File tools.** They refuse anything outside the task's worktree, `.git` and `.env*`, and the paths in AGENTS.md § Paths you must not edit by hand. They also refuse `AGENTS.md`, `ROADMAP.md`, `.gitignore`, other tasks' files and the review files.
  - The exception: in `respond`, DeepSeek may write the latest round's Responses table.
  - Plan steps can write only `plan.md`.
- **Post-step check.** After every step, the driver checks every changed path and every commit against the same rules. It also checks that the approved plan and Claude's review text are unchanged. A step that breaks a rule is not handed off (exit 3).

**The limit of the sandbox.**
- The `run` tool takes no shell, and only allowlisted commands: read-only git, `python3 -m unittest`, `python3 <script>`, `npm test|run|ls` and `npx --no-install`.
- Those commands still run the task's own code, which can do anything the user can, including reading `.env.local`. So the key is not in its environment, is replaced in every tool result before DeepSeek or the log sees it, and a step whose changed files hold it is not handed off.
- The post-step check, Claude's code review and "only the human pushes" are the real boundary. The docs say so.

**No more "opencode unavailable".**
- The human no longer moves tasks between tools.
- Reviews stay independent: DeepSeek reads only the repo and the review files, never Claude's suggested code.

**Evidence and cost.**
- DeepSeek's commits carry `AI-Agent: DeepSeek <model> (OpenRouter)`, which names the model.
- Every step logs its messages, tool calls and cost to `.deepseek-logs/` (gitignored).
- Each step has a cost cap: $1 to plan or revise, $3 to respond and $5 to build.

**Secrets.**
- `OPENROUTER_API_KEY` stays in the gitignored `.env.local` of the main checkout.
- The driver reads it into memory only, and guards it as above.

## AI involvement

The human chose to replace opencode with OpenRouter, named the model, and asked that Claude run DeepSeek and review its work.

Claude Code:
- tested two-turn tool calling against the model
- wrote the driver, its tests and the `/run-task` skill
- drafted this ADR

An advisor model pointed out that the file rules can't stop code run through `python3`. That led to the post-step check, and to the wording above that doesn't claim more than the sandbox enforces.

## Evidence

- [OpenRouter tool-calling docs](https://openrouter.ai/docs/guides/features/tool-calling) (checked 2026-10-29)
- `.claude/deepseek/deepseek.py`, `.claude/deepseek/test_deepseek.py`, `.claude/skills/run-task/SKILL.md`
- [AI journal 2026-10-29](../plan.md#ai-journal)
