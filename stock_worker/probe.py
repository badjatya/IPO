"""Task 014's one deliberate live probe: find a working NSE quote source.

Run once by the human after the build — ``python3 -m stock_worker.probe`` —
under a hard call budget (``MAX_CALLS = 6``: 1 prime + up to 3 candidate
fetches + 2 re-checks: standalone and consolidated), stopping at the first
working candidate. It tries, in fixed order:

1. ``stock_page_embedded`` — the quote JSON embedded in the stock page
   (``get-quotes/equity?symbol=X``, the page that primed the run). Parses the
   prime's own body; no extra fetch.
2. ``nextapi`` — the ``_next/data/<buildId>/…`` quote route the roadmap names.
   Its exact URL is read from the prime page's HTML at run time; if the page
   carries no such URL, the candidate is recorded as unprobed with that reason.
3. ``trade_info`` — ``/api/quote-equity?symbol=X&section=trade_info``.
4. ``cookie_order`` — ``/api/quote-equity?symbol=X`` with the stock page primed.

The same run fetches ``results-comparision?symbol=X`` and its
``…&consolidated=true`` variant back to back under the same prime and records
``identical`` or ``distinct`` from that pair only — the committed fixtures are
never consulted for this comparison.

When a quote source answers, the probe saves ``quote.json`` (top-level lists
trimmed to 20 rows) and upserts its ``manifest.json`` entry — the **only** two
files it writes; 003's fixtures and README are never touched. ``--dry-run``
prints the plan and makes no network call. No estimate is ever made: if no
candidate answers, the quote source stays "not confirmed" and the outcome (the
table plus ``quote source:`` line) is pasted back for step 6b.
"""

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

from ipo_agent.net import Client

from .util import get_path

BASE = "https://www.nseindia.com"
DEFAULT_SYMBOL = "RELIANCE"
DEFAULT_SAVE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "nse_stock"
FIXTURE_MAX_ROWS = 20
MAX_CALLS = 6  # 1 prime + up to 3 candidate fetches + 2 re-checks (standalone, consolidated)

# The fixed candidate order. ``url`` is None for the embedded candidate (it
# parses the prime's own body), "from-stock-page" for the NextApi route (read
# from the prime HTML at run time), else the URL pattern to fetch.
CANDIDATES = (
    ("stock_page_embedded", None),
    ("nextapi", "from-stock-page"),
    ("trade_info", f"{BASE}/api/quote-equity?symbol={{symbol}}&section=trade_info"),
    ("cookie_order", f"{BASE}/api/quote-equity?symbol={{symbol}}"),
)


class BudgetExceeded(RuntimeError):
    pass


class CallBudget:
    def __init__(self, limit):
        self.limit = limit
        self.count = 0

    def spend(self):
        if self.count >= self.limit:
            raise BudgetExceeded(f"request budget of {self.limit} already spent")
        self.count += 1


def stock_page(symbol):
    return f"{BASE}/get-quotes/equity?symbol={quote(str(symbol).strip().upper(), safe='')}"


def consolidated_url(symbol):
    return f"{BASE}/api/results-comparision?symbol={symbol}&consolidated=true"


def standalone_url(symbol):
    return f"{BASE}/api/results-comparision?symbol={symbol}"


def trim_for_fixture(data):
    if isinstance(data, list):
        return data[:FIXTURE_MAX_ROWS]
    if isinstance(data, dict):
        return {
            key: (value[:FIXTURE_MAX_ROWS] if isinstance(value, list) else value)
            for key, value in data.items()
        }
    return data


_NEXT_DATA_SCRIPT_RE = re.compile(
    r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', re.S
)
_SCRIPT_RE = re.compile(r"<script[^>]*>(.*?)</script>", re.S)
_NEXT_DATA_URL_RE = re.compile(r"/_next/data/[^\"'\s\\]+")


def _find_quote_dict(obj):
    if isinstance(obj, dict):
        if isinstance(obj.get("priceInfo"), dict) and "lastPrice" in obj["priceInfo"]:
            return obj
        for value in obj.values():
            found = _find_quote_dict(value)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_quote_dict(item)
            if found is not None:
                return found
    return None


