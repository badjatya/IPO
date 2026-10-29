# ADR-0003: Research runs on a schedule, not on request

- **Status:** Accepted for IPO research. Stock analysis on request is handled separately, by the Gemini stock worker ([ADR-0017](0017-gemini-for-stocks-claude-for-ipos.md))
- **Decided:** 2026-10-12 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

IPO numbers move during market hours: GMP overnight, subscription during bidding (10:00–17:00 IST). Investors decide before bidding opens or before it closes. Reading an RHP takes minutes and costs tokens.

## Options

| Option | For | Against |
| --- | --- | --- |
| On request: research when a user opens a page | Always fresh | Users wait minutes; cost grows with page views; the same IPO is analysed many times |
| **Scheduled routine twice a day** | Pages are instant; cost tied to new IPOs, not traffic; one place to look after | Numbers are up to a few hours old |

## Decision

A Claude Code routine runs on weekdays at 09:07 IST (before bidding opens) and 19:07 IST (after it closes). The app only shows stored results. The only AI call on request is Ask.

## Consequences

- A brief is never more than one session old. For IPO decisions this is enough; the app is not a trading terminal.
- Watchlist research follows the same schedule.
- An optional 15:07 run is documented for closing days.

## AI involvement

Built in Claude Code (Opus 5.5) sessions; the commit carries a Claude co-author trailer. Who proposed what in those sessions was not recorded at the time. This ADR was written afterwards, from the commit and the code. Per the project notes, the routine was enabled on 2026-10-12 after two clean test runs.

## Evidence

- `SETUP.md` § Routine
- Routine commits since 2026-10-12, twice per weekday (authored by `Claude`)

