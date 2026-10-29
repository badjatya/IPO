# ADR-0013: Research is per stock and shared across users

- **Status:** Accepted. Since [ADR-0017](0017-gemini-for-stocks-claude-for-ipos.md), every request counts against the quota, even when the saved analysis is served
- **Decided:** 2026-10-29 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

The app is multi-user. If research were per user, Claude's cost would grow with every sign-up, and two users watching the same stock could see different summaries.

## Options

| Option | For | Against |
| --- | --- | --- |
| Per-user research | Can be personalised | Cost grows with users; inconsistent text |
| **One summary per filing, shared by everyone who watches the stock** | Cost grows with distinct stocks and new filings only; one source of truth | No per-user tailoring of summaries |

## Decision

Analysis is saved per stock, not per user. The first time a stock needs analysis, the stock worker does it with Gemini (on request, [ADR-0017](0017-gemini-for-stocks-claude-for-ipos.md)) and the result is stored in the database. When any other user asks for that stock, they get the stored analysis from the database, and it is not done again. New analysis happens only when the stock files something new (a result, an announcement, a shareholding change), and that new piece is also done once and shared.

In the human's words: "we save the analysis and when a different user wants the analysis on that stock we give them from db and not have to do it again".

## Consequences

- The stock worker reads only the distinct watched symbols, with no user data.
- Alerts belong to stocks and are shown in the app to everyone watching that stock.
- Personal features (Ask history) stay per user.

## AI involvement

Claude Code proposed this on 2026-10-29. The human accepted it the same day, and restated it as: save the analysis, and serve it from the database to every later user instead of redoing it.

## Evidence

- [db.md](../db.md) (`alerts`, `watched_symbols`)

