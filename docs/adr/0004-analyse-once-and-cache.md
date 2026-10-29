# ADR-0004: Analyse each IPO once and cache it

- **Status:** Accepted
- **Decided:** 2026-10-14 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

The deep analysis (`analysis/<key>.md`) was written once per IPO from the start. Before `f0be1a3`, though, each run's report held a full entry for every IPO: summary, financials, quota, positives, red flags and anchor book. Claude rewrote them every run, although those facts don't change between runs. Only the numbers and the call do.

## Options

| Option | For | Against |
| --- | --- | --- |
| Re-analyse every run | Always considers everything | Same RHP read many times; tokens wasted; wording drifts between runs |
| **Cache the RHP text, the analysis and a card per IPO; runs write only what changed** | Analysis paid once; stable wording; small run output | Needs rules for when a cache is stale |

## Decision

The extracted RHP text, the deep analysis and a facts card are cached in `analysis/` per IPO. Python flags `needs_analysis`, `needs_card` and `needs_anchor_update` only when something is missing. Each run's report holds only the fields that changed, merged over the card.

## Consequences

- Cards hold facts only, with no GMP and no "today", so they stay true for days.
- A web-search stub card is replaced once the RHP analysis exists.
- The same "once, then reuse" rule applies to stock filings ([ADR-0013](0013-shared-per-stock-research.md)).

## AI involvement

Built in Claude Code (Opus 5.5) sessions; the commit carries a Claude co-author trailer. Who proposed what in those sessions was not recorded at the time. This ADR was written afterwards, from the commit and the code.

## Evidence

- Commit `f0be1a3` (cache per-IPO email cards)
- `ipo_agent/cards.py`, `ROUTINE.md` "Cache, don't redo"

