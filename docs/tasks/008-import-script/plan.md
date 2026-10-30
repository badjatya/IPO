---
task: 008-import-script
status: done
branch: task/008-import-script
assigned_by: Vijay
planner: DeepSeek deepseek-v4-flash-0731 (OpenRouter)
reviewer: Claude Code
---

# 008: Import script: git to database

## Task

> Task 008 from docs/tasks/ROADMAP.md:
>
> ### 008 · Import script: git to database
>
> | | |
> | --- | --- |
> | Slug | `008-import-script` |
> | Status | **Ready** |
> | Depends on | 007 |
> | Owner | DeepSeek plans and builds |
> | Milestone | M1 |
>
> The script that turns the repo's research files into rows. It reads snapshots, cards, analyses, reports and outcomes and maps them as in [db.md § Where the data comes from](../db.md#where-the-data-comes-from). It works one commit per transaction, records progress in `imports`, skips unchanged content, and has a full-rebuild command. Provenance fields are read when present (004) and null otherwise.
>
> - **Done when:** importing the whole repo twice gives the same row counts; a rebuild recreates every research table and leaves app tables alone; the tests use the repo's own files.
> - **Out of scope:** `data/stocks/` (added in 015 and 018).
> - **Watch for:** the import runs outside `ipo_agent/`, which has no Postgres driver ([tech.md](../tech.md#repository-layout) puts it in `web/`).
> - **Read:** [db.md § Import and rebuild](../db.md#import-and-rebuild), [arch.md § 4.3](../arch.md#43-import-action-decided).
> - **Start:** `/run-task 008`

## Goal and scope

- **In scope:** the import script in `web/`. A TypeScript library under `web/lib/import/` (parsers, git helpers, the apply layer) and a CLI entry `web/scripts/import.ts` run through tsx. It:
  - reads the repo's research files — `data/snapshots/<time>.json`, `analysis/<key>.json`, `analysis/<key>.md`, `reports/<date>-<am|pm>.json`, `data/outcomes.json` — and maps them exactly as [db.md § Where the data comes from](../db.md#where-the-data-comes-from) says;
  - works **one commit per transaction**, along **main's first-parent history** from the last `ok` row in `imports` (or an explicit `--from <sha>`), recording each commit in `imports`;
  - skips unchanged content (`content_sha` on `ipo_analyses`) and skips commits already imported;
  - has a full-rebuild command (`--rebuild`) that empties the IPO research tables and replays every research file in the repo, leaving app tables alone;
  - reads `ai_model`, `ai_prompt_version` and `ai_written_at` from cards and reports when the file carries them (task 004) and stores null otherwise. `ipo_analyses` provenance stays null because the `.md` marker is not defined yet (020/021) — db.md already says so;
  - when the `imports` table is empty or no `ok` sha lies on the current first-parent history (rewritten history), the **default** command runs the rebuild instead of replaying ~190 first-parent commits one by one; the only schema change is the decided `shareholder` enum value and its generated migration.
- **Out of scope:** `data/stocks/*` and every stock table (015/018); the GitHub Actions workflow that runs the import on push (009, which also needs H02); the app pages that read the imported rows (011, 012); deleting files from git (the routine never deletes); any schema change beyond the `shareholder` enum value the human decided on 2026-10-30.
- **Packages:** `tsx` as a new devDependency (the CLI runner); nothing else changes. `pg` stays a devDependency, used only by the test harness (`web/scripts/neon-branch.mjs`); the import's transactional client is Neon's WebSocket `Pool`, already installed ([ADR-0025](docs/adr/0025-drizzle-on-neon-serverless-driver.md)).
- **Done when (from the roadmap):** importing the whole repo twice gives the same row counts; a rebuild recreates every research table and leaves app tables alone; the tests use the repo's own files — as **copies of real files committed into a throwaway temp git repo** for the git-layer and per-commit paths, plus the real checkout's HEAD tree for the whole-repo rebuild, both of which work in CI's shallow clone.

## Context read

- **db.md § Where the data comes from** — the exact JSON field → column mapping for all five file kinds, the insert-only snapshot/subscription rule, and the legacy-file caveats. **§ Import and rebuild** — one transaction per commit, upsert rules, rebuild definition, provenance-on-import rule. **§ `imports`** — the bookkeeping table's shape (no sequence column, so "last ok" must be found through git, not by max id). **§ Migrations and environments** — the Neon-branch test harness the import tests will join; migrations are generated, never hand-edited.
- **arch.md § 4.3 and § 5.2** — the Import Action design: the script is the "unit of work / idempotency / bookkeeping / rebuild" row; the Action itself is task 009.
- **tech.md § Repository layout, § Web platform, § Configuration** — the import lives in `web/` (the agent has no Postgres driver, ADR-0002); `DATABASE_URL` is pooled and lives in `web/.env.local` locally; `pg` (dev) and `@neondatabase/serverless` (deps) are already installed; Node is 22.22+ locally, 24.15+ in CI — both have a global `WebSocket`.
- **ADR-0011 (git as the hand-off)** — research tables are a rebuildable copy of git; app tables live only in the database. This is what the import enforces.
- **ADR-0025 (Drizzle on Neon's serverless driver)** — HTTP for queries, the WebSocket `Pool` (`drizzle-orm/neon-serverless` over `@neondatabase/serverless`'s `Pool`) for interactive transactions; the connection belongs in `web/lib/db.ts`. The import needs real per-commit transactions, which `drizzle-orm/neon-http` cannot do, so the transactional client is that WebSocket `Pool`, exposed next to `db()` (see Approach).
- **ROADMAP entry + task 007 result** — `web/db/schema.ts` and the migrations define every table this import writes; the `imports` table exists with no sequence column; the db tests run under `npm run test:db` (`web/scripts/neon-branch.mjs`, `vitest.db.config.mts`, `NEON_TEST_BRANCH_ID` guard) and refuse to run anywhere else. H02 (`DATABASE_URL` Actions secret) gates 009, not this task.
- **The repo's own research files (sampled)** — `data/snapshots/2026-10-29T0907.json`, `analysis/zetwerk.json`, `analysis/zetwerk.md`, `reports/2026-10-13-am.json`, `reports/2026-10-29-pm.json`, `data/outcomes.json`; a routine commit touches `data/latest.*`, one snapshot, and `reports/<date>-am.{html,json,txt}`. No current file carries `ai_*` fields yet (task 004's fields are optional and the guard accepts both) and none has `"generated": "quiet"` yet, but `ipo_agent/quiet.py` writes both (`quiet.py:169`). Report entries can lack `verdict` (the card's call holds) and can carry full card fields (`summary`, `financials`, `quota`, `positives`, …) that must go to `ipo_verdicts.overrides`, per db.md's mapping. `subscription`, `nse` and `categories` can be missing or null. Phases and some numeric fields are null on early snapshots. Six committed snapshots (2026-10-21T09:07 through 2026-10-23T19:08) carry a `shareholder` subscription category — `ipo_agent/nse.py:71` emits it — and **today's `sub_category` enum has no such value**, so the import would fail on them unless the enum grows.
- **The repo's git history** — main has merge commits (`c12d599`, `ce583d0`, …); `git show --name-only --format=` on a merge lists only conflicted paths, and `git log --reverse <from>..HEAD` yields side-branch commits in date order (e.g. the IPO brief `77b5ed5` reached main through a merge). Cards, reports and outcomes are modified after first write (12 committing commits). Exactly one research-file deletion exists: `c09248d` deleted `reports/2026-10-12-pm.md` — an ignored kind (`.md`), so no mapped row is affected. Today HEAD holds 35 snapshots (277 IPO entries), 13 cards, 13 analyses + 13 RHP texts, and 27 report sessions, 8 outcomes (as of 2026-10-30) — and the routine adds two runs a weekday, so the tests must derive counts from the repo at run time, never hard-code them.
- **ai.md § Guardrails / provenance** — the three fields' names and that they are checked when present, absent otherwise: exactly what the import copies.
- **`.claude/hooks/test_guard.py`-style fixtures** — precedent for tiny hand-built JSON when a property (here: `ai_*` in cards and reports, `generated: quiet` in reports) exists in no committed file yet.

## Approach

**Where it lives and how it runs.** The import is TypeScript in `web/` (ADR-0002 binds only `ipo_agent/`; tech.md puts the database work in `web/`). The library modules sit in `web/lib/import/`, the CLI entry in `web/scripts/import.ts`, run with `tsx` so aliases and TypeScript both work on the Node versions the project already requires. The transactional writer is Drizzle over Neon's WebSocket `Pool` — `drizzle-orm/neon-serverless` over `@neondatabase/serverless`'s `Pool` — on the pooled `DATABASE_URL`, exposed as a new `poolDb()` (plus `closePool()`) next to `db()` in `web/lib/db.ts`, exactly where ADR-0025 says the connection lives. Both packages are already installed. Node 22+ has a global `WebSocket`, so no `neonConfig.webSocketConstructor` override is needed. `pg` stays a devDependency, used only by the test harness. Schema definitions come from the existing `web/db/schema.ts` — one source of truth, no hand-written SQL.

**Two commands.**
- `npm run import` — default: an empty `imports` table or a history with no `ok` sha on the current first-parent chain runs the full rebuild; otherwise it imports the commits after the last `ok` row (or `npm run import -- --from <sha>`), **one transaction per commit**, then stops at the first failure. The CLI loads `web/.env.local` via `tsx --env-file-if-exists=.env.local` and exits with a clear message when `DATABASE_URL` is unset.
- `npm run import -- --rebuild` — in one transaction: delete the rows of the IPO research tables (child first), replay every research file in the repo, record HEAD as the imported commit.

**Which commits, and what changed in each.** `git rev-list --first-parent --reverse <from>..HEAD` lists the commits to import — only main's first-parent chain, so side-branch commits are never applied out of order and each merge appears once. Each commit's changed files come from `git diff --name-status --no-renames <sha>^1 <sha>` (the empty tree for the root commit); a classifier keeps only the paths that map to tables (`data/snapshots/<time>.json`, `analysis/<key>.json`, `analysis/<key>.md`, `reports/<date>-<am|pm>.json`, `data/outcomes.json`) and ignores `data/latest.*`, rendered email (`.html`, `.txt`) and later stock files. **Every file is read from the commit itself** — `git show <sha>:<path>` (batched with `git cat-file --batch` for the snapshot-heavy commits) — never from the working tree, so importing an old commit stores that commit's version under its own `imports` row, and a rebuild records HEAD while reading HEAD, immune to a dirty working tree. A deleted research file (status `D`) deletes the rows that file owns in the same transaction, child first — the database converges to exactly git in per-commit mode, matching the rebuild (documented in db.md, tested in the temp repo). Within the transaction the upserts run in foreign-key order: `ipos`, then snapshots + subscriptions, then cards and analyses, then reports + verdicts, then outcomes. The transaction also inserts the commit's `imports` row (`status ok`, `files`, `started_at`, `finished_at`), so the record is atomic with its data. A failed commit rolls back completely, records a `failed` row (with the error) in its own small transaction, and the run exits non-zero — the next run resumes from the last `ok`. Writing `ok` **upserts over an earlier `failed` row for the same sha** (`commit_sha` is the primary key), so a commit that failed once transiently imports on a later run. A commit that failed on its own content never changes — history is immutable — so once HEAD has moved past it the default command stops retrying it and runs the rebuild at HEAD instead (round-4 fix 13, below), logging why. Commits whose sha is already recorded `ok` are skipped, which makes re-runs free and re-importing twice give the same row counts.

**Last ok, exactly.** The table has no sequence column; the only sound order is git's: **last ok = the first sha in `git rev-list --first-parent HEAD` that has an `ok` row**. Commits to import are `git rev-list --first-parent --reverse <lastOk>..HEAD`. When the table is empty, or no `ok` sha is on the current first-parent history (rewritten history), the default command runs the rebuild — replaying ~190 commits one by one would let old versions of early files (phases and fields that later changed) fail today's validation and block imports for good. `--from <sha>` stays as the explicit override.

**Upsert semantics (db.md § Import and rebuild).** Snapshots and subscriptions are **insert-only, keyed by time**: `on conflict do nothing` on `(ipo_key, taken_at)` / `(ipo_key, taken_at, category)`. Cards, analyses, outcomes, reports, verdicts and `ipos` are **replaced on their natural keys** (`on conflict do update`). `ipo_analyses` computes `content_sha` (sha256 of the markdown) and skips the update when the stored hash matches — the "skip unchanged content" from the task. `ipos` facts are merged, not blindly overwritten: the update maps only the **fields present in the snapshot entry — key present and non-null** — so a later snapshot that lacks NSE data cannot blank previously imported facts; the documented flip side is that a field which later becomes null keeps its old value (a rebuild reproduces the same rows either way). The mapping covers every `ipos` column the snapshot carries: `price` → `price_high`, `nse.price_low` → `price_low`, `nse.symbol` → `symbol`, `rhp_url` → `rhp_url`, `rhp_source` → `rhp_source` (`nse`/`sebi`/null), `url` → `investorgain_url`, `anchor_done` → `anchor_done`, and the rest per db.md — db.md's table gains the four missing rows. `ipos.updated_at` is the **`generated_at` of the snapshot that last updated the row**, never `now()`, so a rebuild gives identical rows. On rebuild, snapshot files replay **chronologically** (their `YYYY-MM-DDTHHMM` names sort that way), so the newest merged facts win. `reports.commit_sha` is "the last commit that changed the file": the commit being imported in per-commit mode, `git log -1 --format=%H -- <path>` in rebuild mode — db.md's "the commit that added it" is reworded to match. `source_file` is the repo-relative path (`data/snapshots/2026-10-29T0907.json`, `analysis/<key>.json`, `reports/<date>-<am|pm>.json`), as db.md notes. `taken_at` comes verbatim from `generated_at` (an ISO time with offset — `timestamptz`, shown in IST later). Numbers come from the files as-is: the import computes none (rule 1).

**Data-quality handling.** Enum-valued and typed columns (phase, verdict, anchor grade, source, session, category, numerics, dates) are validated against the schema's enums before insert; an invalid or malformed file fails that commit's transaction, is recorded `failed` with the error, and blocks the incremental import until HEAD moves on — after which the default command rebuilds at HEAD (round-4 fix 13, below) instead of retrying the immutable commit forever. Missing fields map to null (`not found`, never an estimate). Report entries without a `verdict` insert null (`coalesce(verdict, card.verdict)` in the app), any report field outside `{verdict, verdict_text, best_category, category_note}` goes into `ipo_verdicts.overrides`, and a report with `"generated": "quiet"` maps to `quiet = true` with `carried_from` kept and null provenance — exactly as db.md's mapping row says, and as `quiet.py:169` writes.

**Rebuild boundary.** The rebuild deletes and replays the IPO research tables this import owns: `ipo_subscriptions`, `ipo_snapshots`, `ipo_verdicts`, `reports`, `ipo_cards`, `ipo_analyses`, `ipo_outcomes`, `ipos`. It does **not** touch the stock research tables in this task — `data/stocks/` is out of scope, so 008's import owns no stock source yet; 015/018 extend both the import and the rebuild's table list. (Plain `DELETE`s in child-first order inside one transaction, not `TRUNCATE ... CASCADE`: cascade would pull in `stocks` → `watchlist_items` and break the "leave app tables alone" guarantee. `DELETE FROM ipos` fails only if a `stocks` row references an IPO key, and no stock rows exist until 015/018 do their rebuild planning.) App tables (`users`, `watchlist_items`, `analysis_jobs`/`events`/`requests`, `ai_questions`, `settings`) are never touched by either command. Each import and rebuild transaction starts with `pg_advisory_xact_lock(<fixed constant>)` — a cheap serialisation guard so a local run and the Action (009) can't interleave.

**Decided 2026-10-30 (human).** Two decisions from the plan review are settled, and this task builds them:
1. **`shareholder` subscription category** joins the `sub_category` enum, through a new generated migration (`web/db/schema.ts` + `drizzle-kit generate`, the generated file committed untouched). Six committed snapshot entries carry it and dropping them would lose data git holds (rule 9).
2. **tsx** as the CLI runner, a devDependency, installed by the human before the build.

No other Open or Proposed item touches 008 (see Decisions needed).

**Why tsx, and the fallback.** Running TypeScript from the CLI needs a runner; Node 22.22/24.x cannot resolve the `@/` path aliases that `web/lib/db.ts` uses. `tsx` (small, standard, already the ecosystem default) avoids a compile step and version-sensitive strip-types flags. Fallback if the human prefers no new package: the same modules run through the existing Vitest harness and a plain-Node entry with `--experimental-strip-types` + `allowImportingTsExtensions`, but tsx is the planned choice (decided 2026-10-30). It is a devDependency, so the GitHub Actions runner (009) gets it from `npm ci`.

## Steps

| # | Step | Files | Test that proves it |
| --- | --- | --- | --- |
| 1 | **Packages and scripts.** Add `tsx` as a devDependency in `web/package.json`; add npm scripts `import` (`tsx --env-file-if-exists=.env.local scripts/import.ts`) and `import:rebuild` (`tsx --env-file-if-exists=.env.local scripts/import.ts --rebuild`) — the flag loads `web/.env.local` (locally written by `neon checkout dev`); CI and the Action (009) set `DATABASE_URL` in the environment instead. **Setup before the build:** the human runs `npm install` in `web/` once (regenerates the lockfile; `/run-task` stops for this, AGENTS.md § Building) | `web/package.json`, `web/package-lock.json` (via `npm install`) | `npm run typecheck` and `npm test` still pass with the new scripts present |
| 2 | **The decided `shareholder` migration.** Add `"shareholder"` to `subCategory` in `web/db/schema.ts`, run `npx drizzle-kit generate`, and commit the new generated migration (`0003_*.sql`) untouched (db.md § Migrations); update db.md's `sub_category` enum row | `web/db/schema.ts`, `web/db/migrations/0003_*.sql` (generated), `docs/db.md` | The db suite's schema-shape test (`web/tests/db/schema-shape.test.ts`) asserts the `sub_category` enum's values — it now expects `shareholder`; the parser test maps a snapshot's `shareholder` subscription to one `ipo_subscriptions` row. CI's schema-drift step stays green because the migration ships with the change |
| 3 | **Git helpers and the file classifier.** Repo-root discovery from `web/scripts` (no cwd dependence); `mainlineCommitsAfter(from)` via `git rev-list --first-parent --reverse <from>..HEAD`; `changedPaths(sha)` via `git diff --name-status --no-renames <sha>^1 <sha>` (empty tree for the root commit); `readFileAt(sha, path)` via `git show <sha>:<path>` (batched with `git cat-file --batch`); `listResearchFilesAtHead()` via `git ls-tree -r --name-only HEAD`; `lastCommitTouching(path)` via `git log -1 --format=%H -- <path>`; and `classifyResearchFile(path)` returning snapshot / card / analysis / report / outcome / ignore | `web/lib/import/git.ts`, `web/lib/import/files.ts` | `web/tests/import-git.test.ts` builds a throwaway git repo in a temp dir: it commits **copies of real repo files** (a snapshot, a card, a report, `data/outcomes.json`) across a few commits — including a modification, a side branch merged with `--no-ff`, and a deletion — then asserts the classifier on each commit's diff, that `mainlineCommitsAfter` skips the side-branch commit and orders the rest, that per-commit reads return each commit's own version of the file, and that the deletion shows status `D`. No pinned moving shas; the test works in CI's shallow clone because it never touches this repo's history |
| 4 | **Parsers.** One pure module per file kind, each returning Drizzle insert rows for `ipos` / `ipo_snapshots` / `ipo_subscriptions` (snapshot: the full mapping including `rhp_url`, `rhp_source`, `url` → `investorgain_url`, `anchor_done`), `ipo_cards` (card), `ipo_analyses` (analysis, with `content_sha` and `rhp_text_path`), `reports` + `ipo_verdicts` (report, with `overrides` for the extra fields and `quiet`/`carried_from`), and `ipo_outcomes` (outcomes). Enum validation against the schema's enums; numbers, dates and times passed through verbatim; the `ai_*` fields copied when the file carries them | `web/lib/import/snapshot.ts`, `card.ts`, `analysis.ts`, `report.ts`, `outcomes.ts` | `web/tests/import-parsers.test.ts`: real files (`data/snapshots/2026-10-29T0907.json`, `data/snapshots/2026-10-23T1908.json` — the one with `shareholder` — `analysis/zetwerk.json`, `analysis/zetwerk.md`, `reports/2026-10-13-am.json` — verdicts plus `overrides` — and `reports/2026-10-29-pm.json` — an entry with no `verdict`, and `data/outcomes.json`) map to the expected rows: spot-checked typed values, a `shareholder` subscription row, nulls where a file lacks a field, empty subscription/categories handled; a synthetic card and report carrying `ai_model`/`ai_prompt_version`/`ai_written_at` map them, and one without yields null; a synthetic quiet report shaped like `quiet.py`'s output (`"generated": "quiet"`, `carried_from`, no provenance) maps to `quiet = true` with `carried_from` kept and null `ai_*`, while a normal report maps to `quiet = false`; an unknown phase or verdict value throws; `content_sha` is a stable 64-hex sha256 |
| 5 | **Apply layer and CLI.** `log.ts`: last-ok lookup as first `ok` sha on the first-parent chain, ok/failed row writes with the ok write upserting over `failed`. `apply.ts`: per-commit upserts in FK order inside one WebSocket-`Pool` transaction (`poolDb()` from `web/lib/db.ts`), insert-only snapshots/subscriptions, content-sha skip, `ipos` merge on present-and-non-null fields with `updated_at` = the updating snapshot's `generated_at`, deleted-file rows removed child-first, `reports.commit_sha`; `rebuild()` deletes the eight IPO research tables (child first), replays every file `git ls-tree -r --name-only HEAD` returns — read from HEAD — and records HEAD in one transaction; every transaction starts with `pg_advisory_xact_lock(<constant>)`. `run.ts` + `web/scripts/import.ts`: resolve the range (default = last-ok → commits after it, or rebuild when nothing to resume from; `--from <sha>`; `--rebuild`), one transaction per commit, stop and exit non-zero on the first failed commit, exit with a clear `DATABASE_URL is not set` message when the variable is missing, print a short summary per commit and at the end | `web/lib/import/log.ts`, `web/lib/import/apply.ts`, `web/lib/import/run.ts`, `web/scripts/import.ts`, `web/lib/db.ts` (`poolDb`/`closePool`) | `web/tests/db/import.test.ts`, run by `npm run test:db` on a real Neon branch: (a) `--rebuild` twice gives identical per-table row counts, derived from the repo's own files at run time (one `ipo_snapshots` row per snapshot entry, etc.); (b) app rows — a `users` row, a `settings` row, and a watchlist item on a standalone `stocks` row — survive a rebuild; (c) in the **temp repo**, one commit adds a good snapshot and a malformed card: the commit leaves no rows (not even from the good file), records one `failed` row with the error, and the run exits non-zero; then a fix commit makes the next run import both commits' data and turn the row `ok` (the upsert over `failed`); (d) a deleted report file's rows (report + its verdicts) are gone after its commit, while `ipos` facts survive; (e) re-running an already-imported range changes nothing; (f) spot-checks: one known snapshot's `gmp`/`taken_at`/`source_file`, zetwerk's card row and verdict, the AM report's `overrides`, outcomes' `sub_retail`, and `ipo_analyses.content_sha` + `rhp_text_path`; (g) an unchanged `ipo_analyses` is not rewritten (hash equal). No `reports.commit_sha` assertion against the real checkout — a shallow clone gives the graft commit (Risks) |
| 6 | **Docs and status labels.** Mark db.md § Import and rebuild **Running** with the commands, the first-parent walk, the WebSocket-`Pool` driver, per-commit reads, the deleted-file policy, teardown-by-delete and the stock-table boundary; add the four `ipos` mapping rows, the `shareholder` enum row, `updated_at` semantics, the "present" definition, and the `reports.commit_sha` rewording; tech.md repository layout, web-platform table and local setup gain the import script and its `npm run import` commands; arch.md § 4.3 notes the script is Running while the Action stays Decided (009). List the roadmap changes to make after merge | `docs/db.md`, `docs/tech.md`, `docs/arch.md` | `npm run typecheck && npm test` still pass; reviewer checks the docs' commands and mapping table against the built script |

## Data and AI

- **Tables written:** `ipos`, `ipo_snapshots`, `ipo_subscriptions`, `ipo_cards`, `ipo_analyses`, `reports`, `ipo_verdicts`, `ipo_outcomes` (research, from git); `imports` (bookkeeping). **Tables read:** `imports` only. One schema change: the `shareholder` enum value and its generated migration (decided 2026-10-30). No other table or column changes; no other migrations.
- **Settings read:** none (no quotas or caps apply to an import run).
- **AI calls:** none — this script never calls an AI provider. It only copies the provenance columns (`ai_model`, `ai_prompt_version`, `ai_written_at`) from card and report files when present, and stores null on legacy files; `ipo_analyses` provenance awaits the `.md` marker that 020/021 define (db.md says so today).
- **Numbers:** every number in the rows comes verbatim from the files (snapshot prices, GMP, odds, subscription, outcomes); the import computes nothing — it does not even compute the track record (that is 012).

## Doc updates

- **`docs/db.md`** — § Where the data comes from: add the four missing mapping rows (`rhp_url` → `ipos.rhp_url`, `rhp_source` → `ipos.rhp_source`, `url` → `ipos.investorgain_url`, `anchor_done` → `ipos.anchor_done`); note `generated: "quiet"` → `quiet = true` already there is expanded with `carried_from`. § Enums: `sub_category` gains `shareholder`. § `ipos`: note `updated_at` is set from the last updating snapshot's `generated_at`, and that "present" for the merge means key present and non-null (a field that later becomes null keeps its old value). § `reports`: `commit_sha` is "the last commit that changed the file" (the imported commit per commit; `git log -1` on the path in rebuild), reworded from "the commit that added it". § Import and rebuild: label **Running**; add the two commands, the tsx + WebSocket-`Pool` runner and driver, the first-parent walk with per-commit diffs and per-commit reads, the last-ok definition and the rebuild-when-nothing-to-resume rule, the failed→ok upsert retry, the deleted-file policy (a deleted research file's rows are deleted with it, child first; the routine never deletes, so this is history-curation only), the delete-not-truncate rebuild and its boundary (stock research tables join in 015/018), and that analyses provenance arrives with 020/021. § Migrations and environments: the "seed data" note can point at the import as the path that fills the database from the repo.
- **`docs/tech.md`** — repository layout: the `web/` row names `web/lib/import/` and `web/scripts/import.ts` as built; the web-platform table gains an import-script row (Running); local setup gains `npm run import` and `npm run import -- --rebuild` (which load `web/.env.local`). No new environment variables.
- **`docs/arch.md`** — § 4.3: one line that the import script is Running (task 008) while the Action that triggers it stays Decided (task 009); no other flow changes.
- **Roadmap changes after merge (human or Claude, on `main`):** mark 008 **Done**. 009 stays **Blocked**: its remaining dependency is H02 (the `DATABASE_URL` Actions secret) — once that lands, 009 becomes Ready, and its plan must give the Action `fetch-depth: 0` and `DATABASE_URL` (Risks). No new tasks: 015/018 extending the import and the rebuild list to `data/stocks/` was already their scope.

## Decisions needed

None. The two decisions this plan needed were settled by the human on 2026-10-30 and recorded in the round-1 review: **tsx** as the CLI runner, and **`shareholder`** added to `sub_category` through a generated migration. D01–D07, D09 are decided; D08, D10–D13 and G1 don't touch the import (no settings rows are read or written, no AI, no cap). The transactional driver follows ADR-0025 (the WebSocket `Pool`), which is not an open choice.

## Risks and rollback

- **Setup before the build (human):** `npm install` in `web/` for `tsx` (new devDependency). The driver stops and asks; Claude confirms with the human.
- **Runner fallback:** if tsx is refused, the same modules run through Vitest (tests unaffected) and the CLI entry is a plain-Node file using `--experimental-strip-types` (flag on Node 22.22, default on Node 23.6+/24) — noted so the plan survives the decision; tsx remains the planned choice (decided 2026-10-30).
- **Persistent bad file blocks imports.** A file that fails validation fails its commit every time, so the incremental import stops there. History is never rewritten, so this could block every later commit forever. Round-4 fix 13 changed that: when the first commit to import already has a `failed` row and HEAD is a newer commit, the default command runs the rebuild at HEAD instead of retrying it, logging why — HEAD's tree holds the fixed files. A commit that fails for the first time, or one that is HEAD itself, still retries, so transient failures behave the same; the `ok` write upserts over that commit's earlier `failed` row (tested, test c). A rebuild that throws records a `failed` row for HEAD in its own small transaction, like a failed commit (tested, test k). Rollback for a bad import: the rebuild is now automatic once HEAD moves on — or `npm run import -- --rebuild` / `-- --from <good-sha>` by hand.
- **Force-pushed or rewritten history.** The last `ok` sha may leave the new history. The default command then runs the **rebuild** (HEAD's files, one transaction) instead of replaying ~190 commits whose early file versions may fail today's validation. Upserts replace, insert-only keys no-op, `content_sha` skips — counts stay stable (the "twice, same counts" guarantee holds).
- **Shallow clones (CI, the Action).** Both CI jobs check out with `fetch-depth: 1`, so the git-layer tests cannot depend on this repo's history and don't assert `reports.commit_sha` against the real checkout (the graft commit). The temp-repo tests and the `git ls-tree HEAD`-based rebuild work in a shallow clone. **009's Action needs `fetch-depth: 0`** for the first-parent walk and per-commit reads; noted in Doc updates for 009.
- **FK edges.** A verdict/card/outcome for an IPO whose `ipos` row is not yet imported fails that commit (in practice every report IPO appears in the same run's snapshot); deleting a file's rows is child-first, so it can't hit a referenced row; `DELETE FROM ipos` fails only once `stocks` rows reference an IPO (impossible before 015/018; their rebuild work inherits the boundary noted in db.md).
- **Concurrency.** A local run overlapping the Action (009) is serialised by `pg_advisory_xact_lock(<constant>)` at the start of each import/rebuild transaction; the script is race-safe beyond that because it resumes from the last `ok` and skips already-recorded commits.
- **Neon free tier.** A paused project makes the first connection slow (accepted, arch § 7.2); the import is a handful of small statements per commit, far inside the free tier; the db test run already provisions and deletes a branch per run.
- **Rollback of the change itself:** 008 adds one migration (an enum value, reversible by a later migration or by re-running the schema build) and changes no existing table; undoing is `git revert` of the task branch. A wrong import is undone by re-importing (commands above), not by surgery.

## Revisions

| Round | What changed | In answer to |
| --- | --- | --- |
| 1 | Recorded the two human decisions (2026-10-30) in the Approach: `shareholder` joins `sub_category` through a new generated migration (new step 2, with schema-shape and parser tests), and tsx stays the only package change. Swapped the transactional driver from `drizzle-orm/node-postgres`/`pg` to Neon's WebSocket `Pool` (`drizzle-orm/neon-serverless`) exposed as `poolDb()` next to `db()` in `web/lib/db.ts`; `pg` stays a devDependency; the "no migrations" lines and ADR-0025 reading are corrected. Per-commit and rebuild now read files from git (the commit, or `git ls-tree HEAD`), never the working tree. The commit walk is now first-parent (`git rev-list --first-parent --reverse`) with per-commit diffs against the first parent (empty tree for the root), and a defined deleted-file policy (a deleted file's rows go with it, child first). "Last ok" is defined as the first `ok` sha on the first-parent chain; empty `imports` or a history without one runs the rebuild; an `ok` write upserts over `failed` for the same sha. The `ipos` mapping now covers `rhp_url`, `rhp_source`, `url` → `investorgain_url` and `anchor_done`; `updated_at` is the last updating snapshot's `generated_at`; "present" means key present and non-null. Git tests build a throwaway temp repo from copies of real files (no pinned shas, shallow-clone safe); a quiet-report fixture test was added; the failure test (c) now uses the temp repo (bad commit → fix → next run turns the row ok). The CLI loads `DATABASE_URL` via `tsx --env-file-if-exists=.env.local` and exits clearly when unset. Added the advisory lock, the 009 `fetch-depth: 0` note, and the reworded `reports.commit_sha` doc line; counts refreshed to HEAD (35 snapshots / 277 entries, 13 cards, 27 reports, 8 outcomes) | Items 1–10 and the notes |

## Changes during build

Anything built differently from the approved plan, and why.

1. **Test (c)'s retry seam.** The plan's literal scenario — a bad commit, then "a fix commit makes the next run import both commits' data and turn the row ok" — cannot work with per-commit immutable reads (a fix commit on top leaves the bad commit's own tree invalid, and the plan itself documents that a bad file "blocks until the file is fixed **(or history rewritten)**"). The db test therefore fixes the commit by rewriting it (`git commit --amend`, the plan's documented recovery), and inserts a synthetic `failed` row for the *fixed* sha to simulate the transient first-attempt failure, so the next run's `ok` write genuinely upserts over a `failed` row for the same sha through the real CLI path. The mechanism the plan names — failed row → re-attempt → ok upserts over failed, same sha — is exercised end-to-end; only the setup differs.
2. **The no-verdict report fixture.** The plan names `reports/2026-10-29-pm.json` as "an entry with no `verdict`", but at HEAD every entry of that file carries one. The no-verdict path is covered instead with a synthetic fixture in the exact shape of `reports/2026-10-19-am.json`'s tonbo-imaging entry (which at HEAD really has no verdict), plus an assertion that every committed report parses to one verdict row per entry.
3. **Test (b) asserts the seeded `settings` rows survive, not a new one.** The schema-rules db suite asserts `settings` has *exactly* the three seed rows, and db test files run in parallel on the same branch, so inserting a new row would make that suite flaky. A `users` row and a watchlist item on a standalone `stocks` row are still inserted and asserted; the settings coverage is a read + equality check of the seeded rows.
4. **Test (a)'s expected counts are computed by raw JSON parsing** of the repo's own files (distinct keys, entry/subscription/report-entry counts), not by reusing the import's parsers — reusing them would make the "same counts" check a tautology.
5. **Replaced tables null their absent fields.** The plan says cards, analyses, outcomes, reports and verdicts are "replaced on their natural keys"; the build implements "replaced" as: the update also nulls the table's nullable columns the file no longer carries (`ipos` alone keeps the present-and-non-null merge). This is what makes per-commit and rebuild converge to exactly the file state, and is documented in db.md § Import and rebuild.
6. **Review round 1 fixes.** The respond step changed how the parsers build rows and how the apply layer orders and trims them:
   - Timestamps are converted to `Date` at the parser boundary (`maybeDate`, which throws on an unparseable value), and numerics are passed as `string` — the rows are built with each table's real insert type instead of `Loose<T>` plus casts, which is what let the timestamp bug through. A stricter parse-time error also replaced the insert-time not-null failure for a snapshot entry missing `phase`.
   - A commit's changes are applied in FK order (deletions first, then snapshot → card → analysis → report → outcome) instead of `git diff`'s path order — this is the plan's own "foreign-key order" promise, which the first build did not keep.
   - An edited report or `data/outcomes.json` drops the entries the new version no longer carries (leftover verdicts/outcomes), which the plan's convergence claim needed; skipped empty snapshot/subscription inserts let the 10 no-subscription snapshots import.
   - `--from`/`--root` without a value exit with usage (code 2) instead of silently running the default command.
8. **Review round 3: batched upserts and timeouts (finding 12).** A whole-repo rebuild ran ~110 s on CI because every verdict and outcome row was its own awaited statement over the WebSocket, plus a `git log` process per file for `reports.commit_sha`; test (a)'s two rebuilds hit the 180 s timeout and kept the `db` job red. `applyFile` now upserts a whole report's verdicts in one statement and the whole of `data/outcomes.json` in one — a new `commonReplacedSet` builds the per-conflicting-row SET (`excluded.<col>`, with nulls for columns no row carries and `coalesce` for a NOT NULL column some rows carry) that the per-row `replacedSet` it replaces produced, exactly — and `rebuild` gets every path's last commit from one `git log --name-only` pass (`lastCommitsTouching`) instead of a process per file. `ipos` deliberately stays one statement per row: a common `coalesce(excluded.<col>, ipos.<col>)` SET cannot preserve the present-and-non-null merge for `anchor_done` — Drizzle fills a column a row lacks with the SQL `default` keyword, so the excluded value is the column's *evaluated default* (`false`), not null, and a later snapshot entry carrying `anchor_done: null` (common in the repo's files) would silently reset a true value. "Keep old when absent" for a NOT NULL defaulted column is inexpressible in one `INSERT ... ON CONFLICT` statement; an INSERT batch + UPDATE-from-VALUES merge would batch it exactly, and that stays a finding-11 follow-up. Tests (a) and (b) — the two that run whole-repo rebuilds — get 600 s timeouts (a few times even the old per-rebuild figure, with headroom for the twice-weekly growth), and the measured per-rebuild time is pasted into Verification from CI's next run.
9. **Review round 4: a failed commit no longer blocks the import for good (finding 13).** The approved plan said a bad file's commit "blocks until the file is fixed (or the history rewritten)"; with per-commit immutable reads and history never rewritten, that blocked every later commit forever until a hand-run rebuild. The default command now checks, before retrying, whether the first commit to import already has a `failed` row while HEAD is a newer commit — if so it logs "commit X failed before; HEAD has moved on, so rebuilding from HEAD" and runs the rebuild at HEAD, whose tree holds the fixed files. A commit that fails for the first time, or one that is HEAD itself, still retries exactly as before (transient failures behave the same; test (c) still covers the ok-over-failed upsert). New db tests: (j) commit B has a malformed card (failed row for B), commit C fixes it on top without rewriting history, and the next default run succeeds — C's card and B's good snapshot are both in the database and HEAD (C) has an `ok` row; (k) a rebuild that throws records a `failed` row for HEAD with the error in its own small transaction (`rebuildRecordingFailure` in `run.ts`), like a failed commit. `log.ts` gains `failedCommitShas`; db.md's "blocks until the file is fixed" claims (the `imports` section and the Failure-and-retry bullet) are corrected to the fallback.

## Verification

Test commands run by the respond steps (after review rounds 1 and 2), with their output pasted.

**Offline suite** (`npm test` — 6 files, 57 tests, all green; the db suite is excluded by design; rerun unchanged in the round-2 respond step):

```text
> test
> vitest run

 ✓ tests/env-example.test.ts (2 tests) 2ms
 ✓ tests/neon-branch.test.ts (14 tests) 4ms
 ✓ tests/layout.test.tsx (5 tests) 60ms
 ✓ tests/schema.test.ts (4 tests) 2ms
 ✓ tests/import-parsers.test.ts (17 tests) 21ms
 ✓ tests/import-git.test.ts (15 tests) 384ms

 Test Files  6 passed (6)
      Tests  57 passed (57)
```

**Type check** (`npm run typecheck` — clean, including the round-2 test edits):

```text
> typecheck
> tsc --noEmit
```

**Lint** (`npm run lint` — 0 warnings, 0 errors, 40 files):

```text
> lint
> oxlint --deny-warnings

Found 0 warnings and 0 errors.
```

**Schema drift** (`npx drizzle-kit generate` is a no-op after step 2's migration — required by CI's `web` job):

```text
No schema changes, nothing to migrate 😴
```

**Parser run over every committed file** (the closest offline proxy for the db suite's whole-repo import: parse all 373 committed files with the built parsers — 277 snapshot rows, 13 cards, 13 analyses, 27 reports, 8 outcome rows — zero failures):

```text
parsed OK across 373 committed files: snapshot-rows=277 cards=13 analyses=13 reports=27 outcome-rows=8 failures=0
```

**Round-2 respond step: raw-counts sanity check** (finding 8's fix read against the repo's own files — every snapshot and report parses as JSON, and the counts match the parser run above; verdicts/cards/analyses/reports/outcomes are derived at run time in the test, never hard-coded):

```text
{"ipos":13,"snapshots":277,"subscriptions":513,"cards":13,"analyses":13,"reports":27,"verdicts":143,"outcomes":8}
```

**Python suite** (`python3 -m unittest discover -s tests` — unchanged by this step, which touches only `web/`):

```text
Ran 330 tests in 0.568s
OK
```

**CLI smoke tests** (`npx --no-install tsx scripts/import.ts`):

```text
$ npx --no-install tsx scripts/import.ts --help
usage: tsx scripts/import.ts [--rebuild] [--from <sha>] [--root <repo>]
  (default)  import the commits after the last ok row, one transaction each;
             an empty imports table or rewritten history runs the rebuild
  --rebuild  empty the IPO research tables and replay every research file at HEAD
  --from     import only the commits after <sha>, instead of the last ok row
  --root     the repo to import (default: the checkout containing web/scripts)

$ npx --no-install tsx scripts/import.ts --from        # no value → usage, exit 2
--from needs a value
usage: ... (as above)

$ npx --no-install tsx scripts/import.ts --rebuild --root /tmp
DATABASE_URL is not set: the npm scripts load web/.env.local (write it with
`neon checkout dev` in web/); CI and the import Action set the variable instead.
```

**Database suite** (`npm run test:db` — `web/tests/db/import.test.ts` plus the existing schema tests). Still cannot run in this environment: the harness refuses without the Neon secrets, exactly as designed. The refusal itself:

```text
> npm run test:db
> node scripts/neon-branch.mjs

test:db needs NEON_API_KEY and NEON_PROJECT_ID (CI secrets, H06). Refusing to run without them —
the db tests must never touch the `dev` branch by accident.
```

Round 1's CI `db` job caught the three blockers the first respond step fixed (findings 1–3) — the code side is green (rebuild, retry, re-run, spot-checks all pass — run transcript in code-review.md). Round 2's CI run (code-review.md) found five failures, all test bugs; the second respond step fixed them in `web/tests/db/import.test.ts`, none in the library:

- (8) `expectedResearchCounts` no longer `JSON.parse`s the analysis `.md` files (their `---` front matter threw), so test (a)'s "twice, same counts" check compares real numbers — verified offline above (277 snapshot rows, 13 distinct IPOs, 513 subscriptions, 13 cards, 13 analyses, 27 reports, 143 verdicts, 8 outcomes).
- (9) the temp-repo tests now start from an empty research database: a `beforeEach` deletes the eight research tables child first plus `imports`, so tests (d), (g), (h) and (i)'s absolute counts (`is(1)`, `is(2)`) no longer see the whole-repo rebuild's rows (27 reports, 141 verdicts, 13 cards). App tables are left alone (schema-rules runs in parallel).
- (10) test (g) filters its final select on `ipo_key` and now actually exercises the content-sha skip: it deletes commit a's `imports` row and re-imports, so `applyFile` re-runs on the same `.md` (a 0-commit run re-applies nothing) and the assertion checks the row's `xmin` did not move.

Claude pushes this branch after the respond step so the `db` job re-runs, and pastes the run result into the next review round.

**Round-3 respond step (finding 12 — the batching).** Everything runnable here, after the verdict/outcome batching and the single-pass `commit_sha` lookup:

```text
$ npm test
 Test Files  7 passed (7)          # +2: import-apply (3), lastCommitsTouching (2)
      Tests  62 passed (62)        # was 57; the db suite stays excluded
$ npm run typecheck                # clean
$ npm run lint                     # Found 0 warnings and 0 errors (41 files)
$ npx --no-install drizzle-kit generate
No schema changes, nothing to migrate 😴
$ python3 -m unittest discover -s tests
Ran 330 tests in 0.561s
OK
```

The rebuild's statement count drops from ~550 awaited statements to ~430 — a whole report's verdicts (143 rows across 27 reports) upsert in one statement, `data/outcomes.json`'s rows in one, and one `git log --name-only` pass replaces 54 `git log -1` processes. `ipos` stays one statement per row (why, in Changes during build 8). Tests (a) and (b) now allow 600 s. The suite's tests: (a) rebuild twice → identical counts matching the repo's files, (b) app rows survive, (c) bad commit leaves no rows + failed-row upsert retry, (d) deleted report's rows go with it, (e) re-running a complete range changes nothing, (f) spot-checks of known rows, (g) an unchanged analysis is not rewritten (re-apply with unchanged content leaves its xmin alone), (h) an edit that drops an entry removes its rows and matches a rebuild, (i) one commit can first introduce an IPO with its card, analysis and report, plus the CLI value-flag check.

**Round-4 respond step (finding 14 — the measured db-suite run).** The human ran the db suite locally at `b3d76f3` on a throwaway Neon branch, and the whole run — including test (a)'s two whole-repo rebuilds and test (b)'s one — finished in 146.69 s, so a rebuild takes at most about 49 s from that machine, far inside the new 600 s timeouts. The runner's own figure belongs in the record with 009's first CI run:

```text
test:db using branch br-autumn-sun-a1leihog (db-test-1793333677153)
[✓] migrations applied successfully!
 RUN  v5.0.5 /Users/badjatya/Developer/IPO/.worktrees/008-import-script/web
 Test Files  4 passed (4)
      Tests  43 passed (43)
   Start at  09:44:52
   Duration  146.69s (tests 99%, import 1%)
test:db deleted branch br-autumn-sun-a1leihog
```

**Round-4 respond step (finding 13 — the failed-commit fallback).** Everything runnable here, after the default run learns to rebuild at HEAD when the first commit to import already failed and HEAD has moved on, and a failed rebuild records a `failed` row for HEAD:

```text
$ npm test                        Test Files 19 passed (19) · Tests 133 passed (133)
$ npm run typecheck               exit 0
$ npm run lint                    Found 0 warnings and 0 errors.
$ npx --no-install drizzle-kit generate
No schema changes, nothing to migrate 😴
$ python3 -m unittest discover -s tests
Ran 376 tests in 0.558s
OK
```

New db tests (j) and (k) cover the fallback and the failed-rebuild record; they can only run on a Neon branch, so CI's `db` job is their proof. The db suite at `b3d76f3` above predates them (43 tests); the next `db` run has 45.