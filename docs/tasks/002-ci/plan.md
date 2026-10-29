---
task: 002-ci
status: code-review
branch: task/002-ci
assigned_by: Vijay
planner: Claude Code (opencode unavailable)
builder: Claude Code (opencode unavailable)
reviewer: Human, or a fresh reviewer given the diff
---

# 002: CI workflow

**Who built this.** On 2026-10-29 the human asked Claude Code to work on task 002 because opencode was unavailable. Claude wrote this plan and built it in one step. No plan review took place, and Claude has not reviewed its own code. The review is still owed: by the human, or by a fresh Claude session running `/review-code 002` that sees only the diff and this plan.

## Task

> **Task 002 from `docs/tasks/ROADMAP.md`**
>
> ### 002 · CI workflow
>
> A GitHub Actions workflow that runs on every push and pull request. It runs the agent tests and `.claude/hooks/test_guard.py`, which already checks every saved card and report against its schema (the **Schema check** eval in [ai.md](../../ai.md#evals)).
>
> - **Done when:** CI passes on the task branch and on `main`; `ai.md` marks Schema check as Running; `tech.md` marks CI as Running.
> - **Watch for:** the routine pushes to `main` twice a day, so CI must be fast and read-only. Later tasks add jobs (005, 006).
> - **Already true after 001:** `python3 -m unittest discover -s tests` takes under a second and needs no network.
>   - The NSE smoke workflow from task 003 (`.github/workflows/nse-stock-smoke.yml`) does call NSE.
>   - So CI runs the test suite only, not that workflow's probe.
> - **Read:** [tech.md](../../tech.md), [ai.md § Evals](../../ai.md#evals).

## Goal and scope

- **In scope:**
  - `.github/workflows/ci.yml`: one job that runs both suites on every push to any branch, on every pull request, and when started by hand.
  - Status labels in `tech.md`, `ai.md` and `hackathon.md`, plus one line in AGENTS.md § Building.
- **Out of scope:**
  - Jobs for the web app (task 006) and the figures check (task 005).
  - The NSE smoke probe, and any other live call.
  - Branch protection or required checks (see Risks).
  - Changing any test or the guard.

## Context read

| Doc / code | What matters for this plan |
| --- | --- |
| ROADMAP.md § 002 | The scope and done-when quoted above. 005 and 006 will add jobs later. |
| AGENTS.md | Tests use saved files only and make no live calls; docs and status labels change in the same commit. |
| tech.md | The CI row (Decided), the GitHub row (about 2,000 free Actions minutes a month), and the `.github/workflows/` row. |
| ai.md § Guardrails, § Evals, § Building | Schema check is Decided; the CI row says "app tests against a Neon branch", which is still to come. |
| `.claude/hooks/test_guard.py` | Standard library only. Its docstring gives the command `python3 -m unittest discover -s .claude/hooks`. `CardTests` and `ReportTests` read every `analysis/*.json` and `reports/*.json`; that is the schema check. |
| `.github/workflows/nse-stock-smoke.yml` | Ran on this repo's runners with `actions/checkout@v4`, `actions/setup-python@v5` and Python 3.12 (run 40869763010). CI uses the same pins and the same idiom. |
| `tests/` | 188 tests, under a second, no network (`NoNetworkCase`), with no use of `pdftotext`. |

## Approach

One workflow, one job, two steps:

1. `python3 -m unittest discover -s tests`: the agent tests.
2. `python3 -m unittest discover -s .claude/hooks`: the guard tests, which include the schema check of every saved card and report. The step has `if: ${{ !cancelled() }}`, so it still runs when step 1 fails. A red build then shows both results.

Other settings:

- **Triggers:** `push` (every branch), `pull_request` and `workflow_dispatch`.
- **No `paths-ignore`:** the routine's pushes to `main` carry the new cards and reports, and those are the commits the schema check exists for.
- **Read-only:** `permissions: contents: read`, no secrets, and no network beyond checkout and setup-python.
- **Fast:** `timeout-minutes: 5`. Both suites take under a second together; checkout and setup take most of the run.
- **Concurrency:** on task branches the group is the ref, so a new push cancels the older run. On `main` the group is the commit SHA, so runs never share a group and every routine push gets its own result. (Keying `main` by ref with `cancel-in-progress: false` isn't enough: GitHub keeps only one pending run per group and cancels the others.)
- **Python 3.12:** the same version as the smoke workflow and local development.

## Steps

| # | Step | Files | Test that proves it |
| --- | --- | --- | --- |
| 1 | Add the workflow | `.github/workflows/ci.yml` | Parses as YAML. Both commands pass from a clean worktree (tracked files only) under `TZ=UTC`, `LC_ALL=C.UTF-8`. A bad card and a misnamed report each make the schema step fail (see Verification) |
| 2 | Update status labels | `docs/tech.md`, `docs/ai.md`, `docs/hackathon.md` | Each Running label names `.github/workflows/ci.yml` |
| 3 | Tell builders about CI | `AGENTS.md` § Building | — |
| 4 | Run on GitHub | — | The human pushes `task/002-ci`; the run URL goes into Verification. After merge, the first run on `main` is the second piece of evidence |

## Data and AI

None.

## Doc updates

Made in this branch:

- `tech.md`: CI → Running; the GitHub row → "Repo and CI running; import and stock worker decided"; `.github/workflows/` → Running / Decided.
- `ai.md`: Schema check eval → Running; the CI row in § Building → Running for the agent, with app tests against a Neon branch still Decided.
- `hackathon.md` § 6: "CI or test output _(to build)_" now points to `ci.yml`.
- `AGENTS.md` § Building: one line saying CI runs both suites and both must pass.

For the human or Claude to make on `main` after merge:

- **Roadmap:** 002 → Done, with the run URLs.
  - 005 → Ready (it depends on 001 and 002).
  - 006 and 009 stay Blocked on their other dependencies.
  - The optional item "Changes to `ROUTINE.md` reviewed through a PR" now has its dependency met.
- **Not done here:** `hackathon.md` § 6 still says `tests/` _(to build)_ in two rows, which has been stale since task 001 merged. That is a one-line fix on `main`.

## Decisions needed

None. One thing for the human to know: **don't make CI a required status check on `main`.** The routine pushes straight to `main` without a pull request, and a required check would block it. CI reports results; it doesn't gate anything.

## Risks and rollback

- **Actions minutes.** About one billed minute per run. The routine makes about 44 pushes a month (two per weekday). With development pushes and pull requests, that is well under 200 of the roughly 2,000 free minutes. Pushes from a branch with an open pull request run twice (once for `push`, once for `pull_request`); that is cheap, so it isn't worth splitting the triggers.
- **A routine push fails CI.** Nothing is blocked. GitHub marks the commit red and, by default, notifies the account that pushed it. The failure means a card or report doesn't match its schema, which is exactly the signal this task exists to give.
- **Runner differences.** The tests passed under UTC, Asia/Kolkata and America/Los_Angeles time zones and under the C locale, so the runner's UTC default doesn't matter.
- **Action versions.** `checkout@v4` and `setup-python@v5` are the same major tags the smoke workflow already ran with on this repo.
- **Rollback:** delete `.github/workflows/ci.yml` and revert the label changes.

## Revisions

| Round | What changed | In answer to |
| --- | --- | --- |

## Changes during build

None. Plan and build were done together; see the note at the top.

## Verification

Run in `.worktrees/002-ci` (tracked files only), Python 3.12.3, on 2026-10-29.

YAML parses:

```text
$ python3 -c "import yaml; d=yaml.safe_load(open('.github/workflows/ci.yml')); print(d[True])"
{'push': None, 'pull_request': None, 'workflow_dispatch': None}
```

Both suites, as the runner runs them:

```text
$ TZ=UTC LC_ALL=C.UTF-8 python3 -m unittest discover -s tests
Ran 188 tests in 0.250s

OK
$ TZ=UTC LC_ALL=C.UTF-8 python3 -m unittest discover -s .claude/hooks
Ran 17 tests in 0.260s

OK
```

The schema step fails on bad data. A temporary card with `verdict: "buy"`, then a report copied to `reports/2099-01-01-am.json` (the date in the file name doesn't match its contents); both were removed afterwards:

```text
FAIL: test_every_card_in_the_repo_passes (test_guard.CardTests.test_every_card_in_the_repo_passes) (card='zz-ci-probe.json')
FAILED (failures=1)
FAIL: test_every_report_in_the_repo_passes (test_guard.ReportTests.test_every_report_in_the_repo_passes) (report='2099-01-01-am.json')
FAILED (failures=1)
```

Also passed under `TZ=Asia/Kolkata` and `TZ=America/Los_Angeles`, and under `LC_ALL=C`.

**On GitHub (to fill in after the human pushes `task/002-ci`):**

- Task branch run: _pending_
- First run on `main` after merge: _pending_
