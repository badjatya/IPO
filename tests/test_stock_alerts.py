import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from support import NoNetworkCase  # noqa: E402

from stock_worker import alerts, pledges, results, shareholding  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "nse_stock"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _dec(value):
    if value is None:
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


def sh(quarter_end, promoter=None, filed_at=None, fii=None, dii=None):
    """A shareholding record in the 014 parsed shape (a plain dict)."""
    return {
        "quarter_end": quarter_end,
        "filed_at": filed_at,
        "promoter_pct": _dec(promoter),
        "fii_pct": _dec(fii),
        "dii_pct": _dec(dii),
    }


def pl(quarter_end, pledged=None, disclosed_at=None):
    """A pledge record in the 014 parsed shape (a plain dict)."""
    return {
        "quarter_end": quarter_end,
        "disclosed_at": disclosed_at,
        "promoter_pledged_pct": _dec(pledged),
    }


def rs(period_end, revenue=None, pat=None, filed_at=None):
    """A quarterly-results record in the 014 parsed shape (a plain dict)."""
    return {
        "period_end": period_end,
        "filed_at": filed_at,
        "revenue_cr": _dec(revenue),
        "pat_cr": _dec(pat),
    }


def ann(exchange_ref, importance=None, title="Board meeting outcome"):
    """An announcements record in the 014 parsed shape (a plain dict)."""
    return {"exchange_ref": exchange_ref, "importance": importance, "title": title}


def compute(fetched=None, stored=None, existing_keys=(), symbol="RELIANCE"):
    return alerts.compute_alerts(symbol, fetched or {}, stored or {}, existing_keys)


class ContractTests(NoNetworkCase):
    """Step 1: the core module — the record contract, the dedupe-key builder,
    the settled D10 severities and thresholds, and the formatting helpers."""

    def test_dedupe_key_matches_the_db_md_example(self):
        self.assertEqual(
            alerts.dedupe_key("HDFCBANK", "pledge_up", "2026-09-30"),
            "HDFCBANK:pledge_up:2026-09-30",
        )
        self.assertEqual(
            alerts.dedupe_key("reliance", "results", "2026-09-30"),
            "RELIANCE:results:2026-09-30",
        )

    def test_format_pct_strips_trailing_zeros_and_renders_missing(self):
        self.assertEqual(alerts.format_pct(Decimal("4")), "4")
        self.assertEqual(alerts.format_pct(Decimal("2.23")), "2.23")
        self.assertEqual(alerts.format_pct(Decimal("52.10")), "52.1")
        self.assertEqual(alerts.format_pct(Decimal("4.00")), "4")
        self.assertEqual(alerts.format_pct(None), "not available")

    def test_format_cr_renders_in_crore_with_commas_and_up_to_two_dp(self):
        self.assertEqual(alerts.format_cr(Decimal("128260.00")), "₹128,260")
        self.assertEqual(alerts.format_cr(Decimal("8721.00")), "₹8,721")
        self.assertEqual(alerts.format_cr(Decimal("12826.00")), "₹12,826")
        self.assertEqual(alerts.format_cr(Decimal("12.50")), "₹12.5")
        self.assertEqual(alerts.format_cr(Decimal("1234567.89")), "₹1,234,567.89")
        self.assertEqual(alerts.format_cr(None), "not available")

    def test_severities_cover_exactly_the_six_alert_kinds_with_settled_values(self):
        self.assertEqual(
            alerts.SEVERITIES,
            {
                "results": "info",
                "announcement": "watch",
                "fii_move": "watch",
                "dii_move": "watch",
                "pledge_up": "warning",
                "promoter_down": "warning",
            },
        )
        self.assertEqual(set(alerts.ALERT_KINDS), set(alerts.SEVERITIES))

    def test_default_thresholds_match_the_settled_d10_values(self):
        self.assertEqual(
            alerts.DEFAULT_THRESHOLDS,
            {
                "pledge_up": Decimal("1.00"),
                "promoter_down": Decimal("2.00"),
                "fii_move": Decimal("1.00"),
                "dii_move": Decimal("1.00"),
            },
        )


