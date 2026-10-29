---
task: 013-admin-settings
status: plan-changes
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
  - The page `web/app/admin/settings/page.tsx` — a client component under the already-guarded admin layout: lists the rows with their descriptions and current values, edits one at a time with a labelled number input per row, posts the change, and shows the saved state or the server's error. Form elements follow the invite page's plain-labelled-input style (see Context read, design.md); the shadcn `Button` only.
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
- **Update-only: the page lists the rows that exist and edits one at a time.** A known key with no row (today, only `analysis_daily_limit_platform`) is not shown and cannot be created from the page. Reasons: db.md's documented path for a new setting is "new rows, plus an entry in the app's list of known keys" — the D08 cap row is seeded once D08 decides, before the tasks that read it — and a row-less key has no `description` to show. This keeps the gate exactly as documented: closed until the row exists, and nothing in 013 can invent a default (rule 6). The alternative (letting the page upsert a value for any known key) is laid out under Decisions needed with D08, since it changes how the cap would be set.
- **The page is a client component under the already-guarded admin layout.** 010 made the admin layout the authoritative page-side check for every `/admin/*` page, and the proxy's cookie check covers the URL, so the page itself only renders and posts. It fetches `GET /api/admin/settings` on mount, renders one block per row (key, description, current value, "Changed by <email> on <date/time IST>", or "Seeded" when `updated_by` is null), and an inline form per row: a labelled number input (`min` from `KNOWN_SETTINGS`, `step 1`, required) and the shadcn `Button`. Saving posts `{ key, value }`, then shows the returned row (new value, updater, timestamp) or the server's error. Values come back as JSON numbers and are shown as entered — nothing is computed or estimated (rule 1). Styling follows the invite page and design.md's layout rules (`max-w-5xl` centred, tokens only); form elements are plain labelled inputs, the style the 010 admin pages already use, and design.md's row is updated accordingly. (Alternative, if the review prefers the kit: the human runs `npx shadcn@latest add input label` once and the page uses the components — a one-line stop, otherwise unchanged.)
- **Tests in four layers.** (1) Pure validator tests — every key at its bound and above, and every refused shape. (2) Route tests with auth and db mocked (the invite-route pattern): the three done-when behaviours plus cross-origin, unknown-key, missing-row 404 and bad-JSON. (3) Page tests with fetch mocked (the invite-page pattern): rows render, a save posts `{ key, value }`, a 400 shows the error and keeps the old value. (4) One Neon-branch describe block appended to `tests/db/auth.test.ts` — where the real session helpers already are — placed before the rate-limit test, which must stay last. It reuses the file's helpers and exercises the route end-to-end with a real admin session and real rows: change a value and prove `updated_by`/`updated_at`; refuse a bad value and prove the row unchanged; refuse a non-admin on both handlers; refuse a forged-Origin POST; 404 on the row-less cap and prove no row appears (gate stays closed).
- **No setup steps:** no new packages, no new shadcn components under the primary approach, no env vars, no migration — the build runs start to finish without the human.

## Steps

