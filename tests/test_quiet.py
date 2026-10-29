import io
import json
import pathlib
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from support import NoNetworkCase, TempRepo, snapshot  # noqa: E402

from ipo_agent import cards, email_render, quiet  # noqa: E402

TODAY = "2026-10-29"


def ipo(key="acme", **fields):
    base = {
        "key": key,
        "name": "Acme Industries",
        "phase": "announced",
        "open": None,
        "close": None,
        "listing": None,
        "rhp_url": None,
        "needs_analysis": False,
        "needs_card": False,
        "needs_anchor_update": False,
        "trend": None,
        "gmp": 10,
        "price_high": 100,
    }
    base.update(fields)
    return base


class ReasonsTests(NoNetworkCase):
    def setUp(self):
        super().setUp()
        self.repo = TempRepo()
        self.addCleanup(self.repo.cleanup)
        patcher = mock.patch.object(cards, "DIR", self.repo.path("analysis"))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.prev = {"date": TODAY, "session": "AM", "ipos": {}}

    def why(self, ipos, prev=None, entries=None, outcome_errors=None, errors=None):
        snap = snapshot(f"{TODAY}T09:07+05:30", ipos, errors=errors)
        return quiet.reasons(snap, self.prev if prev is None else prev, entries or {}, outcome_errors or {})

    def test_source_errors(self):
        self.assertEqual(self.why([], errors={"investorgain": "offline"}),
                         ["source error: investorgain"])

    def test_outcome_errors(self):
        self.assertEqual(self.why([], outcome_errors={"hd-fire": "no prices"}),
                         ["outcomes: hd-fire — no prices"])

    def test_no_previous_report(self):
        snap = snapshot(f"{TODAY}T09:07+05:30", [])
        self.assertEqual(quiet.reasons(snap, None, {}, {}),
                         ["no previous report to carry calls from"])

    def test_live_phases(self):
        self.assertEqual(self.why([ipo(phase="open", open="2026-10-27", close="2026-10-30")]),
                         ["acme: open"])
        self.assertEqual(self.why([ipo(phase="closing_today", open="2026-10-27", close="2026-10-29")]),
                         ["acme: closing today"])

    def test_needs_analysis_only_with_an_rhp(self):
        self.assertEqual(self.why([ipo(needs_analysis=True, rhp_url="https://x")]),
                         ["acme: needs_analysis (RHP available)"])
        self.assertEqual(self.why([ipo(needs_analysis=True)]), [])

    def test_needs_card_and_anchor_update(self):
        self.assertEqual(self.why([ipo(needs_card=True)]), ["acme: needs_card"])
        self.assertEqual(self.why([ipo(needs_anchor_update=True)]), ["acme: needs_anchor_update"])

    def test_phase_change_since_the_previous_report(self):
        entry = ipo(phase="open", open="2026-10-27", close="2026-10-30")
        prev = {"date": "2026-10-26", "session": "AM", "ipos": {}}
        self.assertEqual(self.why([entry], prev=prev),
                         ["acme: open", "acme: upcoming → open since 2026-10-26 AM"])

    def test_listing_day_is_exempt_from_the_phase_change_reason(self):
        entry = ipo(phase="listing_today", open="2026-10-20", close="2026-10-24", listing=TODAY)
        prev = {"date": "2026-10-28", "session": "PM", "ipos": {}}
        self.assertEqual(self.why([entry], prev=prev), [])

    def test_falling_gmp_for_an_applicable_ipo(self):
        entry = ipo(phase="announced", trend={"gmp": {"direction": "down"}})
        self.assertEqual(self.why([entry]), ["acme: GMP falling"])

    def test_non_positive_gmp_needs_a_call_other_than_avoid(self):
        entry = ipo(phase="announced", gmp=0)
        self.assertEqual(self.why([entry]), ["acme: GMP ≤ 0 but call is None"])
        self.assertEqual(self.why([entry], entries={"acme": {"verdict": "apply"}}),
                         ["acme: GMP ≤ 0 but call is apply"])
        self.assertEqual(self.why([entry], entries={"acme": {"verdict": "avoid"}}), [])

    def test_card_verdict_can_exempt_a_non_positive_gmp(self):
        self.repo.card("acme", {"verdict": "avoid"})
        entry = ipo(phase="announced", gmp=0)
        self.assertEqual(self.why([entry]), [])


