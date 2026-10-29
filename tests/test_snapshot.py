import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from support import FakeClient, NoNetworkCase, TempRepo, fixture  # noqa: E402

from ipo_agent import cards, investorgain, nse, sebi, snapshot  # noqa: E402

TODAY = "2026-10-29"
SEBI_PAGE = "https://www.sebi.gov.in/filings/public-issues/oct-2026/acme-industries-123.html"


class PhaseTests(NoNetworkCase):
    def test_every_phase_and_boundary(self):
        self.assertEqual(snapshot.phase({}, TODAY), "announced")
        self.assertEqual(snapshot.phase({"open": "2026-10-30", "close": "2026-11-03"}, TODAY), "upcoming")
        self.assertEqual(snapshot.phase({"open": "2026-10-29", "close": "2026-10-30"}, TODAY), "open")
        self.assertEqual(snapshot.phase({"open": "2026-10-27", "close": "2026-10-29"}, TODAY), "closing_today")
        self.assertEqual(snapshot.phase({"open": "2026-10-20", "close": "2026-10-24", "listing": "2026-11-05"}, TODAY),
                         "awaiting_listing")
        self.assertEqual(snapshot.phase({"open": "2026-10-20", "close": "2026-10-24", "listing": "2026-10-29"}, TODAY),
                         "listing_today")
        self.assertEqual(snapshot.phase({"open": "2026-10-20", "close": "2026-10-24", "listing": "2026-10-28"}, TODAY),
                         "listed")

    def test_closed_issue_without_a_listing_date_is_listed(self):
        self.assertEqual(snapshot.phase({"open": "2026-10-20", "close": "2026-10-24"}, TODAY), "listed")


class NameTests(NoNetworkCase):
    def test_norm_drops_company_suffixes(self):
        self.assertEqual(snapshot.norm("SFC Environmental Technologies Limited"),
                         "sfc environmental technologies")

    def test_slug(self):
        self.assertEqual(snapshot.slug("SFC Environmental Technologies Limited"),
                         "sfc-environmental-technologies")
        self.assertEqual(snapshot.slug(None), "unknown")

    def test_same_company(self):
        self.assertTrue(snapshot.same_company("Acme Industries", "Acme Industries Limited"))
        self.assertTrue(snapshot.same_company("Acme Industries Limited", "Acme Industries"))
        self.assertFalse(snapshot.same_company("Acme Industries", "Beta Corp"))
        self.assertFalse(snapshot.same_company("", "Beta Corp"))

    def test_nse_date(self):
        self.assertEqual(snapshot.nse_date("27-Oct-2026"), "2026-10-27")
        self.assertIsNone(snapshot.nse_date(None))


