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

## Round 2 (2026-10-30)

**Verdict:** Changes requested

**Read:** plan.md (revision 1), docs/arch.md § 4.2 Mode 1, the RELIANCE `shareholding.json` fixture parsed through `shareholding.parse`

**Round 1 items:**

| # | Item | Checked |
| --- | --- | --- |
| 1 | Only what's new | `fetched`/`stored` split; first sight raises nothing; a change rule pairs the new quarter with the latest earlier quarter on record; 018's contract warns about an incomplete `stored` set. Done, apart from announcements (item 6 below) |
| 2 | Pledge path | Option (a): the orchestrator joins pledges to shareholding on `quarter_end`, both one-sided cases are tested, and ADANIENT is its own case. Done |
| 3 | Dedupe rule | Per-series timestamp, `None` sorts older, and an order-independent tie-break, all tested. Done |
| 4 | Decisions written in | Approach § 5 table, steps 1 and 6, ADR-0027 Proposed, `settings` contingencies dropped. Done |
| 5 | `source_id` | Each form is in db.md and pinned per kind. Done |

### Changes requested

6. **The `announcement` rule can never fire.**
   - **The order of steps.** arch.md § 4.2 Mode 1 computes alert candidates at step 3 (Python). It rates importance at step 4 (Gemini). So when 018 calls `compute_alerts`, every announcement that's new in this run still has `importance = None`.
   - **The rule blocks the only other path.** Approach § 3 also says an announcement already on record "never re-alerts, even when 020 sets its importance afterwards". So there's no other route either: the rule is dead by construction, not just "silent until 020".
   - **The tests hide it.** They feed `importance` by hand, so they'd pass while the rule is unreachable in production.
   - **Change.** Make the rule reachable once an announcement has been rated, and state who calls it. The simplest fit for the arch.md order:
     - `announcement_alert(symbol, record)` stays pure.
     - It's called for each announcement the run's rating step has just rated: 020's step 4, after Gemini writes `importance`. That's still one alert per `exchange_ref`, guarded by the dedupe key.
     - `compute_alerts` handles only the change rules and `results`.
     - § 6's contract, the `ai.md` Alert-explanation line and the roadmap note for **020** say this.
   - **Or another route.** If you'd rather have `compute_alerts` take announcements whose importance has just been set, the newness test has to change too, and you need to say what triggers the second call.
   - **Either way:** add a test that a fetched announcement with `importance = None`, rated later, raises exactly one alert through whichever path you choose.

7. **Pin exact outcomes in step 5(b).**
   - **The gap.** "At most one change alert from the new shareholding quarter pair" would pass with zero or one alerts, so it doesn't test the rule.
   - **What the fixture gives.** Parsed through `shareholding.parse`, its last two quarters are 2026-06-30 at 50.48% and 2026-09-30 at 50.44% promoter holding, with FII/DII `None`. That's a 0.04 pp fall, so case (b) should raise exactly **one** `results` alert and **zero** change alerts.
   - **Change.** Assert those exact counts and keys. Put a threshold-crossing pair in a synthetic case, not the fixture.

### Notes

- **Leave § 6's line about the incomplete `stored` set for 018.** It's the right warning. That task's tests should cover it.

## Round 3 (2026-10-30)

**Verdict:** Approved

**Read:** plan.md (revision 2), the RELIANCE results fixture parsed through `results.parse_results` (periods 2023-12-31 → 2024-12-31)

**Round 2 items:**

| # | Item | Checked |
| --- | --- | --- |
| 6 | Announcement rule reachable | `announcement_alert` stays pure and isn't called by `compute_alerts`. 020's rating step calls it after `importance` is written. § 6, the ai.md line, step 6 and the roadmap note for 020 all say so, and a "rated later" test pins the flow. Done |
| 7 | Exact outcomes in 5(b) | One alert, `RELIANCE:results:2024-12-31`, and zero change alerts (a 0.04 pp promoter fall). The threshold-crossing pair is in step 4's synthetic tests. I checked both fixture values against the parsers. Done |

No setup step or package is needed. The human settled D10 and the FII/DII scoping in round 1, and nothing is left open.

### Notes

- **Name the rating set in the 020 note.** The re-rate risk row relies on 020 rating only the run's new announcements. When the roadmap note for 020 goes in, say so there too, so 020's plan keeps it.
