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
| 1 | **Fixed.** `_try_candidate` now unpacks `_parse_candidate_body`'s `(payload, error)` pair and returns the parse error as the candidate's error (with the URL appended for the human's table). A 200 non-JSON body and a 200 JSON body without `priceInfo.lastPrice` give `ok: False` with the error, the run moves to the next candidate, and no `quote.json` is written (new tests for all three, plus `quote_payload` asserted to be the dict itself on the success paths). | 48fe4db |
| 2 | **Fixed.** The re-check fetches `results-comparision?symbol=X` and its `…&consolidated=true` variant back to back under the same prime and records `identical`/`distinct` only from that pair — the 003 fixture is never consulted. Budget stays 6 (1 prime + up to 3 candidate fetches + 2 re-checks). Module docstring, `dry_run_lines`, the `MAX_CALLS` comment and the dry-run test updated; `identical`, `distinct` and "ignores a saved fixture" all tested with a `FakeClient`. | 48fe4db |
| 3 | **Fixed.** Both sides parse via the new `util.to_aware_datetime` and compare as timezone-aware datetimes. `since`: offset kept, naive read as +05:30, date-only read as midnight +05:30, junk raises `ValueError` — all said in the docstring. Tests: a UTC `since` drops an older IST row and keeps a newer one, the equal-time boundary keeps the row, naive/date-only behaviour, and junk raising. | 906c4db |
| 4 | **Fixed.** tech.md:62 now reads "one module per side: the app's is TypeScript in `web/lib/`, the worker's is Python in `stock_worker/` (020)" (ADR-0026 linked). `docs/adr/README.md` gains the 0026 row with status **Proposed**. | 798bb4d |
| 5 | **Fixed.** The fallback is dropped: a missing `re_net_sale` gives `revenue_cr = None` (the plan's missing-is-missing rule); `re_total_inc` is never used as revenue because it includes other income, which has its own column. The data-sources results row and the module docstring say so; a test pins `revenue_cr=None` while `other_income_cr` still parses. | cca9f40 |
| 6 | **Fixed.** `to_decimal` returns `None` unless `value.is_finite()`, so `NaN`/`Infinity` can't reach numeric columns or the pledge arithmetic. Test added. | 906c4db |
| 7 | **Fixed.** `pledges.parse` returns `company: None` when the stripped name is empty. Test added. | cca9f40 |
| 8 | **Fixed.** The Context links are now `0018-stock-worker-on-github-actions.md` and `0002-standard-library-only-agent.md` (no `adr/` prefix, so they resolve from inside `docs/adr/`). | 798bb4d |
| 9 | **Fixed (nit).** `industry` moved under an "Extras" line in the docstring — it has no db.md column but stays in the record (the test's key set is unchanged). | 906c4db |

Full suite after the fixes: `python3 -m unittest discover -s tests` → 319 tests OK (was 301); stock tests 92 OK (was 74); `.claude/hooks` 19 OK. Output is pasted in plan.md "Verification".

## Round 2 (2026-10-30)

**Verdict:** Changes requested (step 6b only, plus one Minor)

**Diff:** `git diff main...task/014-stock-fetchers` at `a5cc1e4`

**Tests:** run by Claude in the worktree.

```
$ python3 -m unittest discover -s tests
Ran 319 tests in 0.564s
OK

$ python3 -m unittest discover -s tests -p 'test_stock_*.py'
Ran 92 tests in 0.024s
OK

$ python3 -m unittest discover -s .claude/hooks
Ran 19 tests in 0.207s
OK
```

**Round 1, checked:** all nine responses verified in the code.

- **Finding 1:** re-run with the round-1 reproduction (a 200 "Access Denied" body for every candidate). Every candidate is now `ok: False` with the error, `quote source` is `None`, and no `quote.json` or `manifest.json` is written.
- **Finding 2:** the re-check fetches standalone and consolidated in the same run, 5 calls in that reproduction.
- **Finding 3:** a UTC `since` of `2026-10-29T05:00:00+00:00` now drops the 08:55 IST row.
- **Finding 4:** `tech.md:62` and the ADR index (0026, Proposed) are updated.
- **Findings 5–9:** fixed as described.

### The human's probe run (input for 6b)

Run once by the human on 2026-10-30 from the task worktree. It wrote no files (`git status` clean afterwards).

```
$ python3 -m stock_worker.probe
candidate            ok         source / error
stock_page_embedded  False      no embedded quote JSON found in the stock page
nextapi              False      unprobed: the stock page carries no _next/data URL
trade_info           False      HTTPError: HTTP Error 403: Forbidden
cookie_order         False      HTTPError: HTTP Error 403: Forbidden
quote source: none (see table errors)
consolidated re-check: identical (the endpoint still returns the standalone body)
```

### Findings

| # | Severity | Where | Problem (what breaks, and when) | Suggested fix |
| --- | --- | --- | --- | --- |
| 10 | Major | step 6b (`stock_worker/quote.py`, `docs/data-sources.md`, `docs/arch.md` § 9) | Step 6b isn't built yet, and the approved plan requires it. The probe above found no quote source, so the plan's "nothing answered" path applies. | Build the plan's "nothing answered" path: (a) `fetch_quote` raises `SourceError` pointing at the recorded gap, wired into `fetch_all` so the gap shows in `errors` while the other sources still return records; add tests for both and update the call-count test. (b) The `data-sources.md` quote row records the 2026-10-30 run with each candidate's error, verbatim from the table above. (c) The consolidated row records that the same-run re-check was `identical`, so the gap is confirmed. (d) `arch.md` § 9 keeps quote and consolidated as open. (e) The NextApi candidate is recorded honestly: the probe searched the stock page only for a `_next/data` route and found none, so NSE's `/api/NextApi/…` paths were **not** tried; say so, and leave them as an unprobed candidate for a later task. No `quote.json` fixture is added. Paste the run into the plan's Verification. |
| 11 | Minor | `stock_worker/util.py` (`to_aware_datetime`), `stock_worker/announcements.py:40` | `since` with a `Z` suffix (`2026-10-29T05:00:00Z`) or fractional seconds (`2026-10-29 05:00:00.123456+00:00`, how a Postgres `timestamptz` often prints) raises `ValueError`, so the whole announcements source fails into `errors`. A `datetime` object works only because its `str()` happens to match. 018 will pass a stored run time. | Accept a timezone-aware `datetime` directly, and parse strings with `datetime.fromisoformat` (Python 3.11+ reads `Z` and fractional seconds), still reading a naive value as +05:30. Add tests for `Z`, fractional seconds and a `datetime` object. |

### Plan and docs

With 6b built as the "nothing answered" path, the plan is complete. No `quote.json` is added and `stock_quotes` stays unfilled. After merge, the roadmap must record that the quote source is still open; see the report to the human.

## Responses (DeepSeek)

| # | Response | Commit |
| --- | --- | --- |
| 10 | **Fixed.** 6b built as the plan's "nothing answered" path. (a) New `stock_worker/quote.py`: `fetch_quote` raises `SourceError` pointing at the recorded gap (probe run 2026-10-30) and makes no call — there is no confirmed endpoint; wired into `fetch_all` as the last source, so every run reports the quote gap in `errors` while the other sources still return records. The call-count test still pins exactly 1 prime + 5 API calls (quote adds none) and now asserts the quote `SourceError`; `plan_calls`/`--dry-run` list quote as "(no call: quote source unconfirmed — see data-sources.md)"; tests cover the raise, that no session state is touched, and that the gap message names the run and each candidate honestly (`tests/test_stock_quote.py`, updated `tests/test_stock_fetchers.py`). (b) `data-sources.md` quote row records the 2026-10-30 run with each candidate's error verbatim, including the `quote source:` and `consolidated re-check:` lines. (c) The consolidated row records the same-run `identical` re-check, confirming the gap. (d) `arch.md` § 9 keeps quote and consolidated as open, and § 4.2 notes the probe ran and found nothing. (e) The NextApi candidate is recorded honestly as **unprobed**: the probe searched only the stock page's HTML for a `_next/data` route and found none, so NSE's `/api/NextApi/…` paths were **not** tried and stay the candidate for a later task. No `quote.json` fixture is added; the run is pasted into plan.md "Verification" and the roadmap note records that the quote source stays open. | 0ac2bb5 (code), 7163a42 (docs) |
| 11 | **Fixed.** `to_aware_datetime` accepts a timezone-aware `datetime` directly (a naive object read as +05:30) and parses strings with `datetime.fromisoformat` (Python 3.11+), which reads the `Z` suffix and fractional seconds — how a Postgres `timestamptz` prints — while junk still gives `None` (and so still raises `ValueError` in the announcements `since` path). Tests: `Z`, fractional seconds, a `datetime` object and a naive `datetime` object, at both the util and the `since`-filter level. Docstrings updated. | 5944ca7 |
