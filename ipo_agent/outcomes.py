"""Listing-day scorecard: once an IPO lists, record how it actually did next to what we
expected, so the verdict rules can be checked against real outcomes over time.

For every IPO whose listing date has passed and isn't in data/outcomes.json yet:
  * listing price (listing-day open) and the day's close, from NSE's daily price history;
    the issue price is NSE's "previous close" on listing day
  * GMP the night before: the last snapshot taken before listing day with a GMP
  * our call: the last report written while bids were still open (up to the close day's AM run)
  * final category-wise subscription: NSE issue details now, else the last snapshot that had it
Price history appears only after the listing day's close, so an IPO that isn't available yet
is retried on the next run. If NSE is blocked, record the prices by hand with --set.

Usage:
    python3 -m ipo_agent.outcomes                     # record new listings, print the scorecard
    python3 -m ipo_agent.outcomes --no-fetch          # just print the scorecard
    python3 -m ipo_agent.outcomes --set hd-fire-protect listing=348 close=361 [issue=271]
"""

import argparse
import datetime as dt
import json
import pathlib
import statistics
import sys
import urllib.parse
from zoneinfo import ZoneInfo

from .net import Client
from .nse import MAINBOARD_SERIES, NSE

ROOT = pathlib.Path(__file__).resolve().parent.parent
IST = ZoneInfo("Asia/Kolkata")
CATEGORIES = ("qib", "snii", "bnii", "retail", "total")
GRADE_RANK = {"weak": 0, "average": 1, "strong": 2}
VERDICT_ORDER = ("apply", "listing_gains", "neutral", "avoid", "pending")


def _load(p):
    return json.loads(p.read_text())


def _pct(x, base):
    return round(100 * (x / base - 1), 2) if x and base else None


def collect(root):
    """Everything the saved snapshots know about each IPO, oldest snapshot first."""
    seen = {}
    for p in sorted((root / "data" / "snapshots").glob("*.json")):
        snap = _load(p)
        at = snap["generated_at"]
        for i in snap["ipos"]:
            h = seen.setdefault(i["key"], {"gmps": [], "sub": None})
            for k in ("name", "open", "close", "listing", "price_high", "pe", "size_cr"):
                if i.get(k) is not None:
                    h[k] = i[k]
            nse = i.get("nse") or {}
            if nse.get("symbol"):
                h["symbol"], h["series"] = nse["symbol"], nse.get("series") or "EQ"
            if i.get("gmp") is not None:
                h["gmps"].append({"at": at, "gmp": i["gmp"], "updated": i.get("gmp_updated")})
            if i.get("subscription"):
                h["sub"] = {"source": f"snapshot {at}", "data": i["subscription"]}
    return seen


def eve_gmp(h):
    """GMP from the last snapshot taken before listing day (Friday PM for a Monday listing)."""
    before = [g for g in h["gmps"] if g["at"][:10] < h["listing"]]
    return before[-1] if before else None


def call(root, key, close):
    """The last call made while bids were open: reports up to the close day's AM run,
    merged over the card the way the email renderer does it."""
    if not close:
        return {"verdict": None, "verdict_text": None, "best_category": None, "verdict_report": None,
                "anchor_grade": None}
    cutoff = f"{close}-am"
    card_file = root / "analysis" / f"{key}.json"
    card = _load(card_file) if card_file.exists() else {}
    for p in sorted((root / "reports").glob("*.json"), reverse=True):
        if p.stem > cutoff:
            continue
        entry = _load(p).get("ipos", {}).get(key)
        if entry is not None:
            v = {**card, **entry}
            return {"verdict": v.get("verdict"), "verdict_text": v.get("verdict_text"),
                    "best_category": v.get("best_category"), "verdict_report": p.name,
                    "anchor_grade": v.get("anchor_grade")}
    return {"verdict": None, "verdict_text": None, "best_category": None, "verdict_report": None,
            "anchor_grade": card.get("anchor_grade")}


def listing_prices(nse, symbol, listing):
    """First trading day on or after the listing date: open (= listing price) and close."""
    d0 = dt.date.fromisoformat(listing)
    fmt = lambda d: d.strftime("%d-%m-%Y")
    q = urllib.parse.urlencode({"from": fmt(d0), "to": fmt(d0 + dt.timedelta(days=10)), "symbol": symbol,
                                "type": "priceVolumeDeliverable", "series": "ALL"})
    rows = [r for r in nse.api(f"/api/historicalOR/generateSecurityWiseHistoricalData?{q}").get("data") or []
            if r.get("CH_SERIES") in MAINBOARD_SERIES]
    if not rows:
        return None
    r = min(rows, key=lambda r: dt.datetime.strptime(r["mTIMESTAMP"], "%d-%b-%Y"))
    return {"listed_on": dt.datetime.strptime(r["mTIMESTAMP"], "%d-%b-%Y").date().isoformat(),
            "issue": r.get("CH_PREVIOUS_CLS_PRICE"), "listing": r["CH_OPENING_PRICE"],
            "close": r["CH_CLOSING_PRICE"], "high": r.get("CH_TRADE_HIGH_PRICE"),
            "low": r.get("CH_TRADE_LOW_PRICE"), "source": "nse"}


