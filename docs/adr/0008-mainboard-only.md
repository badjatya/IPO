# ADR-0008: Mainboard IPOs only; SME out of scope

- **Status:** Accepted
- **Decided:** 2026-10-12, reaffirmed 2026-10-29 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

SME IPOs outnumber mainboard issues several times over. They have different minimum applications and allotment rules, prospectuses filed with the exchange rather than SEBI, and a GMP that is easier to manipulate.

## Options

| Option | For | Against |
| --- | --- | --- |
| Mainboard and SME at full depth | Widest coverage | Several times the token cost; new rules and sources |
| SME with a quick screen | Coverage at lower cost | Still new rules and sources; competes with the watchlist for the month |
| **Mainboard only for now** | Focus on depth and the watchlist | SME investors not served |

## Decision

Mainboard only. SME rows from Investorgain and the SME series from NSE are filtered out.

## Consequences

- SME data already flows in and is dropped at the filter, so adding SME later starts from a working base.
- It would need SME allotment rules, an exchange RHP source and a cheaper screening step.

## AI involvement

The original mainboard-only scope was set when the project started (2026-10-12). On 2026-10-29 Claude Code proposed adding SME with a quick screen. The human answered "skip sme for now".

## Evidence

- `ipo_agent/investorgain.py` (board tag), `ipo_agent/nse.py` (`MAINBOARD_SERIES`)
- [AI journal 2026-10-29](../plan.md#ai-journal)

