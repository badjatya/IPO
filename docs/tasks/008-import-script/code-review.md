# Code review: 008-import-script

## Round 1 (2026-10-30)

**Verdict:** Changes requested

**Diff:** `git diff main...task/008-import-script` at e4424f6

**Tests:**

The offline checks pass locally, in the worktree:

```text
$ npm test                       # web/
 Test Files  6 passed (6)
      Tests  55 passed (55)
$ npm run typecheck              # clean
$ npm run lint                   # clean
$ npx drizzle-kit generate
No schema changes, nothing to migrate 😴
$ python3 -m unittest discover -s tests
Ran 330 tests in 0.602s
OK
$ python3 -m unittest discover -s .claude/hooks
Ran 19 tests in 0.211s
OK
```

The database suite had never run: the plan's Verification says it couldn't run without the Neon secrets. Claude pushed `task/008-import-script` so CI's `db` job would run it ([run 40953566444](https://github.com/badjatya/IPO/actions/runs/40953566444)). `web` and `tests` passed; **`db` failed, with 7 of the 8 import tests failing**:

```text
 ✓ tests/db/schema-shape.test.ts (7 tests)
 ✓ tests/db/schema-rules.test.ts (8 tests)
 × rebuilds twice to identical counts that match the repo's own files
 × leaves app tables alone through a rebuild
 × spot-checks a snapshot, zetwerk's card, analysis and latest verdict, an override and an outcome
 × (c) a bad commit leaves no rows and fails the run; a fixed commit imports and flips its row to ok
 × (d) a deleted report file's rows go with it; ipos facts survive
 × (e) re-running an already-imported range changes nothing
 × (g) an unchanged ipo_analyses row is not rewritten
 ✓ import: CLI > exits non-zero with a clear message when DATABASE_URL is unset

TypeError: value.toISOString is not a function
 ❯ PgTimestamp.mapToDriverValue node_modules/src/pg-core/columns/timestamp.ts:68:16
AssertionError: expected [] to have a length of 1 but got +0
AssertionError: expected false to be true   (tests/db/import.test.ts:266, :346 — first.ok)

 Test Files  1 failed | 2 passed (3)
      Tests  7 failed | 16 passed (23)
```

### Findings