def find_quote_payload(html):
    """Best-effort: the quote JSON embedded in the stock page (candidate 1).

    Tries the ``__NEXT_DATA__`` script, then any script chunk that mentions
    ``priceInfo``, for the first dict carrying ``priceInfo.lastPrice``.
    """
    chunks = list(_NEXT_DATA_SCRIPT_RE.findall(html))
    if not chunks:
        chunks = [
            chunk for chunk in _SCRIPT_RE.findall(html) if '"priceInfo"' in chunk
        ]
    for chunk in chunks:
        try:
            data = json.loads(chunk)
        except ValueError:
            continue
        payload = _find_quote_dict(data)
        if payload is not None:
            return payload
    return None


def find_next_data_url(html):
    """The first ``/_next/data/…`` URL in the stock page (candidate 2).

    Prefers a route whose path mentions ``quote``; ``None`` when the page
    carries no such URL (recorded as unprobed, not guessed).
    """
    urls = sorted(set(_NEXT_DATA_URL_RE.findall(html)))
    for url in urls:
        if "quote" in url.lower():
            return url
    return urls[0] if urls else None


def is_quote_payload(payload):
    return get_path(payload, "priceInfo.lastPrice") is not None


def _full_url(url):
    return url if url.startswith("http") else BASE + url


def _try_candidate(candidate_id, url, symbol, prime_html, client, budget):
    """Returns (payload, source) or (None, error); never estimated."""
    if candidate_id == "stock_page_embedded":
        payload = find_quote_payload(prime_html)
        if payload is None:
            return None, "no embedded quote JSON found in the stock page"
        return payload, "prime page (get-quotes/equity)"
    if candidate_id == "nextapi":
        route = find_next_data_url(prime_html)
        if route is None:
            return None, "unprobed: the stock page carries no _next/data URL"
        budget.spend()
        body = client.get(_full_url(route), referer=stock_page(symbol), accept="application/json")
        payload, error = _parse_candidate_body(body)
        if error is not None:
            return None, f"{error} ({_full_url(route)})"
        return payload, f"nextapi route {route}"
    budget.spend()
    target = url.format(symbol=symbol)
    body = client.get(
        _full_url(target),
        referer=stock_page(symbol),
        accept="application/json",
    )
    payload, error = _parse_candidate_body(body)
    if error is not None:
        return None, f"{error} ({target})"
    return payload, target


def _parse_candidate_body(body):
    """The candidate's body as (payload, error); ``payload`` is a dict only
    when the body is JSON with ``priceInfo.lastPrice``, else ``None`` with the
    reason as ``error``."""
    try:
        payload = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
    except ValueError as exc:
        return None, f"response is not JSON: {exc}"
    if not is_quote_payload(payload):
        return None, "response has no priceInfo.lastPrice"
    return payload, None


def run(client, symbol, save_dir, budget):
    """One budgeted run: prime, candidates in order, consolidated re-check.

    Writes ``quote.json`` + its ``manifest.json`` entry only when a candidate
    answers, and only into ``save_dir``.
    """
    outcome = {
        "symbol": symbol,
        "candidates": [],
        "quote_source": None,
        "quote_url": None,
        "quote_payload": None,
        "consolidated": {"result": "not run", "note": ""},
    }
    budget.spend()  # the shared prime
    prime_body = client.get(stock_page(symbol), referer=BASE + "/", accept="text/html")
    prime_html = (
        prime_body.decode("utf-8", "replace") if isinstance(prime_body, bytes) else prime_body
    )

    for candidate_id, url in CANDIDATES:
        entry = {"id": candidate_id, "ok": False, "source": None, "error": None}
        try:
            payload, source = _try_candidate(
                candidate_id, url, symbol, prime_html, client, budget
            )
        except BudgetExceeded:
            raise
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
            outcome["candidates"].append(entry)
            continue
        if payload is None:
            entry["error"] = source
            outcome["candidates"].append(entry)
            continue
        entry["ok"] = True
        entry["source"] = source
        outcome["candidates"].append(entry)
        outcome["quote_source"] = candidate_id
        outcome["quote_url"] = source
        outcome["quote_payload"] = payload
        break

    # Consolidated re-check: standalone and consolidated bodies fetched back to
    # back under the same prime; identical/distinct is recorded only from that
    # pair (the committed fixtures are read-only and never consulted here).
    budget.spend()
    try:
        body = client.get(
            standalone_url(symbol), referer=stock_page(symbol), accept="application/json"
        )
        standalone = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
    except Exception as exc:
        outcome["consolidated"] = {
            "result": "failed",
            "note": f"standalone fetch: {type(exc).__name__}: {exc}",
        }
    else:
        budget.spend()
        try:
            body = client.get(
                consolidated_url(symbol),
                referer=stock_page(symbol),
                accept="application/json",
            )
            fetched = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
        except Exception as exc:
            outcome["consolidated"] = {
                "result": "failed",
                "note": f"consolidated fetch: {type(exc).__name__}: {exc}",
            }
        else:
            if fetched == standalone:
                outcome["consolidated"] = {
                    "result": "identical",
                    "note": "the endpoint still returns the standalone body",
                }
            else:
                outcome["consolidated"] = {
                    "result": "distinct",
                    "note": "a distinct consolidated body answered (parsing it is 6b/016's job)",
                }

    if outcome["quote_payload"] is not None and save_dir is not None:
        _save_quote_fixture(save_dir, outcome, symbol)
    return outcome


