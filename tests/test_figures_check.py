"""Tests for the figures check (ipo_agent/figures_check.py).

Unit tests pin the figure shapes named in the plan: crore vs lakh, million on the
RHP side, "lakh Cr", comma groups, unit-less per-share prices, the half-a-unit
tolerance, ranges (plain and with a unit), ≈/~ approximate figures, whole-word short
units, word numbers, missing figures, and bare table cells that are not candidates.
``TempRepo`` tests cover the key resolution and skip rules; the integration tests run
the check over the repo's own saved analyses (system of record, in git) with no live
calls.
"""

import contextlib
import io
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from support import NoNetworkCase, TempRepo  # noqa: E402

from ipo_agent import figures_check as fc  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def figures(text):
    return [(f.rupees, f.decimals, f.unit_multiplier, f.approximate)
            for f in fc.extract_figures(text)]


class ExtractTests(unittest.TestCase):
    """Extraction: units, commas, ranges, word numbers, ≈/~ markers."""

    def test_comma_grouped(self):
        self.assertEqual(figures("issue ₹30,213 Cr (snapshot)"),
                         [(30213 * 10 ** 7, 0, 10 ** 7, False)])

    def test_lakh_cr_composed_unit(self):
        self.assertEqual(figures("₹10.3 lakh Cr market cap"),
                         [(10.3 * 10 ** 12, 1, 10 ** 12, False)])

    def test_plain_range_is_two_figures(self):
        self.assertEqual(figures("Price band ₹313–330"),
                         [(313.0, 0, 1, False), (330.0, 0, 1, False)])

    def test_range_hyphen_also_two_figures(self):
        self.assertEqual(figures("GMP ₹40-46"),
                         [(40.0, 0, 1, False), (46.0, 0, 1, False)])

    def test_range_with_unit_applies_to_both(self):
        self.assertEqual(figures("₹1,000–1,200 Cr"),
                         [(1000 * 10 ** 7, 0, 10 ** 7, False),
                          (1200 * 10 ** 7, 0, 10 ** 7, False)])

    def test_whole_word_short_unit_is_no_unit(self):
        # "₹20 Listing gain" is ₹20 with no unit, not ₹20 lakh: L matches only
        # as a whole word.
        self.assertEqual(figures("GMP ₹20 Listing gain"),
                         [(20.0, 0, 1, False)])

    def test_word_number(self):
        self.assertEqual(figures("₹two hundred crore"),
                         [(200 * 10 ** 7, 0, 10 ** 7, False)])

    def test_rs_prefix(self):
        self.assertEqual(figures("Rs. 1,119 per share"),
                         [(1119.0, 0, 1, False)])

    def test_approximate_markers(self):
        self.assertTrue(figures("≈₹2,534 Cr")[0][3])
        self.assertTrue(figures("≈ ₹10,765 Cr")[0][3])
        self.assertTrue(figures("~₹852.2 Cr")[0][3])

    def test_trailing_comma_is_punctuation(self):
        # "At ₹693, P/E" — the comma after 693 is punctuation, not part of the number.
        self.assertEqual(figures("At ₹693, P/E is 160x"), [(693.0, 0, 1, False)])
        self.assertTrue(fc.check_one("At ₹693, P/E", "₹ 693.00").found == 1)

    def test_unparseable_words_are_none_not_crash(self):
        self.assertIsNone(fc._parse_number("zillion"))
        self.assertEqual(fc._parse_number("two hundred"), 200.0)


class CheckTests(unittest.TestCase):
    """Matching: found/missing/share/approximate from analysis + RHP strings."""

    def test_crore_finds_lakhs(self):
        c = fc.check_one("₹77.6 Cr", "₹7,756.07 lakhs")
        self.assertEqual((c.found, c.total, c.share, c.missing), (1, 1, 1.0, []))

    def test_million_on_rhp_side(self):
        c = fc.check_one("₹2,830 Cr", "₹28,300.00 million")
        self.assertEqual((c.found, c.total, c.share), (1, 1, 1.0))

    def test_lakh_cr_found(self):
        c = fc.check_one("₹10.3 lakh Cr", "₹10,30,00,000.00 lakh")
        self.assertEqual((c.found, c.total, c.share), (1, 1, 1.0))

    def test_unitless_per_share(self):
        c = fc.check_one("₹1,119", "₹ 1,119.00")
        self.assertEqual((c.found, c.total, c.share), (1, 1, 1.0))

    def test_precision_tolerance_matches_rounded_figures(self):
        self.assertEqual(fc.check_one("₹78 Cr", "₹7,756.07 lakhs").found, 1)
        self.assertEqual(fc.check_one("₹0.5 Cr", "₹46.20 lakhs").found, 1)

    def test_precision_tolerance_rejects_close_but_wrong(self):
        c = fc.check_one("₹1,119", "₹ 1,125.00")
        self.assertEqual((c.found, c.total, c.share), (0, 1, 0.0))

    def test_range_with_unit_found_in_rhp(self):
        c = fc.check_one("₹1,000–1,200 Cr", "₹1,00,000.00 lakh and ₹1,20,000.00 lakh")
        self.assertEqual((c.found, c.total, c.share), (2, 2, 1.0))

    def test_word_number_found(self):
        c = fc.check_one("₹two hundred crore", "₹20,000.00 lakh")
        self.assertEqual((c.found, c.total, c.share), (1, 1, 1.0))

    def test_approximate_excluded_from_share(self):
        c = fc.check_one("Market cap ≈₹2,534 Cr", "₹1,000 Cr")
        self.assertEqual((c.found, c.total, c.share, c.approximate, c.missing),
                         (0, 0, None, 1, []))

    def test_missing_figure_is_reported(self):
        c = fc.check_one("Issue ₹9,999 Cr", "₹77.56 Cr")
        self.assertEqual((c.found, c.total, c.share), (0, 1, 0.0))
        self.assertEqual(c.missing, ["₹9,999 Cr"])

    def test_bare_table_cell_is_not_a_candidate(self):
        rhp = "(₹ in lakhs)\n  Particulars  Amount\n  1,09,558"
        self.assertEqual(fc.rhp_candidates(rhp), [])
        c = fc.check_one("₹1,095.58 Cr", rhp)
        self.assertEqual((c.found, c.total, c.share), (0, 1, 0.0))

    def test_foreign_currency_bare_number_is_not_a_candidate(self):
        self.assertEqual(fc.rhp_candidates("more than USD 1.00 million"), [])
        c = fc.check_one("₹1.00 million", "more than USD 1.00 million")
        self.assertEqual(c.found, 0)

    def test_rs_prefix_matches(self):
        c = fc.check_one("Rs. 1,119 per share", "₹ 1,119.00")
        self.assertEqual(c.found, 1)


