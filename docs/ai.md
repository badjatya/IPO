# AI design

AI plays two roles in this project:

1. **Inside the product.** Two AIs, one per domain ([ADR-0017](adr/0017-gemini-for-stocks-claude-for-ipos.md)):
   - **Claude researches IPOs:** it reads prospectuses and makes the IPO calls.
   - **Gemini researches listed stocks:** it writes the on-request analyses and the filing summaries, and answers users' questions (Ask).
2. **Building the product.** Claude Code writes, reviews and tests the code and these docs, and a human decides.

Status labels follow [docs/README.md](README.md#status-labels). The rest of the system is described in [arch.md](arch.md).

## Part 1: AI inside the product

### Tasks the AI does

| Task | Status | Model | Input | Output | How often |
| --- | --- | --- | --- | --- | --- |
| Deep analysis of an IPO | **Running** | Sonnet 5.5 (routine) | RHP extract `analysis/rhp/<key>.txt`, web search (anchors, news) | `analysis/<key>.md` | Once per IPO |
| Email card | **Running** | Sonnet 5.5 | The analysis, or one web search before the RHP is filed | `analysis/<key>.json` | Once per IPO; replaced once when the RHP analysis lands |
| Anchor book update | **Running** | Sonnet 5.5 | Web search for the anchor allocation | Anchor section of the analysis and card | Once, after anchor bidding |
| Day's verdict and best category | **Running** | Sonnet 5.5 | `data/latest.md`: numbers, odds, trends and cached calls | `reports/<date>-<am\|pm>.json` | Each run where an IPO is open, closing or just closed |
| Results summary | **Decided** ([ADR-0017](adr/0017-gemini-for-stocks-claude-for-ipos.md)) | Gemini (stock worker, scheduled) | New quarterly result vs previous quarters (numbers from Python) | `quarterly_results.ai_summary` | Once per result |
| Announcement triage | **Decided** ([ADR-0017](adr/0017-gemini-for-stocks-claude-for-ipos.md)) | Gemini (stock worker, scheduled) | Announcement title, subject and attachment text | Importance plus summary | Once per announcement |
| Stock analysis on request | **Decided** ([ADR-0017](adr/0017-gemini-for-stocks-claude-for-ipos.md)) | Gemini (stock worker, dispatched by the app) | Price, valuation, 8 quarterly results, shareholding, announcements (Python); news through search grounding if the free tier allows it | `stock_analyses`, plus `data/stocks/<SYMBOL>/analysis.{md,json}` in git | Once per stock while fresh; refreshed when out of date; shared by every user |
| Alert explanation | **Decided** ([ADR-0017](adr/0017-gemini-for-stocks-claude-for-ipos.md)) | Gemini (stock worker, scheduled) | The rule that fired, with its numbers | `alerts.detail` | Once per alert |
| Ask about an IPO or stock | **Decided** ([ADR-0014](adr/0014-gemini-free-api-for-ask.md)) | Gemini API, free tier (model **Open**) | Stored card, analysis, latest numbers, recent filings | Answer with references | On request, capped |

### What the AI does not do

- **Compute numbers.** Python computes prices, odds, subscription, return on blocked capital, quarter-on-quarter changes and alert thresholds. The AI quotes them ([ADR-0001](adr/0001-python-for-exact-work-claude-for-judgement.md)).
- **Decide what to redo.** Python sets the `needs_*` flags and decides whether a run is quiet. Claude acts on them.
- **Lay out the email.** Claude writes JSON; `email_render.py` builds the email ([ADR-0005](adr/0005-email-rendered-from-json.md)).
- **Say buy or sell on listed stocks.** The watchlist summarises and flags ([ADR-0012](adr/0012-research-not-advice.md)).

### Context engineering

How Claude gets exactly the context it needs and no more.

| Technique | Where | Effect |
| --- | --- | --- |
| A short project map | [CLAUDE.md](../CLAUDE.md) | Claude knows every command and file without exploring the repo |
| A step-by-step procedure | [ROUTINE.md](../ROUTINE.md) | Same steps every run; the analysis template fixes the sections and the rules |
| One compact input per run | `data/latest.md`, built by `snapshot.py` | Claude reads one Markdown page instead of raw JSON from three sources |
| Read the extract, not the PDF | `rhp.py` pulls the key RHP sections into text | A 400-page prospectus becomes the sections that matter |
| Cache once, never reread | `analysis/` plus `needs_*` flags | Later runs read the cached call shown in `data/latest.md`, not the analysis |
| Write only what changed | Report entries override the card | A typical run writes a few short strings per IPO |
| Skip Claude when nothing changed | `quiet.py` | Quiet runs ask Claude for no judgement at all; it only sends and commits |
| Cards hold facts, not live numbers | Card rules in `ROUTINE.md` | A card stays true for days and is never rewritten for a GMP move |

### Guardrails

| Guardrail | Kind | Status |
| --- | --- | --- |
| "Never invent numbers; write 'not found'" | Instruction (`ROUTINE.md`) | **Running** |
| Quota split only from the RHP's "Offer structure"; never guessed | Instruction, backed by `rhp.py` extracting that section | **Running** (added after a wrong retail quota, commit `44f553a`) |
| Cards hold facts only: no GMP, subscription or "today" | Instruction | **Running** |
| Say which numbers came from web search when NSE is blocked | Instruction | **Running** |
| Numbers and layout produced by code | Architecture (Python + renderer) | **Running** |
| Claude doesn't decide what to redo | Architecture (`needs_*` flags, `quiet.py`) | **Running** |
| Routine limited to the Gmail connector and an allowlisted network | Environment ([SETUP.md](../SETUP.md)) | **Running** |
| Validate card and report JSON when they're written (schema, enums, file name vs date and session) | Hook `.claude/hooks/guard.py post-write` | **Running** (2026-10-29; checked against every saved card and report) |
| Reject GMP, subscription or today/tomorrow text inside cards | Hook `guard.py post-write` | **Running** |
| Every ₹ figure in an analysis must appear in the RHP text | Verifier script, run by a hook and in CI | **Running** in CI (`ipo_agent/figures_check.py`); the hook is **Decided** until the human applies the diff in plan 005 |
| Push only to `origin`; no force, mirror or delete pushes | Hook `guard.py pre-bash` (Claude). DeepSeek has no push: its `run` tool allows only read-only git, and the driver commits | **Running** |
| DeepSeek's file tools refuse the routine's files, Claude's config, `AGENTS.md`, the roadmap, review files and `.env*`; plan steps write only `plan.md` | `.claude/deepseek/deepseek.py`, tests in `test_deepseek.py` | **Running** |
| After every DeepSeek step, every changed path and commit is checked against the same rules, along with the approved plan and Claude's review text; a step that broke one isn't handed off | `deepseek.py` post-step check | **Running**. The limit: code a task runs through `python3` or `npm` can still touch anything, so this check, Claude's code review and "only the human pushes" are the boundary ([ADR-0021](adr/0021-deepseek-on-openrouter.md)) |
| The OpenRouter key stays out of DeepSeek's reach: not in its commands' environment, replaced in every tool result before the model or the log sees it, and a step whose changed files contain it is not handed off | `deepseek.py`, tested in `test_deepseek.py` | **Running** |
| Documents are data, not instructions (prompt-injection defence) | Instruction in the routine and in the worker's prompts; Gemini calls have no tools beyond search grounding | **Decided** |
| Per-person daily Ask limit (5) and monthly analysis limit (3), the same for every user in phase 1; every analysis request counts; no user identity in any prompt | App code + `settings` table | **Decided** |
| The stock worker gets no user text; it reads job rows whose symbols were checked against the stocks list | App code + worker | **Decided** |
| Platform cap on analyses a day, so analyses can't use up the Gemini quota that Ask shares | `settings.analysis_daily_limit_platform` | **Decided** (default **Open** until the quota is read in AI Studio) |
| An analysis says "news not checked" when search grounding isn't available | Worker | **Decided** |
| "Not investment advice" on every page and email | Renderer and app layout | **Decided** |

### Evals

| Eval | What it measures | Status |
| --- | --- | --- |
| **Listing scorecard** (`python3 -m ipo_agent.outcomes --no-fetch`) | Each call against the real listing: average listing gain by verdict, GMP miss, which signals tracked listing gains ([ADR-0007](adr/0007-listing-scorecard-as-eval.md)) | **Running**: 8 listings scored by 2026-10-29 |
| Figures check | Share of ₹ figures in each analysis found in its RHP text | **Running**: 13 analyses checked on 2026-10-29, 54/316 ₹ figures found overall (17%); a low share is expected (price band, GMP, anchor book and computed market caps are not RHP text) and points at the missing list to read, not a failure |
| Schema check | Every card and report in the repo matches its schema | **Running**: `.claude/hooks/test_guard.py`, run by CI on every push (`.github/workflows/ci.yml`) |
| Analysis quality review | A second Claude pass grades each analysis against the template (all sections, numbers cited, grade justified) | **Proposed** |
| Regression set | Past IPOs replayed with a changed instruction; calls and figures compared with before | **Proposed** |

Scorecard by 2026-10-29:

| Call | IPOs | Average listing gain |
| --- | --- | --- |
| Apply | 1 | +23.6% |
| Listing gains only | 4 | +23.7% |
| Neutral | 1 | +5.5% |
| Avoid | 2 | +4.7% |

GMP the night before missed the listing by 3.5 points on average. Eight listings are too few to judge the calls; the scorecard says so itself.

### In-app AI: Ask

Design (**Decided**, [ADR-0014](adr/0014-gemini-free-api-for-ask.md); Gemini model **Open**):

1. **Grounded.** The prompt contains only stored context: the card, the analysis, the latest numbers and recent filing summaries for that one IPO or stock. The system instruction tells Gemini to answer from that context, say when the answer isn't in it, and point to the section it used.
2. **No tools.** The call can't browse, write or send anything, so text hidden in a document can at most change the answer.
3. **Capped.** The free tier's quota is per project and shared by every user, and by the stock worker's analyses and summaries. Before each call, the user's questions today are counted in `ai_questions` and compared with `ask_daily_limit_per_user` in the [`settings`](db.md#settings) table. An admin can change that limit without a deploy. When the project quota runs out, Ask says so and nothing else on the page is affected.
4. **Private.** On the free tier, Google may use prompts and answers to improve its products. The prompt therefore carries only the question and our public-source research, never the user's email, name or watchlist. The Ask box tells users their question goes to Google's Gemini API.
5. **Logged.** Question, answer, model and token counts are stored ([db.md](db.md#ai_questions)).
6. **Labelled.** Every answer carries "not investment advice".
7. **Swappable.** The provider sits behind one module, so moving to a paid tier or another provider changes only that module.

### Human review in the product

| Point | Who reviews | What | Status |
| --- | --- | --- | --- |
| Before the routine was enabled | Owner | Two full test runs checked against the [SETUP.md](../SETUP.md) checklist | **Running** (done 2026-10-12) |
| Every brief | Owner reads the email | Wrong facts are fixed in code or instructions, e.g. the retail quota fix in `44f553a` | **Running** |
| After every listing | Scorecard | Calls compared with outcomes | **Running** |
| Scorecard patterns | Owner | Patterns in the scorecard feed instruction changes | **Proposed** |
| Changes to `ROUTINE.md` | Owner, via PR | Instruction changes are reviewed like code | **Proposed** |

## Part 2: AI used to build the product

### Tools and models

| Tool | Used for | Evidence |
| --- | --- | --- |
| Claude Code (Opus 5.5) | Until 2026-10-29: writing the agent, renderer, scorecard and docs. From 2026-10-29: reviewing every task's plan and code ([ADR-0019](adr/0019-deepseek-builds-claude-reviews.md)), and running DeepSeek's steps ([ADR-0021](adr/0021-deepseek-on-openrouter.md)) | Commits with `Co-Authored-By: Claude Opus 5.5`; `plan-review.md` and `code-review.md` in `docs/tasks/` |
| DeepSeek in opencode | 2026-10-29, briefly: planning tasks 001 and 003 ([ADR-0019](adr/0019-deepseek-builds-claude-reviews.md)); often unavailable | Commits with the trailer `AI-Agent: DeepSeek (opencode)` |
| DeepSeek through OpenRouter (`deepseek/deepseek-v4-flash-0731`) | From 2026-10-29: planning and building each task, run by Claude Code ([ADR-0021](adr/0021-deepseek-on-openrouter.md)) | `plan.md` in `docs/tasks/`; commits with the trailer `AI-Agent: DeepSeek <model> (OpenRouter)`; step logs with cost in `.deepseek-logs/` (local) |
| Claude Code routine (Sonnet 5.5) | The twice-daily research runs | Commits by `Claude` with `Co-Authored-By: Claude Sonnet 5.5` |
| Claude web search | Anchor books and news inside the IPO routine | Report and analysis sources |
| Gemini API (free tier) | In the product: stock analyses, filing summaries, Ask (not used for development) | [ADR-0014](adr/0014-gemini-free-api-for-ask.md), [ADR-0017](adr/0017-gemini-for-stocks-claude-for-ipos.md) |
| Web search while building | Current service facts before deciding, e.g. Neon and MongoDB Atlas free tiers ([ADR-0010](adr/0010-postgresql-on-neon.md)) | Sources listed in the ADR |

### How we work: two agents and a human

From 2026-10-29 ([ADR-0019](adr/0019-deepseek-builds-claude-reviews.md), with DeepSeek through OpenRouter since [ADR-0021](adr/0021-deepseek-on-openrouter.md); workflow in [tasks/README.md](tasks/README.md)). Claude Code runs the loop with `/run-task NNN` and stops for the human:

```mermaid
flowchart LR
    H(["Human<br/>assigns task"]) --> P["DeepSeek (OpenRouter)<br/>plan.md"]
    P --> PRClaude Code<br/>plan review
    PR -- "changes requested" --> P
    PR -- "approved" --> B["DeepSeek<br/>builds on task branch"]
    B --> CRClaude Code<br/>code review
    CR -- "changes requested" --> B
    CR -- "approved" --> M(["Human<br/>merges"])
```

1. **Architecture first.** Before tasks, Claude Code and the human settle the architecture.
   - Claude proposes options with trade-offs, and the human decides; each decision goes into an [ADR](adr/README.md).
   - Overrides are recorded too, for example Next.js over a standard-library web app ([ADR-0009](adr/0009-nextjs-web-platform.md)) and Gemini over Claude for stocks ([ADR-0017](adr/0017-gemini-for-stocks-claude-for-ipos.md)).
2. **Plan.** DeepSeek writes the task's plan in `docs/tasks/NNN-slug/plan.md`, following [AGENTS.md](../AGENTS.md).
3. **Plan review.** Claude checks the plan against the architecture, the ADRs and the project rules, then approves it or requests changes.
4. **Build.** DeepSeek builds the approved plan with tests, and records any deviation.
5. **Code review.** Claude runs the tests, reviews the diff, and ranks findings Blocker, Major, Minor or Nit. DeepSeek responds to each finding.
6. **Merge.** The human merges.
7. **Record.** Every round stays in the task folder, and each task gets an entry in the [AI journal](plan.md#ai-journal).

### AI structure in the repo

| Piece | Status | Purpose |
| --- | --- | --- |
| `CLAUDE.md` | **Running** | Project map for Claude Code; kept short because the IPO routine loads it on every run; reviewer steps for development sessions |
| `AGENTS.md` | **Running** | Project rules for every coding agent; the driver puts it in DeepSeek's system prompt |
| `docs/tasks/` | **Running** | One folder per task: plan, plan review, code review, responses; templates and reviewer guide |
| `ROUTINE.md` | **Running** | The routine's procedure, templates and rules |
| `docs/` with status labels and ADRs | **Running** | Shared context for people and agents; every claim traceable |
| `.claude/skills/`: `run-task`, `review-plan`, `review-code` | **Running** | `/run-task NNN` runs the whole loop; `/review-plan NNN` and `/review-code NNN` are Claude's reviewer steps |
| `.claude/skills/`: `analyse-ipo`, `anchor-update`, `daily-verdict` | **Running** for development sessions | `ROUTINE.md` steps 2, 2b and 3 for one IPO or session; `ROUTINE.md` stays the source of truth for the scheduled run |
| `.claude/agents/`: `rhp-analyst`, `verdict-reviewer` | **Running** | Narrow subagents: one drafts an analysis from RHP text and lists where each figure came from; one checks a verdict file against the day's numbers, read-only |
| `.claude/settings.json` hooks | **Running** | Guardrails above, enforced by the harness instead of by instruction; tests in `.claude/hooks/test_guard.py` |
| `.claude/deepseek/deepseek.py` | **Running** | Runs DeepSeek through OpenRouter for one step (`plan`, `revise`, `build`, `respond`): tools, write rules, post-step check, status and hand-off commit; tests in `test_deepseek.py`, run in CI |
| Agent `tests/` | **Running** | Python `unittest` for the agent, saved fixtures only, no network |
| CI | **Running** for the agent | GitHub Actions (`.github/workflows/ci.yml`): agent tests, the schema check and the figures check on every push and pull request. App tests against a Neon branch are **Decided** (tasks 006, 007) |
