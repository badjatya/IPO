"""One-off development probe for the NSE stock endpoints in task 003.

This is not the stock worker's fetcher and does not settle D09. Task 014 may
move, replace or delete it when it chooses where the real stock code lives.

The probe makes one fixed list of requests, prints the shape and field coverage
of each response, and can save a trimmed fixture per data call together with a
manifest and a generated README.
"""

import argparse
import csv
import datetime as dt
import io
import json
import os
import socket
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote

from .net import Client

BASE = "https://www.nseindia.com"
ARCHIVE = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
DEFAULT_SYMBOL = "RELIANCE"
DEFAULT_PLEDGE_SYMBOL = "ADANIENT"
FIXTURE_MAX_ROWS = 20
UNIT_NOT_STATED = "unit not stated"
ACCEPT = {"json": "application/json", "csv": "*/*", "html": "text/html"}


class BudgetExceeded(RuntimeError):
    pass


class Field(NamedTuple):
    name: str
    paths: tuple[str, ...]


class Endpoint(NamedTuple):
    id: str
    kind: str
    fixture: str | None
    required: bool
    save: bool
    fields: tuple[Field, ...] = ()


class Request(NamedTuple):
    endpoint: Endpoint
    url: str
    referer: str | None


def field(name, *paths):
    return Field(name, tuple(paths))


QUOTE_FIELDS = (
    field("last_price", "priceInfo.lastPrice"),
    field("change", "priceInfo.change"),
    field("pct_change", "priceInfo.pChange"),
    field("week_high", "priceInfo.weekHighLow.weekHigh"),
    field("week_low", "priceInfo.weekHighLow.weekLow"),
    field("symbol", "securityInfo.symbol", "info.symbol"),
    field("isin", "securityInfo.isin", "info.isin"),
    field("market_cap", "securityInfo.marketCap", "metadata.marketCap", "priceInfo.marketCap"),
    field("pe", "metadata.pdSymbolPe", "securityInfo.pdSymbolPe", "priceInfo.pdSymbolPe"),
    field("industry", "industryInfo.industry", "info.industry", "metadata.industry"),
)

RESULTS_FIELDS = (
    field("period_end", "resCmpData[].re_to_dt"),
    field("revenue", "resCmpData[].re_net_sale", "resCmpData[].re_total_inc"),
    field("other_income", "resCmpData[].re_oth_inc_new", "resCmpData[].re_oth_inc"),
    field("expenses", "resCmpData[].re_oth_tot_exp"),
    field("net_profit", "resCmpData[].re_net_profit", "resCmpData[].re_proloss_ord_act"),
    field("eps", "resCmpData[].re_basic_eps_for_cont_dic_opr", "resCmpData[].re_dilut_eps_for_cont_dic_opr"),
    field("ebitda", "resCmpData[].re_ebitda"),
    field("filing_link", "resCmpData[].re_filing_link"),
)

FILING_FIELDS = (
    field("period_start", "[].fromDate"),
    field("period_end", "[].toDate"),
    field("consolidated", "[].consolidated"),
    field("audited", "[].audited"),
    field("filed_at", "[].filingDate", "[].broadCastDate"),
    field("xbrl_link", "[].xbrl"),
    field("details_link", "[].resultDetailedDataLink"),
)

ANNOUNCEMENT_FIELDS = (
    field("symbol", "[].symbol", "data[].symbol"),
    field("subject", "[].desc", "data[].desc"),
    field("announced_at", "[].an_dt", "data[].an_dt"),
    field("title", "[].attchmntText", "data[].attchmntText"),
    field("attachment", "[].attchmntFile", "data[].attchmntFile"),
    field("exchange_ref", "[].seq_id", "data[].seq_id", "[].orgid", "data[].orgid"),
    field("industry", "[].smIndustry", "data[].smIndustry"),
)

