"""Render the daily IPO email (HTML + plain text) from the numbers snapshot and
Claude's verdict file, so the layout is identical every day.

Usage:
    python3 -m ipo_agent.email_render reports/2026-10-12-pm.json
      -> reports/2026-10-12-pm.html, reports/2026-10-12-pm.txt, prints the subject line

Each IPO's entry is merged over its cached card, analysis/<key>.json (see cards.py), so the
verdict file only needs what changes run to run; any card field can be overridden here.

Verdict file (written by Claude each run), keyed by snapshot `key`:
{
  "date": "2026-10-12", "session": "PM",
  "headline": "optional one-line takeaway",
  "ipos": {
    "<key>": {
      "verdict": "apply|listing_gains|avoid|neutral|pending",  # optional if the card's still holds
      "verdict_text": "Apply (Retail)",
      "best_category": "Retail",                 # or null
      "category_note": "1 lot per family PAN",   # optional
      # usually from the card, override only if changed:
      "summary": "one sentence: what the company does",
      "financials": "FY26 revenue ₹489 Cr (+13%), PAT ₹117 Cr", # optional
      "quota": "QIB 50% · NII 15% · Retail 35%",  # optional
      "positives": ["...", "..."],
      "red_flags": ["...", "..."],
      "anchor": "Pending" | "₹213 Cr from 18 anchors: SBI MF, ...",
      "anchor_grade": "strong|average|weak|pending"
    }
  },
  "notes": ["optional footer notes"]
}
"""

import datetime as dt
import html
import json
import pathlib
import sys

from . import cards

ROOT = pathlib.Path(__file__).resolve().parent.parent

VERDICT = {  # label, background, text colour
    "apply": ("Apply", "#E6F4EA", "#137333"),
    "listing_gains": ("Listing gains only", "#FEF7E0", "#B06000"),
    "avoid": ("Avoid", "#FCE8E6", "#C5221F"),
    "neutral": ("Neutral", "#F1F3F4", "#3C4043"),
    "pending": ("Analysis pending", "#F1F3F4", "#5F6368"),
}
PHASE_COLOR = {
    "closing_today": ("#FCE8E6", "#C5221F"),
    "open": ("#E6F4EA", "#137333"),
    "listing_today": ("#F3E8FD", "#8430CE"),
    "awaiting_listing": ("#F3E8FD", "#8430CE"),
    "upcoming": ("#E8F0FE", "#1967D2"),
    "announced": ("#F1F3F4", "#5F6368"),
}
TREND = {"up": ("↑", "📈", "#137333"), "down": ("↓", "📉", "#C5221F"), "flat": ("→", "➡️", "#5F6368")}
GRADE = {"strong": ("Strong", "#137333"), "average": ("Average", "#B06000"),
         "weak": ("Weak", "#C5221F"), "pending": ("Pending", "#5F6368")}
FONT = "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"


def table(style="", bg=None, width="100%"):
    """Layout table. Backgrounds go in a bgcolor attribute plus background-color: Gmail drops the
    `background:` shorthand, which left the header's white text on a white page."""
    attrs = f' bgcolor="{bg}"' if bg else ""
    style = (f"background-color:{bg};" if bg else "") + style
    return (f'<table role="presentation" width="{width}" cellpadding="0" cellspacing="0"{attrs}'
            + (f' style="{style}"' if style else "") + ">")


def esc(s):
    return html.escape(str(s if s is not None else ""))


def d(s):
    return dt.date.fromisoformat(s) if s else None


def fmt_day(s):
    x = d(s)
    return x.strftime("%a %d %b") if x else "?"


def inr(x):
    if x is None:
        return "–"
    if x >= 1e5:
        return f"₹{x / 1e5:.2f} L"
    return f"₹{x:,.0f}"


def gmp_text(ipo, short=False):
    if ipo.get("gmp") is None:
        return "–"
    if not ipo.get("price_high"):  # no price band yet: % is meaningless
        return f"₹{ipo['gmp']:g}"
    return f"{ipo['gmp_pct']:+.0f}%" if short else f"₹{ipo['gmp']:g} ({ipo['gmp_pct']:+.1f}%)"


def trend(ipo, kind):
    return (ipo.get("trend") or {}).get(kind)


