# ADR-0027: Alert thresholds and severities live in code; FII/DII parsing is a separate task

- **Status:** Proposed
- **Decided:** 2026-10-30 · **Recorded:** 2026-10-30
- **Deciders:** Vijay · **Drafted with:** DeepSeek (deepseek-v4-flash-0731, OpenRouter) in task 016; reviewed by Claude Code

## Context

Roadmap decision D10: the thresholds and severities behind the stock worker's change-detection alerts, and where they live. Task 016 builds the six pure alert rules over the 014 fetchers' record shapes; the worker (018) will insert the alert rows, and the app shows them on watchlists and stock pages. The FII/DII split exists only in the XBRL filing ([data-sources.md § NSE stock data](../data-sources.md#nse-stock-data)), so without a parser the `fii_move`/`dii_move` rules can never fire on real data.

## Options

| Option | For | Against |
| --- | --- | --- |
| **A — thresholds and severities in code** (`DEFAULT_THRESHOLDS` and the `SEVERITIES` map in `stock_worker/alerts.py`, still passable as parameters) | Analytic parameters live with the code that uses them; one-line tuning, no migration; AGENTS.md rule 6 ("quotas and caps from `settings`") is about the user-facing limits the admin page edits | A code change plus review to tune |
| B — `settings` rows | Tunable without a deploy | `settings` is the app's cap store; worker thresholds are not user-facing; 016 would need a seed and a settings read before any alert could fire |

The FII/DII parsing question — here or in a separate task:

| Option | For | Against |
| --- | --- | --- |
| **A — separate task 027 ("XBRL shareholding parsing")** | 016 ships the rules forward-compatible and tested on synthetic records; 027 (depends on 014 and 016) parses the XBRL filings recorded as `source_url` by 014 against its own fixtures | One more task before `fii_move`/`dii_move` fire on real data |
| B — parse in 016 | Fewer hand-offs | 016 is already the contract, four change rules plus `results` and `announcement`, and the orchestrator; XBRL parsing needs its own fixture set and tests |

## Decision

D10, settled by the human at 016's round-1 plan review ([plan-review § Decisions](../tasks/016-alert-rules/plan-review.md)), all four parts:

- **Thresholds** (quarter-on-quarter, percentage points, "a move at least this size fires"): `pledge_up` rise ≥ 1.00; `promoter_down` fall ≥ 2.00; `fii_move`/`dii_move` absolute move ≥ 1.00.
- **Severities**: `results` → `info`; `announcement`, `fii_move`, `dii_move` → `watch`; `pledge_up`, `promoter_down` → `warning`.
- **Where they live**: code. `DEFAULT_THRESHOLDS` and the `SEVERITIES` map in `stock_worker/alerts.py`, still passable as parameters (`thresholds=`). No `settings` rows.
- **FII/DII scoping**: a separate task 027 does the XBRL parsing. 016 ships `fii_move`/`dii_move` forward-compatible, tested on synthetic records; the rules stay silent on real data ("missing data, no alert") until 027 feeds real `fii_pct`/`dii_pct` values.

This ADR also records that `promoter_pledged_pct` is a **share of the promoter's holding** — not of total equity — so 020's explanation prompt can state it correctly. (014 computes it as shares pledged ÷ promoter holding × 100, half-up to 2 dp, never NSE's `percSharesPledged`.)

## Consequences

- Tuning the thresholds is a one-line change in `DEFAULT_THRESHOLDS`; the rule code is identical and alert rows already written are untouched. No migration.
- No `settings` rows exist for thresholds or severities; 018 and 020 read none.
- `fii_move`/`dii_move` stay silent until task 027 lands — that silence is a pinned test in 016, never an estimate.
- Task 027's roadmap entry (added at 016) names 014 and 016 as dependencies and feeds `fii_pct`/`dii_pct` from the shareholding XBRL recorded as `source_url` by 014.

## AI involvement

The plan's draft carried these as a recommendation under "Decisions needed" with the human to settle them at plan review. The human settled all four parts at 016's round-1 review, each matching the recommended option; DeepSeek wrote the settled values into the plan and this ADR. The `promoter_pledged_pct` share-of-promoter note came from the reviewer's plan-review note.

## Evidence

- `stock_worker/alerts.py` and `tests/test_stock_alerts.py` (task 016)
- [docs/tasks/016-alert-rules/plan-review.md § Decisions](../tasks/016-alert-rules/plan-review.md)
- [docs/db.md § alerts](../db.md#alerts) (severity map and `source_id` forms), [docs/data-sources.md § NSE stock data](../data-sources.md#nse-stock-data) (XBRL gap and task 027)