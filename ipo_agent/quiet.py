"""Quiet runs: when nothing in today's snapshot needs judgement, write the run's verdict file
from the previous run's calls and render the email, so Claude only delivers and commits.

A run is quiet when no IPO is open or closing today and nothing needs research. These make it
not quiet:
  * a source error in the snapshot, so Claude has to web-search the missing numbers
  * needs_card, needs_anchor_update, or needs_analysis for an IPO whose RHP is available
  * an IPO whose phase changed since the previous report, e.g. it opened or its bids closed
    (but not listing day: nothing to decide, the headline says it lists today)
  * for an IPO that can still be applied to: a falling GMP trend, or GMP ≤ 0 on a call
    other than avoid
  * an outcomes error, so the listing price has to be found by hand and recorded with --set
  * no previous report to carry calls from, or this session's report already written by Claude

It runs the outcomes step first (python3 -m ipo_agent.outcomes) and adds one note per newly
listed IPO. From the previous report, only the run-specific fields are carried over: verdict,
verdict_text, best_category and category_note. Card fields come from the card, which may be newer.
A category_note that says "today" or "tomorrow" is dropped. The headline is generated.

Usage:
    python3 -m ipo_agent.quiet AM|PM            # QUIET: writes + renders reports/<date>-<am|pm>.*
                                                # NOT QUIET: lists the reasons
    python3 -m ipo_agent.quiet PM --check       # only say whether the run is quiet
"""

import argparse
import datetime as dt
import json
import pathlib
import re
import sys

from . import cards, email_render, outcomes
from .snapshot import phase

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
RUN_FIELDS = ("verdict", "verdict_text", "best_category", "category_note")
LIVE = ("open", "closing_today")
CAN_APPLY = ("announced", "upcoming", "open", "closing_today")
RELATIVE = re.compile(r"\b(today|tonight|tomorrow|yesterday)\b", re.I)


def previous_report(stem):
    """The latest report before this run (2026-10-14-am < 2026-10-14-pm)."""
    earlier = sorted(p for p in REPORTS.glob("*.json") if p.stem < stem)
    return earlier[-1] if earlier else None


def carry(prev, ipos):
    """This run's entries: the previous report's run-specific fields, minus stale ones."""
    prev_date = prev["date"]
    out = {}
    for i in ipos:
        entry = {k: v for k, v in prev.get("ipos", {}).get(i["key"], {}).items() if k in RUN_FIELDS}
        if RELATIVE.search(entry.get("category_note") or ""):
            del entry["category_note"]
        card = cards.load(i["key"]) or {}
        if (card.get("analysed") or "") > prev_date:  # card rewritten since: its call wins
            entry.pop("verdict", None)
            entry.pop("verdict_text", None)
        if entry:
            out[i["key"]] = entry
    return out


def reasons(snap, prev, entries, outcome_errors):
    """Why this run needs Claude (empty list = quiet)."""
    why = [f"source error: {k}" for k in snap.get("errors") or {}]
    why += [f"outcomes: {k} — {v}" for k, v in outcome_errors.items()]
    if prev is None:
        why.append("no previous report to carry calls from")
    for i in snap["ipos"]:
        k, ph = i["key"], i["phase"]
        if ph in LIVE:
            why.append(f"{k}: {ph.replace('_', ' ')}")
        if i.get("needs_analysis") and i.get("rhp_url"):
            why.append(f"{k}: needs_analysis (RHP available)")
        if i.get("needs_card"):
            why.append(f"{k}: needs_card")
        if i.get("needs_anchor_update"):
            why.append(f"{k}: needs_anchor_update")
        was = phase(i, prev["date"]) if prev else ph
        if was != ph and (was, ph) != ("awaiting_listing", "listing_today"):
            why.append(f"{k}: {was} → {ph} since {prev['date']} {prev['session']}")
        if ph in CAN_APPLY:
            if ((i.get("trend") or {}).get("gmp") or {}).get("direction") == "down":
                why.append(f"{k}: GMP falling")
            verdict = {**(cards.load(k) or {}), **entries.get(k, {})}.get("verdict")
            if i.get("gmp") is not None and i["gmp"] <= 0 and i.get("price_high") and verdict != "avoid":
                why.append(f"{k}: GMP ≤ 0 but call is {verdict}")
    return why


