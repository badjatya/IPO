# Plan review: 005-figures-check

## Round 1 (2026-10-29)

**Verdict:** Changes requested

**Read:** plan.md, AGENTS.md, docs/tasks/README.md (reviewer guide), ROADMAP.md § 005 and § 002, docs/ai.md § Guardrails and § Evals (rows at lines 63 and 80), docs/tech.md, `.claude/hooks/guard.py`, the price-band lines of every `analysis/*.md`, and the Claude Code hooks reference on PostToolUse output (code.claude.com/docs/en/hooks, checked 2026-10-29).

The plan is well grounded. It reads the real figure shapes in `analysis/` and `analysis/rhp/`, keeps `ipo_agent/` standard-library, makes no AI call, and has a test for every step. Five items need changing before the build.

### Decisions (human)

- **Fail vs report:** the human chose **Option A, report only**, on 2026-10-29. CI prints the share and exits 0, and the hook never blocks. Write this into the plan and remove it from "Decisions needed".

### Changes requested

1. **The hook's report would never reach Claude.** The hooks reference says: "Claude never sees stderr from a hook that exits 0." The proposed `figures_feedback` prints to stderr and exits 0, so neither the routine nor a development session would see the missing list. That defeats the point of running it on write.
   - **Change:** for a non-blocking report from a PostToolUse hook, print JSON to stdout and exit 0: `{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "<the found/missing lines>"}}`. Claude Code adds that text next to the tool result.
   - Keep the rest of the design: exit 0, nothing printed when the analysis is skipped or fully found, and an import or runtime error swallowed. A swallowed error may still go to stderr, because then nobody needs to see it.
   - Update the diff, the Approach paragraph and step 6's check. The check becomes: the `echo … | python3 .claude/hooks/guard.py post-write` command prints that JSON on stdout and exits 0.
2. **Rounding tolerance should come from the precision written, not a flat `max(1%, ₹1)`.**
   - **Too loose for per-share prices.** 1% lets `₹1,119` match any candidate from ₹1,108 to ₹1,130.
   - **Too tight for small rounded amounts.** `₹0.5 Cr` doesn't match `₹46.20 lakhs` (₹0.462 Cr, 8% off), though it is that figure rounded.
   - **Change:** a figure matches when a candidate lies within half a unit of its last written digit, in the figure's own unit:
     - `₹78 Cr` covers ±₹0.5 Cr, so it matches `₹7,756.07 lakhs`.
     - `₹10.3 lakh Cr` covers ±₹0.05 lakh Cr.
     - `₹1,119` covers ±₹0.5.
   - Add tests: `₹0.5 Cr` ↔ `₹46.20 lakhs` matches; `₹1,119` doesn't match `₹ 1,125.00`; `₹78 Cr` ↔ `₹7,756.07 lakhs` still matches.
3. **Ranges aren't specified.** Every analysis has a price band written as a range, such as `₹78–82` and `₹1585–1665` (`bombay-coated-and-special-steels.md:5`, `eaaa-alternatives.md:5`). As planned, the upper end has no `₹`, so it is silently dropped. The share's denominator then depends on how a writer punctuated a range.
   - **Change:** treat `₹A–B` and `₹A-B` (en dash or hyphen) as two figures, A and B. A unit after B applies to both: `₹1,000–1,200 Cr` is two crore figures.
   - Add tests for a plain range and a range with a unit.
4. **The guardrail label must match what is applied at merge.** ai.md line 63 says the check is "run by a hook and in CI". The hook is applied by the human, possibly after the merge (step 6 says "on the task branch or at merge"). Marking the whole row **Running** at merge could claim a hook that isn't there.
   - **Change:** set the row to "**Running** in CI (`ipo_agent/figures_check.py`); the hook is **Decided** until the human applies the diff in plan 005".
   - Under "Doc updates", list the follow-up for `main`: once the hook is applied and its check passes, flip the hook part to Running.
   - The eval row (line 80) can go to **Running** as planned.
5. **Step 4's test names a CI run on the task branch, which DeepSeek can't produce.** Only the human pushes.
   - **Change:** step 4's test should be the CI command run from a clean worktree, with its output in Verification.
   - Say that the GitHub run is recorded after the human pushes the branch, as in task 002.

### Notes

- **Approximate figures.** Figures written with `≈`, such as `≈₹2,534 Cr` or `≈ ₹10,765 Cr` market caps, mark themselves as computed. You could count them separately ("n approximate, not checked") instead of as missing, so the share measures what the writer claims came from the RHP. Optional. If you do it, test it.
- **Short units need word boundaries.** `L`, `cr` and `mn` must only match as whole words, so `₹20 Listing…` isn't read as ₹20 lakh. A test for that would be cheap.
- **Report-only output is still output.** A missing figure in `--all` must never change the exit code. The step 2 test already says so; keep it.
