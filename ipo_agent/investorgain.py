"""Investorgain live GMP table: IPO list, dates, price, GMP, P/E.

The page is a Next.js app; the table rows are embedded as JSON inside
`self.__next_f.push([1, "..."])` chunks under the key `reportTableData`.
"""

import html
import json
import re

GMP_URL = "https://www.investorgain.com/report/live-ipo-gmp/331/"

# Status codes seen in the table: U = upcoming, O = open, C = closed (awaiting
# listing), LP / LN = listed at premium / discount.
STATUS = {"U": "upcoming", "O": "open", "C": "closed", "LP": "listed", "LN": "listed"}


def _strip(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).replace("\xa0", " ").strip()


def _num(s):
    s = re.sub(r"[^\d.\-]", "", s or "")
    try:
        return float(s)
    except ValueError:
        return None


def parse(page):
    chunks = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', page)
    stream = "".join(json.loads(c) for c in chunks)
    key = '"reportTableData":'
    i = stream.find(key)
    if i < 0:
        raise ValueError("reportTableData not found; Investorgain layout changed")
    rows, _ = json.JSONDecoder().raw_decode(stream, i + len(key))

    out = []
    for r in rows:
        gmp_text = _strip(r.get("GMP"))
        m = re.search(r"₹\s*([\d.\-]+)", gmp_text)
        lowhigh = re.search(r"([\d.]+)\s*↓\s*/\s*([\d.]+)\s*↑", gmp_text)
        code = (r.get("~ipo_status1") or "").strip()
        out.append(
            {
                "name": (r.get("~ipo_name") or "").strip(),
                "board": "mainboard" if r.get("~ipo_category1") == "IPO" else "sme",
                "status": STATUS.get(code, code),
                "status_code": code,
                "open": r.get("~Srt_Open") or None,
                "close": r.get("~Srt_Close") or None,
                "allotment": r.get("~Srt_BoA_Dt") or None,
                "listing": r.get("~Str_Listing") or None,
                "price": _num(r.get("Price (₹)")) or None,
                "lot": int(_num(r.get("Lot"))) if _num(r.get("Lot")) else None,
                "size_cr": _num(_strip(r.get("IPO Size"))),
                "gmp": _num(m.group(1)) if m else None,
                "gmp_pct": _num(r.get("~gmp_percent_calc")),
                "gmp_low": _num(lowhigh.group(1)) if lowhigh else None,
                "gmp_high": _num(lowhigh.group(2)) if lowhigh else None,
                "pe": _num(r.get("~P/E")),
                "subscription_x": _num(_strip(r.get("Sub"))),
                "gmp_updated": _strip(r.get("Updated-On")),
                "url": "https://www.investorgain.com"
                + (r.get("~urlrewrite_folder_name") or ""),
            }
        )
    return out


def fetch(client):
    return parse(client.get_text(GMP_URL, accept="text/html"))
