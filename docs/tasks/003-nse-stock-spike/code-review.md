# Code review: 003-nse-stock-spike

## Round 1 (2026-10-29)

**Verdict:** Changes requested

**Diff:** `git diff main...task/003-nse-stock-spike` at `622b278`. The last commit, `622b278`, records the GitHub runner result. Claude Code made it at the human's request because opencode was unavailable. It only fills in the run URL and `G1 candidate:` line that the approved plan reserved for that step, and sets `code-review`.

**Tests:**

```text
$ python3 -m unittest discover -s tests
...................
----------------------------------------------------------------------
Ran 19 tests in 0.011s

OK

$ python3 -m unittest discover -s .claude/hooks
Ran 17 tests in 0.284s

OK
```

**Runner:** https://github.com/badjatya/IPO/actions/runs/40869763010, `G1 candidate: PARTIAL`. It matches the local run exactly: nine of ten data calls answered, and `quote` returned 403 in both places.

### Findings

| # | Severity | Where | Problem (what breaks, and when) | Suggested fix |
| --- | --- | --- | --- | --- |
| 1 | Major | `docs/data-sources.md:73` | `shareholding.promoter_pledged_pct ← data[].percSharesPledged` is the wrong mapping. [db.md](../../db.md) defines `promoter_pledged_pct` as the "share of promoter holding that is pledged". The committed fixtures show `percSharesPledged` is pledged shares as a share of **all** (demat) shares: for ADANIENT, 21,723,685 / 1,353,182,590 = 1.61 % (the field says 1.61), while 21,723,685 / 974,234,554 promoter shares = 2.23 %. In `pledges_market.json`, 20 Microns gives 4.52 against 10.00 %. Task 014 builds from this table, so the worker would store a figure roughly half the real one, and `pledge_up` alerts would fire on the wrong number. The quirks column even says the definition is unknown, but the fixture already answers that. `percPromoterShares` is also not the pledge share: it equals `totPromoterShares / totPromoterHolding` (7,700,000 / 974,234,554 = 0.79). | Map `promoter_pledged_pct` to "computed in code: `numSharesPledged / totPromoterHolding × 100`", following rule 1 (numbers come from code). Map `promoter_pct` to `percPromoterHolding` (share of total equity). Rewrite the quirk to say what the fixture shows: `percSharesPledged` ≈ pledged ÷ demat shares, and `percPromoterShares` = `totPromoterShares` ÷ `totPromoterHolding`, which is not the pledge. Values are strings with leading spaces. |
| 2 | Minor | `ipo_agent/nse_stock_smoke.py:126` | `field("promoter_pledged_pct", "data[].percPromoterShares")` gives the wrong meaning to a field (see finding 1). The label is copied into `manifest.json` and the generated fixture README, which 014 reads as provenance. | Rename it to what the field is, e.g. `field("promoter_shares_pct", "data[].percPromoterShares")`, and add `field("pledged_pct_of_total", "data[].percSharesPledged")` (renaming the current `pledged_pct`). Regenerate `manifest.json` and `README.md` from the saved bodies, or edit only the labels in them consistently with the code. Don't run a new live capture. |
| 3 | Minor | `docs/arch.md:403` | The row says 003 confirmed "announcements, equity list and standalone results". But results filings, shareholding (promoter and public) and pledges answered too, and are confirmed in `data-sources.md`. It also lists "pledge symbol" as unconfirmed: the endpoint is confirmed, and what's missing is a `symbol` in the response. A status note is also squeezed into the "Needed by" column. | Narrow the question to what's still open, e.g. "NSE stock endpoints still unconfirmed: quote (403 locally and on a runner), consolidated results, FII/DII split, filing links in results-comparision", with "Needed by: 014". Point to `data-sources.md` for what's confirmed. |
| 4 | Minor | `docs/data-sources.md:66`, `:79` | The quote row says 403 "from the build IP", and the "Worker host" paragraph says only the local build saw a mixed result. The runner returned the same 403, which is the useful fact: the quote failure is specific to that endpoint, not a GitHub block. | Say "403 locally and from a GitHub runner (run 40869763010)" in the quote row. In the paragraph, say the runner answered the same nine of ten calls, so the quote 403 isn't a runner block. Leave ticking G1 to the human. |
| 5 | Nit | `ipo_agent/nse_stock_smoke.py:283` | `text` is assigned in the HTML branch of `summarise` and never used. | Drop the line. |

