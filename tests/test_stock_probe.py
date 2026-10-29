import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from support import FakeClient, NoNetworkCase  # noqa: E402

from stock_worker import probe  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "nse_stock"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def quote_html():
    payload = {
        "props": {
            "pageProps": {
                "priceInfo": {
                    "lastPrice": "1234.50",
                    "pChange": "1.23",
                    "weekHighLow": {"weekHigh": "1300.00", "weekLow": "1100.00"},
                },
                "securityInfo": {"symbol": "RELIANCE", "isin": "INE002A01018"},
                "metadata": {"marketCap": "123456789", "pdSymbolPe": "12.5"},
            }
        }
    }
    return (
        '<html><head><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(payload)
        + "</script></head></html>"
    )


class RegistryTests(NoNetworkCase):
    def test_candidate_registry_is_the_fixed_ordered_list(self):
        self.assertEqual(
            [candidate[0] for candidate in probe.CANDIDATES],
            ["stock_page_embedded", "nextapi", "trade_info", "cookie_order"],
        )

    def test_candidate_urls(self):
        self.assertIsNone(probe.CANDIDATES[0][1])  # parses the prime body
        self.assertEqual(probe.CANDIDATES[1][1], "from-stock-page")
        self.assertEqual(
            probe.CANDIDATES[2][1].format(symbol="RELIANCE"),
            "https://www.nseindia.com/api/quote-equity?symbol=RELIANCE&section=trade_info",
        )
        self.assertEqual(
            probe.CANDIDATES[3][1].format(symbol="RELIANCE"),
            "https://www.nseindia.com/api/quote-equity?symbol=RELIANCE",
        )

    def test_max_calls_is_six(self):
        self.assertEqual(probe.MAX_CALLS, 6)

    def test_budget_refuses_a_seventh_call(self):
        budget = probe.CallBudget(probe.MAX_CALLS)
        for _ in range(probe.MAX_CALLS):
            budget.spend()
        with self.assertRaises(probe.BudgetExceeded):
            budget.spend()


class PageParsingTests(NoNetworkCase):
    def test_find_quote_payload_in_next_data(self):
        payload = probe.find_quote_payload(quote_html())
        self.assertIsNotNone(payload)
        self.assertEqual(payload["priceInfo"]["lastPrice"], "1234.50")

    def test_find_quote_payload_returns_none_without_quote_json(self):
        self.assertIsNone(probe.find_quote_payload("<html>no scripts</html>"))
        self.assertIsNone(probe.find_quote_payload('<script>var x = 1;</script>'))

    def test_find_next_data_url_prefers_quote_route(self):
        html = (
            '<script src="/_next/static/chunks/app.js"></script>'
            '<script>window.__N = "/_next/data/BUILDID/en/quote/RELIANCE.json";</script>'
        )
        self.assertIn("quote", probe.find_next_data_url(html))

    def test_find_next_data_url_returns_none_without_one(self):
        self.assertIsNone(probe.find_next_data_url("<html>nothing</html>"))


class DryRunTests(NoNetworkCase):
    def test_dry_run_prints_the_plan_and_creates_no_client(self):
        original = probe.Client

        class ExplodingClient:
            def __init__(self, *args, **kwargs):
                raise AssertionError("dry-run created a client")

        probe.Client = ExplodingClient
        output = StringIO()
        try:
            with redirect_stdout(output):
                code = probe.main(["--dry-run"])
        finally:
            probe.Client = original
        self.assertEqual(code, 0)
        lines = output.getvalue().splitlines()
        self.assertIn(f"prime\t{probe.stock_page('RELIANCE')}", lines)
        self.assertIn("stock_page_embedded\t(parses the prime page's own body)", lines)
        self.assertIn("nextapi\t(_next/data/<buildId> route read from the prime page)", lines)
        self.assertIn(
            "trade_info\thttps://www.nseindia.com/api/quote-equity?symbol=RELIANCE&section=trade_info",
            lines,
        )
        self.assertIn(
            f"consolidated re-check\t{probe.consolidated_url('RELIANCE')}", lines
        )
        self.assertTrue(
            any(line.startswith(f"max calls: {probe.MAX_CALLS}") for line in lines)
        )


