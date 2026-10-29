# Code review: 001-agent-tests

## Round 1 (2026-10-29)

**Verdict:** Changes requested

**Diff:** `git diff main...task/001-agent-tests` at `7528609`: 26 files, all under `tests/`, plus `docs/tech.md`, `docs/ai.md` and the task folder. No change to `ipo_agent/`, `data/`, `analysis/` or `reports/`.

**Tests:**

```text
$ python3 -m unittest discover -s tests
.......................................................................................................................................................................
----------------------------------------------------------------------
Ran 167 tests in 0.215s

OK

$ unshare -rn python3 -m unittest discover -s tests    # no network namespace at all
Ran 167 tests in 0.217s

OK

$ git status --short --untracked-files=all data analysis reports
(no output)
```

These checks went beyond the suite:
- **A frozen clock.** I re-ran `BuildTests` with `snapshot.dt.datetime.now` frozen at a later date (finding 1).
- **The saved outcomes.** I compared the NSE price types in `data/outcomes.json` with the outcomes test fixture (finding 3).

### Findings

| # | Severity | Where | Problem (what breaks, and when) | Suggested fix |
| --- | --- | --- | --- | --- |
| 1 | Major | `tests/test_snapshot.py:129-136` | **`test_trends_are_attached` stops working in late October 2027.** `snapshot.build` takes `generated_at` from the real clock (`snapshot.py:75`). `trends._gmp_time` reads the year of "27-Oct" / "28-Oct" from that clock. From about 27 Oct 2027, the temp snapshot's reading maps to 2026 and the new one to 2027. The 7-day window then drops the old point, `trend["gmp"]` is `None`, and the test errors with `TypeError`. I re-ran `BuildTests` with `now` frozen: it passes at 2026-10-29 and 2027-03-01, and errors at 2027-11-01. CI from task 002 would go red for every later task on that date. | Freeze the clock in `BuildTests`: patch `snapshot.dt` with a stand-in whose `datetime.now` returns `2026-10-29T09:07+05:30`. That also makes `generated_at` assertable. No other test reads the real clock: `final_subscription` is handled by its prefix assertion, and `record`'s `recorded_at` isn't asserted. |
| 2 | Major | `tests/test_snapshot.py:101-110`, `tests/fixtures/nse_detail_*.json` | **Step 7's "NSE values overriding IG" has no test.** For every IPO in both sources, the Investorgain and NSE fixtures carry the same price and lot: SFC is 330 / 45 in both, Acme is 250 / 60 in both. `test_investorgain_and_nse_values_are_merged` therefore passes whichever source `build` takes `price_high` and `lot` from (`snapshot.py:144-145`). If the precedence were reversed, a stale Investorgain price band would reach the odds table and nothing would fail. | Give one IPO different values in the two sources, e.g. Investorgain Acme at ₹245 / 50 shares and NSE at ₹250 / 60. Assert that `price_high`, `lot` and the `categories` minimum amount follow NSE. Record the deliberate mismatch in `tests/fixtures/README.md`. |
| 3 | Minor | `tests/test_outcomes.py:130-141`; plan "Bugs found", 2nd bullet | **The listing-price fixture invents string prices.** `ListingPricesTests.row` sends `CH_OPENING_PRICE` and the other price fields as strings, and the test asserts `result["listing"] == "110"`. The saved data shows NSE returns numbers: every `price_source: "nse"` row in `data/outcomes.json` has numeric prices (e.g. `hd-fire-protect`: issue 271, listing 335, close 306.75). With strings, `record` → `_pct("110", 90)` would raise `TypeError`, so the fixture pins a shape that would crash the code it feeds. The "Bugs found" note says no saved evidence exists either way, but the evidence exists and shows numbers. | Use numbers in the fixture (`"CH_OPENING_PRICE": 110` and so on) and assert `110`. Rewrite the plan's second "Bugs found" bullet to cite `data/outcomes.json`, or drop it. |
| 4 | Minor | `tests/test_support.py:12-38` | **The guard self-tests call `socket.getaddrinfo` directly.** The approved step 1 asked for proof that the guard raises `NoNetworkAttempt` and not `URLError`. A direct `getaddrinfo` call can never produce a `URLError`, so these tests don't show that `urllib`'s path (`create_connection` → module-level `getaddrinfo`) goes through the patch. I checked it by hand in round 3, and it does, but nothing in the suite would catch a later change that breaks it, such as patching `ipo_agent.net.socket` instead. | Add one test that calls `ipo_agent.net.Client(retries=0).get("https://no-such-host.invalid/")`. It should assert that `NoNetworkAttempt` is raised and `("dns", "no-such-host.invalid")` is recorded, then clear the list. |
| 5 | Minor | `tests/support.py:7-17` | **The `TempRepo` docstring gives wrong advice for import-time defaults.** It says to patch `outcomes.ROOT` and `trends.SNAP_DIR` for the "`load`/`update`/`attach` defaults". Default arguments are evaluated when the function is defined, so patching the module global doesn't move `outcomes.load()`, `outcomes.update()`, `trends.load()` or `trends.attach()`. A later test that follows the docstring and calls `outcomes.load()` would read the real `data/outcomes.json`. The tests themselves do the right thing and pass `root` / `snap_dir` explicitly. | Reword the bullet to "pass `root` / `snap_dir` explicitly to `outcomes.load`/`update` and `trends.load`/`attach`; patching `ROOT`/`SNAP_DIR` does not move a default argument". Keep the `outcomes.ROOT` bullet for `outcomes.main`, which reads the global at call time. |

### Plan and docs

- **Built as approved.** All 12 steps are there, and every test case inherits `NoNetworkCase`. The guard blocks DNS and connect, `tearDown` asserts no attempts, and every `build` test asserts the exact `errors` dict. Orchestration tests patch the roots listed in the plan. The email smoke test pairs `reports/2026-10-29-am.json` with `data/snapshots/2026-10-29T0907.json` and calls the render functions directly. `outcomes.main --no-fetch` runs on a temp `outcomes.json` and asserts that no `Client` is built.
- **Changes during build are justified.** The plan records all four:
  - the extra `tests/test_support.py`;
  - two split-out fixtures;
  - the inline malformed Investorgain page;
  - `quiet.outcomes.update` patched for the `outcome_errors` path.
- **Docs.**
  - `docs/tech.md` moves "Agent tests" and `tests/` to **Running** and gives the command.
  - `docs/ai.md` splits the old `tests/ + CI` row: agent tests are **Running**, CI stays **Decided**.

  Both match the plan's Doc updates.
- **Fixture provenance.** `tests/fixtures/README.md` labels every fixture hand-built, dated 2026-10-29, and modelled on the 0907 snapshot.
- **Rules.** No `ipo_agent/` change, no new dependency, no live call. All task commits carry the `AI-Agent: DeepSeek (opencode)` trailer.
- **Notes, not findings.**
  - `test_weekday_exchange_holiday_still_counts_as_a_bidding_day` uses Mon 26 → Thu 29 Oct, which is the same weekday count as the test above it. It pins the documented behaviour, but naming a specific weekday as "the holiday" in the comment would make the intent clearer.
  - `test_investor_sub_rows_without_offered_quantity_are_skipped` asserts that `"foreign institutional investors"` is not a key. It never could be, so that line is decoration. The `set(sub)` assertion below it does the real work.

## Responses (DeepSeek)

| # | Response | Commit |
| --- | --- | --- |
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |
