# Data sources

Every external source the system reads: what we take from it, how often, what goes wrong, and the fallback. Fetching happens in the IPO routine (IPO sources) and in the stock worker (NSE stock data), both with the same standard-library Python fetchers. The web app never calls these sources ([arch.md](arch.md#3-containers)).

## Summary

| Source | Used for | Status | Code |
| --- | --- | --- | --- |
| Investorgain | IPO list, dates, price band, lot, issue size, GMP (with low/high), P/E | **Running** | `ipo_agent/investorgain.py` |
| NSE (`www.nseindia.com`) | Current and upcoming issues, issue details, subscription by category, listing-day prices | **Running** | `ipo_agent/nse.py`, `ipo_agent/outcomes.py` |
| NSE archives (`nsearchives.nseindia.com`) | RHP, ratios and anchor report downloads | **Running** | `ipo_agent/rhp.py` |
| SEBI | RHPs filed with the RoC, before NSE lists the issue | **Running** | `ipo_agent/sebi.py` |
| Web search (inside the routine) | Anchor investor lists, company news, numbers NSE didn't return | **Running** | `ROUTINE.md` steps 1, 2 and 2b |
| NSE stock data | Quotes, quarterly results, announcements, shareholding, pledges | **Decided**; fetchers built in 014 (`stock_worker/`), worker planned (018); quote still **not confirmed** (014's 2026-10-30 probe: no candidate answered, each error recorded below), consolidated re-checked in the same run and confirmed identical | `stock_worker/` |

The routine's network allowlist covers `www.nseindia.com`, `nsearchives.nseindia.com`, `www.investorgain.com`, `www.sebi.gov.in` and `www.bseindia.com` ([SETUP.md](../SETUP.md)).

## Investorgain

| | |
| --- | --- |
| What | The live IPO GMP report (`/report/live-ipo-gmp/331/`): the list of IPOs, dates, price, GMP and its range, P/E |
| Filter | Mainboard only ([ADR-0008](adr/0008-mainboard-only.md)); rows are tagged `mainboard` or `sme` and SME rows are dropped |
| Cadence | Every run (09:07 and 19:07 IST) |
| Caveat | GMP is an unofficial grey-market quote. It is shown as a signal, with its own update time, never as fact |
| Failure | Page layout changes break the parser. The error is reported in the snapshot's `errors` and the run continues on NSE data |

## NSE

| Endpoint | Used for |
| --- | --- |
| `/api/ipo-current-issue` | Issues open now |
| `/api/all-upcoming-issues?category=ipo` | Upcoming issues |
| `/api/ipo-detail?symbol=…&series=…` | Price band, lot, issue size text, lead managers, registrar, RHP, ratios and anchor report links, subscription by category |
| `/api/historicalOR/generateSecurityWiseHistoricalData?…` | Listing-day open, high, low and close for the scorecard |
| `nsearchives…/content/ipo/RHP_<SYMBOL>.zip` | RHP download |

| | |
| --- | --- |
| Access | NSE wants a browser-like session. `net.py` loads an HTML page first to get cookies, then calls `/api/*` with browser headers and retries |
| Filter | Series `EQ` and `BE` are mainboard; the SME series is dropped |
| Failure | NSE often blocks cloud IPs. The snapshot reports the error; Claude fills the gaps from web search and the brief says which numbers came from where. Listing prices that aren't out yet are retried next run, or can be set by hand: `python3 -m ipo_agent.outcomes --set <key> listing=<price> close=<price>` |

## SEBI

| | |
| --- | --- |
| What | SEBI's list of offer documents filed with the RoC |
| Why | The RHP often appears here days before NSE publishes the issue, so the analysis can be ready before bidding opens |
| Failure | No match means `rhp_url` stays null; the IPO shows "analysis pending: RHP not filed" and is checked again next run |

## Web search

| | |
| --- | --- |
| What | Anchor investors (allocated the working day before an IPO opens), recent company news, missing numbers |
| Rule | Results are cited; numbers from search are labelled as such in the brief |
| Limit | In the routine's environment, web *fetch* can't reach most news sites, but web *search* works |

## NSE stock data

Needed for the watchlist ([plan.md](plan.md#watchlist-signals)). The smoke probe in task 003 made one fixed 12-request run on 2026-10-29 local time. It confirmed the endpoints below except where marked **not confirmed**; task 014 turned the confirmed paths into the `stock_worker/` fetchers (one module per source, plain records keyed by the `db.md` columns, missing fields `None`). The results API's amounts are **₹ lakh** — confirmed in 014 against RELIANCE's own note text (see the results row) — and the fetcher converts them to crore inside the parser. Other responses state no unit; **unit not stated** means the response did not say whether a value is rupees, lakh or crore. No headers, cookies or secrets are stored in the fixtures.

| Data | Confirmed endpoint | Fields used (`db.md` ← source path) | Unit | Cadence | Quirks |
| --- | --- | --- | --- | --- | --- |
| Quote | **Not confirmed.** `GET https://www.nseindia.com/api/quote-equity?symbol=RELIANCE` returned `HTTP 403 Forbidden` locally and from a GitHub runner (run 40869763010), and 014's one deliberate probe (`python3 -m stock_worker.probe`, RELIANCE, a budgeted run of 6 calls) ran once on 2026-10-30 with no candidate answering — the run's exact table:<br>`stock_page_embedded` — ok `False` — no embedded quote JSON found in the stock page<br>`nextapi` — ok `False` — unprobed: the stock page carries no _next/data URL<br>`trade_info` — ok `False` — HTTPError: HTTP Error 403: Forbidden<br>`cookie_order` — ok `False` — HTTPError: HTTP Error 403: Forbidden<br>`quote source: none (see table errors)`; `consolidated re-check: identical` | Expected: `stocks.symbol`/`isin` ← `securityInfo.symbol`/`securityInfo.isin`; `stock_quotes.price` ← `priceInfo.lastPrice`; `change_pct` ← `priceInfo.pChange`; `week52_high`/`low` ← `priceInfo.weekHighLow.weekHigh`/`weekLow`; market cap and P/E only if the base response states them. None confirmed | unit not stated | Every run | The stock page (`/get-quotes/equity?symbol=RELIANCE`) answered 200, but the base quote API returned 403 from both places and the probe's other candidates failed too, so the failure is specific to this endpoint. Until a working source is found, `fetch_quote` (`stock_worker/quote.py`) raises `SourceError` pointing at this record and `fetch_all` reports it in `errors`; no `stock_quotes` row is ever fabricated and no price is estimated. The **NextApi** candidate is recorded honestly: the probe read the `_next/data/<buildId>/…` quote route from the prime page's HTML and the page carried none, so NSE's `/api/NextApi/…` paths themselves were **not** tried — that candidate stays **unprobed** for a later task |
| Financial results, standalone | `GET https://www.nseindia.com/api/results-comparision?symbol=RELIANCE` | `quarterly_results.period_end` ← `resCmpData[].re_to_dt`; `revenue_cr` ← `resCmpData[].re_net_sale` (`None` when absent — `re_total_inc` includes other income, kept in its own column, and is never used as revenue); `other_income_cr` ← `resCmpData[].re_oth_inc_new` (fallback `re_oth_inc`); `expenses_cr` ← `resCmpData[].re_oth_tot_exp`; `pat_cr` ← `resCmpData[].re_net_profit`; `eps` ← `resCmpData[].re_basic_eps_for_cont_dic_opr` | **₹ lakh** (recorded in 014): the response states no unit field, but its own note text does — the first RELIANCE fixture row's `re_desc_note_seg` says "Net Revenue is Rs 128,260 crore" and `re_net_sale` is 12,826,000, so 12,826,000 lakh = 128,260 crore. The fetcher divides every amount by 100 via the tested `to_crore` helper; record keys are the `*_cr` db.md columns. EPS is ₹ per share and is **not** converted (a test pins it) | Daily check; new rows only | EBITDA and a filing link are **not in this response**. 014 derives operating EBITDA, excluding other income, in code: `revenue − (total expenses − finance costs − depreciation)` from `re_net_sale`, `re_oth_tot_exp`, `re_int_new`, `re_depr_und_exp` — `None` unless all four are stated (a stated `0` is a value); the fixture's first row: 12,826,000 − (11,987,700 − 237,100 − 445,900) = 1,521,300 lakh → `Decimal("15213.00")` crore. `filed_at`/`source_url` come only from the filings row with the same `toDate` and `consolidated == "Non-Consolidated"`; without such a row both are `None`. `consolidated` is always `False` for comparison rows. `period_start` (`re_from_dt`) and `audited` (the matched filing's) stay in the record as extras. The first response has 5 quarters |
| Financial results, consolidated | `GET https://www.nseindia.com/api/results-comparision?symbol=RELIANCE&consolidated=true` | Same paths as standalone | unit not stated | Daily check; new rows only | **Consolidated numbers not confirmed — gap confirmed by 014's probe.** The response was byte-for-byte identical to standalone in 003, and 014's re-check under the same 2026-10-30 probe recorded `identical` again (the endpoint still returns the standalone body; `consolidated=true` is ignored), so `results.py` returns **no consolidated rows** and a gap flag (`parse_consolidated`) — standalone figures are never relabelled. The `Consolidated` *filings* rows (results_filings) each carry an XBRL link, a likely consolidated source for a later task. 016's alert rules must not compare consolidated against standalone |
| Results filings | `GET https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Quarterly&symbol=RELIANCE` | `quarterly_results.period_end` ← `[].toDate`; period start ← `[].fromDate`; `consolidated` ← `[].consolidated` (string, e.g. `Non-Consolidated`); `audited` ← `[].audited` (string); `filed_at` ← `[].filingDate` or `[].broadCastDate`; `source_url` ← `[].xbrl` | unit not stated | Daily check; new rows only | The join rule (014): only the `Non-Consolidated` filings row with the same `toDate` supplies `filed_at`, `source_url` and the `audited` extra; with no such row all three are `None`. `resultDetailedDataLink` was null in all sampled rows; the XBRL link is present. Values are strings, not booleans, so 014 maps them |
| Corporate announcements, per symbol | `GET https://www.nseindia.com/api/corporate-announcements?index=equities&symbol=RELIANCE` | `announcements.symbol` ← `[].symbol`; subject ← `[].desc`; announced_at ← `[].an_dt`; title ← `[].attchmntText`; attachment ← `[].attchmntFile`; exchange_ref ← `[].seq_id`; industry ← `[].smIndustry` | unit not stated | Every run; new rows only | The response has 3,374 rows for one symbol; 014's fetcher keeps the response as one call and filters in code — an optional `since` (ISO timestamp) drops rows announced before it |
| Corporate announcements, market-wide | `GET https://www.nseindia.com/api/corporate-announcements?index=equities&from_date=<DD-MM-YYYY>&to_date=<DD-MM-YYYY>` | Same paths as per-symbol; each row carries `symbol` | unit not stated | Every run; new rows only | One fixed call with the run date and six days earlier answered (3,484 rows). The date format `DD-MM-YYYY` is accepted. Evidence for 018's one-call option; not a second fetcher |
| Shareholding pattern | `GET https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol=RELIANCE` | `shareholding.quarter_end` ← `[].date`; filed_at ← `[].submissionDate`; `promoter_pct` ← `[].pr_and_prgrp`; `public_pct` ← `[].public_val`; `other_pct` ← `[].employeeTrusts`; source ← `[].xbrl` | unit not stated | Quarterly; daily check | **FII and DII splits are not in this response**; only the XBRL filing carries them. 014's fetcher returns `fii_pct`/`dii_pct` missing (`None`) and parses them when a future response adds them. XBRL parsing is a recorded gap for 016/018 and must exist before `fii_move`/`dii_move` alerts can fire. `filed_at` is `submissionDate` — a date only in the sampled rows — so the record keeps the ISO date exactly as stated, no time invented |
| Pledged shares, per symbol | `GET https://www.nseindia.com/api/corporate-pledgedata?index=equities&symbol=ADANIENT` | `shareholding.promoter_pledged_pct` ← computed in code as `numSharesPledged / totPromoterHolding × 100` (no field carries it); `promoter_pct` ← `data[].percPromoterHolding`; promoter shares held ← `data[].totPromoterHolding`; pledged shares ← `data[].numSharesPledged`; quarter end ← `data[].shp`; disclosed_at ← `data[].broadcastDt`; company ← `data[].comName` | unit not stated | Daily check | **The row has no `symbol`**, only `comName`; 014's record carries the company name and never a made-up symbol — name→symbol resolution is the caller's (015's `EQUITY_L.csv`). **`percSharesPledged` is not the share of promoter holding**: the fixture shows it is pledged ÷ demat shares (ADANIENT: 21,723,685 / 1,353,182,590 = 1.61), so the fetcher computes `promoter_pledged_pct` = `numSharesPledged / totPromoterHolding × 100`, rounded half-up to 2 dp (2.23), and keeps `percSharesPledged` raw as the `pledged_pct_of_total` extra. `percPromoterShares` is also not the pledge. A row with zero promoter holding yields `promoter_pledged_pct = None`, never a division error. Values are strings, some with leading spaces (stripped) |
| Pledged shares, market-wide | `GET https://www.nseindia.com/api/corporate-pledgedata?index=equities` | Same paths as per-symbol | unit not stated | Daily check | One fixed call answered (1,558 rows). **Rows have no `symbol`**, only `comName`, and quarter-ends vary within one response; a market-wide fetch needs a name-to-symbol map from `EQUITY_L.csv` (015). Evidence for 018's one-call option |
| Equity list | `GET https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv` | `stocks.symbol` ← `SYMBOL`; name ← `NAME OF COMPANY`; `ISIN NUMBER`; `SERIES`; `DATE OF LISTING`; `PAID UP VALUE`; `MARKET LOT`; `FACE VALUE` | unit not stated | On demand / daily | **No industry and no explicit active flag**; 015 must source industry elsewhere or leave it null. The header has spaces after commas in the raw CSV; the probe strips them for comparison |

**Smoke test.** `.github/workflows/nse-stock-smoke.yml` runs the probe on a `push` to `task/003-*` (only when the probe or workflow changes) and on `workflow_dispatch`; it uploads `nse-smoke.json` and `tests/fixtures/nse_stock/` as the `nse-stock-smoke` artifact. Observed on run [40869763010](https://github.com/badjatya/IPO/actions/runs/40869763010): `G1 candidate: PARTIAL`. From a GitHub runner, the same nine data calls answered as locally, and `quote` returned the same HTTP 403. The human ticked G1 on 2026-10-29: NSE answers from GitHub's runners, and the quote endpoint is left to task 014.

**Worker host and NSE.** NSE blocks some cloud IP ranges. If the stock worker runs on GitHub Actions ([ADR-0018](adr/0018-stock-worker-on-github-actions.md)), a week-1 smoke test must confirm that NSE answers from GitHub's runners before anything is built on it. The local run and a GitHub runner gave the same result: nine of the ten data calls answered, and the quote endpoint returned 403 in both places, so the quote failure is not a runner block.

## Rules for every source

- **One source failing doesn't stop the run.** Each fetcher reports its error, and the snapshot carries on with what it has.
- **Report where every number came from.** The snapshot keeps the source (`rhp_source`, `subscription_source`, `price_source`), and the brief labels web-search figures.
- **Be gentle.** Each run reads a source a few times, twice a day. There is no polling and no parallel scraping.
- **Keep raw documents out of the database.** RHP text lives in git; filing PDFs stay at the exchange and only links are stored.
