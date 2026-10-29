import datetime as dt
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

from ipo_agent import nse_stock_smoke as smoke

FIXTURES = ROOT / "tests" / "fixtures" / "nse_stock"


class StubClient:
    def __init__(self, body=b"{}"):
        self.body = body
        self.calls = []

    def get(self, url, referer=None, accept="*/*"):
        self.calls.append((url, referer, accept))
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


def result(required=True, ok=True, kind="json"):
    return {"required": required, "kind": kind, "ok": ok}


class UrlTests(unittest.TestCase):
    def test_fixed_urls(self):
        requests = smoke.build_requests("reliance", "adanient", dt.date(2026, 10, 29))
        self.assertEqual(len(requests), 12)
        urls = {item.endpoint.id: item.url for item in requests}
        self.assertEqual(urls["prime_home"], "https://www.nseindia.com/")
        self.assertEqual(
            urls["prime_stock"],
            "https://www.nseindia.com/get-quotes/equity?symbol=RELIANCE",
        )
        self.assertEqual(
            urls["quote"],
            "https://www.nseindia.com/api/quote-equity?symbol=RELIANCE",
        )
        self.assertEqual(
            urls["results_standalone"],
            "https://www.nseindia.com/api/results-comparision?symbol=RELIANCE",
        )
        self.assertEqual(
            urls["results_consolidated"],
            "https://www.nseindia.com/api/results-comparision?symbol=RELIANCE&consolidated=true",
        )
        self.assertEqual(
            urls["results_filings"],
            "https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Quarterly&symbol=RELIANCE",
        )
        self.assertEqual(
            urls["announcements"],
            "https://www.nseindia.com/api/corporate-announcements?index=equities&symbol=RELIANCE",
        )
        self.assertEqual(
            urls["announcements_market"],
            "https://www.nseindia.com/api/corporate-announcements?index=equities&from_date=23-10-2026&to_date=29-10-2026",
        )
        self.assertEqual(
            urls["shareholding"],
            "https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol=RELIANCE",
        )
        self.assertEqual(
            urls["pledges"],
            "https://www.nseindia.com/api/corporate-pledgedata?index=equities&symbol=ADANIENT",
        )
        self.assertEqual(
            urls["pledges_market"],
            "https://www.nseindia.com/api/corporate-pledgedata?index=equities",
        )
        self.assertEqual(
            urls["equity_list"],
            "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
        )

    def test_registry_and_required_flags(self):
        self.assertEqual(len(smoke.ENDPOINTS), 12)
        self.assertEqual(smoke.MAX_CALLS, 12)
        required = [item for item in smoke.ENDPOINTS if item.required and item.kind != "html"]
        self.assertEqual(len(required), 8)
        optional = {item.id for item in smoke.ENDPOINTS if not item.required}
        self.assertEqual(
            optional,
            {"prime_home", "prime_stock", "announcements_market", "pledges_market"},
        )


class BudgetTests(unittest.TestCase):
    def test_budget_refuses_second_call(self):
        budget = smoke.CallBudget(1)
        budget.spend()
        with self.assertRaises(smoke.BudgetExceeded):
            budget.spend()

    def test_run_entries_stops_before_thirteenth_call(self):
        endpoint = smoke.Endpoint("probe", "html", None, False, False)
        requests = tuple(
            smoke.Request(endpoint, f"https://example.test/{index}", None)
            for index in range(13)
        )
        client = StubClient(b"ok")
        with self.assertRaises(smoke.BudgetExceeded):
            smoke.run_entries(client, smoke.CallBudget(12), requests)
        self.assertEqual(len(client.calls), 12)

    def test_dry_run_does_not_create_a_client(self):
        original = smoke.Client

        class ExplodingClient:
            def __init__(self, *args, **kwargs):
                raise AssertionError("dry-run created a client")

        smoke.Client = ExplodingClient
        output = StringIO()
        try:
            with redirect_stdout(output):
                code = smoke.main(["--dry-run"])
        finally:
            smoke.Client = original
        self.assertEqual(code, 0)
        lines = [line for line in output.getvalue().splitlines() if line.strip()]
        self.assertEqual(len(lines), 12)
        self.assertIn(
            "quote\thttps://www.nseindia.com/api/quote-equity?symbol=RELIANCE",
            lines,
        )


