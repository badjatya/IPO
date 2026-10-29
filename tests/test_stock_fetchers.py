import json
import sys
import unittest
import urllib.error
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from support import FakeClient, NoNetworkCase  # noqa: E402

from stock_worker import fetchers  # noqa: E402
from stock_worker import __main__ as cli  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "nse_stock"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def routes_for(symbol="RELIANCE", shareholding=None):
    return {
        fetchers.stock_page(symbol): "<html>stock page</html>",
        fetchers.BASE + fetchers.results_url(symbol): json.dumps(
            load("results_standalone.json")
        ),
        fetchers.BASE + fetchers.filings_url(symbol): json.dumps(
            load("results_filings.json")
        ),
        fetchers.BASE + fetchers.announcements_url(symbol): json.dumps(
            load("announcements.json")
        ),
        fetchers.BASE + fetchers.shareholding_url(symbol): (
            shareholding
            if shareholding is not None
            else json.dumps(load("shareholding.json"))
        ),
        fetchers.BASE + fetchers.pledges_url(symbol): json.dumps(
            load("pledges.json")
        ),
    }


def expected_calls(symbol="RELIANCE"):
    return [
        ("get", fetchers.stock_page(symbol)),
        ("get_text", fetchers.BASE + fetchers.results_url(symbol)),
        ("get_text", fetchers.BASE + fetchers.filings_url(symbol)),
        ("get_text", fetchers.BASE + fetchers.announcements_url(symbol)),
        ("get_text", fetchers.BASE + fetchers.shareholding_url(symbol)),
        ("get_text", fetchers.BASE + fetchers.pledges_url(symbol)),
    ]


class FetchAllTests(NoNetworkCase):
    def test_fetches_every_source_under_one_shared_prime(self):
        client = FakeClient(routes_for())
        bundle = fetchers.fetch_all(client, "RELIANCE")
        # Quote adds no call (source unconfirmed), so the count stays 6.
        self.assertEqual(client.calls, expected_calls())
        # The only error is the unconfirmed quote source (probe 2026-10-30).
        self.assertEqual([e["source"] for e in bundle["errors"]], ["quote"])
        self.assertTrue(bundle["errors"][0]["error"].startswith("SourceError:"))
        self.assertIn("not confirmed", bundle["errors"][0]["error"])
        self.assertNotIn("quote", bundle["records"])
        self.assertEqual(len(bundle["records"]["results"]), 5)
        self.assertEqual(len(bundle["records"]["announcements"]), 20)
        self.assertEqual(len(bundle["records"]["shareholding"]), 20)
        self.assertEqual(len(bundle["records"]["pledges"]), 1)
        self.assertEqual(
            bundle["records"]["results"][0]["revenue_cr"],
            int(load("results_standalone.json")["resCmpData"][0]["re_net_sale"]) / 100,
        )

    def test_failing_source_lands_in_errors_and_does_not_stop_the_rest(self):
        client = FakeClient(
            routes_for(shareholding=RuntimeError("shareholding down"))
        )
        bundle = fetchers.fetch_all(client, "RELIANCE")
        self.assertNotIn("shareholding", bundle["records"])
        self.assertIn("results", bundle["records"])
        self.assertIn("announcements", bundle["records"])
        self.assertIn("pledges", bundle["records"])
        # The failing source and the unconfirmed quote both land in errors.
        self.assertEqual(
            [e["source"] for e in bundle["errors"]],
            ["shareholding", "quote"],
        )
        self.assertEqual(
            bundle["errors"][0]["error"], "RuntimeError: shareholding down"
        )

    def test_http_404_without_a_body_does_not_stop_the_rest(self):
        url = fetchers.BASE + fetchers.shareholding_url("RELIANCE")
        not_found = urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        client = FakeClient(routes_for(shareholding=not_found))
        bundle = fetchers.fetch_all(client, "RELIANCE")
        self.assertIn("pledges", bundle["records"])
        self.assertEqual(bundle["errors"][0]["source"], "shareholding")
        self.assertTrue(bundle["errors"][0]["error"].startswith("HTTPError:"))

    def test_symbol_is_uppercased_for_urls(self):
        client = FakeClient(routes_for("RELIANCE"))
        fetchers.fetch_all(client, " reliance ")
        self.assertEqual(client.calls, expected_calls("RELIANCE"))

    def test_since_is_passed_to_the_announcements_fetch(self):
        client = FakeClient(routes_for())
        bundle = fetchers.fetch_all(client, "RELIANCE", since="2026-10-25T00:00:00+05:30")
        self.assertEqual(len(bundle["records"]["announcements"]), 3)


class DryRunTests(NoNetworkCase):
    def test_dry_run_prints_the_urls_and_creates_no_client(self):
        original = cli.Client

        class ExplodingClient:
            def __init__(self, *args, **kwargs):
                raise AssertionError("dry-run created a client")

        cli.Client = ExplodingClient
        output = StringIO()
        try:
            with redirect_stdout(output):
                code = cli.main(["--dry-run"])
        finally:
            cli.Client = original
        self.assertEqual(code, 0)
        calls = dict(line.split("\t", 1) for line in output.getvalue().splitlines())
        self.assertEqual(
            calls["prime"], "https://www.nseindia.com/get-quotes/equity?symbol=RELIANCE"
        )
        self.assertEqual(
            calls["results"],
            "https://www.nseindia.com/api/results-comparision?symbol=RELIANCE",
        )
        self.assertEqual(
            calls["results_filings"],
            "https://www.nseindia.com/api/corporates-financial-results?index=equities"
            "&period=Quarterly&symbol=RELIANCE",
        )
        self.assertEqual(
            calls["announcements"],
            "https://www.nseindia.com/api/corporate-announcements?index=equities&symbol=RELIANCE",
        )
        self.assertEqual(
            calls["shareholding"],
            "https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol=RELIANCE",
        )
        self.assertEqual(
            calls["pledges"],
            "https://www.nseindia.com/api/corporate-pledgedata?index=equities&symbol=RELIANCE",
        )
        self.assertEqual(
            calls["quote"],
            "(no call: quote source unconfirmed — see data-sources.md)",
        )


class MarketUrlTests(NoNetworkCase):
    def test_announcements_market_window(self):
        import datetime as dt

        url = fetchers.announcements_market_url(dt.date(2026, 10, 29))
        self.assertEqual(
            url,
            "/api/corporate-announcements?index=equities&from_date=23-10-2026&to_date=29-10-2026",
        )

    def test_pledges_market_url(self):
        self.assertEqual(fetchers.pledges_market_url(), "/api/corporate-pledgedata?index=equities")


if __name__ == "__main__":
    unittest.main()