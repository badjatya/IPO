# ADR-0025: Drizzle ORM on Neon's serverless driver

- **Status:** Accepted
- **Decided:** 2026-10-29 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

The app needs an ORM with versioned migrations (roadmap decision D03) and a Postgres driver ([tech.md § Web platform](../tech.md#web-platform)). The host is still open (D11), and the right driver usually follows from the host: a long-lived Node server pools TCP connections, while serverless and edge runtimes can't keep a pool between requests.

## Options

ORM:

| Option | For | Against |
| --- | --- | --- |
| **Drizzle, with drizzle-kit migrations** | Schema in TypeScript, SQL-shaped queries, plain SQL migration files; small; Neon's own guides use it | Fewer batteries than Prisma (no studio-first workflow) |
| Prisma | Mature, generated client | Needs a generated client and an adapter for Neon's driver; its migrations need a separate direct URL |

Driver:

| Option | For | Against |
| --- | --- | --- |
| **`@neondatabase/serverless`** | Works on any host: Node, serverless and edge. HTTP for one-shot queries, WebSocket `Pool` for interactive transactions; no pool to size | Neon-only |
| `pg` (node-postgres) | Standard; best on a long-lived Node server or Vercel Fluid compute | Needs pool management on serverless hosts; doesn't run on edge without a proxy |

## Decision

The app uses Drizzle ORM, with drizzle-kit for versioned migrations, on Neon's serverless driver: `drizzle-orm/neon-http` for queries, and `drizzle-orm/neon-serverless` (WebSocket `Pool`) only where an interactive transaction is needed.

## Consequences

- The connection lives in `web/lib/db.ts`, which reads the pooled `DATABASE_URL`. drizzle-kit runs migrations over the direct `DATABASE_URL_UNPOOLED`, because PgBouncer's transaction mode breaks session state.
- Task 007 installs `drizzle-orm` and `drizzle-kit`, writes the schema in TypeScript and checks the generated migrations in.
- The host (D11) is no longer tied to the driver. If it turns out to be a long-lived Node server, switching to `pg` touches only `web/lib/db.ts`.
- Neon setup is in `web/neon.ts` (the branch policy) and `web/.neon` (the linked project, gitignored). `production` is the default branch and `dev` is the long-lived local branch. Any other new branch, such as one per CI test run, expires after 7 days.

## AI involvement

The human chose Drizzle and left the driver to Claude Code. Claude chose Neon's serverless driver because it works on every host still in the running, following Neon's agent skill for Postgres (`neon-postgres`).

## Evidence

- `web/lib/db.ts`, `web/app/api/health/db/route.ts`, `web/neon.ts`
- `GET /api/health/db` answered `{"ok":true,"database":"neondb"}` from `next start` on 2026-10-29
