# Code review: 004-routine-provenance

## Round 1 (2026-10-29)

**Verdict:** Approved

**Diff:** `git diff main...task/004-routine-provenance` at `ac0ce98`

**Tests:** run by Claude in the worktree:

```text
$ python3 -m unittest discover -s tests
Ran 191 tests in 0.269s

OK

$ python3 -m unittest discover -s .claude/hooks
Ran 17 tests in 0.264s

OK
```

The guard suite above is unchanged on this branch. The plan's `guard.py` and `test_guard.py` diffs (step 4, human-applied) were checked in plan review round 2 on a scratch copy: 22 tests, OK.

### Findings

| # | Severity | Where | Problem (what breaks, and when) | Suggested fix |
| --- | --- | --- | --- | --- |
| 1 | Minor | `tests/test_email_render.py:136` | The "renders identically" test adds provenance to the **report** only. Cards are the files that will carry the fields most often, and they reach the renderers through `merged()` (`email_render.py:347`, `{**card, **entry}`). Nothing pins that a card with provenance renders the same. I checked by reading the code: `card()`, `render_text()` and `snapshot.py`'s `latest.md` all read named keys only, so nothing breaks today. A future renderer that loops over `v.items()` would leak `ai_*` into the email unnoticed | Follow-up, or fix now: write a card with the three fields through `TempRepo.card` and assert that `render_html` and `render_text` match a card without them |
| 2 | Nit | `docs/ai.md:62`, `docs/ai.md:68` | Both rows say **Running (task 004)**, but they are only true once the human applies the `ROUTINE.md` and guard diffs (plan step 4). Merging without applying them leaves the docs ahead of reality | No code change. Apply the step-4 diffs right after merging, before the next routine run, as the plan says |

### Plan and docs

- **Built as approved.** Steps 1–3 match the plan. The `cards.py` and `email_render.py` docstrings match the plan's diffs line for line, and "Changes during build: none" is accurate. No commit touches the approved plan's body or the review files. The only plan edits are the status line and the "Changes during build" and "Verification" sections.
- **Behaviour:**
  - No runtime code changed, only docstrings.
  - Every reader of card fields reads only named keys: `snapshot.py:65,155`, `email_render.py:347`, `quiet.py:58,89`, `outcomes.py:92`. Optional `ai_*` fields therefore change no output.
  - `latest.json` stores the whole card, which is harmless.
  - `quiet.py` still writes reports with no provenance.
- **Rules:**
  - Rule 1: the timestamp comes from `date -u`, never from the AI.
  - Rule 10: implemented for cards and reports.
  - Rule 5: the documents-as-data instruction is in the `ROUTINE.md` diff.
  - The protected paths are left to the human.
  - Tests use temp repos and fixtures, with no live calls.
- **Docs:**
  - `ai.md`: a provenance row is added, and the documents-as-data row names the `ROUTINE.md` rule, the `rhp-analyst` rule and the planned worker prompts.
  - `db.md`: principle 4's example ID now matches the stamped format. `reports` gains the provenance columns, with notes on quiet runs and `carried_from`. `ipo_verdicts` inherits provenance from its report. The field mapping and the import note are updated.
  - `ipo_analyses` provenance stays planned, and the plan calls it a possible follow-up.

### After merge (human)

1. Apply the plan's step-4 diffs (`ROUTINE.md`, `.claude/hooks/guard.py`, `.claude/hooks/test_guard.py`) **in one commit on `main`, before the next routine run**. Then run `python3 -m unittest discover -s .claude/hooks`; it should report 22 tests, OK.
2. The last Done-when, "the next routine run writes the fields", is confirmed on the first non-quiet run after that commit. Check that the new card or report has `ai_model`, `ai_prompt_version: "1"` and `ai_written_at`.
3. Roadmap: 004 becomes **Done** after step 2 is confirmed. Add the provenance follow-up for `analysis/<key>.md` to the roadmap if wanted.
4. Expect a small conflict in `docs/ai.md` § Guardrails if task 005 merges first. Keep both sets of rows.

## Responses (DeepSeek)

| # | Response | Commit |
| --- | --- | --- |
