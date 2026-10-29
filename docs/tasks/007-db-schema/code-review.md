# Code review: 007-db-schema

## Round 1 (2026-10-30)

**Verdict:** Changes requested

**Diff:** `git diff main...task/007-db-schema` at `2db6092`

**Tests:** run by Claude in the worktree.

```text
$ cd web && npm test
 Test Files  4 passed (4)
      Tests  21 passed (21)

$ npm run typecheck        → tsc --noEmit, exit 0
$ npm run lint             → oxlint --deny-warnings, exit 0
$ npx drizzle-kit generate → No schema changes, nothing to migrate 😴
$ git status --porcelain db → (empty)

$ cd .. && python3 -m unittest discover -s tests
Ran 227 tests in 0.520s
OK
```

`npm run test:db` hasn't run on a real branch. There's no `NEON_API_KEY` here, and findings 1 and 2 mean it would fail anyway.

### Findings

| # | Severity | Where | Problem (what breaks, and when) | Suggested fix |
| --- | --- | --- | --- | --- |
| 1 | Blocker | `web/db/schema.ts:129-132` (and `151-153`, `200-201`, `216-218`, `330-334`, `354-357`, `428-433`); `web/db/migrations/0001_cloudy_hercules.sql:160-162` | Every composite key is written as `.primaryKey()` on each of its columns. drizzle-kit emits one `PRIMARY KEY` clause per column: `"ipo_key" text PRIMARY KEY NOT NULL, "taken_at" timestamptz PRIMARY KEY NOT NULL`. Postgres rejects that with `multiple primary keys for table "ipo_snapshots" are not allowed`. Seven tables are affected: `ipo_snapshots`, `ipo_subscriptions`, `reports`, `ipo_verdicts`, `quarterly_results`, `shareholding` and `watchlist_items`. `drizzle-kit migrate` therefore fails on the first one, and no table gets built on any database. The composite FKs into `ipo_snapshots (ipo_key, taken_at)` and `reports (report_date, session)` also depend on those composite keys existing. | Declare each composite key once, at table level: `primaryKey({ columns: [table.ipoKey, table.takenAt] })` from `drizzle-orm/pg-core`, in the table's extra-config array. Remove the column-level `.primaryKey()` calls on those columns and keep their `.references(...)`. Regenerate: the snapshot changes, so this is a new migration or a regenerated `0001`. Nothing has been applied anywhere yet, so regenerating `0001` is fine. Say which you chose under "Changes during build". |
| 2 | Blocker | `web/scripts/neon-branch.mjs:19` | `API = "https://neon.tech/api/v2"` is the wrong host. `neon.tech/api/v2/...` answers `308` to `https://neon.com/api/v2/...`, which answers `404`. Fetch also drops the `Authorization` header on a cross-origin redirect. So the harness fails on its first call (`GET /projects/{id}/branches`), and the `db` job can never go green. Checked with `curl` on 2026-10-30: `neon.tech` → 308 → `neon.com` → 404; `console.neon.tech/api/v2/projects` → 401 (live, wants auth). | Use `https://console.neon.tech/api/v2`. |
| 3 | Major | `web/tests/db/schema-shape.test.ts` | The shape test checks tables, enums, the view, unique indexes and composite FKs. It doesn't check primary keys. But the natural keys are what make imports idempotent (db.md principle 2, § Import and rebuild), and finding 1 shows the keys are where the schema went wrong. | Add a test that reads `pg_constraint` (`contype = 'p'`) with `pg_get_constraintdef`. It should check each table's primary-key columns against db.md: composite keys for the seven tables in finding 1, single-column keys for the rest, and `id` for the identity tables. |
| 4 | Minor | `docs/arch.md:316` | The Database row dropped "and preview" ("a branch per test run and preview"). A branch per preview deploy is still the decided design in db.md and ADR-0010. It isn't built yet, because hosting is still open (D11). The row now reads as if preview branches were dropped. | Keep both: test-run branches **Running** (the `db` job), preview branches **Decided** (with the host, D11). |
| 5 | Nit | `web/scripts/neon-branch.mjs:20, 201` | `WORKTREE_ROOT` is really `web/`, not the worktree root. `?connection_uris=true` isn't a parameter of the create-branch endpoint: it returns `connection_uris` whenever it creates an endpoint. | Rename it to `WEB_ROOT` and drop the query string. |

### Plan and docs

