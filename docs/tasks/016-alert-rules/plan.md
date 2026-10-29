---
task: 016-alert-rules
status: plan-review
branch: task/016-alert-rules
assigned_by: Vijay
planner: DeepSeek deepseek-v4-flash-0731 (OpenRouter)
reviewer: Claude Code
---

# 016: Change detection and alert rules

## Task

> Task 016 from docs/tasks/ROADMAP.md:
>
> ### 016 · Change detection and alert rules
>
> | | |
> | --- | --- |
> | Slug | `016-alert-rules` |
> | Status | **Ready** |
> | Depends on | 014, D10 |
> | Owner | DeepSeek plans and builds |
> | Milestone | M2 |
>
> Pure Python functions that compare a stock's latest filings with earlier ones, and raise alerts (pledge up, promoter holding down, FII or DII move, new results, important announcement) using the thresholds from D10. Each alert's title and numbers come from Python, with a `dedupe_key`.
>
> - **Done when:** every rule has tests, including the first quarter on record and missing data (no alert); the same input never raises the same alert twice.
> - **D10 gates approval, not planning:** the plan lays out the thresholds and severities with a recommendation under "Decisions needed", and the human settles D10 at plan review.
> - **From 014:** the shareholding fetcher returns `fii_pct` and `dii_pct` as `None`, because the FII/DII split exists only in the XBRL filing. The `fii_move` and `dii_move` rules can't fire until something parses that XBRL: this task, or a separate task the plan proposes. Results are standalone only; never compare them with consolidated figures.
> - **Read:** [plan.md § Watchlist signals](../plan.md#watchlist-signals), [db.md § alerts and § shareholding](../db.md#alerts).
> - **Start:** `/run-task 016`

## Goal and scope

- **In scope:**
  - A pure, standard-library module `stock_worker/alerts.py` with the six alert rules — `pledge_up`, `promoter_down`, `fii_move`, `dii_move`, `results`, `announcement` — as deterministic functions over the record shapes the 014 fetchers already produce (plain dicts keyed by the `db.md` column names). No database, no AI, no network.
  - Each rule returns an **alert record** keyed exactly as the `db.md` `alerts` columns: `kind`, `severity`, `title`, `detail` (always `None` here; Gemini fills it in 020), `dedupe_key`, `source_table`, `source_id`. Titles and every number in them come from Python, from stated fields only; a missing value renders as "not available", never an estimate ([AGENTS.md](../../AGENTS.md) rule 1).
  - A `compute_alerts()` orchestrator: sorts and pairs consecutive quarter records, applies the change rules, applies the `results` and `announcement` rules, and skips any alert whose `dedupe_key` is already in a caller-supplied set (`existing_keys`), so the same input never raises the same alert twice. Deterministic output order.
  - Thresholds and severities per **D10** ([Decisions needed](#decisions-needed)): the rules take thresholds as parameters and carry code-held `DEFAULT_THRESHOLDS`; the severity map is code-held. The design is the same whichever way D10 lands (parameters + defaults), so only the docs differ.
  - Tests (`tests/test_stock_alerts.py`) for every rule: first quarter on record (no alert), missing data (no alert), threshold boundary, exact titles, dedupe keys (the `db.md` example `HDFCBANK:pledge_up:2026-09-30`), idempotence (same input twice → same output; `existing_keys` → nothing re-emitted), and an integration test that runs the 014 parsers over the saved `tests/fixtures/nse_stock/` fixtures end to end. No live sites, no AI APIs.
  - Doc updates: `db.md`, `data-sources.md`, `arch.md`, `tech.md`, `ai.md`, and a new ADR-0027 (status **Proposed**) recording D10 as the human settles it. Roadmap changes for `main` are listed under "Doc updates", including the **new task 027** this plan proposes for XBRL parsing (FII/DII).
- **Out of scope:**
  - Writing any database row, migration, seed or `settings` row — the `alerts` table's schema is built in 007 and its rows are written by the worker in 018. No Postgres driver.
  - Writing `data/stocks/<SYMBOL>/…` files — that is 018's persistence.
  - XBRL/PDF fetching and parsing. `fii_pct`/`dii_pct` stay missing (014 returns `None`), the `fii_move`/`dii_move` rules stay silent until the proposed task 027 (or the human's fold-in choice) feeds real values; 016's rules are forward-compatible, exactly as `shareholding.py` is.
  - Rating announcement importance (`importance`) and writing `alerts.detail` — those are Gemini's jobs in 020, with their `ai_*` provenance there. 016's `announcement` rule consumes the `importance` value, and 016 writes no `ai_*` column.
  - Name→symbol resolution for pledge rows (which carry only `comName`; that is 015/018's job) and the quote/consolidated-results gaps (018's records).
  - Anything in `web/`, any GitHub Actions workflow, any new package or dependency. Standard library only, like 014.
  - Editing protected paths: `analysis/`, `reports/`, `data/`, `ROUTINE.md`, `config/delivery.json`, `CLAUDE.md`, `.claude/`, `AGENTS.md`, `ROADMAP.md`.

## Context read

| Doc / code | What matters for this plan |
| --- | --- |
| [ROADMAP.md](../ROADMAP.md) § 016, and the decisions/setup tables | The task: six rules, titles and numbers from Python, a `dedupe_key`, tests for the first quarter on record and missing data, idempotence. It depends on 014 (done) and **D10** (open; gates approval). No `H..` setup step gates 016 — H02 (Actions `DATABASE_URL`) belongs to 018. 014's map note says the FII/DII gap may grow 016's scope or spawn a follow-up task; this plan proposes the follow-up (task 027). |
| [plan.md § Watchlist signals](../plan.md#watchlist-signals) | What the alerts serve: quarterly results (Python builds trends, Gemini summarises), announcements digest (Gemini drops routine filings and explains the ones that matter), shareholding and pledges (Python flags changes past a threshold, Gemini explains them). "Python for exact work, AI for judgement": alerts are Python's job, explanations Gemini's. |
| [db.md](../db.md) | The contract: the `alerts` table (`kind` ∈ `results, announcement, pledge_up, promoter_down, fii_move, dii_move`; `severity` ∈ `info, watch, warning`; `title` with numbers from Python; `detail` = Gemini's explanation; unique `dedupe_key` like `HDFCBANK:pledge_up:2026-09-30`; `source_table`/`source_id` for the triggering row), the `shareholding` note that quarter-on-quarter changes come from a SQL window "Python's alert rules use the same comparison", `quarterly_results` (standalone only, `consolidated` always `False` today), `announcements` (`exchange_ref` unique, `importance` ∈ `high, medium, low, routine` written by Gemini), and the `settings` principle (rule 6 concerns user-facing quotas/caps). |
| [data-sources.md § NSE stock data](../data-sources.md#nse-stock-data) | The record shapes and gaps the rules inherit: shareholding rows carry promoter/public/other but **no FII/DII** (only the XBRL filing has the split; parsing is a recorded gap for 016/018); pledge rows carry `promoter_pledged_pct` computed by 014 and `company` but never a symbol; results are standalone only and must never be compared with consolidated figures; announcements rows carry `exchange_ref`, `announced_at`, `title` and no importance yet. |
| [arch.md](../arch.md) § 4.2 and § 9 | Mode 1 step 3 — "Compute changes and alert candidates (pledge up, promoter holding down, big FII/DII moves) | Python | Rule-based flags with numbers" — is exactly this task's output. § 9's open-question row still lists the FII/DII split as reachable only through XBRL parsing "that 016/018 must add before `fii_move`/`dii_move` alerts can fire"; 016 ships the rules and proposes task 027 for the parsing. Alerts show in the app only; users get no email ([ADR-0015](../adr/0015-email-to-admin-only.md)). |
| [ai.md](../ai.md) | The "Alert explanation" row is **Decided**: Gemini writes `alerts.detail` once per alert, from "the rule that fired, with its numbers" — so 016's rules supply the trigger and the exact numbers, 020 writes the explanation. "Compute numbers": Python computes quarter-on-quarter changes and alert thresholds. |
| [ADR-0001](../adr/0001-python-for-exact-work-claude-for-judgement.md) and [ADR-0017](../adr/0017-gemini-for-stocks-claude-for-ipos.md) | "Python computes changes and alert thresholds; Claude/Gemini explains them." The thresholds and every title number are exact-work, computed here in code; Gemini's explanation must quote, never invent. |
| [ADR-0026](../adr/0026-stock-worker-code-location.md) | The worker's Python lives in the top-level `stock_worker/` package, standard library so far; 016 continues there with no new dependencies. |
| [tech.md](../tech.md) | Repository layout and entry points; 014 already added the `stock_worker/` row. 016 extends the row's description; no new entry point (016 has no CLI; 018 imports it). |
| [`stock_worker/results.py`](../../stock_worker/results.py), [`shareholding.py`](../../stock_worker/shareholding.py), [`pledges.py`](../../stock_worker/pledges.py), [`announcements.py`](../../stock_worker/announcements.py), [`util.py`](../../stock_worker/util.py) | The exact record shapes the rules consume: `quarterly_results` records keyed by `period_end` with `revenue_cr`, `pat_cr` etc. as `Decimal` or `None` and `consolidated` always `False`; `shareholding` records with `quarter_end`, `promoter_pct`, `fii_pct`/`dii_pct` always `None` today; `pledges` records with `quarter_end`, `promoter_pledged_pct` (computed), `company`; `announcements` records with `exchange_ref`, `announced_at`, `title`, and no `importance`. Parsers normalise dates to ISO and return `None` for missing; a stated `0` is a value. The rules compare `Decimal`s, never floats. |
| [`tests/test_stock_results.py`](../../tests/test_stock_results.py), [`tests/support.py`](../../tests/support.py), `tests/fixtures/nse_stock/` | Test conventions to follow: `NoNetworkCase` blocks DNS and sockets; fixtures load via `json.loads((FIXTURES / name).read_text())`; the fixture set is RELIANCE's `results_standalone.json` (5 quarters), `results_filings.json`, `results_consolidated.json`, `shareholding.json` (20 quarters, 2022-03-31 → 2026-09-30, no FII/DII), `pledges.json` (one ADANIENT row for 2026-09-30), `pledges_market.json`, `announcements.json` (20 rows, no `importance`). |
| Task 014's [plan](../014-stock-fetchers/plan.md) and [code review](../014-stock-fetchers/code-review.md) | The house style for a stock-side task (record contract, "missing is missing", fixture-only tests, doc updates with roadmap changes listed) and the explicit hand-off: FII/DII parsing is a recorded gap "for 016", pledge records carry `company` only, and 016's rules "must not compare consolidated against standalone". |

## Approach

### 1. One pure module, `stock_worker/alerts.py`

The rules are stateless, standard-library functions in the package 014 created. They consume the same record shapes the 014 parsers return (keyed by the `db.md` column names, `Decimal`/`None` values) and emit alert records keyed by the `db.md` `alerts` columns, so 018 can insert them straight into the `alerts` table. No module reads the database, a file, a setting or the network; nothing here is wired into any workflow yet, exactly like 014's fetchers were when they shipped.

Alert record contract (keys = `alerts` columns):

| Key | Value |
| --- | --- |
| `kind` | one of `pledge_up`, `promoter_down`, `fii_move`, `dii_move`, `results`, `announcement` |
| `severity` | from the code-held severity map (D10) |
| `title` | built by Python from stated fields — the `db.md` example style: "Promoter pledge up from 4% to 11%" |
| `detail` | `None` — Gemini's explanation is written in 020 against the same alert |
| `dedupe_key` | `<SYMBOL>:<kind>:<period>` where the period is the triggering quarter's `period_end`/`quarter_end`, or `<SYMBOL>:announcement:<exchange_ref>` — uppercase symbol, the `db.md` example form |
| `source_table` / `source_id` | `shareholding`/quarter_end for the four shareholder rules, `quarterly_results`/period_end for `results`, `announcements`/exchange_ref for `announcement` |

Formatting helpers (`format_pct` for percentages with trailing zeros stripped, `format_cr` for ₹ crore with commas and up to 2 dp) are tested alongside the rules; `None` renders as "not available", never a guessed number.

### 2. Change rules: shareholding, pledges, FII/DII

`pledge_up`, `promoter_down`, `fii_move` and `dii_move` each take `(symbol, prev_record, curr_record, threshold)` and compare **consecutive stored quarters** (sorted ascending by `quarter_end`; an omitted quarter simply means the next stored one is the comparison partner — the comparison is "vs the previous quarter on record"). A record pair that is missing the compared field on either side yields no alert. Thresholds are in percentage points, compared as `Decimal`s; a move of exactly the threshold fires ("at least" semantics), less does not. Titles state the exact before and after values ("Promoter pledge up from 4% to 11%", "Promoter holding down from 52.1% to 48.9%", "FII holding up from 14.2% to 16.1%"). The `fii_move`/`dii_move` rules are identical logic over `fii_pct`/`dii_pct`; today those are always `None` on real data, so they stay silent until task 027 feeds parsed values — "missing data (no alert)" is their steady state, and the tests pin it.

The first quarter on record has no predecessor, so no pair exists and no change alert fires — the first stored quarter is the baseline, not an event. This is the roadmap's "first quarter on record (no alert)", tested through `compute_alerts`.

### 3. Existence rules: new results, important announcements

- **`results`**: fires for a quarterly result that has an **earlier quarter on record** (the very first stored quarter is the baseline and alerts nothing, so a fresh stock's history backfill stays quiet; from the second quarter on, each new filing alerts once, ever). The title states the period and the revenue and PAT the filing states — "Quarterly results for 2026-09-30: revenue ₹12,826 cr, PAT ₹872 cr", with "not available" for fields the record does not state. Dedupe key `RELIANCE:results:2026-09-30`. The rules only ever compare within one consolidation series: the input records have `consolidated` always `False` today, and the plan's contract says the caller (018) passes a single-consolidation series — consolidated figures are never compared with standalone, per the data-sources gap note.
- **`announcement`**: fires for an announcement whose `importance` is `high` or `medium` — the value Gemini writes in 020 (until then `importance` is `None`, so no announcement alert fires; the missing-data test pins it). The title is the announcement's own title as NSE stated it (data, quoted as-is; announcements carry no numbers). Dedupe key `RELIANCE:announcement:<exchange_ref>`, the exchange's own unique ID; an announcement without `exchange_ref` cannot be keyed and alerts nothing.

### 4. "The same input never raises the same alert twice"

Three layers, only the first two in this task:

1. **Deterministic rules**: identical input yields identical alert records — same `dedupe_key`, same title, same order. A test runs `compute_alerts` twice on the same input and asserts the lists are equal and the keys unique.
2. **`existing_keys`**: `compute_alerts(..., existing_keys=...)` drops any alert whose `dedupe_key` is already there (018 passes the symbol's stored alert keys). A test passes the first call's keys to the second call and asserts nothing new comes back. This also bounds the one-time history backfill after 015: the first run may alert the honest history of changes per quarter, and no later run repeats it.
3. **The unique index on `alerts.dedupe_key`** (built by 007) plus insert-on-conflict in 018 is the final guard — outside this task, noted in the contract.

### 5. D10 and the FII/DII scoping choice

D10 decides the threshold values, the severity map, and whether thresholds live in `settings` or code — all under [Decisions needed](#decisions-needed), with a recommendation. Whichever way it lands, the rules take thresholds as parameters with code-held defaults, so the module is decision-proof; the difference is only in the docs (and, if the human chooses `settings`, in what 018 reads when it wires the rules).

For the FII/DII split, the roadmap lets this plan propose the route: this plan **recommends task 027** (XBRL shareholding parsing) as a separate follow-up and ships the rules forward-compatible, rather than growing 016 into a fetch-and-parse task that needs a live fixture capture. The proposal is a roadmap change under "Doc updates" and also listed for the human to overrule at plan review.

### 6. What 018 consumes

018 imports `compute_alerts`, passes the fetched records for a symbol (the same sets it is about to persist: results, merged shareholding/pledge rows, announcements) and the symbol's stored `dedupe_key`s, and inserts the returned alert records with the unique key as the conflict target. 016's plan documents this contract so 018 can build the merged per-quarter input records (shareholding row + the pledge row for the same quarter_end, resolved by the 015 name→symbol map) — 016 itself does no merging, because each rule reads only its own fields.

## Steps

| # | Step | Files | Test that proves it |
| --- | --- | --- | --- |
| 1 | Core module: the alert record contract, the `dedupe_key(symbol, kind, period)` builder, the code-held `SEVERITIES` map (all six kinds — values per D10, default recommendation below), `DEFAULT_THRESHOLDS`, and the formatting helpers `format_pct` (trailing zeros stripped; `None` → "not available") and `format_cr` (₹ crore, commas, up to 2 dp; `None` → "not available"). Standard library only, no imports from `ipo_agent/` | `stock_worker/alerts.py` | `tests/test_stock_alerts.py` (new): `dedupe_key("HDFCBANK","pledge_up","2026-09-30") == "HDFCBANK:pledge_up:2026-09-30"` (the db.md example); `format_pct(Decimal("4")) == "4"`, `format_pct(Decimal("2.23")) == "2.23"`, `format_pct(None) == "not available"`; `format_cr(Decimal("128260.00"))` renders ₹ crore with commas, `format_cr(None) == "not available"`; `SEVERITIES` covers exactly the six `alert_kind` values from db.md |
| 2 | Change rules: `pledge_up_alert`, `promoter_down_alert`, `fii_move_alert`, `dii_move_alert` — each `(symbol, prev, curr, threshold_pp)` → an alert record or `None`; `Decimal` comparison, "at least the threshold" fires, below does not; a `None` value on either side → no alert; titles with exact before/after values; dedupe on the current `quarter_end`; `source_table="shareholding"` | `stock_worker/alerts.py` | `tests/test_stock_alerts.py`: per rule — fires above the threshold with the exact pinned title ("Promoter pledge up from 4% to 11%" and the promoter/FII/DII equivalents, direction-aware for FII/DII); silent below; boundary (a move exactly equal to the threshold fires); silent when `prev` or `curr` lacks the compared field (`None`), including the real-data case `fii_pct`/`dii_pct` `None` on both sides; dedupe key and source fields as pinned |
| 3 | Existence rules: `results_alert(symbol, record, has_earlier)` — fires only when an earlier quarter is on record, title with revenue and PAT from stated fields ("not available" when missing), key `RELIANCE:results:<period_end>`, silent when `period_end` is missing; `announcement_alert(symbol, record)` — fires only for `importance` in `("high","medium")`, title = the announcement's title as stated, key `RELIANCE:announcement:<exchange_ref>`, silent for `low`/`routine`/missing `importance` and for a missing `exchange_ref` | `stock_worker/alerts.py` | `tests/test_stock_alerts.py`: a two-quarter results input fires for the later quarter only (first quarter on record → no alert) with the exact title; a one-quarter input fires nothing; missing `revenue_cr` renders "not available"; the same `exchange_ref` yields the same key; `importance=None`/`low`/`routine` → no alert; high and medium → alert |
| 4 | Orchestrator: `compute_alerts(symbol, results, shareholding, announcements, existing_keys=(), thresholds=DEFAULT_THRESHOLDS)` — dedupes each input by natural key keeping the latest (a revised filing doesn't duplicate alerts), sorts ascending, pairs consecutive `shareholding` records for the change rules, applies `results_alert` with per-record `has_earlier` and `announcement_alert` per record, drops alerts whose `dedupe_key` is in `existing_keys`, and returns a deterministic list ordered by `(kind, period)` | `stock_worker/alerts.py` | `tests/test_stock_alerts.py`: first quarter on record → no change alert and no results alert; a two-quarter pair crossing a threshold fires exactly one alert; running the same input twice returns identical lists with unique keys; passing the first call's keys as `existing_keys` returns nothing new; output order is deterministic; no network (inherits `NoNetworkCase`) |
| 5 | Integration over the 014 fixtures: load `results_standalone.json` + `results_filings.json` through `results.parse_results`, `shareholding.json` through `shareholding.parse`, `pledges.json` (its single ADANIENT row, which carries no symbol — passed as the caller would after 015's resolution) through `pledges.parse`, and feed real parsed records to `compute_alerts` | `tests/test_stock_alerts.py` | `tests/test_stock_alerts.py`: on the real fixture data — results alerts exist for the four RELIANCE quarters that have an earlier quarter (five in the fixture), each keyed `RELIANCE:results:<period_end>`; no `fii_move`/`dii_move` alerts (values `None` on every shareholding row); no `announcement` alerts (no `importance` on the fixture rows); the single pledge row alerts nothing (first quarter on record); a second call with the first call's keys emits nothing; the whole run is under `NoNetworkCase` |
| 6 | Docs: update `db.md` (`alerts` note: rules come from `stock_worker/alerts.py` in 016, dedupe-key forms, severity map per D10), `data-sources.md` (shareholding row: 016 ships the FII/DII rules; the values still require XBRL parsing — proposed task 027; rules stay silent until then), `arch.md` (§ 4.2 step 3 names the module; § 9's FII/DII item points at task 027), `tech.md` (repository-layout `stock_worker/` row gains the rules module), `ai.md` (Alert explanation row: the rule that fired comes from 016's Python rules with its numbers; Gemini writes only `alerts.detail`); write ADR-0027 (status **Proposed**) recording D10 as the human settled it at plan review — thresholds, severities, code-vs-settings | `docs/db.md`, `docs/data-sources.md`, `docs/arch.md`, `docs/tech.md`, `docs/ai.md`, `docs/adr/0027-alert-thresholds-and-severities.md` | Manual doc diff review in code review; every title, key and threshold claimed in the docs is pinned by a test in `tests/test_stock_alerts.py`; the ADR's numbers match the settled D10 |
| 7 | Verification: run the full suites and paste the output into this plan | this plan, "Verification" | `python3 -m unittest discover -s tests` (and `.claude/hooks`, `.claude/deepseek`) pass with no network, output pasted |

## Data and AI

- **Tables or columns added or changed:** none. The `alerts` table (schema in [db.md](../db.md#alerts), migrations in 007) is the consumer: the alert records map 1:1 onto its columns, `detail` stays `NULL` for 020 to fill. No migration, no seed, no `settings` row — thresholds are parameters with code-held defaults so rule 6 (quotas and caps from `settings`) is untouched: 016 sets no user-facing limit.
- **Settings read:** none by 016. If D10 settles on `settings` as the thresholds' home, 018 reads the rows and passes them into `compute_alerts` — nothing in this module changes.
- **AI calls:** none. No provider, prompt, prompt version or `ai_*` provenance column. Two cross-task inputs are consumed but neither is produced here: `announcements.importance` (Gemini, 020, with its provenance there) gates the `announcement` rule, and `alerts.detail` (Gemini's explanation, 020) is left unfilled by 016's records. Rule 3 (right AI for the domain) is untouched: Python decides *whether* an alert fires ([arch.md § 4.2](../arch.md#42-stock-worker-decided): "Python decides **whether**"), Gemini decides *what to say*.
- **Data written:** none — no files in `data/`, `analysis/` or `reports/`, no database rows. The only outputs are the alert records returned by the rules and the docs/ADR in step 6.

## Doc updates

- `docs/db.md`: under `alerts` — one line noting the rules and dedupe-key forms are implemented in `stock_worker/alerts.py` (016) with the severity map chosen in D10, and that `detail` is Gemini's (020). Under `shareholding` — extend the "Python's alert rules use the same comparison" note with "implemented in `stock_worker/alerts.py` (016)". If the human's D10 chooses `settings`, add the four threshold rows to the seeded `settings` list with a note that 007's seeds/013's known keys pick them up (listed under the roadmap changes as a scope note).
- `docs/data-sources.md` § NSE stock data, shareholding row: the FII/DII gap note gains — 016 ships the `fii_move`/`dii_move` rules consuming `fii_pct`/`dii_pct`; the values still exist only in the XBRL filing; parsing is the proposed task 027; until then the rules stay silent ("missing data, no alert"), never estimated.
- `docs/arch.md`: § 4.2, Mode 1 step 3 — the change/alert computation is implemented in `stock_worker/alerts.py` (016); § 9's open-question row — the FII/DII item now points at task 027 (quote and consolidated items unchanged).
- `docs/tech.md`: repository layout — the `stock_worker/` row's description gains the alert rules module (numerics only, standard library; no new entry point).
- `docs/ai.md`: the "Alert explanation" row — note that the rule that fired, with its numbers, comes from 016's Python rules; Gemini writes only `alerts.detail` (decision unchanged).
- New ADR `0027-alert-thresholds-and-severities` (D10), status **Proposed**, written in the build with the values the human settles at plan review: each threshold (percentage points, quarter-on-quarter), the severity map, and whether thresholds live in code or `settings`.
- **Roadmap changes for the human or Claude to make on `main` after merge** (`ROADMAP.md` is edited only there):
  - Mark **016** Done.
  - Tick **D10** once the human accepts ADR-0027, and write the chosen thresholds, severities and home (code/settings) into the decision table's "Docs today" cell.
  - Add **task 027 "XBRL shareholding parsing (FII/DII)"** (next unused ID): depends on 014 and 016; feeds `fii_pct`/`dii_pct` from the shareholding XBRL filing recorded as `source_url` by 014, so the 016 rules can fire; status Ready once 016 merges.
  - In **018**'s entry, add that it wires `stock_worker/alerts.py` (the plan's contract: fetched records + stored `dedupe_key`s → alert rows, unique key as conflict target), and that `fii_move`/`dii_move` alerts fire only after task 027 merges.
  - If the human chooses `settings` for D10, note in **007**'s and **013**'s entries that the seeded `settings` rows and the known-keys list gain the four alert thresholds.

## Decisions needed

**D10 — alert thresholds, severities, and where they live** (the roadmap's open decision; gates plan approval):

1. **Threshold values** (percentage points, quarter-on-quarter, "at least X fires"):
   - **Recommendation:** `pledge_up` rise ≥ 1.00 pp; `promoter_down` fall ≥ 2.00 pp; `fii_move` and `dii_move` absolute move ≥ 1.00 pp.
   - Alternative ladders: 0.50–2.00 pp for `pledge_up`, 1.00–3.00 pp for `promoter_down`, 0.50–2.00 pp for the FII/DII moves. A lower value alerts more often (noisier watchlists), a higher one misses gradual creep. Settled by the human; the build pins the winners in `DEFAULT_THRESHOLDS` and ADR-0027.
2. **Severity map** (the `severity` enum `info`/`watch`/`warning`):
   - **Recommendation:** `results` → `info` (a filing fact), `announcement` → `watch` (an important announcement), `pledge_up` → `warning`, `promoter_down` → `warning` (holding/pledge red flags), `fii_move` → `watch`, `dii_move` → `watch`.
3. **Home of the thresholds** (and severities):
   - **Option A (recommended): code** — `DEFAULT_THRESHOLDS` and the severity map live in `stock_worker/alerts.py`, still passable as parameters. Reasons: thresholds are analytic parameters, not user-facing quotas/caps (rule 6's examples are Ask/analysis limits); [ai.md](../ai.md) and [ADR-0001](../adr/0001-python-for-exact-work-claude-for-judgement.md) already say Python computes alert thresholds; 016 is a standard-library pure module and the `settings` table arrives with 007/013; the rules stay callable in tests without a database.
   - **Option B: `settings` rows** — four rows (`alert_pledge_up_min_rise_pp`, `alert_promoter_down_min_fall_pp`, `alert_fii_move_min_abs_pp`, `alert_dii_move_min_abs_pp`) and a severity row, seeded by 007, edited on the admin page (013), read by 018 and passed into `compute_alerts`. More moving parts across three tasks for values that change rarely; the rules stay parameterised either way, so the code is unchanged — only the docs and the roadmap notes differ.

**FII/DII scoping** (not a roadmap D item — the roadmap's "From 014" note delegates the choice to this plan; stated here so the human can overrule at plan review):
- **Option A (recommended): separate task 027** — 016 ships `fii_move`/`dii_move` forward-compatible, tested with synthetic records; 027 ("XBRL shareholding parsing") fetches and parses the shareholding XBRL filings 014 records as `source_url`, feeds `fii_pct`/`dii_pct`, and unlocks the alerts. Keeps 016 "pure Python functions" per its roadmap entry; XBRL parsing needs a live fixture-capture run and its own tests.
- **Option B: fold XBRL parsing into 016** — 016 grows a fetcher/parser and a deliberate one-off capture (like 014's probe) for a fixture. Bigger task, delays the pure-rules review; only chosen if the human prefers one task before 018.

## Risks and rollback

| Risk | How it shows | What to do / rollback |
| --- | --- | --- |
| D10 not settled by plan review | The task cannot be approved (D10 gates approval by design) | The human settles D10 at plan review; options and a recommendation are above. The module design (parameters + defaults) does not change either way |
| FII/DII and announcement alerts stay silent for a while | `fii_move`/`dii_move` never fire (values `None` from 014) and `announcement` never fires (`importance` `None` until 020) | By design — "missing data (no alert)", never an estimate; the tests pin the silence. Task 027 (proposed) feeds FII/DII; 020 feeds importance. Watchlists and stock pages (017/019) show the alerts that do exist |
| One-time history backfill bursts on the first worker run after 015 | The first run alerts every historical quarter that crosses a threshold (a handful per stock; e.g. 19 RELIANCE shareholding pairs) | Honest, bounded and one-time: dedupe keys are per (symbol, kind, quarter), and later runs pass `existing_keys` so nothing repeats. 018's insert-on-conflict against the unique index (007) is the final guard |
| Thresholds set in D10 need tuning later | Alerts too noisy or too quiet | One-line change to `DEFAULT_THRESHOLDS` (code option), or an admin edit of the `settings` rows (settings option) — the rule code is identical. No data migration; alert rows already written are untouched |
| A revised filing duplicates a quarter | Duplicate period_ends in the input (e.g. a revised shareholding submission) | `compute_alerts` dedupes inputs by natural key keeping the latest, so a revision replaces its quarter instead of alerting twice; a test pins it |
| NSE changes a format and the parsers (014) drift | A parser test fails against its fixture; 016's integration test then fails visibly | Fixtures pin the shapes; no live calls in tests. The failure is visible at CI, not a wrong number in the app; a deliberate re-capture is the fix |
| `importance` arrives with values other than the enum (`high`, `medium`, `low`, `routine`) | The announcement rule sees an unexpected string | The rule treats any value outside `high`/`medium` as not important — silent, never an error; the enum in db.md is the documented contract |
| Parallel tasks touch the same docs (`db.md`, `data-sources.md`, `arch.md`, `tech.md`) | Merge conflict on `main` | 016 edits one row or a few lines per doc and adds ADR-0027; whoever merges second resolves the conflict |
| Rollback overall | This task is additive: one pure module, tests, doc lines, one Proposed ADR | Revert the task branch's commits; nothing calls the rules yet (018 does), so no production behaviour changes |
| No setup step gates this task | — | H01–H06 belong to other tasks (007/009/018/020/022/025); 016 needs no account, secret or environment |

## Revisions

| Round | What changed | In answer to |
| --- | --- | --- |

## Changes during build

Anything built differently from the approved plan, and why.

## Verification

Test commands run, with their output pasted.