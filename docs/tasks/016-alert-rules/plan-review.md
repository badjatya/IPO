# Plan review: 016-alert-rules

## Round 1 (2026-10-30)

**Verdict:** Changes requested

**Read:** plan.md, AGENTS.md, docs/tasks/README.md § Reviewer guide, ROADMAP.md § 016, docs/db.md (§ shareholding, § announcements, § alerts, enums, read paths), docs/plan.md § Watchlist signals, docs/arch.md § 4.2 and § 9, ADR-0001, ADR-0026, `stock_worker/results.py`, `shareholding.py`, `pledges.py`, `announcements.py`

### Decisions (human)

Settled by the human at this review, 2026-10-30. Each one is the plan's recommended option.

- **D10, thresholds** (quarter-on-quarter, percentage points; a move at least this size fires):
  - `pledge_up`: a rise ≥ 1.00 pp
  - `promoter_down`: a fall ≥ 2.00 pp
  - `fii_move` and `dii_move`: an absolute move ≥ 1.00 pp
- **D10, severities:**
  - `results` → `info`
  - `announcement`, `fii_move`, `dii_move` → `watch`
  - `pledge_up`, `promoter_down` → `warning`
- **D10, where they live:** in code. `DEFAULT_THRESHOLDS` and the severity map go in `stock_worker/alerts.py`, and callers can still pass thresholds as parameters. No `settings` rows.
- **FII/DII scoping:** a separate task 027 does the XBRL shareholding parsing. 016 ships `fii_move`/`dii_move` forward-compatible, tested on synthetic records.

### Changes requested

1. **Alert only on what's new, not on the stored history.**
   - **The gap.** `compute_alerts` fires a change alert for every consecutive pair in its input, and a `results` alert for every quarter but the first. A stock's first worker run passes its full history: 20 shareholding quarters and 5 results quarters in the RELIANCE fixture. That run raises every historical threshold crossing back to 2022, and four `results` alerts (step 5 asserts exactly that).
   - **Why it matters.** Each of those rows gets `created_at` = insert time. So the watchlist's "latest alert per stock" (db.md § Read paths) shows a 2022 quarter as news, and 020 spends a Gemini call explaining each one. That breaks plan.md's "AI only on what changed". It also contradicts the plan's own line in Approach § 3 that "a fresh stock's history backfill stays quiet".
   - **The opposite failure.** If 018 passes only the newly fetched quarter, there's no pair, so nothing ever fires. The function's behaviour depends on a calling convention the plan doesn't state.
   - **Change.** Give `compute_alerts` both what's already stored and what was just fetched, for example `stored=` and `fetched=` record sets per series, or a per-series "latest period already on record". An alert fires only for a record that's new against what's stored. A change rule compares the new quarter with the latest quarter on record before it, which may come from the stored set.
   - **First sight.** For a stock with nothing stored, the whole fetched history is the baseline and raises no alerts. If you think the latest pair should still fire on first sight, say so with a reason. Either way, pin it in a test.
   - **Then:** update step 4's signature and tests, step 5's expected counts, the "backfill burst" risk row, and § 6's contract for 018. `existing_keys` can stay as the second guard.

2. **Pledge data has no path into `compute_alerts`.**
   - **The gap.** `pledge_up` reads `promoter_pledged_pct`, but 014's `shareholding.parse` doesn't produce that field. Only `pledges.parse` does, in separate records keyed by `quarter_end`, each carrying `company` and no symbol. `compute_alerts` takes no pledge records, so on 014's real output `pledge_up` can never fire.
   - **Step 5 doesn't fit.** It parses `pledges.json` without a way to pass it in. The fixture is also an ADANIENT row next to RELIANCE shareholding, so it can't be joined to them anyway.
   - **Change.** Pick one and state it:
     - (a) `compute_alerts` takes the pledge records for the symbol (already resolved by 015/018) and joins them to the shareholding quarters by `quarter_end` itself, with tests for the join, including a quarter that has shareholding but no pledge row (no `pledge_up`).
     - (b) The contract says the caller passes shareholding records that already carry `promoter_pledged_pct`, and `pledges.parse` output is never passed directly.
   - **Recommendation:** (a), because the join is pure and can be tested here. Under either option, make step 5 run the pledge fixture as its own single-symbol case and drop the cross-symbol mix.

3. **Say what "keeping the latest" means.** Step 4 dedupes each input by natural key "keeping the latest", but doesn't say latest by what.
   - **Name the field per series.** `filed_at` for results and shareholding, `disclosed_at` for pledges, `announced_at` for announcements.
   - **Name the tie-break,** including when the timestamp is `None` on one or both sides, so the output stays deterministic.
   - **Test it:** two records for the same quarter with different `filed_at` keep the later one.

4. **Write the decisions into the plan.** Replace the recommendations with the settled values above, in Approach § 5, steps 1 and 6, and the ADR line under Doc updates.
   - **Decisions needed:** remove D10 and the FII/DII choice, since nothing is left open.
   - **ADR-0027:** still status **Proposed**, recording the four decisions.
   - **Doc updates:** drop the `settings` contingencies (the 007/013 notes and the db.md seed-rows line).
   - **Roadmap:** keep the changes for `main`: tick D10 once ADR-0027 is accepted, add task 027, and add the 018 note.

5. **Document what `source_id` holds.** db.md has `source_table`/`source_id` as text, "the row that triggered it". The plan uses natural keys: `quarter_end` for `shareholding` and `period_end` for `quarterly_results`, both scoped by the alert's `symbol`. For `announcements` it uses `exchange_ref` (that table's PK is a `bigint` id that the pure module never sees).
   - **The reason.** That's the right call for a pure module, and it keeps alerts rebuildable from git (rule 9). But a reader of db.md would take `source_id` to be the row's PK.
   - **Change.** Add one line under db.md § alerts with the `source_id` form for each `source_table`, and pin each one in a test.

### Notes

- **Thresholds in code are fine under rule 6.** They're analytic parameters, not user-facing quotas or caps. The `settings` table holds the limits that the admin page edits.
- **Pledge title wording.** `promoter_pledged_pct` is a share of the promoter holding, not of total equity. db.md's example "Promoter pledge up from 4% to 11%" leaves that out. Keeping the db.md wording is fine, but say in the ADR what the percentage is a share of, so 020's explanation prompt can state it correctly.
- **Results.** The plan already stays within one consolidation series, and its `results` title uses only stated fields with "not available" for gaps. Both are good. Keep them through the item 1 rework.
- **Step 7** lists the `.claude/hooks` and `.claude/deepseek` suites as well as `tests/`. Good. Paste all three.
