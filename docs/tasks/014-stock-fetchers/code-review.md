# Code review: 014-stock-fetchers

## Round 1 (2026-10-30)

**Verdict:** Changes requested

**Diff:** `git diff main...task/014-stock-fetchers` at `4fc50c6`

**Tests:** run by Claude in the worktree.

```
$ python3 -m unittest discover -s tests
Ran 301 tests in 0.545s
OK

$ python3 -m unittest discover -s tests -p 'test_stock_*.py'
Ran 74 tests in 0.020s
OK

$ python3 -m unittest discover -s .claude/hooks
Ran 19 tests in 0.197s
OK
```

The parsers do what the approved plan says. EBITDA, the lakh-to-crore conversion, the `Non-Consolidated` filings join, the pledge share and FII/DII as a gap all match the plan, and the tests pin the fixture numbers. The problems are in the probe, which the human is about to run against NSE, and in the `since` filter that 018 will rely on. **The human doesn't run the probe until findings 1 and 2 are fixed.**

### Findings

| # | Severity | Where | Problem (what breaks, and when) | Suggested fix |
| --- | --- | --- | --- | --- |
| 1 | Blocker | `stock_worker/probe.py:171`, `:178`, `:181-188` | `_parse_candidate_body` returns a `(payload, error)` pair, and `_try_candidate` returns `_parse_candidate_body(body), source`, which nests that pair inside another. So `payload` is never `None` for a fetched candidate. Any 200 that isn't a quote counts as success: an HTML "Access Denied" page, or JSON without `priceInfo.lastPrice`. Reproduced with a fake client that serves a non-JSON 200 for `trade_info`: the run reports `quote source: trade_info`, `ok: True`, and writes `quote.json` containing `[null, "response is not JSON: …"]` plus a manifest entry. The live run would then record a false quote source in `data-sources.md`. The existing `trade_info` and `nextapi` tests pass only because they feed a valid quote, and they never inspect `quote_payload`. | Unpack the pair in `_try_candidate` and return the parse error as the candidate's error. Add tests that a 200 non-JSON body and a 200 JSON body without `priceInfo.lastPrice` each give `ok: False` with the error, move on to the next candidate, and write no `quote.json`. Assert `quote_payload` is the dict itself on the success paths. |
| 2 | Major | `stock_worker/probe.py:246-258` | The consolidated re-check compares today's `consolidated=true` body with the `results_standalone.json` **fixture** captured in 003. NSE adds a quarter or revises a row, the standalone body changes, and the probe reports `distinct`, implying a consolidated source when the endpoint still ignores the flag. That outcome goes into `data-sources.md` in 6b. | Compare two bodies fetched in the same run: fetch `results-comparision?symbol=X` and `…&consolidated=true` back to back under the same prime. That's 1 prime + up to 3 candidate fetches + 2 = 6, within `MAX_CALLS`. Record `identical` or `distinct` only from that pair. Update the docstring, `dry_run_lines` and the budget comment, and test both outcomes with a `FakeClient`. |
| 3 | Major | `stock_worker/announcements.py:37` | `since` is compared as a string with `announced_at`. That's only right when both use the same format and offset. With `since="2026-10-29T05:00:00+00:00"` (10:30 IST), a row announced `29-Oct-2026 08:55:40` IST is kept (reproduced), though it's older. A date-only `since` compares differently again. 018 will pass a stored run time, probably UTC, so new-row detection breaks there. | Parse both sides to timezone-aware `datetime`s and compare those. A naive or date-only `since` is either rejected (`ValueError`) or read as IST; say which in the docstring. Add tests: a UTC `since` that drops an older IST row and keeps a newer one, and the boundary (equal time kept). |
| 4 | Major | `docs/tech.md:62`, `docs/adr/README.md`, `docs/adr/0026-stock-worker-code-location.md` | Two docs are out of step. (a) ADR-0026's Evidence says "tech.md's Gemini row now reads 'one module per side'", but `tech.md:62` still says "behind one module that the app (Ask) and the stock worker share"; the plan's Doc updates required this change (D09, human decision). (b) The ADR index has no row for 0026. | Update `tech.md:62`: the app's module is TypeScript in `web/lib/` and the worker's is Python in `stock_worker/` (020), as ADR-0026 says. Add the 0026 row to `docs/adr/README.md` with status Proposed. |
| 5 | Minor | `stock_worker/results.py:108` | `revenue_cr` falls back to `re_total_inc` when `re_net_sale` is absent. Total income *includes* other income, which is also stored in `other_income_cr`. On that path, revenue and other income double-count, under a column labelled revenue. (The fallback came from 003's data-sources mapping, so it isn't invented, but it gives a wrong figure.) | Drop the fallback, so a missing `re_net_sale` gives `None`, and update the data-sources results row. Or keep it only as `revenue − other income` when both are stated, and document that. Test whichever is chosen. |
| 6 | Minor | `stock_worker/util.py:69` | `to_decimal("NaN")` and `to_decimal("Infinity")` return non-finite `Decimal`s, which would flow into `numeric` columns and into the pledge arithmetic. | Return `None` unless `value.is_finite()`. Add a test. |
| 7 | Minor | `stock_worker/pledges.py:52` | A row without `comName` gives `company: ""`, not `None`. Missing fields are `None` (plan § 1). | `None` when the stripped name is empty. Add a test. |
| 8 | Minor | `docs/adr/0026-stock-worker-code-location.md` (Context) | The links `adr/0018-…` and `adr/0002-…` resolve to `docs/adr/adr/…` from inside `docs/adr/`, so both are broken. | Use `0018-stock-worker-on-github-actions.md` and `0002-standard-library-only-agent.md`. |
| 9 | Nit | `stock_worker/announcements.py:12` | `industry` isn't a db.md `announcements` column. The plan asks for such fields to be listed as extras. | Move it under an "Extras" line in the docstring. |

### Plan and docs

- **Built as approved:** yes for steps 1–5, 6a, 7 and 8, apart from the findings above.
- **Deviations:** all justified and recorded.
  - 6b is pending by design.
  - The prime lives in `fetchers.Session`, as the round-2 note asked.
  - Results makes two calls, so a run makes 6 calls, and the test pins them.
  - Shareholding `filed_at` uses the date-only `submissionDate`, as stated. `broadcastDate` has a full time. Leave it for now; 018 can decide when it maps to `timestamptz`.
- **Docs:** `data-sources.md`, `arch.md`, `db.md` and `tech.md` are updated, apart from finding 4.
- **Step 6b, after this round:** once findings 1 and 2 are fixed and reviewed, the human runs the probe once **from the task worktree** (`.worktrees/014-stock-fetchers/`; `stock_worker/` doesn't exist in the main checkout). Claude pastes the output into the next review round. DeepSeek then writes `quote.py`, its tests, and the quote and consolidated doc rows from that output.

## Responses (DeepSeek)

| # | Response | Commit |
| --- | --- | --- |
