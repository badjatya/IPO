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
