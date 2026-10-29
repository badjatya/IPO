"""Parsing helpers shared by the stock fetchers.

The NSE responses are strings with Indian digit grouping ("1,28,26,000"),
leading spaces ("    71.97") and NSE-local dates and times
("31-DEC-2024", "30-Sep-2026", "29-Oct-2026 08:55:40", "16-Jan-2025 20:20").
Every helper returns ``None`` for junk or missing input: a missing field is
always ``None``, never zero and never estimated. The exactness of a number is
a ``decimal.Decimal``, never ``float`` (db.md principle 5).
"""

import datetime as dt
import re
from decimal import ROUND_HALF_UP, Decimal

_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

_ISO_TS_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?([+-]\d{2}:\d{2})?$"
)
_NSE_TS_RE = re.compile(
    r"^(\d{1,2})-([A-Za-z]{3})-(\d{4})[ ](\d{1,2}):(\d{2})(?::(\d{2}))?$"
)
_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_NSE_DATE_RE = re.compile(r"^(\d{1,2})-([A-Za-z]{3})-(\d{4})$")


def get_path(obj, path):
    """Look up a dotted path in a JSON object, e.g. ``priceInfo.lastPrice``.

    A ``[]`` part means "the first element of a list" (the smoke probe's
    convention). Returns ``None`` when any step is missing or unexpected.
    """
    for part in path.split("."):
        if part == "[]":
            if not isinstance(obj, list) or not obj:
                return None
            obj = obj[0]
            continue
        list_key = part.endswith("[]")
        key = part[:-2] if list_key else part
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
        if obj is None:
            return None
        if list_key:
            if not isinstance(obj, list) or not obj:
                return None
            obj = obj[0]
    return obj


def to_decimal(value):
    """Parse an NSE number string into ``Decimal``; junk or missing -> ``None``.

    Commas (Indian digit grouping, e.g. ``1,28,26,000``) and surrounding
    whitespace are stripped first. A stated ``"0"`` is a value, not a missing
    field.
    """
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except ArithmeticError:
        return None


def parse_date(value):
    """NSE ``DD-MMM-YYYY`` (any month case) or ISO ``YYYY-MM-DD`` -> ISO date.

    Returns ``YYYY-MM-DD``; junk or an impossible date -> ``None``.
    """
    if value is None:
        return None
    text = str(value).strip()
    match = _NSE_DATE_RE.fullmatch(text)
    if match:
        day, mon, year = match.groups()
        month = _MONTHS.get(mon.upper())
        if month is None:
            return None
        try:
            return dt.date(int(year), month, int(day)).isoformat()
        except ValueError:
            return None
    match = _ISO_DATE_RE.fullmatch(text)
    if match:
        year, mon, day = match.groups()
        try:
            return dt.date(int(year), int(mon), int(day)).isoformat()
        except ValueError:
            return None
    return None


def parse_timestamp(value):
    """NSE local date/time -> ISO 8601 with NSE's ``+05:30`` offset.

    Accepts ``DD-MMM-YYYY HH:MM[:SS]`` (NSE's local times), ISO timestamps
    (the offset is preserved, ``+05:30`` assumed when absent) and date-only
    values (which come back as the ISO date string, exactly as stated, with no
    invented time of day).
    """
    if value is None:
        return None
    text = str(value).strip()
    match = _NSE_TS_RE.fullmatch(text)
    if match:
        day, mon, year, hh, mm, ss = match.groups()
        month = _MONTHS.get(mon.upper())
        if month is None:
            return None
        try:
            moment = dt.datetime(int(year), month, int(day), int(hh), int(mm), int(ss or 0))
        except ValueError:
            return None
        return moment.isoformat(timespec="seconds") + "+05:30"
    match = _ISO_TS_RE.fullmatch(text)
    if match:
        year, mon, day, hh, mm, ss, offset = match.groups()
        try:
            moment = dt.datetime(int(year), int(mon), int(day), int(hh), int(mm), int(ss or 0))
        except ValueError:
            return None
        return moment.isoformat(timespec="seconds") + (offset or "+05:30")
    date_only = parse_date(text)
    if date_only is not None:
        return date_only
    return None


def to_crore(value):
    """Convert ₹ lakh to ₹ crore (the results endpoint's unit; ÷100).

    ``None`` stays ``None``; the result is rounded to 2 dp (``ROUND_HALF_UP``)
    to match the ``numeric(14,2)`` column.
    """
    if value is None:
        return None
    return (Decimal(value) / Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )