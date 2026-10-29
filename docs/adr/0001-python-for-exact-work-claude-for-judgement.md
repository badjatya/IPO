# ADR-0001: Python for exact work, Claude for judgement

- **Status:** Accepted
- **Decided:** 2026-10-12 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

An IPO brief mixes two kinds of work:

- **Exact work.** Prices, lots, subscription by category, allotment odds and dates must be right to the rupee.
- **Judgement.** What does the business do, are the financials healthy, is the valuation fair, how good is the anchor book?

A language model is good at the second and unreliable at the first.

## Options

| Option | For | Against |
| --- | --- | --- |
| Claude does everything (fetches, reads, computes, writes) | Fewest moving parts | Arithmetic and parsing errors; numbers can't be checked; every run costs more tokens |
| Python only, rules-based verdicts | Exact and cheap | Can't read a 400-page RHP or grade an anchor book |
| **Python for numbers, Claude for judgement** | Each does what it's good at; numbers are reproducible | Two layers, and a contract (JSON schemas) between them |

## Decision

Python fetches the data, computes every number and renders the output. Claude reads documents, researches and writes the analysis and verdicts. Claude quotes numbers that Python computed or that appear in the RHP; it never computes them.

## Consequences

- Every number in a brief can be reproduced by rerunning a Python command.
- The schemas at the top of `cards.py` and `email_render.py` are the contract, so a change to either needs both sides updated.
- The same split carries over to the watchlist: Python computes changes and alert thresholds; Claude explains them.

## AI involvement

Built in Claude Code (Opus 5.5) sessions; the commit carries a Claude co-author trailer. Who proposed what in those sessions was not recorded at the time. This ADR was written afterwards, from the commit and the code.

## Evidence

- Commit `3ae0266` (prototype: fetcher, RHP extractor, routine instructions)
- [README.md](../../README.md) ("The work is split in two")
- `ROUTINE.md`: "Never invent numbers"

