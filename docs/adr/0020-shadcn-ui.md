# ADR-0020: shadcn/ui and Tailwind CSS for the web app

- **Status:** Accepted
- **Decided:** 2026-10-29 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

The Next.js app ([ADR-0009](0009-nextjs-web-platform.md)) needs UI components and a styling approach (roadmap decision D05). The human judge scores UI quality, and the app is data-heavy: cards, tables, badges, alerts and a loading screen.

## Options

| Option | For | Against |
| --- | --- | --- |
| **shadcn/ui with Tailwind CSS** | Accessible components copied into the repo and owned by us; theme as CSS variables; widely known by coding agents | Component code lives in our repo and has to be kept up |
| A packaged component library | Upgrades come from the package | Harder to restyle; adds a runtime dependency per component |
| Hand-written CSS | No dependencies | Slow, and accessibility is on us |

## Decision

The web app uses shadcn/ui with Tailwind CSS v4. The rules for using it are in [design.md](../design.md).

The sub-choices are the `shadcn init --defaults` values, not a human decision: style `base-nova`, Base UI primitives (rather than Radix) and the neutral base colour. Base UI or Radix is still open ([design.md § Open questions](../design.md#open-questions)).

## Consequences

- Components are added with `npx shadcn@latest add <name>` into `web/components/ui/` and are ours to change.
- The theme lives in `web/app/globals.css`; there is no Tailwind config file.
- `npm audit` reports low-severity issues in the `shadcn` CLI's dependencies (`deepmerge`); the suggested fix downgrades shadcn, so it was not applied.

## AI involvement

The human chose shadcn/ui. Claude Code wrote the options table afterwards to record the alternatives; they were not weighed before the choice. Claude ran `shadcn init` with its defaults (`--defaults`: the `next` template and `nova` preset) and wrote [design.md](../design.md).

## Evidence

- `web/components.json`, `web/app/globals.css`
