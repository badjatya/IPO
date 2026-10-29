---
name: anchor-update
description: Fill in a pending anchor book for one IPO once the anchor allocation is out (ROUTINE.md step 2b). Use when the human asks to update an IPO's anchor investors, or the snapshot shows needs_anchor_update.
argument-hint: <IPO key>
---

# Update one IPO's anchor book

`ROUTINE.md` step 2b is the source of truth. For `$ARGUMENTS`:

1. **Search the web** for "<company name> anchor investors": the exchange filing, then news and IPO trackers.
2. **Replace only the `## Anchor book` section** of `analysis/$ARGUMENTS.md`, if that file exists. Include:
   - the total ₹ Cr raised and the number of anchors
   - the top 5–10 names with amounts
   - a grade: **Strong** (top mutual funds, FIIs or insurers), **Average**, or **Weak** (unknown AIFs, small funds, related parties)
   - the lock-in
3. **Update `anchor` and `anchor_grade`** in `analysis/$ARGUMENTS.json` to match. The `post-write` hook checks the card.
4. **If it's still not public,** leave both as pending and say so.
5. **Cite your sources** to the human, and say where each name came from.
