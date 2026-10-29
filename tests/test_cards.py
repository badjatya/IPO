import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from support import NoNetworkCase, TempRepo  # noqa: E402

from ipo_agent import cards  # noqa: E402


class CardTests(NoNetworkCase):
    def setUp(self):
        super().setUp()
        self.repo = TempRepo()
        self.addCleanup(self.repo.cleanup)
        patcher = mock.patch.object(cards, "DIR", self.repo.path("analysis"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_path_is_under_the_analysis_dir(self):
        self.assertEqual(cards.path("acme"), self.repo.path("analysis", "acme.json"))

    def test_load_missing_is_none(self):
        self.assertIsNone(cards.load("acme"))

    def test_load_reads_the_card(self):
        self.repo.card("acme", {"verdict": "apply", "source": "rhp"})
        self.assertEqual(cards.load("acme"), {"verdict": "apply", "source": "rhp"})

    def test_needs_card_without_a_card(self):
        self.assertTrue(cards.needs_card("acme"))

    def test_web_stub_without_an_analysis_is_fine(self):
        self.repo.card("acme", {"source": "web"})
        self.assertFalse(cards.needs_card("acme"))

    def test_web_stub_with_an_analysis_needs_refreshing(self):
        self.repo.card("acme", {"source": "web"})
        self.repo.analysis("acme", "## Anchor book\n\nPending\n")
        self.assertTrue(cards.needs_card("acme"))

    def test_rhp_card_with_an_analysis_is_fine(self):
        self.repo.card("acme", {"source": "rhp"})
        self.repo.analysis("acme", "## Anchor book\n\nPending\n")
        self.assertFalse(cards.needs_card("acme"))

    def test_card_with_an_unknown_source_and_an_analysis_needs_refreshing(self):
        self.repo.card("acme", {})
        self.repo.analysis("acme", "text")
        self.assertTrue(cards.needs_card("acme"))


if __name__ == "__main__":
    unittest.main()