class BuildTests(NoNetworkCase):
    def setUp(self):
        super().setUp()
        self.repo = TempRepo()
        self.addCleanup(self.repo.cleanup)
        for patcher in (
            mock.patch.object(snapshot, "ROOT", self.repo.root),
            mock.patch.object(cards, "DIR", self.repo.path("analysis")),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def routes(self, **overrides):
        routes = {
            investorgain.GMP_URL: fixture("investorgain_gmp.html"),
            nse.BASE + "/": "<html>home</html>",
            nse.REFERER: "<html>referer</html>",
            nse.BASE + "/api/ipo-current-issue": fixture("nse_current.json"),
            nse.BASE + "/api/all-upcoming-issues?category=ipo": fixture("nse_upcoming.json"),
            nse.BASE + "/api/ipo-detail?symbol=SFCTECH&series=EQ": fixture("nse_detail_SFCTECH.json"),
            nse.BASE + "/api/ipo-detail?symbol=ACME&series=EQ": fixture("nse_detail_ACME.json"),
            nse.BASE + "/api/ipo-detail?symbol=BETA&series=EQ": fixture("nse_detail_BETA.json"),
            sebi.LIST_URL: fixture("sebi_listing.html"),
            SEBI_PAGE: fixture("sebi_rhp_page.html"),
        }
        routes.update(overrides)
        return routes

    def build(self, **overrides):
        fake = FakeClient(self.routes(**overrides))
        with mock.patch.object(snapshot, "Client", return_value=fake):
            return snapshot.build(today=TODAY)

    def by_key(self, snap):
        return {i["key"]: i for i in snap["ipos"]}

    def test_merge_keeps_mainboard_and_drops_sme_and_old_listings(self):
        snap = self.build()
        self.assertEqual(snap["errors"], {})
        self.assertEqual(
            [i["key"] for i in snap["ipos"]],
            ["sfc-environmental-technologies", "acme-industries", "beta-corp", "closed"],
        )
        self.assertNotIn("sme-widgets", self.by_key(snap))
        self.assertNotIn("old-listed", self.by_key(snap))

    def test_investorgain_and_nse_values_are_merged(self):
        sfc = self.by_key(self.build())["sfc-environmental-technologies"]
        self.assertEqual(sfc["phase"], "closing_today")
        self.assertEqual(sfc["nse"]["symbol"], "SFCTECH")
        self.assertEqual(sfc["price_high"], 330.0)
        self.assertEqual(sfc["lot"], 45)
        self.assertEqual(sfc["subscription"]["total"]["times"], 0.15)
        self.assertEqual(sfc["rhp_source"], "nse")
        self.assertTrue(sfc["categories"])
        self.assertIsNotNone(sfc["best_category"])

    def test_zero_bid_subscription_is_dropped(self):
        acme = self.by_key(self.build())["acme-industries"]
        self.assertIsNone(acme["subscription"])
        self.assertEqual(acme["phase"], "upcoming")

    def test_sebi_rhp_fallback(self):
        acme = self.by_key(self.build())["acme-industries"]
        self.assertEqual(acme["rhp_source"], "sebi")
        self.assertEqual(acme["rhp_url"],
                         "https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/acme-rhp.pdf")

    def test_nse_only_row(self):
        beta = self.by_key(self.build())["beta-corp"]
        self.assertEqual(beta["name"], "Beta Corp Limited")
        self.assertEqual(beta["open"], "2026-11-02")
        self.assertIsNone(beta["rhp_url"])

    def test_trends_are_attached(self):
        self.repo.snapshot("2026-10-28T0907", [{
            "key": "sfc-environmental-technologies", "name": "SFC Environmental Technologies",
            "gmp": 5, "gmp_updated": "27-Oct 18:00",
        }])
        sfc = self.by_key(self.build())["sfc-environmental-technologies"]
        self.assertEqual([p["gmp"] for p in sfc["trend"]["gmp"]["points"]], [5, 10])
        self.assertEqual(sfc["trend"]["gmp"]["direction"], "up")

    def test_needs_flags_against_a_temp_analysis_dir(self):
        snap = self.build()
        for ipo in snap["ipos"]:
            self.assertTrue(ipo["needs_analysis"])
            self.assertTrue(ipo["needs_card"])
            self.assertFalse(ipo["needs_anchor_update"])

        self.repo.analysis("sfc-environmental-technologies", "## Anchor book\n\nPending\n")
        self.repo.card("sfc-environmental-technologies", {"source": "rhp", "anchor_grade": "pending"})
        sfc = self.by_key(self.build())["sfc-environmental-technologies"]
        self.assertFalse(sfc["needs_analysis"])
        self.assertFalse(sfc["needs_card"])
        self.assertTrue(sfc["needs_anchor_update"])

        self.repo.analysis("acme-industries", "text")
        self.repo.card("acme-industries", {"source": "web", "anchor_grade": "strong"})
        acme = self.by_key(self.build())["acme-industries"]
        self.assertTrue(acme["needs_card"])

    def test_an_nse_source_error_is_recorded_and_the_build_continues(self):
        snap = self.build(**{nse.BASE + "/api/all-upcoming-issues?category=ipo": ConnectionError("boom")})
        self.assertEqual(snap["errors"], {"nse.upcoming": "ConnectionError('boom')"})
        keys = self.by_key(snap)
        self.assertIn("sfc-environmental-technologies", keys)
        self.assertIn("acme-industries", keys)
        self.assertNotIn("beta-corp", keys)

    def test_a_detail_error_is_recorded_against_the_symbol(self):
        snap = self.build(**{nse.BASE + "/api/ipo-detail?symbol=ACME&series=EQ": ConnectionError("down")})
        self.assertEqual(snap["errors"], {"nse.detail.ACME": "ConnectionError('down')"})
        self.assertIn("acme-industries", self.by_key(snap))

    def test_investorgain_error_falls_back_to_nse(self):
        snap = self.build(**{investorgain.GMP_URL: RuntimeError("offline")})
        self.assertEqual(snap["errors"], {"investorgain": "RuntimeError('offline')"})
        keys = self.by_key(snap)
        self.assertIn("sfc-environmental-technologies", keys)
        self.assertIn("acme-industries", keys)
        self.assertIn("beta-corp", keys)


if __name__ == "__main__":
    unittest.main()
