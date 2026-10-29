# Plan review: 001-agent-tests

## Round 1 (2026-10-29)

**Verdict:** Changes requested

**Read:** plan.md, AGENTS.md, docs/tasks/README.md § Reviewer guide, ROADMAP.md (001, 002, 004, 005), docs/arch.md § 4.1, ADR-0001, ADR-0002, docs/tech.md, docs/ai.md, docs/data-sources.md, `.claude/hooks/test_guard.py`, and every `ipo_agent/` module the plan covers (`allotment`, `trends`, `investorgain`, `nse`, `sebi`, `snapshot`, `cards`, `quiet`, `email_render`, `outcomes`, `net`).

The scope, the module list, the three kinds of test and the doc updates are right. The roadmap changes are right too: 002 and 004 depend only on 001, and 005 stays Blocked on 002. Test discovery with no `tests/__init__.py` works from the repo root. The items below are about tests that could pass while proving nothing, or that could write into `reports/`.

### Changes requested

1. **Make the no-network guard fail loudly.** The plan has `NoNetworkCase` make `net.Client.get` raise, but every caller swallows that error:
   - `NSE._prime` catches every exception (`nse.py:21-29`).
   - `snapshot.build` catches `Exception` around each source and records it in `errors` (`snapshot.py:80-90`, `112-115`, `124-138`).
   - `outcomes.update` catches it around `listing_prices` (`outcomes.py:176-180`), and `final_subscription` does the same (`outcomes.py:114-119`).

   A stray real `Client` would turn into an `errors` entry, and the test could still pass. Change step 1 so the guard records every attempted call and raises something the code doesn't catch: a `BaseException` subclass, or a patch on `socket.socket.connect`. `tearDown` then asserts the call list is empty. Also make every `build` test assert the exact `errors` dict: `{}` for the happy path, and only the expected key for the source-error case. Then a swallowed failure fails the test. *Why:* the task's Done-when is "passes with no network access", so the guard has to prove that, not just hope for it.

2. **Pair the saved report with its own snapshot, not `data/latest.json`.** Approach § 3 and step 10 pair `reports/2026-10-29-am.json` with `data/latest.json`. Every run rewrites `latest.json`; its keys match the AM report today but won't after the PM run. Use `data/snapshots/2026-10-29T0907.json`, the snapshot that report was written from, which Risks already names. Also remove "`data/latest.json`" from Approach § 3. *Why:* the plan's own Risks rule ("fixed committed filenames … never 'the latest'").

3. **The smoke test must not write next to the real report.** `email_render.main` writes `.html` and `.txt` beside the report path it is given (`email_render.py:440-443`), and it always reads `ROOT/data/latest.json`. Called on `reports/2026-10-29-am.json`, it would overwrite the committed `reports/2026-10-29-am.{html,txt}`, a path AGENTS.md says no agent edits by hand. Say in step 10 that the read-only smoke test calls `render_html`, `render_text` and `subject` directly. Tests of `main` should copy the report and snapshot into a temp root and patch `email_render.ROOT`.

4. **Spell out every root and default each orchestration test must redirect.** Some paths are fixed at import, so patching `ROOT` alone doesn't move them:
   - **Defaults bound at import:** `outcomes.load(root=ROOT)`, `outcomes.update(root=ROOT, …)`, `trends.load(snap_dir=SNAP_DIR)` and `trends.attach(…, snap_dir=SNAP_DIR)`. Tests call these with an explicit `root` or `snap_dir`.
   - **`quiet.main` tests:** patch `quiet.ROOT`, `quiet.REPORTS`, `email_render.ROOT` and `cards.DIR` together. `main` also calls `outcomes.update(ROOT, …)`, which builds a real `Client` for any listed IPO not yet in `outcomes.json`, so either pass `--no-outcomes` or patch `outcomes.Client` (or `outcomes.update`). Say which in step 9, and give one test that covers the `outcome_errors` path through `update`.
   - **`snapshot.build` tests:** patch `snapshot.ROOT` and `cards.DIR` to the same temp root (`cards.DIR = root / "analysis"`). `build` computes `cards.path(key).relative_to(ROOT)` (`snapshot.py:166`), which raises `ValueError` if the two disagree. `build` passes `ROOT / "data" / "snapshots"` to `trends.attach` itself, so `snapshot.ROOT` already covers trends there.

   Put this list in `tests/support.py`'s `TempRepo` docstring or the Approach, so the build doesn't find out one test at a time. *Why:* Risk "Tests writing into the system of record": one missed patch writes into `reports/` or `data/`.

