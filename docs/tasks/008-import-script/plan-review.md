# Plan review: 008-import-script

## Round 1 (2026-10-30)

**Verdict:** Changes requested

**Read:** plan.md, AGENTS.md, docs/tasks/README.md, docs/db.md (IPO tables, `imports`, § Where the data comes from, § Import and rebuild, § Migrations and environments), docs/arch.md § 4.3, docs/tech.md (web platform, repository layout), ADR-0011, ADR-0025, `web/lib/db.ts`, `web/db/schema.ts` (`sub_category`, `imports`), `web/package.json`, `web/tsconfig.json`, `web/vitest.db.config.mts`, `web/tests/db/setup.ts`, `web/scripts/neon-branch.mjs`, `.github/workflows/ci.yml`, `ipo_agent/quiet.py`, `ipo_agent/nse.py`. I also checked every committed snapshot, card, analysis, report and `data/outcomes.json` at HEAD, plus the research-file history (`git log`).

The shape is right. The library sits in `web/lib/import/` with a CLI. Snapshots are insert-only and the rest is replaced on natural keys. The rebuild deletes child-first and leaves app tables alone. Counts come from the repo at run time, and there's no AI. The data check found good news too: every card, analysis, report and outcome key has an `ipos` row from some snapshot, and no snapshot entry has a null phase or name. The changes below are about the driver, reading the right version of each file, walking the history correctly, and one enum gap that would make the import fail on today's files.

### Decisions (human)

1. **`shareholder` subscription category:** add `shareholder` to the `sub_category` enum in this task, through a new generated migration (Vijay, 2026-10-30). Six committed snapshot entries carry it (`ipo_agent/nse.py:71` emits it), and dropping those rows would lose data that git holds (rule 9).
2. **TypeScript runner:** add `tsx` as a devDependency, as planned (Vijay, 2026-10-30). The human runs the install before the build.

### Changes requested

1. **Record the decisions and the `shareholder` migration.** Move both decisions into the Approach as decided by the human on 2026-10-30. Add a step that adds `shareholder` to `subCategory` in `web/db/schema.ts` and runs `drizzle-kit generate` to get a new migration, with the generated file untouched (db.md § Migrations). That step also updates db.md's enum table and changes the plan's "no migrations" lines. Test it with a schema-shape check that the enum has the value, plus a parser test that a `shareholder` subscription maps to a row. Without this, the plan's "unknown value throws" rule fails the rebuild on today's repo.

2. **Use Neon's WebSocket `Pool`, not `pg`, for transactions.** ADR-0025 (Accepted) decides `drizzle-orm/neon-serverless` with `@neondatabase/serverless`'s `Pool` wherever an interactive transaction is needed. It also says the connection lives in `web/lib/db.ts`. The plan picks `drizzle-orm/node-postgres` and moves `pg` into dependencies. That breaks a binding ADR, and the plan's Context section misreads it ("transactions over a pooled interactive connection" is the WebSocket Pool). Instead:
   - Add the transactional client next to `db()` in `web/lib/db.ts`, e.g. a function that returns Drizzle over a `Pool` on the pooled `DATABASE_URL`, plus a way to close it.
   - Node 22+ has a global `WebSocket`. If the driver still needs `neonConfig.webSocketConstructor`, say so.
   - Keep `pg` a devDependency, used only by the test harness.
   - Drop the `pg` move from step 1 and the Packages line. The only package change is `tsx`.

3. **Read each file as it was in the commit being imported, not from the working tree.** The plan reads content from the working tree. A per-commit import of an old commit would then store a later version of the file under that commit's `imports` row, and in this repo cards, reports and outcomes are modified after they're first written (12 modifying commits). A rebuild would also record HEAD while it reads a possibly dirty working tree.
   - Per commit: read `git show <sha>:<path>`, or batch with `git cat-file --batch`.
   - Rebuild: list files with `git ls-tree -r --name-only HEAD`, not `git ls-files`, which includes staged changes, and read them from HEAD.
   - Remove "a file that no longer exists since the commit is skipped", since the file always exists in its own commit.

4. **Walk main's first-parent history and diff each commit against its first parent.** `git show --name-only --format=` on a merge commit lists only conflicted paths, and `git log --reverse <from>..HEAD` also yields side-branch commits in date order. This repo has both. For example, `77b5ed5` ("IPO brief 2026-10-29 pm") reached main only through a merge, and a side commit's older file version can be applied after a newer one.
   - List commits with `git rev-list --first-parent --reverse <from>..HEAD`.
   - Get each commit's paths from `git diff --name-status --no-renames <sha>^1 <sha>`. Use the empty tree for a root commit.
   - Say what a deleted research file (status `D`) does. Either delete the rows that file owns in the same transaction, or skip it and leave the rows for the next rebuild. Pick one, document it in db.md and test it. `c09248d` deleted a report file, though one of an ignored kind (`.md`).