| # | Step | Files | Test that proves it |
| --- | --- | --- | --- |
| 1 | **Known keys and the validator.** `web/lib/settings.ts`: `KNOWN_SETTINGS` with the four keys of db.md's seeded-rows table (`ask_daily_limit_per_user`, `analysis_monthly_limit_per_user`, `analysis_daily_limit_platform` — integer ≥ 0; `analysis_refresh_after_days` — integer ≥ 1) and `validateSettingValue(body)`, which returns a typed success (the parsed key and number) or one concrete error message per failure (unknown key; not a number; not a whole number; below the bound). No descriptions in code. | `web/lib/settings.ts` | `web/tests/settings-validation.test.ts` — each key accepts its minimum and a larger integer; refuses `"5"`, `5.5`, `true`, `null`, objects, arrays, negatives, below-min integers and unknown keys, and each error message is asserted |
| 2 | **The API route.** `web/app/api/admin/settings/route.ts`: `GET` — `requireAdmin`, then all rows with the updater's email (left join `users`), ordered by key. `POST` — `assertSameOrigin` → `requireAdmin` → bad JSON 400 → `validateSettingValue` (bad value 400 with its message) → `UPDATE settings SET value, updated_at = now(), updated_by = <admin id> WHERE key` → no row matched 404, success 200 with the saved row. AuthError → 401/403; anything else → 500 (the invite route's shape). | `web/app/api/admin/settings/route.ts` | `web/tests/settings-route.test.ts` (auth and db mocked, invite-route pattern) — an admin POST writes the parsed value and the admin's id; a bad value, a bad body and an unknown key are 400 with no db write; a known key with no row is 404; a non-admin is 403 and a missing session 401 on both handlers; a forged-Origin POST is 403; GET returns the mocked rows |
| 3 | **The page.** `web/app/admin/settings/page.tsx` — client component (the admin layout already checks the session and role): fetches GET on mount; one block per row (key, description, current value, "Changed by …" with an IST timestamp, "Seeded" when `updated_by` is null); a labelled number input per row (`min` from `KNOWN_SETTINGS`, `step 1`, required) with the shadcn `Button`; save posts `{ key, value }` and shows the returned row or the server's error. Invite-page form style and tokens, `max-w-5xl` centred. | `web/app/admin/settings/page.tsx` | `web/tests/admin-settings-page.test.tsx` (fetch mocked, invite-page pattern) — the GET rows render with their values and descriptions (by label); editing a row posts `{ key, value }` and shows the updated value; a 400 response shows the error and keeps the old value |
| 4 | **Neon-branch integration.** Append an "admin settings on a real branch" describe block to `web/tests/db/auth.test.ts`, **before** the rate-limit test (which must stay last — it drains the shared sign-in bucket). A small `settings()` helper calls the route's GET/POST with the session cookie (and `Origin` on POST), mirroring the file's `invite()`. Reuses `adminCookie`, `api()`, `signInCookie()`, `latestResetToken()`, `userIdByEmail()` and the invite route (imported as `adminInvite`) to create the non-admin user it needs. | `web/tests/db/auth.test.ts` | `npm run test:db` passes (CI's `db` job on every push; locally when the `NEON_API_KEY`/`NEON_PROJECT_ID` environment is present). The block: an admin GETs exactly the three seeded rows (5, 3, 30, with descriptions and null `updated_by`); an admin POST changes a value and the row records the admin's id and a fresh `updated_at`; a bad value (negative, fractional, string) and an unknown key are 400 and the row is unchanged; `analysis_daily_limit_platform` (known key, no row) is 404 and no row appears — the gate stays closed; a signed-in non-admin gets 403 from both handlers; a forged-Origin POST is 403 |
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

- **D08 — the `analysis_daily_limit_platform` default** (Open; the ROADMAP's D08 row and [db.md § settings](../db.md#settings)). 013 does not need the number: the page lists and edits rows that exist, the cap has no row, so it does not appear and the gate stays closed — exactly the documented state. Options:
  - (a) **Leave D08 open (recommended).** 013 ships update-only; once D08 is decided, the cap row is seeded (the documented path: "The cap row is added once D08 decides, before the tasks that read it") and the settings page edits it like any other row, no rework.
  - (b) Decide D08 now and seed the row in this task — rejected: the default needs the free-quota read from AI Studio and is the human's call; no default may be invented (rule 6).
  - (c) Extend 013 so the page can upsert a value for any known key without a row (the admin types the cap in the UI) — affects how D08's number lands; rejected for 013 because a row-less key has no `description` to display and db.md's documented path is the seed. It can be added later if the human wants it.

## Risks and rollback

- **A wrong value turns a feature off for everyone** (e.g. `ask_daily_limit_per_user` → 0 disables Ask for every account; a miskeyed `analysis_refresh_after_days`). The validator refuses anything that is not a whole number at or above the bound; the human is the only writer (role check plus the guarded layout); the page shows the current value and description before saving. Recovery is through the same page — set the value back. The table keeps no history ("one row per setting"): the previous value is gone, which is the documented design, not a bug.
- **The Neon block mutates the seeded rows** — every `npm run test:db` creates a fresh schema-only branch from the project's default branch and drops/recreates `public`, so 5/3/30 are pristine per run; a local run without the branch marker refuses to start (`web/tests/db/setup.ts`). The settings tests change a seed value freely, and the branch dies with the run.
- **Order dependence in `web/tests/db/auth.test.ts`** — the settings block must sit before the rate-limit test, which must stay last (it drains the shared sign-in bucket; any later sign-in would be 429). Vitest runs a file's tests serially; the plan fixes the insertion point, and the block creates its own non-admin user (invite → reset token → sign in) instead of reaching into earlier tests' users.
- **JSONB type edge** — a crafted request (`"5"`, `5.5`, `true`) is refused 400 with no silent coercion; a stored number round-trips as a JS number (the task-007 seed test already proves 5/3/30). A value written straight into the table (never via this route or the seed) would display as stored and fail validation on save — nothing in the app writes that way.
- **The cap gate must stay untouched** — nothing in 013 creates the `analysis_daily_limit_platform` row (update-only; the 404 test proves the row stays absent), so the gate stays closed as documented until D08.
- **Rollback** — the change is additive (one lib, one route file, one page, tests, doc labels) with no migration, package or env-var change: revert the merge commit on `main` to remove the files; any value an admin changed through the page is restored by setting it back in the page.

## Revisions

| Round | What changed | In answer to |
| --- | --- | --- |

## Changes during build

Anything built differently from the approved plan, and why.

## Verification

Test commands run, with their output pasted.