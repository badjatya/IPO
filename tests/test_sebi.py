import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from support import FakeClient, NoNetworkCase, fixture  # noqa: E402

from ipo_agent import sebi  # noqa: E402


class ListingTests(NoNetworkCase):
    def test_normal_row_is_kept_and_corrigendum_addendum_and_no_link_rows_are_skipped(self):
        client = FakeClient({sebi.LIST_URL: fixture("sebi_listing.html")})
        rows = sebi.listing(client)
        self.assertEqual(rows, [(
            "Oct 25, 2026",
            "Acme Industries Limited",
            "https://www.sebi.gov.in/filings/public-issues/oct-2026/acme-industries-123.html",
        )])

    def test_title_splits_on_hyphen_and_en_dash(self):
        page = (
            '<table>'
            '<tr><td>Oct 26, 2026 Hyphen Co Limited - RHP <a href="https://www.sebi.gov.in/filings/public-issues/h.html">x</a></td></tr>'
            '<tr><td>Oct 27, 2026 En Dash Co Limited \u2013 RHP <a href="https://www.sebi.gov.in/filings/public-issues/e.html">x</a></td></tr>'
            '</table>'
        )
        rows = sebi.listing(FakeClient({sebi.LIST_URL: page}))
        self.assertEqual([r[1] for r in rows], ["Hyphen Co Limited", "En Dash Co Limited"])

    def test_points_class_tail_is_stripped(self):
        page = (
            '<table><tr><td>Oct 26, 2026 Points Co Limited RHP " class="points">1.2 MB '
            '<a href="https://www.sebi.gov.in/filings/public-issues/p.html">x</a></td></tr></table>'
        )
        rows = sebi.listing(FakeClient({sebi.LIST_URL: page}))
        self.assertEqual(rows[0][1], "Points Co Limited RHP")

    def test_row_without_a_date_keeps_the_title(self):
        page = (
            '<table><tr><td>Acme Industries Limited - RHP '
            '<a href="https://www.sebi.gov.in/filings/public-issues/a.html">x</a></td></tr></table>'
        )
        rows = sebi.listing(FakeClient({sebi.LIST_URL: page}))
        self.assertEqual(rows[0][0], "")
        self.assertEqual(rows[0][1], "Acme Industries Limited")


class PdfUrlTests(NoNetworkCase):
    def test_file_parameter_shape(self):
        client = FakeClient({"https://www.sebi.gov.in/filings/public-issues/oct-2026/acme-industries-123.html":
                             fixture("sebi_rhp_page.html")})
        self.assertEqual(
            sebi.pdf_url(client, "https://www.sebi.gov.in/filings/public-issues/oct-2026/acme-industries-123.html"),
            "https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/acme-rhp.pdf",
        )

    def test_generic_attachdocs_link(self):
        client = FakeClient({"https://www.sebi.gov.in/filings/public-issues/generic.html":
                             fixture("sebi_rhp_page_generic.html")})
        self.assertEqual(
            sebi.pdf_url(client, "https://www.sebi.gov.in/filings/public-issues/generic.html"),
            "https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/acme-rhp-generic.pdf",
        )

    def test_no_pdf_link_returns_none(self):
        client = FakeClient({"https://www.sebi.gov.in/filings/public-issues/none.html": "<html>none</html>"})
        self.assertIsNone(sebi.pdf_url(client, "https://www.sebi.gov.in/filings/public-issues/none.html"))


if __name__ == "__main__":
    unittest.main()
