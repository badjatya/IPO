# ADR-0002: Research agent uses the Python standard library only

- **Status:** Accepted
- **Decided:** 2026-10-12 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

The agent runs inside a fresh Claude Code cloud environment on every scheduled run. Anything it depends on has to be installed each time, and a failed install means a missed brief.

## Options

| Option | For | Against |
| --- | --- | --- |
| Common libraries (requests, BeautifulSoup, pandas) | Shorter code | Install on every run; more ways to fail; more to keep updated |
| **Standard library only**, plus `pdftotext` with a `pypdf` fallback | Nothing to install except PDF tools; starts fast; small attack surface | Hand-written HTTP client and parsers |

## Decision

The research agent uses only the Python standard library. The one exception is PDF text extraction: `pdftotext`, falling back to `pypdf`.

## Consequences

- `net.py` implements cookies, browser headers and retries itself.
- No database driver in the agent. This is one reason research reaches the database through git ([ADR-0011](0011-git-as-the-hand-off.md)).
- The rule covers the agent only. The web app has its own stack ([ADR-0009](0009-nextjs-web-platform.md)).

## AI involvement

Built in Claude Code (Opus 5.5) sessions; the commit carries a Claude co-author trailer. Who proposed what in those sessions was not recorded at the time. This ADR was written afterwards, from the commit and the code.

## Evidence

- `CLAUDE.md`: "Python standard library only"
- `SETUP.md`: setup script installs only poppler-utils and `pypdf`

