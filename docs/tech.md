# Tech stack

What the product is built with: languages, frameworks, services and tooling, layer by layer.

- How the parts fit together and why: [arch.md](arch.md) and [adr/](adr/README.md)
- The database schema: [db.md](db.md)
- The AI design: [ai.md](ai.md)

Status labels (**Running**, **Decided**, **Proposed**, **Open**) are defined in [docs/README.md](README.md#status-labels).

## At a glance

| Layer | Choice | Status | ADR |
| --- | --- | --- | --- |
| IPO research runtime | Claude Code routine on the personal Pro account, cloud environment with a network allowlist, scheduled; IPOs only | Running | [0003](adr/0003-research-on-a-schedule.md), [0017](adr/0017-gemini-for-stocks-claude-for-ipos.md) |
| Stock research runtime | Stock worker: GitHub Actions workflow, dispatched by the app and on a schedule; its fetcher layer is built in 014 (`stock_worker/`, Python, standard library) | Decided; fetchers built | [0017](adr/0017-gemini-for-stocks-claude-for-ipos.md), [0018](adr/0018-stock-worker-on-github-actions.md), [0026](adr/0026-stock-worker-code-location.md) |
| Research models | Claude Sonnet 5.5 for IPOs (running); Gemini, free tier, for stocks (decided; model Open) | Running / Decided | [0017](adr/0017-gemini-for-stocks-claude-for-ipos.md) |
| Research code | Python 3, standard library only | Running | [0002](adr/0002-standard-library-only-agent.md) |
| PDF text | `pdftotext` (poppler-utils), `pypdf` as fallback | Running | — |
| Research store | Git repo (`analysis/`, `reports/`, `data/`) | Running | [0011](adr/0011-git-as-the-hand-off.md) |
| Owner's brief | Gmail connector on the routine's Claude account | Running | [0005](adr/0005-email-rendered-from-json.md) |
| Web framework | Next.js: pages and API routes in one app | Decided | [0009](adr/0009-nextjs-web-platform.md) |
| Web language | TypeScript, strict mode | Running | [0023](adr/0023-typescript-strict.md) |
| Database | PostgreSQL on Neon (free tier) | Running | [0010](adr/0010-postgresql-on-neon.md) |
| ORM and migrations | Drizzle ORM, drizzle-kit migrations, on Neon's serverless driver | Running | [0025](adr/0025-drizzle-on-neon-serverless-driver.md) |
| Auth | Better Auth (Drizzle adapter), sessions in Postgres; email and password, admin invites only | Running | [0028](adr/0028-better-auth-invite-only.md) |
| Account email | Resend: invites and password resets only | Running | [0028](adr/0028-better-auth-invite-only.md) |
| UI components and styling | shadcn/ui (Base UI) with Tailwind CSS v4; rules in [design.md](design.md) | Running | [0020](adr/0020-shadcn-ui.md) |
| Charts | shadcn/ui `chart` on Recharts, added with the first chart page | Decided | [0027](adr/0027-shadcn-charts-on-recharts.md) |
| Sync | GitHub Actions: import on push | Decided | [0011](adr/0011-git-as-the-hand-off.md) |
| In-app AI (Ask) | Gemini API, free tier | Decided (model Open) | [0014](adr/0014-gemini-free-api-for-ask.md) |
| Email | Admin's brief only, through the Gmail connector; no email to users | Decided | [0015](adr/0015-email-to-admin-only.md) |
| Hosting | Not chosen yet; local until week 4 | Open | — |
| Agent tests | Python `unittest`; run with `python3 -m unittest discover -s tests` | Running | — |
| App tests | Vitest with React Testing Library (jsdom), `npm test` in `web/`; database tests on a Neon branch per run (`npm run test:db`, task 007) | Running | [0024](adr/0024-vitest-for-app-tests.md) |
| App lint | oxlint with its React, Next.js, jsx-a11y, import, TypeScript and Vitest plugins (`web/.oxlintrc.json`); ESLint's TypeScript parser doesn't support TypeScript 7 | Running | — |
| CI | GitHub Actions on every push and pull request (`.github/workflows/ci.yml`): the `tests` job runs the agent tests, the schema check and the figures check (`ipo_agent/figures_check.py`); the `web` job runs the app's lint, type check, tests, a schema-drift check (`npx drizzle-kit generate` must be a no-op) and build; the `db` job runs `npm run test:db` on a Neon branch (`NEON_API_KEY` secret, `NEON_PROJECT_ID` variable) | Running | — |
| Dev tooling | DeepSeek through OpenRouter (plans and builds; model in `OPENROUTER_MODEL_NAME`), run by `.claude/deepseek/deepseek.py`; Claude Code, Opus 5.5 (runs the loop, reviews plans and code) | Running | [0021](adr/0021-deepseek-on-openrouter.md) |

## Research agent

| Item | Detail |
| --- | --- |
| Language | Python 3; standard library only (`urllib`, `http.cookiejar`, `json`, `gzip`, `zipfile`, `subprocess`, `statistics`, `zoneinfo`, `html`) |
| External tools | `pdftotext` from poppler-utils; `pypdf` only if `pdftotext` is missing |
| Entry points | `python3 -m ipo_agent.<module>`: `snapshot`, `quiet`, `rhp`, `outcomes`, `trends`, `email_render`; `nse_stock_smoke` is a development probe, not a routine entry point. Stock worker (014): `python3 -m stock_worker` (dev print of one symbol's records), `python3 -m stock_worker.probe` (the one-off quote probe the human runs once) |
| Packaging | None needed; the routine's setup script installs only poppler-utils and `pypdf` ([SETUP.md](../SETUP.md)) |
| Runtime | Claude Code cloud environment; network allowlist for NSE, NSE archives, Investorgain, SEBI and BSE |
| Schedule | Weekdays 09:07 and 19:07 IST |
| Output | JSON, Markdown, HTML and text files committed to `main` |

Module by module: [arch.md § IPO routine](arch.md#41-ipo-routine-running). The stock worker's fetchers (`stock_worker/`, 014) reuse `net.py` for HTTP: [arch.md § Stock worker](arch.md#42-stock-worker-decided).

## Web platform

| Item | Detail | Status |
| --- | --- | --- |
| Framework | Next.js: server-rendered pages for IPOs, track record and stocks; API routes for the watchlist, analysis requests and progress, Ask, admin settings and worker dispatch | Decided |
| Language | TypeScript, with strict mode ([ADR-0023](adr/0023-typescript-strict.md)) | Running |
| Data access | Drizzle ORM; drizzle-kit for versioned migrations ([ADR-0025](adr/0025-drizzle-on-neon-serverless-driver.md)) | Running |
| Database driver | `@neondatabase/serverless`: HTTP for queries, WebSocket `Pool` for interactive transactions; connection in `web/lib/db.ts` ([ADR-0025](adr/0025-drizzle-on-neon-serverless-driver.md)) | Running |
| Auth | Better Auth with its Drizzle adapter and database sessions. Email and password only; sign-up is off and the admin invites users. Invite and reset links are sent with the `resend` SDK behind a small mail module that tests replace ([ADR-0028](adr/0028-better-auth-invite-only.md)) | Running |
| AI | Google Gen AI SDK for the Gemini API, server side only, one module per side: the app's is TypeScript in `web/lib/`, the worker's is Python in `stock_worker/` (020) ([ADR-0026](adr/0026-stock-worker-code-location.md)) | Decided |
| UI | shadcn/ui components in `web/components/ui/`, Tailwind CSS v4, theme in `web/app/globals.css`; see [design.md](design.md) | Running |
| Charts | shadcn/ui `chart` (`web/components/ui/chart.tsx`, added by the first chart task) on Recharts, coloured by the `--chart-*` tokens; client components fed plain arrays by server pages. For GMP and subscription trends, results trends and the track record ([ADR-0027](adr/0027-shadcn-charts-on-recharts.md)) | Decided |
| Tests | Vitest, React Testing Library, jsdom; tests in `web/tests/` ([ADR-0024](adr/0024-vitest-for-app-tests.md)) | Running |
| Lint and type check | oxlint (`npm run lint`), `tsc --noEmit` (`npm run typecheck`) | Running |
| Product name and disclaimer | `web/lib/site.ts`: the name is a placeholder until D13; the footer shows the disclaimer on every page | Running |

## Infrastructure

| Service | Used for | Tier | Status |
| --- | --- | --- | --- |
| Anthropic: Claude Code routine | IPO research only | Personal Claude Pro plan (existing; nothing extra paid) | Running |
| Google: Gemini API | Ask | Free tier: per-project quotas (check AI Studio); prompts may be used by Google | Decided |
| GitHub | Repo, Actions (import, CI, stock worker) | Free: about 2,000 Actions minutes a month for a private repo (third-party sources; check GitHub's billing page) | Repo and CI running; import and stock worker decided |
| Resend | Account emails: invites and password resets | Free tier; needs a verified sending domain | Running |
| Neon | PostgreSQL; branch per test run and preview | Free: 1 GB per project, 100 compute-hours a month, pauses when idle | Decided |
| App host | Next.js | Not chosen yet | Open |

## Configuration and secrets

Names; values are never committed. The app's variables are listed, empty, in `web/.env.example`; a test keeps that file in step with this table. `AUTH_SECRET`, `RESEND_API_KEY` and `EMAIL_FROM` are required in production (task 010 fails fast at server start without them); locally and in tests, a missing mail key means print-mode email and a dev-only `AUTH_SECRET` fallback.

| Variable | Used by | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | App, import Action, stock worker | Neon connection, pooled (a different branch per environment). Locally, `neon checkout dev` writes it to `web/.env.local` |
| `DATABASE_URL_UNPOOLED` | App: drizzle-kit migrations | The same branch's direct connection; migrations can't run through the pooler |
| `NEON_API_KEY` | CI | Neon API key scoped to the project, so CI can create a database branch per test run (Actions secret) |
| `NEON_PROJECT_ID` | CI | The Neon project, `dark-field-33023581` (Actions variable, not secret) |
| `GEMINI_API_KEY` | App, stock worker | Ask; stock analyses and summaries |
| `AUTH_SECRET` | App | Session signing; required in production (missing → the server fails at start) |
| `RESEND_API_KEY` | App | Sends invite and password-reset emails; required in production |
| `EMAIL_FROM` | App | The from-address for account emails, on the domain verified in Resend; required in production |
| `AUTH_URL` | App | The app's public URL — Better Auth's `baseURL` and the same-origin target for the app's own cookie-authenticated routes (task 010) |
| `GITHUB_DISPATCH_TOKEN` | App | Fine-grained token that can only dispatch the stock worker workflow |
| `config/delivery.json` | Routine | The admin's email address for the brief (running) |
| `OPENROUTER_API_KEY` | Dev tooling: `.claude/deepseek/deepseek.py` | DeepSeek through OpenRouter. In the main checkout's `.env.local` (gitignored); never in CI (running) |
| `OPENROUTER_MODEL_NAME` | Dev tooling: `.claude/deepseek/deepseek.py` | The DeepSeek model, e.g. `deepseek/deepseek-v4-flash-0731`. In `.env.local` (running) |

## Repository layout

| Path | Contents | Status |
| --- | --- | --- |
| `ipo_agent/` | Python research agent | Running |
| `stock_worker/` | NSE stock fetchers (014): quote probe, results, announcements, shareholding, pledges; standard library, reusing `ipo_agent/net.py` | New in 014 ([ADR-0026](adr/0026-stock-worker-code-location.md)) |
| `analysis/`, `reports/`, `data/` | Research output (system of record) | Running |
| `docs/` | Project, architecture, stack, database, AI, sources, ADRs, plan | Running |
| `CLAUDE.md`, `ROUTINE.md` | Instructions for Claude (routine and reviewer) | Running |
| `AGENTS.md` | Rules for every coding agent (DeepSeek through OpenRouter) | Running |
| `docs/tasks/` | Task plans, reviews and responses | Running |
| `.claude/` | Claude Code skills, subagents, hooks, the DeepSeek driver (`.claude/deepseek/`), and their tests | Running |
| `tests/` | Agent tests (`python3 -m unittest discover -s tests`, saved fixtures only) | Running |
| `web/` | Next.js app, the Drizzle schema (`web/db/schema.ts`) and its checked-in migrations (`web/db/migrations/`); accounts: Better Auth config and guards (`web/lib/auth.ts`, `web/lib/auth-guard.ts`), the single mail module (`web/lib/mail.ts`), the sign-in / forgot-password / reset-password pages, the admin invite page and route, and the first-admin CLI (`web/scripts/first-admin.mjs`); import script to come | Running ([ADR-0022](adr/0022-web-app-in-same-repo.md)) |
| `.github/workflows/` | CI (`ci.yml`) and the NSE stock smoke test (`nse-stock-smoke.yml`) running; the import Action decided | Running / Decided |

## Local setup

The research agent needs Python 3 and poppler-utils:

```bash
python3 -m ipo_agent.snapshot --print       # numbers → data/latest.{json,md}
python3 -m ipo_agent.quiet AM               # quiet run, or prints why Claude is needed
python3 -m ipo_agent.rhp <SYMBOL|url>       # extract RHP sections
python3 -m ipo_agent.outcomes --no-fetch    # listing scorecard
python3 -m ipo_agent.email_render reports/<date>-<am|pm>.json
python3 -m ipo_agent.nse_stock_smoke --dry-run   # print the NSE stock smoke URLs without calling NSE
python3 -m stock_worker --dry-run                 # print the planned NSE stock calls for one symbol
python3 -m stock_worker.probe                     # one-off quote probe (014; run once by the human)
```

Scheduled routine setup: [SETUP.md](../SETUP.md). The web app (`web/`) needs Node.js 22.22 or later, or 24.15 or later (Vitest's jsdom needs it; CI uses 24):

```bash
cd web
npm ci                  # install from the lockfile
cp .env.example .env.local   # optional: nothing reads these yet
npm run dev             # http://localhost:3000
npm run lint            # oxlint
npm run typecheck       # tsc --noEmit
npm test                # Vitest, once; npm run test:watch to rerun on save
npm run build           # production build
```
