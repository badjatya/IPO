"""Tests for guard.py. Run: python3 -m unittest discover -s .claude/hooks"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import guard  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
GUARD = Path(__file__).with_name("guard.py")


def run_hook(mode, event, project_dir=ROOT):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project_dir))
    return subprocess.run([sys.executable, str(GUARD), mode], input=json.dumps(event),
                          capture_output=True, text=True, env=env)


class PushTests(unittest.TestCase):
    def test_routine_push_is_allowed(self):
        cmd = 'git add data reports analysis && git commit -m "IPO brief" && git push origin HEAD:main'
        self.assertEqual(guard.push_problems(cmd), [])

    def test_plain_push_is_allowed(self):
        self.assertEqual(guard.push_problems("git push"), [])

    def test_force_push_is_blocked(self):
        for cmd in ("git push --force origin main", "git push -f", "git push --force-with-lease",
                    "git push origin +main", "git push --delete origin task/001-x"):
            self.assertTrue(guard.push_problems(cmd), cmd)

    def test_other_remote_is_blocked(self):
        self.assertTrue(guard.push_problems("git push github main"))
        self.assertTrue(guard.push_problems("cd x; git -C repo push upstream main"))

    def test_non_push_commands_pass(self):
        for cmd in ("git status", "git log --oneline", "echo git push", "python3 -m ipo_agent.snapshot"):
            self.assertEqual(guard.push_problems(cmd), [], cmd)


class CardTests(unittest.TestCase):
    def test_every_card_in_the_repo_passes(self):
        for path in sorted((ROOT / "analysis").glob("*.json")):
            with self.subTest(card=path.name):
                self.assertEqual(guard.file_problems(f"analysis/{path.name}", path.read_text()), [])

    def test_live_numbers_in_a_card_are_rejected(self):
        card = {"name": "X", "source": "rhp", "verdict": "apply", "verdict_text": "Apply",
                "red_flags": ["GMP fell to ₹10 today"]}
        self.assertTrue(guard.card_problems(card))

    def test_bad_enums_and_missing_fields(self):
        self.assertTrue(guard.card_problems({"name": "X", "source": "rhp", "verdict": "buy",
                                             "verdict_text": "Buy"}))
        self.assertTrue(guard.card_problems({"name": "X"}))
        self.assertTrue(guard.card_problems({"name": "X", "source": "rhp", "verdict": "apply",
                                             "verdict_text": "Apply", "anchor_grade": "great"}))

    def test_invalid_json(self):
        self.assertTrue(guard.file_problems("analysis/x.json", "{not json"))


class ReportTests(unittest.TestCase):
    def test_every_report_in_the_repo_passes(self):
        for path in sorted((ROOT / "reports").glob("*.json")):
            with self.subTest(report=path.name):
                self.assertEqual(guard.file_problems(f"reports/{path.name}", path.read_text()), [])

    def test_mismatched_date_and_unknown_fields(self):
        report = {"date": "2026-10-28", "session": "AM", "ipos": {"x": {"verdict": "maybe", "price": 1}}}
        problems = guard.file_problems("reports/2026-10-29-am.json", json.dumps(report))
        self.assertTrue(any("date" in p for p in problems))
        self.assertTrue(any("verdict" in p for p in problems))
        self.assertTrue(any("unknown" in p for p in problems))

    def test_other_files_are_ignored(self):
        self.assertIsNone(guard.file_problems("analysis/zetwerk.md", "# anything"))
        self.assertIsNone(guard.file_problems("analysis/rhp/zetwerk.txt", "anything"))
        self.assertIsNone(guard.file_problems("reports/2026-10-29-am.html", "<html>"))


class HookProcessTests(unittest.TestCase):
    """The hook as Claude Code runs it: JSON on stdin, exit code and stderr out."""

    def test_blocked_push_exits_2(self):
        r = run_hook("pre-bash", {"tool_input": {"command": "git push --force"}})
        self.assertEqual(r.returncode, 2)
        self.assertIn("force", r.stderr)

    def test_allowed_push_exits_0(self):
        r = run_hook("pre-bash", {"tool_input": {"command": "git push origin HEAD:main"}})
        self.assertEqual(r.returncode, 0)

    def test_bad_card_on_disk_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            card = Path(tmp, "analysis", "x.json")
            card.parent.mkdir()
            card.write_text(json.dumps({"name": "X", "source": "rhp", "verdict": "apply",
                                        "verdict_text": "Apply", "summary": "Listed today"}))
            r = run_hook("post-write", {"tool_input": {"file_path": str(card)}}, project_dir=tmp)
            self.assertEqual(r.returncode, 2)
            self.assertIn("today", r.stderr)

    def analysis_hook(self, analysis, rhp="Issue of ₹ 7,756.07 lakhs", source="rhp"):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp, "analysis", "x.md")
            (md.parent / "rhp").mkdir(parents=True)
            md.write_text(analysis)
            (md.parent / "rhp" / "x.txt").write_text(rhp)
            (md.parent / "x.json").write_text(json.dumps({"source": source}))
            return run_hook("post-write", {"tool_input": {"file_path": str(md)}}, project_dir=tmp)

    def test_analysis_reports_missing_figures_without_blocking(self):
        r = self.analysis_hook("Issue ₹77.6 Cr; PAT ₹27.0 Cr")
        self.assertEqual(r.returncode, 0)
        report = json.loads(r.stdout)["hookSpecificOutput"]
        self.assertEqual(report["hookEventName"], "PostToolUse")
        self.assertIn("1/2 ₹ figures found", report["additionalContext"])
        self.assertIn("₹27.0 Cr", report["additionalContext"])
        self.assertNotIn("₹77.6 Cr", report["additionalContext"])

    def test_analysis_fully_found_or_skipped_is_quiet(self):
        for r in (self.analysis_hook("Issue ₹77.6 Cr"),
                  self.analysis_hook("PAT ₹27.0 Cr", source="web")):
            self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_file_outside_project_is_ignored(self):
        r = run_hook("post-write", {"tool_input": {"file_path": "/etc/hostname"}})
        self.assertEqual(r.returncode, 0)

    def test_garbage_input_never_blocks(self):
        r = subprocess.run([sys.executable, str(GUARD), "post-write"], input="not json",
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
