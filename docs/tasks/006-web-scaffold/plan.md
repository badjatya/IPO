---
task: 006-web-scaffold
status: merge-ready
branch: task/006-web-scaffold
assigned_by: Vijay
planner: Claude Code (Opus 5.5), at the human's request
reviewer: Claude Code (self-check; no independent review)
---

# 006: Web app scaffold

## Task

> Task 006 from docs/tasks/ROADMAP.md:
>
> ### 006 · Web app scaffold
>
> The Next.js app ([ADR-0009](../../adr/0009-nextjs-web-platform.md)) in the location chosen in D01, with the language from D02, the UI kit from D05 and the test runner from D07. It has a base layout with "not investment advice" on every page, a product-name placeholder (D13), environment variables named as in tech.md, lint and test scripts, and a CI job.
>
> A bare app already exists in `web/` (commits c835c42 and 33c5a73): Next.js with strict TypeScript, shadcn/ui on Tailwind CSS v4, and the disclaimer footer. This task builds on it rather than starting over.
>
> - **Done when:** the app starts locally and shows an empty home page with the disclaimer; its tests run in CI; `tech.md` has the local setup and updated status labels.
> - **Out of scope:** database, auth, real pages.

The human then said: "claude you do it right now". `/run-task 006` couldn't start DeepSeek (no `.env.local` with the OpenRouter key), so Claude Code planned and built the task itself, as AGENTS.md allows when the human asks. There was no DeepSeek plan, and so no plan review; this file records the plan as built.

## Goal and scope

- **In scope:**
  - The existing `web/` app, kept as it is: Next.js 16, strict TypeScript 7, shadcn/ui on Tailwind CSS v4.
  - `web/lib/site.ts`: the product-name placeholder (`PRODUCT_NAME`, D13), the description and the disclaimer text, in one place.
  - `web/components/site-footer.tsx`: the disclaimer footer, rendered by `web/app/layout.tsx` on every page. The home page shows only the product name.
  - `web/.env.example`: the app's variables from tech.md (`DATABASE_URL`, `GEMINI_API_KEY`, `AUTH_SECRET`, `GITHUB_DISPATCH_TOKEN`), all empty.
  - Tests with Vitest and React Testing Library, plus lint (oxlint) and type-check scripts.
  - A `web` job in `.github/workflows/ci.yml`: `npm ci`, lint, type check, tests, build.
  - ADRs for D01, D02 and D07, and updates to tech.md, design.md, arch.md and the ADR index.
- **Out of scope:** database, auth, real pages, the header and navigation, dark mode, and code that reads the environment variables.

## Context read

