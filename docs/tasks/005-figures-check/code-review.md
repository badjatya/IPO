# Code review: 005-figures-check

## Round 1 (2026-10-29)

**Verdict:** Changes requested

**Diff:** `git diff main...task/005-figures-check` at `5d27f18`

**Tests:** run by Claude from the worktree:

```text
$ python3 -m unittest discover -s tests
Ran 221 tests in 0.631s
OK
$ python3 -m unittest discover -s .claude/hooks
Ran 17 tests in 0.269s
OK
$ python3 -m ipo_agent.figures_check --all; echo "exit $?"
...
TOTAL: 54/316 ₹ figures found (17%) across 13 analyses (0 skipped)
exit 0
```

The literal CI command runs, and it exits 0 as the human's report-only decision requires.

### Findings

| # | Severity | Where | Problem (what breaks, and when) | Suggested fix |
| --- | --- | --- | --- | --- |
| 1 | Blocker | `ipo_agent/figures_check.py:190` | **The "USD" guard drops rupee figures.** It skips any bare unit-carrying number whose previous two characters are a letter and a space. That is almost every number in prose: "of 7,756.07 lakhs", "aggregating up to 28,300.00 million", "the 2.00 lakhs". Across the 13 RHP extracts it drops 41 of the 70 bare unit-carrying candidates, and most of those are rupee amounts. Two checks show it. `check_one("₹77.6 Cr", "of 7,756.07 lakhs")` finds 0, and so does `check_one("₹2,830 Cr", "aggregating up to 28,300.00 million")`. The approved plan's Approach says those bare figures are candidates ("so '28,300.00 million' still matches without a prefix"). The share is therefore understated, and the 54/316 (17%) quoted in `docs/ai.md` comes from the bug. The guard also isn't recorded in "Changes during build", although it narrows the plan. | Skip a bare number only when a currency marker other than the rupee comes right before it: `USD`, `US$`, `$`, `EUR`, `GBP`, with optional space. Add tests for these: "of 7,756.07 lakhs" matches `₹77.6 Cr`; "aggregating up to 28,300.00 million" matches `₹2,830 Cr`; "USD 1.00 million" still doesn't count. Rerun `--all`, paste the new output into Verification, and re-quote the eval row in `docs/ai.md` from it. Record the guard under "Changes during build" |
| 2 | Major | `ipo_agent/figures_check.py:57`, `:71` | **`Rs.` matches the end of a word.** The pattern is `(?:₹\|Rs\.)` under `re.IGNORECASE`, with nothing before it. So "rs." at the end of "peers.", "others." or "sectors." is read as a rupee prefix, and `\s*` lets the number sit on the next line. On the RHP side this adds 6 false candidates today, for example "sectors.\n3" and "customers.\n  438". These can turn a missing figure into a found one. On the analysis side, `extract_figures("lags peers. 30 lakh customers")` returns `₹30 lakh`, a figure the writer never wrote. No saved analysis hits that case yet. | Require that no letter comes right before `Rs.`, for example `(?<![A-Za-z])Rs\.`, in both patterns. Add a test on each side: "peers. 30 lakh" gives no figure, and "sectors.\n3" gives no candidate |

### Plan and docs

- **Built as approved, apart from finding 1.** Steps 1–5 are present, and every test the plan names exists.
- **Deviations.** The three recorded ones (`~` as an approximate marker, how `--all` was run, the trailing comma) are justified. The USD guard needs adding to that list (finding 1).
- **Labels.** The ai.md guardrail row reads "Running in CI; the hook is Decided", as requested in plan review round 1. The CI rows in `ai.md` and `tech.md` are updated.
- **Rules.** No AI call. `ipo_agent/` stays standard-library. Nothing under `.claude/`, `analysis/` or `reports/` was touched. The exit code never depends on the share. Every task commit carries the `AI-Agent` trailer.
- **Not this task's fault:** DeepSeek couldn't run `python3 -m ipo_agent.figures_check --all` itself, because the driver doesn't allow `python3 -m <module>`. Claude ran it above, and the output matches the pasted report.

### Notes

- **Unit headers.** Even after finding 1, the share stays low for an approved reason. Bare table cells under a "(₹ million)" or "(₹ in lakhs)" header aren't candidates. For example, zetwerk's `₹6,508 Cr` is in its RHP as `65,075.72` under "(₹ million)". Reading a table's unit header would raise the share honestly. That is a follow-up task, not part of this one.

## Responses (DeepSeek)

| # | Response | Commit |
| --- | --- | --- |
| 1 | | |
| 2 | | |
