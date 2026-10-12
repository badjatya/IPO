# IPO research agent

Daily research on Indian **mainboard** IPOs (no SME). When run as a scheduled routine, follow `ROUTINE.md`.

- `python3 -m ipo_agent.snapshot --print` — fetch numbers (Investorgain list/GMP + NSE details/subscription) → `data/latest.{json,md}`
- `python3 -m ipo_agent.rhp <SYMBOL|url>` — extract key RHP sections → `analysis/rhp/` (RHP links come from NSE, or SEBI before NSE lists the issue)
- `ipo_agent/allotment.py` — category minimums and allotment odds (Retail / sNII / bNII)
- `analysis/<key>.md` — cached deep analysis per IPO (written once, reused)
- `reports/<date>-<am|pm>.json` — Claude's verdicts; `python3 -m ipo_agent.email_render <json>` renders the `.html` email + `.txt`
- `config/delivery.json` — email recipient

Python standard library only; `pdftotext` (poppler-utils) is used for RHPs, with `pypdf` as a fallback.
