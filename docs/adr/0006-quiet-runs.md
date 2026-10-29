# ADR-0006: Quiet runs skip Claude

- **Status:** Accepted
- **Decided:** 2026-10-14 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

Many runs have nothing to judge: no IPO is open or closing, and nothing needs research. Asking Claude for a verdict on those runs spends tokens to repeat yesterday's call.

## Options

| Option | For | Against |
| --- | --- | --- |
| Always ask Claude | Simple | Pays for judgement when nothing changed |
| Skip the run entirely | Cheapest | No email; numbers and listings go unrecorded |
| **Python carries the last calls forward over fresh numbers** | Brief still goes out with fresh numbers; no Claude judgement | Python must decide reliably when a run is quiet |

## Decision

`quiet.py` scores new listings, then checks whether anything is open, closing or needs research. If nothing is, it writes the report from the previous run's calls, marks it `"generated": "quiet"` and renders the email. Claude only sends and commits.

## Consequences

- The reasons a run is *not* quiet are printed, so Claude knows why it's needed.
- If `quiet` errors, the routine treats the run as not quiet.

## AI involvement

Built in Claude Code (Opus 5.5) sessions; the commit carries a Claude co-author trailer. Who proposed what in those sessions was not recorded at the time. This ADR was written afterwards, from the commit and the code.

## Evidence

- Commit `1377e86`
- `ipo_agent/quiet.py`; `ROUTINE.md` step 1