def gmp_arrow(ipo):
    """Glance-row arrow for the GMP trend (rising/falling only)."""
    t = trend(ipo, "gmp")
    if not t or t["direction"] == "flat":
        return ""
    arrow, _, color = TREND[t["direction"]]
    return f' <span style="color:{color};font-weight:700">{arrow}</span>'


def gmp_trend_line(ipo):
    t = trend(ipo, "gmp")
    if not t:
        return ""
    _, icon, color = TREND[t["direction"]]
    return f'<p style="font-size:13px;color:{color};font-weight:600;margin:0 0 4px">{icon} {esc(t["text"])}</p>'


def sub_by_day(t):
    """Category × bidding-day table of subscription (shown once there are 2+ days)."""
    head = ('<tr bgcolor="#F1F3F4"><th></th>'
            + "".join(f'<th style="padding:5px 8px;font-size:11px;color:#5F6368;text-align:right">Day {x["day"]}'
                      f'<div style="font-weight:400">{esc(dt.date.fromisoformat(x["date"]).strftime("%a %d"))}</div></th>'
                      for x in t["days"]) + "</tr>")
    rows = []
    for k, label in (("retail", "Retail"), ("snii", "Small HNI"), ("bnii", "Big HNI"), ("qib", "QIB"), ("total", "Total")):
        if not all(k in x["times"] for x in t["days"]):
            continue
        bold = "font-weight:700;" if k == "total" else ""
        rows.append(f'<tr><td style="padding:4px 8px;font-size:13px;color:#3C4043;{bold}">{label}</td>'
                    + "".join(f'<td style="padding:4px 8px;font-size:13px;text-align:right;{bold}">{x["times"][k]:g}x</td>'
                              for x in t["days"]) + "</tr>")
    return (f'<div style="font-size:13px;font-weight:700;color:#202124;margin:14px 0 4px">Subscription by day</div>'
            + table("border:1px solid #E8EAED;border-radius:8px;border-collapse:separate;overflow:hidden")
            + f'{head}{"".join(rows)}</table>')


def phase_label(ipo, today):
    ph, o, c, l = ipo["phase"], ipo.get("open"), ipo.get("close"), ipo.get("listing")
    t = d(today)
    if ph == "closing_today":
        return "Closes today"
    if ph == "open":
        return f"Open · closes {fmt_day(c)}"
    if ph == "upcoming":
        return "Opens tomorrow" if d(o) == t + dt.timedelta(days=1) else f"Opens {fmt_day(o)}"
    if ph == "awaiting_listing":
        return f"Lists {fmt_day(l)}"
    if ph == "listing_today":
        return "Lists today"
    return "Announced"


def pill(text, bg, fg, size=12):
    return (f'<span style="display:inline-block;padding:3px 10px;border-radius:999px;'
            f'background-color:{bg};color:{fg};font-size:{size}px;font-weight:600;line-height:1.3">{esc(text)}</span>')


def fact(label, value):
    return (f'<td valign="top" width="50%" style="padding:8px 10px">'
            f'<div style="font-size:11px;color:#5F6368">{esc(label.upper())}</div>'
            f'<b style="font-size:14px;color:#202124">{value}</b></td>')


def facts_grid(pairs):
    rows = []
    for i in range(0, len(pairs), 2):
        cells = "".join(fact(k, v) for k, v in pairs[i:i + 2])
        if len(pairs[i:i + 2]) == 1:
            cells += '<td width="50%"></td>'
        rows.append(f"<tr>{cells}</tr>")
    return table("border-radius:8px;margin:12px 0", "#F8F9FA") + f'{"".join(rows)}</table>'


def sub_table(sub):
    order = [("qib", "QIB"), ("nii", "NII (total)"), ("bnii", "Big HNI"), ("snii", "Small HNI"),
             ("retail", "Retail"), ("employee", "Employee"), ("total", "Total")]
    mx = max((v["times"] for v in sub.values()), default=1) or 1
    rows = []
    for k, label in order:
        if k not in sub:
            continue
        t = sub[k]["times"]
        w = max(2, int(100 * t / mx))
        bold = "font-weight:700;" if k == "total" else ""
        rows.append(
            f'<tr><td style="padding:4px 0;font-size:13px;color:#3C4043;{bold}width:90px">{label}</td>'
            f'<td style="padding:4px 8px">{table("border-radius:4px", "#E8F0FE")}<tr><td>{table("border-radius:4px", "#1A73E8", f"{w}%")}'
            f'<tr><td height="10" style="font-size:0;line-height:0">&nbsp;</td></tr></table></td></tr></table></td>'
            f'<td style="padding:4px 0;font-size:13px;text-align:right;{bold}width:60px">{t:g}x</td></tr>')
    return (f'<div style="font-size:13px;font-weight:700;color:#202124;margin:14px 0 4px">Live subscription</div>'
            + table() + f'{"".join(rows)}</table>')


