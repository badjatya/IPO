# ADR-0005: Email rendered from Claude's JSON verdicts

- **Status:** Accepted
- **Decided:** 2026-10-12 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

The first briefs were Markdown written by Claude end to end (`reports/2026-10-12-pm.md`, removed in `c09248d`). With the model writing the whole brief, the layout depends on the run, numbers are retyped by the model, and every word of a long email costs tokens.

## Options

| Option | For | Against |
| --- | --- | --- |
| Claude writes the whole email | Flexible | Layout drifts; retyped numbers can be wrong; more tokens |
| **Claude writes JSON verdicts; Python renders HTML and text** | Same layout every day; numbers come straight from the snapshot; Claude writes a few strings | A schema to maintain |

## Decision

Claude writes `reports/<date>-<am|pm>.json`. `email_render.py` merges each entry over the IPO's card and the snapshot numbers, and renders the HTML and plain-text email.

## Consequences

- Design changes, like the Gmail-safe backgrounds in `b423c4a`, are code changes with no prompt changes.
- The same JSON feeds the database and the web app.

## AI involvement

Built in Claude Code (Opus 5.5) sessions; the commit carries a Claude co-author trailer. Who proposed what in those sessions was not recorded at the time. This ADR was written afterwards, from the commit and the code.

## Evidence

- Commit `c09248d` (designed HTML email from Claude's JSON verdicts)
- Schema at the top of `ipo_agent/email_render.py`

