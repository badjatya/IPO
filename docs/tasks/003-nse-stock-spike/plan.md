---
task: 003-nse-stock-spike
status: plan-review
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
  - Save one parsed response per endpoint (or per endpoint variant actually used) under `tests/fixtures/nse/`, with a short provenance README (capture date, symbol, GitHub run URL).
  - Add a small standard-library probe (`ipo_agent/nse_stock_smoke.py`) that makes one request per endpoint, prints a table and a field-coverage report, and can write the fixtures and a JSON summary.
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

### 1. What "confirmed" means

The probe calls each candidate endpoint once with one symbol per data type (`RELIANCE` by default; the pledge probe uses a company that has a pledge, as described in the table), after priming NSE's cookies with one GET to the homepage and one GET to a stock page. It uses `net.Client(timeout=30, retries=0)`, so a block is measured as a block and the "one call per endpoint" rule holds. It records, for each response:

- the exact URL and query string (public data; no headers or cookies),
- success or the HTTP/network error,
- response size and elapsed time,
- the top-level shape (JSON keys, list length, CSV header and row count),
- a **field-coverage table**: for every column the future fetcher needs, the JSON/CSV path in this response and whether it was found. A missing column is recorded as "not in this response", never estimated.

The candidate endpoints are below. The build records the exact one that answered in `data-sources.md`; the alternate is only tried if the primary fails, never in a loop.

| Data | Primary candidate | What to look for |
| --- | --- | --- |
| Quote | `https://www.nseindia.com/api/quote-equity?symbol=RELIANCE` | `priceInfo.lastPrice`, `priceInfo.change`, `priceInfo.pChange`, `priceInfo.weekHighLow`; market cap and P/E (in the base response or in a `section=trade_info` call); `securityInfo` (symbol, ISIN); `industryInfo` (sector/industry). Fallback candidate only if the base call is blocked: NSE's `/api/NextApi/apiClient/GetQuoteApi?functionName=getSymbolData&marketType=N&series=EQ&symbol=RELIANCE`. |
| Quarterly results, standalone | `https://www.nseindia.com/api/results-comparision?symbol=RELIANCE` (NSE's spelling) | `resCmpData[]`: date, income, expenditure, net profit, EPS; whether other income, EBITDA and a filing link are present. Record the unit (NSE returns this endpoint's amounts in ₹ lakh; 014 converts to ₹ crore in code, never in the fixture). |
| Quarterly results, consolidated | `https://www.nseindia.com/api/results-comparision?symbol=RELIANCE&consolidated=true` | Same fields for the consolidated basis. If the endpoint ignores or rejects the parameter, record that and use the filing-metadata endpoint below; do not infer consolidated numbers from standalone. |
| Results filing metadata | `https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Quarterly&symbol=RELIANCE` | Period start/end, `consolidated` flag, audited flag, filed/broadcast time, XBRL/details link. This is the candidate source for `quarterly_results.filed_at` and `source_url`. |
| Corporate announcements | `https://www.nseindia.com/api/corporate-announcements?index=equities&symbol=RELIANCE` | `symbol`, subject (`desc`), announcement time (`an_dt`), title (`attchmntText`), attachment (`attchmntFile`), exchange ID (`seq_id`/`orgid`), industry (`smIndustry`). |
| Shareholding pattern | `https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol=RELIANCE` | As-on date, submission/filing date, promoter & promoter group (`pr_and_prgrp`), public (`public_val`), employee trusts, XBRL link. Explicitly check whether FII and DII splits are present; if they are not, record that they are only in the XBRL filing. |
| Promoter pledges | `https://www.nseindia.com/api/corporate-pledgedata?index=equities&symbol=ADANIENT` | Promoter holding, pledged shares, pledged % of promoter holding, disclosure/quarter date. If the symbol returns no rows, make one market-wide call (`?index=equities`) to choose a company that has a pledge, then one per-symbol call; record the chosen symbol. |
| Listed equities | `https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv` | Header: `SYMBOL`, `NAME OF COMPANY`, `SERIES`, `DATE OF LISTING`, `PAID UP VALUE`, `MARKET LOT`, `ISIN NUMBER`, `FACE VALUE`. Note: no industry and no explicit active flag; record that for 015. |

### 2. Where the code lives

