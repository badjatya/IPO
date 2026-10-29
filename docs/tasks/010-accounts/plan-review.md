# Plan review: 010-accounts

## Round 1 (2026-10-30)

**Verdict:** Changes requested

**Read:** plan.md, AGENTS.md, docs/tasks/README.md, ADR-0028, ADR-0015, ADR-0012, ADR-0025, db.md § users, arch.md § 4.4 and § 7.1, tech.md § Configuration, `web/lib/db.ts`, `web/db/schema.ts`, `web/package.json`. Checked against the published packages, not memory: `better-auth@1.7.14`, `@better-auth/drizzle-adapter@1.7.14` and `@better-auth/core@1.7.14` (`npm pack`, read the `dist/` sources), and `next@16.4.3` in `web/node_modules`.

The approach is right: Better Auth carries the security properties (single-use tokens, the non-revealing reset reply), the app adds a thin shell, and there is one mail path. The items below are mostly places where the plan's picture of Better Auth 1.7.14 doesn't match the package, plus two security gaps in the app's own code.

### Decisions (human)

1. **First admin:** Option A, the CLI script. See item 6 for how the script gets its link.
2. **Link expiry:** Option A, one mechanism and `resetPasswordTokenExpiresIn` = 24 hours for both invite and reset links. Re-inviting voids the old link.

Write both into the plan as settled, and move them out of "Decisions needed". The ADR in step 10 records a decision the human has made, so it is **Accepted**, not Proposed.

### Changes requested

1. **The admin plugin adds columns the schema step leaves out.** In 1.7.14 the `admin` plugin extends `user` with `role`, `banned`, `banReason` and `banExpires`, and `session` with `impersonatedBy` (`plugins/admin/schema.mjs`). The drizzle adapter throws when a model field is missing from the Drizzle table, so step 2 as written would fail at the first `createUser`. Choose one of these and state it in Approach and step 2:
   - **(a)** Keep the admin plugin. Add all its columns to the migration, and to db.md under Doc updates. Say what the app does with ban and impersonation: they come with the plugin and are admin-only endpoints. Impersonation in particular is a new admin power that no doc mentions.
   - **(b)** Drop the plugin. Declare `role` as a `user.additionalFields` entry (`input: false`, default `user`, so a client can never set it), and create invited users server-side through the auth context or a scoped Drizzle insert.

   Either is fine. The plan must pick one and list the exact column set.
2. **Ids: `user.fields.id: { input: false }` isn't how Better Auth makes ids.** Better Auth generates every id itself, as a random 32-character string, unless `advanced.database.generateId` says otherwise (`false | "serial" | "uuid" | fn` in core's `init-options`). A text id going into the `uuid` column fails on insert. Use `advanced.database.generateId: "uuid"`, or `false` with a database default on every auth table. Then make `session`, `account` and `verification` (and `rate_limit`, see item 4) use `uuid` ids too, and their `user_id` FKs `uuid` to match `users.id`. db.md's `users.id uuid` stays, as the task requires.
3. **CSRF on the app's own routes.** Better Auth's origin check covers only its own `/api/auth/*` endpoints. `POST /api/admin/invite` is the app's own cookie-authenticated route, so nothing checks its origin. Give it an explicit check (`Origin` must equal the `AUTH_URL` origin, else 403) or make it a Server Action, which Next checks against the host. Add a test: a cross-origin invite POST carrying an admin session is refused. State the rule in Approach so 013's settings route follows it.
4. **Rate limits: name what 1.7.14 actually does.**
   - It is **off unless `NODE_ENV === "production"`** (`rateLimit.enabled ?? isProduction` in `context/create-context.mjs`). Set `enabled: true` explicitly so the test in step 8 tests something and dev behaves like prod.
   - The default store is **in memory**, which is per instance on any serverless host. 1.7.14 has `storage: "database"` (a `rateLimit` model with `key`, `count`, `lastRequest`). Use it and add its table to the migration, instead of deferring the choice to the build.
   - Limits are keyed by **client IP and path**, not by email address as the plan says. Use `customRules` for `/sign-in/email` and `/request-password-reset`. Note in Risks that without `advanced.ipAddress` configured for the host (D11), every request lands in one shared bucket, and Better Auth logs a warning. The test harness has no client IP, so the step 8 test exercises that shared bucket. Say so.
   - `/api/admin/invite` is not behind Better Auth's limiter, and server-side `auth.api.*` calls skip it too. Either drop the "invite 5/hour" claim or implement it in the route. Admin-only is an acceptable reason to drop it.