class ChangeRuleTests(NoNetworkCase):
    """Step 2: the four shareholder change rules — direct calls over records
    in the 014 parsed shapes."""

    THRESHOLDS = alerts.DEFAULT_THRESHOLDS

    def test_pledge_up_fires_with_the_exact_db_md_style_title(self):
        alert = alerts.pledge_up_alert(
            "RELIANCE", pl("2026-06-30", 4), pl("2026-09-30", 11),
            self.THRESHOLDS["pledge_up"],
        )
        self.assertEqual(alert["kind"], "pledge_up")
        self.assertEqual(alert["severity"], "warning")
        self.assertEqual(alert["title"], "Promoter pledge up from 4% to 11%")
        self.assertEqual(alert["dedupe_key"], "RELIANCE:pledge_up:2026-09-30")
        self.assertEqual(alert["source_table"], "shareholding")
        self.assertEqual(alert["source_id"], "2026-09-30")
        self.assertIsNone(alert["detail"])

    def test_promoter_down_fires_with_the_exact_title(self):
        alert = alerts.promoter_down_alert(
            "RELIANCE", sh("2026-06-30", 52.1), sh("2026-09-30", 48.9),
            self.THRESHOLDS["promoter_down"],
        )
        self.assertEqual(alert["title"], "Promoter holding down from 52.1% to 48.9%")
        self.assertEqual(alert["severity"], "warning")
        self.assertEqual(alert["kind"], "promoter_down")

    def test_fii_move_is_direction_aware(self):
        up = alerts.fii_move_alert(
            "RELIANCE", sh("2026-06-30", fii=14.2), sh("2026-09-30", fii=16.1),
            self.THRESHOLDS["fii_move"],
        )
        self.assertEqual(up["title"], "FII holding up from 14.2% to 16.1%")
        self.assertEqual(up["severity"], "watch")
        down = alerts.fii_move_alert(
            "RELIANCE", sh("2026-06-30", fii=16.1), sh("2026-09-30", fii=14.2),
            self.THRESHOLDS["fii_move"],
        )
        self.assertEqual(down["title"], "FII holding down from 16.1% to 14.2%")

    def test_dii_move_is_direction_aware(self):
        up = alerts.dii_move_alert(
            "RELIANCE", sh("2026-06-30", dii=30.0), sh("2026-09-30", dii=32.0),
            self.THRESHOLDS["dii_move"],
        )
        self.assertEqual(up["title"], "DII holding up from 30% to 32%")
        self.assertEqual(up["severity"], "watch")
        down = alerts.dii_move_alert(
            "RELIANCE", sh("2026-06-30", dii=32.0), sh("2026-09-30", dii=30.0),
            self.THRESHOLDS["dii_move"],
        )
        self.assertEqual(down["title"], "DII holding down from 32% to 30%")

    def test_below_threshold_is_silent_for_every_rule(self):
        self.assertIsNone(
            alerts.pledge_up_alert("R", pl("2026-06-30", 4), pl("2026-09-30", Decimal("4.99")),
                                   self.THRESHOLDS["pledge_up"])
        )
        self.assertIsNone(
            alerts.promoter_down_alert("R", sh("2026-06-30", 52), sh("2026-09-30", Decimal("50.01")),
                                       self.THRESHOLDS["promoter_down"])
        )
        self.assertIsNone(
            alerts.fii_move_alert("R", sh("2026-06-30", fii=14.2), sh("2026-09-30", fii=14.5),
                                  self.THRESHOLDS["fii_move"])
        )
        self.assertIsNone(
            alerts.dii_move_alert("R", sh("2026-06-30", dii=30.0), sh("2026-09-30", dii=29.5),
                                  self.THRESHOLDS["dii_move"])
        )

    def test_a_move_exactly_at_the_threshold_fires(self):
        self.assertIsNotNone(
            alerts.pledge_up_alert("R", pl("2026-06-30", 4), pl("2026-09-30", 5),
                                   self.THRESHOLDS["pledge_up"])
        )
        self.assertIsNotNone(
            alerts.promoter_down_alert("R", sh("2026-06-30", 52), sh("2026-09-30", 50),
                                       self.THRESHOLDS["promoter_down"])
        )
        self.assertIsNotNone(
            alerts.fii_move_alert("R", sh("2026-06-30", fii=14.2), sh("2026-09-30", fii=15.2),
                                  self.THRESHOLDS["fii_move"])
        )
        self.assertIsNotNone(
            alerts.dii_move_alert("R", sh("2026-06-30", dii=30.0), sh("2026-09-30", dii=31.0),
                                  self.THRESHOLDS["dii_move"])
        )

    def test_missing_value_on_either_side_is_silent(self):
        # Missing on the previous record, or on the current one — including
        # the real-data steady state: fii_pct/dii_pct are always None on
        # 014's shareholding rows, so fii_move/dii_move stay silent (the
        # "missing data, no alert" test, forward-compatible until task 027).
        self.assertIsNone(
            alerts.pledge_up_alert("R", pl("2026-06-30"), pl("2026-09-30", 11),
                                   self.THRESHOLDS["pledge_up"])
        )
        self.assertIsNone(
            alerts.pledge_up_alert("R", pl("2026-06-30", 4), pl("2026-09-30"),
                                   self.THRESHOLDS["pledge_up"])
        )
        self.assertIsNone(
            alerts.fii_move_alert("R", sh("2026-06-30"), sh("2026-09-30"),
                                  self.THRESHOLDS["fii_move"])
        )
        self.assertIsNone(
            alerts.dii_move_alert("R", sh("2026-06-30"), sh("2026-09-30"),
                                  self.THRESHOLDS["dii_move"])
        )
        self.assertIsNone(
            alerts.promoter_down_alert("R", sh("2026-06-30"), sh("2026-09-30", 48.9),
                                       self.THRESHOLDS["promoter_down"])
        )
        # A missing record on either side is equally silent.
        self.assertIsNone(
            alerts.promoter_down_alert("R", None, sh("2026-09-30", 48.9),
                                       self.THRESHOLDS["promoter_down"])
        )


