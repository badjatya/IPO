import io
import json
import pathlib
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from support import ROOT, NoNetworkCase, TempRepo, snapshot  # noqa: E402

from ipo_agent import cards, email_render  # noqa: E402

TODAY = "2026-10-29"
CATEGORIES = [
    {"category": "retail", "label": "Retail", "min_lots": 1, "min_shares": 10,
     "min_amount": 1000, "odds_text": "≥1 in 2"},
    {"category": "snii", "label": "Small HNI (sNII)", "min_lots": 21, "min_shares": 210,
     "min_amount": 21000, "odds_text": "full"},
    {"category": "bnii", "label": "Big HNI (bNII)", "min_lots": 101, "min_shares": 1010,
     "min_amount": 101000, "odds_text": "n/a"},
]


def ipo(key="acme", name="Acme Industries", phase="open", **fields):
    base = {
        "key": key, "name": name, "phase": phase,
        "open": "2026-10-27", "close": "2026-10-30", "listing": "2026-11-03",
        "price_high": 100.0, "lot": 10, "size_cr": 50.0, "pe": 12.5,
        "gmp": 10.0, "gmp_pct": 10.0, "nse": {"price_low": 95.0},
        "categories": CATEGORIES, "best_category": "retail",
        "subscription": None, "trend": None, "anchor_done": False,
    }
    base.update(fields)
    return base


def rep_entry():
    return {
        "verdict": "apply", "verdict_text": "Apply", "best_category": "Retail",
        "category_note": "1 lot per PAN", "summary": "Makes widgets.",
        "positives": ["Cheap"], "red_flags": ["Concentration"],
        "anchor": "Anchors", "anchor_grade": "strong",
    }


def report(ipos=None):
    return {"date": TODAY, "session": "AM", "headline": "Headline line",
            "ipos": ipos if ipos is not None else {"acme": rep_entry()}, "notes": ["A note"]}


