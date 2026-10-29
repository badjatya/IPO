"""Quote: no confirmed source — the 2026-10-30 probe found none.

The one deliberate probe (``python3 -m stock_worker.probe``) ran once on
2026-10-30 under its 6-call budget, and no candidate answered:

- ``stock_page_embedded`` — no embedded quote JSON found in the stock page
- ``nextapi`` — **unprobed**: the stock page carries no ``_next/data`` URL, so
  the NextApi route could not be read from it. NSE's ``/api/NextApi/…`` paths
  themselves were **not** tried; the candidate stays unprobed for a later task
- ``trade_info`` — ``HTTPError: HTTP Error 403: Forbidden``
- ``cookie_order`` — ``HTTPError: HTTP Error 403: Forbidden``

The same run's consolidated re-check was ``identical`` (the endpoint still
returns the standalone body), confirming that gap too. Until a working source
is found, ``fetch_quote`` raises ``SourceError`` pointing at this record, and
no ``stock_quotes`` row is ever fabricated and no price is ever estimated. The
candidates and errors are recorded in ``docs/data-sources.md`` § NSE stock
data.
"""

from .errors import SourceError

GAP_MESSAGE = (
    "quote source is not confirmed: the 2026-10-30 probe found no working "
    "candidate (stock_page_embedded: no embedded quote JSON found in the stock "
    "page; nextapi: unprobed, the stock page carries no _next/data URL; "
    "trade_info and cookie_order: HTTP Error 403: Forbidden). See "
    "docs/data-sources.md § NSE stock data."
)


def fetch_quote(session):
    """Raise :class:`SourceError`: the quote source stays unconfirmed.

    ``session`` mirrors the other fetchers' signature but is unused — there is
    no confirmed endpoint to call, and the probe recorded that none of the
    candidates answered. A later task that confirms a working source replaces
    this body with the real fetch.
    """
    raise SourceError(GAP_MESSAGE)