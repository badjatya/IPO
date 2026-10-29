# AI Hackathon: Brief and Submission Guide

This is the reference for the organization's month-long AI hackathon: how it is judged, what we have to submit, and where each answer will come from. The project we are submitting is the **IPO research agent** in this repository, widened during the hackathon into a multi-user research app with a stock watchlist (scope in [plan.md](plan.md#scope)).

- **What it is and how a run works:** [README.md](../README.md)
- **What Claude does on each run:** [ROUTINE.md](../ROUTINE.md)
- **Instructions Claude loads in this repo:** [CLAUDE.md](../CLAUDE.md)
- **What the project is (problem and solution text for the form):** [project.md](project.md)
- **Architecture (form section 3):** [arch.md](arch.md), with [tech.md](tech.md) (stack), [db.md](db.md) (database) and [data-sources.md](data-sources.md) (integrations)
- **AI design (form sections 4–6):** [ai.md](ai.md)
- **Decisions (form section 7):** [adr/](adr/README.md)
- **Index of all docs:** [docs/README.md](README.md)
- **Scope, month plan and AI journal:** [plan.md](plan.md)

## At a glance

| Item                | Detail                                                                                    |
| ------------------- | ----------------------------------------------------------------------------------------- |
| Product             | Research app for Indian investors: a scheduled Claude agent researches mainboard IPOs; Gemini researches listed stocks on request and for each user's watchlist (results, announcements, shareholding and pledges); web app plus email brief |
| Format              | Internal AI hackathon, about one month                                                    |
| Start               | 2026-10-28                                                                                |
| Submission deadline | _TBD (we assume about 2026-11-27 until it's confirmed)_                                   |
| Team                | 1 developer (Vijay) + AI agents: DeepSeek through OpenRouter (plans and builds), Claude Code (runs DeepSeek's steps and reviews them; runs the IPO routine) |
| Goal                | Win: score highly on every judging criterion                                              |

## Starting point

The agent existed before the hackathon. The form should say plainly what was built before 2026-10-28 and what was built during it.

| Period                 | What happened                                                                                                                                           | Evidence                                                    |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| 2026-10-12 to 10-15    | Built with Claude Code (Opus 5.5): fetchers, RHP extractor, allotment maths, cached cards, quiet runs, trends, listing scorecard, HTML email             | Commits with `Co-Authored-By: Claude Opus 5.5` trailers     |
| 2026-10-12 onwards     | Runs as a scheduled Claude Code routine (Sonnet 5.5) at 09:07 and 19:07 IST on weekdays; each run commits its brief                                    | `reports/`, `data/snapshots/`, routine commits (`Claude`)   |
| From 2026-10-28        | Hackathon work: see [plan.md](plan.md)                                                                                                                  | AI journal, ADRs, PR history                                |

_Open question: confirm with the organisers that existing work is allowed, as long as it is declared._

## How we are judged

### Criteria (as announced)

1. **AI-assisted engineering:** how well AI is used to build the product.
2. **How well we use AI:** the depth and quality of AI usage overall.
3. **AI structure:** how the AI work is organised (agents, skills, instructions, workflows, guardrails).
4. **Bonus: AI used inside the platform.** The product itself uses AI as a core capability.

### Evaluation process

| Stage | Evaluator        | What they look at                                                                                                     |
| ----- | ---------------- | --------------------------------------------------------------------------------------------------------------------- |
| 1     | **AI evaluator** | The written submission (all form sections) and the repository; produces an AI score                                   |
| 2     | **Human judge**  | The AI score, plus how well the problem statement and solution fit, plus **UI/UX quality**, which has to be top notch |

### What this means for us

- **The AI evaluator reads text and repos.** Every claim in the form needs evidence in the repository: instruction files, agent and skill definitions, hooks, tests, evals, ADRs, PR history.
- **Sections 4–6 carry most of the form.** They are about _process_, so from now on the process is recorded as it happens (AI journal in [plan.md](plan.md)).
- **The human judge sees the demo.** Today the only UI is the email. A dashboard has to make the product feel finished, not like a prototype.
- **The bonus criterion is our strongest.** AI is the analyst inside the product:
  - **Claude** reads each RHP, researches anchor investors and news, and gives every IPO a verdict and a best category.
  - **Gemini** writes stock analyses on request, with a live progress screen, summarises filings and answers questions. The listing scorecard (`data/outcomes.json`) measures those calls against real listings.

### Where we stand per criterion

| Criterion                | Already in the repo                                                                                     | Missing                                                                       |
| ------------------------ | ------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| AI-assisted engineering  | Every commit has a Claude co-author trailer; the code was built with Claude Code                        | AI journal, ADRs, PRs that show the plan → build → review loop                |
| How well we use AI       | Split between Python (exact work) and Claude (judgement); RHP and analysis cached once per IPO; quiet runs skip Claude | Write-up with numbers: tokens or runs saved, analyses reused             |
| AI structure             | `AGENTS.md`, `CLAUDE.md`, `ROUTINE.md`, scheduled routine; `.claude/` skills, subagents and tested hooks; the DeepSeek driver `.claude/deepseek/` and the `/run-task` loop; task workflow in `docs/tasks/` | The scheduled routine still follows `ROUTINE.md` directly, not the skills; the first tasks run through the workflow |
| AI inside the platform   | Claude writes every analysis, card and verdict; scorecard tracks the calls                              | An in-product AI feature the judge can try (e.g. "Ask about this IPO")        |
| QA & testing (form §6)   | Listing scorecard works as an eval of the verdicts                                                      | No `tests/`; no schema checks; no check that analysis numbers come from the RHP |
| UI/UX (human judge)      | Designed HTML email                                                                                     | Dashboard                                                                     |

## Submission form

Fields marked \* are required. Character limits apply per field.

### 1. Project overview

| Field                      | Limit | Source                                                                                     |
| -------------------------- | ----- | ------------------------------------------------------------------------------------------ |
| Project / product name     | —     | _TBD_ (no longer IPO-only)                                                                 |
| Problem statement\*        | 2,000 | [project.md § Problem](project.md#problem)                                                 |
| Solution & key features\*  | 3,000 | [project.md § Solution](project.md#solution)                                               |
| Working product / demo URL | —     | Dashboard (hosting TBD) or a recording of a local run, plus a sample email from `reports/` |
| Source code repositories\* | —     | GitHub repo link (_access for judges TBD: the repo is private_)                            |

### 2. Demo video

| Field            | Limit | Source                                                                       |
| ---------------- | ----- | ---------------------------------------------------------------------------- |
| Demo video URL\* | —     | 3-minute scripted video ([plan.md § Demo script](plan.md#demo-script-3-min)) |

### 3. Technical architecture & stack

Markdown (or an uploaded `.md`) covering system architecture, components, data flow, technology stack, APIs, integrations and key technical decisions.

| Field                     | Limit  | Source                                                                                                                  |
| ------------------------- | ------ | ----------------------------------------------------------------------------------------------------------------------- |
| Architecture (Markdown)\* | 10,000 | Condensed from [arch.md](arch.md), [tech.md](tech.md), [db.md](db.md) and [data-sources.md](data-sources.md); the full docs stay in the repo |

### 4. AI development approach & context engineering

| Field                                           | Limit | Evidence                                                                                   |
| ----------------------------------------------- | ----- | ------------------------------------------------------------------------------------------ |
| How was AI used during development?\*           | 5,000 | Commit history (Opus for development), AI journal                                          |
| Which AI tools and models were used?\*          | 5,000 | DeepSeek `deepseek-v4-flash-0731` through OpenRouter (plan and build; briefly in opencode before that), Claude Code Opus 5.5 (runs and reviews DeepSeek's steps; earlier build), Claude Sonnet 5.5 (IPO routine), Gemini (stocks, Ask), Gmail connector, web search |
| How did you manage context?\*                   | 5,000 | `CLAUDE.md`, `ROUTINE.md`, cached `analysis/`, `data/latest.md` as the single input, quiet runs |
| Approach to planning, prompting and iteration\* | 5,000 | AI journal, ADRs, commit history (e.g. quota fix in `44f553a`)                             |

### 5. AI skills, agents, instructions & guardrails

| Field                                                | Limit | Evidence                                                                                 |
| ---------------------------------------------------- | ----- | ---------------------------------------------------------------------------------------- |
| Agents, skills, reusable instructions or workflows\* | 5,000 | `AGENTS.md`, `CLAUDE.md`, `ROUTINE.md`, the task workflow in `docs/tasks/`, scheduled routine; `.claude/` skills, subagents and hooks; the `/run-task` loop and the DeepSeek driver in `.claude/deepseek/` |
| Responsibilities the agents handled\*                | 5,000 | RHP analysis, anchor research, cards, daily verdicts, best category, delivery, commits  |
| Guardrails implemented\*                             | 5,000 | Rules: never invent numbers, facts only in cards (`ROUTINE.md`, `AGENTS.md`). Hooks: card and verdict schema, live-number words, push limits (`.claude/hooks/guard.py`, 17 tests). DeepSeek driver: no push; file tools refuse routine output and agent config; plan steps write only the plan; a post-step check on every changed path; no API key in its environment. Quiet runs; per-user quotas from `settings` |
| How was human review incorporated?\*                 | 5,000 | Test runs before enabling the routine; every task goes plan → Claude plan review → build → Claude code review → human merge ([docs/tasks/](tasks/README.md)); human decisions and overrides in ADRs |

### 6. AI-assisted QA & testing

| Field                                                | Limit | Evidence                                                                         |
| ---------------------------------------------------- | ----- | -------------------------------------------------------------------------------- |
| AI-assisted testing strategy\*                       | 5,000 | `tests/` (188 offline tests) and CI on every push; scorecard as an eval of the verdicts |
| Tests created or executed\*                          | 5,000 | `tests/`; `python3 -m ipo_agent.outcomes --no-fetch`                |
| How AI helped find bugs, edge cases or regressions\* | 5,000 | AI journal; commits such as the Sahajanand retail quota fix (35%, not 10%)       |
| How were test results validated?\*                   | 5,000 | CI on every push (`.github/workflows/ci.yml`); scorecard against real listing prices |

### 7. Key decisions, limitations & dependencies

| Field                                          | Limit | Evidence                                                                                          |
| ---------------------------------------------- | ----- | ------------------------------------------------------------------------------------------------- |
| Important architectural or product decisions\* | 2,000 | [adr/](adr/README.md): 19 ADRs with options, consequences and AI involvement |
| Known limitations or incomplete features\*     | 1,500 | SME IPOs out of scope; depends on public NSE/Investorgain data; few listings scored so far; GMP is unofficial |
| External dependencies\*                        | 1,000 | Investorgain, NSE, SEBI, `pdftotext`, Claude Code routine, Gemini API, GitHub Actions, Neon, Gmail connector |
| Current risks and future improvements\*        | 5,000 | Source sites changing or blocking; not financial advice; features in [plan.md](plan.md)           |

## Submission checklist

- [x] Project chosen: **IPO research agent**
- [ ] Product name final
- [ ] Organisers confirm that existing work is allowed if declared
- [ ] Judges' access to the repo decided (private personal repo today)
- [x] `plan.md` written: scope, weeks, AI journal
- [x] `project.md`, `arch.md`, `tech.md`, `db.md`, `ai.md`, `data-sources.md` and ADRs written
- [ ] Problem statement and solution text within limits
- [ ] AI journal started and kept up to date
- [ ] `tests/` added and passing
- [x] `.claude/` skills, subagents and hooks in place; `.claude/deepseek/` driver for DeepSeek
- [ ] Web app built: accounts, watchlist, IPO and stock pages, track record
- [ ] "Not financial advice" disclaimer in the email, dashboard and README
- [ ] Demo runs end to end on live IPO data
- [ ] Demo video recorded and uploaded
- [ ] README explains how to run it locally in one or two commands
- [ ] Architecture text for the form condensed to under 10,000 characters
- [ ] Sections 4–7 written from the AI journal, ADRs and repo evidence
- [ ] Every claim in the form points to something real in the repo
