# ADR-0024: Vitest and Testing Library for the web app's tests

- **Status:** Accepted
- **Decided:** 2026-10-29 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

The web app needs a test runner (roadmap decision D07). Every change needs tests ([AGENTS.md](../../AGENTS.md#building)), and CI runs on every push, including the routine's, so the runner has to be quick.

## Options

| Option | For | Against |
| --- | --- | --- |
| **Vitest with Testing Library** | Fast; TypeScript and ESM without extra config; one of the two runners the Next.js docs cover; renders components in jsdom | Can't render async Server Components; those need end-to-end tests later |
| Jest with Testing Library | The other runner the Next.js docs cover (`next/jest`) | More config and slower with ESM and TypeScript |
| Node's built-in test runner | No dependency | No component rendering without extra setup |
| Playwright only | Tests the real app in a browser | Slow in CI; no unit tests |

## Decision

The web app's tests run on Vitest, with React Testing Library and jsdom for components.

## Consequences

- Tests live in `web/tests/*.test.ts(x)` and run with `npm test`; `web/vitest.config.mts` holds the config and the `@/` alias.
- `@testing-library/jest-dom` adds DOM matchers such as `toHaveTextContent`.
- Async Server Components and database tests need another layer later: end-to-end tests, or tests on Neon branches ([tech.md](../tech.md#at-a-glance)).
- `@vitejs/plugin-react` was left out: it has a peer conflict on `@babel/core`, and Vite compiles JSX without it.

## AI involvement

Claude Code laid out the four options with Vitest as the recommendation; the human chose it during task 006.

## Evidence

- `web/vitest.config.mts`, `web/tests/`; task [006](../tasks/006-web-scaffold/plan.md)