class SummaryTests(unittest.TestCase):
    def test_summarise_json_object(self):
        summary = smoke.summarise("json", {"data": [{"a": 1}, {"a": 2}], "meta": {"x": 1}})
        self.assertEqual(summary["type"], "object")
        self.assertEqual(summary["row_count"], 2)
        self.assertEqual(summary["keys"], ["data", "meta"])

    def test_summarise_json_list(self):
        summary = smoke.summarise("json", [{"a": 1}, {"a": 2}, {"a": 3}])
        self.assertEqual(summary["type"], "list")
        self.assertEqual(summary["row_count"], 3)

    def test_summarise_csv(self):
        summary = smoke.summarise("csv", b"SYMBOL,NAME\nA,B\nC,D\n")
        self.assertEqual(summary["header"], ["SYMBOL", "NAME"])
        self.assertEqual(summary["row_count"], 2)

    def test_get_path(self):
        body = {
            "resCmpData": [{"income": 10}],
            "priceInfo": {"weekHighLow": {"weekHigh": 5}},
        }
        self.assertEqual(smoke.get_path(body, "resCmpData[].income"), 10)
        self.assertEqual(smoke.get_path(body, "priceInfo.weekHighLow.weekHigh"), 5)
        self.assertIsNone(smoke.get_path(body, "missing"))
        self.assertEqual(smoke.get_path([{"symbol": "X"}], "[].symbol"), "X")

    def test_field_coverage_marks_missing(self):
        endpoint = smoke.Endpoint(
            "probe",
            "json",
            "probe.json",
            True,
            True,
            (smoke.field("income", "data[].income"), smoke.field("missing", "data[].missing")),
        )
        coverage = {item["name"]: item for item in smoke.field_coverage("json", {"data": [{"income": 1}]}, endpoint)}
        self.assertTrue(coverage["income"]["found"])
        self.assertFalse(coverage["missing"]["found"])

    def test_unit_is_not_assumed(self):
        self.assertEqual(smoke.extract_unit("json", {"income": 1}), smoke.UNIT_NOT_STATED)
        self.assertEqual(smoke.extract_unit("json", {"unit": "INR lakh"}), "INR lakh")

    def test_g1_candidate(self):
        self.assertEqual(smoke.g1_candidate([result()]), "PASS")
        self.assertEqual(smoke.g1_candidate([result(ok=True), result(ok=False)]), "PARTIAL")
        self.assertEqual(smoke.g1_candidate([result(ok=False)]), "FAIL")

    def test_summary_keys_and_no_headers(self):
        results = [
            {
                "endpoint": "quote",
                "kind": "json",
                "fixture": "quote.json",
                "required": True,
                "url": "https://example.test/quote",
                "ok": True,
                "bytes": 10,
                "rows": 1,
                "fields": [],
                "unit": smoke.UNIT_NOT_STATED,
                "error": None,
                "elapsed_ms": 1,
                "original_bytes": None,
                "saved_bytes": None,
                "lists": [],
            }
        ]
        summary = smoke.build_summary(results, "RELIANCE", "ADANIENT", "local", None)
        self.assertTrue(
            {"endpoint", "ok", "bytes", "rows", "fields", "unit", "error"}
            <= set(summary["results"][0])
        )
        text = json.dumps(summary)
        self.assertNotIn("Cookie", text)
        self.assertNotIn("User-Agent", text)

    def test_readme_is_generated_from_manifest(self):
        manifest = {
            "generated_at": "2026-10-29T00:00:00+00:00",
            "captured_by": "local",
            "run_url": None,
            "files": [
                {
                    "endpoint": "quote",
                    "fixture": "quote.json",
                    "rows": 1,
                    "original_bytes": 120,
                    "saved_bytes": 100,
                    "unit": smoke.UNIT_NOT_STATED,
                    "fields": [{"name": "last_price", "path": "priceInfo.lastPrice", "found": True}],
                }
            ],
        }
        text = smoke.render_readme(manifest)
        self.assertIn("Captured by: local", text)
        self.assertIn("`quote`", text)
        self.assertIn("last_price: found", text)


