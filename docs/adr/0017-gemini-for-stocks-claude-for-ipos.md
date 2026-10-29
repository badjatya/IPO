# ADR-0017: Claude for IPOs only; Gemini for all stock work; every analysis request counts

- **Status:** Accepted. Supersedes [ADR-0016](0016-on-demand-stock-analysis.md)
- **Decided:** 2026-10-29 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

ADR-0016 ran on-demand stock analysis through the Claude Code routine on the personal Pro account. The human decided the same day that the account is for IPOs only. Phase 1 has no payments, and every user gets the same limits: 5 Ask questions a day and 3 stock analyses a month.

The human's words:
- "architj240 is the personal claude pro plan but it will be used only for ipo and not for stock analysis that we are doing as per user request, that we will be doing using gemini"
- On quotas: "we can still count it as some research we might have to do, as there might be some older data so count it"

## Options

| Option | For | Against |
| --- | --- | --- |
| Keep ADR-0016 (Claude routine for stocks) | Same model for all research | Uses the personal account for user requests; about 3 runs a day across all users |
| **Claude for IPOs; Gemini for every stock task** | Personal account stays IPO-only; no 5-runs-a-day cap on stock work; free in phase 1 | Two AI providers; Gemini's free quota is shared by Ask and all stock work; search grounding may not be free |

## Decision

1. **Claude does IPOs only.** The Claude Code routine on the personal Pro account does IPO research and nothing else.
2. **Gemini does every stock task:** full stock analyses on request, plus the scheduled watchlist work (results summaries, announcement triage, alert explanations). A separate stock worker runs it; the host is in [ADR-0018](0018-stock-worker-on-github-actions.md).
3. **Every analysis request counts** against the user's monthly 3, even when a saved analysis can be served, because older data may need refreshing. A saved analysis is served when fresh, and refreshed first when it's out of date.
4. **Kept from ADR-0016:**
   - jobs are queued, and users asking for the same stock share one job
   - the live loading screen
   - quotas in the [`settings`](../db.md#settings) table, the same for every user in phase 1
   - the saved analysis is reused across users ([ADR-0013](0013-shared-per-stock-research.md))

## Consequences

**The 5-runs-a-day routine cap no longer limits stock work**, and `on_demand_runs_per_day` is dropped.

**One Gemini quota covers everything.** Its free quota (per Google project) is now shared by Ask, analyses and filing summaries. The new platform setting `analysis_daily_limit_platform` stops analyses from using up Ask's share. Its default can only be set after reading the real quotas in AI Studio.

**News may not be free.** Search grounding may not be included in the free tier for the chosen model. If it isn't, analyses say that news wasn't checked.

**Provenance names the provider.** `ai_model` records the provider and model, such as `gemini-…` or `claude-sonnet-5.5`, so every saved text shows which AI wrote it.

**The AI picture changes.** Claude researches IPOs; Gemini researches stocks and answers questions. This affects the "AI inside the platform" story in the submission, and `ai.md` describes both.

**Follow-up decisions** (proposed by Claude, accepted by the human on 2026-10-29):
- A saved analysis is refreshed when it's older than 30 days or older than the company's latest quarterly result.
- Reopening the same stock in the same month isn't charged again.
- A failed analysis refunds the request.

Still open: the platform cap's default, which waits on the Gemini quota in AI Studio.

## AI involvement

Claude Code had proposed running stock analysis on the Claude routine (ADR-0016) and charging only for new research. **The human overrode both:** Gemini for stocks, and every request counts.

Claude read "Pro account only for IPOs" as moving the scheduled watchlist work to Gemini as well, and asked the human to confirm that reading.

## Evidence

- [AI journal 2026-10-29](../plan.md#ai-journal)