| # | Severity | Where | Problem (what breaks, and when) | Suggested fix |
| --- | --- | --- | --- | --- |
| 1 | Blocker | `web/lib/import/snapshot.ts:61,77,106,129`, `card.ts:42`, `report.ts:52`, `outcomes.ts:38`, `types.ts:10-28` | Every `timestamptz` column (`ipos.updated_at`, `ipo_snapshots.taken_at`, `ipo_subscriptions.taken_at`, `ai_written_at`, `ipo_outcomes.gmp_eve_snapshot`) gets an ISO **string**. Drizzle's `timestamp()` columns are in `date` mode, and `PgTimestamp.mapToDriverValue` calls `value.toISOString()`, so the first snapshot insert throws `TypeError: value.toISOString is not a function`. Nothing imports: rebuild and per-commit mode both fail (CI above). The comment at `types.ts:11-12` ("Postgres accepts both") is wrong for Drizzle's mapping, and `Loose<T>` plus the casts back to the insert type kept `tsc` from catching it. | Convert at the parser boundary: `new Date(value)`, with a check that throws on an invalid date so it lands in `imports.error`. The alternative is `mode: "string"` on those columns, which changes no SQL. Either way, fix the comment. See also #4. |
| 2 | Blocker | `web/lib/import/apply.ts:99-100` | `tx.insert(...).values([])` throws `values() must be called with at least one value`. **10 of HEAD's 35 snapshots have no subscription data at all** (`2026-10-12T1634` … `2026-10-13T0907`, and `2026-10-26T0907`), so `rows.subscriptions` is empty and the rebuild fails every time. A snapshot with an empty `ipos` array does the same on line 99. Reproduced with `parseSnapshotDocument` on `data/snapshots/2026-10-26T0907.json`: `subscriptions rows: 0`, and `.values(rows.subscriptions)` throws. Finding #1 currently hides this one. | Skip the insert when the array is empty, for both `snapshots` and `subscriptions`. Add a parser or db test with one of the real no-subscription snapshots. |
| 3 | Blocker | `web/lib/import/apply.ts:216-223` (with `git.ts:91-106`) | Per-commit mode applies files in `git diff` order, which is path order: `analysis/` < `data/outcomes.json` < `data/snapshots/` < `reports/`. That is not the FK order the plan promises ("Within the transaction the upserts run in foreign-key order: `ipos`, then snapshots…"). When a routine run analyses a newly listed IPO, the same commit adds its card and analysis **and** the snapshot that first creates its `ipos` row. The card goes in first and violates `ipo_cards.ipo_key → ipos.key`, the commit fails, and because a commit's content never changes, every later import is blocked until someone runs a rebuild. Replaying main's first-parent history shows this in **6 real routine commits**: `ffdb3cb` (paras-healthcare), `6632e26` (bls-polymers), `07abccd` (eaaa-alternatives, sfc-environmental-technologies), `f35a790` (bombay-coated-and-special-steels), `6962cca` (m-k-sons-fine-jewels). For `6962cca`, `changedPaths` returns `analysis/m-k-sons-fine-jewels.json, analysis/m-k-sons-fine-jewels.md, data/outcomes.json, data/snapshots/2026-10-23T1908.json, reports/2026-10-23-pm.json`. This is the normal path for the Action (009). The rebuild avoids it only because it applies snapshots first. | Sort a commit's changes by kind before applying them: upserts in FK order (snapshot → card → analysis → report → outcome), deletions child first. Add a temp-repo db test where **one commit** adds a snapshot that first introduces an IPO together with its card, analysis and a report, and assert it imports `ok`. |
| 4 | Major | `web/lib/import/types.ts:18-28`, every `as NewX` cast in the parsers | `Loose<T>` widens every column to `string \| number \| boolean \| Date \| …` and casts back, which switched off the type checking that would have caught #1 at `npm run typecheck`. | Build the rows with the real insert types (`typeof table.$inferInsert`), converting dates (#1) and passing numerics as `string` (Drizzle's `numeric` type). Keep a cast only where it can't be avoided, with a comment saying why. |
| 5 | Major | `web/lib/import/apply.ts:132-137` (report), `:141-147` (outcomes); `docs/db.md` § Import and rebuild | Per-commit mode and the rebuild disagree after an edit that **drops an entry**. If a report is rewritten without one of its IPOs (for example, a re-run brief), or `data/outcomes.json` loses a key, the per-commit upsert leaves the old `ipo_verdicts` / `ipo_outcomes` row in place, while a rebuild drops it. db.md (as changed in this task) says per-commit mode "converges to exactly git … matching the rebuild", and the plan's "twice, same counts" check depends on that. | When applying a report, delete that `(report_date, session)`'s verdict rows whose `ipo_key` isn't in the file. When applying `data/outcomes.json`, delete outcome rows whose key isn't in it. Add a temp-repo test: commit a report with two IPOs, then one with one, and assert the counts equal a rebuild's. |
| 6 | Major | `docs/tasks/008-import-script/plan.md` § Verification | The task was handed off with its database suite never run, and the suite fails on every import test. CI on a pushed branch is how this suite runs (it ran this way for 007). | Before handing back, record a green `db` job in Verification. Claude pushes the branch after the fix step so CI runs; DeepSeek can't push, so it pastes what it can run, and Claude adds the CI run link in the next round. |
| 7 | Minor | `web/scripts/import.ts:34-37` | `--from` or `--root` given without a value (`npm run import -- --from`) gives `undefined`, and the CLI silently runs the default (last-ok, or a rebuild!) on the default root. | Exit with usage (code 2) when a value flag has no value or the value starts with `--`. |

### Plan and docs

- **Built as approved, mostly.** The five "Changes during build" are justified:
  - (1) Test (c) uses `--amend`: the plan's own recovery path for an immutable bad commit.
  - (2) A synthetic no-verdict fixture replaces the misnamed real file.
  - (3) The settings rows are read rather than inserted, because the db suites run in parallel.
  - (4) Raw-JSON expected counts avoid a tautology.
  - (5) Replaced tables null the fields a file drops.

  Point 5 needs #5 above to make convergence hold for dropped *entries* as well as dropped *fields*.
- **The FK-order promise isn't kept** in per-commit mode (#3); the plan's Approach is right and the code isn't.
- **Docs:**
  - db.md, tech.md and arch.md are updated with the Running labels, the four new mapping rows, the `shareholder` enum, the `updated_at` semantics, the `commit_sha` rewording and the rebuild boundary. They match the code, except db.md's convergence claim (#5).
  - The migration `0003_zippy_dexter_bennett.sql` is generated, and `drizzle-kit generate` is a no-op afterwards.
