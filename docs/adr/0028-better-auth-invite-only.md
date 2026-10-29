# ADR-0028: Better Auth, invite-only password sign-in, account emails through Resend

- **Status:** Accepted
- **Decided:** 2026-10-30 · **Recorded:** 2026-10-30
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

Task 010 (accounts) was blocked on D04: the auth library, and Google sign-in or password. [ADR-0015](0015-email-to-admin-only.md) had ruled out all email to users, so sign-in could not use emailed links and a lost password needed an admin reset.

The human then set the shape of accounts: **email and password, no public sign-up, and the admin invites each user by email, sent through Resend.** That needs the app to email users, which ADR-0015 forbade, so this ADR supersedes it. The rest of ADR-0015 stands: no alert digests, and the brief still goes to the admin only.

The stack is Next.js 16 with Drizzle on Neon ([ADR-0025](0025-drizzle-on-neon-serverless-driver.md)), and sessions must live in Postgres ([arch.md § 7.1](../arch.md#71-security-and-trust-boundaries)).

## Options

| Option | For | Against |
| --- | --- | --- |
| **Better Auth, in the app** | MIT; a Drizzle adapter, so its tables are ours, in `web/db/schema.ts` and our migrations; sessions in Postgres; email and password with sign-up turned off (`disableSignUp`); an admin plugin (create user, set role, ban, revoke sessions); a reset-password hook that both the invite and "forgot password" can use. Peers accept Next 16, React 19 and drizzle-orm 0.45 | Its user table defaults to text ids; matching db.md's `uuid` id and `citext` email takes config. One more dependency tree |
| Auth.js (NextAuth v5) with credentials | Well known | The credentials provider works only with JWT sessions, not database sessions. Password hashing, invites and resets are ours to write |
| Neon Auth (managed Better Auth) | Least code; on the same Neon project | Auth runs outside the app; tables sit in a `neon_auth` schema we don't migrate; only the plugins Neon supports |

For email: **Resend** (the human's choice), through its Node SDK. It is MIT and has a free tier.

## Decision

The web app uses **Better Auth** with its Drizzle adapter and database sessions. Sign-in is by **email and password only**. **Public sign-up is off.** The **admin invites** a user by email. The user gets a one-time link through **Resend** and sets their own password. Users can also reset a forgotten password by an emailed link (the human chose this).

## Consequences

- **The app now sends email,** but only account emails: the invite and the password reset. There are still no alert digests and no marketing email, and the brief stays on the routine's Gmail connector ([ADR-0015](0015-email-to-admin-only.md) is superseded only for these two emails).
- **Invites.** An admin-only action creates the user, with role `user` and no usable password, and sends a set-password link. Better Auth's reset-password token is the natural basis, with a longer expiry for invites. The plan settles the exact mechanism. Re-inviting sends a fresh link and voids the old one.
- **No sign-up route.** Nothing creates an account except an admin invite and the first-admin mechanism, and a test proves sign-up is refused.
- **First admin.** There's no one to invite the first admin, so it needs a server-side bootstrap, such as a script run with the database URL. The plan proposes one, and it never ships in a public route.
- **Schema.** db.md's `users` fields (`uuid` id, `citext` email unique, `role` defaulting to `user`) are kept, and Better Auth's `session`, `account` and `verification` tables are added to `web/db/schema.ts` through a migration. Passwords are stored only as hashes in `account`.
- **New setup step (H07).** The human creates a Resend account and API key, and verifies a sending domain. Until a domain is verified, Resend's test sender only delivers to the account owner's address. New variables: `RESEND_API_KEY` and a from-address (`EMAIL_FROM`). Tests never call Resend; the sender is behind a small module that tests replace.
- **Email content.** Account emails carry only the link and the product's placeholder name, with no research, and a link that never reveals whether an address has an account ("If an account exists…" on the reset form).
- **Security work in 010.** Rate limits on sign-in and reset requests, CSRF protection (Better Auth checks the origin; the plan confirms it), route guards, and every user query scoped to the signed-in user, as before.
- **Personal data.** User email addresses now go to Resend for delivery. The privacy note in the submission must say so.

## AI involvement

The human set the method and the email provider: password sign-in, admin invites only, Resend. Claude Code proposed Better Auth over Auth.js and Neon Auth, giving the reasons above, and the human took it. Claude also asked whether "forgot password" should email a reset link, since the invite path makes it nearly free, and the human said yes. Claude found that this supersedes ADR-0015 and recorded which parts of 0015 still hold.

## Evidence

- `npm view better-auth` (1.7.14, MIT; peers `next ^16`, `react ^19`, `drizzle-orm ^0.45.2`) and `npm view resend` (6.35.0, MIT), 2026-10-30
- [ADR-0015](0015-email-to-admin-only.md), roadmap D04 and task 010
