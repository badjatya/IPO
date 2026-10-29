# ADR-0007: Listing scorecard is the eval of the AI's calls

- **Status:** Accepted
- **Decided:** 2026-10-14 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

An AI that makes calls needs a way to show whether they're any good. IPOs give a clean outcome within days: the listing price.

## Options

| Option | For | Against |
| --- | --- | --- |
| No measurement | No work | No way to know if the calls help |
| Manual review of past emails | Flexible | Subjective; doesn't scale |
| **Automatic scorecard on listing day** | Objective; compares the call with GMP and subscription as signals | Few data points at first |

## Decision

On each run, `outcomes.py` records every newly listed IPO: listing price, day-1 close, GMP the night before, our last call before bids closed, final subscription and anchor grade. It reports average gains by call and how each signal tracked listing gains.

## Consequences

- The scorecard is the standing eval for any change to `ROUTINE.md`.
- It warns itself that correlations mean little under about 15 IPOs.
- The track record page in the app is built on it.

## AI involvement

Built in Claude Code (Opus 5.5) sessions; the commit carries a Claude co-author trailer. Who proposed what in those sessions was not recorded at the time. This ADR was written afterwards, from the commit and the code.

## Evidence

- Commit `d8c4840`
- `ipo_agent/outcomes.py`, `data/outcomes.json` (8 listings by 2026-10-29)

