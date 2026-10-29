# ADR-0016: On-demand stock analysis through the routine, with quotas and live progress

- **Status:** Superseded by [ADR-0017](0017-gemini-for-stocks-claude-for-ipos.md) on 2026-10-29. Stock analysis moved to Gemini, and every request now counts against the quota. The quotas, queue and live progress screen carry over
- **Decided:** 2026-10-29 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

A user who wants an analysis of a stock nobody has analysed yet shouldn't wait up to about 12 hours for the next scheduled run. The human expects one analysis to take about 15 minutes at most. They want it to start in the background at once, with a loading screen that shows what is being researched and what comes next. Usage must be limited, so the human set quotas: 3 stock analyses per person per month, and 5 Ask questions per person per day.

What we confirmed about Claude Code routines on 2026-10-29:
- **Starting a run.** A routine can be started over HTTP with `POST /v1/claude_code/routines/{id}/fire` and a per-routine bearer token. The request can carry up to 64 KB of free text, which is passed to the run with its saved prompt. The call returns a session ID and URL, but no output: it doesn't stream and doesn't wait.
- **Rate limits.** Each routine accepts up to 30 fires per hour, and each account up to 100.
- **Daily runs.** Runs count against a daily allowance per account. Anthropic's launch post gives 5 a day for Pro (15 for Max), with extra usage available beyond that. Scheduled runs use the same allowance. Our brief uses 2 a day on weekdays, so about 3 are left for on-demand work.
- **Usage.** Runs also use the account's normal Claude Code usage.

## Options

| Option | For | Against |
| --- | --- | --- |
| Wait for the next scheduled run | No new parts | Up to about 12 hours' wait |
| Run the analysis in the app with the Gemini free API | No routine runs used | Weaker research; Gemini's free quota is already shared by Ask; long jobs don't fit a web request |
| Run it in the app with the Claude API | Fast, full control | Paid per token |
| **Start the existing routine on demand; it reports progress to the app** | Same agent, same quality, same git → database path; no worker to host | About 3 runs a day across all users; the app must be reachable from the routine |

## Decision

1. **Saved analyses are free to read.** When a user asks for a stock's analysis and one is saved, the app serves it from the database at once, with no AI call ([ADR-0013](0013-shared-per-stock-research.md)).
2. **New analysis goes through a queue.** If no analysis is saved, the app creates or joins a queued **analysis job** for that stock and checks the quotas.
3. **One run works through the queue.** If no on-demand run is active and the day's on-demand budget isn't used up, the app starts the routine. The run's text carries only the queued job IDs and symbols, never user text. One run takes every job queued at that point, one stock after another. Scheduled runs also work through anything still queued.
4. **The routine reports each step to the app** through a small Python helper. The app shows the steps on the loading screen: queued (with position), starting the research session, price and valuation, quarterly results, shareholding and pledges, announcements, news, writing the analysis, saving.
5. **Results take the usual path.** The routine writes `data/stocks/<SYMBOL>/analysis.{md,json}` and commits, and the import puts it in the database ([ADR-0011](0011-git-as-the-hand-off.md)). The job is done when the import has the analysis, and the loading screen then opens it.
6. **The same quotas for every user** (phase 1 has no paid tiers). They live in the [`settings`](../db.md#settings) table and an admin can change them without a deploy:
   - `analysis_monthly_limit_per_user` = 3
   - `ask_daily_limit_per_user` = 5
   - `on_demand_runs_per_day` = 3, which protects the scheduled brief's runs

## Consequences

**The user leaves the page while they wait.** The job page polls its status, and the user can leave and come back. The loading screen shows queue position and the step in progress.

**No paid way out of the cap in phase 1.** Phase 1 has no payments: users are on one free tier, and we don't buy extra routine usage or a bigger plan. So the platform cap stays at what the current Claude plan allows, and busy days queue.

**Waits get longer when demand is high.** With about 3 runs a day, a busy day queues jobs into the next scheduled run, and the loading screen says when that is. Batching keeps throughput up: one run can handle several stocks.

**The quota counts new research only.** A request is charged only when it starts new research; reading a saved analysis is free. If several users ask for the same stock while its job is queued or running, they share the job and only the first is charged. A failed job refunds the charge. The human still has to confirm this rule.

**The app has to be reachable from the routine.** The routine's network allowlist needs the app's host, so on-demand analysis needs a public host or a tunnel, earlier than week 4.

**Some failures need handling.**
- A job with no progress for 30 minutes is marked failed and refunded, and the next run picks it up again.
- A 429 or 5xx from the fire endpoint leaves the job queued.

**Duplicate starts are possible.** The fire endpoint has no idempotency key, so the app records the session it started and never fires while one is active.

**Two ADRs change.**
- ADR-0003 (research on a schedule) is partly superseded: stock analysis can now also run on request, asynchronously.
- The [`settings`](../db.md#settings) defaults change: Ask goes from 10 to 5.

## AI involvement

**The human set the direction:** on-demand background analysis, a loading screen with steps, and the quotas. Claude Code did three things:
- checked the routine API and its limits
- found the shared daily-run cap, and proposed batching and the platform-wide `on_demand_runs_per_day` cap to protect the brief
- proposed the "charge new research only" rule, which is still waiting for the human

## Evidence

- [Trigger a routine through the API](https://platform.claude.com/docs/en/api/claude-code/routines-fire) (checked 2026-10-29)
- [Introducing routines in Claude Code](https://claude.com/blog/introducing-routines-in-claude-code) (daily run counts per plan)
- [AI journal 2026-10-29](../plan.md#ai-journal)