SHAREHOLDING_FIELDS = (
    field("as_on", "[].date"),
    field("submitted_at", "[].submissionDate", "[].broadcastDate"),
    field("promoter", "[].pr_and_prgrp"),
    field("public", "[].public_val"),
    field("employee_trusts", "[].employeeTrusts"),
    field("fii", "[].fii"),
    field("dii", "[].dii"),
    field("xbrl_link", "[].xbrl"),
)

PLEDGE_FIELDS = (
    field("symbol", "data[].symbol"),
    field("company", "data[].comName"),
    field("shares_held", "data[].totPromoterHolding"),
    field("shares_pledged", "data[].numSharesPledged"),
    field("pledged_pct", "data[].percSharesPledged"),
    field("promoter_pct", "data[].percPromoterHolding"),
    field("promoter_pledged_pct", "data[].percPromoterShares"),
    field("quarter_end", "data[].shp"),
    field("disclosed_at", "data[].broadcastDt"),
)

EQUITY_FIELDS = (
    field("SYMBOL", "SYMBOL"),
    field("NAME OF COMPANY", "NAME OF COMPANY"),
    field("SERIES", "SERIES"),
    field("DATE OF LISTING", "DATE OF LISTING"),
    field("PAID UP VALUE", "PAID UP VALUE"),
    field("MARKET LOT", "MARKET LOT"),
    field("ISIN NUMBER", "ISIN NUMBER"),
    field("FACE VALUE", "FACE VALUE"),
)

ENDPOINTS = (
    Endpoint("prime_home", "html", None, False, False),
    Endpoint("prime_stock", "html", None, False, False),
    Endpoint("quote", "json", "quote.json", True, True, QUOTE_FIELDS),
    Endpoint("results_standalone", "json", "results_standalone.json", True, True, RESULTS_FIELDS),
    Endpoint("results_consolidated", "json", "results_consolidated.json", True, True, RESULTS_FIELDS),
    Endpoint("results_filings", "json", "results_filings.json", True, True, FILING_FIELDS),
    Endpoint("announcements", "json", "announcements.json", True, True, ANNOUNCEMENT_FIELDS),
    Endpoint("announcements_market", "json", "announcements_market.json", False, True, ANNOUNCEMENT_FIELDS),
    Endpoint("shareholding", "json", "shareholding.json", True, True, SHAREHOLDING_FIELDS),
    Endpoint("pledges", "json", "pledges.json", True, True, PLEDGE_FIELDS),
    Endpoint("pledges_market", "json", "pledges_market.json", False, True, PLEDGE_FIELDS),
    Endpoint("equity_list", "csv", "equity_list.csv", True, True, EQUITY_FIELDS),
)

MAX_CALLS = len(ENDPOINTS)

KNOWN_GAPS: set[tuple[str, str]] = {
    ("quote", "fixture"),
    ("results_standalone", "ebitda"),
    ("results_standalone", "filing_link"),
    ("results_consolidated", "ebitda"),
    ("results_consolidated", "filing_link"),
    ("results_filings", "details_link"),
    ("shareholding", "fii"),
    ("shareholding", "dii"),
    ("pledges", "symbol"),
    ("pledges_market", "symbol"),
}


class CallBudget:
    def __init__(self, limit):
        self.limit = limit
        self.count = 0

    def spend(self):
        if self.count >= self.limit:
            raise BudgetExceeded(f"request budget of {self.limit} already spent")
        self.count += 1


