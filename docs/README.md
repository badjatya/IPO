# Documentation

Start with [project.md](project.md) for what the product is, then [arch.md](arch.md) for how it fits together.

| Doc | What it covers |
| --- | --- |
| [project.md](project.md) | The problem, the solution, who it's for, what is built and what is planned |
| [arch.md](arch.md) | System architecture: context, containers, components, runtime flows, deployment, security, failure handling, cost |
| [tech.md](tech.md) | The tech stack layer by layer, tooling, configuration and local setup |
| [db.md](db.md) | Database: entity diagram, every table and column, keys and indexes, how repo files map to tables, sizing |
| [design.md](design.md) | UI design: component kit, theme, status colours, number formats, layout and page rules for the web app |
| [ai.md](ai.md) | How AI works inside the product and how AI is used to build it: tasks, models, context, guardrails, evals, human review |
| [data-sources.md](data-sources.md) | Every external source: what we read, how often, what breaks, and the fallback |
| [adr/](adr/README.md) | Architecture decision records: one file per decision, with the options weighed and the evidence |
| [plan.md](plan.md) | Scope, week-by-week plan, open decisions and the AI journal |
| [tasks/](tasks/README.md) | How DeepSeek and Claude work on each task: workflow, statuses, reviewer guide, templates, and one folder per task |
| [tasks/ROADMAP.md](tasks/ROADMAP.md) | Every task from today to a finished system: build order, dependencies, decisions and setup needed, status |
| [hackathon.md](hackathon.md) | Hackathon brief and where each submission answer comes from |

Repo-level files: [README.md](../README.md) (how a run works), [ROUTINE.md](../ROUTINE.md) (the routine's instructions to Claude), [CLAUDE.md](../CLAUDE.md) (the project map Claude loads), [AGENTS.md](../AGENTS.md) (rules for every coding agent), [SETUP.md](../SETUP.md) (setting up the routine).

## Status labels

Every component, table and choice in these docs carries one of these labels, so a reader can tell what exists today from what is still a plan.

| Label | Meaning |
| --- | --- |
| **Running** | Built and in use; the code or data is in this repo |
| **Decided** | Agreed by a human (in an ADR or the [plan's scope](plan.md#scope)), not built yet |
| **Proposed** | Drafted or recommended by Claude, waiting for a human decision |
| **Open** | Not decided yet; no recommendation so far |

## How these docs are kept

- **Claude drafts and a human decides.** Claude Code drafts each doc and proposes options with trade-offs. A human picks among them, and the choice is recorded in an ADR. Where a human overrode a proposal, the ADR and the [AI journal](plan.md#ai-journal) say so.
- **Docs change in the same commit as the code.** A change to a table, a flow or a choice updates the matching doc.
- **No claim without evidence.** Every "Running" item names a file or commit. Every "Decided" item traces to an ADR or the plan's scope.
