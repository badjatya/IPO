# Plan review: 013-admin-settings

## Round 1 (2026-10-30)

**Verdict:** Changes requested

**Read:**
- plan.md, AGENTS.md, docs/tasks/README.md § Reviewer guide;
- db.md § settings and § Access patterns;
- design.md § Page elements;
- arch.md § 4.4;
- ROADMAP.md (013 and D08);
- 010's `web/lib/auth-guard.ts`, `web/app/admin/layout.tsx`, `web/proxy.ts`, `web/app/admin/invite/page.tsx` and `web/tests/db/auth.test.ts`.

The plan fits the task and the docs well:
- update-only, one row at a time;
- the known-keys list as db.md describes it;
- 010's guard order (`assertSameOrigin`, then `requireAdmin`);
- no schema, package or env change;
- no invented cap row (rule 6).

The items below are about the test harness's limits and one mis-filed "decision".

### Changes requested

1. **The Neon block must not add sign-ins: they share the sign-in rate-limit bucket.** In the harness every `/sign-in/email` call lands in one database bucket: 10 per 15 minutes, with no client IP (D11 open). `auth.test.ts` already makes 7 sign-in calls before its last test, and the forged-Origin attempt may count too. The rate-limit test then needs at least one `401` before the `429` (`statuses.filter((s) => s === 401).length >= 1`). The plan's block creates and signs in its own non-admin user (invite, then reset token, then sign in), which is one or two more calls. That leaves the last test one attempt from failing, or past it. And any later task that adds a sign-in breaks it without warning. A separate test file is no way out: vitest runs files in parallel, against the same bucket. Change step 4 so the settings block makes **no new sign-in calls**:
   - reuse `adminCookie`;
   - reuse a non-admin session cookie that an earlier test already minted, kept in a file-level variable the way `adminCookie` is (the role-check test's user, for example);
   - say in the plan that the block adds no sign-ins, and why.
2. **D08 is not a decision this task needs; take it out of "Decisions needed".** Option (a) changes nothing, and db.md already records it: the cap has no row until D08, and "the cap row is added once D08 decides". Option (c), creating rows from the page, is outside the task, which "lists the `settings` rows and edits one at a time". Under `/run-task`, a listed decision stops the loop for the human, and here there's nothing to decide. Move it to Approach or Risks as a statement: 013 is update-only; the cap row stays absent; a known key with no row is neither listed nor creatable; the 404 test proves it. Keep the D08 reference.
3. **The page must post a JSON number, and a test must prove it.** The validator refuses the string `"5"`, and an `<input type="number">` gives a string. If the page posts the input's raw value, every save from the page is a 400, and a mocked-fetch test that checks only the URL won't notice. Say in step 3 that the page converts the input with `Number(...)`, and blocks an empty or non-numeric input before posting. In the page test, assert that the posted body is exactly `{ key, value: <number> }` (`typeof value === "number"`).
4. **Say what the page does with a row whose key isn't in `KNOWN_SETTINGS`.** GET returns every row. A row with an unknown key (inserted by hand, or a key that a later task's code drops) has no `min`, and every save of it is a 400. Show such a row read-only, labelled as not in the app's list of known keys, with no input. Add a page test for it. The route already refuses the POST, so no route change is needed.
5. **Map "a non-admin gets 403" to where it actually happens.** For the page, 010's admin layout redirects a signed-in non-admin to `/` (a 401 goes to `/sign-in`); it doesn't answer 403. The 403 comes from `GET` and `POST /api/admin/settings`. In Approach (or the test table), state that the done-when 403 is the API's, and that the page path is covered by 010's layout tests, so nobody reads the redirect as a gap later. No new page guard.

### Notes

- **design.md:** changing the "Sign-in, admin settings" row to plain labelled inputs is within the plan's remit, because design.md says "the task that builds the page confirms or changes it", and 010's pages already use plain inputs. That's fine.
- **GET without the origin check** is fine: it changes nothing, and it's same-origin JSON behind the session cookie.
- **No upper bounds:** none are in db.md, and none may be invented (rule 6). The validator's lower bounds come straight from db.md's table.
