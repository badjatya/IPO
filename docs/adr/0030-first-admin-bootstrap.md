# ADR-0030: First-admin bootstrap and one link expiry for invites and resets

- **Status:** Accepted
- **Decided:** 2026-10-30 · **Recorded:** 2026-10-30
- **Deciders:** Vijay · **Drafted with:** DeepSeek (OpenRouter), reviewed by Claude Code

## Context

[ADR-0028](0028-better-auth-invite-only.md) made accounts invite-only: no public sign-up, the admin invites each user by an emailed one-time link, and the first admin has no one to invite them. It left two mechanisms to plan review: how the first admin gets created (never in a public route), and how long the invite and reset links live.

Two plan-review facts shaped the options. The first-admin script cannot import the TypeScript auth core (`web/lib/auth.ts`, `@/` aliases, no `tsx` in the project), so a script that "requests a reset token" would either hand-write Better Auth's `verification` row (copying library internals) or add a TypeScript runner. And Better Auth 1.7.14 has one reset-password token mechanism — the invite and the "forgot password" flows both rest on it.

## Options

**First admin:**

| Option | For | Against |
| --- | --- | --- |
| **CLI script** (chosen) | Plain JavaScript, no TypeScript runner needed; only upserts `users.role = 'admin'` through the existing neon-http client (insert or promote, idempotent, re-runs never duplicate); works before any deploy; the password is set through the running app's `/forgot-password`, so Better Auth stays in charge of tokens | One more manual step for the operator; the admin can't sign in until the app issues the reset link (fine: the app runs first anyway) |
| Admin API route | No manual step | A public route that promotes a user would be the very thing invite-only forbids; needs a guard before any admin exists, and the operator still has to call it |
| Hand-writing a `verification` row | The script alone could produce a working link | Copies library internals (token format, identifier scheme); breaks when Better Auth changes them |

**Link expiry:**

| Option | For | Against |
| --- | --- | --- |
| **One mechanism, one expiry of 24 hours for both flows** (chosen) | One code path, one constant; re-inviting voids the old link either way | A single, fairly long window for reset links; acceptable at this stage |
| Longer invite expiry, shorter reset expiry | Invites could linger longer | Two mechanisms for the same token, more configuration, no user-visible gain now |

## Decision

1. **First admin is a CLI script**: `web/scripts/first-admin.mjs <email> [name]`, run with `DATABASE_URL` from the environment. It does only the database part — upsert the user to role `admin` (insert on missing, promote on existing, idempotent) — and writes no token and no `verification` row. The password is set through the running app's `/forgot-password`, whose link prints in dev (print mode) and emails once a Resend domain is verified (H07). It never ships as a route.
2. **Invite and reset links are one mechanism with one expiry**: Better Auth's reset-password token, with `emailAndPassword.resetPasswordTokenExpiresIn` set to `60 * 60 * 24` seconds (24 hours) for both flows. Re-inviting deletes the user's outstanding reset rows first, voiding the old link. "Works once and expires" and "forgot password doesn't reveal whether an account exists" come from Better Auth itself.

## Consequences

- The first-admin script stays plain JavaScript and tests are limited to its pure helpers (argv parsing, upsert SQL); the end-to-end proof (script → forgot-password → set password → admin session) lives in the Neon-branch suite.
- The passwordless admin row is harmless: nothing can sign in with it until a password is set, and the app can issue the reset link the moment it runs.
- A mis-run (wrong email promoted) is repaired by re-running the script or one SQL `update`; auth tables are app tables, so no research data is ever at risk.
- The reset-token expiry is a security parameter, set in code — not a product quota, so it does not live in the `settings` table (AGENTS.md rule 6).

## AI involvement

The plan proposed both options; the human settled both at plan review round 1: the CLI script (option A) and the single 24-hour expiry (option A). DeepSeek refined the script after review: it writes no token and no `verification` row, because a `.mjs` cannot import the TypeScript auth core and Better Auth must stay in charge of tokens. Recorded as **Accepted** because these are decisions the human has made, not a proposal.

## Evidence

- `docs/tasks/010-accounts/plan-review.md` rounds 1–3 (decisions 1 and 2)
- Better Auth 1.7.14 sources: `api/routes/password.mjs` (one `resetPasswordTokenExpiresIn`, the `reset-password:<token>` verification identifier, single-use consumption), read in plan review