def final_subscription(nse, h, errors, key):
    if nse and h.get("symbol"):
        try:
            sub = nse.detail(h["symbol"], h.get("series", "EQ"))["subscription"]
            if sub.get("total", {}).get("shares_bid"):
                return {"source": f"nse ipo-detail {dt.date.today().isoformat()}", "data": sub}
        except Exception as e:
            errors[f"{key}.subscription"] = repr(e)
    return h.get("sub")


def record(root, key, h, prices, sub):
    issue = prices.get("issue") or h.get("price_high")
    eve = eve_gmp(h)
    gmp_pct = round(100 * eve["gmp"] / issue, 2) if eve and issue else None
    listing_gain = _pct(prices["listing"], issue)
    return {
        "name": h.get("name"), "symbol": h.get("symbol"),
        "listing_date": prices.get("listed_on") or h["listing"],
        "issue_price": issue, "listing_price": prices["listing"], "day_close": prices.get("close"),
        "day_high": prices.get("high"), "day_low": prices.get("low"),
        "listing_gain_pct": listing_gain, "close_gain_pct": _pct(prices.get("close"), issue),
        "gmp_eve": eve and eve["gmp"], "gmp_eve_pct": gmp_pct,
        "gmp_eve_snapshot": eve and eve["at"], "gmp_eve_updated": eve and eve["updated"],
        # + = listed above what the GMP implied, in percentage points of the issue price
        "gmp_miss_pts": round(listing_gain - gmp_pct, 2) if None not in (listing_gain, gmp_pct) else None,
        **call(root, key, h.get("close")),
        "pe": h.get("pe"), "size_cr": h.get("size_cr"),
        "subscription": {c: sub["data"][c]["times"] for c in CATEGORIES if c in (sub or {}).get("data", {})},
        "subscription_source": sub and sub["source"],
        "price_source": prices.get("source"),
        "recorded_at": dt.datetime.now(IST).isoformat(timespec="minutes"),
    }


def outcomes_path(root):
    return root / "data" / "outcomes.json"


def load(root=ROOT):
    p = outcomes_path(root)
    return _load(p) if p.exists() else {}


def save(root, outcomes):
    p = outcomes_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    ordered = dict(sorted(outcomes.items(), key=lambda kv: (kv[1].get("listing_date") or "", kv[0])))
    p.write_text(json.dumps(ordered, indent=1, ensure_ascii=False))


def update(root=ROOT, today=None, client=None):
    """Record every IPO that has listed and isn't scored yet. Returns (new keys, waiting, errors)."""
    today = today or dt.datetime.now(IST).date().isoformat()
    outcomes = load(root)
    nse = NSE(client or Client())
    new, waiting, errors = [], [], {}
    for key, h in collect(root).items():
        if key in outcomes or not h.get("listing") or h["listing"] > today:
            continue
        if not h.get("symbol"):
            errors[key] = "no NSE symbol in any snapshot — record it with --set"
            continue
        try:
            prices = listing_prices(nse, h["symbol"], h["listing"])
        except Exception as e:
            errors[key] = repr(e)
            continue
        if not prices:
            if dt.date.fromisoformat(today) - dt.date.fromisoformat(h["listing"]) > dt.timedelta(days=3):
                errors[key] = "no NSE prices 3+ days after listing (BSE-only, renamed or withdrawn?) — use --set"
            else:
                waiting.append(key)  # listing-day prices are published after the close
            continue
        outcomes[key] = record(root, key, h, prices, final_subscription(nse, h, errors, key))
        new.append(key)
    if new:
        save(root, outcomes)
    return new, waiting, errors


def set_manual(root, key, fields, client=None):
    """Record prices found elsewhere (e.g. web search when NSE is blocked)."""
    h = collect(root).get(key)
    if h is None:
        raise SystemExit(f"{key}: not in any snapshot")
    if not h.get("listing"):
        raise SystemExit(f"{key}: no listing date in the snapshots")
    prices = {k: float(v) for k, v in (f.split("=", 1) for f in fields)}
    if "listing" not in prices:
        raise SystemExit("--set needs at least listing=<price>")
    prices["source"] = "manual"
    errors = {}
    outcomes = load(root)
    outcomes[key] = record(root, key, h, prices, final_subscription(NSE(client or Client()), h, errors, key))
    save(root, outcomes)
    return errors


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return f"{statistics.fmean(xs):+.1f}%" if xs else "–"


def _corr(pairs):
    pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
    if len(pairs) < 3:
        return "–", len(pairs)
    xs, ys = zip(*pairs)
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in pairs)
    sxx, syy = sum((x - mx) ** 2 for x in xs), sum((y - my) ** 2 for y in ys)
    if not sxx or not syy:  # one of the series is constant
        return "–", len(pairs)
    return f"{sxy / (sxx * syy) ** 0.5:+.2f}", len(pairs)  # Pearson r


