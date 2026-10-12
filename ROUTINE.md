# Daily IPO research routine

You are running as a scheduled Claude Code routine. Follow these steps exactly.
Scope: **Indian mainboard IPOs only** (no SME). Times are IST.

Work on the `main` branch (`git checkout main && git pull`), not a `claude/` branch: the cached
analyses in `analysis/` must be on `main` so the next run can reuse them.

## 1. Refresh the numbers

```bash
python3 -m ipo_agent.snapshot --print
```

This writes `data/latest.json` and `data/latest.md`. It lists every mainboard IPO
that is announced, upcoming, open, closing today, or awaiting listing, with:
dates, price band, lot, issue size, GMP, P/E, live category-wise subscription
(QIB / sNII / bNII / Retail) and an allotment-odds table per category.

If the `errors` field is non-empty (e.g. NSE blocked), continue with what you
have and use web search to fill the missing numbers. Say in the report which
numbers came from web search.

## 2. Deep analysis — for every IPO with `needs_analysis: true` and a non-null `rhp_url`

This is the most important step; do not skip it to save time. Do it once per IPO and save it to the
file in `analysis_file`; later runs reuse it. Do every eligible IPO, one after another. IPOs with
`rhp_url: null` (RHP not filed yet) are skipped this run and say "analysis pending — RHP not filed".

1. Extract the RHP: `python3 -m ipo_agent.rhp "<rhp_url>" --out analysis/rhp/<key>.txt`
   (skip if that file already exists). `rhp_url` comes from NSE or SEBI; both work.
   Read the extracted text file in full (never the whole PDF). Base every number on it.
2. Search the web for the anchor investor list (anchor bidding happens the
   working day before the IPO opens), and for recent news on the company.
   If the anchor allocation isn't out yet, write `**Pending**` as the first word of the
   Anchor book section; step 2b will fill it in on a later run.
3. Write `analysis/<key>.md` using the template below. Be specific and numeric.
   Cite RHP figures in ₹ crore. Never invent numbers; write "not found" instead.

```markdown
# <Company> (<SYMBOL>)
_Analysed: <date> · Sources: RHP, <others>_

## Snapshot
Price band · lot · issue size · fresh issue vs OFS (₹ Cr each) · market cap at upper band · listing date
Quota split: QIB % · NII % (sNII = 1/3, bNII = 2/3 of NII) · **Retail %** · employee / shareholder reservation (₹ Cr, discount)

## What the company does
3–5 lines: products/services, customers, revenue mix, plants/geography, moat.

## Promoters & ownership
Who the promoters are, background, pre/post-issue promoter holding, who is selling in the OFS (and at what cost of acquisition), any PE investors exiting.

## Financials (₹ Cr)
| | FY24 | FY25 | FY26 | Latest qtr |
Revenue · EBITDA · EBITDA % · PAT · PAT % · Net worth · Debt · ROE/ROCE
One line on growth trend and quality (cash flow vs profit, receivables).

## Valuation vs peers
P/E, EV/EBITDA, P/B at upper band vs listed peers from "Basis of Offer Price". Cheap / fair / expensive.

## Use of proceeds
Fresh issue use (capex, debt repayment, general corporate). OFS = money goes to sellers, not the company.

## Anchor book
Total anchor amount, number of anchors, top names. Quality grade: **Strong** (top MFs/FIIs/insurers,
e.g. SBI MF, HDFC MF, ICICI Pru, Nomura, Goldman, GIC, ADIA), **Average**, or **Weak** (unknown
AIFs/small funds/related parties). Note lock-in (50% 30 days, 50% 90 days).

## Red flags
Litigation, related-party dependence, customer concentration, negative cash flow, high OFS share, aggressive pricing.

## Verdict
**Apply / Apply for listing gains only / Avoid / Neutral**, with 2–3 reasons.
Long-term view in one line.
```

## 2b. Anchor update — only for IPOs with `needs_anchor_update: true`

The cached analysis still says the anchor book is Pending, but the anchor allocation is now done.
Web-search "<company> anchor investors" (exchange filing, news, IPO trackers), then replace **only**
the `## Anchor book` section of `analysis/<key>.md`: total ₹ Cr raised, number of anchors, top 5–10
names with amounts, and the Strong/Average/Weak grade. If it's still not findable, leave it Pending.

## 3. Write today's report

Write `reports/<YYYY-MM-DD>-<am|pm>.md`. Structure:

1. **Action list (top)**: one line per IPO, e.g.
   `CLOSING TODAY · Tonbo Imaging · Apply (Retail) · Retail 12.4x, GMP +55%`.
2. **Open / closing today**: live subscription by category (QIB / bNII / sNII / Retail / Total),
   the category odds table from the snapshot, and the **best category to apply in**
   with a one-line reason. Use the snapshot's `best_category`; if GMP is ≤ 0 say "skip" instead.
   Explain it plainly: expected gain per ₹ blocked = odds × GMP ÷ price, and GMP ÷ price is the same
   for every category, so **the least-subscribed category wins**. The odds are a lower bound and
   retail's real odds are usually further above it than sNII's (many retail bids are for >1 lot),
   so when Retail and sNII are close, prefer Retail.
3. **Upcoming**: dates, price band, lot, quota split (esp. retail %), minimum capital per category,
   GMP, anchor book (amount + grade), and the 5-line summary + verdict from the cached analysis.
4. **Awaiting listing**: allotment and listing dates, latest GMP.
5. Footer: data time stamps, source errors, and
   "Research aid, not investment advice. GMP is unofficial and can be manipulated."

Category rules to remember (mainboard): Retail ≤ ₹2 L (1 lot is enough when oversubscribed — apply
1 lot from each family member's PAN); sNII ₹2–10 L (lottery of the minimum sNII size); bNII > ₹10 L
(lottery of the minimum bNII size). Odds shown are conservative (≥ 1 in subscription-times).

## 4. Deliver

Send the report with the Gmail connector:
- To: the address in `config/delivery.json` (`"to"`).
- Subject: `IPO brief <date> <AM|PM>: <n> open, <n> upcoming` (+ "· CLOSING TODAY: <names>" when relevant).
- Body: the **complete** report, nothing dropped or shortened — every IPO, its full
  analysis summary, odds table and verdict. Gmail doesn't render markdown tables, so convert tables to
  short "label: value" lines (or send HTML if the connector supports an HTML body).
- If the send fails, wait ~30 s and retry up to 3 times with the same full body.

## 5. Save

```bash
git add data reports analysis && git commit -m "IPO brief <date> <am|pm>" && git push origin HEAD:main
```