def build_requests(symbol=DEFAULT_SYMBOL, pledge_symbol=DEFAULT_PLEDGE_SYMBOL, run_date=None):
    run_date = run_date or dt.date.today()
    symbol = quote(str(symbol).strip().upper(), safe="")
    pledge_symbol = quote(str(pledge_symbol).strip().upper(), safe="")
    stock_page = f"{BASE}/get-quotes/equity?symbol={symbol}"
    start = (run_date - dt.timedelta(days=6)).strftime("%d-%m-%Y")
    end = run_date.strftime("%d-%m-%Y")
    urls = {
        "prime_home": BASE + "/",
        "prime_stock": stock_page,
        "quote": f"{BASE}/api/quote-equity?symbol={symbol}",
        "results_standalone": f"{BASE}/api/results-comparision?symbol={symbol}",
        "results_consolidated": f"{BASE}/api/results-comparision?symbol={symbol}&consolidated=true",
        "results_filings": f"{BASE}/api/corporates-financial-results?index=equities&period=Quarterly&symbol={symbol}",
        "announcements": f"{BASE}/api/corporate-announcements?index=equities&symbol={symbol}",
        "announcements_market": f"{BASE}/api/corporate-announcements?index=equities&from_date={start}&to_date={end}",
        "shareholding": f"{BASE}/api/corporate-share-holdings-master?index=equities&symbol={symbol}",
        "pledges": f"{BASE}/api/corporate-pledgedata?index=equities&symbol={pledge_symbol}",
        "pledges_market": f"{BASE}/api/corporate-pledgedata?index=equities",
        "equity_list": ARCHIVE,
    }
    requests = []
    for endpoint in ENDPOINTS:
        if endpoint.id == "prime_home":
            referer = None
        elif endpoint.id == "prime_stock":
            referer = BASE + "/"
        else:
            referer = stock_page
        requests.append(Request(endpoint, urls[endpoint.id], referer))
    return tuple(requests)


def get_path(obj, path):
    for part in path.split("."):
        if part == "[]":
            if not isinstance(obj, list) or not obj:
                return None
            obj = obj[0]
            continue
        list_key = part.endswith("[]")
        key = part[:-2] if list_key else part
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
        if obj is None:
            return None
        if list_key:
            if not isinstance(obj, list) or not obj:
                return None
            obj = obj[0]
    return obj


def summarise(kind, body):
    if kind == "json":
        if isinstance(body, dict):
            rows = {key: len(value) for key, value in body.items() if isinstance(value, list)}
            return {
                "kind": "json",
                "type": "object",
                "keys": sorted(body.keys()),
                "rows": rows,
                "row_count": max(rows.values(), default=0),
                "header": [],
            }
        if isinstance(body, list):
            return {
                "kind": "json",
                "type": "list",
                "keys": [],
                "rows": {"$": len(body)},
                "row_count": len(body),
                "header": [],
            }
        return {
            "kind": "json",
            "type": type(body).__name__,
            "keys": [],
            "rows": {},
            "row_count": 0,
            "header": [],
        }
    if kind == "csv":
        text = body.decode("utf-8", "replace") if isinstance(body, bytes) else body
        reader = csv.reader(io.StringIO(text))
        try:
            header = [item.strip() for item in next(reader)]
        except StopIteration:
            header = []
        count = sum(1 for _ in reader)
        return {
            "kind": "csv",
            "type": "table",
            "keys": [],
            "rows": {"$": count},
            "row_count": count,
            "header": header,
        }
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)
    return {
        "kind": "html",
        "type": "html",
        "keys": [],
        "rows": {},
        "row_count": None,
        "header": [],
    }


def field_coverage(kind, body, endpoint):
    coverage = []
    if kind == "csv":
        header = summarise("csv", body)["header"]
        for item in endpoint.fields:
            path = item.paths[0]
            coverage.append({"name": item.name, "path": path, "found": path in header})
        return coverage
    for item in endpoint.fields:
        found_path = None
        for path in item.paths:
            if get_path(body, path) is not None:
                found_path = path
                break
        coverage.append(
            {
                "name": item.name,
                "path": found_path or item.paths[0],
                "found": found_path is not None,
            }
        )
    return coverage


def extract_unit(kind, body):
    if kind != "json":
        return UNIT_NOT_STATED
    for path in ("unit", "currency", "unitOfMeasurement", "metadata.unit", "metadata.currency"):
        value = get_path(body, path)
        if value not in (None, ""):
            return str(value)
    return UNIT_NOT_STATED


