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
