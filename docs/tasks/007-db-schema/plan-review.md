# Plan review: 007-db-schema

## Round 1 (2026-10-29)

**Verdict:** Changes requested

**Read:** plan.md, AGENTS.md, docs/tasks/README.md, docs/db.md, docs/tech.md, docs/arch.md § 7.2, docs/ai.md (CI row), ADR-0010, ADR-0011, ADR-0025, ROADMAP.md (007, D04, D08), `web/lib/db.ts`, `web/neon.ts`, `web/package.json`, `web/vitest.config.mts`, `web/.env.example`, `.github/workflows/ci.yml`

The scope is right: 23 tables, 12 enums, the view, the three decided seed rows and no cap row. One connection, migrations over the unpooled URL. Most of the changes below are about the test harness. It touches a real Neon project, so it has to be hard to point at the wrong branch.

### Decisions (human)

1. **D08 cap row:** leave `analysis_daily_limit_platform` unseeded in 007 (Option B). The row is added once D08 sets a number, before 020/022 read it.
2. **Unset cap:** gate closed (Option A). While the row is missing, no new or refreshed analysis is dispatched. Jobs stay queued, and the loading screen says why. No Gemini quota is spent until an admin sets the cap.

### Changes requested

1. **Record the decisions.** Move both items out of "Decisions needed" into the Approach, as decided by the human on 2026-10-29. The db.md update in step 7 should state the gate-closed rule beside the `settings` seed table. It should also add the rule to the "Start the worker" row in § Access patterns, so 018/022 build it.

2. **Don't hand-edit the generated migration.** drizzle-kit never emits `CREATE EXTENSION`, and appending INSERTs to `0000_*.sql` mixes hand-written SQL into a generated file. That also makes the "generate twice, no changes" check say little. Instead:
   - Put `CREATE EXTENSION IF NOT EXISTS citext` in a custom migration (`drizzle-kit generate --custom`) that runs before the tables.
   - Put the seed INSERTs in their own custom migration after the tables.
   - Do the same for `watched_symbols` if `pgView` can't generate it.
   - Leave the generated file untouched.
   - Say how `users.email` gets its `citext` type, e.g. a `customType` in `schema.ts`, since drizzle has no built-in citext column.

3. **Catch schema drift in CI, not only by hand.** Step 3's "re-run generate" check runs once, at build time. Add a CI step that runs `npx drizzle-kit generate` and fails if `web/db/migrations/` changed (`git status --porcelain`). It needs no database, so it can go in the existing `web` job. `drizzle.config.ts` must therefore load without `DATABASE_URL_UNPOOLED` set when it only generates. Otherwise a later task can change `schema.ts` without a migration and nothing fails.

4. **Keep the rule tests out of `npm test` by config, not by a missing `DATABASE_URL`.** Locally, `DATABASE_URL` is the `dev` branch (`neon checkout dev` writes it, and many shells export it). A skip-if-unset guard would therefore run the inserts against `dev` whenever the variable is set. Instead:
   - Exclude `tests/db/**` in `vitest.config.mts`.
   - Run the db tests from a separate Vitest config with the `node` environment, used only by the harness.
   - Make that config refuse to start unless the harness set a marker variable naming the branch it created (e.g. `NEON_TEST_BRANCH_ID`).
   - The harness sets `DATABASE_URL` for its child processes only.

5. **Make the test branch empty, short-lived, and the only thing deleted.**
   - **Parent branch.** Name the parent and how the branch starts empty. Branching from `production` copies whatever is in it. Once 008 and 010 land, that includes research rows and user data. Migrating a copy of an already-migrated parent doesn't prove the migrations build an empty database, which is the Done-when. Use a schema-only branch (`init_source: "schema-only"`) and drop `public` and the `drizzle` schema before migrating, or another method that gives the same result. That's safe only because it's a branch the script just created.
   - **Expiry.** The `web/neon.ts` 7-day policy is applied by `neon checkout`, not by a raw API call. The plan's backstop doesn't exist for a branch made with `POST /branches`. Set `expires_at` on the create request (e.g. now + 1 day).
   - **Deletion.** Delete only by the branch ID the create call returned. Refuse to run if that ID is the default branch or `dev`.

