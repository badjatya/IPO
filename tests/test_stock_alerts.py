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


if __name__ == "__main__":
    unittest.main()