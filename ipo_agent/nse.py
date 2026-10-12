"""NSE public IPO APIs: current/upcoming issues, issue details and live
category-wise subscription (consolidated bid details).

NSE needs a session cookie: hit an HTML page first, then call /api/* with a
Referer. The homepage may answer 403 but still sets the cookies we need.
"""

import json
import re

BASE = "https://www.nseindia.com"
REFERER = BASE + "/market-data/all-upcoming-issues-ipo"
MAINBOARD_SERIES = {"EQ", "BE"}  # "SME" = SME platform; BE = mainboard in trade-for-trade


class NSE:
    def __init__(self, client):
        self.client = client
        self._primed = False

    def _prime(self):
        if self._primed:
            return
        for url in (BASE + "/", REFERER):
            try:
                self.client.get(url, accept="text/html")
            except Exception:
                pass
        self._primed = True

    def api(self, path):
        self._prime()
        body = self.client.get_text(
            BASE + path, referer=REFERER, accept="application/json"
        )
        return json.loads(body)

    def current(self):
        return self.api("/api/ipo-current-issue")

    def upcoming(self):
        return self.api("/api/all-upcoming-issues?category=ipo")

    def detail(self, symbol, series="EQ"):
        return parse_detail(self.api(f"/api/ipo-detail?symbol={symbol}&series={series}"))


def _clean(v):
    if v is None:
        return None
    v = re.sub(r"<[^>]+>", " ", str(v)).strip().strip('"').strip()
    return re.sub(r"\s+", " ", v)


def _f(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


# Map NSE bid-detail rows to stable keys. Order matters: bNII/sNII rows also
# contain "Non Institutional Investors".
_CATEGORY_RULES = [
    ("bnii", lambda c: "more than ten lakh" in c),
    ("snii", lambda c: "two lakh" in c),
    ("qib", lambda c: c.startswith("qualified institutional")),
    ("nii", lambda c: c.startswith("non institutional investors")),
    ("retail", lambda c: c.startswith("retail individual")),
    ("employee", lambda c: "employee" in c),
    ("shareholder", lambda c: "shareholder" in c),
    ("total", lambda c: c == "total"),
]


def parse_subscription(bid_details):
    out = {}
    for row in bid_details or []:
        cat = (row.get("category") or "").strip().lower()
        offered = _f(row.get("noOfSharesOffered"))
        if not offered:  # sub-rows (FII, MF, corporates...) have no offered qty
            continue
        for key, match in _CATEGORY_RULES:
            if match(cat) and key not in out:
                out[key] = {
                    "shares_offered": offered,
                    "shares_bid": _f(row.get("noOfsharesBid")),
                    "times": round(_f(row.get("noOfTime")) or 0.0, 2),
                }
                break
    return out


def parse_detail(d):
    info = {}
    for row in (d.get("issueInfo") or {}).get("dataList", []):
        if row.get("title"):
            info[row["title"].strip()] = _clean(row.get("value"))

    price = info.get("Price Range") or ""
    nums = [float(x) for x in re.findall(r"Rs\.?\s*([\d,.]+)", price.replace(",", ""))]
    lot = re.search(r"(\d+)\s*Equity", info.get("Bid Lot") or "")
    period = re.findall(r"\d{2}-[A-Za-z]{3}-\d{4}", info.get("Issue Period") or "")

    rows = (d.get("issueInfo") or {}).get("dataList") or [{}]
    return {
        "company": (rows[0].get("title") or d.get("companyName") or "").strip(),
        "symbol": info.get("Symbol"),
        "issue_period": period,
        "price_low": nums[0] if nums else None,
        "price_high": nums[-1] if nums else None,
        "face_value": info.get("Face Value"),
        "lot": int(lot.group(1)) if lot else None,
        "issue_size_text": info.get("Issue Size"),
        "employee_discount": info.get("Discount"),
        "lead_managers": info.get("Book Running Lead Managers"),
        "registrar": info.get("Name of the Registrar"),
        "rhp_url": info.get("Red Herring Prospectus"),
        "ratios_url": info.get("Ratios / Basis of Issue Price"),
        "anchor_report_url": info.get("Anchor Allocation Report"),
        "subscription": parse_subscription(d.get("bidDetails")),
    }
