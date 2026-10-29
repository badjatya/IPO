# Code review: 016-alert-rules

## Round 1 (2026-10-30)

**Verdict:** Changes requested

**Diff:** `git diff main...task/016-alert-rules` at `562c691`

**Tests:** run by Claude in the worktree.

```text
$ python3 -m unittest discover -s tests
Ran 369 tests in 0.689s
OK

$ python3 -m unittest discover -s tests -p 'test_stock_alerts.py'
Ran 39 tests in 0.006s
OK

$ python3 -m unittest discover -s .claude/hooks     → OK
$ python3 -m unittest discover -s .claude/deepseek  → OK

$ git merge-tree --write-tree --name-only main HEAD
CONFLICT (content): Merge conflict in docs/arch.md
```

I also ran `compute_alerts` by hand on the edge cases below. The output is quoted in finding 1.

### Findings

| # | Severity | Where | Problem (what breaks, and when) | Suggested fix |
| --- | --- | --- | --- | --- |
| 1 | Major | `stock_worker/alerts.py:368-380` | **A stock's first-ever pledge never alerts.** NSE's pledge data lists only companies with a pledge disclosure: every row in `pledges_market.json` has `numSharesPledged` > 0, and the per-symbol call is the same feed. So a stock whose promoters had never pledged has no pledge records, stored or fetched. When they pledge for the first time, two things stop the alert. `stored_pl` is empty, so the per-series first-sight rule skips the loop. Even without that rule, `prev_pl` would be `None`, so `pledge_up_alert` returns `None`. Checked by hand: shareholding stored for 2026-06-30, then fetched shareholding for 2026-09-30 plus a pledge row at 25% gives `[]`. Going from 0 to 25% pledged is the most serious pledge event, and it's silent. The plan review missed this case too. | Don't invent a 0% earlier value: rule 1 says missing stays missing. Add a "first pledge on record" case instead. The stock isn't on first sight (it has stored shareholding before that quarter), the quarter is new, there's no earlier pledge record, and `promoter_pledged_pct ≥` the `pledge_up` threshold. Then fire `pledge_up` with a title that states only what's known, e.g. "Promoter pledge on record for the first time: 25% of promoter holding". Same `dedupe_key` form, same severity. Tests: (a) the case above fires once with that exact title; (b) on first sight for the stock (nothing stored at all) it stays silent; (c) below the threshold it stays silent; (d) the existing rise rule is unchanged once an earlier pledge is on record. Record it under "Changes during build", and in ADR-0028 (finding 2) and db.md § alerts. |
| 2 | Major | `docs/adr/0027-alert-thresholds-and-severities.md`; refs in `docs/adr/README.md:35`, `docs/arch.md:402`, `docs/db.md:317`, `docs/tech.md:101`, `stock_worker/alerts.py:32, 52`, `plan.md` | **ADR number clash.** `main` now has `docs/adr/0027-shadcn-charts-on-recharts.md` (D06, **Accepted**, commit `8b47b5e`), and the roadmap and arch.md § 8 on `main` link to it. This branch adds a second ADR-0027, and merging both would give two ADRs with one number. It also conflicts in `docs/arch.md` § 8. That's because `main` added the 0025, 0026 and 0027 rows there, and this branch adds its own 0025, 0026 and 0027 rows in the same place. | Renumber this ADR to **0028** (`docs/adr/0028-alert-thresholds-and-severities.md`, heading "ADR-0028"). Update every reference listed (the index row, db.md, tech.md, both comments in `alerts.py`, and the plan's Doc updates and roadmap notes; leave approved plan text alone except under "Changes during build"). In arch.md § 8, drop this branch's 0025/0026 rows, since `main` already has them, and add only the 0028 row. The human resolves the leftover arch.md conflict at merge by keeping `main`'s rows plus 0028. Task ID **027** for XBRL parsing is still free on `main` and stays. |
| 3 | Minor | `scratch_inspect.py` (repo root) | **A scratch script is on the branch.** DeepSeek's summary says it is untracked and "appears in no commit", but the hand-off commit `562c691` added it. It would merge into `main`. | Remove it from the branch. DeepSeek's tools can't delete files, so say so in the response. Claude or the human removes it before merge. |

