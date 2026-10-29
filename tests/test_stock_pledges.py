import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from support import NoNetworkCase  # noqa: E402

from stock_worker import pledges  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "nse_stock"
KEYS = {
    "company", "quarter_end", "disclosed_at", "shares_held", "shares_pledged",
    "promoter_pledged_pct", "promoter_pct", "pledged_pct_of_total",
}


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class PledgesTests(NoNetworkCase):
    def test_fixture_parses_to_one_record(self):
        records = pledges.parse(load("pledges.json"))
        self.assertEqual(len(records), 1)
        self.assertEqual(set(records[0]), KEYS)

    def test_first_row_values(self):
        record = pledges.parse(load("pledges.json"))[0]
        self.assertEqual(record["company"], "Adani Enterprises Limited")
        self.assertEqual(record["quarter_end"], "2026-09-30")
        self.assertEqual(record["disclosed_at"], "2026-10-29T16:30:25+05:30")
        self.assertEqual(record["shares_held"], Decimal("974234554"))
        self.assertEqual(record["shares_pledged"], Decimal("21723685"))
        # The computed share of promoter holding (2.23), never NSE's 1.61
        # (pledged ÷ total shares).
        self.assertEqual(record["promoter_pledged_pct"], Decimal("2.23"))
        self.assertNotEqual(record["promoter_pledged_pct"], Decimal("1.61"))
        # percPromoterHolding arrives with leading spaces; stripped.
        self.assertEqual(record["promoter_pct"], Decimal("71.97"))
        # percSharesPledged is kept raw for reference.
        self.assertEqual(record["pledged_pct_of_total"], Decimal("1.61"))

    def test_market_fixture_parses_to_20_records_without_symbol(self):
        records = pledges.parse(load("pledges_market.json"))
        self.assertEqual(len(records), 20)
        for record in records:
            self.assertNotIn("symbol", record)
            self.assertTrue(record["company"])
            # Quarter-ends vary across rows (30-Sep, 31-Mar, 30-Jun 2026).
            self.assertRegex(record["quarter_end"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(records[0]["company"], "20 Microns Limited")
        self.assertEqual(records[0]["quarter_end"], "2026-09-30")
        self.assertEqual(records[0]["promoter_pct"], Decimal("45.04"))

    def test_zero_promoter_holding_yields_none_not_division_by_zero(self):
        row = {
            "comName": "Empty Holdings Limited",
            "shp": "30-Sep-2026",
            "totPromoterHolding": "0",
            "numSharesPledged": "1000",
            "percSharesPledged": "0.5",
            "percPromoterHolding": "0",
        }
        record = pledges.parse([row])[0]
        self.assertIsNone(record["promoter_pledged_pct"])
        self.assertEqual(record["shares_held"], Decimal("0"))

    def test_missing_share_counts_yield_none(self):
        record = pledges.parse([{"comName": "X Limited"}])[0]
        self.assertIsNone(record["promoter_pledged_pct"])
        self.assertIsNone(record["shares_held"])
        self.assertIsNone(record["shares_pledged"])
        self.assertIsNone(record["promoter_pct"])
        self.assertIsNone(record["quarter_end"])

    def test_rounds_half_up_to_two_dp(self):
        row = {
            "totPromoterHolding": "3",
            "numSharesPledged": "1",
            "comName": "X Limited",
        }
        record = pledges.parse([row])[0]
        # 1/3 × 100 = 33.333... → rounds HALF_UP to 33.33; 33.333 is not 33.34.
        self.assertEqual(record["promoter_pledged_pct"], Decimal("33.33"))

    def test_missing_company_name_is_none(self):
        # A row without comName gives company None, never an empty string.
        record = pledges.parse([{"shp": "30-Sep-2026"}])[0]
        self.assertIsNone(record["company"])
        record = pledges.parse([{"comName": "   ", "shp": "30-Sep-2026"}])[0]
        self.assertIsNone(record["company"])

    def test_empty_response_is_empty(self):
        self.assertEqual(pledges.parse({"data": []}), [])
        self.assertEqual(pledges.parse([]), [])


if __name__ == "__main__":
    unittest.main()