Add `ipo_agent/nse_stock_smoke.py`, run as `python3 -m ipo_agent.nse_stock_smoke`. It is a development probe, not a routine entry point and not the future fetcher. Keeping it in `ipo_agent/` lets it reuse `net.Client` and be tested with the repo's `unittest` command, while making no claim about D09: task 014 may move or replace it when it chooses where the real stock fetchers live.

The module contains:

- an `ENDPOINTS` registry: id, URL builder, response kind (`json`/`csv`), required fields and their paths, fixture filename;
- `prime(client)`: one GET to `https://www.nseindia.com/` and one to a stock page, catching the expected 403 that still sets cookies (the same behaviour as `ipo_agent/nse.py`);
- `summarise(kind, body)`: top-level keys, row count, header, field coverage;
- `main(argv)`: `--symbol`, `--save DIR`, `--json-out FILE`, `--dry-run`; prints a fixed-width table and a final `G1 candidate: PASS / PARTIAL / FAIL`; exits 1 if any required endpoint fails; `--dry-run` prints URLs and makes no network call (used by the tests);
- no third-party imports, no AI, no secrets, no cookie/header output.

### 3. Fixtures and their provenance

Fixtures go under `tests/fixtures/nse/`, not `data/` (which is written only by the routine). One file per endpoint variant that actually answered, e.g. `quote.json`, `results_standalone.json`, `results_consolidated.json`, `results_filings.json`, `announcements.json`, `shareholding.json`, `pledges.json`, `equity_list.csv`. JSON is saved pretty-printed with sorted keys so diffs are readable; the CSV is saved as received.

`tests/fixtures/nse/README.md` records, for each file: endpoint URL, symbol, capture date, GitHub run URL (if captured on a runner), and any field gaps. This is the provenance that lets 014 trust the fixture and lets the human see what the smoke test actually returned.

If the build environment cannot reach NSE, the workflow's artifact is the source of the fixtures: the human or DeepSeek downloads the artifact and commits the files. If neither the build environment nor the runner can reach NSE, the task stops short of the done-when; no fixture is invented and no endpoint is marked confirmed.

### 4. The workflow

`.github/workflows/nse-stock-smoke.yml`:

- `on: workflow_dispatch` and `on: push: branches: ["task/003-*"]`.
- `permissions: contents: read`; no repository secrets; checkout only.
- `timeout-minutes: 10`; one job on `ubuntu-latest` with Python 3.12.
- Runs `python3 -m ipo_agent.nse_stock_smoke --save tests/fixtures/nse --json-out nse-smoke.json`.
- Uploads `nse-smoke.json` and `tests/fixtures/nse/` with `actions/upload-artifact`, `if: always()`, `if-no-files-found: warn`, retention 14 days.
- A `concurrency` group keyed on the ref with `cancel-in-progress: true`, so two quick pushes cannot double-call NSE.

The `push` trigger is the roadmap's pre-merge option and is chosen deliberately: it is the only way to get a GitHub-runner answer before the workflow file is on the default branch. It matches only `task/003-*`, so it goes quiet when the branch is deleted; `workflow_dispatch` remains for later re-checks. The human pushes the task branch (agents do not push), which triggers the run. The workflow's red/green result is the G1 evidence; it does not tick G1 itself.

### 5. What the build records in the docs

`docs/data-sources.md`:

- Replace the "NSE stock data (planned)" section with a confirmed table: data, confirmed endpoint, fields used (with the source path next to the `db.md` column), cadence, and quirks (cookie priming, per-symbol filter, FII/DII gap, consolidated results gap, equity list without industry).
- Update the summary row from "**Decided**; endpoints to confirm" to "**Decided**; endpoints confirmed in 003; fetchers in 014", keeping the overall status **Planned**.
- Add the smoke-test line: workflow path, how it is run, and where the result is recorded. The actual pass/fail and run URL are added by the human after the runner answers; the build must not claim a result it did not see.

`docs/tech.md`:

- Add `nse_stock_smoke` to the agent entry points as a development probe, and add the command to "Local setup".
- Update the `.github/workflows/` row to mention the NSE stock smoke test.
- No status label changes: the stock worker and its fetchers remain **Decided**/planned.

`docs/arch.md § 9`:

