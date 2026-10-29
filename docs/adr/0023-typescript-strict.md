# ADR-0023: TypeScript in strict mode for the web app

- **Status:** Accepted
- **Decided:** 2026-10-29 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

The web app needs a language (roadmap decision D02). [tech.md](../tech.md#web-platform) proposed TypeScript with strict mode, and the bare app in `web/` was created that way (`"strict": true` in `web/tsconfig.json`).

## Options

| Option | For | Against |
| --- | --- | --- |
| **TypeScript, strict** | Catches nulls and shape mistakes before review, which matters when an AI agent writes most of the code; the default for Next.js and shadcn/ui | A type-check step in CI; some typing effort |
| Plain JavaScript | No types to write | Mistakes reach review or runtime; shadcn/ui and most examples are TypeScript |

## Decision

The web app is written in TypeScript with `strict` on.

## Consequences

- `npm run typecheck` (`tsc --noEmit`) runs locally and in CI, and `next build` type-checks again.
- The bare app ships TypeScript 7, the native compiler. typescript-eslint supports only TypeScript below 6.1, so the app lints with oxlint instead of ESLint (task 006).

## AI involvement

Claude Code recommended keeping strict TypeScript, as the docs proposed and the bare app already used; the human chose it during task 006.

## Evidence

- `web/tsconfig.json`, `web/package.json`; task [006](../tasks/006-web-scaffold/plan.md)
