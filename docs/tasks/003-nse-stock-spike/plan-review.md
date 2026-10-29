# Plan review: 003-nse-stock-spike

## Round 1 (2026-10-29)

**Verdict:** Changes requested

**Read:** plan.md, AGENTS.md, docs/tasks/README.md (reviewer guide), ROADMAP.md § 003, docs/data-sources.md, ADR-0018, docs/arch.md § 4.2 and § 9, docs/tech.md, docs/db.md (stock tables), ipo_agent/net.py, ipo_agent/nse.py, opencode.json, and task 001's plan.md (it shares `tests/`).

The plan is solid on goal, scope and rules: stdlib only, no AI, no `data/` writes, no D09 decision, fixtures under `tests/`, `--dry-run` for network-free tests, and an honest "stop, don't invent" path if NSE blocks both environments. Choosing the `push` trigger is allowed by the roadmap and the plan says why. The items below are about making the call budget, the units and the G1 evidence exact before the build.

### Changes requested

1. **Fix the call list and enforce a hard cap in code.** The plan says "one call per endpoint", but some calls are conditional or open-ended: the quote may or may not need a second `section=trade_info` call; the pledge probe may make a market-wide call "to choose a company", then a per-symbol call; and any primary may fall back to an alternate. Together these make the number of requests per run unknown, which goes against "be gentle" ([data-sources.md § Rules for every source](../../data-sources.md#rules-for-every-source)) and the roadmap's "one call per endpoint, no loops".
   - List in the plan every request the probe can make, including the two priming GETs, the `trade_info` call (decide now: always made, or never made), and each fallback. Give the total, which should be about 12 at most.
   - Have `ENDPOINTS` define exactly that list, and have the probe refuse to make more than `MAX_CALLS` requests per run. Test the cap with the `Client.get` stub.
   - Drop the adaptive "market-wide pledge call, then choose a symbol" step. Pick the pledge symbol now and write it in the plan. If that symbol returns no rows, record an empty result. If you want the market-wide variant, make it one fixed call in the list (see note 1); don't pick a second call based on the result of the first.

2. **Don't assume units before seeing the response.** The table says `results-comparision` amounts "are ₹ lakh" as a fact. Under rule 1, a unit is part of the number, so it has to be confirmed rather than assumed. Change this to "record the unit only if the response or NSE's results page states it; otherwise record *unit not stated* for 014 to check against one filing". Treat the quote's market cap and the results filings the same way.

3. **Say how the runner result gets onto the branch before code review.** With the `push` trigger, the GitHub run happens before merge. The plan still says the human adds the run URL "after merge" and describes no step that does it. Settle the order:
   1. DeepSeek builds and commits.
   2. The human pushes the branch, which runs the workflow.
   3. The human gives DeepSeek the run URL and its `G1 candidate:` line.
   4. DeepSeek records both in the plan's "Verification" and in `data-sources.md` (as "observed on run <URL>"), then sets `code-review`.

   Ticking G1 and editing `arch.md § 9`'s runner row stay with the human on `main`, as you planned. Also say which source the committed fixtures come from: the local run or the runner artifact. The fixture README should record that per file, so 014 knows whether a shape was seen from a GitHub IP.

4. **Cap fixture size and say how it's trimmed.** For a large company like RELIANCE, `corporate-announcements`, `corporate-share-holdings-master` and `corporates-financial-results` can return hundreds of rows, and `EQUITY_L.csv` has about 2,000 rows. Choose a rule, for example: keep the first N rows of each top-level list (N = 20) and the full CSV, and record the original row count and byte size in `tests/fixtures/.../README.md`. Apply the trimming in the probe's `--save` code, never by hand, so the fixture is still a faithful sample. Add a test that checks a saved fixture never has more than N rows.

5. **Keep review pushes from calling NSE again.** As written, the workflow runs on every push to `task/003-*`, including the plan-review and code-review commits that only touch `docs/tasks/`. Add a `paths:` filter to the push trigger (the probe module, the workflow file and the fixtures README are enough). A deliberate re-check can then use "Re-run jobs" in the Actions tab. Also pin the actions to major versions (`actions/checkout@v4`, `actions/upload-artifact@v4`, and `actions/setup-python@v5` if you use it). Then either name the system Python on `ubuntu-latest` or use `setup-python`, but not "Python 3.12" without saying where it comes from.

6. **Make the `arch.md § 9` edit depend on the result.** Remove the "Confirmed NSE endpoints" row only if every endpoint in the task was confirmed. If some failed or are partial, keep the row and narrow it to what's still unconfirmed. The same applies to the summary-row wording in `data-sources.md`.

### Notes

1. **Market-wide variants would help 018.** Endpoints such as `corporate-announcements?index=equities` with a date range, and `corporate-pledgedata?index=equities`, could let the scheduled worker make one call per run instead of one per watched stock. That matters for "be gentle" and for Actions minutes once the watchlist grows. If you can fit one fixed call for each within the cap in item 1, record whether they work. If not, list it as an open question for 014 in "Doc updates".
2. **Follow task 001's test layout.** Task 001 uses `tests/test_<module>.py` with no `tests/__init__.py`, puts the repo root on `sys.path` in each test file, and keeps IPO NSE fixtures as `tests/fixtures/nse_*.json`. Use the same conventions. Consider naming the directory `tests/fixtures/nse_stock/` so it isn't confused with the IPO NSE fixtures. Don't add a `tests/__init__.py` or a shared helper that 001 also creates.
3. **`tech.md` is edited by both 001 and 003.** Keep 003's edits to its own rows (entry points, `.github/workflows/`, Local setup) so the second merge rebases cleanly.
4. **`ipo_agent/` placement is fine for a probe.** It doesn't settle D09. Keep the module docstring explicit that it is a one-off development probe that 014 may move or delete.

## Round 2 (2026-10-29)

**Verdict:** Approved

**Read:** plan.md (revision 1 and its Revisions row), the round 1 items above, and the same docs as round 1.

Every round 1 item is fixed:

| Round 1 item | How the revision answers it |
| --- | --- |
| 1. Call budget | Exactly 12 requests, listed in order. `trade_info` is never called, the pledge symbol is fixed at `ADANIENT`, and there are no fallbacks. `MAX_CALLS = len(ENDPOINTS)` and a `CallBudget` guard enforce the limit, with a 12-vs-13 test |
| 2. Units | "Unit not stated" unless the response itself states one. Nothing is converted in the probe or in a fixture. A test asserts no ₹ lakh or crore |
| 3. Runner result | A fixed order: build, human pushes, human hands over the run URL and `G1 candidate:` line, DeepSeek records both, then `code-review`. `captured_by` is recorded per fixture |
| 4. Fixture size | A 20-row cap applied in the `--save` code, with original counts and bytes in `manifest.json`, and a cap test |
| 5. Workflow | `paths:` covers only the probe and the workflow. Actions are pinned to major versions, with `setup-python@v5` on 3.12 |
| 6. Conditional docs | The `arch.md § 9` row and the `data-sources.md` summary row change only as far as the endpoints were confirmed |

The notes are taken up too: market-wide announcement and pledge calls are fixed, optional probes inside the budget; `tests/fixtures/nse_stock/` with 001's test layout; `tech.md` edits limited to 003's rows; and the one-off-probe docstring. Marking the two primes and the two market-wide probes `required: false`, so they can't turn a G1 PASS into a FAIL, is a sound addition.

### Notes

Build-time points that don't need another plan round:

1. **Make the date-range URL testable.** `announcements_market` builds its URL from today's date, so "the registry has exactly the 12 documented URLs" isn't deterministic. Let the URL builders take the run date as a parameter (with `main` passing today's date), and test with a fixed date.
2. **The `paths:` filter and an earlier push.** If the local run is blocked and the human pushes early for the artifact (build order step 3), a later push that doesn't touch the probe or the workflow won't start another run. In that case, the early run is the G1 evidence for step 6. Record its URL, and use "Re-run jobs" only if a fresh result is really needed.
3. **Build `README.md` from `manifest.json` in code,** as the plan says. Field gaps and unit notes can be added to it in code from the summary, so no part of the fixture provenance is written by hand.
