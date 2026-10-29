# ADR-0012: Research, not advice, for listed stocks

- **Status:** Accepted
- **Decided:** 2026-10-29 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

The watchlist covers listed stocks. In India, buy or sell recommendations on securities are regulated investment research. The product is for an internal hackathon and for the owner's own use, not a registered research service.

## Options

| Option | For | Against |
| --- | --- | --- |
| Buy, hold and sell calls on stocks | Feels decisive | Regulated activity; overconfident on a few data points |
| **Summaries, flags and explanations, no buy or sell** | Useful and within bounds | Users make the final call themselves |

## Decision

For listed stocks the app summarises results, triages announcements and flags shareholding and pledge changes. It doesn't say buy or sell. IPO verdicts stay, labelled as research. Every page and email says "not investment advice".

## Consequences

- Prompts for stock tasks forbid buy and sell wording.
- The disclaimer is part of the renderer and the app layout, not left to the model.

## AI involvement

Claude Code proposed this on 2026-10-29. The human accepted it the same day, without changes.

## Evidence

- [plan.md § Scope](../plan.md#scope)

