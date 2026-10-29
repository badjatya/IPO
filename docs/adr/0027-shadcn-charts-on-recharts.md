# ADR-0027: shadcn/ui charts, on Recharts, for the web app

- **Status:** Accepted
- **Decided:** 2026-10-30 · **Recorded:** 2026-10-30
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

Three pages need charts (roadmap decision D06): GMP and subscription trends on IPO detail (011), the track record (012) and quarterly results on stock pages (019). The data is small: a few dozen points per IPO, eight quarters per stock, one row per listed IPO. The app already uses shadcn/ui on Tailwind CSS v4 ([ADR-0020](0020-shadcn-ui.md)), and `web/app/globals.css` already defines `--chart-1`…`--chart-5` for light and dark.

## Options

| Option | For | Against |
| --- | --- | --- |
| **shadcn/ui `chart` (Recharts)** | The kit's own chart component, with a `base-nova` version in the registry. It reads our `--chart-*` tokens and comes with tooltip and legend parts styled like the other components. Recharts 3 is MIT licensed, accepts React 19 as a peer, and has an accessibility layer (keyboard and ARIA) on by default | Adds one client-side dependency tree (Recharts with redux-toolkit, immer, victory-vendor). Charts are client components (`"use client"`). In jsdom, `ResponsiveContainer` needs a `ResizeObserver` stub and a fixed size |
| Hand-written SVG | No dependency; server-rendered, so no JavaScript is sent; easy to test | Axes, scales, ticks and tooltips are ours to write and keep up, in task 011 |
| visx | MIT, flexible D3 primitives for React | More code per chart than Recharts; not tied into shadcn's theming |
| Tremor | Ready-made dashboard charts on Tailwind | `@tremor/react` 3.18 accepts only React 18 as a peer; the app is on React 19 |

## Decision

The web app draws charts with shadcn/ui's `chart` component, which wraps Recharts. It's added with `npx shadcn@latest add chart` when the first page needs it, as design.md says for every component.

## Consequences

- The first chart task (011, 012 or 019, whichever is built first) runs `npx shadcn@latest add chart`. It copies `web/components/ui/chart.tsx` and adds `recharts` (the registry pins 3.8.0) to `web/package.json`.
- Chart components are client components. Pages stay server components: they query the data and pass plain arrays down as props, so the database is never touched from the client.
- Series colours come from the `--chart-*` tokens through `ChartConfig`, not from raw hex ([design.md § Adding components](../design.md#adding-components)). Status colours (verdict, trend) stay on badges and are not used as series colours.
- Charts show stored figures only. Axis and tooltip values use the shared number formatter, and a chart never computes a figure the research didn't produce ([AGENTS.md](../../AGENTS.md) rule 1).
- A chart never carries information alone: the same figures are in a table or a text line next to it ([design.md § Accessibility](../design.md#accessibility)). Tests check that table or text, not the SVG.
- Tests that render a chart stub `ResizeObserver` in jsdom and give the container a fixed size.

## AI involvement

Claude Code checked the shadcn registry, which lists a `base-nova` chart on Recharts 3.8.0, and the alternatives' peer dependencies. Tremor was ruled out on React 19. Claude put three options to the human with shadcn's chart as the recommendation, and the human chose it.

## Evidence

- `npx shadcn@latest view chart`: `registry/base-nova/ui/chart.tsx`, dependencies `cn`, `recharts@3.8.0`
- `npm view recharts@3.8.0 peerDependencies`, `npm view @tremor/react peerDependencies` (2026-10-30)
- `--chart-1`…`--chart-5` in `web/app/globals.css`