- **Rules:**
  - No AI calls, no secrets, nothing computed.
  - Numbers pass through verbatim (rule 1).
  - Research rows are rebuildable from git (rule 9).
  - App tables are left alone: plain child-first `DELETE`, no `TRUNCATE … CASCADE`.

  No project rule is broken.
- **Package lockfile:** `tsx` was already in `package-lock.json` as a transitive dependency, so the one-line lock change is in sync. `npm ci --dry-run` succeeds.
- **Process note:** this round was written by a different Claude session from the plan reviews. The session that ran `/run-task 008` got stuck on a permission prompt partway through its code review and wrote nothing. The human had told this session to take over 008 if it stalled.

## Responses (DeepSeek)

| # | Response | Commit |
| --- | --- | --- |
| 1 | Fixed. The parsers now convert timestamps to `Date` at the boundary (`maybeDate` — throws on an unparseable value so it lands in `imports.error`; parser test added), for `ipos.updated_at`, `ipo_snapshots`/`ipo_subscriptions.taken_at`, both `ai_written_at` columns, `ipo_outcomes.gmp_eve_snapshot` and `recorded_at`; the wrong `types.ts` comment is gone (see also #4) | `eb608ce` |
| 2 | Fixed. `apply.ts` skips the snapshot and subscription inserts when their row arrays are empty; the parser test covers a real no-subscription snapshot (`data/snapshots/2026-10-26T0907.json` → `subscriptions: []`), and the whole-repo rebuild (test a) now imports all 10 of them | `91ddb4f` (parser test in `eb608ce`) |
| 3 | Fixed. `importCommit` now applies deletions first (each `deleteFileRows` removes its own children) and then the upserts sorted by kind in FK order: snapshot (which upserts `ipos`) → card → analysis → report → outcome. New temp-repo test (i) puts the snapshot, card, analysis and report in one commit and asserts it imports `ok` | `91ddb4f` |
| 4 | Fixed. `Loose<T>` is deleted; every parser builds rows with the table's real insert type (`typeof table.$inferInsert`) — timestamps as `Date` (#1), numerics as `string`, integers/bigints as `number`. The only remaining casts are the file-driven `Partial` accumulators, each with a comment saying why (a file decides which optional columns to carry, so NOT NULL columns can't be proven present at build time) | `eb608ce` |
| 5 | Fixed. Applying a report now deletes the `(report_date, session)`'s verdict rows whose `ipo_key` isn't in the file (all of them when the file has no entries), and applying `data/outcomes.json` deletes the outcome rows whose key isn't in it — so per-commit mode converges to exactly git. New temp-repo test (h) rewrites a report and outcomes.json dropping one IPO and asserts the counts equal a rebuild's | `91ddb4f` |
| 6 | Fixed as far as this step can. Verification is updated with everything run here: the offline suite (57 tests), typecheck, lint, schema drift, the parser run over all 373 committed files (277 snapshot rows, 13 cards, 13 analyses, 27 reports, 8 outcomes, 0 failures), and the CLI smoke tests. The db suite still refuses to run without the Neon secrets, so it runs in CI's `db` job once this branch is pushed — per the finding's own instruction, Claude pastes the CI run link in the next review round | `eb608ce`, `91ddb4f`, `95606de`, `5f1707a` |
| 7 | Fixed. A `flagValue` helper exits with usage (code 2) when `--from` / `--root` has no value or the next token starts with `--`; the db suite's CLI block covers all four bad invocations | `95606de` |

## Round 2 (2026-10-30)

**Verdict:** Changes requested

**Diff:** `git diff 4a3d0b9..task/008-import-script` at d9e8a75. The first respond step (`2403ca7`) ended on a turn with no content and no tool calls: the model spent its whole output budget reasoning. It changed nothing but the status, so Claude set `code-changes` again (`4a3d0b9`) and reran the step.

**Tests:**

Locally, in the worktree: `npm test` 6 files, 57 passed. `npm run typecheck`, `npm run lint` and `npx drizzle-kit generate` (no changes) are clean.

