---
task: 014-stock-fetchers
status: plan-review
branch: task/014-stock-fetchers
assigned_by: Vijay
planner: DeepSeek deepseek-v4-flash-0731 (OpenRouter)
reviewer: Claude Code
---

# 014: NSE stock fetchers

## Task

> Task 014 from docs/tasks/ROADMAP.md:
>
> ### 014 · NSE stock fetchers
>
> | | |
> | --- | --- |
> | Slug | `014-stock-fetchers` |
> | Status | **Ready** |
> | Depends on | 003, D09 |
> | Owner | DeepSeek plans and builds |
> | Milestone | M2 |
>
> Fetchers and parsers for the endpoints confirmed in 003: quote, quarterly results, announcements, shareholding and pledges. They reuse `ipo_agent/net.py` and live where D09 says. Each returns plain records with exact numbers.
>
> - **Done when:** each parser is tested against the fixtures from 003; a failing source returns an error and doesn't stop the others; missing fields come back as missing, never estimated.
> - **Gaps from 003** ([data-sources.md § NSE stock data](../data-sources.md#nse-stock-data)):
>   - **Quote:** `quote-equity` returned 403 locally and from a runner, while every other call answered. Find a working quote source (cookie order, the `section=trade_info` or NextApi variants) with one deliberate probe, and record it.
>   - **Consolidated results:** `results-comparision?consolidated=true` returned the standalone body unchanged. Find the consolidated source or record the gap; never infer it from standalone.
>   - **Results:** no EBITDA and no filing link in `results-comparision`. Take the link from `corporates-financial-results`; derive EBITDA in code only from fields that are stated.
>   - **Units:** no response states a unit. The results amounts look like ₹ lakh; confirm against one filing before converting to ₹ crore.
>   - **FII/DII split:** not in the shareholding JSON, only in the XBRL filing.
>   - **Pledges:** `promoter_pledged_pct` is computed as `numSharesPledged / totPromoterHolding × 100`; NSE's `percSharesPledged` is a share of all shares. Pledge rows carry no symbol, only the company name.
> - **Read:** [data-sources.md](../data-sources.md), [arch.md § 4.2](../arch.md#42-stock-worker-decided), [ADR-0001](../adr/0001-python-for-exact-work-claude-for-judgement.md).
> - **Start:** `/run-task 014`

## Goal and scope

- **In scope:**
  - A Python package (location per D09; recommendation: new top-level `stock_worker/`) with one fetch + parse function per confirmed source: quote, quarterly results (standalone; consolidated handled as a recorded gap), results filings, announcements (per-symbol and market-wide), shareholding, pledges (per-symbol and market-wide).
  - All functions reuse `ipo_agent/net.py`'s `Client` (cookie jar, browser headers, gzip, retries) exactly as it is; nothing in the fetchers re-implements HTTP.
  - Each source returns **plain records** — JSON-serialisable dicts with exact numbers (stdlib `decimal.Decimal` for amounts and percentages, `date`/`datetime` converted to ISO strings) — that map to the `db.md` stock tables (`quarterly_results`, `shareholding`, `announcements`, `stock_quotes`). Missing fields come back as `None`, never estimated.
  - An orchestration function that fetches every source for one symbol, catches each source's failure into an `errors` list, and still returns the records of the sources that worked.
  - The **one deliberate probe** the roadmap allows: a single budget-capped run that tries the quote candidates named in `data-sources.md` (stock-page HTML, `section=trade_info`, cookie order), re-checks the consolidated endpoint once under the same run, records which candidate answered, saves a `quote.json` fixture when one does, and records the outcome in `data-sources.md`.
  - Closing or recording the other 003 gaps in the same docs: EBITDA derived in code from stated fields with a documented formula; results unit (₹ lakh) confirmed from the response's own management-note text and a tested `to_crore` conversion; FII/DII recorded as reachable only through the XBRL filing (parsing out of scope here, flagged for 016); `promoter_pledged_pct` computed in code; pledge rows carrying the company name only.
  - Tests (`tests/test_stock_*.py`) against the saved `tests/fixtures/nse_stock/` fixtures only — no live sites, no AI APIs.
- **Out of scope:**
  - Writing any database row, table, migration or setting; anything in `web/`.
  - `EQUITY_L.csv` parsing and the stocks universe — that is 015. Name→symbol resolution for market-wide pledges is 015/018's job; the fetcher returns the company name as NSE gives it.
  - Downloading or parsing XBRL or PDF filings. FII/DII stay `None`; the XBRL link is kept as `source_url`. A later task (016/018) must add XBRL parsing before `fii_move`/`dii_move` alerts can fire; this plan only records the gap.
  - Change detection, alert rules (016), any AI call or `ai_*` column (020), the database driver or the Gemini client (018/020, part of D09's dependency half).
  - The GitHub Actions worker workflow (018) and any dispatch or schedule.
  - Touching `ipo_agent/nse_stock_smoke.py`: it stays the development probe that the smoke workflow runs and that owns the fixture provenance README. 014 may add the `quote.json` fixture entry next to it.
  - Editing protected paths: `analysis/`, `reports/`, `data/`, `ROUTINE.md`, `config/delivery.json`, `CLAUDE.md`, `.claude/`, `AGENTS.md`, `ROADMAP.md`.

## Context read

| Doc / code | What matters for this plan |
| --- | --- |
| [ROADMAP.md](../ROADMAP.md) § 014, and the decisions/setup tables | The task depends on **D09**, which is Open — it goes under "Decisions needed" and is settled at plan review, before the build. No `H..` setup step gates 014. After merge: mark 014 Done, tick D09 once the human accepts the ADR, and unblock 015/016/018 as their other deps allow. |
| [data-sources.md](../data-sources.md) § NSE stock data | The confirmed endpoints, exact field paths per `db.md` column, quirks, and every gap list: quote 403 everywhere, consolidated byte-identical to standalone, no EBITDA/filing link, unit not stated, FII/DII only in XBRL, pledge rows without symbol, `percSharesPledged` ≠ share of promoter holding. Also the market-wide announcements and pledges answers (evidence for 018's one-call option) and the equity list shape (015's job). |
| [arch.md](../arch.md) § 4.2 and § 9 | The stock worker reuses the standard-library Python fetchers for every number; G1 is ticked and the quote 403 is left to 014; § 9's open-question row still names quote, consolidated, FII/DII and filings, and needs narrowing once this task records its outcomes. |
| [ADR-0001](../adr/0001-python-for-exact-work-claude-for-judgement.md) | Python computes every number. The fetchers are the exact-work layer: parse, compute the pledge share and EBITDA only from stated fields, convert units only once confirmed. Missing is missing, never an estimate. |
| [ADR-0002](../adr/0002-standard-library-only-agent.md) | The stdlib rule binds `ipo_agent/` only. A new package can later take a Postgres driver and a Gemini client (D09); for 014 the fetchers use the standard library regardless. |
| [ADR-0018](../adr/0018-stock-worker-on-github-actions.md) | The worker runs on GitHub Actions and shares the Python fetchers; Actions minutes are limited, so "be gentle" carries over: fetchers did not exist yet, 014 builds the calibration, 018 consumes it. |
| [tech.md](../tech.md) | Repository layout, agent entry points, and the D09 wrinkle: tech.md says one Gemini module is shared by the app and the worker, which can't be one module across TypeScript and Python. 014 has no AI, but the package choice must leave room for the Python Gemini client (020) and Postgres driver (018). |
| [db.md](../db.md) §§ `stock_quotes`, `quarterly_results`, `shareholding`, `announcements` | The contract the records map to: prices in ₹, financials in ₹ crore (`numeric(14,2)`), percentages `numeric(7,2)`, `period_end`/`quarter_end` as the natural keys, `exchange_ref` as the unique dedupe key, `source_url` for filings, `promoter_pledged_pct` defined as share of promoter holding. Money in `numeric`, never float — the fetchers return `Decimal`. |
| [plan.md](../plan.md) § Watchlist signals | What the fetched numbers feed: quarterly results trends, announcements digest, shareholding and pledge changes — all computed in Python, all exact. |
| [`ipo_agent/net.py`](../../ipo_agent/net.py) | `Client` (cookie jar, browser headers, gzip, retries) already exists and is what the fetchers reuse unchanged. `FakeClient` in tests mirrors its `get`/`get_text` signatures. |
| [`ipo_agent/nse.py`](../../ipo_agent/nse.py) | The prime pattern (HTML pages first, then `/api/*` with a referer) and the string-cleaning helpers the NSE data is known to need (spaces, commas, tags). |
| [`ipo_agent/nse_stock_smoke.py`](../../ipo_agent/nse_stock_smoke.py) | The endpoint registry, the exact field paths per source, `KNOWN_GAPS`, the budget/`CallBudget` pattern, and the fixture conventions (20-row cap, manifest, README). 014 turns these confirmed paths into parsers and adds the quote candidates the probe never called. |
| [`tests/test_nse_stock_smoke.py`](../../tests/test_nse_stock_smoke.py), [`tests/support.py`](../../tests/support.py) | Test layout: no `tests/__init__.py`, repo root on `sys.path`, `NoNetworkCase` blocking DNS/sockets, `FakeClient` answering exact URLs, fixtures under `tests/fixtures/nse_stock/`. The stock fetcher tests follow the same shape and reuse `support.py`. |
| `tests/fixtures/nse_stock/*` | The exact live shapes 014 parses: `results_standalone.json` (5 rows, `re_*` strings, notes that state "Net Revenue is Rs 128,260 crore"), `results_filings.json` (`consolidated`: "Non-Consolidated"/"Consolidated", `filingDate` without seconds, `xbrl` links), `announcements.json` (absolute `attchmntFile`, `seq_id`), `shareholding.json` (caps month names, no FII/DII), `pledges.json`/`pledges_market.json` (strings with leading spaces, no `symbol`, `percSharesPledged` 1.61 vs pledged÷promoter 2.23). |
| Task 003's [plan](../003-nse-stock-spike/plan.md) and [code review](../003-nse-stock-spike/code-review.md) | What 014 inherits: the pledge mapping was fixed in 003's review (compute in code, never use `percSharesPledged`); the unit suspicion (₹ lakh) is confirmed by the code review "for 014, not a finding"; the quote fixture is a `KNOWN_GAPS` entry 014 is expected to fill or keep gapped; fixtures must not be re-trimmed by hand. |

## Approach

### 1. The package and the record shape (D09)

D09 is open and gates this task. Recommendation: **a new top-level Python package `stock_worker/`**, standard-library only in this task, importing `ipo_agent.net.Client` for HTTP. It keeps `ipo_agent/` as the IPO routine untouched, leaves ADR-0002's stdlib rule intact (it binds `ipo_agent/` only), and gives the worker a home where 018's Postgres driver and 020's Python Gemini client can later live by the package's own dependency rules. The app's Gemini module is TypeScript (`web/`), so "one shared module" between app and worker is impossible across languages anyway; D09 records the split. Picking a package sets the location of this task's code, so the build follows whatever the human decides; the steps below assume the recommended option.

Every fetcher returns "plain records": dicts with keys matching the `db.md` column names (minus the `_cr` unit suffix), amounts and percentages as `decimal.Decimal`, dates as ISO `YYYY-MM-DD` strings and timestamps as ISO 8601 strings with `+05:30` preserved from NSE's local times. Missing → `None`, and a missing field is always `None`, never zero and never estimated. Amounts stay in the unit the API stated ("lakh" once confirmed, below); a small tested `to_crore(value)` helper divides by 100, and 018 maps the records onto the `*_cr` columns. No fetcher writes to `data/`, `analysis/` or `reports/`; the only files this task's code writes are the quote probe's fixture in `tests/fixtures/nse_stock/` (and its manifest entry), because parse results only reach git-free files in 018.

### 2. One module per source, one client

| Source | Module | Endpoint (confirmed in 003 unless noted) | Records |
| --- | --- | --- | --- |
| Results | `stock_worker/results.py` | `results-comparision?symbol=X`; filings from `corporates-financial-results?index=equities&period=Quarterly&symbol=X` | One row per quarter: `period_end`, revenue, other_income, expenses, EBITDA (derived, below), pat, eps from the comparison JSON; `period_start`, `consolidated` (boolean: "Non-Consolidated"/"Consolidated"), `audited`, `filed_at`, `source_url` (the `xbrl` link) from the filings JSON. `consolidated=True` requests return no rows and a gap note, never standalone figures |
| Announcements | `stock_worker/announcements.py` | `corporate-announcements?index=equities&symbol=X` and the market-wide `from_date`/`to_date` variant | `symbol`, `subject` (`desc`), `announced_at` (`an_dt`), `title` (`attchmntText`), `attachment_url` (`attchmntFile`), `exchange_ref` (`seq_id`), `industry` (`smIndustry`). An optional `since` (ISO timestamp) drops older rows in code, so 018's daily run is one call that keeps only what's new |
| Shareholding | `stock_worker/shareholding.py` | `corporate-share-holdings-master?index=equities&symbol=X` | `quarter_end` (`date`), `filed_at` (`submissionDate`), `promoter_pct` (`pr_and_prgrp`), `public_pct` (`public_val`), `other_pct` (`employeeTrusts`), `source_url` (`xbrl`). `fii_pct`/`dii_pct` are `None` — the JSON does not carry them; the gap is recorded, nothing is inferred |
| Pledges | `stock_worker/pledges.py` | `corporate-pledgedata?index=equities&symbol=X` and the market-wide variant | `company` (`comName`, the only identifier; no symbol field exists), `quarter_end` (`shp`), `disclosed_at` (`broadcastDt`), `shares_held` (`totPromoterHolding`), `shares_pledged` (`numSharesPledged`), `promoter_pledged_pct` **computed in code** as `shares_pledged / shares_held × 100` (rounded to 2 dp), `promoter_pct` (`percPromoterHolding`), `pledged_pct_of_total` (`percSharesPledged`, kept raw for reference). Strings are stripped of the leading spaces NSE sends |
| Quote | `stock_worker/quote.py` | Not confirmed yet — chosen by the one probe in step 6 | Whatever the confirmed source states: `symbol`, `isin`, `price`, `change_pct`, `week52_high`, `week52_low`, and market cap/P/E only if the source states them; `as_of` is the fetch time. If no source answers, `fetch_quote` raises `SourceError` with a message pointing at the recorded gap, and no `stock_quotes` row is ever fabricated |

Parsing helpers (path lookup, Decimal/date/datetime parsers tolerant of `31-DEC-2024`, `30-Sep-2026`, `29-Oct-2026 08:55:40`, `16-Jan-2025 20:20`) live in `stock_worker/util.py`. The date/time parsers return ISO strings; the exactness of a money figure is a `Decimal`, never `float`, matching db.md principle 5.

### 3. Units, EBITDA, and the two "never infer" rules

- **Units.** The response states no unit field, but its own management-note text does. RELIANCE's first `results_standalone.json` row has `re_net_sale` = `12826000` and `re_desc_note_seg` saying "Net Revenue is Rs 128,260 crore" — `12826000 lakh = 128260 crore`, so the API's amounts are **₹ lakh**. `results.py` confirms the unit per fetch by matching a `Rs <N> crore` figure in the row's `re_desc_note_fin`/`re_desc_note_seg` against the parsed amount divided by 100; when a match is found the fetch's `unit` is `"lakh"` and `to_crore` is safe. No conversion happens without the match; an unconverted fetch reports `unit: None` and 018 stores nothing for those rows rather than a wrong unit.
- **EBITDA.** `results-comparision` has no EBITDA field. `results.py` derives it only from fields that are stated: `ebitda = revenue + other_income − expenses + depreciation`, using `re_net_sale`, `re_oth_inc_new`, `re_oth_tot_exp`, `re_depr_und_exp` — and only when all four are present. If any is absent, `ebitda` is `None`. The formula is written down in the module docstring and in `data-sources.md`, so the derivation is auditable; it is not a guess, it is a stated rule applied to stated fields.
- **Consolidated results.** The `consolidated=true` endpoint returned a byte-identical body in 003; this task re-checks it once inside the probe run (step 6), and unless it answers with a distinct body, `results.py` returns no consolidated rows and the gap stays recorded. Standalone rows are never relabelled consolidated.
- **FII/DII.** The shareholding JSON has no FII/DII split; the XBRL filing does. 014 does not fetch or parse XBRL; `fii_pct`/`dii_pct` are `None` and the gap is recorded for 016, whose `fii_move`/`dii_move` rules will need XBRL parsing (016's scope note; see "Doc updates").

### 4. Failure isolation and the "be gentle" budget

`stock_worker/fetchers.py` exposes one entry per source and `fetch_all(client, symbol, since=None)` that calls each source, catches each `FetchError`/`SourceError` into `errors = [{"source": ..., "error": ...}]`, and returns a bundle with the successful records — a failing source never stops the others, matching the "Rules for every source". Each source makes exactly one GET per call (the announcements fetcher with `since` still makes one GET; filtering is in code). The probe run in step 6 is the only deliberate live request sequence in the task, and it is one run with a hard budget of 6 requests (2 primes + up to 4 candidates), stopping at the first working quote candidate; `CallBudget`-style guards and tests pin the count, exactly as in 003.

### 5. What is deliberately not here

The equity list (`EQUITY_L.csv`) parser is 015's; the smoke probe stays untouched; the worker's scheduling, database writes and AI calls are 016/018/020. This task ships code that is not yet called by any workflow — it is the calibrated, tested fetcher layer that 018 wires in.

## Steps

The build starts only after D09 is decided at plan review; the steps assume the recommended package location and say so if the human picks another.

| # | Step | Files | Test that proves it |
| --- | --- | --- | --- |
| 1 | Create the `stock_worker/` package (per D09) with `errors.py` (`FetchError`, `SourceError`), `util.py` (path lookup, Decimal/date/timestamp parsers tolerant of NSE's string formats, `to_crore`) and `__init__.py` | `stock_worker/__init__.py`, `stock_worker/errors.py`, `stock_worker/util.py` | `tests/test_stock_util.py` (new): `31-DEC-2024` → `2024-12-31`; `30-Sep-2026` and `21-OCT-2026` both parse; `29-Oct-2026 08:55:40` and `16-Jan-2025 20:20` parse to ISO; `" 71.97"`, `"1,28,26,000"` and `"21723685"` parse as `Decimal`; junk → `None`; `to_crore(Decimal("12826000"))` = `Decimal("128260.00")`; all via `NoNetworkCase` with `FakeClient` only where HTTP is involved |
| 2 | Results fetcher: parse `results-comparision` rows and `results_filings` rows; EBITDA derivation from stated fields; unit confirmation from the note text; `consolidated` boolean mapping; consolidated-gap behaviour (`consolidated=True` → no rows, no inference) | `stock_worker/results.py` | `tests/test_stock_results.py`: the `results_standalone.json` fixture parses to 5 records with exact values (first row: `period_end` `2024-12-31`, revenue `Decimal("12826000")`, pat `Decimal("872100")`, eps `Decimal("6.44")`); `unit` is `"lakh"` confirmed by the "Rs 128,260 crore" note text; `to_crore(revenue)` = `128260.00`; the EBITDA formula on the fixture row uses `re_*` fields only; a synthetic row without depreciation gives `ebitda=None`; `results_filings.json` maps `consolidated` to booleans, `filed_at`, `source_url = xbrl`; the identical `results_consolidated.json` fixture yields zero consolidated records and a gap flag, never standalone numbers |
| 3 | Announcements fetcher: per-symbol and market-wide; `since` filter in code; `exchange_ref` as the dedupe key; attachment and industry kept raw | `stock_worker/announcements.py` | `tests/test_stock_announcements.py`: the `announcements.json` 20-row fixture parses to 20 records with the documented fields; `since` = a timestamp drops older `announced_at` rows and keeps newer; the market fixture parses with the same paths; a synthetic row without `attchmntFile` gives `attachment_url=None` |
| 4 | Shareholding fetcher: promoter/public/other percentages, quarter date, filing date, XBRL `source_url`; FII/DII return `None` with the gap documented, never estimated | `stock_worker/shareholding.py` | `tests/test_stock_shareholding.py`: the `shareholding.json` fixture parses to exact percentages (first row: promoter `Decimal("50.44")`, public `Decimal("49.56")`, other `Decimal("0")`), `quarter_end` `2026-09-30`, `source_url` is the `xbrl` link; `fii_pct` and `dii_pct` are `None` on every row; a synthetic row with a `fii` value is parsed when present (forward-compatible) |
| 5 | Pledges fetcher: per-symbol and market-wide; `promoter_pledged_pct` computed in code as `shares_pledged / shares_held × 100` rounded to 2 dp; strings stripped; record carries `company`, never a made-up symbol | `stock_worker/pledges.py` | `tests/test_stock_pledges.py`: the `pledges.json` fixture parses to one record — company `"Adani Enterprises Limited"`, shares_held `Decimal("974234554")`, shares_pledged `Decimal("21723685")`, `promoter_pledged_pct` `Decimal("2.23")` (the computed share, not NSE's `1.61`), `promoter_pct` `Decimal("71.97")` (leading spaces stripped), `quarter_end` `2026-09-30`; the market fixture parses to 20 records with the same shape, none carrying a `symbol` key; a synthetic row with `totPromoterHolding=0` yields `promoter_pledged_pct=None`, not a division error |
| 6 | Quote: add the parser and the **one deliberate probe** — a single budget-capped run (2 primes + up to 4 candidates, stop at the first success) trying, in order: the stock page HTML's embedded quote JSON (the `get-quotes` page answered 200 everywhere in 003 and is already the prime), `quote-equity?symbol=X&section=trade_info`, and `quote-equity?symbol=X` with the per-symbol page primed first (cookie-order variant); the run also re-checks `results-comparision?consolidated=true` once under the same prime; on success, save a trimmed `quote.json` fixture and record the working URL; on failure, record every candidate's error | `stock_worker/quote.py`, `stock_worker/probe.py` (dev entry `python3 -m stock_worker.probe`), `tests/fixtures/nse_stock/quote.json` + `manifest.json`/`README.md` entry when captured, `docs/data-sources.md` | `tests/test_stock_quote.py`: the quote parser turns a captured `quote.json` fixture (or, if the probe found no source, a synthetic body matching the recorded gap) into the documented record with missing fields `None`; the probe's candidate registry is the fixed ordered list with `MAX_CALLS = 6` and a `CallBudget` refusing a 7th call (mirrors 003's test); `--dry-run` prints the candidates and makes no network call; the fixture test asserts every top-level list in `quote.json` is within the 20-row cap |
| 7 | Orchestration: the per-source public functions in `fetchers.py` and `fetch_all()` with per-source error capture; a `stock_worker/__main__.py` dev CLI that prints planned calls with `--dry-run` and prints records on a real run | `stock_worker/fetchers.py`, `stock_worker/__main__.py` | `tests/test_stock_fetchers.py`: a `FakeClient` whose `get` raises for exactly one URL (e.g. the shareholding one) → `fetch_all` returns the other sources' records plus an `errors` entry naming the failed source; a source that 404s without a body doesn't stop the rest; `python3 -m stock_worker --dry-run` returns 0, prints the per-source URLs for one symbol, and never creates a client (monkeypatch `Client` to raise if called) |
| 8 | Update the docs and the roadmap notes: quote/consolidated/unit/EBITDA/FII-DII/pledges rows in `data-sources.md` with the probe outcome; fetchers' location and entry points in `tech.md`; `arch.md` § 4.2 and § 9; new Proposed ADR for D09; roadmap changes for `main` listed below | `docs/data-sources.md`, `docs/tech.md`, `docs/arch.md`, `docs/adr/0026-stock-worker-code-location.md` | Manual doc diff review in code review; the full suite `python3 -m unittest discover -s tests` passes with no network; every doc claim matches a fixture or the probe outcome (no unconfirmed URL presented as confirmed) |
| 9 | Run the full verification and paste the output | this plan, "Verification" | `python3 -m unittest discover -s tests` (and `.claude/hooks` tests) output pasted; the probe run's table pasted with its `quote source:` line |

### Build order and fallbacks

1. Steps 1–5 are fixture-only and never touch the network; they are the bulk of the task and come first.
2. Step 6 is the single live probe. It runs once, locally. If the local environment is blocked (as 003's quote call was), the same probe can be run from a GitHub runner by adding `task/014-*` to the smoke workflow's `push` filter and uploading the artifact — the plan records that fallback under "Risks"; no estimate is made if both are blocked, and the quote source stays "not confirmed" with the candidates recorded.
3. Step 7 wraps the parsers; step 8 writes the docs; step 9 verifies.

## Data and AI

- **Tables or columns added or changed:** none. No database row, table, migration or seed is written; `db.md` columns are only referenced as the record contract.
- **Settings read:** none. No `settings` row is read or set; rule 6 (quotas from `settings`) is not touched by fetchers.
- **AI calls:** none. No provider, prompt, prompt version or `ai_*` provenance column is involved; rule 3 (right AI for the domain) is untouched.
- **Data written:** only the probe's `tests/fixtures/nse_stock/quote.json` (if a quote source answers) and a manifest/README entry alongside it — code-written, trimmed to 20 rows, no cookies, headers, user data or secrets, consistent with 003's fixture rules. Nothing is written to `data/`, `analysis/` or `reports/`.

## Doc updates

- `docs/data-sources.md` § NSE stock data:
  - Quote row: the working source (exact URL/variant and the fields it states) once the probe answers, or stays **not confirmed** with the candidates attempted and their errors.
  - Consolidated results row: closed with the re-check's outcome, or confirmed as a permanent gap ("do not infer" stays).
  - Results row: EBITDA derivation formula from stated fields; `filed_at`/`source_url` come from `corporates-financial-results`; unit confirmed as ₹ lakh, with the note-text evidence and the `to_crore` conversion rule.
  - Shareholding row: FII/DII remain reachable only through the XBRL filing; 014's fetcher returns them missing; XBRL parsing is a recorded gap for 016/018.
  - Pledges rows: `promoter_pledged_pct` is computed in code (`numSharesPledged / totPromoterHolding × 100`); rows carry only `comName`; symbol resolution is the caller's (015's stocks / `EQUITY_L.csv`).
  - The summary row: status moves to "**Decided**; fetchers built in 014 (`stock_worker/`), worker planned (018)".
- `docs/tech.md`: repository layout gains the `stock_worker/` row; the agent entry-points table gains `python3 -m stock_worker` (dev print) and the probe `python3 -m stock_worker.probe`; the stock-worker row notes the fetcher package exists.
- `docs/arch.md`: § 4.2 notes the fetchers now exist and where (per D09); § 9's open-question row narrows to what remains (FII/DII XBRL parsing, consolidated if still gapped, quote if still gapped).
- `docs/db.md`: one-line notes under `quarterly_results` (amounts are NSE's ₹ lakh converted to crore by 014's tested helper) and `shareholding` (`promoter_pledged_pct` computed by the fetcher from stated share counts; FII/DII come later from XBRL).
- New ADR `0026-stock-worker-code-location` (D09) with status **Proposed** — the human accepts it and ticks D09.
- **Roadmap changes for the human or Claude to make on `main` after merge** (`ROADMAP.md` is edited only there): mark **014** Done; keep/tick **D09** once the human accepts ADR-0026; set **015** Ready once 008 is Done; set **016** Ready once D10 is decided (adding a note that `fii_move`/`dii_move` need an XBRL-parsing step that 014 explicitly left as a gap — its scope likely grows or a follow-up task appears); **018** stays Blocked until 007/015/016/H02; nothing else changes.

## Decisions needed

**D09 — where the stock worker's code lives, and its dependencies** (Open in the roadmap; gates 014 and 020). Options:

| Option | For | Against |
| --- | --- | --- |
| **A. New top-level Python package `stock_worker/`** (recommended) | Keeps `ipo_agent/` the IPO routine; ADR-0002's stdlib rule keeps binding `ipo_agent/` only, so 018's Postgres driver and 020's Python Gemini client have a legal home later; reuses `ipo_agent/net.py` by import; clear boundary for the worker's own dependency rules | A third Python package in the repo; 018's workflow must install it (a repo checkout already has it) |
| B. Inside `ipo_agent/` | No new top-level layout; closest reuse | Reads as extending ADR-0002 to the worker: no `pip` at all, which collides with 018's Postgres driver and 020's Gemini client unless ADR-0002 is amended anyway; mixes the IPO routine's and the stock worker's moving parts |
| C. A Python folder inside `web/` | None here | `web/` is the TypeScript app; a Python subpackage with its own deps there muddies the app's build and the D22 "same repo" boundary |

Also part of D09: the worker's Gemini client is Python, the app's is TypeScript, so tech.md's "one Gemini module shared by the app and the worker" cannot be one module — the ADR should record the split (worker: Python module in the new package; app: `web/lib/` TypeScript module) as part of the dependency decision. **Recommendation: option A**, fetchers standard-library only in this task, importing `ipo_agent.net.Client`; the Postgres/Gemini dependencies are decided for 018/020 and do not enter this build.

## Risks and rollback

| Risk | How it shows | What to do / rollback |
| --- | --- | --- |
| D09 stays unsettled | 014 is Ready but the plan review can't approve | The plan lays out the options; the human settles D09 (accepting ADR-0026) before the build starts, as the roadmap requires |
| The quote probe finds no working source (all candidates 403 or unparseable) | No `quote.json` fixture; the probe table shows every candidate failing | Record the gap: quote stays **not confirmed** in `data-sources.md`, `fetch_quote` raises a `SourceError` pointing at it, and `stock_quotes` remains unfilled until a later task. No estimate is ever made. If the local environment is blocked but a GitHub runner answers, run the same probe from the runner by adding `task/014-*` to the smoke workflow's `push` filter (recorded in "Changes during build"); the smoke workflow already proved runners reach nine endpoints, so this is a fallback, not a gate |
| NSE blocks the build's one probe run | The probe run prints 403/timeouts | The budget cap holds it to one run of ≤ 6 requests; tests never call NSE; the fixtures stay exactly as 003 captured them; nothing fake is recorded |
| Unit confirmation inconclusive for a company | The note text has no "Rs … crore" match | That fetch reports `unit: None`, the amounts stay unconverted, and 018 stores nothing for those rows rather than a wrong unit. The fixture's RELIANCE rows confirm lakh, which is recorded; the plan does not assume it for all symbols |
| EBITDA formula disputed | A reviewer or later reader questions the derivation | The formula is stated in code, tests and `data-sources.md` ("revenue + other income − expenses + depreciation, only when all four are stated"); if rejected at review, `ebitda` falls back to `None` (missing, never estimated) — a one-line change, no data affected |
| Consolidated endpoint still returns the standalone body | The probe re-check shows byte-identical bodies again | The gap stays recorded and `results.py` never returns consolidated rows; 016's alert rules must not compare consolidated against standalone (noted in the data-sources quirks) |
| Pledge arithmetic edge (zero promoter holding) | Division by zero on a degenerate row | The fetcher returns `promoter_pledged_pct=None` for `totPromoterHolding=0`; the test pins it |
| NSE redeploys and a field drifts | A parser test fails against a fixture that no longer matches live | The fixtures and capture dates pin the shapes; a live re-capture is a deliberate run (smoke workflow artifact or the probe), not something the tests do. Until re-captured, the parser fails visibly instead of the app showing wrong numbers |
| Parallel tasks touch the same docs (`data-sources.md`, `tech.md`, `arch.md`) | Merge conflict on `main` | This plan edits only 014's rows and adds one ADR file; whoever merges second resolves the conflict |
| Rollback overall | This task is additive: one new package, tests, fixtures, docs, one Proposed ADR | Revert the task branch's commits; no workflow calls the fetchers yet, so nothing in production behaviour changes |

## Revisions

| Round | What changed | In answer to |
| --- | --- | --- |

## Changes during build

Anything built differently from the approved plan, and why.

## Verification

Test commands run, with their output pasted.