- Remove the "Confirmed NSE endpoints for quotes and filings" row (this task closes it) and add a one-line pointer to `data-sources.md`.
- Leave the "Does NSE answer requests from GitHub's runners?" row for the human to answer from the smoke run. The build must not tick it.

### 6. Tests

`tests/test_nse_stock_smoke.py`, standard-library `unittest`, no network:

- URL builders produce the documented URLs, encode the symbol, and never include a secret or a cookie.
- `summarise` handles a JSON object, a JSON list and the equity CSV; it reports the top-level shape and row count.
- `get_path` resolves the registered field paths against each fixture, and every field marked as present in `ENDPOINTS` resolves; fields marked "not in this response" are listed in a `KNOWN_GAPS` set so the gap is explicit rather than silently passing.
- `EQUITY_L.csv` has exactly the documented header.
- The summary JSON has the expected keys (`endpoint`, `ok`, `bytes`, `rows`, `fields`, `error`) and no header/cookie fields.
- `main(["--dry-run"])` returns 0 and prints URLs without calling `net.Client` (monkeypatch `Client.get` to raise if it is called).

The tests run with the existing command, `python3 -m unittest discover -s tests`, and add no runner or dependency.

## Steps

| # | Step | Files | Test that proves it |
| --- | --- | --- | --- |
| 1 | Add the stdlib probe, endpoint registry and field-coverage helpers | `ipo_agent/nse_stock_smoke.py` | `tests/test_nse_stock_smoke.py` covers URL building, path resolution and `--dry-run` with no network |
| 2 | Capture one live response per endpoint (primary, plus a fallback only where the primary fails) | `tests/fixtures/nse/*.json`, `tests/fixtures/nse/equity_list.csv`, `tests/fixtures/nse/README.md` | The probe run prints one row per endpoint with `ok` and a field-coverage table; fixtures parse as UTF-8 JSON/CSV |
| 3 | Add fixture-shape tests and the explicit gap list | `tests/test_nse_stock_smoke.py` | `python3 -m unittest discover -s tests` passes; every "present" path resolves in its fixture |
| 4 | Add the GitHub Actions smoke workflow | `.github/workflows/nse-stock-smoke.yml` | A push to `task/003-*` (by the human) runs the workflow; the job prints the table and uploads the artifact; no secret is referenced |
| 5 | Record the confirmed endpoints and field mappings, and update the open-questions row | `docs/data-sources.md`, `docs/tech.md`, `docs/arch.md` | Doc diff matches the fixtures; every `db.md` field is either mapped to a source path or marked "not in this response"; no unconfirmed URL is presented as confirmed |
| 6 | Run the full verification and paste the output | this plan, "Verification" | `python3 -m unittest discover -s tests` and the probe output are pasted; the workflow run URL/result is added by the human after the run |

### Build order and fallbacks

1. Write the probe and its tests first, so a live failure is a clean one-line error rather than a stack trace.
2. Run the probe locally. If NSE answers, save the fixtures and commit them with the probe.
3. If the local run is blocked, push the branch (the human does this) with the workflow in step 4, download the artifact, and commit the fixtures. The workflow is added before the fixture commit in that case so the artifact exists.
4. If the GitHub run is also blocked, stop after recording the failure in the plan's "Changes during build"; do not mark endpoints confirmed and do not fill `data-sources.md` with guesses.

## Data and AI

- **Tables or columns added or changed:** none. This task writes no database rows and changes no schema.
- **Settings read:** none.
- **AI calls:** none. No provider, prompt, prompt version or provenance column is touched.
- **Data written:** public NSE responses as test fixtures under `tests/fixtures/nse/`, with a provenance README. No user data, no cookies, no headers, no secrets, no PDFs, no `data/` or `analysis/` writes.

## Doc updates