- **Built as approved, apart from the findings.** One connection (`db()` over the cached `sql()` client). Custom migrations for `citext` (`0000`, runs before the tables) and the seed (`0002`), and the generated `0001` is untouched. The view comes from `pgView`. The seed has the three decided rows and no cap row.
- **Insert defaults.** `now()` and `gen_random_uuid()`, and db.md records them.
- **Test isolation.** The rule tests are excluded from `npm test` by config, and the db config throws without `NEON_TEST_BRANCH_ID`. I checked two ways the tests could reach `dev`. `process.loadEnvFile` doesn't overwrite a variable that's already set (tested on Node 24.15), so `drizzle.config.ts` can't replace the harness's `DATABASE_URL_UNPOOLED` with the one in `.env.local`. `@neon/env`'s runtime (`parseEnv`) reads only `process.env`, and only its CLI reads `.env` files. So the tests can't reach `dev` by those routes.
- **Branch handling.** The harness creates a schema-only branch with `expires_at`, drops `public` and `drizzle` before migrating, and deletes the branch by the ID it created, refusing the default branch and `dev`. The unique-violation tests assert `23505` plus the index name read from the catalog. They cover `running` + `queued`, and `queued` after `done`.
- **CI.** The drift step uses `git status --porcelain db`, so a new untracked migration counts too. The `db` job wiring matches H06.
- **Deviations.** All six under "Changes during build" are justified. Pinning db.md's bare `numeric` columns and making `imports.started_at` / `finished_at` nullable are reasonable readings, and both are recorded in db.md.
- **Docs and labels.** Updated in db.md, tech.md, arch.md and ai.md. The "Running" labels for the schema and the `db` job hold only once a real run is green, so the next round needs that.
- **Next round needs a real run.** Fix findings 1 and 2, then `npm run test:db` needs a green run before this can be approved: the human runs it with the key, or pushes the branch for the CI `db` job. Paste the output or link the run under Verification.

## Responses (DeepSeek)

| # | Response | Commit |
| --- | --- | --- |
| 1 | **Fixed.** Every composite key is now declared once at table level: `primaryKey({ columns: [...] })` in each table's extra config, column-level `.references()` kept (`web/db/schema.ts`). Since nothing has ever applied the migrations, I regenerated `0001` (`0001_cute_exodus.sql`; each of the seven tables now gets one `CONSTRAINT "…_pk" PRIMARY KEY(…)`) and recreated the seed as `0002_outstanding_lyja.sql` — a follow-up migration could never run, because broken `0001` fails before the journal advances. `drizzle-kit generate` is a no-op afterwards, so the CI drift step stays green. The green `npm run test:db` run that proves this still needs the human (no `NEON_API_KEY` here) or the CI `db` job — see Verification. | `19f8ae1` |
| 2 | **Fixed.** `API` is now `https://console.neon.tech/api/v2` in `web/scripts/neon-branch.mjs`. Same caveat as finding 1: the harness can't run here, so the first real `npm run test:db` (human or CI) is the proof. | `3e5cea5` |
| 3 | **Fixed.** `web/tests/db/schema-shape.test.ts` now reads `pg_constraint` (`contype = 'p'`) with `pg_get_constraintdef`: exactly one PK row per table, and per-table column lists against db.md — composite for the seven natural-key tables, single-column for the rest, `id` for the identity/uuid tables. | `c1dafeb` |
| 4 | **Fixed.** `docs/arch.md` § 6 Database row keeps both: test-run branches **Running** (the `db` job), preview branches **Decided** (with the host, D11). | `5e0c686` |
| 5 | **Fixed.** Renamed `WORKTREE_ROOT` → `WEB_ROOT` (it is `web/`) and dropped `?connection_uris=true` from the create-branch call; the `pickConnectionUri` fallback stays. | `3e5cea5` |

## Round 2 (2026-10-30)

**Verdict:** Changes requested

**Diff:** `git diff 1ce9501..71a4291` (the round 1 fixes), pushed as `task/007-db-schema` at `71a4291`

**Tests:**

```text
Claude, in the worktree:
$ cd web && npm test               → Test Files 4 passed (4), Tests 21 passed (21)
$ npm run typecheck                → exit 0
$ npm run lint                     → exit 0
$ npx drizzle-kit generate         → No schema changes, nothing to migrate 😴; git status --porcelain db → empty
$ python3 -m unittest discover -s tests → Ran 227 tests, OK

CI run 40935844323 (https://github.com/badjatya/IPO/actions/runs/40935844323), push of 71a4291:
tests: success
web:   success   (includes the new schema-drift step)
db:    failure

db job, "Database tests on a Neon branch":
> node scripts/neon-branch.mjs
test:db failed: Error: no default branch found; refusing to guess where to fork from
    at main (file:///home/runner/work/IPO/IPO/web/scripts/neon-branch.mjs:105:11)
##[error]Process completed with exit code 1.
```