def scorecard(outcomes):
    rows = list(outcomes.values())
    if not rows:
        return "# IPO scorecard\n\nNo listings recorded yet."
    lines = [f"# IPO scorecard — {len(rows)} listing{'s' * (len(rows) != 1)}", "",
             "## By our call (last call before bids closed)", "",
             "| Call | IPOs | Avg listing gain | Avg day-1 close | Listed above issue |",
             "|---|---|---|---|---|"]
    for v in sorted({r.get("verdict") for r in rows}, key=lambda v: (v not in VERDICT_ORDER,
                    VERDICT_ORDER.index(v) if v in VERDICT_ORDER else 0, str(v))):
        g = [r for r in rows if r.get("verdict") == v]
        up = sum(1 for r in g if (r.get("listing_gain_pct") or 0) > 0)
        lines.append(f"| {v or 'no call'} | {len(g)} | {_avg(r['listing_gain_pct'] for r in g)} | "
                     f"{_avg(r.get('close_gain_pct') for r in g)} | {up}/{len(g)} |")

    miss = [r["gmp_miss_pts"] for r in rows if r.get("gmp_miss_pts") is not None]
    lines += ["", "## GMP vs actual listing", ""]
    if miss:
        lines.append(f"- {len(miss)} IPOs · average miss {statistics.fmean(miss):+.1f} pts "
                     f"(+ = listed above GMP) · average size of miss {statistics.fmean(map(abs, miss)):.1f} pts")
    else:
        lines.append("- no GMP recorded the night before any listing yet")

    signals = [
        ("GMP % (night before)", lambda r: r.get("gmp_eve_pct")),
        ("Total subscription", lambda r: r["subscription"].get("total")),
        ("QIB subscription", lambda r: r["subscription"].get("qib")),
        ("Retail subscription", lambda r: r["subscription"].get("retail")),
        ("bNII subscription", lambda r: r["subscription"].get("bnii")),
        ("Anchor grade (weak 0 → strong 2)", lambda r: GRADE_RANK.get((r.get("anchor_grade") or "").lower())),
        ("P/E", lambda r: r.get("pe")),
        ("Issue size (₹ Cr)", lambda r: r.get("size_cr")),
    ]
    lines += ["", "## Which signals tracked listing gains", "",
              "Correlation with listing gain (−1 to +1; needs 3+ IPOs, means little under ~15).", "",
              "| Signal | Correlation | IPOs |", "|---|---|---|"]
    for label, f in signals:
        c, n = _corr((f(r), r.get("listing_gain_pct")) for r in rows)
        lines.append(f"| {label} | {c} | {n} |")

    lines += ["", "## Listings", "",
              "| IPO | Listed | Call | GMP eve | Listing | Day-1 close | Subscription (QIB / Retail / Total) |",
              "|---|---|---|---|---|---|---|"]
    fp = lambda x: f"{x:+.1f}%" if x is not None else "–"
    fx = lambda x: f"{x:g}x" if x is not None else "–"
    for r in sorted(rows, key=lambda r: r.get("listing_date") or "", reverse=True):
        s = r["subscription"]
        lines.append(f"| {r['name']} | {r['listing_date']} | {r.get('verdict_text') or r.get('verdict') or '–'} | "
                     f"{fp(r.get('gmp_eve_pct'))} | {fp(r['listing_gain_pct'])} | {fp(r.get('close_gain_pct'))} | "
                     f"{fx(s.get('qib'))} / {fx(s.get('retail'))} / {fx(s.get('total'))} |")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true", help="only print the scorecard")
    ap.add_argument("--set", nargs="+", metavar="ARG",
                    help="KEY listing=<price> [close=<price>] [issue=<price>]: record prices by hand")
    ap.add_argument("--date", help="override today (YYYY-MM-DD), for testing")
    args = ap.parse_args(argv)

    if args.set:
        errors = set_manual(ROOT, args.set[0], args.set[1:])
        print(f"recorded {args.set[0]} (manual prices)", file=sys.stderr)
    elif not args.no_fetch:
        new, waiting, errors = update(ROOT, args.date)
        for k in new:
            r = load(ROOT)[k]
            print(f"recorded {r['name']}: listed {r['listing_gain_pct']:+.1f}%, closed "
                  f"{(r['close_gain_pct'] or 0):+.1f}% · GMP eve {r['gmp_eve_pct'] if r['gmp_eve_pct'] is not None else '–'}% "
                  f"· our call {r.get('verdict_text') or r.get('verdict') or 'none'}", file=sys.stderr)
        if waiting:
            print(f"listing-day prices not out yet: {', '.join(waiting)}", file=sys.stderr)
    else:
        errors = {}
    for k, v in errors.items():
        print(f"error {k}: {v}", file=sys.stderr)
    print(scorecard(load(ROOT)))
    return 0  # never fail the routine: anything missed is retried next run


if __name__ == "__main__":
    sys.exit(main())
