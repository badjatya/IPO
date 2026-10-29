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


if __name__ == "__main__":
    unittest.main()