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
| Stock research runtime | Stock worker: GitHub Actions workflow, dispatched by the app and on a schedule | Decided | [0017](adr/0017-gemini-for-stocks-claude-for-ipos.md), [0018](adr/0018-stock-worker-on-github-actions.md) |
| Research models | Claude Sonnet 5.5 for IPOs (running); Gemini, free tier, for stocks (decided; model Open) | Running / Decided | [0017](adr/0017-gemini-for-stocks-claude-for-ipos.md) |
| Research code | Python 3, standard library only | Running | [0002](adr/0002-standard-library-only-agent.md) |
| PDF text | `pdftotext` (poppler-utils), `pypdf` as fallback | Running | — |
| Research store | Git repo (`analysis/`, `reports/`, `data/`) | Running | [0011](adr/0011-git-as-the-hand-off.md) |
| Owner's brief | Gmail connector on the routine's Claude account | Running | [0005](adr/0005-email-rendered-from-json.md) |
| Web framework | Next.js: pages and API routes in one app | Decided | [0009](adr/0009-nextjs-web-platform.md) |
| Web language | TypeScript | Proposed | — |
| Database | PostgreSQL on Neon (free tier) | Decided | [0010](adr/0010-postgresql-on-neon.md) |
| ORM and migrations | Drizzle or Prisma | Open | — |
| Auth | Auth library for Next.js, sessions in Postgres | Open | — |
| UI components and styling | shadcn/ui (Base UI) with Tailwind CSS v4; rules in [design.md](design.md) | Running | [0020](adr/0020-shadcn-ui.md) |
| Charts | Not chosen yet | Open | — |
| Sync | GitHub Actions: import on push | Decided | [0011](adr/0011-git-as-the-hand-off.md) |
| In-app AI (Ask) | Gemini API, free tier | Decided (model Open) | [0014](adr/0014-gemini-free-api-for-ask.md) |
| Email | Admin's brief only, through the Gmail connector; no email to users | Decided | [0015](adr/0015-email-to-admin-only.md) |
| Hosting | Not chosen yet; local until week 4 | Open | — |
| Agent tests | Python `unittest`; run with `python3 -m unittest discover -s tests` | Running | — |
| App tests | Test runner not chosen yet; database tests on Neon branches | Open | — |
| CI | GitHub Actions: agent tests and the schema check on every push and pull request (`.github/workflows/ci.yml`) | Running | — |
| Dev tooling | DeepSeek in opencode (plans and builds); Claude Code, Opus 5.5 (reviews plans and code) | Running | [0019](adr/0019-deepseek-builds-claude-reviews.md) |

## Research agent

| Item | Detail |
| --- | --- |
| Language | Python 3; standard library only (`urllib`, `http.cookiejar`, `json`, `gzip`, `zipfile`, `subprocess`, `statistics`, `zoneinfo`, `html`) |
| External tools | `pdftotext` from poppler-utils; `pypdf` only if `pdftotext` is missing |
| Entry points | `python3 -m ipo_agent.<module>`: `snapshot`, `quiet`, `rhp`, `outcomes`, `trends`, `email_render`; `nse_stock_smoke` is a development probe, not a routine entry point |
| Packaging | None needed; the routine's setup script installs only poppler-utils and `pypdf` ([SETUP.md](../SETUP.md)) |
| Runtime | Claude Code cloud environment; network allowlist for NSE, NSE archives, Investorgain, SEBI and BSE |
| Schedule | Weekdays 09:07 and 19:07 IST |
| Output | JSON, Markdown, HTML and text files committed to `main` |

Module by module: [arch.md § IPO routine](arch.md#41-ipo-routine-running). The stock worker reuses `net.py` and the NSE client: [arch.md § Stock worker](arch.md#42-stock-worker-decided).

## Web platform

| Item | Detail | Status |
| --- | --- | --- |
| Framework | Next.js: server-rendered pages for IPOs, track record and stocks; API routes for the watchlist, analysis requests and progress, Ask, admin settings and worker dispatch | Decided |
| Language | TypeScript, with strict mode | Proposed |
| Data access | ORM with versioned migrations (Drizzle or Prisma) | Open |
| Database driver | Neon's serverless driver or standard Postgres driver, depending on the host | Open |
| Auth | An auth library for Next.js with a Postgres adapter; Google sign-in or password (no emailed links, because the app sends no email) | Open |
| AI | Google Gen AI SDK for the Gemini API, server side only, behind one module that the app (Ask) and the stock worker share | Decided |
| UI | shadcn/ui components in `web/components/ui/`, Tailwind CSS v4, theme in `web/app/globals.css`; see [design.md](design.md) | Running |
| Charts | GMP and subscription trends, results trends, the track record | Open |

## Infrastructure

| Service | Used for | Tier | Status |
| --- | --- | --- | --- |
| Anthropic: Claude Code routine | IPO research only | Personal Claude Pro plan (existing; nothing extra paid) | Running |
| Google: Gemini API | Ask | Free tier: per-project quotas (check AI Studio); prompts may be used by Google | Decided |
| GitHub | Repo, Actions (import, CI, stock worker) | Free: about 2,000 Actions minutes a month for a private repo (third-party sources; check GitHub's billing page) | Repo and CI running; import and stock worker decided |
| Neon | PostgreSQL; branch per test run and preview | Free: 1 GB per project, 100 compute-hours a month, pauses when idle | Decided |
| App host | Next.js | Not chosen yet | Open |

## Configuration and secrets

Names are planned; values are never committed.

| Variable | Used by | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | App, import Action, stock worker | Neon connection (a different branch per environment) |
| `GEMINI_API_KEY` | App, stock worker | Ask; stock analyses and summaries |
| `AUTH_SECRET` | App | Session signing |
| `GITHUB_DISPATCH_TOKEN` | App | Fine-grained token that can only dispatch the stock worker workflow |
| `config/delivery.json` | Routine | The admin's email address for the brief (running) |

## Repository layout

| Path | Contents | Status |
| --- | --- | --- |
| `ipo_agent/` | Python research agent | Running |
| `analysis/`, `reports/`, `data/` | Research output (system of record) | Running |
| `docs/` | Project, architecture, stack, database, AI, sources, ADRs, plan | Running |
| `CLAUDE.md`, `ROUTINE.md` | Instructions for Claude (routine and reviewer) | Running |
| `AGENTS.md` | Rules for every coding agent (DeepSeek in opencode) | Running |
| `docs/tasks/` | Task plans, reviews and responses | Running |
| `.claude/` | Claude Code skills, subagents, hooks and their tests | Running |
| `opencode.json`, `.opencode/` | DeepSeek's permissions, planner agent, workflow commands | Running |
| `tests/` | Agent tests (`python3 -m unittest discover -s tests`, saved fixtures only) | Running |
| `web/` | Next.js app, migrations, import script | Proposed (same repo; [arch.md § Open questions](arch.md#9-open-questions)) |
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
```

Scheduled routine setup: [SETUP.md](../SETUP.md). The web app (`web/`) needs Node.js 20.9 or later:

```bash
cd web
npm install
npm run dev      # http://localhost:3000
npm run build    # production build and type check
```
