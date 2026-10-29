import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from support import NoNetworkCase, fixture  # noqa: E402

from ipo_agent import investorgain  # noqa: E402


class ParseTests(NoNetworkCase):
    def setUp(self):
        super().setUp()
        self.rows = {r["name"]: r for r in investorgain.parse(fixture("investorgain_gmp.html"))}

    def test_joins_self_next_f_chunks(self):
        self.assertEqual(len(self.rows), 5)

    def test_mainboard_row_fields(self):
        sfc = self.rows["SFC Environmental Technologies"]
        self.assertEqual(sfc["board"], "mainboard")
        self.assertEqual(sfc["status"], "open")
        self.assertEqual(sfc["status_code"], "O")
        self.assertEqual((sfc["open"], sfc["close"], sfc["allotment"], sfc["listing"]),
                         ("2026-10-27", "2026-10-29", "2026-10-30", "2026-11-03"))
        self.assertEqual(sfc["price"], 330.0)
        self.assertEqual(sfc["lot"], 45)
        self.assertEqual(sfc["size_cr"], 667.53)
        self.assertEqual(sfc["gmp"], 10.0)
        self.assertEqual(sfc["gmp_pct"], 3.03)
        self.assertEqual(sfc["gmp_low"], 10.0)
        self.assertEqual(sfc["gmp_high"], 32.0)
        self.assertEqual(sfc["pe"], 19.24)
        self.assertEqual(sfc["subscription_x"], 0.15)
        self.assertEqual(sfc["gmp_updated"], "28-Oct 23:37")
        self.assertEqual(sfc["url"], "https://www.investorgain.com/gmp/sfc-environmental-technologies-ipo/1642/")

    def test_sme_row_is_marked_sme(self):
        self.assertEqual(self.rows["SME Widgets Limited"]["board"], "sme")

    def test_status_codes_are_mapped(self):
        self.assertEqual(self.rows["Acme Industries Limited"]["status"], "upcoming")
        self.assertEqual(self.rows["Closed Co Limited"]["status"], "closed")
        self.assertEqual(self.rows["Old Listed Co"]["status"], "listed")

    def test_gmp_without_arrows_has_no_low_high(self):
        acme = self.rows["Acme Industries Limited"]
        self.assertEqual(acme["gmp"], 5.0)
        self.assertIsNone(acme["gmp_low"])
        self.assertIsNone(acme["gmp_high"])

    def test_missing_gmp_is_none(self):
        stream = json.dumps({"reportTableData": [
            {"~ipo_name": "No Gmp Co", "~ipo_category1": "IPO", "~ipo_status1": "U"},
        ]}, separators=(",", ":"))
        page = "self.__next_f.push([1," + json.dumps(stream) + "])"
        rows = investorgain.parse(page)
        self.assertIsNone(rows[0]["gmp"])
        self.assertEqual(rows[0]["name"], "No Gmp Co")


class LayoutChangeTests(NoNetworkCase):
    def test_missing_report_table_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            investorgain.parse("<html><body>no data</body></html>")
        self.assertIn("reportTableData not found", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
