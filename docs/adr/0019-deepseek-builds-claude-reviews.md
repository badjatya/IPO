# ADR-0019: DeepSeek plans and builds; Claude reviews the plan and the code

- **Status:** Superseded by [ADR-0021](0021-deepseek-on-openrouter.md) (DeepSeek now runs through OpenRouter; the roles are unchanged)
- **Decided:** 2026-10-29 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

Until now, Claude Code wrote the code and the docs, and the human reviewed. For the hackathon build, the human wants the work split between two agents with a human in charge, and wants each step recorded.

## Options

| Option | For | Against |
| --- | --- | --- |
| One agent plans, builds and reviews its own work | Simple | No independent check; an agent tends to approve its own reasoning |
| **DeepSeek (opencode) plans and builds; Claude Code reviews the plan and the code; the human decides and merges** | Two independent models; a review before any code is written and another before merge; every step leaves a file | More hand-offs; the human moves tasks between tools |

## Decision

1. **DeepSeek in opencode** writes each task's plan and, once the plan is approved, builds it.
2. **Claude Code** reviews the plan and then the finished code.
3. **The human** assigns tasks, decides open questions and merges.
4. **Shared rules and the record.** The rules both agents follow are in [AGENTS.md](../../AGENTS.md). Each task keeps its plan, reviews and responses in `docs/tasks/NNN-slug/`, with a status line that says whose turn it is ([docs/tasks/README.md](../tasks/README.md)).

## Consequences

**Instructions are split by tool.**
- `AGENTS.md` holds the shared project rules. opencode reads it and ignores `CLAUDE.md`, since `AGENTS.md` exists.
- `CLAUDE.md` stays short, because the IPO routine loads it on every run. It points Claude to `AGENTS.md` and the reviewer guide only in development sessions.

**Each step leaves evidence.**
- DeepSeek's commits carry the trailer `AI-Agent: DeepSeek (opencode)`, and Claude's carry its co-author trailer.
- The plan, both reviews and the responses stay in the repo. This is the evidence for the hackathon form's sections 4–6: the agents, the human review, and the bugs found in review.

**The rules are written as checks.** Project rules become review checks: numbers from code, the right AI for the domain, no user identity in prompts, quotas from settings. A broken rule is a Blocker in code review.

**More hand-offs.** The human moves each task between tools when its status changes.

## AI involvement

The human chose the split and the roles. Claude Code drafted `AGENTS.md`, the task workflow, the templates and this ADR, and checked opencode's documented rule-file order: `AGENTS.md` first, `CLAUDE.md` only as a fallback.

## Evidence

- [opencode rules docs](https://opencode.ai/docs/rules) (checked 2026-10-29)
- [AGENTS.md](../../AGENTS.md), [docs/tasks/](../tasks/README.md), [CLAUDE.md](../../CLAUDE.md)
- [AI journal 2026-10-29](../plan.md#ai-journal)