def category_table(cats, best):
    head = ('<tr bgcolor="#F1F3F4">'
            + "".join(f'<th align="{a}" style="padding:6px 8px;font-size:11px;color:#5F6368">{h.upper()}</th>'
                      for h, a in (("Category", "left"), ("Min", "left"),
                                   ("Amount", "right"), ("Odds", "right")))
            + "</tr>")
    rows = []
    for c in cats:
        is_best = best and c["category"] == best
        star = ' <span style="color:#137333">★</span>' if is_best else ""
        bg = ' bgcolor="#E6F4EA"' if is_best else ""
        cell = 'style="padding:6px 8px;font-size:13px"'
        rows.append(
            f'<tr{bg}><td style="padding:6px 8px;font-size:13px;font-weight:600">{esc(SHORT.get(c["category"], c["label"]))}{star}</td>'
            f'<td nowrap {cell}>{c["min_lots"]} lot</td>'
            f'<td align="right" {cell}>{inr(c["min_amount"])}</td>'
            f'<td align="right" {cell}>{esc(odds(c))}</td></tr>')
    return (f'<div style="font-size:13px;font-weight:700;color:#202124;margin:14px 0 4px">Where to apply</div>'
            + table("border:1px solid #E8EAED;border-radius:8px;border-collapse:separate;overflow:hidden")
            + f'{head}{"".join(rows)}</table>'
            + ('<div style="font-size:11px;color:#80868B;margin-top:4px">★ best category · odds appear once bidding starts</div>'
               if all(c["odds_text"] == "n/a" for c in cats) else
               '<div style="font-size:11px;color:#80868B;margin-top:4px">★ best category · odds are a conservative floor</div>'))


SHORT = {"retail": "Retail", "snii": "Small HNI", "bnii": "Big HNI"}


def odds(c):
    return "–" if c["odds_text"] == "n/a" else c["odds_text"]


def bullets(items, icon, color):
    if not items:
        return ""
    lis = "".join(f'<tr><td valign="top" style="padding:2px 8px 2px 0;color:{color};font-size:14px">{icon}</td>'
                  f'<td style="padding:2px 0;font-size:14px;color:#3C4043;line-height:1.45">{esc(t)}</td></tr>'
                  for t in items)
    return table("margin:4px 0", width="auto") + f'{lis}</table>'


def best_label(ipo, v):
    best = v.get("best_category") or ipo.get("best_category")
    return {"retail": "Retail", "snii": "Small HNI", "bnii": "Big HNI"}.get(str(best).lower(), best)


