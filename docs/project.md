# Project

_Working name: IPO research agent. The final product name is still open._

A research app for Indian retail investors. AI agents read IPO prospectuses and company filings and turn them into short, sourced briefs: Claude for IPOs, Gemini for listed stocks. Investors get a clear call on each IPO and a watch on the stocks they care about, without reading 400-page documents or hundreds of exchange announcements.

- **Running since 2026-10-12:** the mainboard IPO agent. It sends an email brief twice every weekday and scores its own calls against real listings.
- **Being built during the hackathon:** a multi-user web app with a stock watchlist, IPO pages and the track record. See [plan.md](plan.md).

How it's built: [arch.md](arch.md) (architecture), [tech.md](tech.md) (stack), [db.md](db.md) (database), [ai.md](ai.md) (AI design), [data-sources.md](data-sources.md), [adr/](adr/README.md) (decisions).

## Problem

Indian retail investors face two jobs that take far more time than most of them have.

**Deciding on IPOs.** In a busy week, several mainboard IPOs are open at once. To judge one properly, an investor has to read a Red Herring Prospectus (RHP) of several hundred pages: what the business does, its financials, who is selling shares, what the money is for, the valuation against listed peers, and the risk factors. They also have to check the quality of the anchor investors, the grey market premium (GMP) and live subscription by category. Then they have to work out where to apply: Retail, small HNI or big HNI. Allotment is a lottery, and the best odds per rupee blocked change every day. Most people end up following a tip or a GMP number with no idea why.

**Following stocks they already own.** Listed companies file quarterly results, shareholding patterns and a steady stream of announcements with the exchanges. Most announcements are routine. A few matter a lot: a large order, an acquisition, an auditor resigning, promoters pledging more shares. Investors either try to read everything and give up, or miss the filing that mattered.

Both jobs are reading and judgement, done again and again on fresh documents. That is work an AI agent can do well, as long as the numbers stay exact and every claim traces back to a source.

## Solution

**What an investor gets:**
- **An IPO brief twice every weekday**, now by email and soon in the web app:
  - every mainboard IPO that is open, closing or upcoming, with its dates, price band, GMP and live subscription by category
  - a short analysis from the RHP: what the business does, financials, the share split between categories, positives, red flags and the anchor book graded Strong, Average or Weak
  - a verdict: Apply, Listing gains only, Neutral or Avoid
  - the best category to apply in, with allotment odds worked out from live subscription
- **A track record.** After every listing, the agent records how the IPO listed against its call and against GMP. Users can see how good the calls are, and the agent can see it too.
- **A stock watchlist** (being built). Each user adds the stocks they follow and gets:
  - quarterly results summarised, with trends
  - an announcements digest that drops routine filings and explains the ones that matter
  - alerts on changes in promoter, FII and DII holdings and on promoter pledges
- **Stock analysis on request** (being built). A user can ask for a full analysis of any listed stock: business, financials, valuation, shareholding, red flags. If a recent analysis exists, it opens at once. If not, or if it's out of date, research starts in the background and a loading screen shows each step as it happens, usually within about 15 minutes. Each person can request 3 analyses a month, and every request counts.
- **Ask about this IPO or stock** (planned). Users can ask questions, answered by Gemini from the cached analysis and the source documents.

**How the work is split:**
- **AI does the judgement.**
  - **Claude**, for IPOs: it reads the RHP, researches anchor investors and news, writes the analysis and gives each IPO a verdict.
  - **Gemini**, for listed stocks: it writes stock analyses and filing summaries, and answers questions.
- **Python does the exact work.** It fetches the data from NSE, SEBI and Investorgain, extracts the RHP sections, works out the allotment odds, renders the brief and keeps the scorecard.

**How costs stay low:**
- **Analyse once, reuse.** Each IPO's RHP, each stock filing and each stock analysis is done once, saved and shared by every user. Later runs only update what moved.
- **Quiet runs.** When nothing is open and nothing needs research, Claude is not asked for any judgement at all.

The briefs are research, not investment advice.

## Who it's for

- **Retail investors** who apply for IPOs and want to know which ones are worth it and in which category.
- **Long-term investors** who hold a handful of stocks and want to hear about the filings that matter, not all of them.

## What is built and what is planned

| Capability | Status | Where |
| --- | --- | --- |
| Daily IPO numbers: list, dates, price band, GMP, P/E, subscription by category | Running | `ipo_agent/snapshot.py`, `investorgain.py`, `nse.py` |
| RHP found on SEBI before NSE lists the issue | Running | `ipo_agent/sebi.py` |
| RHP section extraction | Running | `ipo_agent/rhp.py` → `analysis/rhp/` |
| Claude's deep analysis and email card for each IPO, written once and cached | Running | `ROUTINE.md`, `analysis/` |
| Allotment odds and best category | Running | `ipo_agent/allotment.py` |
| GMP and subscription trends | Running | `ipo_agent/trends.py` |
| Quiet runs that need no Claude judgement | Running | `ipo_agent/quiet.py` |
| Designed HTML and plain-text email, twice every weekday | Running | `ipo_agent/email_render.py`, `reports/` |
| Listing-day scorecard: our call vs actual listing vs GMP | Running, 8 listings scored by 2026-10-29 | `ipo_agent/outcomes.py`, `data/outcomes.json` |
| Web app with accounts, IPO pages and track record | Planned, weeks 1–2 | [arch.md](arch.md#44-nextjs-app-decided) |
| Stock watchlist: results, announcements, shareholding and pledges | Planned, weeks 1–3 | [plan.md](plan.md#scope) |
| Stock analysis on request (Gemini), with live progress and monthly quota | Planned, week 3 | [ADR-0017](adr/0017-gemini-for-stocks-claude-for-ipos.md) |
| Ask about this IPO or stock | Planned, week 4 | [ai.md](ai.md#in-app-ai-ask) |

## Out of scope

- SME IPOs (decided on 2026-10-29; may come back later).
- Buy or sell recommendations on listed stocks. The watchlist summarises and flags; it doesn't advise.
- Placing IPO applications or trades.
- Payments and paid tiers, in phase 1. Every user is on the same free tier with the same limits: 5 Ask questions a day and 3 new stock analyses a month.

## Not investment advice

Everything the app produces is research for the user's own decisions. GMP is an unofficial grey-market figure, and past listing gains don't predict future ones.