### Plan and docs

- **Built as approved.** There are exactly 12 requests, a `CallBudget` with a 12-vs-13 test, `retries=0`, no fallbacks, and `trade_info` is never called. The date is injected into `build_requests` (round 2 note 1). The 20-row cap is applied in code, with a manifest. The README is generated (round 2 note 3), and `--dry-run` makes no client. The workflow has a `paths:` filter, pinned actions, read-only permissions and no secrets. Tests make no network calls.
- **The deviations are justified and recorded:**
  - `prefer_ipv4()` changes no URL, retry or call count.
  - The field paths were corrected from the live shapes.
  - `KNOWN_GAPS` is explicit.
  - The CSV header is stripped only for comparison.
  - Consolidated results are byte-identical to standalone, so they're marked **not confirmed** and no figures are inferred.
- **Rules:** standard library only, no AI, no secrets, no cookies or headers in fixtures (checked), and no writes to `data/` or `analysis/`.
- **Docs:** `data-sources.md`, `tech.md` (only 003's rows) and `arch.md § 9` are updated, apart from findings 1, 3 and 4.
- **For 014, not a finding:** the results amounts look like ₹ lakh. RELIANCE's `re_net_profit` 872,100 with EPS 6.44 is consistent with that. But the response doesn't say so, so "unit not stated" is the right record, and 014 confirms it against a filing as planned.

## Responses (DeepSeek)

opencode was unavailable, so Claude Code made these fixes at the human's request.

| # | Response | Commit |
| --- | --- | --- |
| 1 | Fixed. `promoter_pledged_pct` is now "computed in code as `numSharesPledged / totPromoterHolding × 100`", and `promoter_pct` ← `percPromoterHolding`. The quirk states what the fixture shows for `percSharesPledged` and `percPromoterShares` | `e015f5b` |
| 2 | Fixed. The probe labels are now `pledged_pct_of_total` and `promoter_shares_pct`. `manifest.json` labels were edited to match, and `README.md` was regenerated from it with `render_readme`; only those labels changed. No live capture | `e015f5b` |
| 3 | Fixed. The row now lists only what's still unconfirmed, points to `data-sources.md` for what's confirmed, and says "Needed by: Task 014" | `e015f5b` |
| 4 | Fixed. The quote row and the "Worker host" paragraph say the 403 happened both locally and on the runner, so it isn't a runner block | `e015f5b` |
| 5 | Fixed. Unused `text` removed | `e015f5b` |

## Round 2 (2026-10-29)

**Verdict:** Approved

**Diff:** `git diff main...task/003-nse-stock-spike` at `e015f5b`. The round 1 fixes are in `e015f5b`.

**Tests:**

```text
$ python3 -m unittest discover -s tests
...................
----------------------------------------------------------------------
Ran 19 tests in 0.011s

OK
```

### Findings

None open. All five round 1 findings are fixed:
- The pledge mapping now follows db.md's definition, and the arithmetic in the fixtures backs it.
- The probe labels match what each field is.
- `arch.md § 9` and the quote row are accurate.

Caveat: Claude Code both made and reviewed these fixes, at the human's request. They are small and only about labels and docs: no request, URL or call count changed, and the fixture bodies are untouched.

### Plan and docs

Built as approved. The deviations are recorded in the plan, and the runner result is in the plan's "Verification" and in `data-sources.md`. `e015f5b` changes `ipo_agent/nse_stock_smoke.py`, which is in the workflow's `paths:` filter, so pushing the branch again will run the NSE check once more (12 requests). That's harmless, but it isn't needed.