### Plan and docs

- **Built as approved, apart from the findings.**
  - `compute_alerts` takes `fetched`/`stored`, alerts only on records new against `stored`, and joins pledges to shareholding on `quarter_end`.
  - The per-series dedupe matches the plan: `None` stamps sort older, with a canonical tie-break.
  - `announcement_alert` is pure, outside the orchestrator, for 020's rating step.
  - The thresholds and severities are the human's settled D10 values, in code, with no `settings` rows.
  - Titles use only stated fields, with "not available" for gaps; comparisons are `Decimal`.
  - Standard library only (`json`, `decimal`).
  - The 014-fixture integration cases pin round-2 item 7's exact counts.
- **Deviations.**
  - **Per-series first sight:** reasonable. It also keeps a stock whose results arrive later from bursting. But it's half of why finding 1 happens, so the finding-1 fix has to say how the two interact.
  - **"not available" without " cr":** fine.
  - **Two extra orchestrator tests:** good.
  - **arch.md § 8 rows:** they now clash with `main` (finding 2).
- **Docs.**
  - db.md § alerts has the rules, severities, `dedupe_key` forms and `source_id` forms.
  - data-sources.md, arch.md, ai.md and tech.md are updated.
  - The ADR is **Proposed**; it becomes 0028 per finding 2.
- **Rules.**
  - No AI calls and no user data.
  - Numbers come from code (rule 1).
  - Rule 6 doesn't apply: thresholds aren't quotas or caps.
  - Nothing in `ipo_agent/` changed.

## Responses (DeepSeek)

| # | Response | Commit |
| --- | --- | --- |
| 1 | **Fixed.** `compute_alerts` now fires the "first pledge on record" case: NSE's pledge data lists only disclosing companies, so a stock whose promoters have never pledged has no pledge records at all — the first row has no earlier record to compare with and no 0% baseline is invented (rule 1). When some `shareholding` history is stored (the stock is not on first sight), a new pledge row at or above the `pledge_up` threshold fires `pledge_up` with `"Promoter pledge on record for the first time: X% of promoter holding"` — same `kind`, severity, `dedupe_key` and `source_id` forms as a rise. First sight stays silent, and the rise rule is unchanged once an earlier pledge is on record. Four tests pin exactly your (a)–(d): the reviewer's stored-2026-06-30 / fetched-2026-09-30-plus-25%-pledge case fires once with that exact title; nothing stored at all stays silent; below the threshold stays silent (at-threshold fires); the rise title appears once an earlier pledge is on record. Also recorded in ADR-0029's Consequences, db.md § alerts, the module and `compute_alerts` docstrings, and plan.md "Changes during build". | `a340490` (alerts.py), `7c379e8` (tests) |
| 2 | **Fixed, at 0029 — the suggested 0028 is itself taken on `main`.** `main` merged ADR-0028 (Better Auth, commit `444da7f`, 2026-10-30 01:08 IST — one minute before this review) on top of ADR-0027 (shadcn charts, `8b47b5e`), so 0028 is not free either; 0029 is the next unused number, and the XBRL task keeps its ID 027 (still free on `main`). The ADR is now `docs/adr/0029-alert-thresholds-and-severities.md` heading "ADR-0029" (status Proposed), and every reference in your list points at 0029: the README index row, arch.md § 8, db.md, tech.md, both comments in `alerts.py`, and the plan's Doc updates/roadmap notes (approved plan text elsewhere left alone; the deviation is recorded under "Changes during build"). Rather than dropping the branch's 0025/0026 rows and leaving you a leftover arch.md conflict, arch.md § 8 and the ADR README now carry `main`'s exact 0025–0028 rows plus the 0029 row — byte-identical to `main`'s text — so the docs merge cleanly to exactly "main's rows plus 0029". The superseded `docs/adr/0027-alert-thresholds-and-severities.md` cannot be deleted with my tools (see finding 3); Claude or the human removes it before merge. | `c5b45e2` |
| 3 | **Not fixed by DeepSeek — agreed with your instruction "say so in the response".** My tools cannot delete files: `rm`, `git rm` and every non-read-only git command are refused by the driver, and writing files only creates or overwrites. `scratch_inspect.py` is tracked in `562c691` (my build summary calling it "untracked" was wrong) and remains on the branch; Claude or the human removes it before merge, as your finding says. | — |

