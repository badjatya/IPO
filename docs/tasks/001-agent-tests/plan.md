---
task: 001-agent-tests
status: plan-review
branch: task/001-agent-tests
assigned_by: Vijay
planner: DeepSeek (opencode)
reviewer: Claude Code
---

# 001: Agent test suite

## Task

Quoted from [docs/tasks/ROADMAP.md](../../ROADMAP.md#001--agent-test-suite):

> `unittest` tests for the existing agent in `ipo_agent/`, using saved files only, so that later changes have a safety net. Cover allotment odds per category, trends, snapshot merging, phase and `needs_*` flags, the quiet-run decision, card merging, email rendering of a saved report, `outcomes --no-fetch`, and the Investorgain, NSE and SEBI parsers.
>
> - **Done when:** `python3 -m unittest discover -s tests` passes with no network access; each module above has tests; `tech.md` and `ai.md` show agent tests as Running.
> - **Out of scope:** changing the agent's behaviour. Bugs the tests reveal are listed in the plan for the human, not fixed here.
> - **Watch for:** parser fixtures (saved HTML and JSON) go under `tests/fixtures/`, because DeepSeek can't write to `data/`. Network calls are stubbed at `net.py`.
> - **Read:** AGENTS.md § Building, [arch.md § 4.1](../../arch.md#41-ipo-routine-running), [ADR-0002](../../adr/0002-standard-library-only-agent.md).
> - **Start:** `/plan-task Task 001 from docs/tasks/ROADMAP.md`

## Goal and scope

- **In scope:**
  - A `tests/` tree with `unittest` tests for the existing modules named in the task: `allotment`, `trends`, `snapshot` (merging, phase, `needs_*` flags), `quiet`, `cards`, `email_render`, `outcomes` (including `--no-fetch`), and the `investorgain`, `nse` and `sebi` parsers.
  - Parser fixtures under `tests/fixtures/`, and small helpers under `tests/support.py` for temporary repo roots and fake HTTP clients.
  - Status-label updates in `docs/tech.md` and `docs/ai.md` once the suite runs.
- **Out of scope:**
  - Any change to `ipo_agent/` behaviour, signatures or output. The only production-file changes are documentation status labels.
  - `rhp.py` (not named in the task; its PDF path needs an external binary) and `net.py` internals beyond using it as the network boundary in tests.
  - A CI workflow (task 002), figures check (005), and the stock worker.
  - Fixing any bug the tests reveal; those are recorded under "Bugs found" for the human.
  - Editing `data/`, `analysis/`, `reports/`; the tests only read them.

## Context read

| Read | What matters |
| --- | --- |
| [docs/tasks/ROADMAP.md](../../ROADMAP.md) task 001 | Scope, done-when, fixtures location, and the "no behaviour changes" rule. |
| [AGENTS.md](../../../../AGENTS.md) § Building | Python tests use `unittest` under `tests/`, run with `python3 -m unittest discover -s tests`; no live sites or AI APIs; saved files are fixtures; docs change in the same commit. |
| [docs/arch.md § 4.1](../../arch.md#41-ipo-routine-running) | Module boundaries: `net` → fetchers → `snapshot`/`allotment`/`trends`; `quiet` reads the snapshot and decides whether Claude is needed; `cards` and `email_render` consume saved analysis; `outcomes` is the scorecard. |
| [ADR-0001](../../adr/0001-python-for-exact-work-claude-for-judgement.md) | Numbers and decisions such as odds, phase and quiet are computed in code; tests must pin that arithmetic. |
| [ADR-0002](../../adr/0002-standard-library-only-agent.md) | `ipo_agent/` stays standard library only, so the tests use `unittest`, `unittest.mock`, `tempfile`, `json`, `pathlib` and no test framework. |
| [docs/tech.md](../../tech.md) | Contains the two status labels to move: "Agent tests" in the at-a-glance table and `tests/` in the repository layout. |
| [docs/ai.md](../../ai.md) | Row `tests/ + CI` currently says Decided; the agent-test half becomes Running while CI stays Decided. |
| `ipo_agent/allotment.py` | `min_lots` boundaries at ₹2 L / ₹10 L; `odds` is `1/times` floored at 1; `categories` rounds money and builds the return-on-blocked figure; `best_category` needs live odds. |
| `ipo_agent/trends.py` | Daily GMP readings keyed by Investorgain time; 8% / 1%-of-price significance; peak-based "falling"; 7-day window; 5-point cap; subscription day bucketing at 10:00 IST and close-date clamp. |
| `ipo_agent/investorgain.py` | Parses `self.__next_f.push` chunks and `reportTableData`; status codes U/O/C/LP/LN; GMP and low/high extraction; board from `~ipo_category1`. |
| `ipo_agent/nse.py` | `parse_subscription` maps ordered category rules and skips rows with no offered quantity; `parse_detail` reads `issueInfo.dataList`, price range, lot, issue period, subscription. |
| `ipo_agent/sebi.py` | Parses the RoC document table; skips corrigendum/addendum links; extracts the PDF link from the detail page. |
| `ipo_agent/snapshot.py` | Merges Investorgain and NSE by normalised company name; filters SME and old listings; computes `phase`, `needs_analysis`, `needs_card`, `needs_anchor_update`; captures per-source errors; attaches trends. |
| `ipo_agent/cards.py` | Card schema and `needs_card` rule (no card, or a web stub while the RHP analysis exists). |
| `ipo_agent/quiet.py` | `previous_report`, `carry`, `reasons`, `headline`, and the quiet write path; relative words in `category_note` are dropped. |
| `ipo_agent/email_render.py` | Card fields merged under the run's verdict entry; HTML/text rendering; subject; disclaimer; writes `.html` and `.txt` next to the report JSON. |
| `ipo_agent/outcomes.py` | `collect`, `eve_gmp`, `call`, `listing_prices`, `record`, `scorecard`; `main(["--no-fetch"])` must print without constructing a network client. |
| `.claude/hooks/test_guard.py` | Existing test style: `unittest`, temp dirs, real saved files as read-only fixtures, clear per-test names. |
| `data/snapshots/`, `data/outcomes.json`, `reports/`, `analysis/` | Saved, committed files that tests may read. New snapshots and reports are added twice each weekday, so tests must use fixed filenames or self-contained fixtures, never "the latest" where an exact value matters. |

## Approach

Tests are added only; no `ipo_agent/` module changes. Three kinds of tests:

1. **Pure-arithmetic and pure-parser tests** call functions directly with in-memory inputs or small fixtures:
   - `allotment`, `trends`, `nse.parse_*`, `sebi.listing`/`pdf_url`, `investorgain.parse`, `outcomes.scorecard`/`record`, `email_render.render_*`, `quiet.reasons`/`carry`/`headline`, `snapshot.phase`.
2. **Orchestration tests** build a temporary repo (snapshots, analysis cards, reports, outcomes) and patch only the module-level roots and the network boundary:
   - `snapshot.ROOT`, `cards.DIR`, `quiet.ROOT`, `quiet.REPORTS`, `email_render.ROOT`, `outcomes.ROOT`.
   - `snapshot.build` gets a fake client through `patch("ipo_agent.snapshot.Client", ...)`, which routes `get`/`get_text` by URL to the JSON/HTML fixtures. This keeps the real `nse`, `investorgain` and `sebi` parsers in the path while making no socket calls.
   - No test imports or invokes `urllib` against a live host. A shared `NoNetworkCase` patches both `socket.getaddrinfo` and `socket.socket.connect` (see "Test isolation" below), so an accidental real call records the attempt and fails the test instead of hanging, resolving DNS or being swallowed.
3. **Saved-file smoke tests** read fixed committed files, e.g. `reports/2026-10-29-am.json` paired with the snapshot that report was written from, `data/snapshots/2026-10-29T0907.json`, and assert structural content (subject, every IPO name, disclaimer, verdict merge), not volatile numbers. `data/latest.json` is rewritten every run and is never used as a fixture.

**Fixture policy.** `tests/fixtures/` holds:
- `investorgain_gmp.html` — a minimal Next.js page with two `self.__next_f.push` chunks and a `reportTableData` array covering mainboard/SME, U/O/C/LP/LN, a GMP with low/high arrows, and missing values.
- `nse_current.json`, `nse_upcoming.json` — `ipo-current-issue` and `all-upcoming-issues` response shapes with one mainboard issue each and one SME row.
- `nse_detail_<SYMBOL>.json` — `issueInfo.dataList` plus `bidDetails` in the exact keys `nse.py` reads; one with full subscription, one with zero bids and one with an anchor-report link.
- `sebi_listing.html` — a table with normal, corrigendum and addendum rows.
- `sebi_rhp_page.html` — a detail page with the `file=<pdf>` link and a second page variant with the generic URL.

These fixtures are built from the response shapes the parsers already read and from the saved snapshot values; the build must not fetch a live page. Company names, prices, lots and subscription figures are taken from `data/snapshots/2026-10-29T0907.json` wherever the parser branch allows, so a parser test can compare against the values the live parser saved for the same IPO. `tests/fixtures/README.md` records one line per fixture: **hand-built** or **captured**, the date, and what it was modelled on (for hand-built files, the parser functions and snapshot file; for captures, the source URL and capture date). A real capture may replace a hand-built fixture only if the README records the swap.

**Test isolation: roots and defaults to redirect.** Several paths are bound at import, so patching a `ROOT` alone does not move them. `TempRepo` (in `tests/support.py`) documents this list, and every orchestration test follows it:

- **Defaults bound at import:** `outcomes.load(root=ROOT)`, `outcomes.update(root=ROOT, …)`, `trends.load(snap_dir=SNAP_DIR)` and `trends.attach(…, snap_dir=SNAP_DIR)`. Tests pass an explicit `root` or `snap_dir` rather than relying on the default.
- **`snapshot.build` tests:** patch `snapshot.ROOT` **and** `cards.DIR` to the same temp root, with `cards.DIR = root / "analysis"`. `build` computes `cards.path(key).relative_to(ROOT)` (`snapshot.py:166`), which raises `ValueError` if the two disagree. `build` passes `ROOT / "data" / "snapshots"` to `trends.attach` itself, so `snapshot.ROOT` already covers trends on that path.
- **`quiet.main` tests:** patch `quiet.ROOT`, `quiet.REPORTS`, `email_render.ROOT` and `cards.DIR` together. `main` calls `outcomes.update(ROOT, …)`, which builds a real `Client` for any listed IPO not yet in `outcomes.json`; tests either pass `--no-outcomes` or patch `outcomes.Client` (or `outcomes.update`). One test exercises the `outcome_errors` path through `update` with a fake client.
- **`email_render.main` tests:** copy the report and its snapshot into a temp root, patch `email_render.ROOT`, then call `main`; nothing is ever written beside a committed report.
- **No network, and prove it:** `NoNetworkCase` patches **both** `socket.getaddrinfo` and `socket.socket.connect`. `urllib` resolves the host through `socket.create_connection` → `getaddrinfo` *before* it calls `connect`, so blocking `connect` alone misses a DNS lookup: with no network that lookup fails first and raises an ordinary `URLError` that `Client.get` retries and callers swallow, leaving the attempt list empty. Each patched function records the host or address and raises `NoNetworkAttempt`, a `BaseException` subclass no `except Exception` in the code catches, before any live lookup or connection happens. `tearDown` asserts the attempt list is empty, so a swallowed failure fails the test instead of becoming an `errors` entry. Every `build` test also asserts the exact `errors` dict: `{}` on the happy path, and only the expected key in the source-error case.

**Discovery.** Test files are `tests/test_<module>.py`, with `tests/support.py` as a plain helper module (no `tests/__init__.py`). Each test file inserts the repo root and its own directory into `sys.path`, so the exact required command `python3 -m unittest discover -s tests` works from the repo root and `from support import ...` resolves.

**Bugs.** If a test exposes a genuine behaviour bug, the test is committed with `@unittest.expectedFailure` and a one-line reason, is listed under "Bugs found", and is not fixed in this task. If the bug is later fixed, the unexpected success fails the suite and forces the marker's removal.

## Steps

| # | Step | Files | Test that proves it |
| --- | --- | --- | --- |
| 1 | Add test scaffolding: repo-root helper, `TempRepo` builder (docstring lists every root/default to redirect), `NoNetworkCase` that records and blocks **both** `socket.getaddrinfo` and `socket.socket.connect`, fake client that routes URLs to `tests/fixtures/`, the fixture files and `tests/fixtures/README.md` provenance lines. | `tests/support.py`, `tests/fixtures/*`, `tests/fixtures/README.md` | `python3 -m unittest discover -s tests` starts cleanly; self-tests prove `NoNetworkCase` records and raises `NoNetworkAttempt` (not `URLError`) for both an unresolvable host (`*.invalid`) and a literal IP, and that `tearDown` fails when an attempt is left behind. |
| 2 | Cover allotment: minimum lots at both ₹2 L / ₹10 L boundaries, retail cap when the lot cost exceeds it, odds for None/0/≤1/>1, category rows with and without subscription and GMP, rounding, and best category. | `tests/test_allotment.py` | Tests pass for `min_lots`, `odds`, `categories`, `best_category`. |
| 3 | Cover trends: GMP daily last reading, Investorgain time parsing and year rollover, 7-day window, 5-point cap, 8% / 1%-of-price thresholds, peak-based falling, steady/rising, missing history; subscription day bucketing before 10:00 IST, after close, weekends, a weekday exchange holiday counting as a bidding day (the documented behaviour in `trends.py`: "Day N counts weekdays from the open date, so an exchange holiday mid-issue makes it run ahead"), missing categories; `load`/`attach` with a temp snapshot dir. | `tests/test_trends.py` | Tests pass for `gmp_trend`, `subscription_trend`, `trend`, `attach`, `_gmp_time`, `load`. |
| 4 | Cover Investorgain parser: chunk joining, `reportTableData`, board filter, status mapping, price/lot/size/P/E numbers, GMP low/high, missing GMP, and the layout-change `ValueError`. | `tests/test_investorgain.py`, `tests/fixtures/investorgain_gmp.html` | Tests pass for `parse`; a malformed fixture raises the documented error. |
| 5 | Cover NSE parser: category mapping order (bNII before sNII before NII), rows with no offered quantity skipped, duplicate categories ignored, `_clean`/`_f`, `parse_detail` fields and price range, and cookie priming in `NSE.api` using a fake client that records calls. | `tests/test_nse.py`, `tests/fixtures/nse_*.json` | Tests pass for `parse_subscription`, `parse_detail`, `NSE.current`, `NSE.upcoming`, `NSE.detail`. |
| 6 | Cover SEBI parser: listing rows, date/title extraction, title split on `" - "` and `" – "`, the `"class="points">…` tail stripped (`sebi.py:23-24`), corrigendum and addendum skipped, rows without filing links ignored; `pdf_url` for both link shapes and the no-match case. | `tests/test_sebi.py`, `tests/fixtures/sebi_*.html` | Tests pass for `listing`, `pdf_url`. |
| 7 | Cover snapshot: `norm`/`slug`/`same_company`/`nse_date`, `phase` for every phase and boundary day, and `build` against the fake router — IG + NSE merge, NSE-only row, old listed row dropped, SME dropped, NSE values overriding IG, zero-bid subscription dropped, SEBI RHP fallback, trends attached, and a source error recorded while the other source still builds. Every `build` test patches `snapshot.ROOT` and `cards.DIR` to the same temp root and asserts the exact `errors` dict (`{}` happy path, only the expected key in the source-error case). Then `needs_analysis`, `needs_card`, `needs_anchor_update` against a temp `analysis/`. | `tests/test_snapshot.py` | Tests pass for `build`, `phase`, and the three `needs_*` flags; `build` makes no socket call, and `tearDown` sees an empty attempt list. |
| 8 | Cover cards: missing card, web stub with and without an analysis file, RHP card, and `path`. | `tests/test_cards.py` | Tests pass for `load`, `needs_card`, `path`. |
| 9 | Cover quiet: previous-report selection before the same stem, `carry` field filtering, relative-word dropping and newer-card override, every `reasons` branch (source/outcomes errors, no previous report, open/closing, needs flags, phase change, listing-day exemption, falling GMP, GMP ≤ 0 vs avoid), `headline`, `outcome_note`, and `main` quiet/non-quiet/`--check`/already-written paths writing only inside a temp root. `main` tests patch `quiet.ROOT`, `quiet.REPORTS`, `email_render.ROOT` and `cards.DIR` together, and either pass `--no-outcomes` or patch `outcomes.Client`/`outcomes.update` so no real `Client` is built; one test drives `outcome_errors` through `update` with a fake client. | `tests/test_quiet.py` | Tests pass for `previous_report`, `carry`, `reasons`, `headline`, `main`. |
| 10 | Cover email rendering: `merged` precedence (report over card), text and HTML for a synthetic snapshot/report (escaping, verdict/phase labels, odds, disclaimer), subject line, and `main` writing `.html`/`.txt` after copying the report and `data/snapshots/2026-10-29T0907.json` into a temp root and patching `email_render.ROOT`. Add a read-only smoke test that calls `render_html`, `render_text` and `subject` **directly** over `reports/2026-10-29-am.json` + `data/snapshots/2026-10-29T0907.json` — it never calls `main`, so no committed `.html`/`.txt` is overwritten. | `tests/test_email_render.py` | Tests pass for `merged`, `render_text`, `render_html`, `subject`, `main`. |
| 11 | Cover outcomes: `collect` from temp snapshots, `eve_gmp`, `call` cutoff/card merge, `listing_prices` row pick, `final_subscription` NSE-then-snapshot fallback (its `source` contains `dt.date.today()`, so patch the date or assert the prefix), `record` maths, `scorecard` empty/small-sample/correlation output, `save` ordering, `update` with `listing_prices` stubbed, `set_manual` with network stubbed, and `main(["--no-fetch"])` run with `outcomes.ROOT` patched to a temp root holding a small `data/outcomes.json`, asserting the exact scorecard and that no `Client` is built. It never reads the real, ever-growing `data/outcomes.json`. | `tests/test_outcomes.py` | Tests pass for the module functions and `main --no-fetch`; a guard patch proves no client is built on that path. |
| 12 | Run the exact command, record output, and update the status labels. Add any discovered behaviour mismatch to "Bugs found" with an `expectedFailure` test and record the assertion message it fails with today. | `docs/tech.md`, `docs/ai.md` | `python3 -m unittest discover -s tests` passes; `git diff` shows only `tests/`, the two docs, and this plan; `git status --short data/ analysis/ reports/` is empty after the suite runs. |

## Data and AI

None. No tables, columns, settings or AI calls. Tests must never call an AI API or a live site.

## Doc updates

- `docs/tech.md`: "Agent tests" (at a glance) and `tests/` (repository layout) move from **Decided** to **Running**, with the command `python3 -m unittest discover -s tests` as evidence.
- `docs/ai.md`: split the `tests/ + CI` row so `tests/` is **Running** and CI stays **Decided** (CI arrives in task 002).
- `docs/tasks/ROADMAP.md` after merge (human or Claude, on `main`): mark 001 **Done**; mark 002 and 004 **Ready**; leave 005 **Blocked** until 002 is Done. No ADR is needed.

## Decisions needed

None. The agent test runner (`unittest`) and its command are already Decided/recorded in `tech.md` and `AGENTS.md`.

## Bugs found

To be filled during the build. Each entry gets: module, current behaviour, documented/intended behaviour, the `expectedFailure` test name, the assertion message the test fails with today, and a one-line suggestion for the human. No fix is made here. A behaviour is called a bug only when a doc or code comment states the intended behaviour; where intent is not written down, the test pins the current behaviour and the question goes to the human. This keeps `expectedFailure` from passing on an unrelated error (broken fixture, `KeyError`, a `NoNetworkAttempt`) while pretending to hide a bug; when the section is filled, each recorded message must be an `AssertionError` on the point being tested.

## Risks and rollback

- **Tests writing into the system of record.** Any test that writes patches every root the code reads at import or uses on that path to a `tempfile.TemporaryDirectory` (see "Test isolation: roots and defaults to redirect"). The `email_render` smoke test never calls `main`, so no committed `.html`/`.txt` is touched. Verification checks that `git status --short data/ analysis/ reports/` is empty after the suite runs.
- **Accidental live network.** `NoNetworkCase` patches `socket.getaddrinfo` as well as `socket.socket.connect` to record the attempt and raise a `BaseException` subclass no caller catches, so a DNS lookup cannot happen before the guard fires; `tearDown` asserts the list is empty, and `build` tests assert the exact `errors` dict. Orchestration tests also inject a URL-routing fake at `snapshot.Client`/`outcomes.Client`. No real URL is reachable from the suite, and a swallowed failure cannot hide.
- **Drift in saved files.** The routine adds snapshots and reports twice each weekday. Tests use self-contained fixtures for arithmetic and parsers, or fixed committed filenames (`reports/2026-10-29-am.json` paired with `data/snapshots/2026-10-29T0907.json`) with structural assertions. No test asserts on the contents of `data/latest.json` or the real `data/outcomes.json`.
- **Fixtures not matching a real page.** The fixtures cover the parser branches as written; they are not a substitute for live captures. `tests/fixtures/README.md` labels each one hand-built or captured and names what it was modelled on, so a later reader can tell which fixtures are evidence about the real sites. If a parser branch cannot be represented honestly, the test is omitted and noted rather than asserting invented behaviour.
- **A revealed bug blocks "all green".** Use `expectedFailure` plus the "Bugs found" entry, as described in Approach.
- **Rollback.** The change adds only tests, fixtures and two doc labels. Reverting the task commit restores the previous state; no data, schema, secret or agent behaviour is affected.

## Revisions

| Round | What changed | In answer to |
| --- | --- | --- |
| 1 | Replaced the swallowed `Client.get` guard with a `socket.socket.connect` guard that records attempts and raises an uncatchable `BaseException`; `tearDown` asserts no attempts and every `build` test asserts the exact `errors` dict. Paired the saved report with `data/snapshots/2026-10-29T0907.json` and banned `data/latest.json` as a fixture. Made the email smoke test call `render_html`/`render_text`/`subject` directly and moved `main` to a temp root. Added "Test isolation: roots and defaults to redirect" to the Approach and the `TempRepo` docstring, covering import-time defaults, `snapshot.build`/`cards.DIR`, `quiet.main`, and `outcomes.update`'s real `Client`. Changed step 3 to pin the documented weekday-holiday behaviour, step 6 to the actual SEBI title handling, and step 11 to a temp `outcomes.json` and a date-safe `final_subscription` assertion. Added `tests/fixtures/README.md` provenance lines and removed the unrecorded capture-swap sentence. Recorded the expected-failure assertion message and intent rule in "Bugs found", and added the post-run `git status` check to step 12. | 1, 2, 3, 4, 5, 6, and Notes |
| 2 | Extended `NoNetworkCase` to patch `socket.getaddrinfo` as well as `socket.socket.connect`, because `urllib` resolves DNS before `connect` and a no-network lookup raises a swallowable `URLError`; each patch records the host/address and raises `NoNetworkAttempt` before any live call. Step 1 now self-tests an unresolvable `*.invalid` host and a literal IP, both of which must record and raise `NoNetworkAttempt`, not `URLError`. Noted that a `NoNetworkAttempt` is not a valid `expectedFailure` reason. | Round 2 item 1 and Notes |

## Changes during build

## Verification

To be filled during the build with the exact command output.