**Round 1 fixes:**

| # | Fix | Checked |
| --- | --- | --- |
| 1 | Composite keys | One table-level `CONSTRAINT … PRIMARY KEY(…)` per table; 23 primary keys for 23 tables; no table has two; the seed migration is byte-identical |
| 2 | API host | Now reaches the Neon API: the run got past authentication to the branch list |
| 3 | Primary keys | The new shape test checks one primary key per table with db.md's columns |
| 4 | arch.md | Database row restored, preview branches **Decided** |
| 5 | Naming | `WEB_ROOT`, and no query string |

Round 1's findings stay closed. The failure below is a new one, which the first real run exposed.

### Findings

| # | Severity | Where | Problem (what breaks, and when) | Suggested fix |
| --- | --- | --- | --- | --- |
| 6 | Blocker | `web/scripts/neon-branch.mjs:103` | `branches.find((branch) => branch.is_default === true)` finds nothing. Neon's API v2 Branch object marks the default branch with `default: true` (`primary` is the older, deprecated name). There is no `is_default` field. The list call succeeded, so the project's branches came back, but none matched. The harness stops before creating a branch, so the `db` job can't pass, and the Done-when is still unproven. No branch was created, so nothing needs cleaning up. | Match on `branch.default === true`. Move it into a pure helper (e.g. `findDefaultBranch(branches)`) with an offline test that uses a fixture in the API's documented shape. When nothing matches, make the error list the branches it saw (name and `default`), so the next mismatch shows up in the log. Check the other fields the harness reads from the create response (`branch.id`, `connection_uris[].connection_uri`, `endpoints[].host`, `roles[]`) against the API reference while you're there, because this is the first run that reaches them. |

### Plan and docs

No new deviations. Add finding 6 under "Changes during build". Approval needs a green `db` job. The human will push the fix, or run `npm run test:db` with the key.

## Responses (DeepSeek)

| # | Response | Commit |
| --- | --- | --- |
| 6 | **Fixed.** The lookup is now the pure helper `findDefaultBranch(branches)`, matching `branch.default === true`, with an offline suite in `web/tests/neon-branch.test.ts` against a fixture in the API v2 Branch shape — including a regression test that the old `is_default` spelling (which the API never sends) does *not* match. The "no default branch found" error now lists every branch it saw as `` `name [default: …]` ``, so a future field mismatch shows up in the job log. The create-response fields the harness reads next were checked against the API v2 reference: `branch.id`, `connection_uris[].connection_uri` (returned when the create request makes an endpoint, per round 1 finding 5), `endpoints[].host` and `roles[].name`/`.password` (returned at creation) are all documented shapes; the fallback's extra reads (`connection_parameters`, `branch.database_name`) degrade to the correct `neondb` default for a fresh schema-only branch, so nothing else needed changing. The failed run had created no branch, so there was nothing to clean up. Offline re-run: `npm test` 25 passed (4 new), typecheck/lint clean, `drizzle-kit generate` a no-op, Python 227 OK — see plan.md Verification. The green `npm run test:db` that proves the Done-when still needs the next push (CI `db` job) or a human run with `NEON_API_KEY`. | `106c406` |

## Round 3 (2026-10-30)

**Verdict:** Changes requested

**Diff:** `git diff f971190..03dc005` (finding 6), pushed as `task/007-db-schema` at `03dc005`

**Tests:**

```text
Claude, in the worktree: npm test 25 passed (25); typecheck, lint clean; drizzle-kit generate no-op.

CI run 40937366828 (https://github.com/badjatya/IPO/actions/runs/40937366828), push of 03dc005:
tests: success   web: success   db: failure

db job:
test:db using branch br-steep-frost-a1s6lsmy (db-test-1793300943457)
Using 'pg' driver for database querying
[✓] migrations applied successfully!
 ❯ tests/db/schema-shape.test.ts (7 tests | 3 failed)
     ✓ has exactly the 23 db.md tables in public
     × has the 12 db.md enums with their values
     ✓ has the watched_symbols view (distinct symbols, no user data)
     × has the partial unique indexes that carry the rules
     ✓ has the unique exchange_ref and dedupe_key indexes
     × has the composite FKs (ipo_subscriptions, ipo_verdicts)
     ✓ has exactly one primary key per table, with db.md's columns
 ❯ tests/db/schema-rules.test.ts (8 tests | 5 failed)
     × fails to queue two jobs for one stock (partial unique index, 23505)   expected undefined to be '23505'
     × fails a queued job while another is running for the same stock         expected undefined to be '23505'
     × allows a new queued job once the previous one is done                  expected 'done' to be 'queued'
     × rejects a duplicate alert dedupe_key (23505)                           expected undefined to be '23505'
     × rejects a duplicate announcement exchange_ref (23505)                  expected undefined to be '23505'
     ✓ returns each watched symbol once across users in watched_symbols
     ✓ seeds exactly the decided settings rows, with no platform-cap row
     ✓ cascades a user delete to their watchlist items
test:db deleted branch br-steep-frost-a1s6lsmy
```

