# ADR-0022: The web app lives in this repo, in `web/`

- **Status:** Accepted
- **Decided:** 2026-10-29 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

The Next.js app ([ADR-0009](0009-nextjs-web-platform.md)) needs a home (roadmap decision D01, [arch.md § 9](../arch.md#9-open-questions)). Its database copy of research is rebuilt from the files in `analysis/`, `reports/` and `data/` ([ADR-0011](0011-git-as-the-hand-off.md)), and the import Action runs on push to this repo. A bare app was already created in `web/` (commit `c835c42`).

## Options

| Option | For | Against |
| --- | --- | --- |
| **Same repo, `web/`** | The import script reads the research files directly; one CI workflow; one place for docs, tasks and ADRs; the bare app is already there | The routine's twice-daily pushes to `main` also run the app's CI job |
| Separate repo | The app's history and CI are apart from the routine's commits | The import needs a cross-repo checkout or token; docs and tasks split across two repos; the bare app has to move |

## Decision

The web app stays in this repo, in `web/`.

## Consequences

- `.github/workflows/ci.yml` has a `web` job beside the agent tests; it also runs on the routine's pushes, so it has to stay fast and read-only.
- The import Action (task 009) can read `analysis/`, `reports/` and `data/` from the same checkout.
- `ipo_agent/` stays standard-library Python ([ADR-0002](0002-standard-library-only-agent.md)); the app's npm dependencies live only under `web/`.

## AI involvement

Claude Code laid out the two options with "same repo" as the recommendation, as [tech.md](../tech.md#repository-layout) already proposed; the human chose it during task 006.

## Evidence

- `web/`, `.github/workflows/ci.yml`; task [006](../tasks/006-web-scaffold/plan.md)