def _save_quote_fixture(save_dir, outcome, symbol):
    save_dir.mkdir(parents=True, exist_ok=True)
    payload = trim_for_fixture(outcome["quote_payload"])
    (save_dir / "quote.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    captured_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    lists = []
    if isinstance(payload, dict):
        lists = [
            {"path": key, "rows": len(value)}
            for key, value in payload.items()
            if isinstance(value, list)
        ]
    elif isinstance(payload, list):
        lists = [{"path": "$", "rows": len(payload)}]
    entry = {
        "endpoint": "quote",
        "fixture": "quote.json",
        "candidate": outcome["quote_source"],
        "url": outcome["quote_url"],
        "captured_at": captured_at,
        "captured_by": "local",
        "run_url": None,
        "rows": None,
        "lists": lists,
        "unit": "not stated",
    }
    manifest_path = save_dir / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except ValueError:
            manifest = {}
    else:
        manifest = {}
    manifest.setdefault("generated_at", captured_at)
    manifest.setdefault("captured_by", "local")
    manifest.setdefault("run_url", None)
    files = manifest.setdefault("files", [])
    files[:] = [item for item in files if item.get("fixture") != "quote.json"]
    files.append(entry)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def print_table(outcome):
    print(f"{'candidate':<20} {'ok':<10} source / error")
    for entry in outcome["candidates"]:
        detail = entry["source"] or entry["error"] or ""
        print(f"{entry['id']:<20} {str(entry['ok']):<10} {detail}")


def dry_run_lines(symbol):
    lines = [f"prime\t{stock_page(symbol)}"]
    for candidate_id, url in CANDIDATES:
        if url is None:
            lines.append(f"{candidate_id}\t(parses the prime page's own body)")
        elif url == "from-stock-page":
            lines.append(f"{candidate_id}\t(_next/data/<buildId> route read from the prime page)")
        else:
            lines.append(f"{candidate_id}\t{url.format(symbol=symbol)}")
    lines.append(f"standalone re-check\t{standalone_url(symbol)}")
    lines.append(f"consolidated re-check\t{consolidated_url(symbol)}")
    lines.append(f"max calls: {MAX_CALLS} (1 prime + up to 3 candidate fetches + 2 re-checks)")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Task 014's one deliberate probe: find a working NSE quote source."
    )
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL)
    parser.add_argument(
        "--save",
        default=None,
        metavar="DIR",
        help=f"fixture dir for quote.json (default: {DEFAULT_SAVE})",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.dry_run:
        for line in dry_run_lines(args.symbol):
            print(line)
        return 0

    save_dir = Path(args.save) if args.save else DEFAULT_SAVE
    client = Client(timeout=30, retries=0)
    budget = CallBudget(MAX_CALLS)
    try:
        outcome = run(client, args.symbol, save_dir, budget)
    except BudgetExceeded as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print_table(outcome)
    sourced = outcome["quote_source"]
    print(f"quote source: {sourced if sourced else 'none (see table errors)'}")
    consolidated = outcome["consolidated"]
    note = f" ({consolidated['note']})" if consolidated["note"] else ""
    print(f"consolidated re-check: {consolidated['result']}{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())