- `docs/tasks/ROADMAP.md` § 006 and the decisions table: D01, D02 and D07 were open, D05 decided ([ADR-0020](../../adr/0020-shadcn-ui.md)).
- [tech.md](../../tech.md): status labels, the variable names, and the local setup to update.
- [design.md](../../design.md): the footer rule (in the layout, not page code), the D13 placeholder, and token-only colours.
- [arch.md § 4.4](../../arch.md#44-nextjs-app-decided), § 8 and § 9: the app's modules, the ADR list, and "same repo or separate repo" as an open question.
- [ADR-0012](../../adr/0012-research-not-advice.md): "not investment advice" on every page.
- `.github/workflows/ci.yml`: one `tests` job. The routine pushes to `main` twice a day, so the new job has to be fast and read-only.
- `web/`: layout, page, tsconfig (`strict: true`), `package.json` (TypeScript `^7.0.2`, no test or lint scripts).

## Approach

- Keep the bare app and move the two strings every page shares, the product name and the disclaimer, into `lib/site.ts`. Later pages then import them instead of copying them, and D13 becomes a one-line change.
- Test the rule that matters most: the root layout renders the disclaimer around any page. `next/font/google` is mocked, because it only works inside the Next.js compiler. The layout renders `<html>`, so the test uses `react-dom/server`'s `renderToStaticMarkup` rather than mounting into jsdom.
- Guard rule 11 (no secrets in git) and drift from tech.md with a test. `.env.example` must hold exactly the variables whose tech.md row names the App, and every value must be empty.
- Use oxlint for lint (see "Changes during build"). It runs with its React (including the hooks rules), Next.js, jsx-a11y, import, TypeScript and Vitest plugins, and any warning fails the run.
- CI gets its own `web` job, so a web failure doesn't hide the agent results and the reverse. Each step after `npm ci` runs even if an earlier one failed (`!cancelled()`), as in the `tests` job.

## Steps

| # | Step | Files | Test that proves it |
| --- | --- | --- | --- |
| 1 | Shared product name and disclaimer; footer component; layout and home page use them | `web/lib/site.ts`, `web/components/site-footer.tsx`, `web/app/layout.tsx`, `web/app/page.tsx` | `tests/layout.test.tsx` |
| 2 | Vitest with jsdom, Testing Library and jest-dom matchers; `@/` alias | `web/vitest.config.mts`, `web/tests/setup.ts`, `web/package.json` | `npm test` |
| 3 | `.env.example` with the app's variable names | `web/.env.example` | `tests/env-example.test.ts` |
| 4 | Lint and type-check scripts | `web/.oxlintrc.json`, `web/package.json` | `npm run lint`, `npm run typecheck`; a throwaway file with a conditional hook and a bare `<img>` fails lint |
| 5 | CI job | `.github/workflows/ci.yml` | Clean `npm ci` followed by every step, run locally |
| 6 | ADRs and docs | `docs/adr/0022…0024`, `docs/adr/README.md`, `docs/arch.md`, `docs/tech.md`, `docs/design.md` | Read-through |

## Data and AI

None.

## Doc updates

Made on this branch:

- ADR-0022 (the app lives in this repo, in `web/`), ADR-0023 (strict TypeScript) and ADR-0024 (Vitest). All three are Accepted: the human chose each option during this task. They are added to the ADR index and [arch.md § 8](../../arch.md#8-decisions).
- arch.md § 9: removed "Same repo or separate repo for the app". The ADR index's "still to decide" list drops it too.
- tech.md:
  - Web language, App tests and `web/` become Running.
  - New rows for app lint, tests, lint and type check, and the product-name module.
  - The CI row names both jobs.
  - Local setup lists Node 22.22+ or 24.15+ (jsdom's minimum) and the new scripts.
  - `.env.example` is mentioned under Configuration.
- design.md: the footer now lives in `components/site-footer.tsx`, placed by the layout, and the D13 placeholder is `PRODUCT_NAME`.

For Claude on `main` after merge (`docs/tasks/ROADMAP.md`):

- Tick D01 (same repo, ADR-0022), D02 (strict TypeScript, ADR-0023) and D07 (Vitest, ADR-0024).
- 006 → Done, with a short summary like the other done tasks. 007 and 011 stay blocked on their other dependencies.
- "Already in place": update the bare-web-app row. Tests, lint and CI now exist.
- 002's "For 005 and 006" note: 006 added its CI job (`web`).
- 006's "Watch for" note about `npm install` no longer applies. Claude installed the packages because it built the task.
- Add the task's entry to the AI journal in `docs/plan.md`.

## Decisions needed

All three were decided by the human during this task (asked with AskUserQuestion, recommended option first):

| ID | Options | Human's choice |
| --- | --- | --- |
| D01 | Same repo `web/` (recommended); separate repo | Same repo, `web/` |
| D02 | TypeScript strict (recommended); plain JavaScript | TypeScript, strict |
| D07 | Vitest + Testing Library (recommended); Jest + Testing Library; Node's test runner; Playwright only | Vitest + Testing Library |

## Risks and rollback

- **CI time:** the `web` job adds about a minute per push, including the routine's. It runs in parallel with `tests` and has its own 5-minute timeout.
- **`next build` in CI fetches the Geist font from Google.** If Google Fonts is unreachable, the build step fails. The lint, type and test steps still report.
- **TypeScript 7 and tooling:** typescript-eslint doesn't support it yet, hence oxlint. If a later tool needs the TypeScript JS API, pin TypeScript to 6.0 and revisit.
- **Async Server Components** can't be rendered by Vitest. Pages that fetch data will need end-to-end tests or tests of their data functions ([ADR-0024](../../adr/0024-vitest-for-app-tests.md)).
- **Rollback:** revert the two code and docs commits. Nothing outside `web/`, `ci.yml` and `docs/` changed.

## Revisions

| Round | What changed | In answer to |
| --- | --- | --- |

## Changes during build

- **oxlint instead of ESLint.** `eslint-config-next` loads typescript-eslint, which refuses TypeScript 7 ("typescript-eslint does not support TS 7.0"; its peer range is `>=4.8.4 <6.1.0`). The bare app ships TypeScript `^7.0.2`, and `next build` and `tsc` both work with it. Downgrading TypeScript only for lint seemed the worse trade, so ESLint and `eslint-config-next` were uninstalled and oxlint added.
  - Two side-effect imports are allowed by name in `import/no-unassigned-import`: CSS files and the jest-dom setup.
  - oxlint has its own React-hooks, Next.js and jsx-a11y rules.
- **No `@vitejs/plugin-react`.** It failed to install with a peer conflict on `@babel/core` 8. Vite 8 compiles TSX with the automatic JSX runtime without it.
- **Node version.** jsdom 30 needs Node `^22.22.2 || ^24.15.0 || >=26`, so tech.md's local setup moves from 20.9 to those versions. CI uses Node 24.
- **`npm audit`** still reports the 3 low-severity `deepmerge` issues through the `shadcn` CLI, recorded in ADR-0020. Nothing new.

## Verification

From the worktree, after a clean `rm -rf node_modules .next && npm ci`:

```text
$ cd web && npm run lint
> oxlint --deny-warnings
(no findings)

$ npm run typecheck
> tsc --noEmit
(no errors)

$ npx vitest run --reporter=verbose
 ✓ tests/env-example.test.ts > .env.example > lists exactly the app's variables from tech.md
 ✓ tests/env-example.test.ts > .env.example > holds no values, so no secret lands in git
 ✓ tests/layout.test.tsx > disclaimer > says the research is not investment advice
 ✓ tests/layout.test.tsx > disclaimer > is in the footer
 ✓ tests/layout.test.tsx > disclaimer > is in the root layout, so every page shows it
 ✓ tests/layout.test.tsx > home page > shows the product name as its heading
 ✓ tests/layout.test.tsx > home page > uses the product name as the page title
 Test Files  2 passed (2)
      Tests  7 passed (7)

$ npm run build
✓ Compiled successfully
Route (app)
┌ ○ /
└ ○ /_not-found

$ npx next start -p 3906   # then curl the home page
<title>IPO Research</title>
<h1 class="text-2xl font-semibold tracking-tight">IPO Research</h1>
<footer class="border-t px-4 py-3 text-center text-xs text-muted-foreground">Research, not investment advice.</footer>

$ cd .. && python3 -m unittest discover -s tests
Ran 227 tests in 0.517s
OK
```

The tests fail when they should:

- Changing `DISCLAIMER` to "Research." failed 2 of the 7 tests (the wording test and the layout test).
- A throwaway component with a conditional `useState` and a bare `<img>` failed lint with `react-hooks(rules-of-hooks)`, `jsx-a11y(alt-text)` and `next(no-img-element)`.

The CI job itself runs on the first push of this branch or after merge. It hasn't run yet.
