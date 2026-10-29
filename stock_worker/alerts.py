"""Change detection and alert rules for listed stocks (task 016).

The six rules of db.md's ``alert_kind`` enum as pure, deterministic functions
over the record shapes the 014 fetchers already produce (plain dicts keyed by
the ``db.md`` column names, ``Decimal``/``None`` values). Nothing here reads a
database, a file, a setting or the network, and nothing is wired into any
workflow yet — exactly like 014's fetchers when they shipped. 018 imports
``compute_alerts`` for arch.md Mode 1 step 3; 020's rating step (Mode 1 step
4) calls :func:`announcement_alert` once per announcement it has just rated,
after Gemini writes ``importance`` — the announcement rule is *not* part of
the orchestrator, because the candidates are computed before ``importance``
exists (round-2 review, item 6).

Alert record contract — keys are the ``alerts`` columns:

``kind``          one of the six ``alert_kind`` values
``severity``      from :data:`SEVERITIES` (the settled D10 values)
``title``         built by Python from stated fields; a missing value renders
                  as "not available", never an estimate (AGENTS.md rule 1)
``detail``        always ``None`` — Gemini writes ``alerts.detail`` in 020
``dedupe_key``    ``<SYMBOL>:<kind>:<period>`` — the triggering quarter's
                  ``period_end``/``quarter_end``, or ``<exchange_ref>`` for
                  announcements (db.md's unique ``dedupe_key``)
``source_table`` / ``source_id``: ``shareholding``/quarter_end for the four
                  shareholder rules, ``quarterly_results``/period_end for
                  ``results``, ``announcements``/exchange_ref for
                  ``announcement`` — natural keys scoped by the alert's
                  symbol; never the ``announcements.id`` bigint, which this
                  pure module never sees

Thresholds and severities are the values the human settled for D10 at 016's
round-1 plan review (ADR-0027, status Proposed): analytic parameters, held in
code as :data:`DEFAULT_THRESHOLDS` and :data:`SEVERITIES` and still passable
to :func:`compute_alerts` via ``thresholds=``; there are no ``settings`` rows
for them (AGENTS.md rule 6 concerns user-facing quotas and caps).
"""

import json
from decimal import Decimal

NOT_AVAILABLE = "not available"

ALERT_KINDS = (
    "pledge_up",
    "promoter_down",
    "fii_move",
    "dii_move",
    "results",
    "announcement",
)

# Settled D10 severities (docs/adr/0027-alert-thresholds-and-severities.md).
SEVERITIES = {
    "results": "info",
    "announcement": "watch",
    "fii_move": "watch",
    "dii_move": "watch",
    "pledge_up": "warning",
    "promoter_down": "warning",
}

# Settled D10 thresholds, in percentage points, quarter-on-quarter. A move of
# exactly the threshold fires ("at least" semantics); less does not.
DEFAULT_THRESHOLDS = {
    "pledge_up": Decimal("1.00"),
    "promoter_down": Decimal("2.00"),
    "fii_move": Decimal("1.00"),
    "dii_move": Decimal("1.00"),
}


def dedupe_key(symbol, kind, period):
    """``<SYMBOL>:<kind>:<period>`` — db.md's ``alerts.dedupe_key`` form."""
    return f"{str(symbol).upper()}:{kind}:{period}"


def _strip_trailing_zeros(text):
    if "." in text:
        return text.rstrip("0").rstrip(".")
    return text


def format_pct(value):
    """Percent with trailing zeros stripped; ``None`` -> "not available"."""
    if value is None:
        return NOT_AVAILABLE
    return _strip_trailing_zeros(format(value, "f"))


def format_cr(value):
    """₹ crore with commas and up to 2 dp; ``None`` -> "not available"."""
    if value is None:
        return NOT_AVAILABLE
    text = _strip_trailing_zeros(format(value, "f"))
    integer, _, fraction = text.partition(".")
    if fraction:
        return f"₹{_group_thousands(integer)}.{fraction}"
    return f"₹{_group_thousands(integer)}"


def _group_thousands(integer):
    """Three-digit grouping from the right: ``"128260"`` -> ``"128,260"``."""
    parts = []
    while len(integer) > 3:
        parts.append(integer[-3:])
        integer = integer[:-3]
    parts.append(integer)
    return ",".join(reversed(parts))


def _change_alert(symbol, kind, prev, curr, field, threshold_pp, mode, label):
    """The comparison behind the four shareholder change rules.

    Each takes ``(symbol, prev, curr, threshold_pp)`` and compares the new
    quarter (``curr``) with the latest quarter on record before it (``prev``;
    the orchestrator supplies both after its ``quarter_end`` join).
    ``mode`` is ``"up"`` (a rise of at least ``threshold_pp`` fires, the
    pledge rule), ``"down"`` (a fall of at least ``threshold_pp`` fires, the
    promoter rule) or ``"absolute"`` (an absolute move of at least
    ``threshold_pp`` fires, FII/DII). Comparison is ``Decimal``, never float;
    a move exactly equal to the threshold fires ("at least" semantics). A
    ``None`` value on either side — including a missing record — yields no
    alert: missing is missing, never an estimate. The alert is keyed on the
    current quarter's ``quarter_end``; a quarter that cannot be keyed alerts
    nothing.
    """
    prev_value = (prev or {}).get(field)
    curr_value = (curr or {}).get(field)
    quarter_end = (curr or {}).get("quarter_end")
    if prev_value is None or curr_value is None or quarter_end is None:
        return None
    delta = curr_value - prev_value
    if mode == "up":
        if delta < threshold_pp:
            return None
        direction = "up"
    elif mode == "down":
        if delta > -threshold_pp:
            return None
        direction = "down"
    else:
        if abs(delta) < threshold_pp:
            return None
        direction = "up" if delta > 0 else "down"
    return {
        "kind": kind,
        "severity": SEVERITIES[kind],
        "title": (
            f"{label} {direction} from {format_pct(prev_value)}% "
            f"to {format_pct(curr_value)}%"
        ),
        "detail": None,
        "dedupe_key": dedupe_key(symbol, kind, quarter_end),
        "source_table": "shareholding",
        "source_id": quarter_end,
    }


def pledge_up_alert(symbol, prev, curr, threshold_pp):
    """New quarter's ``promoter_pledged_pct`` up by at least ``threshold_pp``
    percentage points vs the previous pledge on record."""
    return _change_alert(
        symbol, "pledge_up", prev, curr, "promoter_pledged_pct",
        threshold_pp, "up", "Promoter pledge",
    )


def promoter_down_alert(symbol, prev, curr, threshold_pp):
    """New quarter's ``promoter_pct`` down by at least ``threshold_pp``
    percentage points vs the previous shareholding on record."""
    return _change_alert(
        symbol, "promoter_down", prev, curr, "promoter_pct",
        threshold_pp, "down", "Promoter holding",
    )


def fii_move_alert(symbol, prev, curr, threshold_pp):
    """``fii_pct`` moved by at least ``threshold_pp`` percentage points,
    either direction, vs the previous shareholding on record."""
    return _change_alert(
        symbol, "fii_move", prev, curr, "fii_pct",
        threshold_pp, "absolute", "FII holding",
    )


def dii_move_alert(symbol, prev, curr, threshold_pp):
    """``dii_pct`` moved by at least ``threshold_pp`` percentage points,
    either direction, vs the previous shareholding on record."""
    return _change_alert(
        symbol, "dii_move", prev, curr, "dii_pct",
        threshold_pp, "absolute", "DII holding",
    )