# ADR-0015: Email goes to the admin only; no user emails

- **Status:** Superseded by ADR-0028
- **Decided:** 2026-10-29 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

The routine already emails the brief to one address (`config/delivery.json`) through the Gmail connector. With the app becoming multi-user, Claude Code had proposed per-user email digests of watchlist alerts, through a transactional email provider.

## Options

| Option | For | Against |
| --- | --- | --- |
| Per-user email digests | Users hear about alerts without opening the app | An email provider, keys and sending limits; delivery tracking; unsubscribe handling; more personal data in use |
| **Email to the admin only; users see alerts in the app** | Nothing new to run; no email provider; less personal data in use | Users have to open the app to see new alerts |

## Decision

Only the admin receives email: the brief the routine already sends. The app sends no email to users. Alerts are shown on the watchlist and stock pages.

## Consequences

**Removed from the design:**
- the email provider
- the `alert_deliveries` table
- the digest endpoint and its token
- the `digest` preference on users

**Sign-in can't use email.** Users can't sign in by emailed link or reset a password by email. Sign-in is by Google (OAuth) or password, and the auth library choice must support that. If password sign-in is used, a lost password needs an admin reset.

**Admin features build on this.** The admin is identified by `users.role = 'admin'`, which also controls the platform settings page ([db.md § settings](../db.md#settings)).

## AI involvement

Claude Code proposed per-user email digests and listed them among the items the human accepted on 2026-10-29. **The human then overrode that:** only the admin receives email. Claude found the knock-on effect on sign-in and recorded it here.

## Evidence

- [AI journal 2026-10-29](../plan.md#ai-journal)
- `config/delivery.json` (the admin's address, running)
