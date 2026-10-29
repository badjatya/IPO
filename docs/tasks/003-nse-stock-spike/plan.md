---
task: 003-nse-stock-spike
status: done
branch: task/003-nse-stock-spike
assigned_by: Vijay
planner: DeepSeek (opencode)
reviewer: Claude Code
---

# 003: NSE stock-data spike and runner smoke test

## Task

> **Task 003 from `docs/tasks/ROADMAP.md`**
>
> ### 003 · NSE stock-data spike
>
> | | |
> | --- | --- |
> | Slug | `003-nse-stock-spike` |
> | Status | **Ready** |
> | Depends on | — |
> | Owner | DeepSeek plans and builds; the human runs the smoke test on GitHub and ticks G1 |
> | Milestone | M2 (but do it in week 1: it answers gate G1) |
>
> Confirm the NSE endpoints for quotes, quarterly results (standalone and consolidated), corporate announcements, shareholding pattern, promoter pledges and the list of listed equities, and record each one in `data-sources.md`. Save one response per endpoint as a test fixture. Add a manually triggered workflow that calls each endpoint once from a GitHub runner, using `ipo_agent/net.py`, and prints what came back.
>
> - **Done when:** every endpoint and its fields are recorded in `data-sources.md`; fixtures are saved; the smoke-test workflow is merged.
> - **After merge:** the human runs the smoke test and records the result in `data-sources.md` and [arch.md § 9](../../arch.md#9-open-questions), then ticks G1.
>   - GitHub can only run a manually triggered workflow once its file is on the default branch, so the run can't happen from the task branch.
>   - Alternatively, the plan can add a `push` trigger limited to `task/003-*` so the run happens before merge. Either way, the plan must say which.
> - **If NSE blocks GitHub runners:** stop. The human decides what to do (a new ADR superseding [ADR-0018](../../adr/0018-stock-worker-on-github-actions.md)). Tasks 018 onwards wait.
> - **Watch for:** "be gentle" in [data-sources.md](../../data-sources.md#rules-for-every-source): one call per endpoint, no loops.
> - **Read:** [data-sources.md](../../data-sources.md), [ADR-0018](../../adr/0018-stock-worker-on-github-actions.md), `ipo_agent/net.py`, `ipo_agent/nse.py`.
> - **Start:** `/plan-task Task 003 from docs/tasks/ROADMAP.md`

## Goal and scope

- **In scope:**
  - Confirm, against live NSE responses, one working URL for each of: quote; quarterly results (standalone and consolidated); corporate announcements; shareholding pattern; promoter pledges; the list of listed equities.
  - Record each confirmed URL, the fields it returns, and the mapping to the columns in [db.md](../../db.md) in `data-sources.md`.
  - Save one parsed response per data call (or per data call that answered) under `tests/fixtures/nse_stock/`, with a `manifest.json` (source, capture time, original row counts and bytes) and a short provenance README (capture date, symbol, local vs runner, GitHub run URL).
  - Add a small standard-library probe (`ipo_agent/nse_stock_smoke.py`) that makes exactly one request per registry entry (12 in total), prints a table and a field-coverage report, and can write the fixtures, a manifest and a JSON summary.
  - Add `.github/workflows/nse-stock-smoke.yml`, triggered by `workflow_dispatch` **and** by a push to `task/003-*`, so the run happens from a GitHub runner before merge (the roadmap's alternative). It calls each endpoint once, prints the result and uploads the summary and any captured fixtures as an artifact.
- **Out of scope:**
  - Building the real stock fetchers and parsers (task 014), the stock universe (015), change detection (016), the worker (018) or any database row.
  - Deciding where the stock worker's code lives or which dependencies it has (D09).
  - Downloading or parsing filing PDFs/XBRL bodies, beyond recording the links NSE returns.
  - Fixing NSE blocks, adding a proxy, moving the worker host, or superseding ADR-0018.
  - Any AI call, prompt, prompt version or `ai_*` column.
  - Editing protected paths: `analysis/`, `reports/`, `data/`, `ROUTINE.md`, `config/delivery.json`, `CLAUDE.md`, `.claude/`.

## Context read

| Doc / code | What matters for this plan |
| --- | --- |
| [ROADMAP.md](../ROADMAP.md) § 003 | The exact endpoint list, the done-when, the post-merge G1 procedure, the "be gentle" rule, and the explicit permission to add a `push` trigger limited to `task/003-*` if the plan says so. |
| [docs/tasks/README.md](../README.md) | One branch/worktree per task; DeepSeek commits only `plan.md` in the planning step, never pushes; the plan review precedes the build. |
| [AGENTS.md](../../AGENTS.md) | `ipo_agent/` is standard-library Python; tests use saved files and never live sites; numbers come from code, not estimates; open questions are not decided in code; `data/` and `analysis/` are written only by code. |
| [data-sources.md](../../data-sources.md) | The NSE section explains cookie priming and retries; the "NSE stock data (planned)" table lists the five data types and their fields; the "Rules for every source" section requires one failing source not to stop the run and one call per source, no loops. |
| [ADR-0018](../../adr/0018-stock-worker-on-github-actions.md) | The worker will run on GitHub Actions; NSE may block GitHub runners; a week-1 smoke test is required before anything is built on it; Actions minutes are limited. |
| [arch.md § 4.2](../../arch.md#42-stock-worker-decided) | The worker reuses the standard-library Python fetchers (`net.py`, NSE client) for every number; no AI in this task. |
| [arch.md § 9](../../arch.md#9-open-questions) | "Confirmed NSE endpoints" and "Does NSE answer requests from GitHub's runners?" are open; this task closes the first and supplies the evidence for the second. |
| [db.md](../../db.md) §§ `stocks`, `stock_quotes`, `quarterly_results`, `shareholding`, `announcements` | The field set the future fetchers must fill: symbol/ISIN/name/industry; price, change, 52-week range, market cap, P/E; period end, consolidated flag, revenue, other income, expenses, EBITDA, PAT, EPS, filing time and link; quarter end, promoter/FII/DII/public/other and pledged %; exchange ref, announcement time, subject, title, attachment link. This task records where each comes from; it does not fill the tables. |
| [tech.md](../../tech.md) | Repository layout (`.github/workflows/`), agent entry points, and the rule that the agent is standard-library only. The probe is a dev tool, not a new dependency. |
| [plan.md § Watchlist signals](../../plan.md#watchlist-signals) | What the stock side needs from NSE: quarterly results trends, announcements digest, shareholding and pledge changes. |
| [`ipo_agent/net.py`](../../ipo_agent/net.py) | `Client` already provides a cookie jar, browser headers, gzip handling and retries. The probe reuses it; tests do not call it. |
| [`ipo_agent/nse.py`](../../ipo_agent/nse.py) | The IPO client primes against IPO pages and uses an IPO referer. The stock probe needs its own stock-page referer, so it should use `net.Client` directly rather than the IPO `NSE` class. |
| [`.claude/skills/review-plan`](../../.claude/skills/review-plan/SKILL.md) and the plan-review checks | The plan must be testable, keep every AGENTS rule, and leave open decisions under "Decisions needed". |

## Approach

### 1. What "confirmed" means and the call budget

The probe makes exactly **12 HTTP requests per run**, in the order below, and no others. Two are priming GETs; ten are data calls. It uses `net.Client(timeout=30, retries=0)`, so each entry is one HTTP attempt: a 403, timeout or parse error is recorded and the run moves on, never retried. The ordered `ENDPOINTS` registry is the only source of requests; `MAX_CALLS = len(ENDPOINTS)` is 12, and a `CallBudget` guard around every `client.get` raises `BudgetExceeded` before a 13th request. There are no symbol loops, no retries, no alternate URLs and no adaptive second call: a request that is not in the list cannot be made.

| # | ID | Request | Kind | Fixture | What it is for |
| --- | --- | --- | --- | --- | --- |
| 1 | `prime_home` | `GET https://www.nseindia.com/` | HTML | — | Sets cookies; a 403 is expected and recorded, as in `ipo_agent/nse.py`. |
| 2 | `prime_stock` | `GET https://www.nseindia.com/get-quotes/equity?symbol=RELIANCE` | HTML | — | Sets the stock-page cookies and the referer used by the data calls. |
| 3 | `quote` | `GET https://www.nseindia.com/api/quote-equity?symbol=RELIANCE` | JSON | `quote.json` | `priceInfo.lastPrice`, `priceInfo.change`, `priceInfo.pChange`, `priceInfo.weekHighLow`; market cap and P/E only if the base response states them; `securityInfo` (symbol, ISIN); `industryInfo` (sector/industry). |
| 4 | `results_standalone` | `GET https://www.nseindia.com/api/results-comparision?symbol=RELIANCE` (NSE's spelling) | JSON | `results_standalone.json` | `resCmpData[]`: date, income, expenditure, net profit, EPS; whether other income, EBITDA and a filing link are present. |
| 5 | `results_consolidated` | `GET https://www.nseindia.com/api/results-comparision?symbol=RELIANCE&consolidated=true` | JSON | `results_consolidated.json` | Same fields on the consolidated basis. If the endpoint ignores or rejects the parameter, record that; do not infer consolidated numbers from standalone. |
| 6 | `results_filings` | `GET https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Quarterly&symbol=RELIANCE` | JSON | `results_filings.json` | Period start/end, `consolidated` flag, audited flag, filed/broadcast time, XBRL/details link. Candidate source for `quarterly_results.filed_at` and `source_url`. |
| 7 | `announcements` | `GET https://www.nseindia.com/api/corporate-announcements?index=equities&symbol=RELIANCE` | JSON | `announcements.json` | `symbol`, subject (`desc`), announcement time (`an_dt`), title (`attchmntText`), attachment (`attchmntFile`), exchange ID (`seq_id`/`orgid`), industry (`smIndustry`). |
| 8 | `announcements_market` | `GET https://www.nseindia.com/api/corporate-announcements?index=equities&from_date=<DD-MM-YYYY>&to_date=<DD-MM-YYYY>` | JSON | `announcements_market.json` | One fixed market-wide call (run date and six days earlier) to test 018's one-call option. |
| 9 | `shareholding` | `GET https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol=RELIANCE` | JSON | `shareholding.json` | As-on date, submission/filing date, promoter & promoter group (`pr_and_prgrp`), public (`public_val`), employee trusts, XBRL link. Explicitly check whether FII and DII splits are present; if not, record that they are only in the XBRL filing. |
| 10 | `pledges` | `GET https://www.nseindia.com/api/corporate-pledgedata?index=equities&symbol=ADANIENT` | JSON | `pledges.json` | Promoter holding, pledged shares, pledged % of promoter holding, disclosure/quarter date. |
| 11 | `pledges_market` | `GET https://www.nseindia.com/api/corporate-pledgedata?index=equities` | JSON | `pledges_market.json` | One fixed market-wide call to test 018's one-call option. |
| 12 | `equity_list` | `GET https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv` | CSV | `equity_list.csv` | Header: `SYMBOL`, `NAME OF COMPANY`, `SERIES`, `DATE OF LISTING`, `PAID UP VALUE`, `MARKET LOT`, `ISIN NUMBER`, `FACE VALUE`. Note: no industry and no explicit active flag; record that for 015. |

**Fixed choices in the list.**

- The quote is the base response only. The `section=trade_info` variant is **never** called. Market cap and P/E are recorded from the base response; if they are not there, they are a gap for 014, not a reason for a second call.
- The pledge symbol is fixed at `ADANIENT`; it is not chosen from a market-wide response. If the per-symbol response is empty, the fixture is an empty list and the plan records "empty". `--pledge-symbol` may override it for a local experiment, but the committed fixtures use the default.
- The two market-wide calls are fixed probes for 018, not fallbacks. `announcements_market` uses the run date and six days earlier as `from_date`/`to_date` in `DD-MM-YYYY`; if NSE rejects that format, record the error and the format it accepted for 014. `pledges_market` is `?index=equities`. Neither result chooses a symbol or triggers another call.
- **No fallback is attempted.** If a primary fails, the probe records the failure and the run moves on. The NextApi quote URL and any other alternate stay documented in `data-sources.md` as unprobed candidates for a later deliberate run; they are not in `ENDPOINTS` and are not called here. This is what keeps the budget exactly 12.

For each response it records:

- the exact URL and query string (public data; no headers or cookies),
- success or the HTTP/network error,
- response size and elapsed time,
- the top-level shape (JSON keys, list length, CSV header and row count),
- a **field-coverage table**: for every column the future fetcher needs, the JSON/CSV path in this response and whether it was found. A missing column is recorded as "not in this response", never estimated,
- the unit, if the response states one.

**Units.** A unit is part of the number. The probe records a unit only when the response itself states it (for example a `unit` or `currency` field, or a value the response labels). It does not assume ₹ lakh or ₹ crore for `results-comparision`, a currency for quote market cap, or any unit for the results filings. It does not fetch NSE's results page, because that would be a 13th request; if the response is silent, the fixture README and `data-sources.md` say **unit not stated**, and 014 confirms it against one filing (or the results page) before converting. No conversion happens in the probe or in a fixture; amounts are saved exactly as returned.

### 2. Where the code lives

Add `ipo_agent/nse_stock_smoke.py`, run as `python3 -m ipo_agent.nse_stock_smoke`. It is a development probe, not a routine entry point and not the future fetcher. Keeping it in `ipo_agent/` lets it reuse `net.Client` and be tested with the repo's `unittest` command, while making no claim about D09: task 014 may move, replace or delete it when it chooses where the real stock fetchers live. The module docstring says this explicitly.

The module contains:

- an ordered `ENDPOINTS` registry of exactly the 12 requests above, including the two priming GETs: id, URL builder, response kind (`json`/`csv`/`html`), required fields and their paths, fixture filename (`None` for the primes), `save` flag, and `required` flag (whether a failure fails the run). The eight task data calls are `required: true`; the two primes and the two market-wide probes are `required: false`, so an optional probe's failure is recorded without masking the G1 result;
- `MAX_CALLS = len(ENDPOINTS)` and a `CallBudget`/`BudgetExceeded` guard; every request goes through `budget.spend()` before `client.get`, so an unlisted request or a 13th call stops the run with a one-line error;
- `run_entries(client, entries, budget)`: one pass in list order, catches a 403/timeout/parse error per entry and records it, then continues; data calls use the stock page as referer;
- `summarise(kind, body)`: top-level keys, row count, header, field coverage and unit;
- `trim_for_fixture(body)` and `save_fixture(...)`: the only code that writes fixtures, including the 20-row cap and the manifest described below;
- `main(argv)`: `--symbol` (default `RELIANCE`), `--pledge-symbol` (default `ADANIENT`), `--save DIR`, `--json-out FILE`, `--capture-source local|github-runner` (default `local`), `--dry-run`; prints a fixed-width table and a final `G1 candidate:` line (`PASS` if all required data calls answered, `PARTIAL` if some, `FAIL` if none); exits 1 if any required entry fails or the budget is breached. `--dry-run` prints the 12 URLs and creates no client, so the tests make no network call;
- no third-party imports, no AI, no secrets, no cookie/header output.

### 3. Fixtures and their provenance

Fixtures go under `tests/fixtures/nse_stock/`, not `data/` (which is written only by the routine), and are kept apart from task 001's IPO NSE fixtures. There is one file per data call that returned a body: `quote.json`, `results_standalone.json`, `results_consolidated.json`, `results_filings.json`, `announcements.json`, `announcements_market.json`, `shareholding.json`, `pledges.json`, `pledges_market.json`, `equity_list.csv`. The two priming GETs save nothing. JSON is saved pretty-printed with sorted keys so diffs are readable; the CSV is saved as received.

**Size cap.** `FIXTURE_MAX_ROWS = 20`. The `--save` code does the trimming; no fixture is ever trimmed by hand. For a JSON object, every list that is a direct value of the top-level object keeps its first 20 elements; for a top-level JSON list, keep the first 20; lists nested inside a kept row are left intact so the row shape survives. The CSV is saved in full. This is a faithful prefix, not a hand-picked sample. `manifest.json` records, per file: endpoint ID and URL, capture time, `captured_by` (`local` or `github-runner`) and the run URL when applicable, the original row count for each trimmed list, the saved row count, and the original and saved byte sizes. `README.md` is written from the manifest and adds the field gaps and unit notes; it is the provenance 014 reads.

**Source of the committed fixtures.** Preferred: the local build run. If the build environment cannot reach NSE, use the first successful runner artifact. The README records per file which one it was, so 014 knows whether the shape was seen from a GitHub IP. If neither the build environment nor a runner can reach NSE, the task stops short of the done-when; no fixture is invented and no endpoint is marked confirmed.

### 4. The workflow

`.github/workflows/nse-stock-smoke.yml`:

- `on: workflow_dispatch` and `on: push: branches: ["task/003-*"]` with a `paths:` filter for `ipo_agent/nse_stock_smoke.py` and `.github/workflows/nse-stock-smoke.yml`. The fixtures README is deliberately not a path: it only records provenance, and a fixture refresh is a deliberate `workflow_dispatch` or "Re-run jobs", so a docs, plan or fixture commit does not call NSE again. A fix to the probe or the workflow does trigger a fresh run.
- `permissions: contents: read`; no repository secrets; checkout only.
- `timeout-minutes: 10`; one job on `ubuntu-latest`. `actions/checkout@v4`, `actions/setup-python@v5` with `python-version: "3.12"` (pinned, not the runner's unnamed system Python), and `actions/upload-artifact@v4`, all major-version tags.
- Runs `python3 -m ipo_agent.nse_stock_smoke --save tests/fixtures/nse_stock --json-out nse-smoke.json --capture-source github-runner`. The probe reads `GITHUB_RUN_ID` and the repository URL to put the run URL in `manifest.json`; it still saves no headers or cookies.
- Uploads `nse-smoke.json` and `tests/fixtures/nse_stock/` with `actions/upload-artifact@v4`, `if: always()`, `if-no-files-found: warn`, retention 14 days.
- A `concurrency` group keyed on the ref with `cancel-in-progress: true`, so two quick pushes cannot double-call NSE.

The `push` trigger is the roadmap's pre-merge option and is chosen deliberately: it is the only way to get a GitHub-runner answer before the workflow file is on the default branch. It matches only `task/003-*`, so it goes quiet when the branch is deleted; `workflow_dispatch` remains for later re-checks. The human pushes the task branch (agents do not push), which triggers the run. To keep the calls down, the human pushes once when the build commit is ready; only when the local run is blocked is there an earlier push for the artifact. The `G1 candidate:` line, not the job colour alone, is the G1 evidence: a red job can still print `PARTIAL` when some endpoints answered. The workflow does not tick G1 itself.

**How the runner result reaches the branch.** The order is fixed:

1. DeepSeek builds and commits the probe, tests, workflow and docs (and the local fixtures if the local run works) on the task branch.
2. The human pushes `task/003-nse-stock-spike`; the `push` trigger runs the workflow.
3. The human gives DeepSeek the run URL and its `G1 candidate:` line.
4. DeepSeek records both in this plan's "Verification" and in `docs/data-sources.md` as "observed on run `<URL>`: `<line>`", commits, and sets `status: code-review`.

Ticking G1 and editing `arch.md § 9`'s runner row stay with the human on `main` after merge. If the local run supplied the fixtures, the README says so; if the runner artifact supplied them, it says "captured from a GitHub runner" with the run URL. The runner result is recorded either way.

### 5. What the build records in the docs

`docs/data-sources.md`:

- Replace the "NSE stock data (planned)" section with a confirmed table: data, confirmed endpoint, fields used (with the source path next to the `db.md` column), **unit as stated or "unit not stated"**, cadence, and quirks (cookie priming, per-symbol filter, FII/DII gap, consolidated results gap, equity list without industry).
- Include the two market-wide probes as their own rows: whether `corporate-announcements?index=equities` with a date range and `corporate-pledgedata?index=equities` answer, and whether their row shape carries the symbol. This is evidence for 018's one-call option, not a second fetcher.
- An endpoint that fails is shown as **not confirmed**, with the exact URL tried and the error. An unconfirmed URL is never written as confirmed.
- Update the summary row conditionally: if every data type in this task is confirmed, "**Decided**; endpoints confirmed in 003; fetchers in 014", keeping the overall status **Planned**. If any is unconfirmed, "**Decided**; endpoints partly confirmed in 003 (gaps: ...)" and keep **Planned**.
- Add the smoke-test line: workflow path, how it is run, and where the result is recorded. The build writes "result awaited"; after the human supplies the run URL and `G1 candidate:` line, DeepSeek updates it to "observed on run `<URL>`: `<line>`". The build must not claim a result it did not see.

`docs/tech.md`:

- Add `nse_stock_smoke` to the agent entry points as a development probe, and add the command to "Local setup".
- Update the `.github/workflows/` row to mention the NSE stock smoke test.
- Touch only those rows (entry points, `.github/workflows/`, Local setup): task 001 edits the same file, and this keeps the second merge rebasing cleanly.
- No status label changes: the stock worker and its fetchers remain **Decided**/planned.

`docs/arch.md § 9`:

- **If every endpoint in this task is confirmed:** remove the "Confirmed NSE endpoints for quotes and filings" row and add a one-line pointer to `data-sources.md`.
- **If any is failed or partial:** keep the row and narrow it to what is still unconfirmed, e.g. "Confirmed NSE endpoints for quotes and filings (unconfirmed: consolidated results, pledges)". A row that is still partly true is not removed.
- Leave the "Does NSE answer requests from GitHub's runners?" row for the human to answer from the smoke run. The build must not tick it.

### 6. Tests

`tests/test_nse_stock_smoke.py`, standard-library `unittest`, no network. It follows task 001's layout: no `tests/__init__.py`, the repo root put on `sys.path` inside the test file, and its own fixtures under `tests/fixtures/nse_stock/`; it adds no shared helper.

- The registry has exactly the 12 documented request IDs and URLs; `len(ENDPOINTS) == MAX_CALLS == 12`; the eight task data calls are marked required and the primes and market-wide probes are not. URL builders encode the symbol, use the fixed pledge symbol, and never include a secret or a cookie.
- A `CallBudget(1)` with a stub client refuses the second `spend()`, and a 13-entry synthetic registry stops before the 13th `client.get`; the stub records the calls it received.
- `main(["--dry-run"])` returns 0, prints the 12 URLs, and makes no network call (monkeypatch `Client.get` to raise if it is called).
- `summarise` handles a JSON object, a JSON list and the equity CSV; it reports the top-level shape and row count.
- `get_path` resolves the registered field paths against each fixture, and every field marked as present in `ENDPOINTS` resolves; fields marked "not in this response" are listed in a `KNOWN_GAPS` set so the gap is explicit rather than silently passing. A fixture missing for a call the summary marks `ok` is a test failure; a missing fixture for a failed call is itself a `KNOWN_GAPS` entry, and its field paths are skipped.
- **Unit handling:** a synthetic response with no unit field is recorded as `unit not stated`; a response with a `unit` field records the value. No test asserts ₹ lakh, ₹ crore or a currency.
- **Fixture cap:** `trim_for_fixture` turns a 25-row top-level list into 20 and leaves a 3-row list alone; a saved synthetic 25-row response has 20 rows and a manifest with the original count. Every top-level list (or list that is a direct value of the top-level object) in a committed JSON fixture has at most 20 elements; lists nested inside a kept row are exempt. `equity_list.csv` is saved in full and its row count matches `manifest.json`.
- `EQUITY_L.csv` has exactly the documented header.
- The summary JSON has the expected keys (`endpoint`, `ok`, `bytes`, `rows`, `fields`, `unit`, `error`) and no header/cookie fields.

The tests run with the existing command, `python3 -m unittest discover -s tests`, and add no runner or dependency.

## Steps

| # | Step | Files | Test that proves it |
| --- | --- | --- | --- |
| 1 | Add the stdlib probe, the ordered 12-entry registry, the call budget and the field-coverage helpers | `ipo_agent/nse_stock_smoke.py` | `tests/test_nse_stock_smoke.py` covers URL building, path resolution, the 12/13-call budget and `--dry-run` with no network |
| 2 | Capture one live response per data call (all 12 requests; no fallback) and write the trimmed fixtures and manifest | `tests/fixtures/nse_stock/*.json`, `tests/fixtures/nse_stock/equity_list.csv`, `tests/fixtures/nse_stock/manifest.json`, `tests/fixtures/nse_stock/README.md` | The probe run prints one row per request with `ok` and a field-coverage table; fixtures parse as UTF-8 JSON/CSV; no list is longer than 20 |
| 3 | Add fixture-shape, unit and row-cap tests, and the explicit gap list | `tests/test_nse_stock_smoke.py` | `python3 -m unittest discover -s tests` passes; every "present" path resolves in its fixture; every saved JSON fixture respects the cap |
| 4 | Add the GitHub Actions smoke workflow | `.github/workflows/nse-stock-smoke.yml` | A push to `task/003-*` (by the human) that touches the probe or the workflow runs the job; the job prints the table and uploads the artifact; no secret is referenced |
| 5 | Record the confirmed endpoints, units and field mappings, and update the open-questions row | `docs/data-sources.md`, `docs/tech.md`, `docs/arch.md` | Doc diff matches the fixtures; every `db.md` field is either mapped to a source path or marked "not in this response"; every amount has a stated unit or "unit not stated"; no unconfirmed URL is presented as confirmed |
| 6 | After the human pushes and supplies the run URL and `G1 candidate:` line, record both in this plan and `data-sources.md` | this plan, `docs/data-sources.md` | The line says "observed on run `<URL>`"; the build claims no result it did not see |
| 7 | Run the full verification and paste the output | this plan, "Verification" | `python3 -m unittest discover -s tests` and the probe output are pasted; the workflow run URL/result is the one from step 6 |

### Build order and fallbacks

1. Write the probe and its tests first, so a live failure is a clean one-line error rather than a stack trace.
2. Run the probe locally. If NSE answers, save the trimmed fixtures and manifest and commit them with the probe.
3. If the local run is blocked, add the workflow, then the human pushes the branch; download the artifact, commit the fixtures and manifest, and mark each file `captured_by: github-runner` with the run URL in the README. The workflow is added before the fixture commit in that case so the artifact exists.
4. If the GitHub run is also blocked, stop after recording the failure in the plan's "Changes during build"; do not mark endpoints confirmed and do not fill `data-sources.md` with guesses.
5. Once the build commit is ready, the human pushes for the runner evidence (step 6 above), then DeepSeek records the URL and line and sets `code-review`. The docs-only commit does not re-trigger the workflow, because `paths:` covers only the probe and the workflow.

## Data and AI

- **Tables or columns added or changed:** none. This task writes no database rows and changes no schema.
- **Settings read:** none.
- **AI calls:** none. No provider, prompt, prompt version or provenance column is touched.
- **Data written:** public NSE responses as test fixtures under `tests/fixtures/nse_stock/`, with a `manifest.json` and provenance README. Fixture top-level JSON lists are trimmed to 20 rows in the `--save` code, never by hand; the CSV is saved in full. No user data, no cookies, no headers, no secrets, no PDFs, no `data/` or `analysis/` writes.

## Doc updates

- `docs/data-sources.md`: confirmed NSE stock-data table (URLs, fields, units, cadence, quirks), the two market-wide probe results, the conditional summary row, the smoke-test line with "observed on run `<URL>`", and the FII/DII, consolidated-results and equity-industry gaps.
- `docs/tech.md`: `nse_stock_smoke` dev entry point, local command, and the `.github/workflows/` description; only those rows, because 001 edits the same file.
- `docs/arch.md § 9`: remove the "Confirmed NSE endpoints" row only if every endpoint is confirmed; otherwise keep it and narrow it to the unconfirmed ones. Leave the runner-reachability row for the human.
- **Roadmap changes for the human or Claude after merge** (`ROADMAP.md` is edited only on `main`):
  - Mark **003** Done only if every endpoint is confirmed; if partial, leave its status for the human to decide and name the gap in the task.
  - If the smoke run passes: tick **G1**, record the run URL/result in `data-sources.md` and `arch.md § 9`, and move **014** to Ready (D09 remains open and is settled at 014's plan review). Tasks **018** onwards remain blocked until 014–016 are Done and H02 is in place.
  - If the smoke run fails: leave G1 open; 014 and everything after it on the stock side stays blocked; the human decides whether to revisit ADR-0018.
  - If the fixtures show that FII/DII require XBRL parsing, add that as a note to 014's scope or a follow-up task after the build; do not decide it in this plan.
  - If `announcements_market` or `pledges_market` answers, note it as the preferred one-call shape for 018; if either fails, add a note to 014's scope, not a decision in this plan.
  - No new "Already in place" row is needed for a task deliverable.

## Decisions needed

**None for this task.** No `D..` item gates 003, and no setup step (`H..`) is needed: the workflow uses only the public NSE endpoints and a pinned `actions/setup-python` interpreter.

- **D09 (stock worker code and dependencies)** is deliberately untouched. The probe is a development tool in `ipo_agent/`, not the worker's fetcher package; 014 decides where the real fetchers live. It uses no Postgres or Gemini dependency.
- **G1** is not a decision for this plan. It is the outcome the smoke test measures. If it fails, the human's decision is whether to supersede ADR-0018, which is outside this task.
- The workflow trigger choice (push to `task/003-*` plus `workflow_dispatch`) and the fixture location (`tests/fixtures/nse_stock/`) are delegated to the plan by the roadmap and [task 001's guidance](../ROADMAP.md#001--agent-test-suite), not open product decisions.

## Risks and rollback

| Risk | How it shows | What to do / rollback |
| --- | --- | --- |
| NSE blocks GitHub runners | The workflow job fails or prints 403/timeouts; `G1 candidate: FAIL` or `PARTIAL` | Stop. The human decides whether to supersede ADR-0018; 014+ wait. The workflow/probe/fixtures can be reverted as one commit without touching product behaviour. |
| NSE blocks the build environment | The local probe run prints 403/timeouts; no fixtures in the worktree | Use the workflow artifact from the task-branch push. If both are blocked, stop and report; do not invent fixtures or fields. |
| Endpoint or field drift before 014 | A fixture no longer matches the live response in 014's tests | The fixtures and the capture date pin the shape; `data-sources.md` records the exact URL and paths. 014's parser tests fail visibly instead of the app showing wrong numbers. |
| Results data is split across endpoints | `results-comparision` has standalone numbers but not consolidated, or has no EBITDA/link | Record what each endpoint returns, mark the missing column "not in this response", and list it for 014. Do not derive consolidated figures from standalone or estimate EBITDA. |
| Shareholding JSON lacks FII/DII | The shareholding fixture has only promoter/public/employee trusts | Record the XBRL link as the only source for the split and flag it for 014; do not infer FII/DII. |
| Quote JSON lacks market cap/P/E | The base quote response has price data but no valuation | Record them as "not in this response" and list the gap for 014. Do not call `section=trade_info` in this run and do not compute market cap from price and shares without a confirmed share count. |
| Too many calls / rate limiting | A 429, or more than 12 `client.get` calls in one run | The probe uses `retries=0`, one fixed symbol list and exactly 12 registry entries; `CallBudget` raises before a 13th call and the tests prove it. The concurrency group prevents duplicate runs on quick pushes. |
| Actions minutes | The job runs on docs-only pushes | The `paths:` filter covers only the probe and the workflow; plan, code-review and fixture-provenance commits do not trigger it. A deliberate re-check uses `workflow_dispatch` or "Re-run jobs"; the job is one ~1-minute run and goes quiet when the branch is deleted. |
| Fixture too large | A market-wide response has hundreds of rows | `--save` keeps the first 20 rows of each top-level JSON list and the full CSV; `manifest.json` and the README record the original row count and bytes. A test checks every top-level list in a saved JSON fixture is at most 20. |
| Units assumed | A fixture or doc claims ₹ lakh/₹ crore without the response saying so | The probe records "unit not stated" unless the response states it; `data-sources.md` shows the same, and 014 confirms against one filing before converting. |
| Runner result not recorded | The workflow ran but the branch has no run URL or `G1 candidate:` line | The order is fixed: the human pushes and supplies both; DeepSeek records them in the plan and `data-sources.md` before setting `code-review`. |
| Parallel task 001 touches `tests/` | A merge conflict in `tests/` | Both tasks add separate files and separate fixture directories (`tests/fixtures/nse_stock/` here); this plan edits no 001 file. Whoever merges second resolves the `tests/` conflict. |
| Public data in git | Fixtures contain exchange data and public URLs | No user data, cookies, headers or secrets are saved; the fixture README states the source and capture date. |

## Revisions

| Round | What changed | In answer to |
| --- | --- | --- |
| 1 | Fixed the call list at exactly 12 requests (two primes, quote base only with no `trade_info`, three results calls, per-symbol and market-wide announcements, per-symbol and market-wide pledges, shareholding, equity list), fixed the pledge symbol at `ADANIENT`, removed all fallbacks and added a `MAX_CALLS`/`CallBudget` guard with a 12-vs-13 test. Replaced the ₹ lakh assumption with "unit not stated unless the response says it", for results and quote market cap/P/E. Added the fixed build → human push → runner URL/`G1 candidate:` line → DeepSeek records → `code-review` order, and the per-file local-vs-runner fixture provenance. Added the 20-row fixture cap in `--save` code, manifest/README row and byte counts, and a cap test. Added the `paths:` filter (probe and workflow only), pinned actions, and `setup-python@v5` with Python 3.12. Made the `arch.md § 9` and `data-sources.md` summary edits conditional on every endpoint being confirmed. Also followed the notes: market-wide announcement and pledge probes, `tests/fixtures/nse_stock/` and the 001 test layout, `tech.md` edits limited to 003's rows, and an explicit one-off-probe docstring. | Items 1–6; notes 1–4 |

## Changes during build

| Change | Why |
| --- | --- |
| Added an internal `prefer_ipv4()` context manager that filters `socket.getaddrinfo` to IPv4 for the probe's own requests | NSE publishes AAAA records that blackhole in this environment; the IPv4 path answers. This changes no URL, retry or call count |
| Used local fixtures for the nine data calls that answered; `quote` failed with `HTTP 403` and has no fixture | The plan prefers local fixtures and allows the runner artifact only when the build environment is blocked. Local was partly blocked, not wholly blocked. `quote` is recorded as **not confirmed** in `data-sources.md` and as a `KNOWN_GAPS` fixture entry |
| Corrected field paths after reading the live shapes: `results-comparision` uses `resCmpData[].re_*`; `results_filings` and `shareholding` are top-level lists; pledges uses `data[].comName`, `data[].totPromoterHolding`, `data[].numSharesPledged`, `data[].percSharesPledged`, `data[].percPromoterShares`, `data[].shp`, `data[].broadcastDt` | The planned paths were candidates. The fixtures are the evidence, and the corrected paths are what `ENDPOINTS` and `field_coverage` now test |
| Added `KNOWN_GAPS` for EBITDA and filing links in `results-comparision`, `resultDetailedDataLink` in `results_filings`, FII/DII in `shareholding`, the missing `symbol` in pledges, and the missing `quote` fixture | The plan requires a missing column to be explicit, not silently passing. The gap list is asserted by the fixture test |
| Stripped whitespace from CSV header names in `summarise` only; the saved CSV is unchanged | `EQUITY_L.csv` has spaces after commas (`NAME OF COMPANY, SERIES`). Field coverage needed the stripped names; the fixture keeps the exact bytes NSE returned |
| Recorded that `results-comparision?consolidated=true` returned a byte-identical body to standalone | The plan says to record an ignored/rejected parameter and never infer consolidated numbers. Both fixtures are kept; `data-sources.md` marks consolidated results **not confirmed** |
| Local run returned `G1 candidate: PARTIAL` (nine of ten data calls answered; `quote` 403) | The probe exits 1 when a required data call fails. The runner run [40869763010](https://github.com/badjatya/IPO/actions/runs/40869763010) returned the same result, recorded under "Verification" |

## Verification

```bash
python3 -m unittest discover -s tests
```

```text
Ran 19 tests in 0.021s

OK
```

```bash
python3 -m ipo_agent.nse_stock_smoke --dry-run
```

```text
prime_home	https://www.nseindia.com/
prime_stock	https://www.nseindia.com/get-quotes/equity?symbol=RELIANCE
quote	https://www.nseindia.com/api/quote-equity?symbol=RELIANCE
results_standalone	https://www.nseindia.com/api/results-comparision?symbol=RELIANCE
results_consolidated	https://www.nseindia.com/api/results-comparision?symbol=RELIANCE&consolidated=true
results_filings	https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Quarterly&symbol=RELIANCE
announcements	https://www.nseindia.com/api/corporate-announcements?index=equities&symbol=RELIANCE
announcements_market	https://www.nseindia.com/api/corporate-announcements?index=equities&from_date=23-10-2026&to_date=29-10-2026
shareholding	https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol=RELIANCE
pledges	https://www.nseindia.com/api/corporate-pledgedata?index=equities&symbol=ADANIENT
pledges_market	https://www.nseindia.com/api/corporate-pledgedata?index=equities
equity_list	https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv
```

```bash
python3 -m ipo_agent.nse_stock_smoke --save tests/fixtures/nse_stock --json-out /tmp/nse-smoke.json
```

```text
endpoint                 ok       bytes   rows unit               error
prime_home               False        0   None unit not stated    HTTPError: HTTP Error 403: Forbidden
prime_stock              True    147630   None unit not stated
quote                    False        0   None unit not stated    HTTPError: HTTP Error 403: Forbidden
results_standalone       True     14525      5 unit not stated
results_consolidated     True     14525      5 unit not stated
results_filings          True    101760    130 unit not stated
announcements            True   2910087   3374 unit not stated
announcements_market     True   2432858   3484 unit not stated
shareholding             True     43031     23 unit not stated
pledges                  True       670      1 unit not stated
pledges_market           True    972529   1558 unit not stated
equity_list              True    185023   2620 unit not stated
G1 candidate: PARTIAL
```

The third command makes exactly the 12 live requests and is not part of the unit tests.

Runner result, from the human's push of `task/003-nse-stock-spike` (recorded by Claude Code at the human's request, because opencode was unavailable):

```text
Runner: https://github.com/badjatya/IPO/actions/runs/40869763010
G1 candidate: PARTIAL
```

```text
endpoint                 ok       bytes   rows unit               error
prime_home               False        0   None unit not stated    HTTPError: HTTP Error 403: Forbidden
prime_stock              True    147260   None unit not stated
quote                    False        0   None unit not stated    HTTPError: HTTP Error 403: Forbidden
results_standalone       True     14525      5 unit not stated
results_consolidated     True     14525      5 unit not stated
results_filings          True    101760    130 unit not stated
announcements            True   2904372   3367 unit not stated
announcements_market     True   2461231   3525 unit not stated
shareholding             True     43031     23 unit not stated
pledges                  True       670      1 unit not stated
pledges_market           True    972529   1558 unit not stated
equity_list              True    185023   2620 unit not stated
G1 candidate: PARTIAL
```

The runner answered the same nine data calls as the local run, and `quote` failed with the same 403 in both places. The job is red because the probe exits 1 when a required call fails. The committed fixtures stay the local ones; the runner's copies are in the run's `nse-stock-smoke` artifact.
