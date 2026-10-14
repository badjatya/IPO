# Daily IPO research routine

You are running as a scheduled Claude Code routine. Follow these steps exactly.
Scope: **Indian mainboard IPOs only** (no SME). Times are IST.

Work on the `main` branch (`git checkout main && git pull`), not a `claude/` branch: the cached
analyses in `analysis/` must be on `main` so the next run can reuse them.

**Cache, don't redo.** Everything about an IPO that doesn't move with the market is researched once
and cached in `analysis/`: the RHP text (`rhp/<key>.txt`), the deep analysis (`<key>.md`) and the
email card (`<key>.json` — summary, financials, quota, positives, red flags, anchor, baseline
verdict). The snapshot shows each card as "Cached call" and sets `needs_card` / `needs_analysis` /
`needs_anchor_update` only when something is actually missing. Never re-read an `analysis/*.md`
or re-search a company that already has a card unless one of those flags says so.

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
3. Write `analysis/<key>.md` using the template below, then its card (step 2c). Be specific and numeric.
   Cite RHP figures in ₹ crore. Never invent numbers; write "not found" instead.

```markdown
# <Company> (<SYMBOL>)
_Analysed: <date> · Sources: RHP, <others>_

## Snapshot
Price band · lot · issue size · fresh issue vs OFS (₹ Cr each) · market cap at upper band · listing date
Quota split from the RHP "OFFER STRUCTURE" section: QIB % · NII % (sNII = 1/3, bNII = 2/3 of NII) · **Retail %** · employee / shareholder reservation (₹ Cr, discount). Never guess the split; if the section is missing write "not found".

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

The card still says the anchor book is pending, but the anchor allocation is now done.
Web-search "<company> anchor investors" (exchange filing, news, IPO trackers), then replace **only**
the `## Anchor book` section of `analysis/<key>.md` (if it exists): total ₹ Cr raised, number of
anchors, top 5–10 names with amounts, and the Strong/Average/Weak grade. Update `anchor` and
`anchor_grade` in `analysis/<key>.json` to match — the card is what the next run checks. If it's
still not findable, leave both pending.

## 2c. Cards — for every IPO with `needs_card: true`, or whose analysis you just wrote in step 2

Write `analysis/<key>.json` (schema at the top of `ipo_agent/cards.py`), one line per string:
- `"source": "rhp"` when `analysis/<key>.md` exists: fill every field from that analysis
  (summary, financials, quota, 2–3 positives, 2–3 red flags, anchor, anchor_grade, verdict).
- `"source": "web"` when there is no RHP yet: one quick web search for what the company does;
  `verdict: "pending"`, `verdict_text: "Analysis pending"` (or "Watchlist" if only announced).
  This stub is replaced automatically once the RHP analysis exists.
- Facts only: **no GMP, subscription, or "today/tomorrow"** in a card — the email shows the live
  numbers itself, and the card is reused for days. Use absolute dates ("Anchor bidding 14 Oct").

## 3. Write today's verdicts (the email is rendered from them)

Write `reports/<YYYY-MM-DD>-<am|pm>.json`, keyed by each IPO's `key`. The renderer merges each entry
over the IPO's card, so write **only what changes with today's numbers** — work from
`data/latest.md` (numbers + cached calls); don't re-read the analyses. Numbers (dates, price, lot,
GMP, P/E, subscription, odds) come from the snapshot automatically. Keep strings short.

```json
{"date": "2026-10-14", "session": "AM",
 "headline": "Tonbo closes today — Retail 3.2x, apply",
 "ipos": {"tonbo-imaging": {"best_category": "Retail", "category_note": "recheck on 16 Oct"},
          "hd-fire-protect": {"verdict": "avoid", "verdict_text": "Avoid", "best_category": null,
                              "category_note": "GMP turned negative — skip"}},
 "notes": []}
```

Always write an entry for IPOs that are open, closing today or awaiting listing (their call
depends on live subscription/GMP); any other IPO with nothing new can be left out (its card is used as is). Override a card field (`verdict`,
`red_flags`, …) only when today's numbers change the call — and if the change is lasting (e.g. a
fact learned from news), update the card instead. The full schema is at the top of
`ipo_agent/email_render.py`.

- `verdict`: `apply` | `listing_gains` | `avoid` | `neutral` | `pending` (no analysis yet / announced only)
- `verdict_text`: short label, e.g. "Apply", "Listing gains only", "Avoid", "Analysis pending", "Watchlist"
- `best_category`: "Retail" / "Small HNI" / "Big HNI" / null. For open IPOs use the snapshot's
  `best_category`; if GMP ≤ 0 set verdict `avoid` and say skip. Explain it plainly: expected gain per ₹
  blocked = odds × GMP ÷ price, and GMP ÷ price is the same for every category, so **the
  least-subscribed category wins**. The odds are a lower bound and retail's real odds are usually
  further above it than sNII's (many retail bids are for >1 lot), so when Retail and sNII are close,
  prefer Retail.
- `category_note` (optional): e.g. "1 lot per family PAN", "recheck subscription on <close date>"
- Card fields (normally from `analysis/<key>.json`; same rules when writing the card):
  `summary`: one sentence on what the company does · `financials`: one line, latest FY + growth
  `quota`: from the analysis (RHP Offer Structure) · `positives`: 2–3 bullets · `red_flags`: 2–3 bullets
  `anchor` + `anchor_grade` (`strong|average|weak|pending`)
- top level: `date`, `session` ("AM"/"PM"), `headline` (one line: the single most useful takeaway
  today, e.g. "Tonbo closes today — Retail 3.2x, apply"), optional `notes` (source problems, data gaps)

Category rules to remember (mainboard): Retail ≤ ₹2 L (1 lot is enough when oversubscribed — apply
1 lot from each family member's PAN); sNII ₹2–10 L (lottery of the minimum sNII size); bNII > ₹10 L
(lottery of the minimum bNII size).

Then render:

```bash
python3 -m ipo_agent.email_render reports/<YYYY-MM-DD>-<am|pm>.json
```

It prints the email subject and writes `reports/<…>.html` (designed email) and `reports/<…>.txt`
(plain-text version). Fix any "no card or verdict for …" warning by writing that IPO's card (step 2c).

## 4. Deliver

Send with the Gmail connector to the address in `config/delivery.json` (`"to"`), using the subject the
renderer printed.
- Look at the Gmail send tool's parameters. If it accepts HTML (e.g. an `html_body` / `htmlBody`
  field, an `html` / `is_html` flag, or a content/mime type), send the **`.html` file contents as
  the HTML body** and the `.txt` contents as the plain-text body if there is a separate field.
  Otherwise send the `.txt` contents as the body. Send the file contents exactly — do not rewrite,
  summarise or shorten them.
- If the send fails, wait ~30 s and retry up to 3 times with the same body.
- In your final message, say which format was sent (HTML or plain text).

## 5. Save

```bash
git add data reports analysis && git commit -m "IPO brief <date> <am|pm>" && git push origin HEAD:main
```
