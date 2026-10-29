"""Corporate announcements: the per-symbol and market-wide
``corporate-announcements`` responses (the same paths parse both).

Records are keyed exactly as the ``db.md`` ``announcements`` columns:

``symbol``         ``symbol`` (present on per-symbol and market rows alike)
``subject``        ``desc`` — the exchange's category, kept raw
``announced_at``   ``an_dt`` (NSE local time, ISO with +05:30)
``title``          ``attchmntText``, kept raw
``attachment_url`` ``attchmntFile`` (absolute; ``None`` when the row has none)
``exchange_ref``   ``seq_id`` — the exchange's own ID, the dedupe key

Extras (no db.md column; kept in the record as the plan requires):
``industry``       ``smIndustry``, kept raw (``None`` when absent)

The optional ``since`` (a full ISO timestamp, or a timezone-aware ``datetime``
object) is a code-side filter: rows announced strictly before it are dropped,
so a daily run is one call that keeps only what's new. Both sides are compared
as timezone-aware moments via ``util.to_aware_datetime``: ``since``'s offset
is kept, a naive string is read as NSE local time (+05:30), a date-only
``since`` as midnight +05:30, and a ``since`` that parses to nothing raises
``ValueError`` (018 passes a stored run time — a ``datetime`` object or a
``timestamptz`` string, which may print with a ``Z`` or fractional seconds —
so new-row detection compares like for like). Rows without a usable
``announced_at`` are kept — they cannot be proven older. Missing fields are
``None``, never estimated.
"""

from .util import parse_timestamp, to_aware_datetime


def _rows(body):
    if isinstance(body, dict):
        for key in ("data", "announcements"):
            if isinstance(body.get(key), list):
                return body[key]
        return []
    return body or []


def _since_moment(since):
    """``since`` as a timezone-aware moment; junk raises ``ValueError``."""
    moment = to_aware_datetime(since)
    if moment is None:
        raise ValueError(
            "since must be a full ISO timestamp, e.g. '2026-10-29T05:00:00+00:00'"
            f" (a naive value is read as +05:30, a date-only value as midnight "
            f"+05:30); got {since!r}"
        )
    return moment


def parse(rows, since=None):
    """Parse an announcements response into records, dropping rows announced
    strictly before ``since`` (a full ISO timestamp or a timezone-aware
    ``datetime``) when one is given."""
    since_moment = _since_moment(since) if since is not None else None
    records = []
    for row in _rows(rows):
        announced_at = parse_timestamp(row.get("an_dt"))
        if since_moment is not None:
            moment = to_aware_datetime(announced_at)
            if moment is not None and moment < since_moment:
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