def card(ipo, v, today):
    vk = v.get("verdict", "pending")
    vlabel, vbg, vfg = VERDICT.get(vk, VERDICT["pending"])
    vtext = v.get("verdict_text") or vlabel
    pbg, pfg = PHASE_COLOR.get(ipo["phase"], PHASE_COLOR["announced"])
    nse = ipo.get("nse") or {}
    band = (f"₹{nse['price_low']:g}–{ipo['price_high']:g}" if nse.get("price_low") and ipo.get("price_high")
            else (f"₹{ipo['price_high']:g} (upper)" if ipo.get("price_high") else "Not announced"))
    gmp = gmp_text(ipo)
    gmp_color = "#137333" if (ipo.get("gmp_pct") or 0) > 0 else "#5F6368"
    retail_min = next((c["min_amount"] for c in ipo.get("categories", []) if c["category"] == "retail"), None)
    pairs = [
        ("Bidding", f"{fmt_day(ipo.get('open'))} – {fmt_day(ipo.get('close'))}" if ipo.get("open") else "Dates TBA"),
        ("Listing", fmt_day(ipo.get("listing")) if ipo.get("listing") else "TBA"),
        ("Price band", band),
        ("Lot / retail min", f"{ipo.get('lot') or '?'} sh · {inr(retail_min)}" if ipo.get("lot") else "–"),
        ("Issue size", f"₹{ipo['size_cr']:,.0f} Cr" if ipo.get("size_cr") else "–"),
        ("P/E", ("Loss-making" if ipo["pe"] < 0 else f"{ipo['pe']:g}x") if ipo.get("pe") else "–"),
        ("GMP", f'<span style="color:{gmp_color}">{esc(gmp)}</span>'),
    ]
    if v.get("quota"):
        pairs.append(("Quota", esc(v["quota"])))

    body = [
        f'<div style="font-size:19px;font-weight:700;color:#202124">{esc(ipo["name"])}</div>',
        f'<div style="margin:8px 0 2px">{pill(vtext, vbg, vfg, 13)} {pill(phase_label(ipo, today), pbg, pfg, 13)}</div>',
        (f'<div style="font-size:13px;color:#5F6368;margin-top:6px">Best category: <b style="color:#202124">'
         f'{esc(best_label(ipo, v))}</b>' + (f" · {esc(v['category_note'])}" if v.get("category_note") else "") + "</div>"
         if best_label(ipo, v) else ""),
    ]
    if v.get("summary"):
        body.append(f'<p style="font-size:14px;color:#3C4043;line-height:1.5;margin:10px 0 0">{esc(v["summary"])}</p>')
    if v.get("financials"):
        body.append(f'<p style="font-size:13px;color:#5F6368;margin:4px 0 0">📊 {esc(v["financials"])}</p>')
    body.append(facts_grid(pairs))
    body.append(gmp_trend_line(ipo))
    if ipo.get("subscription"):
        body.append(sub_table(ipo["subscription"]))
    if trend(ipo, "subscription"):
        body.append(sub_by_day(trend(ipo, "subscription")))
    if ipo.get("categories") and ipo["phase"] != "announced":
        body.append(category_table(ipo["categories"], (v.get("best_category") or ipo.get("best_category") or "").lower()
                                   .replace("small hni", "snii").replace("big hni", "bnii")))
    if v.get("positives"):
        body.append('<div style="font-size:13px;font-weight:700;color:#137333;margin:14px 0 2px">Why consider</div>'
                    + bullets(v["positives"], "✓", "#137333"))
    if v.get("red_flags"):
        body.append('<div style="font-size:13px;font-weight:700;color:#C5221F;margin:12px 0 2px">Red flags</div>'
                    + bullets(v["red_flags"], "!", "#C5221F"))
    if v.get("anchor"):
        g, gc = GRADE.get((v.get("anchor_grade") or "pending").lower(), GRADE["pending"])
        body.append(f'<p style="font-size:13px;color:#3C4043;margin:12px 0 0"><b>Anchor book:</b> '
                    f'<span style="color:{gc};font-weight:700">{g}</span> · {esc(v["anchor"])}</p>')
    return (f'<tr><td style="padding:0 0 16px">{table("border:1px solid #E8EAED;border-radius:12px", "#FFFFFF")}'
            f'<tr><td style="padding:18px 20px">{"".join(body)}</td></tr></table></td></tr>')


def glance(ipos, verdicts, today):
    rows = []
    for i in ipos:
        v = verdicts.get(i["key"], {})
        vlabel, vbg, vfg = VERDICT.get(v.get("verdict", "pending"), VERDICT["pending"])
        rows.append(
            f'<tr><td style="padding:9px 0;border-bottom:1px solid #F1F3F4;font-size:14px;font-weight:600;color:#202124">'
            f'{esc(i["name"])}<div style="font-size:12px;font-weight:400;color:#5F6368;margin-top:1px">'
            f'{esc(phase_label(i, today))} · GMP {esc(gmp_text(i, short=True))}{gmp_arrow(i)}</div></td>'
            f'<td align="right" valign="middle" style="padding:9px 0 9px 8px;border-bottom:1px solid #F1F3F4">'
            f'{pill(v.get("verdict_text") or vlabel, vbg, vfg, 11)}</td></tr>')
    return (f'<tr><td style="padding:0 0 16px">{table("border:1px solid #E8EAED;border-radius:12px", "#FFFFFF")}<tr><td style="padding:16px 18px">'
            f'<div style="font-size:12px;font-weight:700;color:#5F6368;letter-spacing:.5px;margin-bottom:2px">AT A GLANCE</div>'
            f'{table()}{"".join(rows)}</table>'
            f'</td></tr></table></td></tr>')


