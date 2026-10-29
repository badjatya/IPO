import datetime as dt
import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from support import NoNetworkCase  # noqa: E402

from stock_worker import util  # noqa: E402


class DecimalTests(NoNetworkCase):
    def test_leading_spaces(self):
        self.assertEqual(util.to_decimal(" 71.97"), Decimal("71.97"))

    def test_indian_grouping_commas(self):
        self.assertEqual(util.to_decimal("1,28,26,000"), Decimal("12826000"))

    def test_plain_integer_string(self):
        self.assertEqual(util.to_decimal("21723685"), Decimal("21723685"))

    def test_stated_zero_is_a_value(self):
        self.assertEqual(util.to_decimal("0"), Decimal("0"))

    def test_junk_is_none(self):
        self.assertIsNone(util.to_decimal("n/a"))
        self.assertIsNone(util.to_decimal(""))
        self.assertIsNone(util.to_decimal(None))
        self.assertIsNone(util.to_decimal("12abc"))

    def test_non_finite_is_none(self):
        # NaN and Infinity must not flow into numeric columns or arithmetic.
        self.assertIsNone(util.to_decimal("NaN"))
        self.assertIsNone(util.to_decimal("Infinity"))
        self.assertIsNone(util.to_decimal("-Infinity"))


class DateTests(NoNetworkCase):
    def test_uppercase_month(self):
        self.assertEqual(util.parse_date("31-DEC-2024"), "2024-12-31")

    def test_mixed_case_and_two_digit_day(self):
        self.assertEqual(util.parse_date("30-Sep-2026"), "2026-09-30")
        self.assertEqual(util.parse_date("21-OCT-2026"), "2026-10-21")

    def test_iso_passthrough(self):
        self.assertEqual(util.parse_date("2026-09-30"), "2026-09-30")

    def test_junk_is_none(self):
        self.assertIsNone(util.parse_date("not-a-date"))
        self.assertIsNone(util.parse_date("31-XXX-2024"))
        self.assertIsNone(util.parse_date("31-13-2024"))
        self.assertIsNone(util.parse_date(None))


class TimestampTests(NoNetworkCase):
    def test_with_seconds(self):
        self.assertEqual(
            util.parse_timestamp("29-Oct-2026 08:55:40"),
            "2026-10-29T08:55:40+05:30",
        )

    def test_without_seconds(self):
        self.assertEqual(
            util.parse_timestamp("16-Jan-2025 20:20"),
            "2025-01-16T20:20:00+05:30",
        )

    def test_date_only_returns_the_stated_date(self):
        # NSE's shareholding submissionDate carries no time; no time is invented.
        self.assertEqual(util.parse_timestamp("21-OCT-2026"), "2026-10-21")

    def test_iso_passthrough_preserves_offset(self):
        self.assertEqual(
            util.parse_timestamp("2026-10-29T08:55:40+05:30"),
            "2026-10-29T08:55:40+05:30",
        )

    def test_junk_is_none(self):
        self.assertIsNone(util.parse_timestamp("nope"))
        self.assertIsNone(util.parse_timestamp(None))


class AwareDatetimeTests(NoNetworkCase):
    def test_keeps_the_offset(self):
        moment = util.to_aware_datetime("2026-10-29T05:00:00+00:00")
        self.assertEqual(moment.utcoffset(), dt.timedelta(0))
        self.assertEqual(moment.isoformat(), "2026-10-29T05:00:00+00:00")

    def test_naive_is_read_as_ist(self):
        moment = util.to_aware_datetime("2026-10-29T10:30:00")
        self.assertEqual(moment.utcoffset(), dt.timedelta(hours=5, minutes=30))
        self.assertEqual(moment.isoformat(), "2026-10-29T10:30:00+05:30")

    def test_date_only_is_midnight_ist(self):
        moment = util.to_aware_datetime("2026-10-29")
        self.assertEqual(moment.isoformat(), "2026-10-29T00:00:00+05:30")

    def test_orders_across_offsets(self):
        utc = util.to_aware_datetime("2026-10-29T03:25:40+00:00")
        ist = util.to_aware_datetime("2026-10-29T08:55:40+05:30")
        self.assertEqual(utc, ist)  # the same instant, different offsets

    def test_junk_is_none(self):
        self.assertIsNone(util.to_aware_datetime(None))
        self.assertIsNone(util.to_aware_datetime("not-a-timestamp"))
        self.assertIsNone(util.to_aware_datetime("13-13-2026"))


class ToCroreTests(NoNetworkCase):
    def test_lakh_to_crore(self):
        self.assertEqual(util.to_crore(Decimal("12826000")), Decimal("128260.00"))

    def test_rounds_to_two_dp(self):
        self.assertEqual(util.to_crore(Decimal("1521300")), Decimal("15213.00"))
        self.assertEqual(util.to_crore(Decimal("321400")), Decimal("3214.00"))

    def test_none_stays_none(self):
        self.assertIsNone(util.to_crore(None))


class GetPathTests(NoNetworkCase):
    def test_nested_paths(self):
        body = {
            "priceInfo": {"weekHighLow": {"weekHigh": 1300}},
            "data": [{"symbol": "RELIANCE"}],
        }
        self.assertEqual(util.get_path(body, "priceInfo.weekHighLow.weekHigh"), 1300)
        self.assertEqual(util.get_path(body, "data[].symbol"), "RELIANCE")

    def test_missing_is_none(self):
        self.assertIsNone(util.get_path({"a": 1}, "a.b.c"))
        self.assertIsNone(util.get_path({"a": []}, "a[]"))
        self.assertIsNone(util.get_path("nope", "a.b"))


if __name__ == "__main__":
    unittest.main()