5. **Test what the code does, not what the plan assumes.**
   - **Step 3, "holiday-shifted day numbers".** `_bidding_day` counts weekdays only (`trends.py:97-98`), and nothing in `ipo_agent/` knows about exchange holidays. Pin the current behaviour: a holiday on a weekday counts as a bidding day. If the plan's author thinks that's wrong, it goes under "Bugs found" with an `expectedFailure` test, as the plan already says. Don't write a test that assumes a holiday calendar.
   - **Step 6, "dot-leader titles".** `sebi.listing` has no dot-leader handling. It splits titles on " - " / " – " and strips a `"class="points">…` tail (`sebi.py:23-24`). Name the cases the code has.
   - **Step 11, `main(["--no-fetch"])`.** Run it against a temp root holding a small `data/outcomes.json`, with `outcomes.ROOT` patched, and assert the exact scorecard. Don't assert against the real `data/outcomes.json`, which grows with every listing.
   - **Step 11, `final_subscription`.** Its `source` string contains `dt.date.today()` (`outcomes.py:117`). Assert its prefix, or patch the date, so the test doesn't depend on the day it runs.

6. **Record where each fixture came from.** The roadmap's Watch-for says "saved HTML and JSON", but the repo has no raw Investorgain, NSE or SEBI responses, so the plan's fixtures are hand-built from the parsers' own regexes. That's acceptable, but a test then mostly confirms the parser against a page shaped by the same parser. Add `tests/fixtures/README.md` with one line per fixture: hand-built or captured, the date, and what it was modelled on. Where possible, take company names, prices, lots and subscription figures from `data/snapshots/2026-10-29T0907.json`. A parser test can then check its output against the values the live parser saved for the same IPO. Drop the sentence that a real capture "may replace a fixture byte-for-byte" unless the README records the swap. *Why:* the next reader must be able to tell which fixtures are evidence about the real sites.

### Open choices for the human

- **Real captures for the parser fixtures (optional, not blocking).** DeepSeek can't fetch the live sites, and the plan says the build must not. If you want the Investorgain, NSE and SEBI parser tests to rest on real pages, you or Claude could save one response from each source into `tests/fixtures/` on `main`, trimmed to a few rows, before the build starts. Otherwise the hand-built fixtures stand, labelled as in item 6. The plan can be approved either way.

### Notes

- **`expectedFailure` hides more than the bug.** It also passes if the test errors for an unrelated reason, such as a broken fixture or a `KeyError`. For each one, record in "Bugs found" the assertion message it fails with today. Mark something as a bug only when a doc or code comment states the intended behaviour. Where intent isn't written down, pin the current behaviour and list the question for the human.
- **The `sys.path` insertion is harmless but redundant** when run from the repo root: `-m` puts the current directory on `sys.path`, and `discover -s tests` adds `tests/`. Keep it if it lets a single file run on its own (`python3 tests/test_x.py`), as `.claude/hooks/test_guard.py` does.
- **Step 12's `git diff` check** should also confirm that `git status --short data/ analysis/ reports/` is empty after the suite runs, as Risks says.

## Round 2 (2026-10-29)

**Verdict:** Changes requested

**Read:** plan.md (revision 1, commit `07095f3`), the round-1 items above, `ipo_agent/trends.py:12-13` (the weekday-holiday docstring step 3 now quotes), `ipo_agent/net.py`.

Every round-1 item is addressed:
- **Item 1:** the guard records every attempt, `tearDown` asserts the list is empty, and every `build` test asserts the exact `errors` dict.
- **Items 2 and 3:** the saved report is paired with `2026-10-29T0907.json`, and the email smoke test never calls `main`.
- **Item 4:** "Test isolation" lists every root and default that has to be redirected.
- **Item 5:** step 3 pins the behaviour `trends.py` documents, step 6 names the real SEBI cases, and step 11 uses a temp `outcomes.json` and a date-safe assertion.
- **Item 6:** `tests/fixtures/README.md` records provenance.

One gap is left. It is in the guard design I suggested in round 1.

### Changes requested

1. **The guard must also block DNS: patch `socket.getaddrinfo` as well as `socket.socket.connect`.** `urllib` resolves the host name through `socket.create_connection` → `getaddrinfo` before it calls `connect`. With no network, which is the task's Done-when condition, the lookup fails first. It raises an ordinary `URLError`, which `Client.get` retries (with `time.sleep`) and then re-raises, and `build`, `NSE._prime` and `outcomes.update` swallow it. `connect` is never reached, so the attempt list stays empty and the guard passes. I checked this with `Client(retries=0).get("https://no-such-host.invalid/")` under a patched `socket.socket.connect` that raises a `BaseException` subclass. The result was `URLError: Name or service not known` and **0 recorded attempts**. On a machine with network, the lookup itself is a live call that happens before `connect` is blocked.

   Change "Test isolation" and step 1 so `NoNetworkCase` patches both `socket.getaddrinfo` and `socket.socket.connect`, and has each record the host or address and raise `NoNetworkAttempt`. Step 1's self-test then has two cases: an unresolvable host (`*.invalid`) and a literal IP. Both must be recorded and must raise `NoNetworkAttempt`, not `URLError`. *Why:* the Done-when says "passes with no network access", and in that environment a guard that misses DNS sees nothing.

### Notes

- That is the only change. With it made, the plan is ready to approve.
- An `expectedFailure` test that trips `NoNetworkAttempt` would count as an expected failure. The "Bugs found" rule (record the assertion message it fails with today) already covers this. When the build fills that section, check that each message is an `AssertionError` on the point being tested.
