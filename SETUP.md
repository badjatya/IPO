# Setting up the scheduled routine

The routine must be created while you are signed in to claude.ai as **architj240@gmail.com**.
Routines belong to whichever Claude account creates them, and that account needs a Pro plan or higher.

## 1. GitHub repo
1. Create a **private** repo under architj240's GitHub (e.g. `ipo-agent`) and push this folder to `main`.
2. In claude.ai, signed in as architj240, open Settings and connect GitHub with access to that repo.

## 2. Gmail connector
claude.ai → Customize → Connectors → **Gmail** → connect, and pick the architj240@gmail.com Google account.
The report is emailed to the address in `config/delivery.json`.

## 3. Cloud environment
claude.ai/code/routines → New routine → environment selector → create an environment named `ipo-agent`:
- **Network access:** Custom. Add these domains and keep the default package list ticked:
  `www.nseindia.com`, `nsearchives.nseindia.com`, `www.investorgain.com`, `www.sebi.gov.in`, `www.bseindia.com`.
  If that causes blocks, use **Full** instead.
- **Setup script:**
  ```bash
  (command -v pdftotext >/dev/null || (sudo apt-get update -qq && sudo apt-get install -y -qq poppler-utils)) || true
  pip install -q pypdf || true
  ```

## 4. Routine
- **Name:** IPO brief
- **Repository:** the repo from step 1
- **Environment:** `ipo-agent`
- **Connectors:** keep only Gmail
- **Prompt:**
  > Read ROUTINE.md in the repository and follow it exactly. This is the <AM|PM> run.
- **Triggers** (times in IST; a few minutes past the hour so the run starts on time):
  - Weekdays **09:07**: AM run, before bidding opens at 10:00. Covers the day's open, closing and upcoming IPOs.
  - Weekdays **19:07**: PM run, after bidding closes at 17:00. Final subscription figures and anchor updates.
  - Optional weekdays **15:07**: a check during the last hours of bidding, for IPOs that close today.

  For per-trigger AM/PM labels, create two routines with the same settings. Alternatively, use one prompt that
  says "decide AM or PM from the current IST time".

## 5. First run checklist (use **Run now** before turning on the schedule)
Open the run's transcript and confirm each item. A green status only means the session didn't crash.
- [ ] `python3 -m ipo_agent.snapshot` reports `errors: none`. NSE often blocks cloud IPs. If NSE fails here,
      the report falls back to web search for subscription numbers. Tell Claude and we'll switch the subscription source.
- [ ] Investorgain and `nsearchives.nseindia.com` (RHP downloads) are reachable.
- [ ] Web search worked: the anchor names and non-NSE RHP lookups depend on it.
- [ ] `pdftotext` or `pypdf` was available, and `analysis/rhp/<SYMBOL>.txt` was written.
- [ ] The email arrived at the configured address and reads well on your phone.
- [ ] The commit landed on **main**: the next run should *not* redo analyses that already exist.
