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


if __name__ == "__main__":
    unittest.main()