CI on the pushed branch ([run 40956884017](https://github.com/badjatya/IPO/actions/runs/40956884017)): `web` and `tests` passed; **`db` failed, 5 of 26**:

```text
 ✓ tests/db/schema-shape.test.ts (7 tests)
 ✓ tests/db/schema-rules.test.ts (8 tests)
 × rebuilds twice to identical counts that match the repo's own files   110292ms
 ✓ leaves app tables alone through a rebuild                            109387ms
 ✓ spot-checks a snapshot, zetwerk's card, analysis and latest verdict, an override and an outcome
 ✓ (c) a bad commit leaves no rows and fails the run; a fixed commit imports and flips its row to ok
 × (d) a deleted report file's rows go with it; ipos facts survive
 ✓ (e) re-running an already-imported range changes nothing
 × (g) an unchanged ipo_analyses row is not rewritten
 × (h) an edit that drops an entry removes its rows, matching a rebuild
 × (i) one commit can first introduce an IPO with its card, analysis and report
 ✓ import: CLI (2)

SyntaxError: No number after minus sign in JSON at position 1 (line 1 column 2)        (a)
AssertionError: expected 27 to be 1                                                     (d)
AssertionError: expected '5276b3dd5f00eed638f580af5b9b718eb541d…' to be 'f59e94213450fdd5e6d66807c68d1e5e5e1ec…'  (g)
AssertionError: expected 141 to be 2                                                    (h)
AssertionError: expected 13 to be 1                                                     (i)
 Test Files  1 failed | 2 passed (3)
      Tests  5 failed | 21 passed (26)
```

The round-1 Blockers are fixed in the code. The rebuild now succeeds over the whole repo (test b and the spot-checks pass on its rows), and so do the failure/retry path (c) and the re-run (e). All five remaining failures are bugs in the tests.

### Round 1 findings

| # | Status |
| --- | --- |
| 1 | Fixed: `maybeDate` at the parser boundary; the rebuild writes every timestamp column. |
| 2 | Fixed: empty inserts are skipped; all 10 no-subscription snapshots import. |
| 3 | Fixed in code: deletions first, then upserts in FK order. Its test (i) can't pass yet (#9). |
| 4 | Fixed: `Loose` removed, real insert types, commented `Partial` accumulators. |
| 5 | Fixed in code. Its test (h) can't pass yet (#9). |
| 6 | Open until the `db` job is green. |
| 7 | Fixed, and covered by the CLI test. |

### Findings

| # | Severity | Where | Problem (what breaks, and when) | Suggested fix |
| --- | --- | --- | --- | --- |
| 8 | Major | `web/tests/db/import.test.ts:97-101` (`expectedResearchCounts`) | Runs `JSON.parse` on **every** research file, including the `analysis/<key>.md` analyses, whose `---` front matter throws `No number after minus sign in JSON`. Test (a), the roadmap's "twice, same counts" check, therefore never compares anything. | Parse only the JSON kinds (snapshot, report). Count cards and analyses from the file list, as it already does. |
| 9 | Major | `web/tests/db/import.test.ts:253` onward (tests d, g, h, i) | The temp-repo tests assume an empty research database, but they run on the same branch after the whole-repo rebuild tests, which leave the repo's rows behind (27 reports, 141 verdicts, 13 cards). Their absolute counts (`toBe(1)`, `toBe(2)`) then fail. (c) and (e) pass only because they compare relative values. | Before each temp-repo test, reset the research tables **and `imports`**: a `beforeEach` that deletes them child first, or a rebuild over an empty temp repo plus an `imports` delete. Leave the app tables alone, since `schema-rules` runs in parallel on the same branch. |
| 10 | Major | `web/tests/db/import.test.ts:424-425` (test g) | The last assertion selects `ipo_analyses` with no `where`, so `after[0]` is whichever row comes first. #9 makes that another IPO's analysis, hence the hash mismatch. Also, the third run imports 0 commits, so the content-sha skip (`apply.ts` `setWhere`) is never exercised: an unchanged `xmin` holds trivially, because nothing was re-applied. | Filter on `ipo_key`. To exercise the skip, re-apply the analysis with unchanged content. For example, delete the second commit's `imports` row, or re-import from the first commit with `from` after deleting its ok rows, so `applyFile` runs on the same `.md`. Then assert `xmin` is unchanged. |
| 11 | Minor | `web/lib/import/apply.ts` `rebuild()` | A whole-repo rebuild takes about 55 s on CI (two rebuilds take 110 s in test a). That's one awaited insert per row over the WebSocket, plus one `git log` process per file for `commit_sha`. It's fine today, but it grows by two runs every weekday. | Record as a follow-up. Batch the inserts per file (the snapshot and verdict arrays), and get `commit_sha` for every path from one `git log --name-only` pass. No change needed for this task. |

### Plan and docs

- **Changes during build 6 and 7** (Verification and the responses hash) are fine. The db.md edits match the new convergence behaviour: deletions first, FK order, dropped entries removed.
- **To approve,** CI's `db` job must be green, with the run linked here.