6. **Make the assertions specific, and check the full schema on the branch.**
   - **Unique violations.** Assert SQLSTATE `23505` and the constraint or index name, not just "throws". An FK or not-null error from a bad parent row would otherwise pass the test.
   - **Open jobs.** Add `running` + `queued` for one stock (must fail), because the index covers both statuses. Also add a second `queued` after the first is `done` (must pass).
   - **Full schema.** Add a test that reads `pg_catalog`/`information_schema` after migrating. It should find:
     - the 23 tables
     - the 12 enums with their values
     - the `watched_symbols` view
     - the partial unique indexes (`analysis_jobs`, `ipos.symbol`, `stocks.isin`) and the unique `exchange_ref` and `dedupe_key` indexes
     - the composite FKs
   - That is what proves "migrations build the full schema". The offline `schema.test.ts` in step 2, which checks only that the module exports names, can be dropped or kept as a cheap extra.

7. **State the insert defaults db.md leaves blank.** db.md gives no default for the time a row is created (`created_at`, `queued_at`, `requested_at`, `recorded_at`, `added_at`, `at`, `updated_at`) or for the `uuid` keys (`users.id`, `analysis_jobs.id`). "Defaults only where db.md lists them" means every later task must supply them by hand.
   - Say what the build does. The usual choice is `default now()` and `gen_random_uuid()`.
   - Record whichever you choose in db.md, which says details may change while building. It's a schema detail, not an Open decision.
   - The seed rows need `updated_at` in either case.

8. **Settle the package list and the migrate connection before the human installs.** `/run-task` stops once to install packages, so the list must be final.
   - **devDependency.** `drizzle-kit` is a devDependency, so the command is `npm install drizzle-orm && npm install -D drizzle-kit`.
   - **Migrate driver.** Say which driver `drizzle-kit migrate` uses on the unpooled URL. Check whether `@neondatabase/serverless` alone is enough, or whether it needs `pg` or `ws`. If it would need another package, consider running migrations from the harness with drizzle-orm's own migrator over the serverless driver.
   - **Env loading.** Say how `drizzle.config.ts` loads `.env.local` locally without adding `dotenv`, e.g. Node's built-in `process.loadEnvFile`.

9. **Say who runs the real-database check before code review.** The build step has no `NEON_API_KEY`, so it can only verify the offline parts. The Verification section should say that `npm run test:db` gets a green run before code review is approved. Either the human runs it locally with the key, or the human pushes the branch so the CI `db` job runs it. The output or the run link goes into Verification. Until then the Done-when is unproven.

### Notes

- The harness has logic of its own: building the pooled URI from the response, the `finally` delete, and refusing protected branches. Small pure helpers with an offline unit test would cover it cheaply. Optional.
- Neon's GitHub Actions (`neondatabase/create-branch-action`, `delete-branch-action`) could replace the API calls in CI. The plan's own script also works locally, so either is fine. Pick one and keep it simple.
- `push` and `pull_request` both trigger CI, so a PR run creates two branches. That's harmless with an expiry set.

## Round 2 (2026-10-29)

**Verdict:** Approved

**Read:** plan.md (revision 1), round 1 above, the same docs as round 1

The nine items from round 1 are addressed:

| # | Item | Where |
| --- | --- | --- |
| 1 | Decisions recorded | "Decisions (settled…)", Approach, db.md update (seed table and "Start the worker") |
| 2 | Generated migration untouched | Custom migrations for citext, seed and view (if needed); `citext` as a `customType` |
| 3 | Drift check | `generate` + `git status --porcelain web/db` in the `web` job; config loads without the URL |
| 4 | Rule tests out of `npm test` | Excluded by config; separate node config that throws without `NEON_TEST_BRANCH_ID` |
| 5 | Branch safety | Schema-only branch, `expires_at`, schemas dropped before migrate, delete by ID, default and `dev` refused |
| 6 | Specific assertions | `23505` + index name, `running` + `queued`, `queued` after `done`, `pg_catalog` shape test |
| 7 | Insert defaults | `now()` and `gen_random_uuid()`, recorded in db.md |
| 8 | Packages and migrate driver | `drizzle-orm`; `-D drizzle-kit pg`; `process.loadEnvFile`; migrator fallback |
| 9 | Real-branch run before code review | Verification section |

### Decisions (human)

The same two decisions as round 1 (cap row unseeded; gate closed while unset). Nothing else is open.

### Notes

- **`driver: "pg"`.** In the drizzle-kit versions I know, `driver` only takes special values (e.g. `aws-data-api`, `pglite`). For a plain Postgres URL, drizzle-kit uses `pg` on its own when it's installed. If config validation or the type check rejects `driver: "pg"`, leave the option out and record it under "Changes during build".
- **Dropping `public`.** `DROP SCHEMA public CASCADE` also drops the `citext` extension if it lives there. That's fine, because the first custom migration recreates it. Recreate `public` with the same owner, so the branch's role can create in it.
- **Code review won't approve without a real run.** Code review needs a green `npm run test:db` (pasted output or a CI run link). That's Verification's second bullet.