class FixtureTests(unittest.TestCase):
    def response_fixtures(self):
        if not FIXTURES.exists():
            return []
        return sorted(path for path in FIXTURES.glob("*.json") if path.name != "manifest.json")

    def test_committed_json_fixtures_respect_cap(self):
        fixtures = self.response_fixtures()
        if not fixtures:
            self.skipTest("fixtures not captured yet")
        for path in fixtures:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self.assertLessEqual(len(data), smoke.FIXTURE_MAX_ROWS, path.name)
            elif isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, list):
                        self.assertLessEqual(len(value), smoke.FIXTURE_MAX_ROWS, f"{path.name}:{key}")

    def test_saved_fixture_is_trimmed_with_manifest(self):
        body = json.dumps({"data": [{"n": index} for index in range(25)]}).encode("utf-8")
        endpoint = smoke.Endpoint("probe", "json", "probe.json", True, True)
        request = smoke.Request(endpoint, "https://example.test/probe", None)
        with tempfile.TemporaryDirectory() as directory:
            save_dir = Path(directory)
            results = smoke.run_entries(
                StubClient(body), smoke.CallBudget(1), (request,), save_dir=save_dir
            )
            saved = json.loads((save_dir / "probe.json").read_text(encoding="utf-8"))
            self.assertEqual(len(saved["data"]), smoke.FIXTURE_MAX_ROWS)
            manifest = smoke.build_manifest(results, "local", None)
            self.assertEqual(manifest["files"][0]["lists"][0]["original_rows"], 25)
            self.assertEqual(manifest["files"][0]["lists"][0]["saved_rows"], smoke.FIXTURE_MAX_ROWS)

    def test_csv_is_saved_in_full(self):
        lines = ["SYMBOL,NAME"] + [f"S{index},N{index}" for index in range(25)]
        body = ("\n".join(lines) + "\n").encode("utf-8")
        endpoint = smoke.Endpoint("probe", "csv", "probe.csv", True, True)
        request = smoke.Request(endpoint, "https://example.test/probe.csv", None)
        with tempfile.TemporaryDirectory() as directory:
            save_dir = Path(directory)
            results = smoke.run_entries(
                StubClient(body), smoke.CallBudget(1), (request,), save_dir=save_dir
            )
            saved = (save_dir / "probe.csv").read_bytes()
            self.assertEqual(saved, body)
            self.assertEqual(results[0]["rows"], 25)

    def test_equity_list_header(self):
        path = FIXTURES / "equity_list.csv"
        if not path.exists():
            self.skipTest("equity fixture not captured yet")
        header = smoke.summarise("csv", path.read_bytes())["header"]
        self.assertEqual(
            [item.strip() for item in header],
            [
                "SYMBOL",
                "NAME OF COMPANY",
                "SERIES",
                "DATE OF LISTING",
                "PAID UP VALUE",
                "MARKET LOT",
                "ISIN NUMBER",
                "FACE VALUE",
            ],
        )

    def test_registered_fields_resolve_in_fixtures(self):
        fixtures = self.response_fixtures()
        if not fixtures:
            self.skipTest("fixtures not captured yet")
        for endpoint in smoke.ENDPOINTS:
            if endpoint.kind != "json" or not endpoint.fixture:
                continue
            path = FIXTURES / endpoint.fixture
            if not path.exists():
                if (endpoint.id, "fixture") in smoke.KNOWN_GAPS:
                    continue
                if endpoint.required:
                    self.fail(f"missing required fixture {path.name}")
                continue
            body = json.loads(path.read_text(encoding="utf-8"))
            coverage = {
                item["name"]: item
                for item in smoke.field_coverage("json", body, endpoint)
            }
            for item in endpoint.fields:
                is_gap = (endpoint.id, item.name) in smoke.KNOWN_GAPS
                self.assertEqual(
                    coverage[item.name]["found"],
                    not is_gap,
                    f"{endpoint.id}.{item.name}",
                )


if __name__ == "__main__":
    unittest.main()
