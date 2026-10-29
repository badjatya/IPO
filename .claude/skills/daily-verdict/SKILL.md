---
name: daily-verdict
description: Write a run's verdict file reports/<date>-<am|pm>.json from data/latest.md and render the email (ROUTINE.md step 3). Use in a development session when the human asks to regenerate or fix a brief.
argument-hint: <AM|PM>
---

# Write the day's verdicts

`ROUTINE.md` step 3 is the source of truth. This skill is for a manual rerun of one session (`$ARGUMENTS`, AM or PM).

1. **Get the numbers.** Run `python3 -m ipo_agent.snapshot` unless `data/latest.json` is from this session. Then read `data/latest.md` only. Don't reread the analyses: the cached calls are in `data/latest.md`.
2. **Write the verdict file** `reports/<YYYY-MM-DD>-<am|pm>.json`. Include an entry for every IPO that is open, closing today, or on its first run after bids closed. Write only what changes with today's numbers: `best_category`, `category_note`, and `verdict` or `verdict_text` if the call moved. The best category is the least-subscribed one. Prefer Retail when it's close to sNII.
3. **Let the hook check it.** The `post-write` hook checks the file name, date, session, field names and verdict values. Fix whatever it reports.
4. **Have it reviewed.** Delegate a check of the file against `data/latest.md` to the `verdict-reviewer` subagent, and fix any number it can't trace.
5. **Render** with `python3 -m ipo_agent.email_render reports/<file>.json`, and show the human the subject line. Don't send email or commit unless asked.