5. **Mail print mode must never run in production.** As written, a missing `RESEND_API_KEY` makes `sendAccountEmail` print the email, and with it a live one-time token, to the server log, and the user gets nothing. Print mode is for `NODE_ENV !== "production"` only. In production, a missing `RESEND_API_KEY` or `EMAIL_FROM` throws, so the invite route returns an error the admin sees. Add a unit test for the production branch. The `AUTH_SECRET` dev fallback has the same problem: allow it only outside production.
6. **First-admin script: say how a `.mjs` gets a valid link.** `web/scripts/first-admin.mjs` can't import `web/lib/auth.ts` (TypeScript, `@/` aliases, no `tsx` in the project). "Requests a reset token" therefore means either hand-writing Better Auth's `verification` row (`identifier: reset-password:<token>`, `value: <user id>`, as `api/routes/password.mjs` does), which copies library internals, or some TypeScript runner. Pick the simplest path that keeps Better Auth in charge of tokens. One option: the script only creates or promotes the user with role `admin`, using the existing Neon client and SQL, idempotently. The human then sets the password through `/forgot-password`, which prints the link in dev (item 5) and emails it once H07 is done. Whatever you pick, state it, and test it in the Neon-branch suite.
7. **Invite to an address that already exists.** `createUser` fails on the unique email. Specify the route's behaviour:
   - an existing user gets no new row;
   - their outstanding links are voided and a fresh link is sent;
   - their role is never changed (an invite neither demotes an admin nor promotes a user);
   - the response is the same as for a new invite.
   Also say exactly how "void the old link" works: reset rows are keyed by token, not by address (`identifier = 'reset-password:<token>'`, `value = <user id>`). The delete is `identifier LIKE 'reset-password:%' AND value = <user id>`. That test needs a real database, so it belongs in `tests/db/auth.test.ts`, not in the mocked unit test that step 5 lists.
8. **Invite email vs reset email.** Both go through `sendResetPassword`, so as planned an invited user would get a "reset your password" email. The hook should choose the wording: an invite if the user has no credential account yet, a reset otherwise. Unit-test both. Both emails still carry only the product name, the link and the disclaimer.
9. **Guards: proxy is optimistic; pages and routes are authoritative.**
   - Next 16.4 uses `web/proxy.ts`, which runs on Node (`PROXY_FILENAME` in `next/dist/lib/constants.js`). Name the file, and drop the edge-runtime risk.
   - Don't make the proxy the only check for pages. Middleware bypasses have happened before (CVE-2025-29927). `web/app/admin/**` checks the session and role server-side (a layout or page helper that redirects or returns 403), just as the invite route calls `requireAdmin`. The proxy can stay as a fast cookie check.
   - Unit-test the server-side helper, not only the proxy predicate.
10. **Timing on forgot-password.** Better Auth answers unknown addresses the same way, but for known addresses it awaits `sendResetPassword`, so a slow Resend call reveals that the account exists. Don't await delivery in the hook: fire it and log failures. Use `advanced.backgroundTasks` or the host's `waitUntil` if the installed version supports it. State the trade-off: a delivery failure isn't shown to the person who asked, and for this form that's acceptable. The admin invite route may still await delivery and report errors, because the admin already knows the address exists.

### Notes

- `advanced.csrfCheck` isn't an option to turn on. Better Auth's origin check runs by default against `baseURL` and `trustedOrigins`. Keep it on (never `disableCSRFCheck`), and keep the forged-Origin test.
- With the Postgres provider, the drizzle adapter doesn't use `db.transaction` (only the MySQL paths do), and tokens are consumed with a single `DELETE … RETURNING`. So the neon-http `db()` works and single use holds. Worth one line in Context read.
- Better Auth lowercases emails on sign-in and reset, and `citext` makes the unique index case-insensitive. The two agree, so nothing needs doing.
- The ADR-0012 disclaimer line in account emails is fine.
- The `AUTH_URL` row needs adding to both tech.md and `web/.env.example`, as planned. `web/.env.example` already lists `RESEND_API_KEY` and `EMAIL_FROM` on `main`.