5. **Define "last ok" exactly, and rebuild when there's nothing to resume from.**
   - **Last ok:** the first sha in `git rev-list --first-parent HEAD` that has an `ok` row. The table has no sequence column, so that's the only sound order.
   - **Nothing to resume from:** on an empty `imports` table, or when no `ok` sha is on the current first-parent history (rewritten history), the default command should run the rebuild. It shouldn't replay about 190 commits one by one, where old versions of early files may not pass today's validation and would block the import for good.
   - **Retries:** say that writing an `ok` row upserts over an earlier `failed` row for the same sha, since `commit_sha` is the primary key. Test that a failed commit, once fixed, imports on the next run.

6. **Map every `ipos` column the snapshot carries.** db.md's mapping table leaves out four `ipos` columns that the snapshot entries have: `rhp_url` (249 of 277 entries), `rhp_source` (`nse` / `sebi` / null), `url` → `investorgain_url`, and `anchor_done`. The plan maps only what db.md lists, so these would always be null. Also:
   - Map them, and add the rows to db.md's mapping table in the doc updates.
   - Say what `ipos.updated_at` is set to. Use the `generated_at` of the snapshot that last updated the row, not `now()`, so a rebuild gives the same rows.
   - Define "present" for the merge as key present and non-null. Write down the consequence: a field that later becomes null keeps its old value.

7. **Make the git tests work in CI and stop pinning moving shas.** Both CI jobs use `actions/checkout@v4` with its default `fetch-depth: 1`, so `a63640f`, `ffdb3cb` and `commitsAfter` don't exist there and step 2's tests fail. `lastCommitTouching("analysis/zetwerk.json") == ffdb3cb` also rots the next time that card changes, which goes against the plan's own no-rot aim. Instead:
   - Build a throwaway git repo in a temp directory inside the test.
   - Commit copies of real repo files (a snapshot, a card, a report, `data/outcomes.json`) across a few commits, including a modification, a side branch merged with `--no-ff`, and a deletion.
   - Run the classifier, the first-parent walk and the per-commit reads against it. That keeps "the tests use the repo's own files" true without depending on this repo's history.
   - The db tests can do the same for the per-commit path, and use the real checkout's HEAD tree for the whole-repo rebuild, which works in a shallow clone.
   - Don't assert `reports.commit_sha` against the real checkout, because a shallow clone gives the graft commit. Note in Risks that 009's Action needs `fetch-depth: 0`.

8. **Cover quiet reports with a fixture.** No committed report has `"generated": "quiet"` or `carried_from` yet, but `ipo_agent/quiet.py:169` writes both, and the first quiet run will commit one. Add a parser test with a report shaped like `quiet.py`'s output: it maps to `quiet = true`, keeps `carried_from`, and has null provenance. A normal report maps to `quiet = false`.

9. **Give the failure test a real seam.** Test (c) needs "a commit file set with one invalid file". With change 7, do it in the temp repo: one commit adds a good snapshot and a malformed card. Assert that the commit leaves no rows (not even from the good file), that it records one `failed` row with the error, and that the run exits non-zero. Then commit a fix and check the next run imports both commits' data and turns the row `ok`.

10. **Say how the CLI gets `DATABASE_URL`.** Locally it's in `web/.env.local` (`neon checkout dev`), and tsx doesn't load env files by itself. Name the mechanism, e.g. `tsx --env-file-if-exists=.env.local` in the npm script, or `parseEnv` from `@neon/env` as `web/lib/db.ts` does. Also say that the CLI exits with a clear message when the variable is unset.

### Notes

- **Concurrency.** Taking `pg_advisory_xact_lock(<constant>)` at the start of each import and rebuild transaction is a cheap guard against a local run overlapping the Action (009). It's worth adding, but not required.
- **`reports.commit_sha`.** With change 3, the per-commit value is the commit being imported, and the rebuild value is `git log -1 --format=%H -- <path>`. Both are "the last commit that changed the file". db.md says "the commit that added it", so reword that line in the doc updates.
- Today's HEAD has 35 snapshots (277 IPO entries), 13 cards, 13 analyses, 27 reports and 8 outcomes. The plan's counts are slightly behind, which is another reason to derive them at run time, as planned.
