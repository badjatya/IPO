# Code review: 006-web-scaffold

## Round 1 (2026-10-29)

**Verdict:** Approved (self-check: Claude Code built this task at the human's request, so this is not an independent review)

**Diff:** `git diff main...task/006-web-scaffold` at `f76774b`

**Tests:** run from the worktree after a clean `npm ci`. Lint, type check, 7 Vitest tests, build and the 227 agent tests all pass; output in [plan.md § Verification](plan.md#verification).

### Findings

| # | Severity | Where | Problem (what breaks, and when) | Suggested fix |
| --- | --- | --- | --- | --- |
| 1 | Minor | `.github/workflows/ci.yml` (`web` job) | `next build` downloads the Geist font from Google Fonts. A Google outage, or a runner without that access, fails the build step even when the code is fine | Follow-up if it ever flakes: self-host the font with `next/font/local` |
| 2 | Minor | `web/tests/layout.test.tsx` | Vitest can't render async Server Components, so the "every page shows the disclaimer" test covers the layout, not each real page. That is enough while every page sits under the root layout. A page outside it (a separate root layout or route group) would bypass it | When a second root layout appears, add it to this test |

No Blocker or Major.

### Plan and docs

- Built as the plan describes. The three deviations (oxlint instead of ESLint, no `@vitejs/plugin-react`, the higher Node minimum) are recorded with reasons under "Changes during build".
- The checks against AGENTS.md hold:
  - no secrets (rule 11): `.env.example` is empty, and a test enforces it
  - research, not advice (rule 7): the footer is in the layout and tested
  - no open question picked in code (rule 12): D01, D02 and D07 were decided by the human, and D13 stays a placeholder
- tech.md, design.md, arch.md and the ADR index are updated, with status labels.
- The roadmap changes are listed under "Doc updates" for `main`.
