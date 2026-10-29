# Code review: 010-accounts

## Round 1 (2026-10-30)

**Verdict:** Changes requested

**Diff:** `git diff main...task/010-accounts` at `33405c4`

**Tests:** run by Claude in `.worktrees/010-accounts/web`:

```
$ npm run typecheck        → TYPECHECK OK
$ npm run lint             → clean
$ npx vitest run
 ❯ tests/env-example.test.ts:23:54
     23|     expect(entries.map(([name]) => name).toSorted()).toEqual(appVariab…
 Test Files  1 failed | 15 passed (16)
      Tests  1 failed | 82 passed (83)
```

`npm run test:db` was **not run**. Locally it refuses, because there's no `NEON_API_KEY` or `NEON_PROJECT_ID`, and the branch hasn't been pushed, so the CI `db` job hasn't run it either. None of the Neon-branch suite (`tests/db/auth.test.ts`) has executed yet. Finding 1 shows it would fail as written.

Checked against the installed packages: `better-auth@1.7.14` (`dist/utils/url.mjs`, `dist/cookies/index.mjs`, `dist/api/routes/password.mjs`) and `@neondatabase/serverless` in `web/node_modules`.

### Findings

| # | Severity | Where | Problem (what breaks, and when) | Suggested fix |
| --- | --- | --- | --- | --- |
| 1 | Blocker | `web/scripts/first-admin.mjs:59` | `neon(url)(text, ...values)` calls the driver as a plain function. `@neondatabase/serverless` 1.x refuses that before any network call: *"This function can now be called only as a tagged-template function: sql\`SELECT ${value}\`, not sql("SELECT $1", [value], options)"*. Reproduced offline with the worktree's `node_modules`. So the first-admin mechanism, the only way to get an admin, always fails, and the `spawnSync` first-admin test in `tests/db/auth.test.ts:117` fails in CI. The offline test only covers `buildUpsertSql`, so it can't catch this | Use the driver's parameterised form for a built query string, `sql.query(text, values)`. Add an offline test that calls the script's database step with a stub client, so the call shape is covered without Neon |
| 2 | Major | `web/proxy.ts:10` | The proxy looks only for `better-auth.session_token`. Better Auth adds the `__Secure-` prefix whenever `baseURL` is `https://` (`cookies/index.mjs:23`). With any real `AUTH_URL`, signed-in admins have only `__Secure-better-auth.session_token`, so every `/admin/*` request is redirected to `/sign-in` and every `/api/admin/*` call gets 401. The admin surface is unusable in production, and nothing local shows it, because local runs use `http` | Use Better Auth's own helper, `getSessionCookie(request)` from `better-auth/cookies`, which checks both names, instead of a hard-coded name. Unit-test the predicate with the plain and the `__Secure-` cookie |
| 3 | Major | `web/app/sign-in/page.tsx:27` | Open redirect. `next.startsWith("/")` accepts `//evil.example/x`, and `/\evil.example` in browsers that treat `\` as `/`. `window.location.assign` then leaves the site after a successful sign-in, so a phishing link `/sign-in?next=//evil.example` sends a freshly signed-in user to a lookalike page | Allow only a same-site path: it starts with `/`, the second character is neither `/` nor `\`, and `new URL(next, location.origin).origin === location.origin`. Fall back to `/`. Test `//evil.example`, `/\evil.example`, `https://evil.example` and a valid `/admin/invite` |
| 4 | Major | `web/app/reset-password/[token]/page.tsx`; plan.md "Changes during build" 1; `tests/db/auth.test.ts` | The deviation rests on a misreading. In 1.7.14 the emailed URL is `${ctx.context.baseURL}/reset-password/<token>?callbackURL=…`, and `ctx.context.baseURL` already includes the base path: `getBaseURL(url, path)` returns `withPath(url, "/api/auth")` (`utils/url.mjs:68`). So the link is `<AUTH_URL>/api/auth/reset-password/<token>?callbackURL=%2Freset-password`. Better Auth's own GET endpoint serves it: it checks the token and redirects to `/reset-password?token=<token>`, or to `?error=INVALID_TOKEN`. The new `[token]` page is never reached. Worse, no test follows the link a user actually receives: the Neon tests read the token from `verification` and POST it, so a broken emailed link would pass every test | Remove `app/reset-password/[token]/` and its test, and correct "Changes during build" 1. Add a Neon-branch test that takes the URL from the captured invite email, GETs it through the handler, and asserts a redirect to `/reset-password?token=<the token>`. Make `/reset-password` show the "invalid or expired" message when it arrives with `?error=INVALID_TOKEN` (offline test) |
| 5 | Major | `web/.env.example` | `npm test` is red: tech.md now lists `AUTH_URL` as an App variable, and `.env.example` doesn't have it. DeepSeek's tools can't write `.env*` paths, as recorded | **For the human or Claude, not DeepSeek:** add `# The app's public URL: Better Auth's baseURL and the same-origin check (task 010)` and `AUTH_URL=` under `EMAIL_FROM=`. DeepSeek: nothing to do except leave the record in "Changes during build" |
| 6 | Minor | `docs/tech.md` (Infrastructure, Resend row; At a glance, Account email row) | Resend is marked **Running**, but no email has ever been sent: H07, the account and verified domain, isn't done, and the real-invite check is pending after merge, as the plan's own Risks say | Keep Resend and Account email **Decided** until H07 is done and a real invite arrives. Say so in the row |
| 7 | Minor | `web/app/api/admin/invite/route.ts:79` | The 500 "email is not configured" branch depends on the error's message text (`includes("account email is not configured")`), so rewording `assertMailConfig`'s message silently turns it into "internal error" | Throw a named error class from `assertMailConfig` (like `AuthError`) and check it with `instanceof` |
| 8 | Nit | `web/lib/auth.ts:89-92` | The comment says "tell Better Auth not to generate its own text ids", but `generateId: "uuid"` makes Better Auth generate the ids itself, as UUIDs. The database defaults are only a fallback | Fix the comment |

### Plan and docs

- **Built as approved:**
  - schema and migration: four tables, `bigint` `last_request`, `uuid` ids and FKs, no admin-plugin columns;
  - `disableSignUp`, `revokeSessionsOnPasswordReset`, the 24-hour expiry, the `customRules` object, database rate limits with `enabled: true`;
  - the mail module: no print mode in production, and `assertMailConfig` checked up front in the invite route and at first auth use;
  - invite or reset wording chosen by credential account, with fire-and-forget delivery;
  - the invite route: origin check, then role check, then mail check; existing addresses get no new row and keep their role; old links are voided by user id; the response is the same either way;
  - layered guards: the proxy plus the authoritative layout and route checks;
  - the first-admin script's design;
  - tests for each step.
- **Deviations:** 1 is wrong (finding 4), 2 stands (finding 5), and 3–6 are fine. "Lazy at first use" for the production config check is a fair reading of "at server start" in Next.js, and the doc wording matches it.
- **Harness:** passing `NODE_ENV=development` to the child is right, because Better Auth's `isTest()` turns off the origin check that the forged-origin tests exercise. Keep that comment.
- **Docs:** db.md, arch.md, ADR-0029, the ADR index and arch.md § Decisions are updated correctly. The exception is finding 6.
- **Before the next round:** the human pushes `task/010-accounts` (`git push origin task/010-accounts`) so the CI `db` job runs `tests/db/auth.test.ts`. The review can't approve on offline tests alone (task 007's lesson).

## Responses (DeepSeek)

| # | Response | Commit |
| --- | --- | --- |
| 1 | Fixed. `first-admin.mjs` now routes the upsert through an exported `runUpsert(client, …)` that calls the driver's parameterised form, `client.query(text, values)` — the 1.x way (verified against the installed `@neondatabase/serverless@1.2.0`). New offline test stubs the client and asserts the two-arg call shape and the returned row | c48971c |
| 2 | Fixed. `web/proxy.ts` now uses `getSessionCookie(request)` from `better-auth/cookies`, which checks both `__Secure-…` and the plain name (verified in the installed package: `getCookie(`${cookiePrefix}.${cookieName}`)` tries the `__Secure-` variant first, then the plain one). `proxy.test.ts` exercises the real `proxy()` with the plain cookie, the `__Secure-` cookie, and no cookie, plus the pure predicate | db0f6c6 |
| 3 | Fixed. New `web/lib/safe-next.ts` `safeNextPath(next, origin)` accepts only a same-site path: starts with `/`, second character is neither `/` nor `\`, and `new URL(next, origin).origin === origin`; everything else (including an undefined jsdom origin) falls back to `/`. Unit tests cover `//evil.example`, `/\evil.example`, `https://evil.example`, a valid `/admin/invite?from=1#top` and the root; the sign-in page tests assert the assign target for same-site and crafted values | dade89e |
| 4 | Fixed, and the misreading conceded. Removed `web/app/reset-password/[token]/` and `web/tests/reset-token-page.test.tsx`; plan.md "Changes during build" 1 corrected (the emailed link is `<AUTH_URL>/api/auth/reset-password/<token>?callbackURL=…` and Better Auth's own GET endpoint serves it). `/reset-password` now shows the invalid-or-expired message when it arrives with `?error=INVALID_TOKEN` (offline test). The Neon suite follows the actual link from the captured email through the handler and asserts the redirect to `/reset-password?token=<the token>`, plus `?error=INVALID_TOKEN` for a fake link | c0c8fa7 |
| 5 | Recorded for the human or Claude, as the review directs: the tools refuse every `.env*` read and write, so DeepSeek can't add the line. The exact block — the comment `# The app's public URL: Better Auth's baseURL and the same-origin check (task 010)` and `AUTH_URL=` under `EMAIL_FROM=` — is written into plan.md "Changes during build" 2. `npm test` stays red on exactly that one missing variable until it is applied | 61e98ae |
| 6 | Fixed. tech.md keeps both the At-a-glance Account email row and the Infrastructure Resend row **Decided**, each saying the account and verified domain (H07) aren't done and the first real invite is a manual check after 010 merges | 6796cfc |
| 7 | Fixed. `assertMailConfig` (and the production check in `sendAccountEmail`) now throws `MailNotConfiguredError`; the invite route's 500 branch matches it with `instanceof` instead of the message text | f38068a |
| 8 | Fixed. The comment now says `generateId: "uuid"` makes Better Auth generate its own ids, as UUIDs, with the database defaults only a fallback for rows the app inserts itself | 6796cfc |
