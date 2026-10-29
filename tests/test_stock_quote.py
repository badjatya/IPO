import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from support import NoNetworkCase  # noqa: E402

from stock_worker.errors import SourceError  # noqa: E402
from stock_worker.quote import GAP_MESSAGE, fetch_quote  # noqa: E402


class QuoteFetchTests(NoNetworkCase):
    def test_fetch_quote_raises_source_error_pointing_at_the_gap(self):
        # The "nothing answered" path of plan step 6b: the 2026-10-30 probe
        # found no working candidate, so fetch_quote raises and the gap is
        # recorded in data-sources.md.
        with self.assertRaises(SourceError) as ctx:
            fetch_quote(None)
        self.assertIn("not confirmed", str(ctx.exception))
        self.assertIn("data-sources.md", str(ctx.exception))

    def test_fetch_quote_makes_no_call_and_touches_no_session_state(self):
        class ExplodingSession:
            def __getattr__(self, name):
                raise AssertionError(f"fetch_quote touched {name!r}")

        with self.assertRaises(SourceError):
            fetch_quote(ExplodingSession())

    def test_gap_message_carries_the_run_and_every_candidate_honestly(self):
        self.assertIn("2026-10-30", GAP_MESSAGE)
        self.assertIn("stock_page_embedded", GAP_MESSAGE)
        self.assertIn("nextapi", GAP_MESSAGE)
        # Honest recording: the NextApi candidate was unprobed — the stock page
        # carried no _next/data URL, so /api/NextApi/... paths were not tried.
        self.assertIn("unprobed", GAP_MESSAGE)
        self.assertIn("trade_info", GAP_MESSAGE)
        self.assertIn("cookie_order", GAP_MESSAGE)


if __name__ == "__main__":
    unittest.main()