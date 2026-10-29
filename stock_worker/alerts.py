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