- `docs/data-sources.md`: confirmed NSE stock-data table (URLs, fields, cadence, quirks), summary-row status, smoke-test line, and the FII/DII, consolidated-results and equity-industry gaps.
- `docs/tech.md`: `nse_stock_smoke` dev entry point, local command, and the `.github/workflows/` description.
- `docs/arch.md § 9`: remove the "Confirmed NSE endpoints" row; leave the runner-reachability row for the human.
- **Roadmap changes for the human or Claude after merge** (`ROADMAP.md` is edited only on `main`):
  - Mark **003** Done.
  - If the smoke run passes: tick **G1**, record the run URL/result in `data-sources.md` and `arch.md § 9`, and move **014** to Ready (D09 remains open and is settled at 014's plan review). Tasks **018** onwards remain blocked until 014–016 are Done and H02 is in place.
  - If the smoke run fails: leave G1 open; 014 and everything after it on the stock side stays blocked; the human decides whether to revisit ADR-0018.
  - If the fixtures show that FII/DII require XBRL parsing, add that as a note to 014's scope or a follow-up task after the build; do not decide it in this plan.
  - No new "Already in place" row is needed for a task deliverable.

## Decisions needed

**None for this task.** No `D..` item gates 003, and no setup step (`H..`) is needed: the workflow uses only the public NSE endpoints and the runner's built-in Python.

- **D09 (stock worker code and dependencies)** is deliberately untouched. The probe is a development tool in `ipo_agent/`, not the worker's fetcher package; 014 decides where the real fetchers live. It uses no Postgres or Gemini dependency.
- **G1** is not a decision for this plan. It is the outcome the smoke test measures. If it fails, the human's decision is whether to supersede ADR-0018, which is outside this task.
- The workflow trigger choice (push to `task/003-*` plus `workflow_dispatch`) and the fixture location (`tests/fixtures/nse/`) are delegated to the plan by the roadmap and [task 001's guidance](../ROADMAP.md#001--agent-test-suite), not open product decisions.

## Risks and rollback

| Risk | How it shows | What to do / rollback |
| --- | --- | --- |
| NSE blocks GitHub runners | The workflow job fails or prints 403/timeouts; `G1 candidate: FAIL` or `PARTIAL` | Stop. The human decides whether to supersede ADR-0018; 014+ wait. The workflow/probe/fixtures can be reverted as one commit without touching product behaviour. |
| NSE blocks the build environment | The local probe run prints 403/timeouts; no fixtures in the worktree | Use the workflow artifact from the task-branch push. If both are blocked, stop and report; do not invent fixtures or fields. |
| Endpoint or field drift before 014 | A fixture no longer matches the live response in 014's tests | The fixtures and the capture date pin the shape; `data-sources.md` records the exact URL and paths. 014's parser tests fail visibly instead of the app showing wrong numbers. |
| Results data is split across endpoints | `results-comparision` has standalone numbers but not consolidated, or has no EBITDA/link | Record what each endpoint returns, mark the missing column "not in this response", and list it for 014. Do not derive consolidated figures from standalone or estimate EBITDA. |
| Shareholding JSON lacks FII/DII | The shareholding fixture has only promoter/public/employee trusts | Record the XBRL link as the only source for the split and flag it for 014; do not infer FII/DII. |
| Quote JSON lacks market cap/P/E | The base quote response has price data but no valuation | Record whether a `section=trade_info` call supplies them; if not, mark the columns as missing for 014. Do not compute them from price and shares without a confirmed share count. |
| Too many calls / rate limiting | The workflow prints more than one call per endpoint, or a 429 | The probe uses `retries=0`, one symbol and one call per endpoint (plus a fallback only on failure); no loops. The concurrency group prevents duplicate runs on quick pushes. |
| Actions minutes | The job is red on every task-branch push | The push filter matches only `task/003-*` and the job is one ~1-minute run; it goes quiet when the branch is deleted. `workflow_dispatch` is the only remaining trigger. |
| Parallel task 001 touches `tests/` | A merge conflict in `tests/` | Both tasks add separate files; this plan edits no 001 file. Whoever merges second resolves the `tests/` conflict. |
| Public data in git | Fixtures contain exchange data and public URLs | No user data, cookies, headers or secrets are saved; the fixture README states the source and capture date. |

## Revisions

| Round | What changed | In answer to |
| --- | --- | --- |
| | | |

## Changes during build

None yet.

## Verification

Not run yet: this is the planning step. During the build, run and paste here:

```bash
python3 -m unittest discover -s tests
python3 -m ipo_agent.nse_stock_smoke --dry-run
python3 -m ipo_agent.nse_stock_smoke --save tests/fixtures/nse --json-out /tmp/nse-smoke.json
```

The third command hits live NSE once per endpoint and is not part of the unit tests. The GitHub workflow run URL and its `G1 candidate:` line go in `docs/data-sources.md` and in this section once the human has run it.
