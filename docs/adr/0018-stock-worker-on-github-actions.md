# ADR-0018: Stock worker runs on GitHub Actions

- **Status:** Accepted
- **Decided:** 2026-10-29 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

Stock work now runs on Gemini ([ADR-0017](0017-gemini-for-stocks-claude-for-ipos.md)), outside the Claude routine. It needs somewhere to run.

**What the host must handle:**
- **Long jobs.** An analysis may take up to about 15 minutes, which doesn't fit in a web request.
- **Two triggers.** It must start on request from the app and on a schedule for watched stocks' filings.
- **NSE access.** It must reach NSE, which blocks some cloud IP ranges.
- **Shared code.** It should reuse the standard-library Python fetchers.
- **Free.** Phase 1 has no payments.

## Options

| Option | For | Against |
| --- | --- | --- |
| Background work inside the Next.js app | One deployable | Serverless hosts cap request time well below 15 minutes; long work needs a queue and worker anyway |
| A separate always-on worker on another free host | Fast start; full control | Another service to run; free tiers sleep; NSE access unknown |
| **GitHub Actions workflow** (dispatched by the app, plus a cron schedule) | Already have the repo and secrets; runs the Python fetchers as they are; jobs can run for hours; can commit to git; free minutes | Startup takes tens of seconds; about 2,000 free minutes a month for a private repo (per third-party sources; check GitHub's billing page); NSE may block GitHub's runners |

## Decision

The worker is a GitHub Actions workflow with two triggers:
- **`workflow_dispatch`:** the app calls GitHub's API when a job is queued and no worker is running.
- **`schedule`:** twice each weekday, for watched stocks' filings and any leftover jobs.

**How it runs:**
- **Queue in the database.** The worker claims all `queued` jobs from Postgres and loops until none are left. A dispatch GitHub drops or merges therefore loses nothing; a `concurrency` group keeps one worker at a time.
- **Progress and results go to the database.** The worker writes them straight to Postgres with the app's own database code, so the app never needs to be reachable from the worker. It also commits the result files to git ([ADR-0011](0011-git-as-the-hand-off.md)).
- **Numbers from Python, writing from Gemini.** Numbers come from the standard-library Python fetchers, and the writing comes from the Gemini API.

## Consequences

- **Hosting stays in week 4.** The app's host isn't needed for the worker.
- **NSE smoke test in week 1.** If NSE blocks GitHub's runners, we need another host or source before building on this.
- **Minute budget.** Worker minutes count against the Actions allowance along with the import and CI. The platform cap on analyses a day also keeps minutes in budget.
- **Secrets.** Two secrets go into the repo's Actions settings: the database URL and the Gemini key. The app holds a GitHub token that can only dispatch this workflow.

## AI involvement

Claude Code proposed this host and listed the options. The human accepted it on 2026-10-29.

## Evidence

- [arch.md § Stock worker](../arch.md#42-stock-worker-decided)
