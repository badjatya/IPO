# Plan review: 014-stock-fetchers

## Round 1 (2026-10-29)

**Verdict:** Changes requested

**Read:** plan.md, AGENTS.md, docs/tasks/README.md, ROADMAP.md § 014 and D09, data-sources.md § NSE stock data, arch.md § 4.2, tech.md (repository layout, Gemini row), db.md §§ `stock_quotes`, `quarterly_results`, `shareholding`, `announcements`, `ipo_agent/nse.py`, `.claude/deepseek/deepseek.py` (the `run` tool's limits), and the fixtures `results_standalone.json`, `results_filings.json`, `shareholding.json`, `announcements.json`, `pledges.json`.

The plan is well scoped: fixtures first, one module per source, failure isolation, the pledge share computed in code, and FII/DII and consolidated results kept as gaps rather than guessed. Its two errors are in the numbers: the EBITDA formula and how standalone results are joined to their filings. Its weak points are the unit gate and who runs the live probe.

### Decisions (human)

Asked on 2026-10-29 with the plan's recommendation first; the human chose:

- **D09, location:** option A, a new top-level package `stock_worker/`, importing `ipo_agent.net` for HTTP.
- **D09, dependencies:** standard library only in 014. The package may later take pinned third-party packages (the Postgres driver in 018, the Gemini SDK in 020) through its own requirements file, each named in that task's plan. ADR-0026 also records that the worker's Gemini client is Python and the app's is TypeScript, so tech.md's "one module shared by the app and the worker" becomes one module per side.
- **EBITDA:** operating EBITDA, excluding other income: revenue − (total expenses − finance costs − depreciation).

### Changes requested

1. **Write the D09 decision into the plan.** Replace "recommendation" and "the steps assume the recommended option" with the decision above. ADR-0026 (status Proposed) covers both halves: the location and the dependency rule, including the Python/TypeScript Gemini split. Remove D09 from "Decisions needed". Under Doc updates, the roadmap ticks D09 once the human accepts ADR-0026.

2. **EBITDA is wrong: the formula leaves finance costs subtracted.** In `results_standalone.json` row 1, `re_total_inc` 13,147,400 − `re_oth_tot_exp` 11,987,700 = 1,159,700, which is `re_pro_loss_bef_tax`. So `re_oth_tot_exp` is total expenses *including* finance costs (`re_int_new` 237,100) and depreciation (`re_depr_und_exp` 445,900). The plan's formula gives 1,605,600 (PBT + depreciation), which is not EBITDA under any definition. Per the human's decision, use operating EBITDA, excluding other income: `revenue − (total expenses − finance costs − depreciation)`, from `re_net_sale`, `re_oth_tot_exp`, `re_int_new` and `re_depr_und_exp`. If any of the four is missing, EBITDA is `None` (a stated `0` is a value, not a missing field). The test pins the fixture row: 1,521,300 lakh → `ebitda_cr` `Decimal("15213.00")`. Write the formula and the field names in `data-sources.md`, with a one-line note in db.md under `ebitda_cr`.

3. **The unit is a property of the endpoint: confirm it once, don't gate every fetch on note text.** The evidence is good: `re_net_sale` 12,826,000 against "Net Revenue is Rs 128,260 crore" in `re_desc_note_seg`. But a per-fetch regex gate would leave `unit: None` for almost every company, because few write a "Rs N crore" note. 018 would then store no results for most stocks. Instead:
   - Record ₹ lakh in `data-sources.md` as the endpoint's unit, with this evidence (RELIANCE Q3 FY25, the note text).
   - Keep one test that pins the evidence on the fixture.
   - Convert to ₹ crore in the parser.
   - Name the record's keys exactly as the db.md columns (`revenue_cr`, `other_income_cr`, `expenses_cr`, `ebitda_cr`, `pat_cr`).

   A record field called `revenue` that holds lakh, headed for a column called `revenue_cr`, is a trap for 018. EPS is in ₹ per share and is not converted; add a test that says so. The same "keys are the db.md column names" rule applies to the other records where a column exists.

4. **Make the results/filings join explicit.** `results_filings.json` has two rows per quarter, one `Non-Consolidated` and one `Consolidated` (31-Dec-2024: 20:20 and 20:15). The plan takes `consolidated` "from the filings JSON", which can label standalone numbers consolidated, or attach the consolidated filing's link and time to standalone figures. The comparison rows are standalone (the endpoint ignores `consolidated=true`, and the row's own notes say "Standalone Financial Results"). So:
   - `consolidated` is always `False` for them.
   - `filed_at` and `source_url` come only from the filings row with the same `toDate` and `consolidated == "Non-Consolidated"`. With no such row, both are `None`.
   - The test asserts that the 31-Dec-2024 standalone record gets the 16-Jan-2025 20:20 time, not 20:15.
   - In the consolidated gap note in `data-sources.md`, record that the `Consolidated` filings rows carry an XBRL link, a likely consolidated source for a later task.

5. **Say who runs the live probe, and when; DeepSeek's build step doesn't.** AGENTS.md keeps builds and tests off live sites. The driver's `run` tool would accept `python3 stock_worker/probe.py`, so the plan has to say so explicitly. Split step 6 as follows:
   - **6a (build):** the probe module, its fixed candidate list, the call budget and `--dry-run`, with tests. No live call. The build summary asks the human to run `python3 -m stock_worker.probe` once.
   - **6b (after the human's run):** in the next DeepSeek step, write the quote parser against the captured `quote.json`, the fixture manifest entry, and the `data-sources.md` quote and consolidated rows. If nothing answered, record every candidate's error and make `fetch_quote` raise `SourceError`.

   Also add the **NextApi** variant to the candidates, because the roadmap names it. If its URL can't be pinned without a live call, say how the probe finds it (for example, from the stock page it already fetches as the prime) or record it as unprobed with the reason. Adjust `MAX_CALLS` to the final list.

6. **Prime NSE once per client, and count calls that way.** `ipo_agent/nse.py` primes the cookie jar once per client (`_primed`). The fetchers reuse that pattern, or `NSE` itself, rather than priming per source. "One GET per source" then means one API call per source plus one shared prime per run. The `fetch_all` test asserts the total number of calls against a `FakeClient`.

7. **Records hold `Decimal`, which stdlib `json` can't serialise.** Drop "JSON-serialisable" from the record definition, or say how the dev CLI prints them (for example, `default=str`). State the rounding for `promoter_pledged_pct` (`ROUND_HALF_UP` to 2 dp).

### Notes

- The pledge numbers check out: 21,723,685 / 974,234,554 × 100 = 2.23, and `percPromoterHolding` needs `"    71.97"` stripped.
- `other_pct ← employeeTrusts` follows data-sources.md's mapping. Fine as is; it isn't a new decision.
- `period_start` and `audited` aren't db.md columns. Keeping them in the record is fine if the module docstring lists them as extras.