class KeyTests(NoNetworkCase):
    """Key resolution, skip rules and the CLI (TempRepo, no real repo)."""

    def test_web_card_skips(self):
        with TempRepo() as t:
            t.analysis("x", "Issue ₹100 Cr")
            t.card("x", {"name": "X", "source": "web"})
            c = fc.check_key(t.root, "x")
            self.assertTrue(c.skipped)
            self.assertIn("web", c.reason)

    def test_missing_rhp_skips_with_reason(self):
        with TempRepo() as t:
            t.analysis("x", "Issue ₹100 Cr")
            t.card("x", {"name": "X", "source": "rhp"})
            c = fc.check_key(t.root, "x")
            self.assertTrue(c.skipped)
            self.assertIn("analysis/rhp/x.txt", c.reason)

    def test_missing_card_still_checks(self):
        with TempRepo() as t:
            t.analysis("x", "Issue ₹100 Cr")
            t.write_text("analysis/rhp/x.txt", "₹10,000.00 lakh")
            c = fc.check_key(t.root, "x")
            self.assertFalse(c.skipped)
            self.assertEqual(c.note, "no card")
            self.assertEqual((c.found, c.total), (1, 1))

    def test_unparseable_card_still_checks(self):
        with TempRepo() as t:
            t.analysis("x", "Issue ₹100 Cr")
            t.write_text("analysis/x.json", "{not json")
            t.write_text("analysis/rhp/x.txt", "₹10,000.00 lakh")
            c = fc.check_key(t.root, "x")
            self.assertFalse(c.skipped)
            self.assertIn("card unreadable", c.note)
            self.assertEqual(c.found, 1)

    def test_main_single_key(self):
        with TempRepo() as t:
            t.analysis("x", "Issue ₹100 Cr")
            t.card("x", {"name": "X", "source": "rhp"})
            t.write_text("analysis/rhp/x.txt", "₹10,000.00 lakh")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = fc.main(["--root", str(t.root), "x"])
            self.assertEqual(code, 0)
            self.assertIn("x: 1/1 ₹ figures found (100%)", out.getvalue())

    def test_main_all_aggregates_and_exits_zero_even_when_nothing_found(self):
        with TempRepo() as t:
            t.analysis("alpha", "Issue ₹100 Cr\nGMP ₹20")
            t.card("alpha", {"name": "A", "source": "rhp"})
            t.write_text("analysis/rhp/alpha.txt", "₹10,000.00 lakh")
            t.analysis("gamma", "Anchor ₹5 Cr")          # nothing in the RHP matches
            t.card("gamma", {"name": "C", "source": "rhp"})
            t.write_text("analysis/rhp/gamma.txt", "₹1.00")
            t.analysis("beta", "Anchor ₹5 Cr")
            t.card("beta", {"name": "B", "source": "web"})
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = fc.main(["--all", "--root", str(t.root)])
            text = out.getvalue()
            self.assertEqual(code, 0)
            self.assertIn("alpha: 1/2 ₹ figures found (50%)", text)
            self.assertIn("not found: ₹20", text)
            self.assertIn("gamma: 0/1 ₹ figures found (0%)", text)
            self.assertIn("beta: skipped (source: web)", text)
            self.assertIn("TOTAL: 1/3 ₹ figures found (33%) "
                          "across 3 analyses (1 skipped)", text)

    def test_no_keys_is_usage_error(self):
        with TempRepo() as t:
            with self.assertRaises(SystemExit) as cm:
                fc.main(["--root", str(t.root)])
            self.assertEqual(cm.exception.code, 2)


class IntegrationTests(NoNetworkCase):
    """The repo's own saved analyses (system of record, in git). Read-only."""

    def test_all_saved_analyses_complete(self):
        keys = sorted(p.stem for p in (ROOT / "analysis").glob("*.md"))
        self.assertGreaterEqual(len(keys), 13)
        checks = [fc.check_key(ROOT, key) for key in keys]
        checked = [c for c in checks if not c.skipped]
        self.assertTrue(checked, "at least one analysis is checked")
        for c in checked:
            self.assertTrue(c.share is None or 0 <= c.share <= 1)
            for m in c.missing:
                self.assertIsInstance(m, str)
                self.assertTrue(m)
        for c in checks:
            self.assertIsInstance(c.reason, str)

    def test_main_all_exits_zero(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = fc.main(["--all"])
        self.assertEqual(code, 0)
        self.assertIn("TOTAL:", out.getvalue())


if __name__ == "__main__":
    unittest.main()
