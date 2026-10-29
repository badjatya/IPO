import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from support import NoNetworkCase  # noqa: E402

from stock_worker import results  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "nse_stock"
RESULT_KEYS = {
    "period_end", "consolidated", "revenue_cr", "other_income_cr",
    "expenses_cr", "ebitda_cr", "pat_cr", "eps", "filed_at", "source_url",
    "period_start", "audited",
}


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class ParseResultsTests(NoNetworkCase):
    def setUp(self):
        super().setUp()
        self.standalone = load("results_standalone.json")
        self.filings = load("results_filings.json")
        self.records = results.parse_results(self.standalone, self.filings)

    def test_five_records_with_exactly_the_db_md_keys(self):
        self.assertEqual(len(self.records), 5)
        for record in self.records:
            self.assertEqual(set(record), RESULT_KEYS)

    def test_first_row_values(self):
        first = self.records[0]
        self.assertEqual(first["period_end"], "2024-12-31")
        self.assertEqual(first["consolidated"], False)
        self.assertEqual(first["revenue_cr"], Decimal("128260.00"))
        self.assertEqual(first["other_income_cr"], Decimal("3214.00"))
        self.assertEqual(first["expenses_cr"], Decimal("119877.00"))
        self.assertEqual(first["pat_cr"], Decimal("8721.00"))
        self.assertEqual(first["eps"], Decimal("6.44"))
        self.assertEqual(first["period_start"], "2024-10-01")

    def test_unit_evidence_note_text_matches_net_sale(self):
        # The response states no unit field, but the row's own note does:
        # "Net Revenue is Rs 128,260 crore" ↔ re_net_sale 12,826,000 lakh.
        row = self.standalone["resCmpData"][0]
        self.assertIn("Net Revenue is Rs 128,260 crore", row["re_desc_note_seg"])
        self.assertEqual(row["re_net_sale"], "12826000")
        self.assertEqual(self.records[0]["revenue_cr"], Decimal("128260.00"))

    def test_eps_is_per_share_and_never_converted(self):
        # 6.44 ₹/share stays 6.44; converting it like the lakh amounts (÷100)
        # would give 0.0644.
        self.assertEqual(self.records[0]["eps"], Decimal("6.44"))
        self.assertNotEqual(self.records[0]["eps"], Decimal("0.0644"))

    def test_ebitda_derived_from_stated_fields(self):
        # 12,826,000 − (11,987,700 − 237,100 − 445,900) = 1,521,300 lakh → 15,213.00.
        self.assertEqual(self.records[0]["ebitda_cr"], Decimal("15213.00"))
        # Second row: 13,405,400 − (12,764,100 − 266,200 − 435,000) = 1,342,500 → 13,425.00.
        self.assertEqual(self.records[1]["ebitda_cr"], Decimal("13425.00"))

    def test_ebitda_missing_field_is_none(self):
        rows = {
            "resCmpData": [
                {
                    "re_to_dt": "31-DEC-2024",
                    "re_net_sale": "1000",
                    "re_oth_tot_exp": "800",
                    "re_int_new": "50",
                    # re_depr_und_exp absent — EBITDA must not be derived
                }
            ]
        }
        record = results.parse_results(rows, [])[0]
        self.assertIsNone(record["ebitda_cr"])

    def test_ebitda_stated_zero_is_a_value(self):
        rows = {
            "resCmpData": [
                {
                    "re_to_dt": "31-DEC-2024",
                    "re_net_sale": "1000",
                    "re_oth_tot_exp": "800",
                    "re_int_new": "50",
                    "re_depr_und_exp": "0",
                }
            ]
        }
        record = results.parse_results(rows, [])[0]
        self.assertEqual(record["ebitda_cr"], Decimal("2.50"))

    def test_consolidated_is_false_on_every_comparison_row(self):
        for record in self.records:
            self.assertFalse(record["consolidated"])

    def test_join_takes_the_non_consolidated_filings_row(self):
        # The 31-Dec-2024 quarter has two filings rows: Non-Consolidated at
        # 20:20 and Consolidated at 20:15. The standalone record must take the
        # 20:20 time and the Non-Consolidated XBRL link, never the other row's.
        first = self.records[0]
        self.assertEqual(first["filed_at"], "2025-01-16T20:20:00+05:30")
        self.assertEqual(
            first["source_url"],
            "https://nsearchives.nseindia.com/corporate/xbrl/"
            "INDAS_117298_1348254_16012025082021.xml",
        )
        self.assertEqual(first["audited"], "Un-Audited")

    def test_quarter_without_matching_filings_row_has_none(self):
        rows = {
            "resCmpData": [
                {
                    "re_to_dt": "30-JUN-2026",
                    "re_net_sale": "1000",
                    "re_oth_tot_exp": "800",
                }
            ]
        }
        record = results.parse_results(rows, self.filings)[0]
        self.assertIsNone(record["filed_at"])
        self.assertIsNone(record["source_url"])
        self.assertIsNone(record["audited"])
        self.assertEqual(record["period_end"], "2026-06-30")

    def test_missing_re_net_sale_gives_none_not_total_income(self):
        # re_total_inc includes other income, which is stored separately as
        # other_income_cr; using it as revenue would double-count. Missing is
        # missing, never estimated.
        rows = {
            "resCmpData": [
                {
                    "re_to_dt": "31-DEC-2024",
                    "re_total_inc": "13147400",
                    "re_oth_inc_new": "321400",
                }
            ]
        }
        record = results.parse_results(rows, [])[0]
        self.assertIsNone(record["revenue_cr"])
        self.assertEqual(record["other_income_cr"], Decimal("3214.00"))

    def test_empty_comparison_is_empty(self):
        self.assertEqual(results.parse_results({"resCmpData": []}, self.filings), [])
        self.assertEqual(results.parse_results([], self.filings), [])


class ConsolidatedTests(NoNetworkCase):
    def test_identical_consolidated_body_yields_no_rows_and_a_gap_flag(self):
        # results_consolidated.json is byte-identical to standalone (003); the
        # endpoint ignores consolidated=true. parse_consolidated must return no
        # rows and a gap flag — never standalone figures relabelled.
        consolidated = load("results_consolidated.json")
        records, gap = results.parse_consolidated(consolidated)
        self.assertEqual(records, [])
        self.assertIn("consolidated", gap)
        self.assertIn("standalone", gap["consolidated"])


if __name__ == "__main__":
    unittest.main()