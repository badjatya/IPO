"""GMP and subscription trends from the saved snapshots (data/snapshots/*.json), so the email can
show "GMP ₹80 → ₹65 → ₹48 since 12 Oct, falling" or "Retail 0.4x → 2.8x (Day 1 → 2)".

* GMP: one point per day, the last Investorgain reading of that day. Readings are keyed by
  Investorgain's own `gmp_updated` time, not the snapshot time, because a later run sometimes
  gets an older (cached) page. A move counts as rising/falling when it is at least 8% of the GMP
  and, once the price band is known, at least 1% of the issue price; anything smaller is steady.
  "Falling" is measured from the peak, so ₹50 → ₹90 → ₹70 is falling even though it's above ₹50.
  Only the last 7 days count, so an IPO announced weeks ahead isn't judged against an old peak.
* Subscription: the last reading of each bidding day. A run before 10:00 IST (bidding hours are
  10:00–17:00) still shows the previous day's close, and runs after the close day count as the
  close day. Day N counts weekdays from the open date, so an exchange holiday mid-issue makes it
  run ahead; each day carries its date so that shows.

Usage:
    python3 -m ipo_agent.trends      # print the trends from the saved snapshots
"""

import datetime as dt
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAP_DIR = ROOT / "data" / "snapshots"
MIN_REL, MIN_PP = 0.08, 1.0  # significance: 8% of the GMP and 1% of the issue price
MAX_POINTS = 5
WINDOW_DAYS = 7
SUB_CATS = (("retail", "Retail"), ("snii", "sNII"), ("bnii", "bNII"), ("qib", "QIB"), ("total", "Total"))


def load(snap_dir=SNAP_DIR):
    return [json.loads(p.read_text()) for p in sorted(pathlib.Path(snap_dir).glob("*.json"))]


def _seen_at(snap):
    return dt.datetime.fromisoformat(snap["generated_at"])


def _gmp_time(updated, seen):
    """'13-Oct 23:37' -> datetime in the snapshot's year (or the year before, for a December
    reading seen in January). Falls back to the snapshot time if it doesn't parse."""
    try:
        t = dt.datetime.strptime(f"{seen.year}-{updated}", "%Y-%d-%b %H:%M").replace(tzinfo=seen.tzinfo)
    except (TypeError, ValueError):
        return seen
    return t.replace(year=t.year - 1) if t > seen + dt.timedelta(days=1) else t


def _significant(a, b, price):
    base = max(abs(a), abs(b))
    if not base or abs(b - a) / base < MIN_REL:
        return False
    return not price or 100 * abs(b - a) / price >= MIN_PP


def _rupees(x):
    return f"₹{x:g}"


def gmp_trend(history, price=None):
    """history: [(snapshot time, ipo entry)] oldest first."""
    readings = {}
    for seen, i in history:
        if i.get("gmp") is not None:
            readings[_gmp_time(i.get("gmp_updated"), seen)] = i["gmp"]
    daily = {}
    for t in sorted(readings):
        daily[t.date()] = readings[t]
    if daily:
        start = max(daily) - dt.timedelta(days=WINDOW_DAYS)
        daily = {d: v for d, v in daily.items() if d >= start}
    if len(daily) < 2:
        return None
    days, vals = list(daily), list(daily.values())
    first, last, peak = vals[0], vals[-1], max(vals)
    if _significant(peak, last, price) and last < peak:
        direction, word = "down", "falling" + (f" (peak {_rupees(peak)})" if peak not in (first, last) else "")
    elif _significant(first, last, price):
        direction, word = ("up", "rising") if last > first else ("down", "falling")
    else:
        direction, word = "flat", "steady"
    shown = [_rupees(v) for v in vals]
    if len(shown) > MAX_POINTS:
        shown = shown[:1] + ["…"] + shown[-(MAX_POINTS - 2):]
    return {"points": [{"date": d.isoformat(), "gmp": v} for d, v in daily.items()],
            "direction": direction,
            "text": f"GMP {' → '.join(shown)} since {days[0].strftime('%d %b').lstrip('0')}, {word}"}


def _prev_weekday(d):
    d -= dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def _bidding_day(open_d, d):
    return sum((open_d + dt.timedelta(days=n)).weekday() < 5 for n in range((d - open_d).days + 1))


def subscription_trend(history, open_, close):
    if not open_:
        return None
    o, c = dt.date.fromisoformat(open_), dt.date.fromisoformat(close) if close else None
    by_day = {}
    for seen, i in history:
        sub = i.get("subscription")
        if not sub:
            continue
        d = seen.date() if seen.hour >= 10 else _prev_weekday(seen.date())
        if c and d > c:
            d = c
        if d >= o:
            by_day[d] = {k: v["times"] for k, v in sub.items() if k in dict(SUB_CATS)}
    if len(by_day) < 2:
        return None
    days = [{"day": _bidding_day(o, d), "date": d.isoformat(), "times": t} for d, t in sorted(by_day.items())]
    parts = [f"{label} " + " → ".join(f"{x['times'][k]:g}x" for x in days)
             for k, label in SUB_CATS if all(k in x["times"] for x in days)]
    return {"days": days,
            "text": f"Day {days[0]['day']} → {days[-1]['day']}: " + " · ".join(parts)}


def _history(snaps):
    """key -> [(snapshot time, ipo entry)], oldest first."""
    hist = {}
    for s in snaps:
        for i in s["ipos"]:
            hist.setdefault(i["key"], []).append((_seen_at(s), i))
    return hist


def trend(ipo, history):
    return {"gmp": gmp_trend(history, ipo.get("price_high")),
            "subscription": subscription_trend(history, ipo.get("open"), ipo.get("close"))}


def attach(snap, snap_dir=SNAP_DIR):
    """Add `trend: {gmp, subscription}` to each IPO in `snap` (not yet saved) from the saved
    snapshots plus `snap` itself."""
    hist = _history([s for s in load(snap_dir) if s["generated_at"] < snap["generated_at"]] + [snap])
    for i in snap["ipos"]:
        i["trend"] = trend(i, hist.get(i["key"], []))
    return snap


def main():
    snaps = load()
    if not snaps:
        raise SystemExit("no snapshots")
    hist = _history(snaps)
    for i in snaps[-1]["ipos"]:
        t = trend(i, hist[i["key"]])
        print(f"{i['name']}:")
        print(f"  {t['gmp']['text'] if t['gmp'] else 'GMP: not enough history'}")
        if t["subscription"]:
            print(f"  Subscription {t['subscription']['text']}")


if __name__ == "__main__":
    main()