class ResultsRuleTests(NoNetworkCase):
    """Step 3: the ``results`` existence rule."""

    def test_later_quarter_of_a_two_quarter_input_fires_with_the_exact_title(self):
        earlier = rs("2026-06-30", 12000.00, 900.00)
        later = rs("2026-09-30", 12826.00, 872.00)
        self.assertIsNone(alerts.results_alert("RELIANCE", earlier, has_earlier=False))
        alert = alerts.results_alert("RELIANCE", later, has_earlier=True)
        self.assertEqual(alert["kind"], "results")
        self.assertEqual(alert["severity"], "info")
        self.assertEqual(
            alert["title"],
            "Quarterly results for 2026-09-30: revenue ₹12,826 cr, PAT ₹872 cr",
        )
        self.assertEqual(alert["dedupe_key"], "RELIANCE:results:2026-09-30")
        self.assertEqual(alert["source_table"], "quarterly_results")
        self.assertEqual(alert["source_id"], "2026-09-30")
        self.assertIsNone(alert["detail"])

    def test_one_quarter_input_fires_nothing(self):
        self.assertIsNone(
            alerts.results_alert("RELIANCE", rs("2026-09-30", 12826.00, 872.00),
                                 has_earlier=False)
        )

    def test_missing_revenue_or_pat_renders_not_available(self):
        alert = alerts.results_alert("RELIANCE", rs("2026-06-30", None, 872.00),
                                     has_earlier=True)
        self.assertEqual(
            alert["title"],
            "Quarterly results for 2026-06-30: revenue not available, PAT ₹872 cr",
        )
        both = alerts.results_alert("RELIANCE", rs("2026-06-30"), has_earlier=True)
        self.assertEqual(
            both["title"],
            "Quarterly results for 2026-06-30: revenue not available, PAT not available",
        )

    def test_missing_period_end_is_silent(self):
        self.assertIsNone(
            alerts.results_alert("RELIANCE", rs(None, 12826.00, 872.00),
                                 has_earlier=True)
        )