class RunTests(NoNetworkCase):
    def test_embedded_candidate_wins_without_extra_fetches(self):
        routes = {
            probe.stock_page("RELIANCE"): quote_html(),
            probe.consolidated_url("RELIANCE"): "{}",  # no baseline in this dir
        }
        client = FakeClient(routes)
        outcome = probe.run(client, "RELIANCE", None, probe.CallBudget(probe.MAX_CALLS))
        self.assertEqual(outcome["quote_source"], "stock_page_embedded")
        # prime + consolidated re-check only — the embedded candidate fetched nothing.
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(outcome["consolidated"]["result"], "no baseline")

    def test_trade_info_answers_when_embedded_and_nextapi_fail(self):
        html = "<html>no embedded quote, no _next/data</html>"
        routes = {
            probe.stock_page("RELIANCE"): html,
            probe.CANDIDATES[2][1].format(symbol="RELIANCE"): json.dumps(
                {"priceInfo": {"lastPrice": "99.90", "pChange": "1.10"}}
            ),
            probe.consolidated_url("RELIANCE"): "{}",
        }
        outcome = probe.run(
            FakeClient(routes), "RELIANCE", None, probe.CallBudget(probe.MAX_CALLS)
        )
        self.assertEqual(outcome["quote_source"], "trade_info")
        self.assertEqual(len(outcome["candidates"]), 3)
        self.assertIn("no embedded quote JSON", outcome["candidates"][0]["error"])
        self.assertIn("unprobed", outcome["candidates"][1]["error"])

    def test_nextapi_is_tried_when_the_page_carries_the_route(self):
        html = '<script>window.__N = "/_next/data/XYZ/en/quote/RELIANCE.json";</script>'
        route = "/_next/data/XYZ/en/quote/RELIANCE.json"
        routes = {
            probe.stock_page("RELIANCE"): html,
            probe.BASE + route: json.dumps({"priceInfo": {"lastPrice": "88.00"}}),
            probe.consolidated_url("RELIANCE"): "{}",
        }
        outcome = probe.run(
            FakeClient(routes), "RELIANCE", None, probe.CallBudget(probe.MAX_CALLS)
        )
        self.assertEqual(outcome["quote_source"], "nextapi")

    def test_consolidated_recheck_records_identical_against_the_fixture(self):
        standalone = load("results_standalone.json")
        with tempfile.TemporaryDirectory() as directory:
            save = Path(directory)
            (save / "results_standalone.json").write_text(
                json.dumps(standalone), encoding="utf-8"
            )
            routes = {
                probe.stock_page("RELIANCE"): quote_html(),
                probe.consolidated_url("RELIANCE"): json.dumps(standalone),
            }
            outcome = probe.run(
                FakeClient(routes), "RELIANCE", save, probe.CallBudget(probe.MAX_CALLS)
            )
            self.assertEqual(outcome["consolidated"]["result"], "identical")

    def test_run_writes_only_quote_json_and_manifest(self):
        seed_names = (
            "results_standalone.json",
            "results_consolidated.json",
            "announcements.json",
            "shareholding.json",
        )
        with tempfile.TemporaryDirectory() as directory:
            save = Path(directory)
            for name in seed_names:
                (save / name).write_text(json.dumps(load(name)), encoding="utf-8")
            (save / "README.md").write_text("# 003 fixture README", encoding="utf-8")
            (save / "manifest.json").write_text(
                json.dumps(
                    {
                        "generated_at": "seed",
                        "captured_by": "local",
                        "run_url": None,
                        "files": [
                            {
                                "endpoint": "results_standalone",
                                "fixture": "results_standalone.json",
                                "url": "https://www.nseindia.com/api/results-comparision?symbol=RELIANCE",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            before = {
                name: (save / name).read_bytes()
                for name in (*seed_names, "README.md")
            }
            routes = {
                probe.stock_page("RELIANCE"): quote_html(),
                probe.consolidated_url("RELIANCE"): json.dumps(
                    load("results_standalone.json")
                ),
            }
            outcome = probe.run(
                FakeClient(routes), "RELIANCE", save, probe.CallBudget(probe.MAX_CALLS)
            )
            self.assertEqual(outcome["quote_source"], "stock_page_embedded")
            for name, content in before.items():
                self.assertEqual((save / name).read_bytes(), content, name)
            quote = json.loads((save / "quote.json").read_text(encoding="utf-8"))
            self.assertEqual(quote["priceInfo"]["lastPrice"], "1234.50")
            manifest = json.loads((save / "manifest.json").read_text(encoding="utf-8"))
            fixtures = [item["fixture"] for item in manifest["files"]]
            self.assertIn("quote.json", fixtures)
            self.assertIn("results_standalone.json", fixtures)  # 003 entry kept


if __name__ == "__main__":
    unittest.main()