# ADR-0010: PostgreSQL on Neon

- **Status:** Accepted
- **Decided:** 2026-10-29 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

The app needs a hosted database on a free tier. The human asked to compare MongoDB Atlas and Neon PostgreSQL.

## Options

| Option | For | Against |
| --- | --- | --- |
| MongoDB Atlas, free cluster | Document model fits cards and analyses | Data is relational; joins become lookups or duplication; fixed, small storage; 100 operations a second |
| **PostgreSQL on Neon, free tier** | Relational with foreign keys and unique constraints; SQL aggregates for the track record and trends; `jsonb` for document-shaped data; database branches for tests and previews | Pauses after 5 minutes idle, so the first query after a pause is slower; compute-hour cap |

## Decision

PostgreSQL on Neon. The schema is in [db.md](../db.md).

## Consequences

- Users → watchlists → stocks → filings → alerts are joins with real constraints, such as one watchlist row per user and stock.
- Each test run and preview gets its own Neon branch.
- Prospectus text stays in git to save storage.
- Free-tier limits checked on 2026-10-29: 1 GB storage per project (raised from 0.5 GB on 2 Oct 2026), 100 compute-hours a month, pauses when idle. These change; recheck before launch.
- Backups for app-owned data are an open question, because the free tier keeps only a short history.

## AI involvement

The human asked which of the two to use. Claude Code compared them with current free-tier figures from web search and recommended Postgres. The human then asked for the tech docs to be written, and Claude recorded Postgres as the choice. The human hasn't objected, but hasn't confirmed it in so many words either.

## Evidence

- Sources checked 2026-10-29:
  - [Neon pricing](https://neon.com/pricing)
  - [Neon changelog](https://neon.com/docs/changelog/2025-11-28)
  - [MongoDB Atlas free cluster limits](https://mongodb.com/docs/atlas/reference/free-shared-limitations/)
- [db.md](../db.md)

