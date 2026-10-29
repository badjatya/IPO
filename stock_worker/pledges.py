"""Pledged shares: the per-symbol and market-wide ``corporate-pledgedata``
responses (the same paths parse both).

Records carry the ``db.md`` ``shareholding`` column names where one exists and
extras for the rest (listed here as the plan requires):

``quarter_end``          ``shp`` (ISO date; the natural key)
``promoter_pct``         ``percPromoterHolding`` (percent, leading spaces
                         stripped)
``promoter_pledged_pct`` COMPUTED in code — ``shares_pledged /
                         shares_held × 100``, round HALF_UP to 2 dp. NSE's own
                         ``percSharesPledged`` is a share of *all* shares and
                         is never used for this column (003's finding)
Extras: ``company`` (``comName``, the only identifier — the rows never carry a
symbol; the caller resolves the name, 015/018), ``shares_held``
(``totPromoterHolding``), ``shares_pledged`` (``numSharesPledged``),
``disclosed_at`` (``broadcastDt``), ``pledged_pct_of_total``
(``percSharesPledged``, kept raw for reference).

Missing fields are ``None``, never estimated; a stated ``0`` is a value. A row
whose promoter holding is missing or zero yields ``promoter_pledged_pct=None``
(no division by zero). A ``symbol`` key is never fabricated.
"""

from decimal import ROUND_HALF_UP, Decimal

from .util import parse_date, parse_timestamp, to_decimal


def _rows(body):
    if isinstance(body, dict):
        return body.get("data") or []
    return body or []


def _pledged_pct(shares_held, shares_pledged):
    if not shares_held or shares_pledged is None:
        return None
    return (shares_pledged / shares_held * Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def parse(body):
    """Parse a pledges response into records."""
    records = []
    for row in _rows(body):
        shares_held = to_decimal(row.get("totPromoterHolding"))
        shares_pledged = to_decimal(row.get("numSharesPledged"))
        records.append(
            {
                "company": str(row.get("comName") or "").strip(),
                "quarter_end": parse_date(row.get("shp")),
                "disclosed_at": parse_timestamp(row.get("broadcastDt")),
                "shares_held": shares_held,
                "shares_pledged": shares_pledged,
                "promoter_pledged_pct": _pledged_pct(shares_held, shares_pledged),
                "promoter_pct": to_decimal(row.get("percPromoterHolding")),
                "pledged_pct_of_total": to_decimal(row.get("percSharesPledged")),
            }
        )
    return records