# Month plan and AI journal

The hackathon runs from 2026-10-28 to about 2026-11-27 (deadline to be confirmed). This file holds the scope, the week-by-week plan and the AI journal. The journal is the evidence for form sections 4–6, so it is written as the work happens, not at the end.

## Scope

The product grows from an IPO email into a **multi-user research app for Indian investors**:

| Module | What the user gets | Status |
| --- | --- | --- |
| Mainboard IPOs | Daily brief: what's open or upcoming, analysis from the RHP, verdict, best category, allotment odds | Running since 2026-10-12 |
| Track record | Every IPO call against how it actually listed | Data in `data/outcomes.json`; needs a page |
| Stock watchlist | Each user picks listed stocks and gets quarterly results, an announcements digest, and shareholding and pledge changes, with alerts | To build |
| Stock analysis on request | Full company analysis by Gemini, started in the background with a live loading screen; saved and shared; every request counts against the quota | To build ([ADR-0017](adr/0017-gemini-for-stocks-claude-for-ipos.md)) |
| Web app | Sign-up and login, per-user watchlist, IPO and stock pages, track record | To build |
| SME IPOs | — | **Out of scope for now** (decided 2026-10-29) |
| Payments | — | **None in phase 1** (decided 2026-10-29). One free tier for every user: 5 Ask questions a day, 3 new stock analyses a month |

### Watchlist signals

| Signal | Python does | Gemini does ([ADR-0017](adr/0017-gemini-for-stocks-claude-for-ipos.md)) |
| --- | --- | --- |
| Quarterly results | Fetch filed results from NSE; build revenue, profit and margin trends | Summarise what changed and why, from the filing and management commentary |
| Announcements digest | Fetch corporate announcements since the last run | Drop routine filings; explain the ones that matter (orders, acquisitions, auditor or management changes, fund raising) |
| Shareholding and pledges | Fetch the quarterly shareholding pattern and pledge data; flag changes past a threshold | Explain flagged changes in one or two lines |

_The NSE endpoints for each signal have to be confirmed before building on them._

### Design rules that carry over

- **Analyse once, share across users.** A stock's results summary or announcement digest is written once and cached, like `analysis/<key>.json` for IPOs. Every user watching that stock sees the same cached text. Claude's cost grows with the number of distinct stocks and new filings, not with the number of users.
- **AI only on what changed.** A stock with no new filing since the last run costs no tokens, like today's quiet runs.
- **Python for exact work, AI for judgement.** Numbers, thresholds and alerts are computed in Python; the AI (Claude for IPOs, Gemini for stocks) explains them and never supplies a number that isn't in a source.
- **Research, not advice.** The app summarises and flags. It does not tell users to buy or sell listed stocks (in India, that is regulated research advice). Every page and email carries a "not investment advice" note.

### Architecture decisions