## Round 2 (2026-10-30)

**Verdict:** Changes requested

**Read:** plan.md (revision 1), round 1 above, and again the published `better-auth@1.7.14` and `@better-auth/core@1.7.14` sources (`core/dist/db/get-tables.mjs`, `core/dist/db/schema/rate-limit.mjs`, `core/dist/types/init-options.d.mts`).

All ten round 1 items and both decisions are answered, and the answers are sound. Option (b), dropping the admin plugin, is the simpler surface. Five small corrections remain. Four are places where the plan's config doesn't match 1.7.14 and would fail or misbehave at runtime, and one is a gap that fire-and-forget opened.

### Changes requested

1. **`rate_limit.last_request` is a number of milliseconds, not a timestamp.** Better Auth's `rateLimit` model has `lastRequest` as `type: "number", bigint: true` ("the last request time in milliseconds"), and the store writes `Date.now()` and reads it back with `Number(...)`. Make the column `bigint` (Drizzle `bigint(..., { mode: "number" })`), `not null`, in step 2 and in the db.md update. A `timestamptz` column would reject the insert.
2. **`resetPasswordTokenExpiresIn` is a number of seconds inside `emailAndPassword`.** The type is `resetPasswordTokenExpiresIn?: number` under `emailAndPassword`, and the route computes `getDate(value || 3600, "sec")`. `"24 hours"` would give an invalid date. Write it as `emailAndPassword.resetPasswordTokenExpiresIn: 60 * 60 * 24` in step 3 and the Approach.
3. **`customRules` is an object keyed by path, not an array.** `customRules?: { [path: string]: { window, max } | false | fn }`. Write it as `{ "/sign-in/email": { window: 900, max: 10 }, "/request-password-reset": { window: 3600, max: 5 } }`.
4. **The admin must see a missing mail config, now that the hook fires and forgets.** Round 1 item 5 asked that, in production, a missing `RESEND_API_KEY` or `EMAIL_FROM` reaches the admin as an error. With delivery fired from the hook, the throw happens after the invite route has already answered "Invite sent", so it only reaches the log. Check the mail config up front instead:
   - a small `mailConfigured()` or `assertMailConfig()` in `web/lib/mail.ts`;
   - the invite route calls it before creating any row, and answers 500 with a plain "email is not configured" message if it fails;
   - in production, `web/lib/auth.ts` also fails at start when it's missing, the same as `AUTH_SECRET`.
   Unit-test the route's 500 branch. The public forgot-password route stays generic.
5. **Revoke sessions on password reset.** Set `emailAndPassword.revokeSessionsOnPasswordReset: true`. A reset is how a user recovers a compromised account, and the attacker's session should end with it. Add one assertion to the Neon-branch test: a session from before the reset no longer resolves after it.

### Notes

- Once these five are in, the plan is ready to approve. Step 1 stops for the human's `npm install` as planned.

## Round 3 (2026-10-30)

**Verdict:** Approved

**Read:** plan.md (revision 2) and rounds 1–2 above.

All five round 2 items are in:
- `rate_limit.last_request` is `bigint` (`mode: "number"`).
- `emailAndPassword.resetPasswordTokenExpiresIn` is `60 * 60 * 24`.
- `customRules` is an object keyed by path.
- `assertMailConfig()` runs in the invite route before any row is created (500 "email is not configured"), and `auth.ts` fails at start in production when the mail config is missing.
- `revokeSessionsOnPasswordReset: true`, with a Neon-branch assertion that a session from before the reset is gone.

### Notes

- Step 1 is the human's `cd web && npm install better-auth resend`. `/run-task` stops for it before `build`.
- During the build, check every Better Auth option against the installed package's types, as the Risks section says. Record any difference under "Changes during build", including the hook's context shape and whether `advanced.backgroundTasks` exists.
- Real Neon-branch runs only count in CI (task 007's lesson). Push the branch for the `db` job before asking for the code review.
