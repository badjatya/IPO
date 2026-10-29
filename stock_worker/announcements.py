"""Corporate announcements: the per-symbol and market-wide
``corporate-announcements`` responses (the same paths parse both).

Records are keyed exactly as the ``db.md`` ``announcements`` columns:

``symbol``         ``symbol`` (present on per-symbol and market rows alike)
``subject``        ``desc`` — the exchange's category, kept raw
``announced_at``   ``an_dt`` (NSE local time, ISO with +05:30)
``title``          ``attchmntText``, kept raw
``attachment_url`` ``attchmntFile`` (absolute; ``None`` when the row has none)
``exchange_ref``   ``seq_id`` — the exchange's own ID, the dedupe key
``industry``       ``smIndustry``, kept raw (``None`` when absent)

The optional ``since`` (an ISO timestamp) is a code-side filter: rows
announced before it are dropped, so a daily run is one call that keeps only
what's new. Missing fields are ``None``, never estimated.
"""

from .util import parse_timestamp


def _rows(body):
    if isinstance(body, dict):
        for key in ("data", "announcements"):
            if isinstance(body.get(key), list):
                return body[key]
        return []
    return body or []


def parse(rows, since=None):
    """Parse an announcements response into records, dropping rows announced
    strictly before ``since`` (an ISO timestamp) when one is given."""
    records = []
    for row in _rows(rows):
        announced_at = parse_timestamp(row.get("an_dt"))
        if since is not None and announced_at is not None and announced_at < since:
            continue
        seq_id = row.get("seq_id")
        records.append(
            {
                "symbol": row.get("symbol"),
                "subject": row.get("desc"),
                "announced_at": announced_at,
                "title": row.get("attchmntText"),
                "attachment_url": row.get("attchmntFile"),
                "exchange_ref": str(seq_id) if seq_id is not None else None,
                "industry": row.get("smIndustry"),
            }
        )
    return records