def outcome_note(r):
    gain = r.get("listing_gain_pct")
    gmp = r.get("gmp_eve_pct")
    return (f"{r['name']} listed {gain:+.0f}%" if gain is not None else f"{r['name']} listed") + \
        (f" (GMP said {gmp:+.0f}%)" if gmp is not None else "") + \
        f"; our call: {r.get('verdict_text') or r.get('verdict') or 'none'}"


def headline(snap, listed):
    """One mechanical line: what lists today, what just listed, what opens and lists next."""
    today = dt.date.fromisoformat(snap["date"])
    parts = [f"{i['name']} lists today" for i in snap["ipos"] if i["phase"] == "listing_today"]
    parts += [f"{r['name']} listed {r['listing_gain_pct']:+.0f}%" for r in listed
              if r.get("listing_gain_pct") is not None]
    upcoming = [i for i in snap["ipos"] if i["phase"] == "upcoming" and i.get("open")]
    if upcoming:
        first = min(i["open"] for i in upcoming)
        names = [i["name"] for i in upcoming if i["open"] == first]
        when = "tomorrow" if dt.date.fromisoformat(first) == today + dt.timedelta(days=1) \
            else email_render.fmt_day(first)
        parts.append(f"{', '.join(names)} open{'s' if len(names) == 1 else ''} {when}")
    waiting = [i for i in snap["ipos"] if i["phase"] == "awaiting_listing" and i.get("listing")]
    if waiting:
        first = min(i["listing"] for i in waiting)
        names = [i["name"] for i in waiting if i["listing"] == first]
        parts.append(f"{', '.join(names)} list{'s' if len(names) == 1 else ''} {email_render.fmt_day(first)}")
    return "No IPO open today" + (" · " + " · ".join(parts) if parts else "")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("session", type=str.upper, choices=("AM", "PM"))
    ap.add_argument("--check", action="store_true", help="only say whether the run is quiet")
    ap.add_argument("--no-outcomes", action="store_true", help="skip the outcomes step (testing)")
    args = ap.parse_args(argv)

    snap = json.loads((ROOT / "data" / "latest.json").read_text())
    stem = f"{snap['date']}-{args.session.lower()}"
    target = REPORTS / f"{stem}.json"

    new, outcome_errors = [], {}
    if not args.no_outcomes:
        new, waiting, errs = outcomes.update(ROOT, snap["date"])
        # a failed subscription lookup still records the listing (from the snapshots)
        outcome_errors = {k: v for k, v in errs.items() if not k.endswith(".subscription")}
        if waiting:
            print(f"listing-day prices not out yet: {', '.join(waiting)}")
    listed = [outcomes.load(ROOT)[k] for k in new]
    notes = [outcome_note(r) for r in listed]

    prev_path = previous_report(stem)
    prev = json.loads(prev_path.read_text()) if prev_path else None
    entries = carry(prev, snap["ipos"]) if prev else {}
    why = reasons(snap, prev, entries, outcome_errors)
    if target.exists() and json.loads(target.read_text()).get("generated") != "quiet":
        why.append(f"{target.name} already written this session")

    if why:
        print("NOT QUIET — Claude needed:")
        print("\n".join(f"- {w}" for w in why))
        if notes:
            print("Listed since last run (add to notes):")
            print("\n".join(f"- {n}" for n in notes))
        return 0
    if args.check:
        print(f"QUIET: calls would carry over from {prev_path.name}")
        return 0

    report = {
        "date": snap["date"], "session": args.session,
        "headline": headline(snap, listed),
        "ipos": entries,
        "notes": notes + [f"Quiet run: no IPO open and nothing new to research. Numbers refreshed; "
                          f"calls carried over from the {prev['date']} {prev['session']} brief."],
        "generated": "quiet", "carried_from": prev_path.name,
    }
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"QUIET: wrote {target.relative_to(ROOT)} (calls from {prev_path.name}) and rendered .html/.txt")
    print("Subject: ", end="", flush=True)
    email_render.main([str(target)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