class AnnouncementRuleTests(NoNetworkCase):
    """Step 3: the ``announcement`` rule — a pure function called by 020's
    rating step (round-2 review, item 6), never by ``compute_alerts``."""

    def test_fires_only_for_high_or_medium_importance(self):
        title = "Board meeting outcome"
        self.assertIsNone(alerts.announcement_alert("RELIANCE", ann("106833561", None, title)))
        for importance in ("low", "routine"):
            self.assertIsNone(
                alerts.announcement_alert("RELIANCE", ann("106833561", importance, title))
            )
        for importance in ("high", "medium"):
            alert = alerts.announcement_alert("RELIANCE", ann("106833561", importance, title))
            self.assertIsNotNone(alert)
            self.assertEqual(alert["dedupe_key"], "RELIANCE:announcement:106833561")
            self.assertEqual(alert["severity"], "watch")

    def test_rated_later_flow_raises_exactly_one_alert(self):
        # The 018 fetch state (importance None) alerts nothing; once 020 rates
        # the same record high and calls the rule, exactly one alert appears,
        # with the pinned key (the unique dedupe index guards duplicates).
        record = ann("106833561", None, "Board meeting outcome")
        self.assertIsNone(alerts.announcement_alert("RELIANCE", record))
        record["importance"] = "high"
        alert = alerts.announcement_alert("RELIANCE", record)
        self.assertIsNotNone(alert)
        self.assertEqual(alert["kind"], "announcement")
        self.assertEqual(alert["title"], "Board meeting outcome")
        self.assertEqual(alert["dedupe_key"], "RELIANCE:announcement:106833561")
        self.assertEqual(alert["source_table"], "announcements")
        self.assertEqual(alert["source_id"], "106833561")
        self.assertIsNone(alert["detail"])

    def test_missing_exchange_ref_is_silent(self):
        self.assertIsNone(alerts.announcement_alert("RELIANCE", ann(None, "high")))
        self.assertIsNone(alerts.announcement_alert("RELIANCE", {}))

    def test_any_importance_outside_the_enum_is_silent_never_an_error(self):
        self.assertIsNone(
            alerts.announcement_alert("RELIANCE", ann("106833561", "CRITICAL"))
        )

    def test_source_table_and_source_id_form_for_each_of_the_six_kinds(self):
        # Review round 1, item 5: one line in db.md § alerts pins the
        # source_id form per source_table; this test pins the same forms for
        # all six kinds. source_id is the natural key (quarter_end,
        # period_end, exchange_ref), scoped by the alert's symbol — never the
        # announcements.id bigint.
        thresholds = alerts.DEFAULT_THRESHOLDS
        alerts_by_kind = {
            "pledge_up": alerts.pledge_up_alert(
                "RELIANCE", pl("2026-06-30", 4), pl("2026-09-30", 11),
                thresholds["pledge_up"]),
            "promoter_down": alerts.promoter_down_alert(
                "RELIANCE", sh("2026-06-30", 52.1), sh("2026-09-30", 48.9),
                thresholds["promoter_down"]),
            "fii_move": alerts.fii_move_alert(
                "RELIANCE", sh("2026-06-30", fii=14.2), sh("2026-09-30", fii=16.1),
                thresholds["fii_move"]),
            "dii_move": alerts.dii_move_alert(
                "RELIANCE", sh("2026-06-30", dii=30.0), sh("2026-09-30", dii=32.0),
                thresholds["dii_move"]),
            "results": alerts.results_alert(
                "RELIANCE", rs("2026-09-30", 12826.00, 872.00), has_earlier=True),
            "announcement": alerts.announcement_alert(
                "RELIANCE", ann("106833561", "high")),
        }
        expected = {
            "pledge_up": ("shareholding", "2026-09-30", "RELIANCE:pledge_up:2026-09-30"),
            "promoter_down": ("shareholding", "2026-09-30", "RELIANCE:promoter_down:2026-09-30"),
            "fii_move": ("shareholding", "2026-09-30", "RELIANCE:fii_move:2026-09-30"),
            "dii_move": ("shareholding", "2026-09-30", "RELIANCE:dii_move:2026-09-30"),
            "results": ("quarterly_results", "2026-09-30", "RELIANCE:results:2026-09-30"),
            "announcement": ("announcements", "106833561", "RELIANCE:announcement:106833561"),
        }
        for kind, alert in alerts_by_kind.items():
            table, source_id, key = expected[kind]
            self.assertEqual(alert["kind"], kind)
            self.assertEqual(alert["source_table"], table)
            self.assertEqual(alert["source_id"], source_id)
            self.assertEqual(alert["dedupe_key"], key)
            self.assertIsNone(alert["detail"])