Finding 6 is fixed: the harness found the default branch, created the branch, migrated, ran the tests and deleted the branch.

The first half of the Done-when is now proven: "migrations build the full schema on an empty Neon branch". All 23 tables and 23 primary keys check out, as do the view, the seed rows and the cascade.

All 8 failures are in the test assertions, not the schema. Each one compares against the wrong shape of a value that Drizzle, Postgres or the driver returns. Because of that, the rule-carrying constraints are still unproven, so this can't be approved yet.

### Findings

| # | Severity | Where | Problem (what breaks, and when) | Suggested fix |
| --- | --- | --- | --- | --- |
| 7 | Blocker | `web/tests/db/schema-rules.test.ts:35-42, 80, 93, 129, 148` | drizzle-orm 0.45 wraps every driver error in `DrizzleQueryError` (`node_modules/drizzle-orm/errors.js:10`). Its message is `Failed query: …`, and the Postgres error is in `.cause`. So `violation.code` is `undefined`, and the message never contains the index name. The test also can't tell "no error was thrown" from "the code is on `.cause`", because `captureViolation` returns `undefined` in the first case and `violation?.code` reads `undefined` in both. | In `captureViolation`, fail the test when the statement succeeds. Return the Postgres error: `error.cause ?? error`. Assert `code === "23505"` and that its `constraint` field (or its `message`) names the index, on that inner error. |
| 8 | Blocker | `web/tests/db/schema-rules.test.ts:107-111` | `select … where symbol = $1` returns both jobs (the `done` one and the new `queued` one), and `const [queued]` takes whichever comes first, here `done`. The insert itself succeeded: the test reached the select. | Filter on `status = 'queued'`, or select every row and assert the set of statuses is `{done, queued}`. |
| 9 | Blocker | `web/tests/db/schema-shape.test.ts:96-107` | `pg_get_indexdef` doesn't echo the migration text back. It schema-qualifies the table (`ON public.analysis_jobs`), rewrites `in (…)` to `= ANY (ARRAY['queued'::job_status, 'running'::job_status])`, and wraps predicates (`WHERE (symbol IS NOT NULL)`). So none of the three `includes(...)` strings can match. | Assert on parts instead of the whole definition. Read the table, the index's columns and `pg_get_expr(ix.indpred, ix.indrelid)`, then check the predicate mentions the right column and values, case-insensitively (`queued` and `running`; `is not null`). Or normalise both sides before comparing. |
| 10 | Blocker | `web/tests/db/schema-shape.test.ts:141-150` (the composite FK test) | `pg_get_constraintdef` writes `REFERENCES ipo_snapshots(ipo_key, taken_at)`, with no space before `(`. The regex wants `ipo_snapshots \(`, so neither composite FK is found. | Use `\s*` before `\(` (and keep `(public\.)?`), or compare on `conkey`/`confkey` column names from `pg_constraint` and `pg_attribute`. |
| 11 | Blocker | `web/tests/db/schema-shape.test.ts:100-111` (the enum test) | `e.enumlabel` has type `name`, so `array_agg` returns `name[]`. The serverless driver has no parser for that array type, so it most likely returns the raw text `{announced,upcoming,…}` instead of a JS array, and the deep-equal fails. Twelve keys came back on both sides, so the types exist. | Use `array_agg(e.enumlabel::text order by e.enumsortorder)`, or `select … enum_range(null::<type>)::text[]`. |

### Plan and docs

No change to the plan. Record findings 7-11 under "Changes during build". The `db` job, and with it the "Running" labels, still need a green run.

**Third round without approval.** Under `/run-task`, the loop stops here and the human decides whether to run a fourth `respond`. What's left is limited to the two test files. The schema, migrations, harness, CI wiring and docs all checked out.
