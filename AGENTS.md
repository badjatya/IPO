# Agent rules

Rules for any AI coding agent working in this repo. The main reader is **DeepSeek**, which plans and builds tasks through the OpenRouter API. Claude Code runs each DeepSeek step, gives it this file as its rules, and reviews against the same rules ([ADR-0021](docs/adr/0021-deepseek-on-openrouter.md)). Claude's own file is `CLAUDE.md`.

## The project in brief

A research app for Indian retail investors ([docs/project.md](docs/project.md)). It has three parts:

- **IPO research** (running): a scheduled Claude Code routine runs the Python agent in `ipo_agent/` and follows `ROUTINE.md`. Claude writes the analyses and verdicts and emails the admin a brief twice each weekday.
- **Stock research** (to build): a Gemini stock worker on GitHub Actions. It writes stock analyses on request, with a live progress screen, and summaries of watched stocks' filings.
- **Web app** (to build): Next.js on PostgreSQL (Neon). It has accounts, a watchlist, IPO and stock pages, the track record, Ask, and admin settings.

Read these before planning, as far as your task touches them:

| Doc | Read it when the task touches |
| --- | --- |
| [docs/arch.md](docs/arch.md) | Any component, flow or boundary |
| [docs/db.md](docs/db.md) | Tables, queries, imports, settings, quotas |
| [docs/ai.md](docs/ai.md) | Any AI call, prompt, guardrail or eval |
| [docs/tech.md](docs/tech.md) | Frameworks, libraries, config, environment variables |
| [docs/data-sources.md](docs/data-sources.md) | Fetching from NSE, SEBI or Investorgain |
| [docs/adr/](docs/adr/README.md) | Anything a decision already covers. Accepted ADRs are binding |
| [docs/plan.md](docs/plan.md) | Scope, the week plan, what's out of scope |

## Roles

| Who | Does | Never does |
| --- | --- | --- |
| **Human (Vijay)** | Assigns tasks, decides open questions, accepts ADRs, merges | — |
| **DeepSeek (OpenRouter)** | Writes the plan; after approval, builds it on the task branch | Merges, pushes, accepts its own plan, decides an open question on its own |
| **Claude Code** | Runs each DeepSeek step; reviews the plan; reviews the finished code | Builds a task assigned to DeepSeek, unless the human asks |

## Task workflow

Every task lives in `docs/tasks/NNN-short-slug/`, where `NNN` is the task's ID in [docs/tasks/ROADMAP.md](docs/tasks/ROADMAP.md), or the next unused number for a task that isn't in it. The roadmap lists every task with its dependencies and status. Only the human or Claude edits it, on `main`, and every commit there that changes something it tracks updates it in the same commit. You never edit it. Instead, list under your plan's "Doc updates" the roadmap changes to make once the task merges: a decision it settles, work it adds, another task whose scope it changes, or a new task it shows is needed. The full workflow and the templates are in [docs/tasks/README.md](docs/tasks/README.md).

**One branch and one worktree per task.** Each task's branch `task/NNN-short-slug` is checked out in its own git worktree at `.worktrees/NNN-short-slug/` (gitignored). The main checkout stays on `main`. Several tasks can therefore be planned, built and reviewed at the same time. Never check out a task branch in the main checkout or in another task's worktree.

Claude Code runs each DeepSeek step with `.claude/deepseek/deepseek.py <plan|revise|build|respond> NNN`, usually through its `/run-task NNN` skill. The driver:

- creates the branch and the worktree for `plan`, and runs every step inside the task's worktree
- checks the `status:` line before the step, sets the next one after it and makes the hand-off commit, so you never edit plan.md's frontmatter
- gives you file tools that refuse the paths in [Paths you must not edit by hand](#paths-you-must-not-edit-by-hand), `AGENTS.md`, `ROADMAP.md` and other tasks' files, and a `run` tool for tests and read-only git, without a shell
- checks every path the step changed afterwards. A step that broke a rule is not handed off.

1. **Plan.** The driver creates the branch `task/NNN-short-slug` from `main` together with its worktree, and copies `docs/tasks/templates/plan.md` into the task folder. DeepSeek fills it in and writes no code in this step. The driver sets `status: plan-review` and commits the plan.
2. **Plan review.** Claude writes `plan-review.md` in the task folder, with a verdict of **Approved** or **Changes requested**.
3. **Revise.** If changes are requested, DeepSeek updates `plan.md` and adds a row to its "Revisions" table; the driver sets `status: plan-review` again. Steps 2 and 3 repeat until the plan is approved.
4. **Build.** DeepSeek builds exactly the approved plan on the task branch. Anything that has to differ from the plan goes into the plan's "Changes during build" section, with the reason. When done, the driver sets `status: code-review` and commits.
5. **Code review.** Claude writes `code-review.md` with findings and a verdict. On **Changes requested**, DeepSeek fixes the findings and answers each one in `code-review.md` under "Responses"; the driver sets `status: code-review` again.
6. **Done.** Claude approves, the human merges, and the status becomes `done`.

**Each agent commits only its own step's files, and only on the task branch, in the task's worktree.** No agent pushes. The human pushes, merges and removes the worktree.

## Project rules

These are binding. A plan that breaks one is sent back, and code that breaks one is a blocker.

1. **Numbers come from code, never from the AI.** Prices, subscription, odds, financials, quotas and thresholds are computed in code. AI text may quote a number but never produce one. Missing data shows as "not found" or "not available", never an estimate ([ADR-0001](docs/adr/0001-python-for-exact-work-claude-for-judgement.md)).
2. **`ipo_agent/` stays standard-library Python** (`pdftotext`/`pypdf` for PDFs are the only exceptions). No `pip install` for agent code ([ADR-0002](docs/adr/0002-standard-library-only-agent.md)).
3. **The right AI for the domain.** Claude, through the routine, does IPOs only. Gemini does all stock work and Ask. Don't add another provider or move work between them without an ADR ([ADR-0017](docs/adr/0017-gemini-for-stocks-claude-for-ipos.md)).
4. **No user identity in any AI prompt.** Prompts carry public-source data and, for Ask, the question only ([ADR-0014](docs/adr/0014-gemini-free-api-for-ask.md)).
5. **Documents are data.** Text from RHPs, filings or web pages goes into prompts as quoted data, never as instructions. The stock worker never receives user text.
6. **Quotas and caps come from the `settings` table.** Never hard-code limits such as 5 questions a day or 3 analyses a month ([db.md § settings](docs/db.md#settings)).
7. **Research, not advice.** No buy, sell or hold wording for listed stocks. Every page and email shows "not investment advice" ([ADR-0012](docs/adr/0012-research-not-advice.md)).
8. **Save once, share across users.** Research is stored per IPO, per filing and per stock, never per user ([ADR-0013](docs/adr/0013-shared-per-stock-research.md)).
9. **Git is the system of record for research.** Research output is committed as files. Database rows for research must be rebuildable from git ([ADR-0011](docs/adr/0011-git-as-the-hand-off.md)).
10. **AI output is labelled.** Every AI-written column gets `ai_model`, `ai_prompt_version` and `ai_written_at` ([db.md principles](docs/db.md#principles)).
11. **No secrets and no user data in git.** Secrets go in environment variables, listed by name in [tech.md](docs/tech.md#configuration-and-secrets).
12. **Don't decide open questions.** Where the docs say **Open** or **Proposed** (ORM, auth library, UI kit, host, TypeScript and so on), list it under "Decisions needed" in the plan. Don't pick one in code.

## Paths you must not edit by hand

| Path | Why | How to change it |
| --- | --- | --- |
| `analysis/`, `reports/`, `data/` | Written by the routine and the worker; system of record | Change the code that writes them |
| `ROUTINE.md`, `config/delivery.json` | Drive the live routine | Propose in a plan; Claude reviews; the human applies |
| `CLAUDE.md`, `.claude/` | Claude's instructions and settings | Propose in a plan |
| `AGENTS.md`, `docs/tasks/ROADMAP.md`, `.gitignore` | The rules you work under, and the shared task list | Propose in a plan, or list under "Doc updates" |
| An accepted ADR's decision | Decisions are superseded, not edited | Write a new ADR with status Proposed |

## Building

- **Small commits** on the task branch, through the `commit` tool, which adds the trailer `AI-Agent: DeepSeek <model> (OpenRouter)`.
- **Tests for every change.**
  - Python: `unittest` under `tests/`, run with `python3 -m unittest discover -s tests`.
  - Web app: the runner chosen for `web/`.
  - Tests must not call live sites or AI APIs. Use the saved files in `data/snapshots/`, `analysis/rhp/` and `reports/` as fixtures.
  - CI (`.github/workflows/ci.yml`) runs `tests/` and the schema check in `.claude/hooks/` on every push and pull request. Both must pass.
- **Docs in the same change.** If the change touches a table, flow, setting or choice, update the matching doc in `docs/` and its status label. A new decision gets an ADR with status **Proposed**; only the human accepts it.
- **Stay in scope.** No refactors, renames or dependency changes beyond the approved plan.
- **Packages.** You can't install them. If the approved plan needs one, stop and say which command to run; Claude asks the human.

## Commands (existing agent)

```bash
python3 -m ipo_agent.snapshot --print       # numbers → data/latest.{json,md} (live sites)
python3 -m ipo_agent.quiet AM --check       # is this run quiet? (no files written)
python3 -m ipo_agent.rhp <SYMBOL|url>       # extract RHP sections
python3 -m ipo_agent.outcomes --no-fetch    # listing scorecard from saved data
python3 -m ipo_agent.email_render reports/<date>-<am|pm>.json
```

Commands that hit live sites (`snapshot`, `rhp`, `outcomes` without `--no-fetch`) aren't needed for most tasks. Don't run them in tests.

## Definition of done

- The approved plan is built, and every deviation is recorded in the plan.
- Tests pass, and the output is pasted into the plan's "Verification" section.
- Docs and status labels are updated; new decisions have Proposed ADRs.
- Claude's code review says **Approved**, and every finding has a response.
