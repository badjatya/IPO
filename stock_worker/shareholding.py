"""Shareholding pattern: the ``corporate-share-holdings-master`` response.

Records are keyed exactly as the ``db.md`` ``shareholding`` columns:

``quarter_end``    ``date`` (ISO date) — the natural key
``filed_at``       ``submissionDate``; NSE states a date only in the sampled
                   rows, so this is the ISO date string, no time invented
``promoter_pct``   ``pr_and_prgrp`` (percent, Decimal)
``public_pct``     ``public_val``
``other_pct``      ``employeeTrusts`` (a stated ``"0"`` is a value)
``source_url``     ``xbrl``

``fii_pct`` and ``dii_pct`` are **always** ``None`` here when the JSON does not
carry them, and are parsed when a future response adds them (forward
compatible). The FII/DII split exists only in the XBRL filing; parsing that is
a recorded gap for 016/018, never an inference from these rows.
"""

from .util import parse_date, parse_timestamp, to_decimal


def _rows(body):
    if isinstance(body, dict):
        for key in ("data", "shareholdingPattern"):
            if isinstance(body.get(key), list):
                return body[key]
        return []
    return body or []


def parse(rows):
    """Parse a shareholding response into records."""
    records = []
    for row in _rows(rows):
        records.append(
            {
                "quarter_end": parse_date(row.get("date")),
                "filed_at": parse_timestamp(row.get("submissionDate")),
                "promoter_pct": to_decimal(row.get("pr_and_prgrp")),
                "fii_pct": to_decimal(row.get("fii")),
                "dii_pct": to_decimal(row.get("dii")),
                "public_pct": to_decimal(row.get("public_val")),
                "other_pct": to_decimal(row.get("employeeTrusts")),
                "source_url": row.get("xbrl"),
            }
        )
    return records