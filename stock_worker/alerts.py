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


def _value_cr(value):
    """A crore amount for a results title: ``₹<grouped> cr`` when stated,
    "not available" when missing — the unit has nothing to hang on to."""
    number = format_cr(value)
    if number == NOT_AVAILABLE:
        return NOT_AVAILABLE
    return f"{number} cr"


def results_alert(symbol, record, has_earlier):
    """A new standalone results filing for a quarter that has an earlier
    quarter on record — the quarter that starts a symbol's record is the
    baseline, not an event. Only stated fields go into the title; revenue and
    PAT are the crore amounts the filing states, or "not available". Silent
    when ``period_end`` is missing (the record cannot be keyed).
    """
    period_end = (record or {}).get("period_end")
    if period_end is None or not has_earlier:
        return None
    return {
        "kind": "results",
        "severity": SEVERITIES["results"],
        "title": (
            f"Quarterly results for {period_end}: "
            f"revenue {_value_cr(record.get('revenue_cr'))}, "
            f"PAT {_value_cr(record.get('pat_cr'))}"
        ),
        "detail": None,
        "dedupe_key": dedupe_key(symbol, "results", period_end),
        "source_table": "quarterly_results",
        "source_id": period_end,
    }


def announcement_alert(symbol, record):
    """The announcement rule — for 020's rating step (arch.md Mode 1 step 4).

    Not part of ``compute_alerts``: the candidates are computed at step 3,
    before Gemini writes ``importance`` at step 4, so the orchestrator can
    never see a rated announcement. 020 calls this once per announcement it
    has just rated, after writing ``importance``. Only ``high``/``medium``
    fire (any other value — including `None`, the 018 fetch state — is not
    important and alerts nothing, never an error); a record without an
    ``exchange_ref`` cannot be keyed and alerts nothing. The title is the
    announcement's own title as NSE stated it (data, quoted as-is).
    """
    record = record or {}
    if record.get("importance") not in ("high", "medium"):
        return None
    exchange_ref = record.get("exchange_ref")
    if not exchange_ref:
        return None
    return {
        "kind": "announcement",
        "severity": SEVERITIES["announcement"],
        "title": record.get("title") or NOT_AVAILABLE,
        "detail": None,
        "dedupe_key": dedupe_key(symbol, "announcement", exchange_ref),
        "source_table": "announcements",
        "source_id": exchange_ref,
    }


def _canonical(record):
    """Key-sorted serialisation, ``Decimal`` via ``str()`` — the documented
    tie-break for equal or missing timestamps, so the winner never depends on
    input order."""
    return json.dumps(record, sort_keys=True, default=str)


def _newer(candidate, current, stamp_field):
    """Is ``candidate`` strictly newer than ``current`` under the per-series
    stamp rule? A ``None`` stamp sorts older than any stated timestamp; when
    both are ``None`` or equal, the greater canonical serialisation wins."""
    candidate_stamp = candidate.get(stamp_field)
    current_stamp = current.get(stamp_field)
    if candidate_stamp is not None or current_stamp is not None:
        if candidate_stamp is None:
            return False
        if current_stamp is None:
            return True
        if candidate_stamp != current_stamp:
            return candidate_stamp > current_stamp
    return _canonical(candidate) > _canonical(current)


def _dedupe_latest(records, key_field, stamp_field):
    """One record per natural key, keeping the latest by ``stamp_field``.

    ``stamp_field`` is ``filed_at`` for results and shareholding,
    ``disclosed_at`` for pledges. A record without a natural key cannot be
    joined or keyed and is dropped.
    """
    latest = {}
    for record in records or []:
        key = record.get(key_field)
        if key is None:
            continue
        current = latest.get(key)
        if current is None or _newer(record, current, stamp_field):
            latest[key] = record
    return latest


