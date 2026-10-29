import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from support import NoNetworkCase  # noqa: E402

from stock_worker import shareholding  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "nse_stock"
KEYS = {
    "quarter_end", "filed_at", "promoter_pct", "fii_pct", "dii_pct",
    "public_pct", "other_pct", "source_url",
}


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class ShareholdingTests(NoNetworkCase):
    def test_fixture_parses_to_records_with_the_documented_keys(self):
        records = shareholding.parse(load("shareholding.json"))
        self.assertEqual(len(records), 20)
        for record in records:
            self.assertEqual(set(record), KEYS)

    def test_first_row_values(self):
        first = shareholding.parse(load("shareholding.json"))[0]
        self.assertEqual(first["quarter_end"], "2026-09-30")
        self.assertEqual(first["promoter_pct"], Decimal("50.44"))
        self.assertEqual(first["public_pct"], Decimal("49.56"))
        self.assertEqual(first["other_pct"], Decimal("0"))
        self.assertEqual(first["filed_at"], "2026-10-21")
        self.assertEqual(
            first["source_url"],
            "https://nsearchives.nseindia.com/corporate/xbrl/"
            "SHP_1742991_21102026042504_WEB.xml",
        )

    def test_fii_and_dii_are_none_on_every_row(self):
        # The JSON has no FII/DII split; only the XBRL filing carries it. The
        # gap is recorded; nothing is inferred.
        for record in shareholding.parse(load("shareholding.json")):
            self.assertIsNone(record["fii_pct"])
            self.assertIsNone(record["dii_pct"])

    def test_fii_value_is_parsed_when_present(self):
        row = {
            "date": "30-SEP-2026",
            "submissionDate": "21-OCT-2026",
            "pr_and_prgrp": "50.44",
            "fii": "15.2",
            "dii": "8.7",
            "public_val": "49.56",
            "employeeTrusts": "0",
            "xbrl": "https://example.test/xbrl.xml",
        }
        record = shareholding.parse([row])[0]
        self.assertEqual(record["fii_pct"], Decimal("15.2"))
        self.assertEqual(record["dii_pct"], Decimal("8.7"))

    def test_missing_fields_are_none(self):
        record = shareholding.parse([{"date": "30-SEP-2026"}])[0]
        self.assertIsNone(record["promoter_pct"])
        self.assertIsNone(record["public_pct"])
        self.assertIsNone(record["other_pct"])
        self.assertIsNone(record["source_url"])
        self.assertIsNone(record["filed_at"])

    def test_empty_response_is_empty(self):
        self.assertEqual(shareholding.parse([]), [])
        self.assertEqual(shareholding.parse({"data": []}), [])


if __name__ == "__main__":
    unittest.main()