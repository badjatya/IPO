---
task: 013-admin-settings
status: approved
branch: task/013-admin-settings
assigned_by: Vijay
planner: DeepSeek deepseek-v4-flash-0731 (OpenRouter)
reviewer: Claude Code
---

# 013: Admin settings page

## Task

> Task 013 from docs/tasks/ROADMAP.md:
>
> ### 013 · Admin settings page
>
> | | |
> | --- | --- |
> | Slug | `013-admin-settings` |
> | Status | Ready |
> | Depends on | 010 |
> | Owner | DeepSeek plans and builds |
> | Milestone | M1 |
>
> An admin-only page that lists the `settings` rows and edits one at a time. Each value is checked against the app's list of known keys and types, and `updated_by` and `updated_at` are recorded.
>
> - **Done when:** an admin can change a value; a bad value is refused; a non-admin gets 403; tests cover all three.
> - **From 010:** guard the page and its route with `requireAdmin` and `assertSameOrigin` from `web/lib/auth-guard.ts`; the app's own routes are outside Better Auth's origin check. The admin layout (`web/app/admin/layout.tsx`) already checks the session and role for every `/admin/*` page. The Neon tests' `api()` helper in `web/tests/db/auth.test.ts` shows how to sign in and send `Origin` in tests.
> - **Read:** [db.md § settings](../db.md#settings), [AGENTS.md](../../AGENTS.md) rule 6.
> - **Start:** `/run-task 013`

## Goal and scope

- **In scope:**
  - `web/lib/settings.ts` — the app's list of known settings keys and their types ([db.md § settings](../db.md#settings)): the four known keys (`ask_daily_limit_per_user` and `analysis_monthly_limit_per_user` and `analysis_daily_limit_platform` as integer ≥ 0, `analysis_refresh_after_days` as integer ≥ 1), plus one pure validator that every write path uses. This is the single registration point db.md describes ("New settings are added as new rows, plus an entry in the app's list of known keys"); the later readers (Ask limit, analysis quota, worker dispatch) import it too.
  - `GET /api/admin/settings` — the row list, admin-only: every `settings` row with its `description`, `updated_at`, `updated_by` and the updater's email (left join), ordered by key.
  - `POST /api/admin/settings` — edit one row only: `assertSameOrigin` → `requireAdmin` → validate the raw body against the known keys (a bad value is refused 400) → `UPDATE … SET value, updated_at = now(), updated_by = <admin id> WHERE key` → 404 when the row does not exist; returns the saved row. One request, one row; no bulk editing.
  - The page `web/app/admin/settings/page.tsx` — a client component under the already-guarded admin layout: lists the rows with their descriptions and current values, edits one at a time with a labelled number input per row, converts the input with `Number(...)` (an empty or non-numeric input is blocked before posting) and posts `{ key, value }` with `value` a JSON number, and shows the saved state or the server's error. A row whose key is not in `KNOWN_SETTINGS` renders read-only with a "not in the app's list of known keys" label and no input. Form elements follow the invite page's plain-labelled-input style (see Context read, design.md); the shadcn `Button` only.
  - Tests: validator unit tests, route tests with auth and db mocked, page tests with fetch mocked, and one Neon-branch block appended to `web/tests/db/auth.test.ts`. Doc updates that flip the feature to Running.
- **Out of scope:** creating a row for a known key that has no row (the D08 platform cap stays row-less and the gate stays closed until D08 decides); deleting rows; editing `description`; any settings *readers* (Ask limit, analysis quota, worker dispatch — tasks 018/022/023); an admin navigation header (the invite page stays as it is); touching the auth pages, the schema or the migrations; new packages, new environment variables, and any AI call.

## Context read

- **ROADMAP.md — 013 entry and the D08 row** — the done-when list this plan builds against: "an admin can change a value; a bad value is refused; a non-admin gets 403; tests cover all three." D08 (the platform-cap default) is open and unticked: the cap has no row by design, 013 does not need D08's number, and the gate stays closed ("while the row is missing the gate is closed") until D08 decides.
- **db.md — § settings and § Access patterns** — the table shape (`key` PK, `value` jsonb, `description` "Shown on the admin settings page", `updated_at`, `updated_by` "null for seeded values"); "the app checks every value against a list of known keys and their types before saving"; the seeded rows (5, 3, 30: integers ≥ 0, and `analysis_refresh_after_days` ≥ 1); "New settings are added as new rows, plus an entry in the app's list of known keys. No schema change is needed"; the access pattern "All rows of `settings`; update one row, setting `updated_by` and `updated_at`."
- **AGENTS.md rule 6** — quotas and caps come from the `settings` table; the page writes rows and never hard-codes a limit, a bound or a default (the known-key bounds are the type metadata from db.md's table, and the cap row is never created by code).
- **010's built code — auth-guard, the invite route, the admin layout, the proxy, the Neon suite** — `requireAdmin`/`assertSameOrigin`/`authErrorResponse` and the contract 010 left for this task ("013's settings route must call this too", `web/lib/auth-guard.ts`); the invite route's shape (same-origin first, then the role check, then work; AuthError → its status, `MailNotConfiguredError` → 500, else a generic 500); the admin layout as the authoritative page-side check, so the settings page itself carries no guard (the proxy's matcher already covers `/admin/*` and `/api/admin/*`); the invite page's raw-input admin form; `web/tests/db/auth.test.ts` — the `api()` helper, the session bootstrap (first-admin script → reset token → set password → sign in), the file-level `adminCookie`, why the rate-limit test must stay last, and how tests send cookies and `Origin` to app routes.
- **007's schema and tests (`web/db/schema.ts`, migration `0002`, `web/tests/db/schema-rules.test.ts`)** — the `settings` table already exists with exactly the db.md columns and the three seeded rows; jsonb numbers round-trip as JS numbers (the seed test asserts 5/3/30); 013 needs no schema change and no migration; the Neon harness gives every `npm run test:db` a fresh schema-only branch.
- **design.md — § Page elements** — the mapping "Sign-in, admin settings → `Input`, `Label`, `Button`" is Proposed and "the task that builds the page confirms or changes it"; this plan changes it to the plain labelled-input style the 010 admin pages already use (no `Input`/`Label` components exist in `web/components/ui/` and adding them would mean a human `npx shadcn add` step).
- **arch.md — § 4.4 Admin row and § 7** — the module table's Admin row ("Settings page (admin role only)… Edits [`settings`](db.md#settings): quotas and caps") is where the status label flips to Running; § 7.1's controls this task inherits (role check, same-origin check on the app's own routes); the cap gate in § 7.2.
- **tech.md and the web test setup** — no new environment variables: nothing to add to the config table or `web/.env.example` (the env-example test stays untouched); `npm test` (offline Vitest) versus `npm run test:db` (the Neon harness, run in CI's `db` job on every push); `web/tests/invite-route.test.ts` and `web/tests/admin-invite-page.test.tsx` as the mocking patterns this task copies (auth and db mocked; fetch mocked).

## Approach

- **One pure module owns the known keys and bounds; the database owns the human text.** `web/lib/settings.ts` exports `KNOWN_SETTINGS` — exactly the four keys and bounds of db.md's seeded-rows table — and `validateSettingValue(body)`, which checks the raw JSON body: the key must be known, and the value must be a JSON number that is a whole number at or above the key's bound (so `"5"`, `5.5`, `true`, `null` and `-1` are refused, and `0` is refused for `analysis_refresh_after_days`). It carries no descriptions: `description` is a DB column shown on the page, so the rows are the one source of text and this module the one source of validation. This is the "app's list of known keys" db.md's settings section describes; the reading tasks will import the same module.
- **The route is one file, two guarded handlers, in the invite route's shape.** `web/app/api/admin/settings/route.ts`: `GET` is read-only, so `requireAdmin` alone guards it (there is no state to forge with a GET); it returns every row, left-joined with `users` for the updater's email, ordered by key. `POST` runs the 010 order: `assertSameOrigin` first (the app's own routes are outside Better Auth's origin check — the exact contract left in auth-guard.ts), then `requireAdmin`, then parse the body (bad JSON → 400), validate (bad value → 400 with the validator's message), then `UPDATE settings SET value, updated_at, updated_by WHERE key` — 404 when no row matched, 200 with the saved row on success. AuthError → 401/403, anything else → 500, exactly like the invite route.
- **Update-only: the page lists the rows that exist and edits one at a time.** A known key with no row (today, only `analysis_daily_limit_platform`) is neither listed nor creatable — the Neon block's 404 test proves the row stays absent. Reasons: db.md's documented path for a new setting is "new rows, plus an entry in the app's list of known keys" — the D08 cap row is seeded once D08 decides, before the tasks that read it — and a row-less key has no `description` to show. This keeps the gate exactly as documented: closed until the row exists, and nothing in 013 can invent a default (rule 6). The alternative (letting the page upsert a value for any known key) would change how the D08 default lands — rejected for 013: db.md's path is the seed, and a row-less key has nothing to display; it can be added later if the human wants it. **D08 itself stays open (the ROADMAP's D08 row) but is not a decision this task needs**: 013 is update-only, no path in it depends on the number, the cap row simply stays absent, and nothing here may invent a default — the gate stays closed exactly as documented until D08 decides.
- **The page is a client component under the already-guarded admin layout; the done-when 403 is the API's.** 010 made the admin layout the authoritative page-side check for every `/admin/*` page, and the proxy's cookie check covers the URL, so the page itself only renders and posts. Where "a non-admin gets 403" happens is the API: `GET` and `POST /api/admin/settings` answer 403 (the route tests and the Neon block prove it). On the page path, 010's admin layout redirects a signed-in non-admin to `/` (a missing session goes to `/sign-in`) — it answers no 403, it is already covered by 010's layout tests, so the redirect is not a gap and this task adds no page guard. The page fetches `GET /api/admin/settings` on mount and renders one block per row (key, description, current value, "Changed by <email> on <date/time IST>", or "Seeded" when `updated_by` is null), with an inline form per row: a labelled number input (`min` from `KNOWN_SETTINGS`, `step 1`, required) and the shadcn `Button`. Saving reads the input and converts with `Number(...)` — the validator refuses the string `"5"`, so the page must post a real number — and an empty or non-numeric input is blocked before any POST; the POST body is exactly `{ key, value }` with `value` a JSON number, then the page shows the returned row (new value, updater, timestamp) or the server's error. A row whose key is not in `KNOWN_SETTINGS` (inserted by hand, or a key a later task's code drops) has no `min` and every save of it is a 400, so the page renders it read-only: value and description shown with a "not in the app's list of known keys" label and no input — GET returns every row, and the route already refuses the POST, so no route change is needed. Values come back as JSON numbers and are shown as entered — nothing is computed or estimated (rule 1). Styling follows the invite page and design.md's layout rules (`max-w-5xl` centred, tokens only); form elements are plain labelled inputs, the style the 010 admin pages already use, and design.md's row is updated accordingly — design.md says "the task that builds the page confirms or changes it", and the round-1 review confirmed the plain-input style, so no `npx shadcn add input label` step.
- **Tests in four layers.** (1) Pure validator tests — every key at its bound and above, and every refused shape. (2) Route tests with auth and db mocked (the invite-route pattern): the three done-when behaviours plus cross-origin, unknown-key, missing-row 404 and bad-JSON. (3) Page tests with fetch mocked (the invite-page pattern): rows render; a save posts exactly `{ key, value }` and the test asserts `typeof value === "number"`; an empty or non-numeric input never posts; an unknown-key row renders read-only with no input; a 400 shows the error and keeps the old value. (4) One Neon-branch describe block appended to `web/tests/db/auth.test.ts` — where the real session helpers already are — placed between the role-check test and the rate-limit test, which must stay last. **It adds no sign-in calls** — every `/api/auth/sign-in/email` call shares one bucket (10 per 15 minutes, no client IP, D11 open), the file already makes 7 of them before the rate-limit test, and one more would leave that test short of the 401 it must see before the 429. It reuses the file-level `adminCookie` and a file-level `userCookie` (minted by the role-check test, kept the way `adminCookie` is) and exercises the route end-to-end with a real admin session and real rows: change a value and prove `updated_by`/`updated_at`; refuse a bad value and prove the row unchanged; refuse a non-admin on both handlers; refuse a forged-Origin POST; 404 on the row-less cap and prove no row appears (gate stays closed).
- **No setup steps:** no new packages, no new shadcn components under the primary approach, no env vars, no migration — the build runs start to finish without the human.

## Steps

| # | Step | Files | Test that proves it |
| --- | --- | --- | --- |
| 1 | **Known keys and the validator.** `web/lib/settings.ts`: `KNOWN_SETTINGS` with the four keys of db.md's seeded-rows table (`ask_daily_limit_per_user`, `analysis_monthly_limit_per_user`, `analysis_daily_limit_platform` — integer ≥ 0; `analysis_refresh_after_days` — integer ≥ 1) and `validateSettingValue(body)`, which returns a typed success (the parsed key and number) or one concrete error message per failure (unknown key; not a number; not a whole number; below the bound). No descriptions in code. | `web/lib/settings.ts` | `web/tests/settings-validation.test.ts` — each key accepts its minimum and a larger integer; refuses `"5"`, `5.5`, `true`, `null`, objects, arrays, negatives, below-min integers and unknown keys, and each error message is asserted |
| 2 | **The API route.** `web/app/api/admin/settings/route.ts`: `GET` — `requireAdmin`, then all rows with the updater's email (left join `users`), ordered by key. `POST` — `assertSameOrigin` → `requireAdmin` → bad JSON 400 → `validateSettingValue` (bad value 400 with its message) → `UPDATE settings SET value, updated_at = now(), updated_by = <admin id> WHERE key` → no row matched 404, success 200 with the saved row. AuthError → 401/403; anything else → 500 (the invite route's shape). | `web/app/api/admin/settings/route.ts` | `web/tests/settings-route.test.ts` (auth and db mocked, invite-route pattern) — an admin POST writes the parsed value and the admin's id; a bad value, a bad body and an unknown key are 400 with no db write; a known key with no row is 404; a non-admin is 403 and a missing session 401 on both handlers; a forged-Origin POST is 403; GET returns the mocked rows |
| 3 | **The page.** `web/app/admin/settings/page.tsx` — client component (the admin layout already checks the session and role; done-when's "non-admin gets 403" is the API's — see Approach): fetches GET on mount; imports `KNOWN_SETTINGS`; one block per row (key, description, current value, "Changed by …" with an IST timestamp, "Seeded" when `updated_by` is null); a labelled number input per row (`min` from `KNOWN_SETTINGS`, `step 1`, required) with the shadcn `Button`; on save the page converts the input with `Number(...)`, blocks an empty or non-numeric input before posting, and posts exactly `{ key, value }` with `value` a JSON number; shows the returned row or the server's error. A row whose key is not in `KNOWN_SETTINGS` (hand-inserted, or a key a later task's code drops) is read-only — its value and description shown with a "not in the app's list of known keys" label and no input (every save of it would be a 400, so the page never offers one). Invite-page form style and tokens, `max-w-5xl` centred. | `web/app/admin/settings/page.tsx` | `web/tests/admin-settings-page.test.tsx` (fetch mocked, invite-page pattern) — the GET rows render with their values and descriptions (by label); editing a row posts exactly `{ key, value }` and the test asserts `typeof value === "number"`, then shows the updated value; an empty or non-numeric input never posts; a row with a key outside `KNOWN_SETTINGS` renders read-only with the "not known" label and no input; a 400 response shows the error and keeps the old value |
| 4 | **Neon-branch integration.** Append an "admin settings on a real branch" describe block to `web/tests/db/auth.test.ts`, **between the role-check test and the rate-limit test** (which must stay last — it drains the shared sign-in bucket). A small `settings()` helper calls the route's GET/POST with the session cookie (and `Origin` on POST), mirroring the file's `invite()`. **The block adds no sign-in calls:** every `/api/auth/sign-in/email` call shares one database bucket (10 per 15 minutes, no client IP — D11 open), the file already makes 7 calls before the rate-limit test, the rate-limit test must still see at least one 401 before the 429, and vitest runs files in parallel so a separate file would not help. It reuses the file-level `adminCookie` for all admin work, and `userCookie` — `let userCookie = ""` beside `adminCookie`, assigned by the existing role-check test, which already mints a non-admin session — for the non-admin 403 checks; `sql()` asserts `updated_by`/`updated_at`. No `invite()`, no reset token, no `signInCookie()` in the block. | `web/tests/db/auth.test.ts` | `npm run test:db` passes (CI's `db` job on every push; locally when the `NEON_API_KEY`/`NEON_PROJECT_ID` environment is present). The block: an admin GETs exactly the three seeded rows (5, 3, 30, with descriptions and null `updated_by`); an admin POST changes a value and the row records the admin's id and a fresh `updated_at`; a bad value (negative, fractional, string) and an unknown key are 400 and the row is unchanged; `analysis_daily_limit_platform` (known key, no row) is 404 and no row appears — the gate stays closed; a signed-in non-admin (`userCookie`) gets 403 from both handlers; a forged-Origin POST (`adminCookie`) is 403. The file's sign-in call count is unchanged by this block |
| 5 | **Docs and labels.** Flip the feature to Running: the db.md § settings note (the page lists and edits rows, validates against `web/lib/settings.ts`, records `updated_by`/`updated_at`; a new setting is seeded with its code change and then editable like the rest), arch.md § 4.4's Admin row, tech.md's `web/` repository-layout row, and design.md's page-elements row (admin forms are plain labelled inputs, per 010 and 013). | `docs/db.md`, `docs/arch.md`, `docs/tech.md`, `docs/design.md` | CI's `web` job (lint, typecheck, tests, build) and `db` job pass on the branch; `npm run typecheck` and `npm test` pass locally; the labels match what the code does (checked in review) |

## Data and AI

- **Tables:** `settings` — read in full (GET) and updated one row at a time (POST: `value`, `updated_at`, `updated_by`). No columns added, no schema change, no migration (the table and the three seeded rows came in with task 007).
- **Settings read:** all four known keys are registered in `web/lib/settings.ts` (types and bounds), but only the rows that exist are listed or editable; the D08 platform-cap row has no row yet and is neither shown nor created.
- **AI:** none. No AI call, no prompt, no provenance columns — `settings` values are admin-entered, and db.md gives the table no `ai_*` columns.

## Doc updates

- `docs/db.md` — § settings: a note that the admin settings page (013, Running) lists every row and edits one at a time through `web/app/admin/settings/page.tsx` and `/api/admin/settings`, that POST validates the key and value against the known-keys list in `web/lib/settings.ts` and records `updated_by`/`updated_at`, and that a new setting (like the D08 cap row) is seeded with its code change and then editable like the rest.
- `docs/arch.md` — § 4.4's Admin row flips to Running and names the page and route.
- `docs/tech.md` — the `web/` repository-layout row names the admin settings page, route and `web/lib/settings.ts`.
- `docs/design.md` — the page-elements row for admin settings changes from `Input`, `Label`, `Button` to the plain labelled-input style the admin pages built so far (010, 013) use; shadcn `Input`/`Label` stay Proposed for a later public form.
- No new ADR: the known-keys list and the route are the implementation of db.md's existing sentences, not a new decision.
- **Roadmap changes after merge (the human or Claude, on `main`):** 013 → Done. Nothing else changes: 024 still waits on 013, 022 and 023; 025 on 009–013; no other task becomes Ready.

## Decisions needed

None. Everything this task needs is already settled: the known-keys list, the route and the page implement db.md's existing sentences; design.md's Proposed `Input`/`Label` mapping for the admin settings row is changed by this task per that doc's own rule ("the task that builds the page confirms or changes it"); and **D08 — the `analysis_daily_limit_platform` default** ([db.md § settings](../db.md#settings), the ROADMAP's D08 row) stays open but is **not a decision this task needs** — 013 is update-only, no path in it depends on the number, the cap row simply stays absent, and a known key with no row is neither listed nor creatable (see [Approach](#approach); the Neon block's 404 test in step 4 proves the row stays absent). A listed decision would stop the `/run-task` loop for the human, and here there is nothing to decide.

## Risks and rollback

- **A wrong value turns a feature off for everyone** (e.g. `ask_daily_limit_per_user` → 0 disables Ask for every account; a miskeyed `analysis_refresh_after_days`). The validator refuses anything that is not a whole number at or above the bound; the human is the only writer (role check plus the guarded layout); the page shows the current value and description before saving. Recovery is through the same page — set the value back. The table keeps no history ("one row per setting"): the previous value is gone, which is the documented design, not a bug.
- **The Neon block mutates the seeded rows** — every `npm run test:db` creates a fresh schema-only branch from the project's default branch and drops/recreates `public`, so 5/3/30 are pristine per run; a local run without the branch marker refuses to start (`web/tests/db/setup.ts`). The settings tests change a seed value freely, and the branch dies with the run.
- **Order dependence in `web/tests/db/auth.test.ts`** — the settings block must sit between the role-check test and the rate-limit test, which must stay last (it drains the shared sign-in bucket; any later sign-in would be 429). Vitest runs a file's tests serially, so the insertion point fixes the order — and the block adds **no sign-in calls**: it reuses `adminCookie` and the file-level `userCookie` the role-check test mints, because every `/api/auth/sign-in/email` call shares one bucket (10 per 15 minutes, no client IP, D11 open; vitest runs files in parallel, so a separate file would share it too). The file already makes 7 sign-in calls (six successful sessions and the forged-Origin attempt) before the rate-limit test, which must still land at least one 401 before the 429 — a single extra sign-in, in this block or a later task's, breaks that test without warning, which is why this plan states the no-sign-in rule in step 4 and here.
- **JSONB type edge** — a crafted request (`"5"`, `5.5`, `true`) is refused 400 with no silent coercion; a stored number round-trips as a JS number (the task-007 seed test already proves 5/3/30). A value written straight into the table (never via this route or the seed) would display as stored and fail validation on save — nothing in the app writes that way.
- **The cap gate must stay untouched** — nothing in 013 creates the `analysis_daily_limit_platform` row (update-only; the 404 test proves the row stays absent), so the gate stays closed as documented until D08.
- **Rollback** — the change is additive (one lib, one route file, one page, tests, doc labels) with no migration, package or env-var change: revert the merge commit on `main` to remove the files; any value an admin changed through the page is restored by setting it back in the page.

## Revisions

| Round | What changed | In answer to |
| --- | --- | --- |
| 1 | Neon block adds no sign-in calls: it reuses `adminCookie` plus a new file-level `userCookie` assigned by the role-check test (no invite, no reset token, no `signInCookie`), and the insertion point is now "between the role-check test and the rate-limit test"; the plan now states why (shared sign-in bucket, 10/15 min, no client IP, 7 calls already, rate-limit test needs a 401 before the 429). D08 left "Decisions needed": the section now reads "None", and the D08 statement (update-only; cap row stays absent; a known key with no row is neither listed nor creatable; the 404 test proves it) lives in Approach and Risks. The page posts a JSON number: input converted with `Number(...)`, empty/non-numeric blocked before posting, and the page test asserts the posted body is exactly `{ key, value }` with `typeof value === "number"`. Rows with keys outside `KNOWN_SETTINGS` render read-only with a "not in the app's list of known keys" label and no input; a page test covers it. Done-when's "non-admin gets 403" is mapped to the API routes (GET/POST), with the page path covered by 010's layout redirects and no new page guard. Plain-labelled-input style kept and confirmed per design.md's own rule (review note); the shadcn-kit alternative sentence dropped. | Review items 1–5, plus the design.md note |

## Changes during build

- **POST's saved row carries the updater's email from the session** (`updatedByEmail: admin.email`), not from a second joined select. The plan said POST returns "the saved row" and the page "shows the returned row (new value, updater, timestamp)"; the saved row alone has the updater's id but no email, and `requireAdmin` already has the admin's email — the updater of the row is exactly the admin who just posted, so this is the joined value with no extra query, and the page's "Changed by <email>" line renders without a follow-up GET. The route tests and the Neon block assert it.
- **The scoping test's local `userCookie` was renamed `scopingCookie`.** Adding the plan's file-level `userCookie` made that test's local declaration shadow it, which `npm run lint` (oxlint, `no-shadow`) refuses. Its assertions are unchanged (the rename is mechanical); the role-check test keeps all its original assertions, as the round-2 note required.
- **Offline page-test detail:** jsdom runs interactive form-validation on a submit-button click, so an empty (or non-numeric, which jsdom sanitizes to `""`) required input blocks the submit before the page's own guard runs. The "never posts" tests assert the fetch count stays at one (the mount GET) for the click path, and additionally fire a direct submit to exercise the page's guard and its "Enter a whole number" message. No behaviour deviates from the plan.
- **No other deviations.** Everything else matches the approved plan; the Neon block sits between the role-check test and the rate-limit test and adds no sign-in calls (7 remain before the rate-limit test).

## Verification

Commands run in `web/` on the task branch (worktree `.worktrees/013-admin-settings/`), with their real output:

### `npm test` (offline Vitest suite) — PASS, 19 files / 120 tests

```text
> vitest run

 ✓ tests/proxy.test.ts (9 tests)
 ✓ tests/admin-invite-page.test.tsx (2 tests)
 ✓ tests/layout.test.tsx (5 tests)
 ✓ tests/admin-settings-page.test.tsx (6 tests)
 ✓ tests/mail.test.ts (8 tests)
 ✓ tests/invite-route.test.ts (7 tests)
 ✓ tests/settings-route.test.ts (11 tests)
 ✓ tests/auth-pages.test.tsx (11 tests)
 ✓ tests/auth-config.test.ts (6 tests)
 ✓ tests/auth-handler.test.ts (1 test)
 ✓ tests/auth-prod-start.test.ts (3 tests)
 ✓ tests/auth-guard.test.ts (8 tests)
 ✓ tests/safe-next.test.ts (6 tests)
 ✓ tests/first-admin.test.ts (6 tests)
 ✓ tests/settings-validation.test.ts (7 tests)
 ✓ tests/neon-branch.test.ts (14 tests)
 ✓ tests/env-example.test.ts (2 tests)
 ✓ tests/schema.test.ts (5 tests)
 ✓ tests/admin-layout.test.tsx (3 tests)

 Test Files  19 passed (19)
      Tests  120 passed (120)
```

### `npm run typecheck` — PASS

```text
> tsc --noEmit
```
(exit 0, no output)

### `npm run lint` — PASS

```text
> oxlint --deny-warnings

Found 0 warnings and 0 errors.
Finished in 47ms on 57 files with 250 rules using 12 threads.
```

### `npm run build` — PASS (Next.js 16.4.3, Turbopack)

```text
✓ Compiled successfully in 2.6s
  Running TypeScript ... Finished in 588ms
✓ Generating static pages using 11 workers (10/10) in 192ms

Route (app)
┌ ○ /
├ ○ /_not-found
├ ƒ /admin/invite
├ ƒ /admin/settings          ← this task's page
├ ƒ /api/admin/invite
├ ƒ /api/admin/settings      ← this task's route
├ ƒ /api/auth/[...all]
├ ƒ /api/health/db
├ ○ /forgot-password
├ ○ /reset-password
└ ○ /sign-in
```

### Schema drift (CI's `npx drizzle-kit generate` no-op) — PASS

```text
No config path provided, using default 'drizzle.config.ts'
27 tables
…
settings 5 columns 0 indexes 1 fks
…
No schema changes, nothing to migrate 😴
```

and `git status --porcelain db` (in `web/`) printed nothing.

### `npm run test:db` (Neon-branch suite) — NOT RUN here

Needs `NEON_API_KEY` / `NEON_PROJECT_ID` (CI secrets, H06), which the local environment does not have; the harness refuses to run without them by design (`web/scripts/neon-branch.mjs`). CI's `db` job runs it on this branch; the new "admin settings on a real branch" describe block in `web/tests/db/auth.test.ts` adds no sign-in calls and sits between the role-check test and the rate-limit test.