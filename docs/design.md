# UI design

How the web app looks and behaves: the component kit, theme, colours, numbers, layout and the rules every page follows. Read this before building or reviewing a page in `web/`.

- What the pages are: [arch.md § 4.4](arch.md#44-nextjs-app-decided)
- Why shadcn/ui: [ADR-0020](adr/0020-shadcn-ui.md)
- The email this app sits beside: `ipo_agent/email_render.py`

Status labels (**Running**, **Decided**, **Proposed**, **Open**) are defined in [README.md](README.md#status-labels).

## Principles

| Principle | What it means on a page | Status |
| --- | --- | --- |
| Research, not advice | The footer says "Research, not investment advice." on every page; it lives in `web/app/layout.tsx`, not in page code. IPO verdicts are labelled as research. Stock pages never say buy, sell or hold ([ADR-0012](adr/0012-research-not-advice.md)) | Running (footer); Decided (wording) |
| Every number has a source and a time | A block of figures shows where they came from and "as of HH:MM IST", as the email does. GMP is marked unofficial | Decided ([arch.md § 7.2](arch.md#72-failure-handling): the app shows the "as of" time); Proposed (per block) |
| Numbers are exact | The page shows the stored figure. It never rounds a figure into a different claim, and never computes one the research didn't produce | Decided ([ADR-0001](adr/0001-python-for-exact-work-claude-for-judgement.md)) |
| Same words as the email | Verdicts, phases, trends and grades use the email's labels (below), so the brief and the app read as one product | Proposed |
| Dense but scannable | Lead with the call and the key figures; details (RHP sections, anchor list, day-by-day subscription) go below or in tabs | Proposed |
| Colour is never the only signal | Every coloured badge has a text label; every trend has an arrow | Proposed |

## Foundation

| Item | Choice | Status |
| --- | --- | --- |
| Component kit | [shadcn/ui](https://ui.shadcn.com) (style `base-nova`, an init default): components are copied into `web/components/ui/` and owned by us | Decided ([ADR-0020](adr/0020-shadcn-ui.md)) |
| Primitives | Base UI (`@base-ui/react`), the `shadcn init` default; Radix is the alternative | Running; Open (Base UI or Radix) |
| Styling | Tailwind CSS v4; no `tailwind.config`, the theme lives in `web/app/globals.css` | Running |
| Theme tokens | CSS variables in `globals.css` (`--background`, `--primary`, `--muted`, `--destructive`, `--chart-1`…`5`, `--radius` and the rest), neutral base colour (an init default), light and `.dark` sets | Running |
| Class merging | `cn()` from `web/lib/utils.ts` (the `cn` package from shadcn) | Running |
| Font | Geist via `next/font/google`, as `--font-sans` | Running |
| Icons | lucide-react | Running |
| Dark mode | Tokens exist; a toggle or `prefers-color-scheme` switch is not built | Open |
| Charts | GMP and subscription trends, results, the track record | Open (D06) |

### Adding components

```bash
cd web
npx shadcn@latest add card badge table   # copies into components/ui/
```

- Add a component when a page needs it, not in advance.
- Change `components/ui/*` only for a project-wide reason (a token, a variant), and say so in the commit. Page-specific styling goes in the page through `className`.
- Colours come from tokens (`bg-muted`, `text-muted-foreground`, `border`), not raw hex or Tailwind palette colours, so both themes keep working.

## Status colours

The email already has a colour language (`VERDICT`, `PHASE_COLOR`, `TREND`, `GRADE` in `ipo_agent/email_render.py`). The app uses the same meanings. **Proposed:** add them to `globals.css` as tokens (`--verdict-apply`, `--phase-open` and so on, with light and dark values) when the first IPO page is built, and render them through one `Badge` variant per group.

| Group | Value → label | Email colour (text on tint) |
| --- | --- | --- |
| Verdict | `apply` → Apply | green `#137333` on `#E6F4EA` |
| | `listing_gains` → Listing gains only | amber `#B06000` on `#FEF7E0` |
| | `avoid` → Avoid | red `#C5221F` on `#FCE8E6` |
| | `neutral` → Neutral | grey `#3C4043` on `#F1F3F4` |
| | `pending` → Analysis pending | grey `#5F6368` on `#F1F3F4` |
| Phase | `open` | green |
| | `closing_today` | red |
| | `listing_today`, `awaiting_listing` | purple `#8430CE` on `#F3E8FD` |
| | `upcoming` | blue `#1967D2` on `#E8F0FE` |
| | `announced` | grey |
| Trend | `up` ↑ / `down` ↓ / `flat` → | green / red / grey |
| Anchor grade | `strong` / `average` / `weak` / `pending` | green / amber / red / grey |

On stock pages, green and red show only direction (a price or a figure went up or down), never a judgement. There are no verdict badges for listed stocks ([ADR-0012](adr/0012-research-not-advice.md)).

## Numbers, dates and units

| Kind | Format | Example | Status |
| --- | --- | --- | --- |
| Money | ₹ with Indian grouping (`Intl.NumberFormat("en-IN")`); large amounts in crore as `₹1,234 Cr` | ₹117 Cr | Proposed (matches the email) |
| Price and GMP | ₹ value, then percent of the issue price | ₹51 (34%) | Proposed (matches the email) |
| Subscription | Times, one or two decimals, `x` suffix | 21x, 0.15x | Proposed (matches the email) |
| Dates | Short weekday, day, month | Wed 29 Oct | Proposed (matches the email) |
| Times | 24-hour IST, always labelled | as of 19:07 IST | Proposed (matches the email) |
| Columns of figures | Right-aligned, `tabular-nums` | | Proposed |

Format numbers in one shared module (to be added with the first page that shows figures), not inline in each page.

## Layout

| Item | Rule | Status |
| --- | --- | --- |
| Page shell | `body` is a full-height column; content above, disclaimer footer at the bottom | Running |
| Content width | `max-w-5xl`, centred, `px-4` side gutter | Running (home page) |
| Mobile | Works at 360 px wide with no sideways page scroll; wide tables scroll inside their own container | Proposed |
| Navigation | Header with the modules a user can reach: IPOs, Track record, Watchlist; Admin only for admins. Product name is a placeholder until D13 | Proposed |
| Page header | Title, then the "as of" line and source, then the main call | Proposed |

## Page elements → components

Which shadcn component each part of [arch.md § 4.4](arch.md#44-nextjs-app-decided) should use. All **Proposed**; the task that builds the page confirms or changes it.

| Element | Component |
| --- | --- |
| IPO card on the Today list | `Card` with verdict and phase `Badge`s |
| Key figures (price band, lot, GMP, dates) | Definition grid inside `Card`, `tabular-nums` |
| Subscription by day, allotment odds, anchor book | `Table` |
| Analysis sections (business, financials, risks) | `Tabs` or headed sections |
| Watchlist alerts | `Alert`, one per alert, severity by token |
| Analysis loading screen (queue position, steps) | `Progress` plus a step list; `Skeleton` while loading |
| Ask box and answer | `Textarea`, `Button`; the answer ends with the disclaimer |
| Quota messages ("3 of 3 used this month") | `Alert` |
| Sign-in, admin settings | `Input`, `Label`, `Button` |

## Accessibility

- Text and badges meet WCAG AA contrast in both themes.
- Every interactive element is reachable by keyboard and shows the focus ring (`ring` token); Base UI handles this for its primitives.
- Badges and trends carry text or arrows, not colour alone.
- Tables have header cells; numbers are announced with their units.

## Open questions

| Question | Affects |
| --- | --- |
| Dark mode: follow the system, add a toggle, or light only for the hackathon | Every page |
| Charts library (D06) | IPO trends, track record, stock results |
| Product name (D13) | Header, page titles, metadata |
| Brand colour, or stay on the neutral base | `--primary` and the header |
| Base UI or Radix primitives. Base UI composes with a `render` prop, Radix with `asChild`; most shadcn examples use Radix | Every component; cheapest to switch now |
