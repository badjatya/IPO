# ADR-0011: Git is the hand-off; the database copy of research is rebuildable

- **Status:** Accepted
- **Decided:** 2026-10-29 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

The research agent has no database driver ([ADR-0002](0002-standard-library-only-agent.md)), and the routine already commits every output to git. The app needs that research in Postgres.

## Options

| Option | For | Against |
| --- | --- | --- |
| Routine writes to the database directly | One path | Needs a driver or HTTP API in the agent; database credentials in the routine; no history |
| Routine posts to an app API | No driver needed | App must be up during runs; still no history; a second write path to secure |
| **Routine commits to git; a GitHub Action imports on push** | Agent unchanged; git keeps the history of every call; the database can be rebuilt | Import lag of a minute or two; an Action to maintain |

## Decision

Research output stays in git, as the system of record. A GitHub Action imports each push into Postgres with idempotent upserts. App-owned data (users, watchlists, Ask history, settings) lives only in the database.

## Consequences

- The database's research tables can be dropped and rebuilt by replaying the repo.
- The routine needs only a read-only token to fetch watched symbols, and no database access.
- User data never enters git.

## AI involvement

Claude Code proposed this on 2026-10-29. The human accepted it the same day, without changes.

## Evidence

- [arch.md § Import Action](../arch.md#43-import-action-decided), [db.md § Import and rebuild](../db.md#import-and-rebuild)