def trim_for_fixture(data):
    if isinstance(data, list):
        return data[:FIXTURE_MAX_ROWS], [
            {"path": "$", "original_rows": len(data), "saved_rows": min(len(data), FIXTURE_MAX_ROWS)}
        ]
    if isinstance(data, dict):
        trimmed = dict(data)
        lists = []
        for key, value in data.items():
            if isinstance(value, list):
                trimmed[key] = value[:FIXTURE_MAX_ROWS]
                lists.append(
                    {
                        "path": key,
                        "original_rows": len(value),
                        "saved_rows": min(len(value), FIXTURE_MAX_ROWS),
                    }
                )
        return trimmed, lists
    return data, []


def _write_json(path, data):
    payload = (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    path.write_bytes(payload)
    return len(payload)


def parse_body(kind, body):
    if kind == "json":
        return json.loads(body.decode("utf-8"))
    if kind == "csv":
        return body.decode("utf-8", "replace")
    return body.decode("utf-8", "replace")


def run_entries(client, budget, requests, save_dir=None):
    results = []
    for request in requests:
        endpoint = request.endpoint
        started = time.monotonic()
        record = {
            "endpoint": endpoint.id,
            "kind": endpoint.kind,
            "fixture": endpoint.fixture,
            "required": endpoint.required,
            "url": request.url,
            "ok": False,
            "bytes": 0,
            "rows": None,
            "fields": [],
            "unit": UNIT_NOT_STATED,
            "error": None,
            "elapsed_ms": 0,
            "original_bytes": None,
            "saved_bytes": None,
            "lists": [],
        }
        try:
            budget.spend()
            body = client.get(request.url, referer=request.referer, accept=ACCEPT[endpoint.kind])
        except BudgetExceeded:
            raise
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            record["elapsed_ms"] = int((time.monotonic() - started) * 1000)
            results.append(record)
            continue
        record["bytes"] = len(body)
        record["elapsed_ms"] = int((time.monotonic() - started) * 1000)
        try:
            parsed = parse_body(endpoint.kind, body)
        except Exception as exc:
            record["error"] = f"parse {type(exc).__name__}: {exc}"
            results.append(record)
            continue
        record["ok"] = True
        record["shape"] = summarise(endpoint.kind, parsed)
        record["rows"] = record["shape"]["row_count"]
        record["unit"] = extract_unit(endpoint.kind, parsed)
        record["fields"] = field_coverage(endpoint.kind, parsed, endpoint)
        if save_dir is not None and endpoint.save and endpoint.fixture:
            path = Path(save_dir) / endpoint.fixture
            if endpoint.kind == "json":
                trimmed, lists = trim_for_fixture(parsed)
                record["lists"] = lists
                record["original_bytes"] = len(body)
                record["saved_bytes"] = _write_json(path, trimmed)
            elif endpoint.kind == "csv":
                path.write_bytes(body)
                record["original_bytes"] = len(body)
                record["saved_bytes"] = len(body)
                record["lists"] = []
        results.append(record)
    return results


def g1_candidate(results):
    required = [item for item in results if item["required"] and item["kind"] != "html"]
    answered = [item for item in required if item["ok"]]
    if answered and len(answered) == len(required):
        return "PASS"
    if answered:
        return "PARTIAL"
    return "FAIL"


def build_summary(results, symbol, pledge_symbol, capture_source, run_url):
    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "symbol": symbol,
        "pledge_symbol": pledge_symbol,
        "capture_source": capture_source,
        "run_url": run_url,
        "g1_candidate": g1_candidate(results),
        "results": results,
    }


def build_manifest(results, capture_source, run_url):
    captured_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    files = []
    for item in results:
        if not item["fixture"] or item["saved_bytes"] is None:
            continue
        files.append(
            {
                "endpoint": item["endpoint"],
                "fixture": item["fixture"],
                "url": item["url"],
                "captured_at": captured_at,
                "captured_by": capture_source,
                "run_url": run_url,
                "original_bytes": item["original_bytes"],
                "saved_bytes": item["saved_bytes"],
                "rows": item["rows"],
                "lists": item["lists"],
                "unit": item["unit"],
                "fields": item["fields"],
            }
        )
    return {
        "generated_at": captured_at,
        "captured_by": capture_source,
        "run_url": run_url,
        "files": files,
    }


