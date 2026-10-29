# ADR-0014: Gemini API (free tier) for in-app Ask

- **Status:** Accepted. Since [ADR-0017](0017-gemini-for-stocks-claude-for-ipos.md), the free quota is shared by Ask, stock analyses and filing summaries, not by Ask alone
- **Decided:** 2026-10-29 · **Recorded:** 2026-10-29
- **Deciders:** Vijay · **Drafted with:** Claude Code (Opus 5.5)

## Context

Users can ask a question on any IPO or stock page ("Ask"). The answer comes only from data we already store: the card, the analysis, the latest numbers and recent filing summaries. Unlike the scheduled research, these calls come from users at any time, so they need an API key that the web app can call. That key isn't the Claude Code routine's subscription. The project runs on free tiers.

## Options

| Option | For | Against |
| --- | --- | --- |
| Claude API | Same model family as the research; strong at grounded answers | Paid per token from the first call |
| **Gemini API, free tier** | No cost; good enough for short answers grounded in supplied context | Small daily quotas, set per project and shared by all users; on the free tier Google may use prompts and answers to improve its products; a second AI provider in the stack |

## Decision

Ask uses the Gemini API on its free tier. Research (RHP analysis, cards, verdicts, filing summaries) stays with Claude in the scheduled routine.

## Consequences

**Data sent to Google.** On the free tier, prompts and answers may be used by Google to improve its products, which can include human review.
- The prompt therefore carries only the user's question and our stored research, which is public-source data. It never includes the user's email, name or watchlist.
- The Ask box tells users their question is sent to Google's Gemini API.

**Shared quota.** Free-tier quotas are per project, so every user shares them.
- Each user gets a daily question limit, so one user can't use up the day's quota.
- When the project quota runs out, Ask says so and the rest of the page works normally.
- Limits differ by model and account and change over time. They are read from AI Studio when we build the feature, never hard-coded from blog posts.

**Swappable provider.** The provider sits behind one small module in the app. Moving Ask to a paid tier or to another provider later changes only that module.

**Two providers.** The AI story is now: Claude does the research, and Gemini answers questions over that research. `ai.md` describes both.

## AI involvement

Claude Code proposed using the Claude API for Ask. **The human overrode that** and chose the Gemini free tier. Claude then checked the free tier's terms and quotas with web search, and wrote the privacy and quota consequences above.

## Evidence

- [AI journal 2026-10-29](../plan.md#ai-journal)
- Sources checked 2026-10-29 (all third-party; confirm on Google's own pricing, rate-limit and terms pages before building):
  - [Gemini API free tier in 2026 (apidog)](https://apidog.com/blog/gemini-api-free-tier/)
  - [Gemini free tier guide (pecollective)](https://pecollective-com.pages.dev/tools/gemini-free-tier-guide/)
  - [Gemini API pricing changes (agentdeals)](https://agentdeals.dev/gemini-api-pricing-changes)
