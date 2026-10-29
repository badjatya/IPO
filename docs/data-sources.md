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
| NSE stock data | Quotes, quarterly results, announcements, shareholding, pledges | **Decided**; endpoints to confirm; fetched by the stock worker | Planned |

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

## NSE stock data (planned)

Needed for the watchlist ([plan.md](plan.md#watchlist-signals)). Each endpoint will be confirmed against NSE before we build on it, and recorded here.

| Data | Fields needed | Cadence |
| --- | --- | --- |
| Quote | Price, change, 52-week high and low, market cap, P/E | Every run |
| Financial results | Quarterly revenue, expenses, EBITDA, PAT, EPS; standalone and consolidated; filing link | Daily check; new rows only |
| Corporate announcements | Exchange ID, time, subject, title, attachment link | Every run; new rows only |
| Shareholding pattern | Promoter, FII, DII, public; quarter | Quarterly; daily check |
| Pledged shares | Promoter shares pledged | Daily check |

**Worker host and NSE.** NSE blocks some cloud IP ranges. If the stock worker runs on GitHub Actions ([ADR-0018](adr/0018-stock-worker-on-github-actions.md)), a week-1 smoke test must confirm that NSE answers from GitHub's runners before anything is built on it.

## Rules for every source

- **One source failing doesn't stop the run.** Each fetcher reports its error, and the snapshot carries on with what it has.
- **Report where every number came from.** The snapshot keeps the source (`rhp_source`, `subscription_source`, `price_source`), and the brief labels web-search figures.
- **Be gentle.** Each run reads a source a few times, twice a day. There is no polling and no parallel scraping.
- **Keep raw documents out of the database.** RHP text lives in git; filing PDFs stay at the exchange and only links are stored.
