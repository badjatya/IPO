# Code review: 013-admin-settings

## Round 1 (2026-10-30)

**Verdict:** Approved

**Diff:** `git diff main...task/013-admin-settings` at `815b5c3`

**Tests:** run by Claude in `.worktrees/013-admin-settings/web`:

```
$ npm run typecheck        → tsc --noEmit, exit 0
$ npm run lint             → oxlint --deny-warnings, clean
$ npx vitest run
 Test Files  19 passed (19)
      Tests  120 passed (120)
```

Claude pushed the branch. CI [run 40961622654](https://github.com/badjatya/IPO/actions/runs/40961622654) passed `tests`, `web` and `db`:

```
 ✓ tests/db/schema-shape.test.ts (9 tests) 2586ms
 ✓ tests/db/schema-rules.test.ts (8 tests) 6830ms
 ✓ tests/db/auth.test.ts (21 tests) 67461ms
     ✓ admin settings on a real branch (6)
     ✓ rate limits sign-ins: enough failures in the window → the next is refused (429) 3092ms
 Test Files  3 passed (3)
      Tests  38 passed (38)
```

### Findings

| # | Severity | Where | Problem (what breaks, and when) | Suggested fix |
| --- | --- | --- | --- | --- |
| 1 | Minor | `web/app/admin/settings/page.tsx:147` | `text-emerald-600` is a Tailwind palette colour. design.md § Rules says "Colours come from tokens …, not raw hex or Tailwind palette colours, so both themes keep working". It copies 010's invite page (`web/app/admin/invite/page.tsx:67`), which is already on main | Record as a follow-up for both admin pages: a success token (or `text-foreground` with the text "Saved"), done when the first page needs a success colour, or in 024 |
| 2 | Nit | `web/app/admin/settings/page.tsx:117` | `KNOWN_SETTINGS[row.key]` reads through the prototype, so a hand-inserted row keyed `constructor` would render a form, unlike the validator's `Object.hasOwn`. The POST would still be refused (400), so nothing is written | Use `Object.hasOwn(KNOWN_SETTINGS, row.key) ? KNOWN_SETTINGS[row.key] : undefined` |
| 3 | Nit | `web/app/api/admin/settings/route.ts:61` | `updatedAt: new Date()` takes the app server's clock, where the plan said `now()`. Both are UTC instants, and the Neon test's freshness check passes | Optional: `sql\`now()\`` keeps one clock (the database's) for every timestamp |

### Plan and docs

- **Built as approved:**
  - the known-keys module with db.md's four keys and bounds, and one validator that never coerces;
  - the route in 010's guard order: origin, role, JSON, validate, update; 404 for the row-less cap; generic 500;
  - the page:
    - posts a JSON number, asserted in its test;
    - blocks empty input;
    - shows an unknown-key row read-only;
    - shows "Seeded" or "Changed by … IST";
  - the Neon block, which adds **no sign-in calls**, reuses `adminCookie` and the role-check test's `userCookie`, and sits before the rate-limit test (still green).
- **Done-when holds on a real branch:**
  - an admin changes a value, and `updated_by` and `updated_at` are recorded;
  - bad values and unknown keys get 400 and leave the row unchanged;
  - a non-admin gets 403 on both handlers;
  - a forged Origin gets 403;
  - the cap stays absent.
- **Rules:**
  - no hard-coded quota: only db.md's lower bounds (rule 6);
  - no AI and no numbers made up (rule 1);
  - the footer comes from the layout (rule 7);
  - no secrets or user data (rule 11).
- **Changes during build** are fine: `updatedByEmail` comes from the session, `scopingCookie` is a lint rename, and the jsdom submit path is covered.
- **Docs:** db.md § settings, arch.md § 4.4 (Running), tech.md's `web/` row and design.md's page-elements row are all updated and match the code.
- **Roadmap after merge:** 013 is Done. Record finding 1 as a follow-up, under 024 or the first IPO page task (011), for a success-colour token on the admin pages. Nothing else becomes Ready: 024 still waits on 022 and 023, and 025 on 009, 011 and 012.
