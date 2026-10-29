import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from support import FakeClient, NoNetworkCase, fixture  # noqa: E402

from ipo_agent import nse  # noqa: E402


class ParseSubscriptionTests(NoNetworkCase):
    def detail(self, name):
        return json.loads(fixture(name))

    def test_maps_categories_in_rule_order(self):
        sub = nse.parse_subscription(self.detail("nse_detail_SFCTECH.json")["bidDetails"])
        self.assertEqual(sub["bnii"]["times"], 0.19)
        self.assertEqual(sub["snii"]["times"], 0.33)
        self.assertEqual(sub["nii"]["times"], 0.24)
        self.assertEqual(sub["qib"]["times"], 0.0)
        self.assertEqual(sub["retail"]["times"], 0.2)
        self.assertEqual(sub["total"]["times"], 0.15)
        self.assertEqual(sub["bnii"]["shares_offered"], 2022821.0)

    def test_investor_sub_rows_without_offered_quantity_are_skipped(self):
        sub = nse.parse_subscription(self.detail("nse_detail_SFCTECH.json")["bidDetails"])
        self.assertNotIn("foreign institutional investors", sub)
        self.assertEqual(set(sub), {"qib", "nii", "bnii", "snii", "retail", "total"})

    def test_duplicate_category_keeps_the_first_row(self):
        rows = [
            {"category": "Retail Individual Investors", "noOfSharesOffered": "100", "noOfsharesBid": "100", "noOfTime": "1"},
            {"category": "Retail Individual Investors", "noOfSharesOffered": "100", "noOfsharesBid": "200", "noOfTime": "2"},
        ]
        sub = nse.parse_subscription(rows)
        self.assertEqual(sub["retail"]["times"], 1.0)

    def test_no_rows_is_empty(self):
        self.assertEqual(nse.parse_subscription(None), {})
        self.assertEqual(nse.parse_subscription([]), {})


class CleanAndNumberTests(NoNetworkCase):
    def test_clean_strips_tags_quotes_and_whitespace(self):
        self.assertEqual(nse._clean('  <b>"Acme   Ltd"</b> '), "Acme Ltd")
        self.assertIsNone(nse._clean(None))

    def test_numbers_accept_commas(self):
        self.assertEqual(nse._f("1,234.5"), 1234.5)
        self.assertIsNone(nse._f(None))
        self.assertIsNone(nse._f("n/a"))


class ParseDetailTests(NoNetworkCase):
    def test_sfc_fields(self):
        detail = nse.parse_detail(json.loads(fixture("nse_detail_SFCTECH.json")))
        self.assertEqual(detail["company"], "SFC Environmental Technologies Limited")
        self.assertEqual(detail["symbol"], "SFCTECH")
        self.assertEqual(detail["issue_period"], ["27-Oct-2026", "29-Oct-2026"])
        self.assertEqual((detail["price_low"], detail["price_high"]), (313.0, 330.0))
        self.assertEqual(detail["face_value"], "Rs. 2 per Equity Share")
        self.assertEqual(detail["lot"], 45)
        self.assertEqual(detail["rhp_url"], "https://nsearchives.nseindia.com/content/ipo/RHP_SFCTECH.zip")
        self.assertEqual(detail["anchor_report_url"], "https://nsearchives.nseindia.com/content/ipo/ANCHOR_SFCTECH.zip")
        self.assertEqual(detail["subscription"]["total"]["times"], 0.15)

    def test_zero_bid_total_is_still_parsed(self):
        detail = nse.parse_detail(json.loads(fixture("nse_detail_ACME.json")))
        self.assertEqual(detail["subscription"]["total"]["shares_bid"], 0.0)
        self.assertEqual(detail["subscription"]["total"]["times"], 0.0)

    def test_missing_price_range(self):
        detail = nse.parse_detail({"companyName": "Empty Ltd", "issueInfo": {"dataList": []}})
        self.assertEqual(detail["company"], "Empty Ltd")
        self.assertIsNone(detail["price_low"])
        self.assertIsNone(detail["price_high"])
        self.assertIsNone(detail["lot"])
        self.assertEqual(detail["issue_period"], [])


class ApiTests(NoNetworkCase):
    def client(self, **overrides):
        routes = {
            nse.BASE + "/": "<html>home</html>",
            nse.REFERER: "<html>upcoming</html>",
            nse.BASE + "/api/ipo-current-issue": json.dumps([{"symbol": "SFCTECH", "series": "EQ"}]),
            nse.BASE + "/api/all-upcoming-issues?category=ipo": json.dumps([{"symbol": "ACME", "series": "EQ"}]),
            nse.BASE + "/api/ipo-detail?symbol=SFCTECH&series=EQ": fixture("nse_detail_SFCTECH.json"),
        }
        routes.update(overrides)
        return FakeClient(routes)

    def test_current_primes_cookies_then_calls_the_api(self):
        client = self.client()
        self.assertEqual(nse.NSE(client).current(), [{"symbol": "SFCTECH", "series": "EQ"}])
        self.assertEqual(
            client.calls,
            [
                ("get", nse.BASE + "/"),
                ("get", nse.REFERER),
                ("get_text", nse.BASE + "/api/ipo-current-issue"),
            ],
        )

    def test_priming_happens_once(self):
        client = self.client()
        api = nse.NSE(client)
        api.current()
        api.upcoming()
        self.assertEqual([c[0] for c in client.calls].count("get"), 2)

    def test_upcoming(self):
        self.assertEqual(nse.NSE(self.client()).upcoming(), [{"symbol": "ACME", "series": "EQ"}])

    def test_detail_parses_the_issue(self):
        detail = nse.NSE(self.client()).detail("SFCTECH", "EQ")
        self.assertEqual(detail["symbol"], "SFCTECH")
        self.assertEqual(detail["price_high"], 330.0)

    def test_priming_ignores_a_failing_homepage(self):
        client = self.client(**{nse.BASE + "/": RuntimeError("403")})
        detail = nse.NSE(client).detail("SFCTECH", "EQ")
        self.assertEqual(detail["symbol"], "SFCTECH")


if __name__ == "__main__":
    unittest.main()
