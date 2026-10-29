"""Errors the stock fetchers raise.

``FetchError`` is every source failure the orchestrator catches. ``SourceError``
is a source that is not available at all (for example the quote source while it
stays an unconfirmed gap): a caller can tell "this source answered with a
failure" from "this source is not implemented/confirmed yet".
"""


class FetchError(Exception):
    """A source's request or parse failed."""


class SourceError(FetchError):
    """A source is not available (no confirmed endpoint, still a gap)."""