class CarryTests(NoNetworkCase):
    def setUp(self):
        super().setUp()
        self.repo = TempRepo()
        self.addCleanup(self.repo.cleanup)
        patcher = mock.patch.object(cards, "DIR", self.repo.path("analysis"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_only_run_fields_are_carried(self):
        prev = {"date": "2026-10-28", "session": "PM",
                "ipos": {"acme": {"verdict": "apply", "verdict_text": "Apply",
                                  "best_category": "Retail", "category_note": "1 lot",
                                  "summary": "not carried"}}}
        self.assertEqual(
            quiet.carry(prev, [ipo()]),
            {"acme": {"verdict": "apply", "verdict_text": "Apply",
                      "best_category": "Retail", "category_note": "1 lot"}},
        )

    def test_relative_words_drop_the_category_note(self):
        prev = {"date": "2026-10-28", "session": "PM",
                "ipos": {"acme": {"category_note": "Closes today"}}}
        self.assertEqual(quiet.carry(prev, [ipo()]), {})

    def test_a_newer_card_clears_the_carried_verdict(self):
        self.repo.card("acme", {"analysed": "2026-10-30", "verdict": "avoid"})
        prev = {"date": "2026-10-28", "session": "PM",
                "ipos": {"acme": {"verdict": "apply", "verdict_text": "Apply",
                                  "best_category": "Retail"}}}
        self.assertEqual(quiet.carry(prev, [ipo()]),
                         {"acme": {"best_category": "Retail"}})

    def test_missing_entry_is_omitted(self):
        prev = {"date": "2026-10-28", "session": "PM", "ipos": {}}
        self.assertEqual(quiet.carry(prev, [ipo()]), {})


class PreviousReportTests(NoNetworkCase):
    def test_latest_report_before_the_same_stem(self):
        with TempRepo() as repo:
            repo.report("2026-10-28-pm", {"date": "2026-10-28"})
            repo.report("2026-10-29-am", {"date": "2026-10-29"})
            with mock.patch.object(quiet, "REPORTS", repo.path("reports")):
                self.assertEqual(quiet.previous_report("2026-10-29-am").name, "2026-10-28-pm.json")
                self.assertEqual(quiet.previous_report("2026-10-29-pm").name, "2026-10-29-am.json")
                self.assertIsNone(quiet.previous_report("2026-10-28-am"))


class HeadlineTests(NoNetworkCase):
    def test_lists_today(self):
        snap = snapshot(f"{TODAY}T09:07+05:30", [ipo(phase="listing_today")])
        self.assertEqual(quiet.headline(snap, []), "No IPO open today · Acme Industries lists today")

    def test_upcoming_tomorrow_and_later(self):
        tomorrow = ipo(key="a", name="Alpha", phase="upcoming", open="2026-10-30")
        later = ipo(key="b", name="Beta", phase="upcoming", open="2026-11-03")
        snap = snapshot(f"{TODAY}T09:07+05:30", [tomorrow, later])
        # Only the next opening date is named.
        self.assertEqual(quiet.headline(snap, []),
                         "No IPO open today · Alpha opens tomorrow")
        self.assertEqual(quiet.headline(snapshot(f"{TODAY}T09:07+05:30", [later]), []),
                         "No IPO open today · Beta opens Tue 03 Nov")

    def test_awaiting_listing(self):
        snap = snapshot(f"{TODAY}T09:07+05:30", [
            ipo(phase="awaiting_listing", listing="2026-11-05"),
        ])
        self.assertEqual(quiet.headline(snap, []), "No IPO open today · Acme Industries lists Thu 05 Nov")

    def test_just_listed(self):
        snap = snapshot(f"{TODAY}T09:07+05:30", [])
        listed = [{"name": "HD Fire", "listing_gain_pct": 23.62}]
        self.assertEqual(quiet.headline(snap, listed), "No IPO open today · HD Fire listed +24%")

    def test_nothing_to_say(self):
        self.assertEqual(quiet.headline(snapshot(f"{TODAY}T09:07+05:30", []), []),
                         "No IPO open today")


class OutcomeNoteTests(NoNetworkCase):
    def test_gain_and_gmp(self):
        self.assertEqual(
            quiet.outcome_note({"name": "HD Fire", "listing_gain_pct": 23.62,
                                "gmp_eve_pct": 22.51, "verdict_text": "Apply"}),
            "HD Fire listed +24% (GMP said +23%); our call: Apply",
        )

    def test_missing_numbers(self):
        self.assertEqual(
            quiet.outcome_note({"name": "Beta", "listing_gain_pct": None,
                                "gmp_eve_pct": None, "verdict": None}),
            "Beta listed; our call: none",
        )


class MainTests(NoNetworkCase):
    def setUp(self):
        super().setUp()
        self.repo = TempRepo()
        self.addCleanup(self.repo.cleanup)
        self.repo.latest(snapshot(f"{TODAY}T09:07+05:30", []))
        self.repo.report("2026-10-28-pm", {"date": "2026-10-28", "session": "PM", "ipos": {}})
        for patcher in (
            mock.patch.object(quiet, "ROOT", self.repo.root),
            mock.patch.object(quiet, "REPORTS", self.repo.path("reports")),
            mock.patch.object(email_render, "ROOT", self.repo.root),
            mock.patch.object(cards, "DIR", self.repo.path("analysis")),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_main(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = quiet.main(argv)
        return code, out.getvalue()

    def test_quiet_check(self):
        code, out = self.run_main(["AM", "--check"])
        self.assertEqual(code, 0)
        self.assertIn("QUIET: calls would carry over from 2026-10-28-pm.json", out)
        self.assertFalse(self.repo.path("reports", "2026-10-29-am.json").exists())

    def test_quiet_run_writes_the_report_and_renders_it(self):
        code, out = self.run_main(["AM", "--no-outcomes"])
        self.assertEqual(code, 0)
        report = json.loads(self.repo.path("reports", "2026-10-29-am.json").read_text())
        self.assertEqual(report["generated"], "quiet")
        self.assertEqual(report["carried_from"], "2026-10-28-pm.json")
        self.assertTrue(any(n.startswith("Quiet run") for n in report["notes"]))
        self.assertTrue(self.repo.path("reports", "2026-10-29-am.html").exists())
        self.assertTrue(self.repo.path("reports", "2026-10-29-am.txt").exists())
        self.assertIn("IPO brief", out)

    def test_no_previous_report_is_not_quiet(self):
        self.repo.path("reports", "2026-10-28-pm.json").unlink()
        code, out = self.run_main(["AM", "--no-outcomes"])
        self.assertEqual(code, 0)
        self.assertIn("NOT QUIET", out)
        self.assertIn("no previous report to carry calls from", out)
        self.assertFalse(self.repo.path("reports", "2026-10-29-am.json").exists())

    def test_already_written_report_is_not_quiet(self):
        self.repo.report("2026-10-29-am", {"generated": "claude"})
        code, out = self.run_main(["AM", "--no-outcomes"])
        self.assertIn("2026-10-29-am.json already written this session", out)
        self.assertEqual(json.loads(self.repo.path("reports", "2026-10-29-am.json").read_text()),
                         {"generated": "claude"})

    def test_outcome_errors_are_reported_through_update(self):
        with mock.patch.object(quiet.outcomes, "update",
                               return_value=([], [], {"hd-fire": "no NSE prices"})):
            code, out = self.run_main(["AM"])
        self.assertIn("outcomes: hd-fire — no NSE prices", out)
        self.assertIn("NOT QUIET", out)

    def test_no_outcomes_skips_update(self):
        with mock.patch.object(quiet.outcomes, "update", side_effect=AssertionError("called")):
            code, out = self.run_main(["AM", "--no-outcomes"])
        self.assertEqual(code, 0)
        self.assertIn("QUIET", out)


if __name__ == "__main__":
    unittest.main()