class ComputeAlertsTests(NoNetworkCase):
    """Step 4: the orchestrator — newness against ``stored``, the quarter
    timeline with its ``quarter_end`` join, per-series dedupe, ``results``
    first-sight baseline, ``existing_keys`` and deterministic ordering."""

    def test_first_sight_whole_fetched_history_raises_no_alerts_at_all(self):
        # Nothing stored, everything fetched: the whole history becomes the
        # baseline, even for pairs that cross a threshold — the "backfill
        # burst" would otherwise alert every historical crossing back to 2022.
        fetched = {
            "results": [
                rs("2026-06-30", 12000.00, 900.00, filed_at="2026-07-20"),
                rs("2026-09-30", 12826.00, 872.00, filed_at="2026-10-25"),
            ],
            "shareholding": [
                sh("2026-06-30", 52.00, filed_at="2026-07-16"),
                sh("2026-09-30", 49.00, filed_at="2026-10-21"),
            ],
            "pledges": [
                pl("2026-06-30", 4.00, disclosed_at="2026-07-16"),
                pl("2026-09-30", 11.00, disclosed_at="2026-10-21"),
            ],
        }
        self.assertEqual(compute(fetched=fetched, stored={}), [])

    def test_fetched_new_quarter_against_a_stored_predecessor_crosses_the_threshold(self):
        # The threshold-crossing pair is a synthetic case, not the fixture
        # (the fixture's own 0.04 pp promoter fall is pinned in step 5b,
        # review round 2, item 7).
        fetched = {"shareholding": [sh("2026-09-30", 49.00, filed_at="2026-10-21")]}
        stored = {"shareholding": [sh("2026-06-30", 52.00, filed_at="2026-07-16")]}
        result = compute(fetched=fetched, stored=stored)
        self.assertEqual(len(result), 1)
        alert = result[0]
        self.assertEqual(alert["kind"], "promoter_down")
        self.assertEqual(alert["title"], "Promoter holding down from 52% to 49%")
        self.assertEqual(alert["dedupe_key"], "RELIANCE:promoter_down:2026-09-30")

    def test_everything_stored_and_nothing_fetched_alerts_nothing(self):
        stored = {
            "results": [rs("2026-06-30", 12000.00, 900.00, filed_at="2026-07-20")],
            "shareholding": [sh("2026-09-30", 49.00, filed_at="2026-10-21")],
            "pledges": [pl("2026-09-30", 11.00, disclosed_at="2026-10-21")],
        }
        self.assertEqual(compute(fetched={}, stored=stored), [])

    def test_revision_never_realerts_and_its_fetched_value_serves_as_prev(self):
        # 2026-06-30 is already stored; the fetched revision must not re-alert.
        # The new 2026-09-30 quarter compares against the *revised* value
        # (a fetched record supersedes a stored record on the timeline), so
        # the exact title pins which value was the comparison partner.
        fetched = {
            "shareholding": [
                sh("2026-06-30", 30.00, filed_at="2026-10-21"),  # revision: 52.00 -> 30.00
                sh("2026-09-30", 28.00, filed_at="2026-10-25"),
            ]
        }
        stored = {
            "shareholding": [
                sh("2026-03-31", 50.00, filed_at="2026-04-20"),
                sh("2026-06-30", 52.00, filed_at="2026-07-16"),
            ]
        }
        result = compute(fetched=fetched, stored=stored)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Promoter holding down from 30% to 28%")

    def test_two_records_for_the_same_quarter_keep_the_later_filed_at(self):
        # Both fetched records are for 2026-09-30; the one filed on 10-25
        # wins. If the 10-21 record (50.44%) won, the fall vs 52.00% would be
        # 1.56 pp and nothing would fire; the later record (50.00%) makes it
        # exactly 2.00 pp and the alert fires (review round 1, item 3).
        fetched = {
            "shareholding": [
                sh("2026-09-30", 50.44, filed_at="2026-10-21"),
                sh("2026-09-30", 50.00, filed_at="2026-10-25"),
            ]
        }
        stored = {"shareholding": [sh("2026-06-30", 52.00, filed_at="2026-07-16")]}
        result = compute(fetched=fetched, stored=stored)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Promoter holding down from 52% to 50%")

    def test_none_timestamps_keep_the_same_winner_in_either_input_order(self):
        # Both records state no filing time (a record that states none cannot
        # be proven newer); the canonical tie-break keeps the greater
        # serialisation no matter the input order. Either candidate crosses
        # the absolute FII threshold (±1.00 pp vs 14.2%), so an alert always
        # fires — and its exact title identifies which record won (15.2% >
        # 13.2% canonically, so the up-move wins).
        winner = sh("2026-09-30", fii=15.2, filed_at=None)
        loser = sh("2026-09-30", fii=13.2, filed_at=None)
        stored = {"shareholding": [sh("2026-06-30", fii=14.2, filed_at="2026-07-16")]}
        first = compute(fetched={"shareholding": [loser, winner]}, stored=stored)
        second = compute(fetched={"shareholding": [winner, loser]}, stored=stored)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["title"], "FII holding up from 14.2% to 15.2%")

    def test_equal_stated_timestamps_keep_the_same_winner_in_either_input_order(self):
        winner = sh("2026-09-30", fii=15.2, filed_at="2026-10-21T10:00:00+05:30")
        loser = sh("2026-09-30", fii=13.2, filed_at="2026-10-21T10:00:00+05:30")
        stored = {"shareholding": [sh("2026-06-30", fii=14.2, filed_at="2026-07-16")]}
        first = compute(fetched={"shareholding": [loser, winner]}, stored=stored)
        second = compute(fetched={"shareholding": [winner, loser]}, stored=stored)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["title"], "FII holding up from 14.2% to 15.2%")

    def test_quarter_with_shareholding_but_no_pledge_row_yields_no_pledge_up(self):
        fetched = {
            "shareholding": [sh("2026-09-30", 48.00, filed_at="2026-10-21")],
            "pledges": [],
        }
        stored = {
            "shareholding": [sh("2026-03-31", 50.00, filed_at="2026-04-20")],
            "pledges": [pl("2026-03-31", 5.00, disclosed_at="2026-04-20")],
        }
        result = compute(fetched=fetched, stored=stored)
        self.assertEqual([alert["kind"] for alert in result], ["promoter_down"])

    def test_quarter_with_pledge_but_no_shareholding_yields_no_shareholder_alerts(self):
        fetched = {
            "shareholding": [],
            "pledges": [pl("2026-09-30", 8.00, disclosed_at="2026-10-21")],
        }
        stored = {
            "shareholding": [sh("2026-03-31", 50.00, filed_at="2026-04-20")],
            "pledges": [pl("2026-03-31", 5.00, disclosed_at="2026-04-20")],
        }
        result = compute(fetched=fetched, stored=stored)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["kind"], "pledge_up")
        self.assertEqual(result[0]["title"], "Promoter pledge up from 5% to 8%")

    def test_gap_quarters_are_skipped_the_comparison_is_vs_the_previous_quarter_on_record(self):
        # No shareholding record exists for 2026-06-30; the new 2026-09-30
        # quarter still compares against the latest earlier quarter on record
        # (2026-03-31) and fires.
        fetched = {"shareholding": [sh("2026-09-30", 48.00, filed_at="2026-10-21")]}
        stored = {"shareholding": [sh("2026-03-31", 50.00, filed_at="2026-04-20")]}
        result = compute(fetched=fetched, stored=stored)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Promoter holding down from 50% to 48%")

    def test_from_the_second_run_on_each_new_results_filing_alerts_once_ever(self):
        # A catch-up run bringing two new quarters: both are new against
        # stored, both have an earlier quarter on record, so both alert —
        # each new filing alerts exactly once, ever (Approach § 3).
        fetched = {
            "results": [
                rs("2026-09-30", 12826.00, 872.00, filed_at="2026-10-25"),
                rs("2026-12-31", 13000.00, 900.00, filed_at="2027-01-20"),
            ]
        }
        stored = {"results": [rs("2026-06-30", 12000.00, 900.00, filed_at="2026-07-20")]}
        result = compute(fetched=fetched, stored=stored)
        self.assertEqual(
            [alert["dedupe_key"] for alert in result],
            ["RELIANCE:results:2026-09-30", "RELIANCE:results:2026-12-31"],
        )

    def test_has_earlier_counts_an_earlier_new_fetched_quarter(self):
        # Backfilling older missing quarters against a stored later one: the
        # first fetched quarter has no earlier quarter on record (the stored
        # one is later), so it is the baseline; the second fetched quarter
        # has an earlier *new fetched* quarter and fires (Approach § 3).
        fetched = {
            "results": [
                rs("2026-06-30", 12000.00, 900.00, filed_at="2026-10-25"),
                rs("2026-09-30", 12826.00, 872.00, filed_at="2026-10-26"),
            ]
        }
        stored = {"results": [rs("2026-12-31", 13000.00, 900.00, filed_at="2027-01-20")]}
        result = compute(fetched=fetched, stored=stored)
        self.assertEqual(
            [alert["dedupe_key"] for alert in result],
            ["RELIANCE:results:2026-09-30"],
        )

    def _sample_mixed_inputs(self):
        return {
            "fetched": {
                "results": [rs("2026-09-30", 12826.00, 872.00, filed_at="2026-10-25")],
                "shareholding": [sh("2026-09-30", 49.00, filed_at="2026-10-21")],
                "pledges": [pl("2026-09-30", 5.00, disclosed_at="2026-10-21")],
            },
            "stored": {
                "results": [rs("2026-06-30", 12000.00, 900.00, filed_at="2026-07-20")],
                "shareholding": [sh("2026-06-30", 52.00, filed_at="2026-07-16")],
                "pledges": [pl("2026-06-30", 2.00, disclosed_at="2026-07-16")],
            },
        }

    def test_same_input_twice_returns_identical_lists_with_unique_keys(self):
        inputs = self._sample_mixed_inputs()
        first = compute(**inputs)
        second = compute(**inputs)
        self.assertEqual(first, second)
        keys = [alert["dedupe_key"] for alert in first]
        self.assertEqual(len(keys), 3)
        self.assertEqual(len(keys), len(set(keys)))

    def test_existing_keys_suppress_everything_already_emitted(self):
        inputs = self._sample_mixed_inputs()
        first = compute(**inputs)
        keys = [alert["dedupe_key"] for alert in first]
        self.assertEqual([alert["kind"] for alert in first], [
            "pledge_up", "promoter_down", "results",
        ])
        again = compute(existing_keys=keys, **inputs)
        self.assertEqual(again, [])
        # a partially-supplied set drops only those keys
        partial = compute(existing_keys=keys[:1], **inputs)
        self.assertEqual([alert["dedupe_key"] for alert in partial], keys[1:])

    def test_output_order_is_deterministic_by_kind_then_period(self):
        # Two alerts, different kinds and periods: pledge_up (2026-06-30)
        # sorts before promoter_down (2026-09-30) by (kind, period).
        fetched = {
            "shareholding": [sh("2026-09-30", 49.00, filed_at="2026-10-21")],
            "pledges": [
                pl("2026-06-30", 6.00, disclosed_at="2026-07-16"),
                pl("2026-09-30", 5.00, disclosed_at="2026-10-21"),
            ],
        }
        stored = {
            "shareholding": [
                sh("2026-03-31", 50.00, filed_at="2026-04-20"),
                sh("2026-06-30", 52.00, filed_at="2026-07-16"),
            ],
            "pledges": [pl("2026-03-31", 2.00, disclosed_at="2026-04-20")],
        }
        result = compute(fetched=fetched, stored=stored)
        self.assertEqual([alert["kind"] for alert in result], [
            "pledge_up", "promoter_down",
        ])
        self.assertEqual([alert["source_id"] for alert in result], [
            "2026-06-30", "2026-09-30",
        ])