def compute_alerts(symbol, fetched, stored, existing_keys=(), thresholds=DEFAULT_THRESHOLDS):
    """All four change rules plus ``results`` for one symbol, from the records
    018 is about to persist (``fetched``) and the records already on hand
    (``stored``) for the three series that compare or flag by themselves:
    ``results``, ``shareholding`` and ``pledges``. Announcements are not part
    of it — their rule fires from 020's rating step (round-2 review, item 6).

    Each series is deduped by natural key keeping the latest (``filed_at``
    for results and shareholding, ``disclosed_at`` for pledges; a ``None``
    timestamp sorts older than any stated one; equal or ``None`` timestamps
    are broken by a canonical serialisation, so the winner never depends on
    input order). The quarter timeline is the union of the stored and fetched
    shareholding and pledge records (a fetched record supersedes a stored
    record with the same ``quarter_end``), sorted ascending, with pledge
    records joined to shareholding quarters on ``quarter_end``.

    An alert fires only for a record that is new against ``stored`` — its
    natural key is not in the stored set — and only when the stored set for
    that series is non-empty: on first sight (nothing stored for the series)
    the whole fetched history is the baseline and raises no alerts at all,
    change rules and ``results`` alike. A change rule compares the new
    quarter with the latest earlier quarter on record, which may come from
    ``stored``; an omitted quarter simply means the next one on record is the
    comparison partner. A revised filing whose key is already stored never
    re-alerts, and its value still serves as the comparison partner for later
    new quarters. ``results`` fires for a new filing that has an earlier
    quarter on record (from ``stored`` or an earlier new fetched quarter).

    Alerts whose ``dedupe_key`` is already in ``existing_keys`` are dropped —
    018 passes the symbol's stored alert keys as a second guard behind the
    unique index on ``alerts.dedupe_key`` (built by 007) — and the result is
    a deterministic list ordered by ``(kind, period)``. ``thresholds`` maps
    the four change-rule kinds to their percentage-point moves.
    """
    fetched = fetched or {}
    stored = stored or {}
    existing = set(existing_keys or ())
    alerts_list = []

    stored_sh = _dedupe_latest(stored.get("shareholding") or [], "quarter_end", "filed_at")
    fetched_sh = _dedupe_latest(fetched.get("shareholding") or [], "quarter_end", "filed_at")
    stored_pl = _dedupe_latest(stored.get("pledges") or [], "quarter_end", "disclosed_at")
    fetched_pl = _dedupe_latest(fetched.get("pledges") or [], "quarter_end", "disclosed_at")

    sh_by_quarter = dict(stored_sh)
    sh_by_quarter.update(fetched_sh)  # a fetched record supersedes a stored one
    pl_by_quarter = dict(stored_pl)
    pl_by_quarter.update(fetched_pl)
    quarter_order = sorted(set(sh_by_quarter) | set(pl_by_quarter))

    if stored_sh:
        prev_sh = None
        for quarter in quarter_order:
            shareholding_record = sh_by_quarter.get(quarter)
            if shareholding_record is None:
                # A quarter with a pledge but no shareholding row is not a
                # promoter_down/FII/DII candidate; ``prev_sh`` stays put.
                continue
            if quarter in fetched_sh and quarter not in stored_sh:
                for kind, rule in (
                    ("promoter_down", promoter_down_alert),
                    ("fii_move", fii_move_alert),
                    ("dii_move", dii_move_alert),
                ):
                    alert = rule(symbol, prev_sh, shareholding_record, thresholds[kind])
                    if alert is not None:
                        alerts_list.append(alert)
            prev_sh = shareholding_record

    if stored_pl:
        prev_pl = None
        for quarter in quarter_order:
            pledge_record = pl_by_quarter.get(quarter)
            if pledge_record is None:
                # A quarter with shareholding but no pledge row is not a
                # pledge_up candidate; ``prev_pl`` stays put.
                continue
            if quarter in fetched_pl and quarter not in stored_pl:
                alert = pledge_up_alert(
                    symbol, prev_pl, pledge_record, thresholds["pledge_up"]
                )
                if alert is not None:
                    alerts_list.append(alert)
            prev_pl = pledge_record

    stored_results = _dedupe_latest(stored.get("results") or [], "period_end", "filed_at")
    fetched_results = _dedupe_latest(fetched.get("results") or [], "period_end", "filed_at")
    if stored_results:
        results_by_period = dict(stored_results)
        results_by_period.update(fetched_results)  # a fetched record supersedes a stored one
        for index, period in enumerate(sorted(results_by_period)):
            record = results_by_period[period]
            if period in fetched_results and period not in stored_results:
                alert = results_alert(symbol, record, has_earlier=index > 0)
                if alert is not None:
                    alerts_list.append(alert)

    kept = [alert for alert in alerts_list if alert["dedupe_key"] not in existing]
    kept.sort(key=lambda alert: (alert["kind"], alert["source_id"]))
    return kept