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
        decimal = Decimal(text)
    except ArithmeticError:
        return None
    if not decimal.is_finite():
        # "NaN" and "Infinity" are junk, not values that belong in numeric
        # columns or pledge arithmetic.
        return None
    return decimal


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


IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def to_aware_datetime(value):
    """ISO timestamp or date, or a ``datetime`` -> aware ``datetime``; junk -> ``None``.

    A ``datetime`` object is accepted directly: an aware one is returned as-is,
    a naive one is read as NSE's ``+05:30``. Strings are parsed with
    ``datetime.fromisoformat``, which (Python 3.11+) also reads the ``Z``
    suffix and fractional seconds — how a Postgres ``timestamptz`` often
    prints. A naive timestamp is read as NSE's ``+05:30`` (the same assumption
    ``parse_timestamp`` makes) and a date-only value as midnight ``+05:30`` —
    the earliest moment that date could carry, needed so a date can be
    compared against a moment. Impossible dates and junk -> ``None``.
    """
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=IST)
        return value
    try:
        moment = dt.datetime.fromisoformat(str(value).strip())
    except ValueError:
        return None
    if moment.tzinfo is None:
        return moment.replace(tzinfo=IST)
    return moment


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