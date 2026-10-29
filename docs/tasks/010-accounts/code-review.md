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

## Round 2 (2026-10-30)

**Verdict:** Changes requested

**Diff:** `git diff main...task/010-accounts` at `61d85fe`

**Tests:** offline, run by Claude in `.worktrees/010-accounts/web`:

```
$ npm run typecheck        → tsc --noEmit, exit 0
$ npm run lint             → oxlint --deny-warnings, clean
$ npx vitest run
 Test Files  16 passed (16)
      Tests  96 passed (96)
```

Neon branch suite: Claude pushed `task/010-accounts` (the human was away) to run CI. In [run 40957096331](https://github.com/badjatya/IPO/actions/runs/40957096331), `tests` and `web` passed and **`db` failed**:

```
 ✓ tests/db/schema-shape.test.ts (9 tests) 3063ms
 ✓ tests/db/schema-rules.test.ts (8 tests) 8249ms
 ❯ tests/db/auth.test.ts (14 tests | 11 failed) 16153ms
     ✓ refuses public sign-up 1632ms
     ✓ forgot-password on an unknown address answers the same and mails nothing 1586ms
     × first admin: the script upserts the admin, and the app boots it with a password and an admin session 5004ms
     × admin invite: new user created, invite wording, token works once, session role is user 3ms
     × the emailed link works as sent: GET /api/auth/reset-password/<token> redirects to the form page (code review round 1 finding 4) 5ms
     × inviting an existing address changes no row, voids the old link, sends a working fresh one 225ms
     × re-inviting sends a fresh link and voids the previous one 1ms
     × refuses an expired token 1ms
     × a password reset revokes sessions minted before it (round 2 item 5) 1ms
     × role check: a signed-in user's invite is refused, the admin's succeeds (guards are layered) 774ms
     × scoping: each session token resolves only to its own user 452ms
     × refuses a forged-Origin sign-in POST (Better Auth's origin check) 1240ms
     ✓ refuses a cross-origin invite POST even with an admin session (the route's own check) 225ms
     × rate limits sign-ins: enough failures in the window → the next is refused (429) 5001ms
 FAIL  … first admin: … Error: Test timed out in 5000ms.
 FAIL  … admin invite: … AssertionError: expected '' not to be ''   (tests/db/auth.test.ts:164)
 FAIL  … rate limits sign-ins … Error: Test timed out in 5000ms.
      Tests  11 failed | 20 passed (31)
```

Also on this branch: Claude applied round 1 finding 5 in `61d85fe` (`AUTH_URL` with its comment in `web/.env.example`), as that finding directed. The offline suite is green now.

### Findings

| # | Severity | Where | Problem (what breaks, and when) | Suggested fix |
| --- | --- | --- | --- | --- |
| 1 | Blocker | `web/vitest.db.config.mts:12` | The Neon auth suite is red in CI because of vitest's default 5 s `testTimeout`. Each Better Auth call from the runner to the `ap-southeast-1` branch takes about 1 s (password hashing plus round trips; the passing tests take 1.2–1.6 s for one or two calls). The first-admin test runs `spawnSync("node", …)` plus about eight handler calls, so it hits 5004 ms before it sets `adminCookie`. Nine later tests then fail on the empty cookie or a 401 (`auth.test.ts:164` and onwards). The rate-limit test needs up to ten failed sign-ins of about 1 s each, so it also stops at 5001 ms before any 429. None of the round-1 fixes that need the database (findings 1 and 4) has been shown to work yet | Set `testTimeout: 60_000` and `hookTimeout: 60_000` in `vitest.db.config.mts`'s `test` block, with a comment saying why: real-branch calls take about 1 s each, and `spawnSync` blocks the event loop. Don't raise the default in `vitest.config.mts`; the offline suite stays fast. Leave the tests' assertions as they are. If a test still fails once it has the time, that's a real bug: fix the code, not the assertion |

### Plan and docs

- **Round 1 fixes:** findings 1–4 and 6–8 are fixed as suggested, and the code matches the responses:
  - `runUpsert` calls `client.query(text, values)`;
  - `getSessionCookie` is used in the proxy, tested with both cookie names through the real `proxy()`;
  - `safeNextPath` covers the four cases, and the sign-in page uses it;
  - the `[token]` page is gone, and `/reset-password` handles `?error=INVALID_TOKEN`;
  - the Neon test follows the emailed link;
  - tech.md keeps Resend **Decided**;
  - `MailNotConfiguredError` is matched with `instanceof`;
  - the comment is fixed.
- **Record:** "Changes during build" 1 now describes the link correctly. The driver's commits didn't touch round 1's text or the approved plan's body.
- **Before round 3:** after the response, Claude pushes the branch again so the `db` job reruns. Round 3 approves only when that job is green.

## Responses (DeepSeek)

| # | Response | Commit |
| --- | --- | --- |
| 1 | Fixed. `testTimeout: 60_000` and `hookTimeout: 60_000` added to the `test` block of `web/vitest.db.config.mts`, with a comment recording why: each Better Auth call to the real branch takes about 1 s, the first-admin test's `spawnSync` blocks the event loop (its 5004 ms timeout was the first failure CI showed), and the rate-limit test needs up to ten ~1 s failed sign-ins before the 429. `vitest.config.mts` keeps Vitest's default and the offline suite stays fast; no test assertion changed. Offline checks re-run on the branch: typecheck, lint and `npm test` all green (16/16 files, 96/96 tests). The Neon suite itself still only runs in CI — the branch needs a push for the `db` job to rerun | 6029a4b |

## Round 3 (2026-10-30)

**Verdict:** Changes requested

**Diff:** `git diff main...task/010-accounts` at `43f2ae8`

**Tests:** the round-2 fix (`6029a4b`, 60 s timeouts in `vitest.db.config.mts`) is right and is the only code change. Offline, unchanged from round 2: typecheck, lint, and vitest 16/16 files, 96/96 tests. Claude pushed the branch again. In CI [run 40957678294](https://github.com/badjatya/IPO/actions/runs/40957678294), `tests` and `web` passed and `db` failed, with 2 failures left:

```
 ✓ tests/db/schema-shape.test.ts (9 tests) 2716ms
 ✓ tests/db/schema-rules.test.ts (8 tests) 7318ms
 ❯ tests/db/auth.test.ts (14 tests | 2 failed) 66422ms
     ✓ first admin: … 8149ms
     ✓ admin invite: … 7924ms
     ✓ the emailed link works as sent: … 4192ms
     ✓ inviting an existing address … 7850ms
     ✓ re-inviting … 7643ms
     ✓ refuses an expired token 3408ms
     ✓ a password reset revokes sessions minted before it 13424ms
     ✓ role check: … 3249ms
     × scoping: each session token resolves only to its own user 3266ms
     × refuses a forged-Origin sign-in POST (Better Auth's origin check) 1055ms
     ✓ refuses a cross-origin invite POST even with an admin session 215ms
     ✓ rate limits sign-ins: … 3167ms
 FAIL … scoping … TypeError: Cannot read properties of null (reading 'user')   ❯ tests/db/auth.test.ts:338:54
 FAIL … forged-Origin … AssertionError: expected 200 to be 403                ❯ tests/db/auth.test.ts:350:22
      Tests  2 failed | 29 passed (31)
```

The first-admin script (round 1 finding 1) and the emailed link (round 1 finding 4) now pass on a real branch.

### Findings

| # | Severity | Where | Problem (what breaks, and when) | Suggested fix |
| --- | --- | --- | --- | --- |
| 1 | Blocker | `web/tests/db/setup.ts`; `web/scripts/neon-branch.mjs:194` | **The Neon suite never runs Better Auth's origin or CSRF check, so the forged-Origin test fails (200).** Vitest sets `process.env.TEST = "true"` in every worker (`vitest/dist/chunks/index.*.js`: `TEST: "true", VITEST: "true"`). In 1.7.14, `isTest()` is `nodeENV === "test" \|\| toBoolean(env.TEST)` (`@better-auth/core/dist/env/env-impl.mjs:36`), and `create-context.mjs:211` sets `skipOriginCheck: isTest() ? true : false` when `advanced.disableOriginCheck` isn't set. With `skipOriginCheck === true`, `validateOrigin` returns early for the origin check and the CSRF check alike. The harness's `NODE_ENV=development` fixes only half of `isTest()`, and the round-1 review missed the `TEST` half too. Production is unaffected, because `TEST` isn't set there. But the suite's claim to cover "Better Auth's origin check" (Done-when: CSRF protection) is false, and the test fails | In `tests/db/setup.ts`, before anything builds the auth instance, `delete process.env.TEST`, with a comment citing the two lines above. Keep `NODE_ENV=development` in the harness. Then add an assertion that the check is really on, e.g. `expect((await getAuth().$context).skipOriginCheck).toBe(false)` (or whatever 1.7.14 exposes for it). Expect fallout: with the check on, any **POST that carries a cookie and no `Origin`** gets 403 `MISSING_OR_NULL_ORIGIN`. Make the `api()` helper send `origin: BASE` by default on POSTs, as a browser does, and let a test override it. Don't set `advanced.disableOriginCheck` in `lib/auth.ts` to make tests pass |
| 2 | Major | `web/tests/db/auth.test.ts:336-339` | **The scoping test builds cookies Better Auth can't read.** It sends `better-auth.session_token=<session.token>` straight from the `session` table. Better Auth's session cookie is **signed** (`<token>.<HMAC signature>`, URL-encoded), so an unsigned token resolves to no session, `get-session` returns `null`, and `.user` throws. The test fails on its own construction, so it says nothing about scoping | Check scoping from the cookies Better Auth issued instead: take the token part (before the first `.`, after `decodeURIComponent`) of `adminCookie` and of the user's sign-in cookie. Assert that each token's `session` row has its own user's `user_id`, that the two differ, and that each cookie's `get-session` returns its own email (that part already passes). Don't hand-roll the signature |

### Plan and docs

- **Round 2:** fixed as asked, and no assertions changed. `vitest.config.mts` keeps the default.
- **Record:** "Changes during build" 2 records that Claude applied `.env.example`, and the Verification section is updated. Earlier rounds are untouched.
- **Loop count:** this is the third code-review round without approval. The human asked overnight for 010 to be finished and merged, both findings are in the test harness, failures went from 11 to 2, and the respond steps cost under a cent. So Claude is running one more respond step instead of stopping here, and records that for the human.
- **Before round 4:** Claude pushes the branch again, and round 4 approves only when the `db` job is green.

## Responses (DeepSeek)

| # | Response | Commit |
| --- | --- | --- |
| 1 | Fixed. `tests/db/setup.ts` deletes `process.env.TEST` before anything builds the auth instance, with a comment citing `env-impl.mjs` (`isTest()` = `NODE_ENV === "test" \|\| toBoolean(env.TEST)`) and `create-context.mjs` (`skipOriginCheck = isTest() ? true : false`) — the vitest-propagated `TEST=true` was the second half of `isTest()` the harness's `NODE_ENV=development` didn't cover. `tests/db/auth.test.ts` now asserts `(await AUTH.\$context).skipOriginCheck === false` (and `skipCSRFCheck === false`) as the suite's first test, so the checks being on is proven, not assumed. The `api()` helper sends `origin: BASE` by default on POSTs, as a browser does; a test overrides it (the forged-Origin test still sends `https://evil.example`). No `advanced.disableOriginCheck` anywhere in `lib/auth.ts` — verified in the installed package before the fix. The harness comment in `neon-branch.mjs` and plan.md "Changes during build" 3 are corrected to name vitest's `TEST`, not `NODE_ENV`, as the skipper | 04c4dad |
| 2 | Fixed. The scoping test no longer feeds raw `session.token` values in as cookies — Better Auth signs the session cookie (`<token>.<HMAC signature>`, URL-encoded; better-call's `signCookieValue`, verified in the installed package), so that cookie was one the library couldn't read and the test failed on its own construction. It now extracts the token part (before the first `.`, after `decodeURIComponent`) from the cookies Better Auth itself issued, asserts `adminToken !== userToken`, and asserts each token's `session` row keys to that user's `user_id` (email looked up back through `users`). The two `get-session` calls asserting each cookie resolves to its own email stay as before | 04c4dad |

## Round 4 (2026-10-30)

**Verdict:** Approved

**Diff:** `git diff main...task/010-accounts` at `49d7d27`

**Tests:** run by Claude. Offline in `web/`: vitest 16/16 files, 96/96 tests. CI on the pushed branch, [run 40958866657](https://github.com/badjatya/IPO/actions/runs/40958866657): `tests`, `web` and `db` all passed:

```
 ✓ tests/db/schema-shape.test.ts (9 tests) 2333ms
 ✓ tests/db/schema-rules.test.ts (8 tests) 6363ms
 ✓ tests/db/auth.test.ts (15 tests) 57244ms
 Test Files  3 passed (3)
      Tests  32 passed (32)
```

### Findings

None open.

### Plan and docs

- **Round 3 finding 1** is fixed as suggested:
  - `tests/db/setup.ts` deletes vitest's `TEST`;
  - a new test asserts `skipOriginCheck` and `skipCSRFCheck` are both `false` (`skipCSRFCheck` is a real context field, `create-context.mjs:210`);
  - `api()` sends `Origin: BASE` on POSTs by default;
  - `lib/auth.ts` is untouched, so the forged-Origin 403 now comes from the real check.
- **Round 3 finding 2** is fixed: scoping is checked through the issued cookies' token parts against the `session` rows.
- **Done-when holds on a real branch:**
  - sign-up is refused;
  - first admin, invite, set password, sign in;
  - links work once and expire;
  - forgot-password gives nothing away;
  - the role check and scoping;
  - origin checks and rate limits;
  - docs labels as in round 1.
- **For the merge:** `task/008-import-script` also adds a migration numbered `0003`. Whichever task merges second regenerates its migration on top of the other's (`npx drizzle-kit generate`).
