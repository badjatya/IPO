# ADR-0026: Stock worker code lives in `stock_worker/`, standard library first

- **Status:** Proposed
- **Decided:** 2026-10-29 · **Recorded:** 2026-10-30
- **Deciders:** Vijay · **Drafted with:** DeepSeek (deepseek-v4-flash-0731, OpenRouter) in task 014; reviewed by Claude Code

## Context

Roadmap decision D09: where the stock worker's Python code lives, and how it takes dependencies. Task 003 proved the NSE stock endpoints; the worker (task 018) will run on GitHub Actions ([ADR-0018](adr/0018-stock-worker-on-github-actions.md)) and write to the app's Postgres, and the analyses will be written by Gemini. The IPO routine's standard-library rule ([ADR-0002](adr/0002-standard-library-only-agent.md)) binds `ipo_agent/` only, so the worker's code can do things `ipo_agent/` cannot — but the fetcher layer (task 014) needs no third-party packages.

There is also a Gemini wrinkle: [tech.md](../tech.md) said "one module that the app (Ask) and the stock worker share". The app is TypeScript (`web/lib/`), the worker is Python, so one module cannot serve both sides.

## Options

| Option | For | Against |
| --- | --- | --- |
| **A — new top-level `stock_worker/` package, standard-library only in 014** | `ipo_agent/` stays the IPO routine untouched and ADR-0002 intact; the package can later declare pinned dependencies (Postgres driver, Gemini SDK) through its own requirements file | A second Python package to keep in mind |
| B — extend `ipo_agent/` with a stock subpackage | No new package | ADR-0002 would bind the worker to the standard library forever, blocking the Postgres driver and Gemini SDK later; one package for two runtimes gets confusing |

## Decision

The stock worker's Python code lives in a new top-level package `stock_worker/`, importing `ipo_agent.net` for HTTP. Task 014 (the fetchers) uses the standard library only. Later tasks bring the package's own pinned third-party packages through the package's own requirements file, each dependency named in that task's plan: the Postgres driver in 018, the Python Gemini SDK in 020.

tech.md's "one module shared by the app and the worker" becomes one module per side: the app's Gemini module is TypeScript in `web/lib/`, the worker's is Python in `stock_worker/` (020).

## Consequences

- `ipo_agent/` stays the IPO routine, untouched; ADR-0002's standard-library rule binds it alone.
- 014 ships a calibrated, tested fetcher layer nothing calls yet: `stock_worker/` with `results.py`, `announcements.py`, `shareholding.py`, `pledges.py`, the quote probe (`probe.py`), and `fetchers.py` orchestration.
- 018 adds the Postgres driver through the package's own requirements file; 020 adds the Gemini SDK the same way. Each such task names its dependencies in its plan.
- The human accepts this ADR to tick D09 on the roadmap.

## AI involvement

The plan asked the human to choose the location (D09) at plan review, with option A recommended. The human chose A, including the dependency rule and the Python/TypeScript Gemini split; DeepSeek wrote both halves into the plan and this ADR.

## Evidence

- `stock_worker/` (task 014: fetchers, probe, orchestration, tests)
- [docs/data-sources.md § NSE stock data](../data-sources.md#nse-stock-data), [docs/arch.md § 4.2](../arch.md#42-stock-worker-decided)
- tech.md's Gemini row now reads "one module per side".