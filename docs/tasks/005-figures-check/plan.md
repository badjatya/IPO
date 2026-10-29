---
task: 005-figures-check
status: code-changes
branch: task/005-figures-check
assigned_by: Vijay
planner: DeepSeek deepseek-v4-flash-0731 (OpenRouter)
reviewer: Claude Code
---

# 005: Figures check

## Task

> Task 005 from docs/tasks/ROADMAP.md:
>
> ### 005 · Figures check
>
> | | |
> | --- | --- |
> | Slug | `005-figures-check` |
> | Status | **Ready** |
> | Depends on | 001, 002 |
> | Owner | DeepSeek plans and builds the script and the CI job; any hook change in `.claude/` is applied by the human |
> | Milestone | M1 |
>
> A standard-library script that checks that every ₹ figure in `analysis/<key>.md` appears in `analysis/rhp/<key>.txt`, and reports the share found per analysis. This is the **Figures check** eval and guardrail in [ai.md](../ai.md#guardrails) (Decided). CI runs it over every analysis.
>
> - **Done when:** the script runs on one IPO or all of them; CI runs it; `ai.md` marks Figures check as Running, with today's results quoted.
> - **Watch for:** crore and lakh, commas, rounding, and figures written in words. Analyses written from web search before the RHP (card `source: web`) are skipped. Whether a low score fails CI or only reports is a decision for the plan.
> - **Read:** [ai.md § Guardrails and § Evals](../ai.md#guardrails), `ROUTINE.md` analysis template, a few files in `analysis/`.
> - **Start:** `/run-task 005`

## Goal and scope

- **In scope:**
  - `ipo_agent/figures_check.py`: a standard-library module that extracts every ₹ figure from one analysis, converts units (crore, lakh, million, "lakh crore"), strips commas, handles rounding and word-numbers, and reports which ones appear in that IPO's RHP extract, with the share found.
  - A `python3 -m ipo_agent.figures_check <key>` and `--all` command line; `--all` prints one line per analysis plus an overall share, and exits 0 unless the run itself errors.
  - Skip rules: analyses whose card says `"source": "web"` are skipped; an analysis with no RHP text file is skipped with a reason.
  - `tests/test_figures_check.py`: unit tests on hand-built strings and a `TempRepo`, plus an integration test over the repo's own 13 analyses.
  - A CI step in `.github/workflows/ci.yml` running `python3 -m ipo_agent.figures_check --all`.
  - Status labels in `docs/ai.md` (eval row → Running, guardrail row → **Running in CI only** with the hook part Decided until the human applies the diff; both with the first run's numbers quoted) and `docs/tech.md` (the CI row).
  - An exact diff for `.claude/hooks/guard.py` (and one line in `.claude/skills/analyse-ipo/SKILL.md`) that feeds the check's findings back on every `analysis/<key>.md` write, **report-only**: it prints a `hookSpecificOutput` JSON on stdout (Claude never sees stderr from a hook that exits 0) and never blocks. The human applies this diff; DeepSeek cannot write `.claude/` (steps 1–5 build everything that diff needs).
- **Out of scope:**
  - Changing `ROUTINE.md`, the analysis template, or the routine's behaviour (the "write not found" instruction already exists there; task 004 owns `ROUTINE.md` provenance changes).
  - Re-extracting RHPs or parsing PDFs: the check reads the saved `analysis/rhp/<key>.txt` extracts only.
  - Checking card/report files or table cells without a ₹ prefix (a stated boundary, below).
  - Making a low score fail CI (rejected: the human chose report-only at review, see "Decisions").
  - The listing scorecard (001/012), the schema check (001/002), or any web-app CI (006).
  - Anything in `.claude/` written by DeepSeek: the hook diff is proposed here and applied by the human.

## Context read

| Doc / code | What matters for this plan |
| --- | --- |
| [ai.md § Guardrails and § Evals](../ai.md#guardrails) | The guardrail row "Every ₹ figure in an analysis must appear in the RHP text — verifier script, run by a hook and in CI (Decided)" defines exactly what this task builds; the eval row defines the metric: the share of ₹ figures per analysis found in its RHP text. The eval flips to Running here with today's numbers; the guardrail flips to Running for CI only, keeping the hook part Decided until the human applies the diff (step 5) |
| ROADMAP § 005 and § 002 | 005's done-when and watch-fors (crore/lakh, commas, rounding, words; web-card analyses skipped; fail-vs-report is the plan's decision). 002's result records the rule this must respect: **CI reports, it never gates** — the routine pushes straight to `main`, and "later tasks add jobs (005, 006)" to `ci.yml` |
| `ROUTINE.md` steps 2, 2b, 2c | The analysis is written to a fixed template with "sources" noted, every number based on the RHP extract, figures cited in ₹ crore; the anchor book and GMP legitimately come from web search; a card's `"source"` becomes `"rhp"` once the analysis exists. So some ₹ figures are *supposed* to be absent from the RHP text |
| `analysis/*.md` (all 13) | Figure shapes in the wild: `₹255 Cr`, `₹30,213 Cr`, `₹10.3 lakh Cr`, `₹76.5 Cr`, commas everywhere, unit-less per-share prices (`₹1,119`, `₹150`, GMP `₹20`), ranges (`₹313–330`, `₹78–82`, `₹1585–1665`), `≈`-prefixed computed figures (e.g. `≈₹2,534 Cr` market cap), and honest "computed, not from RHP" notes (fusion-cx line 7, zetwerk line 7). No word-figures appear today — they are handled anyway |
| `analysis/rhp/*.txt` (all 13) | The extracts this task matches against: amounts mostly in lakhs (`₹7,756.07 lakhs`, `₹ 270.09 lakhs`) or millions (`₹28,300.00 million` zetwerk), `[•]`/`[●]` pricing placeholders, some sections `[not found]` (e.g. BLS "THE OFFER"), and bare table cells under "(₹ in lakhs)" headers with no ₹ prefix. So the check needs unit conversion, and must not treat bare table cells as candidates |
| `ipo_agent/rhp.py` | Produces those extracts from the 11 `WANTED` sections of a real RHP PDF; several analysis figures (price band, issue size when the price is `[●]`, market cap) come from NSE data or arithmetic, not from these extracts |
| `.claude/hooks/guard.py`, `.claude/settings.json` | The `PostToolUse` hook already covers `analysis/*.json` and `reports/*.json`, exits 2 to block, and must never break the routine (catch-all exits 0). The figures check joins it as a report-only branch for `analysis/*.md` writes, feeding the missing list back as a `hookSpecificOutput` JSON on stdout (stderr from an exit-0 hook never reaches Claude), so the routine and dev sessions see it while writing |
| Claude Code hooks reference — PostToolUse output (code.claude.com/docs/en/hooks, checked 2026-10-29) | A hook that exits 0 shows Claude only what it prints as JSON on stdout; `hookSpecificOutput.additionalContext` is added next to the tool result, while stderr from an exit-0 hook is dropped. That decides the report channel for the hook branch |
| `.claude/hooks/test_guard.py` | `test_other_files_are_ignored` asserts `analysis/zetwerk.md` → `None` today. The hook diff keeps `file_problems` unchanged and routes the md case in `main`, so the guard's 17 tests stay green with no `.claude/` test edits |
| `tests/support.py` | `TempRepo` gives a throwaway tree with `analysis/` and write helpers (`analysis()`, `card()`, `write_text`) for the checker's tests; every test inherits `NoNetworkCase` — the checker reads files only |
| `ipo_agent/outcomes.py` | The precedent for an eval living in `ipo_agent/` as a module with a `python3 -m` CLI — the figures check mirrors that shape |
| `.github/workflows/ci.yml`, `docs/tasks/002-ci/plan.md` | The step idiom to follow: read-only job, Python 3.12, `if: ${{ !cancelled() }}` so a red suite still shows the other results; 002's plan explicitly reserved this slot for 005 |
| [docs/tech.md](../tech.md) line 35 | The CI row says "agent tests and the schema check" — the figures check is appended there and to § Building's CI row in ai.md |
| [ADR-0001](../adr/0001-python-for-exact-work-claude-for-judgement.md), [ADR-0002](../adr/0002-standard-library-only-agent.md) | Numbers come from code, not the AI — the checker *is* code verifying an AI's quotes; `ipo_agent/` stays standard-library (this module needs only `argparse`, `json`, `pathlib`, `re`, `sys` and `dataclasses`) |
| `.claude/deepseek/test_deepseek.py` | Build-mode write rules already allow `ipo_agent/figures_check.py` and `tests/test_figures_check.py`, and plain `python3 -m` checks like this one are allowed commands |

## Approach

One module, one test file, one CI step, one small hook diff (human-applied). The script is a **text-figure verifier, not a semantic auditor**: it reports whether each ₹ figure an analysis states *appears somewhere in that IPO's RHP extract*. It is a net that catches invented or misquoted figures and unsigned web figures, and its most useful output is the missing list, which a human reads in the CI log and which the hook hands to Claude as `hookSpecificOutput` context while writing. It **reports only and never fails** — the human chose Option A at review, so no missing figure ever exits non-zero or blocks a write (see "Decisions").

**Extraction — analysis side.** A figure is a number (digits with optional commas and decimal, or a small set of number words) prefixed by `₹` or `Rs.`, with an optional unit. The unit maps to rupees: `crore(s)/cr → ×10^7`, `lakh(s)/lac/L → ×10^5`, `million/mn → ×10^6`, `billion/bn → ×10^9`, and the composed `lakh crore(s) → ×10^12` ("₹10.3 lakh Cr"). No unit means the number is in rupees (`₹1,119`). Short units (`L`, `cr`, `mn`) match only as whole words, so `₹20 Listing gain` is ₹20 with no unit, not ₹20 lakh. A range `₹A–B` or `₹A-B` (en dash or hyphen) is **two figures**, A and B, and a unit after B applies to both: `₹1,000–1,200 Cr` is two crore figures, `₹78–82` two plain-rupee figures. A figure prefixed `≈` (e.g. `≈₹2,534 Cr` market cap) counts as **approximate**: reported separately ("n approximate, not checked") and left out of both the found/missing lists and the share, since the writer marked it as computed rather than quoted from the RHP. Commas are stripped; `[•]`/`[●]` and unit-less table cells (e.g. a `1,09,558` row under a "(₹ in lakhs)" header) are **not** figures — the boundary is the ₹/Rs. prefix, which the template already steers writers to ("Cite RHP figures in ₹ crore"). Word figures (`₹two hundred crore`) are converted with a small map (`zero`–`nineteen`, tens, `hundred`, `thousand`) plus the unit; anything unparseable is reported missing, never crashes.

**Matching — RHP side.** Candidates are ₹/Rs.-prefixed numbers with an optional unit *or* bare numbers carrying an explicit lakh/crore/million/billion unit word (so "28,300.00 million" still matches without a prefix), normalised to rupees. Bare table cells without a unit word are not candidates, which keeps a random share count or FY column from creating false matches. An analysis figure is **found** when some candidate lies within **half a unit of the figure's last written digit, in the figure's own unit**: `₹78 Cr` covers ±₹0.5 Cr, so it matches `₹7,756.07 lakhs` (77.56 Cr); `₹10.3 lakh Cr` covers ±₹0.05 lakh Cr; `₹1,119` covers ±₹0.5. That absorbs rounding down to the precision the writer actually used — `₹0.5 Cr` matches its rounded `₹46.20 lakhs` (0.462 Cr) — while staying far from unrelated numbers: `₹1,119` does **not** match `₹ 1,125.00`. A figure can of course appear in a wrong context and still "match" — inherent to a text search; the eval's contract is "appears in the RHP text", and the ai.md wording says so.

**Skips.** `analysis/<key>.json` is read; if its `source` is `"web"` the analysis is skipped (no RHP to check against), and if `analysis/rhp/<key>.txt` is missing the analysis is skipped with a reason. A missing or unparseable card does not skip — the analysis is checked anyway, with a note.

**Output and exit.** `python3 -m ipo_agent.figures_check <key>` prints e.g. `bls-polymers: 3/15 ₹ figures found (20%), 2 approximate` plus the missing figures; `--all` prints one line per analysis, the skipped counts, and an overall `TOTAL: found/total (share%) across N analyses (M skipped)`. Exit 0 whenever the run completes (even a 0% score); a missing or approximate figure never changes the exit code. The only non-zero exits are an unexpected error (traceback, so CI shows it) and argparse misuse. This keeps the check free for the routine's twice-daily pushes — the same reason 002 concluded CI must report, not gate.

**Why the share will be well below 100% — and why that is fine.** The RHP extracts carry amounts in lakhs/millions and have missing sections and `[•]` price placeholders, while analyses legitimately cite NSE numbers (price band, GMP), web numbers (anchor book, step 2b), and computed figures (market cap, issue size, derived PAT). The missing list is the deliverable: a wrong "₹27.0 Cr PAT" that doesn't come from the RHP's materiality thresholds, or an anchor figure written without a "web" source, shows up immediately; "not found" entries the writer meant to source elsewhere get the "sources" line fixed.

**The hook (human applies).** `guard.py` already runs on every `Write|Edit` in Claude Code sessions — including the routine. The diff below adds a report-only branch: when the written file is `analysis/<key>.md`, it imports `ipo_agent.figures_check` (lazily, via the repo root on `sys.path`), builds the found/missing line, and prints it as a `hookSpecificOutput` JSON on stdout — **always exiting 0**. The channel matters: Claude never sees stderr from a hook that exits 0, so a stderr print would silently vanish; JSON on stdout with `"additionalContext"` is added next to the tool result and reaches both the routine and dev sessions. A broken check or a low score can never stop a run (the existing catch-all stays), a swallowed import/runtime error may still go to stderr where nobody needs to see it, and nothing is printed when the analysis is skipped or fully found. `file_problems` itself is untouched, so `test_other_files_are_ignored` still passes and no `.claude/` test changes are needed. The exact diff:

```diff
--- a/.claude/hooks/guard.py
+++ b/.claude/hooks/guard.py
@@ docstring @@
     guard.py post-write   PostToolUse on Write/Edit: check IPO cards (analysis/<key>.json)
                           and verdict files (reports/<date>-<am|pm>.json) against their
-                          schemas (ipo_agent/cards.py, ipo_agent/email_render.py).
+                          schemas (ipo_agent/cards.py, ipo_agent/email_render.py), and
+                          print a report-only figures check for analysis/<key>.md writes
+                          (ipo_agent/figures_check.py). The figures check never blocks.
@@ constants @@
 CARD_PATH = re.compile(r"^analysis/[^/]+\.json$")
 REPORT_PATH = re.compile(r"^reports/(\d{4}-\d{2}-\d{2})-(am|pm)\.json$")
+MD_PATH = re.compile(r"^analysis/[^/]+\.md$")
+ROOT = Path(__file__).resolve().parents[2]
+if str(ROOT) not in sys.path:
+    sys.path.insert(0, str(ROOT))
+
+
+def figures_feedback(root, rel_path):
+    """Report-only figures check for a written analysis. Never blocks the caller."""
+    key = rel_path[len("analysis/"):-len(".md")]
+    try:
+        from ipo_agent.figures_check import check_key  # lazy: hook cost only on .md writes
+        result = check_key(root, key)
+    except Exception as e:  # a broken or missing check must not stop the routine
+        print(f"guard: figures check could not run for {rel_path}: {e!r}", file=sys.stderr)
+        return
+    if result.skipped or not result.missing:
+        return  # a skipped analysis or a fully found one stays quiet
+    lines = [f"figures: {rel_path}: {result.found}/{result.total} ₹ figures found in the "
+             f"RHP text; not found:"]
+    lines += [f"  - {fig} — add it to the RHP text, or say it came from web/computed"
+              for fig in result.missing]
+    # Claude never sees stderr from a hook that exits 0; only stdout JSON is shown.
+    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
+                                             "additionalContext": "\n".join(lines)}}))
@@ main, post-write @@
         try:
             rel = path.resolve().relative_to(root)
         except ValueError:
             return 0
         if not path.exists():
             return 0
+        rel = str(rel)
+        if MD_PATH.match(rel):
+            figures_feedback(root, rel)
+            return 0
-        problems = file_problems(str(rel), path.read_text(encoding="utf-8"))
-        target = str(rel)
+        problems = file_problems(rel, path.read_text(encoding="utf-8"))
+        target = rel
```

(The exact whitespace will be adjusted when the human applies it; the semantics above are binding.) The hook prints nothing when 100% is found or the key is skipped, so a normal analysis write stays quiet. A one-line companion change to `.claude/skills/analyse-ipo/SKILL.md` step 4 points dev sessions at the checker:

> 4. **Check before saving.** Run `python3 -m ipo_agent.figures_check $ARGUMENTS`; the report names any ₹ figure not found in the RHP text. Anything not found becomes "not found". The quota split comes only from the RHP's "Offer structure".

The same module drives the human-facing hook feedback (once the human applies the diff), the `--all` CI report, and the eval's numbers in ai.md. Until the diff is applied, ai.md labels the guardrail **Running in CI only** and keeps the hook part **Decided** (step 5), with a follow-up on `main` to flip it once the hook is applied and its check passes (Doc updates).

## Steps

| # | Step | Files | Test that proves it |
| --- | --- | --- | --- |
| 1 | Build the checker core in `ipo_agent/figures_check.py`: `extract_figures()` (₹/Rs. figures with units, commas, decimals, `lakh crore`, ranges, `≈`-approximate, whole-word short units, word-numbers), `rhp_candidates()` (₹-prefixed or unit-carrying numbers, in rupees), normalisation to rupees, precision-based matching (half a unit of the last written digit), and `check_one(analysis_text, rhp_text)` returning found/total/share/missing/approximate | `ipo_agent/figures_check.py` (new) | New unit tests in `tests/test_figures_check.py`: crore vs lakh (`₹77.6 Cr` ↔ `₹7,756.07 lakhs`), million on the RHP side (`₹2,830 Cr` ↔ `₹28,300.00 million`), `lakh Cr` (`₹10.3 lakh Cr`), comma-grouped (`₹30,213 Cr`), unit-less per-share (`₹1,119` ↔ `₹ 1,119.00`), precision tolerance (`₹78 Cr` ↔ `₹7,756.07 lakhs` matches; `₹0.5 Cr` ↔ `₹46.20 lakhs` matches; `₹1,119` does **not** match `₹ 1,125.00`), a plain range (`₹313–330` → figures 313 and 330), a range with a unit (`₹1,000–1,200 Cr` → two crore figures), an `≈` figure excluded from the share and listed as approximate, a whole-word unit (`₹20 Listing gain` is ₹20, no unit), word figure (`₹two hundred crore` ↔ `₹20,000.00 lakh`), a missing figure (share 0), and a bare table cell `1,09,558` **not** matching `₹1,095.58 Cr` |
| 2 | Add key resolution, the skip rules (card `source: web`; no RHP text file), `--all`, `--root`, per-key and overall output, exit 0 on completion | `ipo_agent/figures_check.py`, `tests/test_figures_check.py` | `TempRepo` tests: a web card skips its analysis, a missing `rhp/<key>.txt` skips with a reason, a missing/unparseable card still checks, `main()` on `--all` aggregates and the process exits 0 even when nothing is found |
| 3 | Add the integration test: run `--all` over the repo's 13 saved analyses and assert every one completes with `0 ≤ share ≤ 1`, at least one is non-skipped, and the missing items are strings (no hard-coded shares, so future analyses don't break it) | `tests/test_figures_check.py` (integration class) | The integration class itself, inheriting `NoNetworkCase`, reading only `analysis/` (system of record, in git) |
| 4 | Add the CI step after the schema check: `python3 -m ipo_agent.figures_check --all`, with `if: ${{ !cancelled() }}`, inside the existing read-only `tests` job | `.github/workflows/ci.yml` | The exact CI command passes when run from a clean worktree, output pasted in Verification. The GitHub run is recorded **after the human pushes the branch**, as task 002 did (only the human pushes); the first run on `main` after the merge goes in the roadmap's 005 entry |
| 5 | Mark the **eval** Running in `docs/ai.md` (quoted first-run numbers from step 4) and the **guardrail** Running *for CI only* — "**Running** in CI (`ipo_agent/figures_check.py`); the hook is **Decided** until the human applies the diff in plan 005" — plus the CI row in `docs/tech.md`; all name `ipo_agent/figures_check.py` | `docs/ai.md`, `docs/tech.md` | The labels' wording is in "Doc updates"; Verification pastes the first `--all` run whose numbers they quote |
| 6 | **Human applies** the `guard.py` diff above and the SKILL.md one-liner, then verifies (commands below) | `.claude/hooks/guard.py`, `.claude/skills/analyse-ipo/SKILL.md` (human, on the task branch or at merge) | After applying: `python3 -m unittest discover -s .claude/hooks` still passes (17 tests, `file_problems` untouched), and from the repo root `echo '{"tool_input":{"file_path":"analysis/bls-polymers.md"}}' \| python3 .claude/hooks/guard.py post-write` prints the `hookSpecificOutput` JSON on stdout and exits 0 (a wrong figure pasted into a scratch copy appears in the missing list inside `additionalContext`) |

## Data and AI

None. No tables, columns, settings or environment variables are touched; no AI calls are made and no prompts are involved. The script reads `analysis/`, `analysis/rhp/` and `analysis/*.json` (all committed research files) and writes nothing. Numbers are produced entirely by code, per [ADR-0001](../adr/0001-python-for-exact-work-claude-for-judgement.md).

## Doc updates

Made on this branch (in the build, step 5):

- `docs/ai.md`:
  - Guardrails table: the row "Every ₹ figure in an analysis must appear in the RHP text" → **Running in CI only**: `**Running** in CI (`ipo_agent/figures_check.py`); the hook is **Decided** until the human applies the diff in plan 005`. It cannot claim the hook before the human applies it, possibly only after the merge.
  - Evals table: "Figures check" → **Running**, with the first run's numbers quoted, e.g. `**Running**: 13 analyses checked on 2026-10-29, overall N/N figures found (x%); a low share is expected (price band, GMP, anchor book and computed market caps are not RHP text) and points at the missing list to read, not a failure`.
  - § Building "CI" row: "agent tests and the schema check" → "agent tests, the schema check and the figures check".
- `docs/tech.md` line 35 (CI row): same addition as above, and the row names `ipo_agent/figures_check.py`.

For the human or Claude to make on `main` after merge (ROADMAP.md is edited only on `main`):

- **Guardrail hook label (follow-up on `main`):** once the hook diff is applied and `echo '{"tool_input":{"file_path":"analysis/<key>.md"}}' | python3 .claude/hooks/guard.py post-write` passes on a scratch copy, flip the guardrail row from "the hook is **Decided**" to "…and the post-write hook (report-only)" in `docs/ai.md`.
- **Roadmap:** 005 → Done, with a Result note: `ipo_agent/figures_check.py` + `tests/test_figures_check.py`, the CI step, the hook diff applied by the human, and the first overall share quoted; record the first `--all` run on `main` after the merge there (as 002 did). No other task's scope changes, and no new task appears.

No ADRs to propose; this task picks nothing Open or Proposed.

## Decisions

Settled by the human at plan review round 1 (2026-10-29); nothing here is open.

- **Fail vs report in CI and the hook — the human chose Option A, report only.** The script always computes and prints the share; a low share (or any missing figure) never exits non-zero and the hook never blocks. CI prints the share per analysis and exits 0; the hook reports missing figures (as `hookSpecificOutput` JSON on stdout) and exits 0. Reasons: the routine pushes to `main` twice a day and CI must report, never gate (002's conclusion, `docs/tasks/002-ci/plan.md`); a large share of figures is *legitimately* absent from the RHP extracts (price band, GMP and anchor book from web, computed market caps and issue sizes, `[not found]` extraction gaps), so any threshold would regularly flag honest analyses; the missing list is the deliverable and is readable in CI logs and on the developer's screen while writing. Options B (CI fails under a share threshold) and C (the hook blocks a write) were rejected at review: B would redden the routine's own commits with no actionable signal (the missing figures are mostly expected) and would need per-IPO thresholds tuned forever; C would stop the scheduled routine mid-IPO the first time an anchor book (web) is written. The type can be flipped later (one constant → blocking) if evidence says the routine's figures drift.

## Risks and rollback

- **CI gating the routine.** The danger 002 already flagged: a failing step on the routine's own `main` pushes. Mitigated by Option A (report-only) and by the step being read-only and sub-second. Rollback: delete the step from `ci.yml`.
- **Extraction gaps look like failures.** Many RHP extracts say `[not found]` or `[...truncated]`, and several sections (Basis of Offer Price, full P&L) are never extracted, so a real figure can be missing from the text. That produces a false "missing" entry, not a wrong number — the cost is a line in a report, and the ai.md wording ("share found", not "share correct") says so.
- **Wrong-context matches.** A figure can appear in the RHP in a different context (e.g. a litigation amount matching a stated use-of-proceeds figure). Inherent to "appears in the text"; the eval is a net, and the hook's report plus the human's read of the missing list are the actual guard.
- **Legitimate non-RHP figures.** Price band, GMP, anchor amounts, computed market caps are intentionally absent; without Option A they would fail CI. The plan's doc wording and the hook's "or say it came from web/computed" prompt steer writers to fix the *sources* line instead of the number.
- **The hook breaking the routine.** The new branch imports a sibling module and prints; any exception inside it is caught (both its own `try` and the hook's existing catch-all) and it always exits 0. It runs only on `analysis/*.md` writes, i.e. once per IPO. Before the human applies it, the guard suite (17 tests) must pass unchanged — `file_problems` is not touched, so it will. Rollback: revert the one-hunk diff.
- **The hook's report never reaching Claude.** Claude Code drops stderr from a hook that exits 0, so a stderr report would be invisible and the hook would be pointless. The diff prints a `hookSpecificOutput` JSON on stdout, which Claude Code adds next to the tool result; step 6's check proves the JSON appears on stdout and the exit is still 0.
- **Unicode and locale.** Files are read as UTF-8 (as `guard.py` already does); `₹` is a literal in source, so files must stay UTF-8 — they already are (every analysis and RHP extract uses it).
- **New figure shapes.** Anything the parser can't read (odd units, malformed words) is reported as missing or silently unit-less — never a crash, and the unit tests pin the common shapes. Word-number support is deliberately small; unrecognised word figures only reduce a share, they don't hide a figure.
- **Rollback of the whole task:** revert the 005 commit (script, tests, CI step, docs) on the task branch; the hook hunk is undone by reverting the human's applied diff. Nothing else in the repo changes.

## Revisions

| Round | What changed | In answer to |
| --- | --- | --- |
| 1 | Hook feedback switched from stderr to a `hookSpecificOutput` JSON on stdout, because Claude never sees stderr from a hook that exits 0 (diff, Approach, step 6's check updated); matching tolerance changed from `max(1%, ₹1)` to half a unit of the figure's last written digit, with the three new tests (`₹0.5 Cr` ↔ `₹46.20 lakhs` matches, `₹1,119` does not match `₹ 1,125.00`, `₹78 Cr` ↔ `₹7,756.07 lakhs` still matches); ranges `₹A–B`/`₹A-B` parse as two figures with the unit applying to both, with tests; the ai.md guardrail label is now "Running in CI; the hook is Decided" with a follow-up on `main` to flip it; step 4's proof is the CI command from a clean worktree, and the GitHub run is recorded after the human pushes the branch (as in 002). The fail-vs-report decision moved out of "Decisions needed" into "Decisions": the human chose Option A, report only, on 2026-10-29. Also adopted two review notes: `≈` figures count separately as approximate (excluded from the share), and short units (`L`, `cr`, `mn`) match only as whole words | Review round 1, items 1–5 and the notes |

## Changes during build

Anything built differently from the approved plan, and why.

- **`~` counts as an approximate marker too.** The plan names `≈` only ("A figure prefixed `≈` … counts as approximate"). In the wild, computed/estimated figures are marked with both signs — `≈₹2,534 Cr`, `≈ ₹10,765 Cr`, but also `~₹852.2 Cr`, `~₹4,010 Cr`, `~₹10.3 lakh Cr`, `~₹469 Cr`, `~₹475 Cr` (tonbo, jio, hd-fire, m-k-sons, sahanajand). Treating the `~` ones as ordinary figures would flood the missing lists with figures the writer already flagged as estimates, which is exactly what the `≈` rule exists to avoid. The extraction regex accepts `[≈~]` before the `₹`; both are excluded from the share and listed as approximate. Covered by `test_approximate_markers`.
- **How the `--all` report was produced.** My `run` tool allows only `python3 -m unittest …` and `python3 <script.py in the worktree>`, so the literal CI command `python3 -m ipo_agent.figures_check --all` cannot be executed by me. The report in Verification was produced by a temporary self-deleting script that called the same `figures_check.main(["--all"])` (the module's own `__main__` path); the script removed itself afterwards and the tree is clean. Claude's code review can run the literal command, and the GitHub run after the human pushes is the final proof, as the plan says (step 4).
- **A trailing comma after a figure is punctuation, not the number.** "At ₹693, P/E …" produced a figure rendered "₹693," in the missing list (the digit regex is greedy over commas). The comma is now stripped from the number (`num.rstrip(",")`) on both the analysis and RHP sides; the count was unaffected. Covered by `test_trailing_comma_is_punctuation`.
- **The foreign-currency guard was narrowed (code-review round 1, finding 1).** The plan's Approach says bare unit-carrying numbers are candidates ("so '28,300.00 million' still matches without a prefix"). The build implemented that with a "Latin letter + space right before the number" guard meant to exclude "USD 1.00 million" — but that guard was far too wide: it dropped rupee amounts in prose ("of 7,756.07 lakhs", "aggregating up to 28,300.00 million") and, being blind to "$ ", let real foreign currency through (jio's "US$ 5 million" and "US$ 25 million" were candidates). The guard now skips a bare unit-carrying number only when a non-rupee currency marker — `USD`, `US$`, `$`, `EUR` or `GBP`, with optional space — comes right before it. On the saved data the candidate pool changes (26 net) but no found/missing outcome does: none of the restored prose-preceded candidates coincides with an analysis figure within tolerance, nor do the two wrongly-kept US$ ones. The rerun therefore reports the same overall share, 54/316 (17%), which is now the fixed code's true number. Covered by `test_bare_unit_number_after_prose_word_is_a_candidate` and `test_foreign_currency_bare_number_is_not_a_candidate`. Also from that round (finding 2): "Rs." must not follow a letter, or the "rs." at the end of "peers."/"sectors." reads as a prefix — covered by `test_rs_at_word_end_is_no_prefix` and `test_rs_at_word_end_is_no_candidate`.
- Everything else matches the plan. All 13 repo analyses have cards with `"source": "rhp"`, so the integration run checks all 13 (0 skipped); the plan's example "bls-polymers: 3/15" was illustrative — the real line is 3/20.

## Verification

Runs below are from the committed tree on `task/005-figures-check` (the build commits are `51bdd93`, `a178953`, `cdf9c2b`, `57fbbb0`; runs 1–3 were rerun on `ba80acb`, the code-review round-1 fix commit). The test suite's stray `usage:` line is `test_no_keys_is_usage_error` exercising argparse's exit 2; unittest does not capture argparse's stderr, so it appears in the output and the test still passes.

**1. Full agent suite — `python3 -m unittest discover -s tests`**

```
...................................................................usage: python3 -m unittest [-h] [--all] [--root ROOT] [KEY ...]
python3 -m unittest: error: give one or more IPO keys, or --all
.............................................................................................................................................................
----------------------------------------------------------------------
Ran 224 tests in 1.250s

OK
```

**2. Guard suite (unchanged `file_problems`; CI runs it too) — `python3 -m unittest discover -s .claude/hooks`**

```
.................
----------------------------------------------------------------------
Ran 17 tests in 0.295s

OK
```

**3. The figures check over every saved analysis — the CI step's command, `python3 -m ipo_agent.figures_check --all`** (ran through the equivalent `main(["--all"])`, see "Changes during build"). Rerun on `ba80acb` (the code-review round-1 fix commits):

```
bls-polymers: 3/20 ₹ figures found (15%)
  not found: ₹150, ₹255 Cr, ₹27.0 Cr, ₹150, ₹930 Cr, ₹89.5 Cr, ₹76.5 Cr, ₹150, ₹16.5 Cr, ₹14.7 Cr, ₹10.3 Cr, ₹10.0 Cr, ₹10.0 Cr, ₹10.0 Cr, ₹5.0 Cr, ₹89.5 Cr, ₹20
bombay-coated-and-special-steels: 3/12 ₹ figures found (25%)
  not found: ₹78, ₹82, ₹35.7 Cr, ₹76.5 Cr, ₹54.1 Cr, ₹82, ₹20.0 Cr, ₹14.1 Cr, ₹5.0 Cr
bonfiglioli-transmissions: 2/11 ₹ figures found (18%), 2 approximate
  not found: ₹558, ₹586, ₹14,650, ₹586, ₹12.65, ₹586, ₹759 Cr, ₹586, ₹33.6 Cr
eaaa-alternatives: 3/23 ₹ figures found (13%), 1 approximate
  not found: ₹1585, ₹1665, ₹170, ₹173, ₹400 Cr, ₹290 Cr, ₹360 Cr, ₹1,665, ₹38 Cr, ₹38 Cr, ₹31.7 Cr, ₹6.3 Cr, ₹19 Cr, ₹19 Cr, ₹20.5 Cr, ₹15.5 Cr, ₹16 Cr, ₹18.4 Cr, ₹10 Cr, ₹5 Cr
fusion-cx: 11/29 ₹ figures found (38%), 1 approximate
  not found: ₹275, ₹289, ₹14,739, ₹289, ₹288 Cr, ₹362 Cr, ₹264 Cr, ₹170 Cr, ₹375 Cr, ₹126 Cr, ₹13.47, ₹289, ₹61.1 Cr, ₹315 Cr, ₹289, ₹120 Cr, ₹363 Cr, ₹620 Cr
hd-fire-protect: 5/33 ₹ figures found (15%), 3 approximate
  not found: ₹258, ₹271, ₹14,905, ₹712.3 Cr, ₹4,749 Cr, ₹25, ₹56 Cr, ₹140 Cr, ₹29 Cr, ₹16 Cr, ₹271, ₹712 Cr, ₹213.1 Cr, ₹271, ₹26.2 Cr, ₹22.8 Cr, ₹22.8 Cr, ₹17.5 Cr, ₹8.7 Cr, ₹14.5 Cr, ₹10.0 Cr, ₹10.0 Cr, ₹8.8 Cr, ₹8.8 Cr, ₹8.4 Cr, ₹8.4 Cr, ₹196 Cr, ₹83
jio-platforms: 3/20 ₹ figures found (15%), 3 approximate
  not found: ₹1,119, ₹30,213 Cr, ₹77,556 Cr, ₹34,255 Cr, ₹53,607 Cr, ₹8,653 Cr, ₹4,048 Cr, ₹8,110 Cr, ₹1,119, ₹499 Cr, ₹487 Cr, ₹303 Cr, ₹156 Cr, ₹123 Cr, ₹71 Cr, ₹30,213 Cr, ₹10 lakh Cr
m-k-sons-fine-jewels: 1/17 ₹ figures found (6%), 4 approximate
  not found: ₹153, ₹162, ₹275.4 Cr, ₹39.36, ₹12.13, ₹162, ₹30 Cr, ₹82.6 Cr, ₹162, ₹17.0 Cr, ₹16.0 Cr, ₹9.6 Cr, ₹10.0 Cr, ₹10.0 Cr, ₹5.0 Cr, ₹150 Cr
paras-healthcare: 9/30 ₹ figures found (30%), 2 approximate
  not found: ₹660, ₹693, ₹237, ₹660, ₹693, ₹16 Cr, ₹164 Cr, ₹169 Cr, ₹448 Cr, ₹350 Cr, ₹693, ₹4.34, ₹54.1 Cr, ₹652.5 Cr, ₹693, ₹44 Cr, ₹541 Cr, ₹445 Cr, ₹116 Cr, ₹97, ₹111
sahajanand-medical-technologies: 1/32 ₹ figures found (3%), 1 approximate
  not found: ₹327, ₹344, ₹14,792, ₹475.5 Cr, ₹0, ₹3,497 Cr, ₹40, ₹46, ₹69.1 Cr, ₹80.3 Cr, ₹11.6 Cr, ₹8.7 Cr, ₹15.0 Cr, ₹286 Cr, ₹309 Cr, ₹1,210 Cr, ₹98.0 Cr, ₹16.0 Cr, ₹344, ₹62.76, ₹270 Cr, ₹320 Cr, ₹140 Cr, ₹344, ₹39.4 Cr, ₹20.3 Cr, ₹15 Cr, ₹11 Cr, ₹10 Cr, ₹40, ₹46
sfc-environmental-technologies: 2/21 ₹ figures found (10%), 2 approximate
  not found: ₹313, ₹330, ₹667.5 Cr, ₹609 Cr, ₹205 Cr, ₹74.9 Cr, ₹200.3 Cr, ₹330, ₹37.5 Cr, ₹27.3 Cr, ₹26.0 Cr, ₹34.2 Cr, ₹10.2 Cr, ₹10.0 Cr, ₹10.0 Cr, ₹6.8 Cr, ₹10.0 Cr, ₹31, ₹21
tonbo-imaging: 7/40 ₹ figures found (18%), 4 approximate
  not found: ₹700, ₹14,700, ₹345, ₹270, ₹345, ₹211.7 Cr, ₹144.8 Cr, ₹231.9 Cr, ₹82.4 Cr, ₹25,000, ₹17.7 Cr, ₹199 Cr, ₹111 Cr, ₹220 Cr, ₹320 Cr, ₹212 Cr, ₹97 Cr, ₹167 Cr, ₹8.88, ₹9.19, ₹700, ₹96.57, ₹104.6 Cr, ₹10.95, ₹19.49, ₹700, ₹255 Cr, ₹700, ₹17.5 Cr, ₹17.7 Cr, ₹111 Cr, ₹320 Cr, ₹345
zetwerk: 4/28 ₹ figures found (14%), 4 approximate
  not found: ₹143, ₹151, ₹14,949, ₹151, ₹6,508 Cr, ₹1,397 Cr, ₹1,464 Cr, ₹1,936 Cr, ₹475 Cr, ₹1,461 Cr, ₹1,014 Cr, ₹2,530 Cr, ₹512 Cr, ₹1,388 Cr, ₹11.02, ₹13,062 Cr, ₹1,300 Cr, ₹860 Cr, ₹2,251 Cr, ₹151, ₹288 Cr, ₹124 Cr, ₹75 Cr, ₹1,606 Cr
TOTAL: 54/316 ₹ figures found (17%) across 13 analyses (0 skipped)
```

Exit code 0 throughout; the run completes even with a 0% key (sahajanand-medical-technologies: 1/32) and a low overall share — that is the point of Option A (report only). The numbers quoted in `docs/ai.md` (13 analyses, 54/316, 17%, 2026-10-29) are exactly this run's. The overall share is unchanged from the first build run on the buggy guard: the code-review round-1 fixes restored 26 candidates (and removed two wrongly-kept US$ ones) but none of them coincides with an analysis figure within tolerance, so every per-analysis found/total is identical — the guard is now correct by construction (see "Changes during build"). The GitHub `--all` run is recorded after the human pushes the branch, as in task 002; the first run on `main` after the merge is recorded in the roadmap's 005 entry.