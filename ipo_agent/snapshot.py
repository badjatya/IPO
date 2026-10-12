"""Build today's IPO snapshot: mainboard IPOs that are upcoming, open, or closed
and awaiting listing, merged from Investorgain (list/dates/GMP) and NSE
(issue details + live category-wise subscription).

Usage:
    python3 -m ipo_agent.snapshot            # writes data/snapshots/*.json + data/latest.json
    python3 -m ipo_agent.snapshot --print    # also prints the markdown digest
"""

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
from zoneinfo import ZoneInfo

from . import allotment, investorgain, sebi
from .net import Client
from .nse import MAINBOARD_SERIES, NSE

ROOT = pathlib.Path(__file__).resolve().parent.parent
IST = ZoneInfo("Asia/Kolkata")
_DROP = {"limited", "ltd", "india", "the", "pvt", "private", "co"}


def norm(name):
    s = (name or "").lower().replace("&", " and ")
    toks = [t for t in re.sub(r"[^a-z0-9 ]", " ", s).split() if t not in _DROP]
    return " ".join(toks)


def slug(name):
    return norm(name).replace(" ", "-") or "unknown"


def same_company(a, b):
    a, b = norm(a), norm(b)
    return bool(a and b) and (a == b or a.startswith(b) or b.startswith(a))


def nse_date(s):
    return dt.datetime.strptime(s, "%d-%b-%Y").date().isoformat() if s else None


def phase(ipo, today):
    o, c, l = ipo.get("open"), ipo.get("close"), ipo.get("listing")
    if not o:
        return "announced"  # dates not yet fixed
    if today < o:
        return "upcoming"
    if c and o <= today < c:
        return "open"
    if c and today == c:
        return "closing_today"
    if l and today < l:
        return "awaiting_listing"
    if l and today == l:
        return "listing_today"
    return "listed"


def anchor_pending(analysis_file):
    """True if the cached analysis still has the anchor-book section marked Pending."""
    if not analysis_file.exists():
        return False
    m = re.search(r"## Anchor book\s*\n(.*?)(\n## |\Z)", analysis_file.read_text(), re.S)
    return bool(m and "pending" in m.group(1).lower())


def build(today=None):
    now = dt.datetime.now(IST)
    today = today or now.date().isoformat()
    client = Client()
    errors = {}

    try:
        ig = investorgain.fetch(client)
    except Exception as e:  # keep going with NSE alone
        ig, errors["investorgain"] = [], repr(e)

    nse = NSE(client)
    nse_list = []
    for fn in (nse.current, nse.upcoming):
        try:
            nse_list += fn() or []
        except Exception as e:
            errors[f"nse.{fn.__name__}"] = repr(e)

    ipos = {}
    for r in ig:
        if r["board"] != "mainboard":
            continue
        # keep if not yet listed, or listing today
        if r["status"] == "listed" and (r.get("listing") or "") < today:
            continue
        ipos[slug(r["name"])] = {"name": r["name"], **{k: r[k] for k in (
            "open", "close", "allotment", "listing", "price", "lot", "size_cr",
            "gmp", "gmp_pct", "gmp_low", "gmp_high", "pe", "gmp_updated", "url")},
            "nse": None}

    for n in nse_list:
        series = (n.get("series") or "").upper()
        if series not in MAINBOARD_SERIES:
            continue
        name = n.get("companyName") or n.get("company") or n.get("symbol")
        key = next((k for k, v in ipos.items() if same_company(v["name"], name)), None)
        if key is None:
            key = slug(name)
            ipos[key] = {"name": name, "open": nse_date(n.get("issueStartDate")),
                         "close": nse_date(n.get("issueEndDate")), "nse": None}
        try:
            ipos[key]["nse"] = nse.detail(n["symbol"], series)
            ipos[key]["nse"]["series"] = series
        except Exception as e:
            errors[f"nse.detail.{n.get('symbol')}"] = repr(e)

    # RHP links: NSE's issue page when it exists, else SEBI's RHP listing (published earlier).
    need_sebi = [k for k, v in ipos.items()
                 if not (v.get("nse") or {}).get("rhp_url")
                 and not (ROOT / "analysis" / f"{k}.md").exists()]
    sebi_list = []
    if need_sebi:
        try:
            sebi_list = sebi.listing(client)
        except Exception as e:
            errors["sebi.listing"] = repr(e)
    for key, ipo in ipos.items():
        d = ipo.get("nse") or {}
        ipo["rhp_url"], ipo["rhp_source"] = (d.get("rhp_url"), "nse") if d.get("rhp_url") else (None, None)
        if key in need_sebi:
            hit = next((r for r in sebi_list if same_company(ipo["name"], r[1])), None)
            if hit:
                try:
                    ipo["rhp_url"], ipo["rhp_source"] = sebi.pdf_url(client, hit[2]), "sebi"
                except Exception as e:
                    errors[f"sebi.pdf.{key}"] = repr(e)

    out = []
    for key, ipo in ipos.items():
        d = ipo.get("nse") or {}
        if not ipo.get("open") and d.get("issue_period"):
            ipo["open"], ipo["close"] = map(nse_date, d["issue_period"][:2])
        price = d.get("price_high") or ipo.get("price")
        lot = d.get("lot") or ipo.get("lot")
        sub = d.get("subscription") or {}
        has_live_sub = bool(sub.get("total", {}).get("shares_bid"))
        cats = allotment.categories(price, lot, sub if has_live_sub else None, ipo.get("gmp"))
        analysis_file = ROOT / "analysis" / f"{key}.md"
        ph = phase(ipo, today)
        anchor_done = bool(d.get("anchor_report_url")) if d else None
        out.append({
            "key": key,
            **ipo,
            "phase": ph,
            "price_high": price,
            "lot": lot,
            "subscription": sub if has_live_sub else None,
            "anchor_done": anchor_done,
            "categories": cats,
            "best_category": allotment.best_category(cats),
            "analysis_file": str(analysis_file.relative_to(ROOT)),
            "needs_analysis": not analysis_file.exists(),
            "needs_anchor_update": anchor_pending(analysis_file) and bool(
                anchor_done or ph in ("open", "closing_today", "awaiting_listing", "listing_today")),
        })

    order = {"closing_today": 0, "open": 1, "listing_today": 2, "upcoming": 3,
             "awaiting_listing": 4, "announced": 5, "listed": 6}
    out.sort(key=lambda x: (order.get(x["phase"], 9), x.get("open") or "9999"))
    return {"generated_at": now.isoformat(timespec="minutes"), "date": today,
            "ipos": out, "errors": errors}


