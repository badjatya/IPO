# Architecture decision records

One file per decision: the context, the options weighed, what we chose and why, and what changed because of it. Each ADR says what Claude proposed and where the human overrode it. For decisions made before 2026-10-29, the split wasn't recorded, and the ADR says so.

Decisions made before the hackathon (0001–0008) were **recorded** on 2026-10-29 from the commits that made them; each ADR names its commit.

| ADR | Decision | Date | Status |
| --- | --- | --- | --- |
| [0001](0001-python-for-exact-work-claude-for-judgement.md) | Python for exact work, Claude for judgement | 2026-10-12 | Accepted |
| [0002](0002-standard-library-only-agent.md) | Research agent uses the Python standard library only | 2026-10-12 | Accepted |
| [0003](0003-research-on-a-schedule.md) | Research runs on a schedule, not on request | 2026-10-12 | Accepted (IPO research) |
| [0004](0004-analyse-once-and-cache.md) | Analyse each IPO once and cache it | 2026-10-14 | Accepted |
| [0005](0005-email-rendered-from-json.md) | Email rendered from Claude's JSON verdicts | 2026-10-12 | Accepted |
| [0006](0006-quiet-runs.md) | Quiet runs skip Claude | 2026-10-14 | Accepted |
| [0007](0007-listing-scorecard-as-eval.md) | Listing scorecard is the eval of the AI's calls | 2026-10-14 | Accepted |
| [0008](0008-mainboard-only.md) | Mainboard IPOs only; SME out of scope | 2026-10-12, reaffirmed 2026-10-29 | Accepted |
| [0009](0009-nextjs-web-platform.md) | Next.js for the web platform | 2026-10-29 | Accepted |
| [0010](0010-postgresql-on-neon.md) | PostgreSQL on Neon | 2026-10-29 | Accepted |
| [0011](0011-git-as-the-hand-off.md) | Git is the hand-off; the database copy of research is rebuildable | 2026-10-29 | Accepted |
| [0012](0012-research-not-advice.md) | Research, not advice, for listed stocks | 2026-10-29 | Accepted |
| [0013](0013-shared-per-stock-research.md) | Research is per stock and shared across users | 2026-10-29 | Accepted |
| [0014](0014-gemini-free-api-for-ask.md) | Gemini API (free tier) for in-app Ask | 2026-10-29 | Accepted |
| [0015](0015-email-to-admin-only.md) | Email goes to the admin only; no user emails | 2026-10-29 | Superseded by 0028 |
| [0016](0016-on-demand-stock-analysis.md) | On-demand stock analysis through the Claude routine | 2026-10-29 | Superseded by 0017 |
| [0017](0017-gemini-for-stocks-claude-for-ipos.md) | Claude for IPOs only; Gemini for all stock work; every analysis request counts | 2026-10-29 | Accepted |
| [0018](0018-stock-worker-on-github-actions.md) | Stock worker runs on GitHub Actions | 2026-10-29 | Accepted |
| [0019](0019-deepseek-builds-claude-reviews.md) | DeepSeek plans and builds; Claude reviews the plan and the code | 2026-10-29 | Superseded by 0021 |
| [0020](0020-shadcn-ui.md) | shadcn/ui and Tailwind CSS for the web app | 2026-10-29 | Accepted |
| [0021](0021-deepseek-on-openrouter.md) | DeepSeek runs through OpenRouter, driven by Claude Code | 2026-10-29 | Accepted |
| [0022](0022-web-app-in-same-repo.md) | The web app lives in this repo, in `web/` | 2026-10-29 | Accepted |
| [0023](0023-typescript-strict.md) | TypeScript in strict mode for the web app | 2026-10-29 | Accepted |
| [0024](0024-vitest-for-app-tests.md) | Vitest and Testing Library for the web app's tests | 2026-10-29 | Accepted |
| [0025](0025-drizzle-on-neon-serverless-driver.md) | Drizzle ORM on Neon's serverless driver | 2026-10-29 | Accepted |
| [0026](0026-stock-worker-code-location.md) | Stock worker code lives in `stock_worker/`, standard library first | 2026-10-30 | Accepted |
| [0027](0027-shadcn-charts-on-recharts.md) | shadcn/ui charts, on Recharts, for the web app | 2026-10-30 | Accepted |
| [0028](0028-better-auth-invite-only.md) | Better Auth, invite-only password sign-in, account emails through Resend | 2026-10-30 | Accepted |
| [0029](0029-alert-thresholds-and-severities.md) | Alert thresholds and severities in code (D10); FII/DII parsing is task 027 | 2026-10-30 | Accepted |
| [0030](0030-first-admin-bootstrap.md) | First admin is a CLI script; one 24-hour expiry for invite and reset links | 2026-10-30 | Accepted |

## Adding one

1. Copy [template.md](template.md) to `NNNN-short-title.md` with the next number.
2. Claude drafts the context and options; the human decides.
3. Fill in "AI involvement" honestly, including overrides.
4. Add a row above, and update [arch.md § Decisions](../arch.md#8-decisions) in the same commit.
5. Never edit an accepted decision's outcome. Supersede it with a new ADR and set the old one's status to "Superseded by ADR-NNNN".

Still to decide, each to become an ADR: host.