def render_readme(manifest):
    source = manifest["captured_by"]
    if manifest["run_url"]:
        source = f"{source} ({manifest['run_url']})"
    lines = [
        "# NSE stock smoke fixtures",
        "",
        f"Captured by: {source}",
        f"Captured at: {manifest['generated_at']}",
        "",
        "Top-level JSON lists keep the first "
        f"{FIXTURE_MAX_ROWS} rows; the equity CSV is saved in full. "
        "Do not trim a fixture by hand.",
        "",
    ]
    if not manifest["files"]:
        lines.extend(["No fixture was saved: every data call failed.", ""])
        return "\n".join(lines)
    lines.append("| Endpoint | Fixture | Rows | Bytes (original / saved) | Unit |")
    lines.append("| --- | --- | --- | --- | --- |")
    for item in manifest["files"]:
        lines.append(
            f"| `{item['endpoint']}` | `{item['fixture']}` | {item['rows']} | "
            f"{item['original_bytes']} / {item['saved_bytes']} | {item['unit']} |"
        )
    lines.append("")
    lines.append("## Field coverage")
    for item in manifest["files"]:
        lines.append("")
        lines.append(f"### `{item['endpoint']}`")
        for field_item in item["fields"]:
            status = "found" if field_item["found"] else "not in this response"
            lines.append(f"- {field_item['name']}: {status} (`{field_item['path']}`)")
    lines.append("")
    return "\n".join(lines)


def print_table(results):
    print(f"{'endpoint':<24} {'ok':<5} {'bytes':>8} {'rows':>6} {'unit':<18} error")
    for item in results:
        error = item["error"] or ""
        print(
            f"{item['endpoint']:<24} {str(item['ok']):<5} {item['bytes']:>8} "
            f"{str(item['rows']):>6} {item['unit'][:18]:<18} {error}"
        )


@contextmanager
def prefer_ipv4():
    original = socket.getaddrinfo

    def ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
        addresses = original(host, port, family, type, proto, flags)
        ipv4 = [item for item in addresses if item[0] == socket.AF_INET]
        return ipv4 or addresses

    socket.getaddrinfo = ipv4_only
    try:
        yield
    finally:
        socket.getaddrinfo = original


def run_url_from_env():
    run_id = os.environ.get("GITHUB_RUN_ID")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if run_id and repo:
        return f"https://github.com/{repo}/actions/runs/{run_id}"
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Probe the NSE stock endpoints for task 003.")
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL)
    parser.add_argument("--pledge-symbol", default=DEFAULT_PLEDGE_SYMBOL)
    parser.add_argument("--save", metavar="DIR")
    parser.add_argument("--json-out", metavar="FILE")
    parser.add_argument("--capture-source", choices=("local", "github-runner"), default="local")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    requests = build_requests(args.symbol, args.pledge_symbol)
    if args.dry_run:
        for request in requests:
            print(f"{request.endpoint.id}\t{request.url}")
        return 0

    run_url = run_url_from_env() if args.capture_source == "github-runner" else None
    save_dir = Path(args.save) if args.save else None
    if save_dir is not None:
        save_dir.mkdir(parents=True, exist_ok=True)
    client = Client(timeout=30, retries=0)
    budget = CallBudget(MAX_CALLS)
    try:
        with prefer_ipv4():
            results = run_entries(client, budget, requests, save_dir=save_dir)
    except BudgetExceeded as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print_table(results)
    candidate = g1_candidate(results)
    print(f"G1 candidate: {candidate}")

    summary = build_summary(results, args.symbol, args.pledge_symbol, args.capture_source, run_url)
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if save_dir is not None:
        manifest = build_manifest(results, args.capture_source, run_url)
        _write_json(save_dir / "manifest.json", manifest)
        (save_dir / "README.md").write_text(render_readme(manifest), encoding="utf-8")

    required_ok = all(
        item["ok"] for item in results if item["required"] and item["kind"] != "html"
    )
    return 0 if required_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