def _inr(x):
    if x is None:
        return "-"
    return f"₹{x / 1e5:.2f} L" if x >= 1e5 else f"₹{x:,.0f}"


def _n(x):
    return f"{x:g}" if isinstance(x, (int, float)) else "?"


def _band(lo, hi):
    if lo and hi:
        return f"₹{_n(lo)}–{_n(hi)}"
    return f"₹{_n(hi)} (upper)" if hi else "not announced"


def _anchor(i):
    if i.get("anchor_done"):
        return f"done ({i['nse']['anchor_report_url']})"
    return "not yet" if i.get("nse") else "unknown (not on NSE yet)"


def render_markdown(snap):
    lines = [f"# IPO numbers – {snap['date']} (as of {snap['generated_at'][11:16]} IST)", ""]
    for i in snap["ipos"]:
        d = i.get("nse") or {}
        gmp = (f"₹{i['gmp']:g} ({i['gmp_pct']:g}%)" if i.get("gmp") is not None else "-")
        lines += [
            f"## {i['name']} — {i['phase'].replace('_', ' ')}",
            f"- Dates: open {i.get('open') or '?'} · close {i.get('close') or '?'} · "
            f"allotment {i.get('allotment') or '?'} · listing {i.get('listing') or '?'}",
            f"- Price band: {_band(d.get('price_low'), i.get('price_high'))} · lot {i.get('lot') or '?'} shares"
            f" · size {('₹%g Cr' % i['size_cr']) if i.get('size_cr') else '-'} · P/E {i.get('pe') if i.get('pe') is not None else '-'}",
            f"- GMP: {gmp} · anchor allocation: {_anchor(i)}",
        ]
        if d.get("issue_size_text"):
            lines.append(f"- Issue: {d['issue_size_text']}")
        if d.get("lead_managers"):
            lines.append(f"- Lead managers: {d['lead_managers']} · registrar: {d.get('registrar')}")
        if i.get("subscription"):
            s = i["subscription"]
            lines.append("- Subscription: " + " · ".join(
                f"{k.upper()} {v['times']}x" for k, v in s.items()))
        if i.get("categories"):
            lines += ["", "| Category | Min application | Capital | Odds | Exp. gain | Return on blocked |",
                      "|---|---|---|---|---|---|"]
            for c in i["categories"]:
                lines.append(
                    f"| {c['label']} | {c['min_lots']} lot ({c['min_shares']} sh) | {_inr(c['min_amount'])} | "
                    f"{c['odds_text']} | {_inr(c['expected_gain'])} | "
                    f"{(str(c['return_on_blocked_pct']) + '%') if c['return_on_blocked_pct'] is not None else '-'} |")
            if i.get("best_category"):
                lines.append(f"\nBest category by return on capital: **{i['best_category']}**")
        lines.append("")
    if snap["errors"]:
        lines += ["## Source errors", *[f"- {k}: {v}" for k, v in snap["errors"].items()]]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", help="print markdown digest")
    ap.add_argument("--date", help="override today (YYYY-MM-DD), for testing")
    args = ap.parse_args(argv)

    snap = build(args.date)
    snap_dir = ROOT / "data" / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    stamp = snap["generated_at"][:16].replace(":", "")
    (snap_dir / f"{stamp}.json").write_text(json.dumps(snap, indent=1, ensure_ascii=False))
    (ROOT / "data" / "latest.json").write_text(json.dumps(snap, indent=1, ensure_ascii=False))
    md = render_markdown(snap)
    (ROOT / "data" / "latest.md").write_text(md)
    if args.print:
        print(md)
    print(f"\n{len(snap['ipos'])} mainboard IPOs · errors: {list(snap['errors']) or 'none'}", file=sys.stderr)
    return 0 if snap["ipos"] or not snap["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