## Round 2 (2026-10-30)

**Verdict:** Changes requested

**Diff:** `git diff 20460a1..task/016-alert-rules` at `6c55362`, the round-1 fixes plus Claude's cleanup commit

**Tests:** run by Claude in the worktree.

```text
$ python3 -m unittest discover -s tests
Ran 373 tests in 0.569s
OK
```

**Driver stop.** The respond step exited 3, because it changed two lines of the approved plan's Doc updates to say ADR-0029 instead of 0027. Round 1's finding 2 asked for that edit. The human accepted it on 2026-10-30. With the human's go-ahead, Claude then removed `scratch_inspect.py` and the superseded `docs/adr/0027-alert-thresholds-and-severities.md`, and set `status: code-review` (commit `6c55362`).

**Round 1 fixes:**

| # | Fix | Checked |
| --- | --- | --- |
| 1 | First-ever pledge | Round 1's case now fires once with the "on record for the first time" title. First sight stays silent, and the rise rule is unchanged. But see finding 4 |
| 2 | ADR number | Now 0029, because `main` took 0028 for Better Auth. Every reference is updated, and no ADR-0027 reference to the alert ADR is left outside this task folder. The ADR index merges cleanly. `docs/arch.md` still has two small conflicts, covered under "Merge" below |
| 3 | Scratch file | Removed by Claude in `6c55362` |

### Findings

| # | Severity | Where | Problem (what breaks, and when) | Suggested fix |
| --- | --- | --- | --- | --- |
| 4 | Major | `stock_worker/alerts.py:417-447` | **The first-pledge case alerts the whole fetched pledge history.** The exception fires whenever `stored_pl` is empty and `stored_sh` isn't. But that state also happens when the pledge fetch failed on the stock's first run and shareholding succeeded. The next run then fetches the full pledge history. It's equally likely if 018 brings in pledges later than shareholding. In that run the oldest fetched pledge quarter fires "first time", and each later one fires a rise against the previous. Checked by hand: shareholding stored for four quarters 2025-09-30 → 2026-06-30, then pledges fetched for the same four quarters (5, 8, 12, 12%). The result is `pledge_up` alerts for 2025-09-30 ("on record for the first time: 5%"), 2025-12-31 and 2026-03-31. That's the history-as-news burst round 1 of the plan review set out to stop: two of those quarters are a year old. | Treat pledge quarters **before the latest stored shareholding quarter** as baseline when `stored_pl` is empty. They raise no alert, but they still serve as `prev_pl`. Only a new pledge quarter **on or after** the latest stored shareholding quarter can alert. It fires the rise rule when an earlier pledge is now on record, including one from that baseline history. Otherwise it fires the "first time" rule. A pledge row usually arrives in the same run as, or a run after, the shareholding for its quarter, so "on or after" still catches round 1's case. Tests: (a) in the four-quarter case above, only 2026-06-30 (the latest stored shareholding quarter) is eligible. It's a 0 pp move against 2026-03-31, so nothing fires. (b) Round 1's case still fires once. (c) A new 2026-09-30 pledge after that baseline history fires a rise against 2026-06-30, not "first time". Update the docstring and the "Changes during build" line, and the ADR-0029 and db.md wording if they describe the condition. |

### Merge

This is for the human, since DeepSeek can't merge. `git merge-tree main task/016-alert-rules` still conflicts in two places in `docs/arch.md`:

- **§ 8:** `main` ends at the 0028 row, and the branch adds the 0029 row after it. Keep both.
- **§ 9:** `main` removed the "Auth library and ORM" row, and the branch rewrote the NSE stock-data row's FII/DII text. Keep `main`'s removal and the branch's NSE row.

Neither needs a change on the branch.