def counts(ipos):
    n_open = sum(i["phase"] in ("open", "closing_today") for i in ipos)
    n_up = sum(i["phase"] == "upcoming" for i in ipos)
    closing = [i["name"] for i in ipos if i["phase"] == "closing_today"]
    return n_open, n_up, closing


def subject(rep, ipos):
    n_open, n_up, closing = counts(ipos)
    s = f"IPO brief {fmt_day(rep['date'])} {rep['session']}: {n_open} open, {n_up} upcoming"
    if closing:
        s += " · CLOSING TODAY: " + ", ".join(closing)
    return s


def merged(rep, ipos):
    """Per-IPO verdicts: cached card fields, overridden by this run's entry."""
    out = {}
    for i in ipos:
        v = {**(cards.load(i["key"]) or {}), **rep.get("ipos", {}).get(i["key"], {})}
        if v:
            out[i["key"]] = v
    return out


def render_html(rep, snap):
    today = rep["date"]
    ipos = snap["ipos"]
    verdicts = merged(rep, ipos)
    n_open, n_up, closing = counts(ipos)
    stats = " &nbsp;·&nbsp; ".join(x for x in (
        f"<b>{n_open}</b> open", f"<b>{n_up}</b> upcoming",
        f'<b style="color:#FDD663">{len(closing)} closing today</b>' if closing else "") if x)
    headline = (f'<div style="font-size:15px;color:#FFFFFF;margin-top:10px;line-height:1.4">{esc(rep["headline"])}</div>'
                if rep.get("headline") else "")
    notes = "".join(f"<li>{esc(n)}</li>" for n in rep.get("notes", []))
    errs = snap.get("errors") or {}
    src = f"Data as of {snap['generated_at'][11:16]} IST · NSE, SEBI, Investorgain, company RHPs" + \
          (f" · source errors: {esc(', '.join(errs))}" if errs else "")
    return f"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><meta charset="utf-8"></head><body bgcolor="#F1F3F4" style="margin:0;padding:0;background-color:#F1F3F4;{FONT}word-break:break-word;-webkit-text-size-adjust:100%">
{table(bg="#F1F3F4")}<tr><td align="center" style="padding:20px 12px">
{table("max-width:640px")}
<tr><td style="padding:0 0 16px">{table("border-radius:12px", "#1A3D7C")}
<tr><td style="padding:22px 24px">
<div style="font-size:12px;color:#AECBFA;letter-spacing:1px">{esc(rep['session'])} BRIEF · {esc(dt.date.fromisoformat(today).strftime('%A, %d %B %Y').upper())}</div>
<div style="font-size:26px;font-weight:700;color:#FFFFFF;margin-top:4px">📈 IPO Brief</div>
<div style="font-size:14px;color:#D2E3FC;margin-top:6px">{stats} &nbsp;·&nbsp; mainboard</div>{headline}
</td></tr></table></td></tr>
{glance(ipos, verdicts, today)}
{''.join(card(i, verdicts.get(i['key'], {}), today) for i in ipos)}
<tr><td style="padding:4px 8px 24px;font-size:12px;color:#80868B;line-height:1.5">
{('<ul style="margin:0 0 8px;padding-left:18px">' + notes + '</ul>') if notes else ''}
{src}<br>Odds are conservative (≥ 1 in subscription-times). Research aid, not investment advice. GMP is unofficial and can be manipulated.
</td></tr></table></td></tr></table></body></html>"""


def render_text(rep, snap):
    today = rep["date"]
    ipos = snap["ipos"]
    verdicts = merged(rep, ipos)
    n_open, n_up, closing = counts(ipos)
    L = [f"IPO BRIEF · {rep['session']} · {dt.date.fromisoformat(today).strftime('%a %d %b %Y')}",
         f"{n_open} open · {n_up} upcoming" + (f" · CLOSING TODAY: {', '.join(closing)}" if closing else ""), ""]
    if rep.get("headline"):
        L += [rep["headline"], ""]
    L += ["AT A GLANCE", "─" * 40]
    for i in ipos:
        v = verdicts.get(i["key"], {})
        vt = v.get("verdict_text") or VERDICT.get(v.get("verdict", "pending"), VERDICT["pending"])[0]
        arrow = TREND[trend(i, "gmp")["direction"]][0] if trend(i, "gmp") else ""
        L.append(f"• {i['name']} — {phase_label(i, today)} — {vt} — GMP {gmp_text(i, short=True)} {arrow}".rstrip())
    for i in ipos:
        v = verdicts.get(i["key"], {})
        vt = v.get("verdict_text") or VERDICT.get(v.get("verdict", "pending"), VERDICT["pending"])[0]
        nse = i.get("nse") or {}
        L += ["", "━" * 40, f"{i['name'].upper()}", f"{phase_label(i, today)}  |  {vt}"]
        if best_label(i, v):
            L.append(f"Best category: {best_label(i, v)}" + (f" ({v['category_note']})" if v.get("category_note") else ""))
        L.append("━" * 40)
        if v.get("summary"):
            L += [v["summary"]]
        if v.get("financials"):
            L += [f"Financials: {v['financials']}"]
        band = (f"₹{nse['price_low']:g}–{i['price_high']:g}" if nse.get("price_low") and i.get("price_high")
                else (f"₹{i['price_high']:g}" if i.get("price_high") else "not announced"))
        size = f"₹{i['size_cr']:,.0f} Cr" if i.get("size_cr") else "–"
        pe = ("loss-making" if i["pe"] < 0 else f"{i['pe']:g}x") if i.get("pe") else "–"
        L += [f"Bidding: {fmt_day(i.get('open'))} – {fmt_day(i.get('close'))}   Listing: {fmt_day(i.get('listing'))}",
              f"Price band: {band}   Lot: {i.get('lot') or '?'}   Size: {size}",
              f"P/E: {pe}   GMP: {gmp_text(i)}"]
        if trend(i, "gmp"):
            L.append(trend(i, "gmp")["text"])
        if v.get("quota"):
            L.append(f"Quota: {v['quota']}")
        if i.get("subscription"):
            L.append("Subscription: " + " · ".join(f"{k.upper()} {s['times']:g}x" for k, s in i["subscription"].items()))
        if trend(i, "subscription"):
            L.append(f"Subscription by day — {trend(i, 'subscription')['text']}")
        if i.get("categories") and i["phase"] != "announced":
            L.append("Where to apply:")
            for c in i["categories"]:
                L.append(f"   {c['label']:<17} {c['min_lots']:>3} lot  {inr(c['min_amount']):>10}  odds {odds(c)}")
        for t in v.get("positives", []):
            L.append(f"  ✓ {t}")
        for t in v.get("red_flags", []):
            L.append(f"  ⚠ {t}")
        if v.get("anchor"):
            g = GRADE.get((v.get("anchor_grade") or "pending").lower(), GRADE["pending"])[0]
            L.append(f"Anchor book: {g} · {v['anchor']}")
    L += ["", "─" * 40] + [f"• {n}" for n in rep.get("notes", [])]
    L += [f"Data as of {snap['generated_at'][11:16]} IST. Research aid, not investment advice. GMP is unofficial."]
    return "\n".join(L)


def main(argv=None):
    argv = argv or sys.argv[1:]
    rep_path = pathlib.Path(argv[0])
    rep = json.loads(rep_path.read_text())
    snap = json.loads((ROOT / "data" / "latest.json").read_text())
    page = render_html(rep, snap)
    rep_path.with_suffix(".html").write_text(page)
    if len(page.encode()) > 95_000:
        print(f"warning: HTML is {len(page.encode()) // 1000} KB; Gmail clips emails above ~102 KB", file=sys.stderr)
    rep_path.with_suffix(".txt").write_text(render_text(rep, snap))
    missing = [i["key"] for i in snap["ipos"] if i["key"] not in merged(rep, snap["ipos"])]
    if missing:
        print(f"warning: no card or verdict for {missing}", file=sys.stderr)
    print(subject(rep, snap["ipos"]))


if __name__ == "__main__":
    main()
