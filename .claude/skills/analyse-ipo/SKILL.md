---
name: analyse-ipo
description: Write or redo the deep RHP analysis and email card for one IPO (ROUTINE.md steps 2 and 2c). Use in a development session when the human asks to (re)analyse a specific IPO, e.g. after a wrong figure was found.
argument-hint: <IPO key, e.g. zetwerk>
---

# Analyse one IPO

`ROUTINE.md` steps 2 and 2c are the source of truth for the template and rules. This skill runs them for a single IPO, `$ARGUMENTS`, outside the scheduled run.

1. **Find the IPO.** Look up `$ARGUMENTS` in `data/latest.json` for its `rhp_url`. If there's no RHP yet, stop: the card stays a web stub.
2. **Extract the RHP** if `analysis/rhp/$ARGUMENTS.txt` is missing: `python3 -m ipo_agent.rhp "<rhp_url>" --out analysis/rhp/$ARGUMENTS.txt`. Read the extracted text in full, never the PDF.
3. **Research the deep parts.** Delegate the RHP reading and drafting to the `rhp-analyst` subagent, giving it the key and the text path. It returns the draft of `analysis/$ARGUMENTS.md`, written to the ROUTINE.md template.
4. **Check before saving.** Every ₹ figure in the draft must appear in the RHP text. Anything not found becomes "not found". The quota split comes only from the RHP's "Offer structure".
5. **Write the card** `analysis/$ARGUMENTS.json` from the analysis, with `"source": "rhp"`. Facts only: no GMP, no subscription, no today or tomorrow. The `post-write` hook rejects a card that breaks the schema or uses those words; fix whatever it reports.
6. **Show the human** the verdict and what changed, before anything is committed.
