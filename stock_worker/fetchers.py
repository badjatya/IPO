"""Orchestration: one shared prime per run, then one fetch per source.

The client is primed **once per run**, not once per source: this is
``ipo_agent/nse.py``'s ``_primed`` once-per-client pattern. The prime is a
single GET of the stock page (``get-quotes/equity?symbol=X``), the HTML page
that sets NSE's session cookie — the same page the quote probe parses.

``fetch_all`` fetches every confirmed source for one symbol (results, including
the filings join; announcements; shareholding; pledges) under that one prime,
catches each source's failure into an ``errors`` list and still returns the
records of the sources that worked — a failing source never stops the others.
The quote source is wired in but unconfirmed: the 2026-10-30 probe found no
working candidate, so ``fetch_quote`` raises ``SourceError`` on every run
without a call, the gap lands in ``errors``, and no ``stock_quotes`` row can
be fabricated until a later task records a working candidate.

Each per-source function takes the shared :class:`Session` and returns the
module's plain records keyed by the ``db.md`` column names. HTTP goes through
``ipo_agent.net.Client`` unchanged (cookie jar, browser headers, gzip,
retries); nothing here re-implements it.
"""

import json
from urllib.parse import quote

from . import announcements, pledges, results, shareholding
from .quote import fetch_quote

BASE = "https://www.nseindia.com"


def stock_page(symbol):
    return f"{BASE}/get-quotes/equity?symbol={quote(str(symbol).strip().upper(), safe='')}"


def results_url(symbol):
    return f"/api/results-comparision?symbol={symbol}"


def filings_url(symbol):
    return (
        "/api/corporates-financial-results?index=equities"
        f"&period=Quarterly&symbol={symbol}"
    )


def announcements_url(symbol):
    return f"/api/corporate-announcements?index=equities&symbol={symbol}"


def shareholding_url(symbol):
    return f"/api/corporate-share-holdings-master?index=equities&symbol={symbol}"


def pledges_url(symbol):
    return f"/api/corporate-pledgedata?index=equities&symbol={symbol}"


def announcements_market_url(run_date=None, days=6):
    """Market-wide announcements window: the run date and ``days`` earlier.

    ``run_date`` is a ``datetime.date``; the format NSE accepts is DD-MM-YYYY.
    """
    import datetime as dt

    run_date = run_date or dt.date.today()
    start = (run_date - dt.timedelta(days=days)).strftime("%d-%m-%Y")
    end = run_date.strftime("%d-%m-%Y")
    return f"/api/corporate-announcements?index=equities&from_date={start}&to_date={end}"


def pledges_market_url():
    return "/api/corporate-pledgedata?index=equities"


class Session:
    """One client per run, primed once (the ``_primed`` pattern from nse.py)."""

    def __init__(self, client, symbol):
        self.client = client
        self.symbol = str(symbol).strip().upper()
        self._primed = False

    def prime(self):
        if self._primed:
            return
        # The stock page sets the session cookie. A failure is ignored exactly
        # as nse.py ignores its prime errors: it may still have set cookies,
        # and if not, the API calls fail into each source's error entry.
        try:
            self.client.get(stock_page(self.symbol), referer=BASE + "/", accept="text/html")
        except Exception:
            pass
        self._primed = True

    def api(self, path):
        self.prime()
        body = self.client.get_text(
            BASE + path, referer=stock_page(self.symbol), accept="application/json"
        )
        return json.loads(body)


def fetch_results(session):
    """Quarterly results records (the comparison rows + the filings join)."""
    comparison = session.api(results_url(session.symbol))
    filings = session.api(filings_url(session.symbol))
    return results.parse_results(comparison, filings)


def fetch_announcements(session, since=None):
    """Announcements records; ``since`` (ISO timestamp) drops older rows in code."""
    return announcements.parse(session.api(announcements_url(session.symbol)), since=since)


def fetch_shareholding(session):
    return shareholding.parse(session.api(shareholding_url(session.symbol)))


def fetch_pledges(session):
    return pledges.parse(session.api(pledges_url(session.symbol)))


def fetch_announcements_market(session, run_date=None):
    """Market-wide announcements: one call with the run date and six days earlier."""
    return announcements.parse(session.api(announcements_market_url(run_date)))


def fetch_pledges_market(session):
    return pledges.parse(session.api(pledges_market_url()))


def fetch_all(client, symbol, since=None):
    """Every source for one symbol, under one shared prime.

    Returns ``{"records": {"results": [...], "announcements": [...],
    "shareholding": [...], "pledges": [...]}, "errors":
    [{"source": ..., "error": ...}]}`` — a failing source lands in ``errors``
    and never stops the others. ``quote`` is wired in but unconfirmed (probe
    2026-10-30): ``fetch_quote`` raises ``SourceError`` without a call, so
    every run reports it in ``errors`` and ``records`` has no ``quote`` entry.
    Call count per run: 1 prime + 2 (results: comparison and filings) +
    1 announcements + 1 shareholding + 1 pledges — quote adds none.
    """
    session = Session(client, symbol)
    sources = (
        ("results", lambda: fetch_results(session)),
        ("announcements", lambda: fetch_announcements(session, since=since)),
        ("shareholding", lambda: fetch_shareholding(session)),
        ("pledges", lambda: fetch_pledges(session)),
        ("quote", lambda: fetch_quote(session)),
    )
    records = {}
    errors = []
    for name, fetch in sources:
        try:
            records[name] = fetch()
        except Exception as exc:
            errors.append({"source": name, "error": f"{type(exc).__name__}: {exc}"})
    return {"records": records, "errors": errors}


def plan_calls(symbol, run_date=None):
    """(source, url) pairs the per-symbol run makes, in call order (--dry-run).

    ``quote`` lists no URL: while the quote source stays unconfirmed (probe
    2026-10-30), ``fetch_quote`` raises ``SourceError`` without a call.
    """
    symbol = str(symbol).strip().upper()
    return (
        ("prime", stock_page(symbol)),
        ("results", BASE + results_url(symbol)),
        ("results_filings", BASE + filings_url(symbol)),
        ("announcements", BASE + announcements_url(symbol)),
        ("shareholding", BASE + shareholding_url(symbol)),
        ("pledges", BASE + pledges_url(symbol)),
        ("quote", "(no call: quote source unconfirmed — see data-sources.md)"),
    )