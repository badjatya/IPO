# IPO research agent

Daily research on Indian **mainboard** IPOs (no SME). When run as a scheduled routine, follow `ROUTINE.md` and skip the "Development sessions" section below.

- `python3 -m ipo_agent.snapshot --print` — fetch numbers (Investorgain list/GMP + NSE details/subscription) → `data/latest.{json,md}`
- `python3 -m ipo_agent.quiet <AM|PM>` — records new listings, then on a quiet run (nothing open/closing, nothing to research) writes `reports/<date>-<am|pm>.json` from the previous run's calls and renders the email; otherwise prints why Claude is needed
- `python3 -m ipo_agent.rhp <SYMBOL|url>` — extract key RHP sections → `analysis/rhp/` (RHP links come from NSE, or SEBI before NSE lists the issue)
- `python3 -m ipo_agent.outcomes` — listing-day scorecard: listing price/close vs GMP the night before, our call and final subscription → `data/outcomes.json`
- `python3 -m ipo_agent.trends` — GMP and subscription-by-day trends from `data/snapshots/` (the snapshot attaches them to each IPO; the email shows them)
- `ipo_agent/allotment.py` — category minimums and allotment odds (Retail / sNII / bNII)
- `analysis/<key>.md` — cached deep analysis per IPO (written once, reused)
- `analysis/<key>.json` — cached email card per IPO (`ipo_agent/cards.py`); the daily report only overrides what changed
- `reports/<date>-<am|pm>.json` — Claude's verdicts; `python3 -m ipo_agent.email_render <json>` renders the `.html` email + `.txt`
- `config/delivery.json` — email recipient (the admin)

Python standard library only; `pdftotext` (poppler-utils) is used for RHPs, with `pypdf` as a fallback.

## Development sessions

The repo is growing into a multi-user research app; start at `docs/README.md`.

Coding is split between agents ([ADR-0019](docs/adr/0019-deepseek-builds-claude-reviews.md)):

- **DeepSeek in opencode** plans and builds each task. Its rules are in `AGENTS.md`.
- **Claude Code reviews:** first the task's plan, then the finished code.
- **The human** assigns tasks, decides open questions, and merges.

When asked to review a task, use the `/review-plan NNN` or `/review-code NNN` skill. They follow these steps:

1. Work in the task's worktree `.worktrees/NNN-*/` (branch `task/NNN-*`); never check out a task branch in the main checkout. Read `AGENTS.md` (the rules both agents enforce), `docs/tasks/README.md` (the reviewer guide, statuses and severities), and the task folder `docs/tasks/NNN-*/` there.
2. Write `plan-review.md` or `code-review.md` from `docs/tasks/templates/`, as a new round section. Never rewrite an earlier round.
3. Set the `status:` line in the task's `plan.md`, and commit only the review file and that status change in the worktree (`git -C .worktrees/NNN-*`). Don't push.

Don't build a task assigned to DeepSeek unless the human asks. Put fixes in the review as findings.