class MergedTests(NoNetworkCase):
    def setUp(self):
        super().setUp()
        self.repo = TempRepo()
        self.addCleanup(self.repo.cleanup)
        patcher = mock.patch.object(cards, "DIR", self.repo.path("analysis"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_report_fields_override_the_card(self):
        self.repo.card("acme", {"verdict": "avoid", "verdict_text": "Avoid", "summary": "card summary"})
        merged = email_render.merged(report(), [ipo()])
        self.assertEqual(merged["acme"]["verdict"], "apply")
        self.assertEqual(merged["acme"]["summary"], "Makes widgets.")

    def test_card_fields_remain_when_the_report_omits_them(self):
        self.repo.card("acme", {"verdict": "avoid", "summary": "card summary"})
        entry = {k: v for k, v in rep_entry().items() if k != "summary"}
        merged = email_render.merged(report(ipos={"acme": entry}), [ipo()])
        self.assertEqual(merged["acme"]["summary"], "card summary")

    def test_card_only_entry_is_included(self):
        self.repo.card("acme", {"verdict": "apply", "summary": "card summary"})
        merged = email_render.merged(report(ipos={}), [ipo()])
        self.assertEqual(merged["acme"]["summary"], "card summary")

    def test_no_card_and_no_entry_is_omitted(self):
        self.assertEqual(email_render.merged(report(ipos={}), [ipo()]), {})


class RenderTests(NoNetworkCase):
    def setUp(self):
        super().setUp()
        self.repo = TempRepo()
        self.addCleanup(self.repo.cleanup)
        patcher = mock.patch.object(cards, "DIR", self.repo.path("analysis"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_text_has_names_labels_odds_and_disclaimer(self):
        text = email_render.render_text(report(), snapshot(f"{TODAY}T09:07+05:30", [ipo()]))
        self.assertIn("IPO BRIEF · AM · Thu 29 Oct 2026", text)
        self.assertIn("Acme Industries", text)
        self.assertIn("Apply", text)
        self.assertIn("Where to apply", text)
        self.assertIn("≥1 in 2", text)
        self.assertIn("not investment advice", text)
        self.assertIn("GMP", text)

    def test_html_has_labels_odds_and_disclaimer(self):
        page = email_render.render_html(report(), snapshot(f"{TODAY}T09:07+05:30", [ipo()]))
        self.assertIn("Acme Industries", page)
        self.assertIn("Apply", page)
        self.assertIn("Open · closes Fri 30 Oct", page)
        self.assertIn("≥1 in 2", page)
        self.assertIn("not investment advice", page)
        self.assertIn("Headline line", page)

    def test_html_escapes_names_and_summaries(self):
        page = email_render.render_html(
            report(ipos={"acme": {**rep_entry(), "summary": "<script>x</script>"}}),
            snapshot(f"{TODAY}T09:07+05:30", [ipo(name="<b>Acme</b>")]),
        )
        self.assertIn("&lt;b&gt;Acme&lt;/b&gt;", page)
        self.assertIn("&lt;script&gt;x&lt;/script&gt;", page)
        self.assertNotIn("<b>Acme</b>", page)

    def test_phase_labels(self):
        cases = [
            ({"phase": "announced"}, "Announced"),
            ({"phase": "closing_today", "close": TODAY}, "Closes today"),
            ({"phase": "upcoming", "open": "2026-10-30"}, "Opens tomorrow"),
            ({"phase": "upcoming", "open": "2026-11-03"}, "Opens Tue 03 Nov"),
            ({"phase": "awaiting_listing", "listing": "2026-11-05"}, "Lists Thu 05 Nov"),
            ({"phase": "listing_today", "listing": TODAY}, "Lists today"),
        ]
        for fields, expected in cases:
            self.assertEqual(email_render.phase_label({**ipo(), **fields}, TODAY), expected)

    def test_best_label_understands_card_names(self):
        self.assertEqual(email_render.best_label(ipo(best_category=None), {"best_category": "Big HNI"}), "Big HNI")

    def test_provenance_fields_do_not_change_the_output(self):
        # ROUTINE.md "Provenance": reports carry ai_model, ai_prompt_version and ai_written_at
        # at the top level. The renderers read only known keys, so a report with the fields
        # must render byte-identically to the same report without them.
        plain = report()
        with_fields = {**report(), "ai_model": "claude-sonnet-5-5", "ai_prompt_version": "1",
                       "ai_written_at": "2026-10-29T05:31:02Z"}
        snap = snapshot(f"{TODAY}T09:07+05:30", [ipo()])
        self.assertEqual(email_render.render_html(with_fields, snap),
                         email_render.render_html(plain, snap))
        self.assertEqual(email_render.render_text(with_fields, snap),
                         email_render.render_text(plain, snap))
        self.assertEqual(email_render.subject(with_fields, snap["ipos"]),
                         email_render.subject(plain, snap["ipos"]))

    def test_quiet_shaped_report_renders(self):
        # quiet.py writes "generated": "quiet" with no provenance fields (code-written,
        # not AI-written); such a report must still render.
        rep = {**report(), "generated": "quiet", "carried_from": "2026-10-29-am"}
        snap = snapshot(f"{TODAY}T09:07+05:30", [ipo()])
        page = email_render.render_html(rep, snap)
        text = email_render.render_text(rep, snap)
        self.assertIn("not investment advice", page)
        self.assertIn("not investment advice", text)
        self.assertIn("Acme Industries", page)


class SubjectTests(NoNetworkCase):
    def test_counts_open_upcoming_and_closing(self):
        ipos = [
            ipo(key="a", name="Alpha", phase="open"),
            ipo(key="b", name="Beta", phase="closing_today", close=TODAY),
            ipo(key="c", name="Gamma", phase="upcoming", open="2026-11-03"),
        ]
        self.assertEqual(
            email_render.subject(report(ipos={}), ipos),
            "IPO brief Thu 29 Oct AM: 2 open, 1 upcoming · CLOSING TODAY: Beta",
        )

    def test_no_closing(self):
        self.assertEqual(email_render.subject(report(ipos={}), [ipo(phase="open")]),
                         "IPO brief Thu 29 Oct AM: 1 open, 0 upcoming")


class MainTests(NoNetworkCase):
    def setUp(self):
        super().setUp()
        self.repo = TempRepo()
        self.addCleanup(self.repo.cleanup)
        snap = snapshot(f"{TODAY}T09:07+05:30", [ipo()])
        self.repo.latest(snap)
        self.report_path = self.repo.report("2026-10-29-am", report())
        for patcher in (
            mock.patch.object(email_render, "ROOT", self.repo.root),
            mock.patch.object(cards, "DIR", self.repo.path("analysis")),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_writes_html_and_text_beside_the_report_in_a_temp_root(self):
        out = io.StringIO()
        with redirect_stdout(out):
            email_render.main([str(self.report_path)])
        self.assertTrue(self.repo.path("reports", "2026-10-29-am.html").exists())
        self.assertTrue(self.repo.path("reports", "2026-10-29-am.txt").exists())
        self.assertIn("IPO brief Thu 29 Oct AM", out.getvalue())


class SavedFileSmokeTests(NoNetworkCase):
    """Read-only: call the render functions directly, never ``main``."""

    def test_the_saved_am_report_renders_against_its_own_snapshot(self):
        rep = json.loads((ROOT / "reports" / "2026-10-29-am.json").read_text())
        snap = json.loads((ROOT / "data" / "snapshots" / "2026-10-29T0907.json").read_text())
        html_page = email_render.render_html(rep, snap)
        text_page = email_render.render_text(rep, snap)
        subject = email_render.subject(rep, snap["ipos"])
        for ipo_entry in snap["ipos"]:
            self.assertIn(ipo_entry["name"], html_page)
            self.assertIn(ipo_entry["name"], text_page)
        self.assertIn("not investment advice", html_page)
        self.assertIn("not investment advice", text_page)
        self.assertIn("Avoid", html_page)
        self.assertEqual(
            subject,
            "IPO brief Thu 29 Oct AM: 4 open, 0 upcoming · CLOSING TODAY: "
            "SFC Environmental Technologies, BLS Polymers",
        )


if __name__ == "__main__":
    unittest.main()
