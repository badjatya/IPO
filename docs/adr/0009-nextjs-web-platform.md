# ADR-0009: Next.js for the web platform

- **Status:** Accepted
- **Decided:** 2026-10-29 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

The product needs a multi-user web app: accounts, a watchlist, IPO and stock pages, the track record and Ask. The human judge scores UI quality, so the interface has to feel like a product.

## Options

| Option | For | Against |
| --- | --- | --- |
| Standard-library Python web app (`wsgiref` + `sqlite3`) | Matches the agent's no-dependency rule | Hand-rolled auth and UI; weaker for a polished, multi-user product |
| **Next.js, frontend and backend in one app** | Mature ecosystem for auth, database access and UI; one codebase for pages and API | A second language and toolchain in the repo |

## Decision

The web platform is a Next.js app with pages and API routes. Research stays in the Python agent run by the Claude routine.

## Consequences

- [ADR-0002](0002-standard-library-only-agent.md) now applies to the agent only.
- The app never calls the data sources; it reads the database ([ADR-0011](0011-git-as-the-hand-off.md)).
- Still open: TypeScript, ORM, auth library, UI kit, host.
- In-app Ask uses the Gemini API, not Claude ([ADR-0014](0014-gemini-free-api-for-ask.md)).

## AI involvement

Claude Code proposed a standard-library Python web app to keep the no-dependency rule. **The human overrode it** in favour of Next.js.

## Evidence

- [AI journal 2026-10-29](../plan.md#ai-journal)