class FixtureIntegrationTests(NoNetworkCase):
    """Step 5: the 014 parsers run over the saved ``tests/fixtures/nse_stock/``
    fixtures end to end. No live sites, no AI APIs."""

    @classmethod
    def setUpClass(cls):
        cls.results_records = results.parse_results(
            load("results_standalone.json"), load("results_filings.json")
        )
        cls.shareholding_records = shareholding.parse(load("shareholding.json"))
        cls.pledge_records = pledges.parse(load("pledges.json"))

    def test_first_sight_on_the_real_fixture_raises_zero_alerts(self):
        # RELIANCE first sight: stored empty, the whole fetched history — no
        # results alert for any of the five quarters, no promoter_down
        # (the pair-wise crossings of the past are the baseline), no
        # pledge_up (no RELIANCE quarter has a pledge row), no FII/DII.
        fetched = {
            "results": self.results_records,
            "shareholding": self.shareholding_records,
            "pledges": [],
        }
        self.assertEqual(alerts.compute_alerts("RELIANCE", fetched, {}), [])

    def test_second_run_alerts_only_what_is_new_with_exact_counts(self):
        # Stored = the fixture records except the latest results quarter
        # (2024-12-31) and the latest shareholding quarter (2026-09-30);
        # fetched = those two latest records. Exactly ONE alert —
        # RELIANCE:results:2024-12-31 — and zero change alerts: the fetched
        # shareholding quarter 2026-09-30 (50.44%) vs the stored 2026-06-30
        # (50.48%) is a 0.04 pp fall, below the 2.00 pp promoter_down
        # threshold; fii_pct/dii_pct are None on every row; no RELIANCE
        # quarter has a pledge row, so there is no pledge_up candidate
        # (review round 2, item 7).
        stored = {
            "results": self.results_records[1:],
            "shareholding": self.shareholding_records[1:],
            "pledges": [],
        }
        fetched = {
            "results": self.results_records[:1],
            "shareholding": self.shareholding_records[:1],
            "pledges": [],
        }
        result = alerts.compute_alerts("RELIANCE", fetched, stored)
        self.assertEqual(len(result), 1)
        alert = result[0]
        self.assertEqual(alert["kind"], "results")
        self.assertEqual(alert["severity"], "info")
        self.assertEqual(alert["dedupe_key"], "RELIANCE:results:2024-12-31")
        self.assertEqual(alert["source_table"], "quarterly_results")
        self.assertEqual(alert["source_id"], "2024-12-31")
        self.assertEqual(
            alert["title"],
            "Quarterly results for 2024-12-31: revenue ₹128,260 cr, PAT ₹8,721 cr",
        )
        self.assertIsNone(alert["detail"])
        keys = [a["dedupe_key"] for a in result]
        self.assertEqual(len(keys), len(set(keys)))

    def test_adanient_pledge_fixture_as_its_own_single_symbol_case(self):
        # The fixture row carries no symbol — only comName, "Adani
        # Enterprises Limited" (015/018 resolve the name); the test passes it
        # for ADANIENT exactly as 018 would after 015's resolution, without
        # asserting on company. First sight: the single quarter becomes the
        # baseline, no alert (no earlier pledge quarter on record), and a
        # second call with the first call's keys emits nothing.
        self.assertEqual(len(self.pledge_records), 1)
        self.assertEqual(self.pledge_records[0]["quarter_end"], "2026-09-30")
        fetched = {"results": [], "shareholding": [], "pledges": self.pledge_records}
        first = alerts.compute_alerts("ADANIENT", fetched, {})
        self.assertEqual(first, [])
        keys = [alert["dedupe_key"] for alert in first]
        self.assertEqual(
            alerts.compute_alerts("ADANIENT", fetched, {}, existing_keys=keys), []
        )


if __name__ == "__main__":
    unittest.main()