Architecture decisions are recorded one per file in [adr/](adr/README.md), and summarised in [arch.md § Decisions](arch.md#8-decisions). Decided on 2026-10-29:

- IPO research stays in the scheduled Claude Code routine, which does IPOs only ([ADR-0003](adr/0003-research-on-a-schedule.md), [ADR-0017](adr/0017-gemini-for-stocks-claude-for-ipos.md)).
- Next.js for the web platform ([ADR-0009](adr/0009-nextjs-web-platform.md)).
- PostgreSQL on Neon ([ADR-0010](adr/0010-postgresql-on-neon.md)).
- Git is the hand-off to the database ([ADR-0011](adr/0011-git-as-the-hand-off.md)).
- Research, not advice ([ADR-0012](adr/0012-research-not-advice.md)).
- Research is shared per stock ([ADR-0013](adr/0013-shared-per-stock-research.md)).
- Gemini API (free tier) for Ask ([ADR-0014](adr/0014-gemini-free-api-for-ask.md)).
- Email to the admin only ([ADR-0015](adr/0015-email-to-admin-only.md)).
- Stock work (analyses on request, filing summaries) on Gemini; every analysis request counts ([ADR-0017](adr/0017-gemini-for-stocks-claude-for-ipos.md), superseding ADR-0016).

- The stock worker runs on GitHub Actions ([ADR-0018](adr/0018-stock-worker-on-github-actions.md)).

Still open: auth library, ORM, Gemini model for Ask, host ([arch.md § Open questions](arch.md#9-open-questions)).

## Week by week

| Week | Dates | Build |
| --- | --- | --- |
| 1 | 29 Oct – 4 Nov | `tests/` for the existing code; `.claude/` skills, subagents and hooks; ADRs; database schema (users, watchlists, stocks, filings, alerts); NSE fetchers for quotes, results, announcements and shareholding, with tests |
| 2 | 5 – 11 Nov | Web app: sign-up, login, watchlist add/remove; IPO pages; track record page; stock pages showing the Python data |
| 3 | 12 – 18 Nov | Gemini stock worker: results summary, announcements digest, shareholding and pledge alerts; shared per-stock cache; on-demand stock analysis with the loading screen and quotas; admin settings page; worker smoke-tested against NSE |
| 4 | 19 – 27 Nov | "Ask about this stock or IPO"; security review; hosting; `project.md`, `architecture.md`, form text; demo video |

If week 3 slips, the IPO side with the web app and track record is still a complete submission.

## Open decisions

- [ ] Product name (it is no longer IPO-only)
- [ ] Hosting
- [ ] Gemini API key; check the free tier's current quotas and terms in AI Studio
- [ ] Judges' access to the repo
- [ ] Organisers confirm that work built before 2026-10-28 is allowed if declared

## Demo script (3 min)

_To write in week 4._

## Submission evidence map

_To fill as the work lands: each form field in [hackathon.md](hackathon.md) → the files, commits and journal entries that back it._

## AI journal

One entry per working session: what we asked the AI to do, what it did, what a human changed or rejected, and what we learned.

### 2026-10-29: Gap analysis and scope

- **Asked:** Claude Code (Opus 5.5) to check the repo against the hackathon brief and say what must change before submitting.
- **AI did:**
  - Pulled the routine's latest runs: 39 commits and 8 listings scored.
  - Mapped each judging criterion to the evidence already in the repo: every commit has a Claude co-author trailer, and `outcomes.py` is a working eval.
  - Listed what's missing: tests, `.claude/` structure, guardrails written as code, a journal, ADRs, any UI besides the email.
  - Found that `docs/hackathon.md` described another project (Atlas), and rewrote it for this one.
- **AI flagged for a human decision:**
  - whether work built before the hackathon may be submitted
  - how judges get access to a private personal repo
- **Human decided:**
  - Submit this project.
  - Widen it beyond IPOs into a multi-user app with a stock watchlist covering results, announcements, and shareholding and pledges.
  - Skip SME IPOs for now.
  - Decide hosting and repo access later.
- **Changed from the AI's proposal:**
  - The AI had suggested SME IPOs with a quick screen and a single-user local app. The human chose multi-user and dropped SME.
  - The AI's "thesis check" signal was not picked.
  - The AI had proposed a standard-library Python web app. The human chose Next.js for the platform and kept the Claude routine for research.

### 2026-10-29 (later): Architecture docs

- **Asked:** for docs that explain the project and its tech stack, then a detailed architecture doc kept apart from the stack doc, a database doc, and any further split that shows the AI-assisted architecture.
- **AI did:**
  - Read the routine's real outputs (snapshot, card, report and outcomes JSON) and the source endpoints in the code.
  - Wrote `project.md`, `arch.md`, `tech.md`, `db.md` (every table mapped to the JSON field it comes from), `ai.md`, `data-sources.md`, a docs index, and 13 ADRs with a template.
  - Kept the Problem (1,335 characters) and Solution (1,873) sections within the form's limits.
  - Checked every relative link and anchor across the docs (0 broken).
- **AI corrected itself:**
  - The first draft of ADRs 0001–0007 said who had proposed each pre-hackathon decision. Nothing in the repo records that, so those lines were replaced with what the commits show.
  - The context of ADRs 0004 and 0005 was rewritten to match commits `f0be1a3` and `c09248d`. The analysis had always been cached; it was the per-run card text and the Markdown email that changed.
  - Items Claude had proposed but the human hadn't approved were relabelled from Decided to **Proposed**. That covers ADRs 0011–0013, the database schema, the import Action, Ask, digests, hooks, skills, subagents, tests and CI.
- **Not verified:** the Mermaid diagrams. Rendering them with the Mermaid CLI was blocked by the session's permissions; they were checked by hand only.
- **Human decided:** the doc set and its split. The proposed items are waiting for a decision.

### 2026-10-29 (later): Decisions on the proposals

- **Human accepted:**
  - ADR-0011 (git → database import), ADR-0012 (research, not advice) and ADR-0013 (shared per-stock research)
  - Ask, per-user digests, hooks, skills and subagents, `unittest` and CI, and the `db.md` schema as the starting point
- **Human overrode:** Ask uses the **Gemini API free tier**, not the Claude API.
- **AI did:**
  - Checked the Gemini free tier with web search. Sources were third-party only and disagree on limits.
  - Recorded ADR-0014 with two consequences of the free tier: Google may use prompts and answers, so no user identity goes in the prompt and users are told; and the quota is shared per project, so each user gets a daily cap.
  - Updated every doc that mentioned the Claude API for Ask, and relabelled the accepted items from Proposed to Decided.
- **Still Proposed:** TypeScript, the analysis quality review and regression set, and two review-process rows in `ai.md`.

### 2026-10-29 (later): Email, shared analysis, settings

- **Human overrode:** no per-user email digests. Only the admin receives email: the routine's existing brief.
- **Human clarified:** shared analysis means that once a stock is analysed, the result is saved and served from the database to every later user; it is never redone for another user.
- **Human asked for:** a platform `settings` table, starting with a daily AI (Ask) limit per person.
- **AI did:**
  - Wrote ADR-0015 and removed digests from every doc: the email provider, `alert_deliveries`, the digest endpoint and token, and the user `digest` preference.
  - Noticed that with no user email, sign-in can't use emailed links or password-reset emails, and recorded Google sign-in or password as the options.
  - Added `users.role` (needed so only an admin can change settings).
  - Designed `settings` as one row per setting, seeded with `ask_daily_limit_per_user = 10`. The default is a placeholder, because Gemini's free quota is shared by all users.
  - Rewrote ADR-0013 in the human's words.

### 2026-10-29 (later): On-demand analysis and quotas

- **Human asked for:**
  - quotas on everything: Ask 5 a day and stock analyses 3 a month per person
  - analysis started in the background at once, instead of waiting for the schedule (expected to take about 15 minutes at most)
  - a loading screen that shows what is being researched and what comes next
- **AI did:**
  - Checked the Claude Code routine API: per-routine token, a free-text payload, no output streaming, and 30 fires an hour per routine.
  - Found the daily run allowance (5 a day on Pro per Anthropic's launch post), which is shared with the scheduled brief and leaves about 3 on-demand runs a day.
  - Designed around it:
    - one run works through the whole queue
    - a platform cap `on_demand_runs_per_day` = 3
    - scheduled runs pick up any leftovers
  - Designed progress reporting: the routine posts each step to the app, and the app shows it.
  - Added `stock_analyses`, `analysis_jobs`, `analysis_job_events` and `analysis_requests`, plus the three quota settings.
  - Wrote ADR-0016 and marked ADR-0003 as partly superseded.
  - Noticed that the app must be reachable from the routine, which moves hosting from week 4 to week 2.
- **Waiting on the human:** whether reading a saved analysis or joining someone else's queued job should use quota. Claude proposed: no, only starting new research counts, and failures are refunded.

### 2026-10-29 (later): No payments in phase 1

- **Human decided:**
  - No payments in phase 1.
  - Every user gets the same limits: 5 Ask questions a day and 3 new stock analyses a month.
- **AI did:**
  - Recorded the decision as out of scope in `project.md` and as a scope row in this plan.
  - Added a "one tier" note to the settings design, so there are no plan or billing tables.
  - Updated ADR-0016: no extra routine usage is bought, so the daily cap on on-demand runs stands.
- **Open:** "Pro plan" in Claude's earlier message meant the Claude subscription that runs the routine, not a user tier. Confirm which plan that account is on, because routines need Pro or higher.

### 2026-10-29 (later): Claude for IPOs only, Gemini for stocks

- **Human decided:**
  - The personal Claude Pro account (architj240) is for IPO research only.
  - Stock analysis on request uses Gemini.
  - Every analysis request counts against the monthly 3, even when a saved analysis is served, because older data may need refreshing.
- **What changed from Claude's proposals:** both points overrode them. ADR-0016 had used the Claude routine for stocks and charged only for new research.
- **AI did:**
  - Superseded ADR-0016 with ADR-0017. The quotas, queue and live loading screen carry over.
  - Read "Pro only for IPOs" as moving the scheduled watchlist summaries to Gemini too, and asked the human to confirm.
  - Proposed a host for the stock worker: GitHub Actions (ADR-0018). Recorded the options and their limits, including the about 2,000 free minutes a month for a private repo (third-party sources only).
  - Had the worker write progress straight to the database, so the app needn't be reachable from it. That moves hosting back to week 4.
  - Fixed a schema problem: serving a saved analysis creates no job, so `analysis_requests` now has its own ID, a `symbol` and a nullable `job_id`.
  - Added the settings `analysis_daily_limit_platform` and `analysis_refresh_after_days`, both with Proposed defaults, and dropped `on_demand_runs_per_day`.
  - Checked whether Gemini's free tier includes search grounding. Sources disagree, so the analysis says "news not checked" when grounding isn't available.
  - Swept every doc for text that said saved analyses are free or that the routine does stock work.
- **Waiting on the human:**
  - the worker host
  - the freshness rule
  - whether reopening the same stock in the same month is charged again
  - refunds on failure
  - the platform cap's default

### 2026-10-29 (later): Follow-up decisions

- **Human accepted all four of Claude's recommendations:**
  - the stock worker runs on GitHub Actions (ADR-0018 accepted)
  - a saved analysis is refreshed after 30 days or when a newer quarterly result exists
  - reopening the same stock in the same month isn't charged again
  - a failed analysis refunds the request
- **AI did:** relabelled these items from Proposed to Decided across the docs.
- **Still open:** the platform cap's default, which waits on the Gemini quota in AI Studio.

### 2026-10-29 (later): Agents and the task workflow

- **Human decided:**
  - DeepSeek in opencode creates each task's plan and builds it.
  - Claude Code reviews the plan, gives feedback, and does the final code review.
  - The human asked for an `AGENTS.md` and an updated `CLAUDE.md`.
- **AI did:**
  - Checked opencode's docs: it loads `AGENTS.md` and falls back to `CLAUDE.md` only when `AGENTS.md` is missing.
  - Wrote `AGENTS.md`: roles, the task workflow, 12 project rules drawn from the ADRs, paths agents must not edit, build and test rules, and the definition of done.
  - Kept `CLAUDE.md` short, because the IPO routine loads it on every run. It gained a "Development sessions" section that points to the reviewer guide.
  - Added `docs/tasks/`: statuses, a reviewer guide with checks and severities, and templates for the plan, plan review and code review.
  - Wrote ADR-0019.
  - Noticed that the human's opencode `superpowers` plugin has its own plan location, and told DeepSeek to keep plans in the task folder.

### 2026-10-29 (later): `.claude/` and `.opencode/`

- **Human asked** why neither directory existed.
- **AI answered:** the skills, subagents and hooks had been marked Decided but not built, and DeepSeek ran on global opencode settings only.
- **Human chose** to build both now, with Claude building them. DeepSeek isn't allowed to write its own limits.
- **AI did:**
  - Built `.claude/hooks/guard.py`:
    - **pre-bash:** blocks force, mirror and delete pushes, and pushes to any remote except `origin`.
    - **post-write:** checks IPO cards and verdict files for schema, verdict values, file name against date and session, and GMP or today words in cards.
    - **Fail-safe:** a bug in the guard never blocks the live routine; only a rule violation does.
  - Wrote 17 tests. They pass, including every card and report already in the repo and the routine's own `git push origin HEAD:main`.
  - Added skills: `review-plan` and `review-code` for Claude's reviews; `analyse-ipo`, `anchor-update` and `daily-verdict` (ROUTINE.md steps) for development sessions.
  - Added subagents `rhp-analyst` and `verdict-reviewer`.
  - Added `opencode.json`: `git push` is denied, risky git and install commands ask first, and edits are denied for routine output, `ROUTINE.md`, Claude's config and opencode's own config.
  - Added `.opencode/agents/planner.md` (can only edit `docs/tasks/`) and four commands, one per workflow step.
  - Checked opencode's docs for the permission format: the last matching rule wins, `*` matches across folders, and edit patterns are relative to the project root.
- **Not verified live:** Claude Code loads hooks when a session starts, so they haven't run in a real session yet. The tests feed them the same JSON Claude Code sends.

### 2026-10-29 (later): Task roadmap

- **Human asked for:** every task from here to a finished system, step by step, each with a description, whether it's done, and what it depends on, in a file DeepSeek can plan from and Claude can review against.
- **AI did:**
  - Wrote `docs/tasks/ROADMAP.md`:
    - 26 tasks with IDs matching their task folders, each with a slug, its dependencies, owner, done-when checks, docs to read and the `/plan-task` line
    - 13 human decisions (D01–D13), one gate (G1: does NSE answer from GitHub's runners) and 6 setup steps (H01–H06)
    - milestones M1 (IPO side live, a complete submission on its own), M2 (stock side) and M3 (complete)
  - Checked that every dependency points to an earlier task (so there are no cycles), that the summary table, the task entries and the graph agree, and that every link resolves.
  - Changed `/plan-task` and `AGENTS.md` so a roadmap task keeps its roadmap ID instead of taking the next free number.
- **AI flagged for a human decision:**
  - **D09:** the stock worker needs a Postgres driver and a Gemini client, and neither is in the standard library. ADR-0002 binds only `ipo_agent/`. Also, `tech.md` says one Gemini module is shared by the TypeScript app and the Python worker, which can't work.
  - **D10:** no doc sets the alert thresholds.
  - The watchlist's 50-stock cap is hard-coded in `db.md`, against rule 6.
  - The docs don't say whether IPO pages need sign-in.
  - Two Decided items weren't built: AI provenance in the routine's cards and reports, and the "documents are data" rule in `ROUTINE.md`. Both are now task 004.

### 2026-10-29 (later): A worktree per task

- **Human asked for:** each task to get its own git branch and worktree, named by task ID, so several tasks can be worked on at once and Claude can review each one easily.
- **AI did:**
  - Checked opencode's docs. Started inside a git worktree, opencode takes the worktree as the project root and reads that worktree's `opencode.json`, so the path-based deny rules keep working there. Agent permissions override global ones, and the last matching rule wins.
  - Changed `/plan-task` to run from the main checkout and create `task/NNN-slug` with its worktree at `.worktrees/NNN-slug/` (gitignored).
  - Changed `/revise-plan`, `/build-task` and `/respond-review` to run only in a session opened inside that worktree. Each one checks first.
  - Changed Claude's `review-plan` and `review-code` skills to read, test and commit inside the worktree, and never check out a task branch in the main checkout.
  - Added a deny rule for `.worktrees/*` to the main checkout's opencode permissions, because path rules like `analysis/*` don't match inside a nested worktree. The planner gets a narrow exception for `.worktrees/*/docs/tasks/*`.
  - Closed a gap: `git -C <path> push` slipped past the `git push*` deny rule.
  - Dry-ran creating and removing a worktree; `git status` stayed clean.

### 2026-10-29 (later): Task 003, NSE stock-data spike

- **Asked:** DeepSeek to plan and build task 003, and Claude Code to review the plan and the code. When opencode stopped working, the human asked Claude to finish the task.
- **Rounds:** two plan rounds and two code rounds.
- **Plan review, round 1 changes:**
  - a fixed list of 12 requests with a hard cap in code
  - no assumed units
  - a set order for getting the GitHub run result onto the branch
  - fixtures trimmed in code
  - a `paths:` filter so review commits don't call NSE again
- **AI did:**
  - DeepSeek built the probe, the fixtures, the workflow and the docs.
  - Claude pushed the branch at the human's request. It read the run with `gh`, recorded the result, reviewed the code, fixed the findings and merged.
- **Result:** NSE answers from GitHub's runners. Nine of ten data calls answered, the same as locally ([run 40869763010](https://github.com/badjatya/IPO/actions/runs/40869763010)). The quote endpoint returns 403 everywhere, so it's a problem with that endpoint, not a runner block.
- **Notable finding:** the docs mapped "share of promoter holding pledged" to NSE's `percSharesPledged`. Arithmetic on the committed fixtures showed that field is a share of *all* shares (ADANIENT: 1.61 against 2.23), so the worker would have stored about half the real figure. The mapping now computes it in code.
- **Human decided:** tick G1, merge, and hand the quote gap and the other gaps to task 014.
- **Learned:**
  - Check field meanings against the fixture's own numbers, not just its field names.
  - When Claude both fixes and reviews, the review records that it isn't independent.

### 2026-10-29 (later): Task 001, agent test suite

- **Asked:** DeepSeek to plan and build task 001, and Claude Code to review the plan and the code. When opencode stopped working, the human asked Claude to fix the code-review findings and merge.
- **Rounds:** three plan rounds and two code rounds.
- **Plan review, what changed:**
  - **Round 1:**
    - A network guard that would actually fail. The first design raised an error that the agent's own `except Exception` handlers swallowed.
    - The saved report paired with its own snapshot, not `data/latest.json`.
    - A smoke test that couldn't overwrite committed email files.
    - A list of every root and default argument to redirect.
    - Provenance for hand-built fixtures.
  - **Round 2:** Claude's own round-1 suggestion was incomplete. Patching only `socket.connect` misses DNS: with no network, the lookup fails first with an ordinary `URLError`, and the guard records nothing. Claude showed this with a probe, and the guard now blocks `getaddrinfo` too.
- **AI did:**
  - DeepSeek built 167 tests over ten modules, with hand-built fixtures.
  - Claude ran the suite normally and inside a no-network namespace (`unshare -rn`).
  - Claude reviewed the tests and found five issues, then fixed them at the human's request:
    - a snapshot test that would fail from late October 2027, because `build` reads the real clock;
    - the "NSE overrides Investorgain" rule untested, because both fixtures used the same price and lot;
    - a fixture with text prices where NSE sends numbers, as `data/outcomes.json` shows;
    - a guard self-test that skipped the HTTP client;
    - a docstring with wrong advice about default arguments.
  - Claude merged the task. On `main`, 188 tests pass (with task 003's).
- **How the fixes were checked:**
  - **Clock:** the build tests pass with the clock frozen in 2026, 2027 and 2030.
  - **Precedence:** with the precedence reversed in a scratch copy of the code, the new test fails.
- **Not taken up:** Claude offered to capture one real page from each source for the parser fixtures. That option was left open, so the fixtures stay hand-built and labelled.
- **Learned:**
  - A safety net needs its own test, run through the real code path. A guard that is only called directly proves little.
  - Tests that depend on the clock pass today and fail in a year. Freeze the clock wherever code stamps the time.
  - The same reviewer finding, fixing and approving is not an independent check. The review says so.

### 2026-10-29 (later): Task 002, CI workflow

- **Asked:** with opencode unavailable, the human asked Claude Code to do task 002, then to push, merge and update the roadmap.
- **Rounds:** none. Claude planned and built the task in one step, and the human merged it without an independent review. The plan and the roadmap say so.
- **AI did:**
  - Claude wrote `.github/workflows/ci.yml`: agent tests and the schema check on every push and pull request.
  - Before pushing, Claude checked that both suites pass from a clean worktree under UTC, IST and US time zones and the C locale. It also showed the schema step goes red on a bad card and on a report whose name doesn't match its date.
  - Claude pushed the branch, read the runs with `gh`, merged and updated the docs.
- **Notable finding:** the first design keyed concurrency on the branch with `cancel-in-progress` off for `main`, on the belief that every routine push would then get a run. GitHub keeps only one pending run per group, so a burst of pushes could still drop one. Runs on `main` are now grouped by commit.
- **Result:** CI passed on the task branch ([run 40877897168](https://github.com/badjatya/IPO/actions/runs/40877897168)) and on `main` ([run 40878105228](https://github.com/badjatya/IPO/actions/runs/40878105228)). Schema check is Running in ai.md.
- **Learned:**
  - A CI that runs on the routine's pushes must never be a required check, or it blocks the routine.
  - Prove a check can fail before calling it Running.

### 2026-10-29 (later): DeepSeek through OpenRouter

- **Human decided:**
  - Drop opencode, which had been unavailable for all three tasks so far.
  - Run DeepSeek through OpenRouter (`deepseek/deepseek-v4-flash-0731`), with Claude Code running its steps and reviewing them ([ADR-0021](adr/0021-deepseek-on-openrouter.md)).
  - The key and the model name went into the gitignored `.env.local`.
- **AI did:**
  - Tested two-turn tool calling against the exact model before writing the driver. The model returns `reasoning_details` with its tool calls, and sending the whole message back works.
  - Wrote `.claude/deepseek/deepseek.py`, standard library only. It has four steps (plan, revise, build, respond) ported from the opencode commands, and gives DeepSeek file tools, a `run` tool with no shell and a `commit` tool.
  - The driver, not the model, checks and sets the status line and makes the hand-off commit. Each step logs its messages and cost to `.deepseek-logs/`, and has a turn limit and a cost cap.
  - Wrote 21 tests with a scripted fake model and a throwaway git repo. They run in CI.
  - Added the `/run-task NNN` skill. It runs the loop and stops for the human on decisions, setup steps, packages to install, a third round without approval, a broken write rule, and `merge-ready`.
  - Removed `opencode.json` and `.opencode/`. Superseded ADR-0019 with ADR-0021, and updated `AGENTS.md`, `CLAUDE.md`, the task guide, the roadmap and the docs.
- **Notable finding:** an advisor model pointed out that file-tool rules can't stop code run through `python3 -m unittest`, which can write anywhere. The driver now checks every changed path and commit after each step. It also replaces the API key in every tool result and blocks a step whose files hold it, because such a script could read `.env.local`. The docs describe these checks, Claude's review and "only the human pushes" as the boundary, not the file tools.

### 2026-10-29 (later): Task 005, figures check

- **Asked:** the human started `/run-task 005`. Later the human asked Claude to do the rest as well: the `.claude/` hook, the merge, the push and the roadmap.
- **Rounds:**
  - **Plan:** two rounds. The human chose report-only when the plan asked.
  - **Code:** two rounds.
  - **Cost:** DeepSeek's steps cost $0.30 in total: plan $0.017, revise $0.009, build $0.205, respond $0.071.
- **Notable findings:**
  - **Plan review:** the planned hook printed its report to stderr and exited 0. Claude Code never shows that to Claude, so the report would have been invisible. It now uses `additionalContext`.
  - **Plan review:** rounding tolerance now comes from the digits written, and price-band ranges count both ends.
  - **Code review, Blocker:** a "USD" guard dropped most rupee figures written in prose.
  - **Code review, Major:** `Rs.` matched the end of words like "peers.".
  - **DeepSeek's correction:** DeepSeek showed that fixing the guard left the total unchanged at 54/316. Claude reran it and confirmed.
- **Result:** the guardrail and the eval are Running. Across 13 analyses, 54 of 316 ₹ figures were found in the RHP text (17%).
- **Learned:**
  - The two-model loop caught real bugs on both sides. DeepSeek's build was solid apart from one over-broad guard.
  - The driver blocked DeepSeek from running its own CI command, so the driver now allows the agent's offline commands.

### 2026-10-29 (later): Task 004, routine provenance and documents-as-data

- **Asked:** the human asked Claude to pick a Ready task nobody was working on. Another session had 005. Claude chose 004, the only Ready task with no open decisions, and ran `/run-task 004`. The human then asked for the merge.
- **Rounds:**
  - **Plan:** two rounds.
  - **Code:** one round, approved with a Minor follow-up: no test checks that a card carrying the fields renders the same.
  - **Cost:** DeepSeek's steps cost $0.065 in total: plan $0.042, revise $0.010, build $0.013.
- **Human decisions:** `ai_prompt_version` comes from a version line in `ROUTINE.md`. `ai_model` is the model actually writing the file, so files from Opus development sessions aren't labelled Sonnet.
- **Notable findings:**
  - **Claude applied the plan's exact diffs to a scratch copy and ran the guard tests.** This showed that the plan's fallback, writing `"not available"` when `date` fails, would be rejected by the plan's own guard and stop the routine at the write hook. The fallback now leaves the field out.
  - **A bare-number `ai_prompt_version` was also rejected,** so `ROUTINE.md` now says to quote it.
  - **The step-4 diffs were written against the branch.** 005 changed `guard.py` on main in the meantime. Rebuilding them against main, rather than diffing the branch's files, kept 005's figures hook.
- **Learned:**
  - Applying a plan's "exact diffs" to a scratch copy and running the tests is a cheap and reliable plan-review check.
  - Changes the human applies by hand should be rebuilt against the current main at merge time.
