"""Tests for deepseek.py. Run: python3 -m unittest discover -s .claude/deepseek

No network: the model is a scripted fake, and each step runs against a throwaway git repo.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import deepseek  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MODEL = "deepseek/deepseek-test"
TRAILER = "AI-Agent: DeepSeek deepseek-test (OpenRouter)"

ROADMAP = """# Roadmap

### 900 · Test task

| | |
| --- | --- |
| Slug | `900-test-task` |
| Status | **Ready** |

Add a helper.

### 901 · Later task

| | |
| --- | --- |
| Slug | `901-later-task` |
| Status | Waiting on 900 |

## Next section
"""


def call(name, **args):
    return {"id": f"call-{name}", "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


def fake_model(script):
    """A chat function that plays back `script`: each item is a list of tool calls, a callable
    run for its side effect (then the next item), or a final string."""
    script = list(script)

    def chat(body):
        while callable(script[0]):
            script.pop(0)()
        item = script.pop(0)
        msg = {"role": "assistant", "content": item if isinstance(item, str) else None}
        if not isinstance(item, str):
            msg["tool_calls"] = item
        return {"choices": [{"message": msg}], "usage": {"cost": 0.001}}
    return chat


class RuleTests(unittest.TestCase):
    def test_planning_steps_write_only_plan(self):
        for mode in ("plan", "revise"):
            self.assertIsNone(deepseek.write_problem("docs/tasks/900-x/plan.md", mode, "900-x"))
            self.assertTrue(deepseek.write_problem("ipo_agent/x.py", mode, "900-x"))
            self.assertTrue(deepseek.write_problem("docs/tasks/900-x/plan-review.md", mode, "900-x"))

    def test_build_protected_paths(self):
        for rel in ("analysis/x.json", "reports/2026-10-29-am.json", "data/latest.md", "ROUTINE.md",
                    "config/delivery.json", "CLAUDE.md", "AGENTS.md", ".claude/hooks/guard.py",
                    "docs/tasks/ROADMAP.md", "docs/tasks/900-x/plan-review.md",
                    "docs/tasks/900-x/code-review.md", "docs/tasks/901-y/plan.md", ".env.local",
                    "web/.env.local", ".git/config", ".gitignore"):
            self.assertTrue(deepseek.write_problem(rel, "build", "900-x"), rel)
        for rel in ("ipo_agent/figures.py", "tests/test_figures.py", "docs/ai.md",
                    "docs/tasks/900-x/plan.md", ".github/workflows/ci.yml", "web/app/page.tsx"):
            self.assertIsNone(deepseek.write_problem(rel, "build", "900-x"), rel)

    def test_respond_may_write_code_review(self):
        self.assertIsNone(deepseek.write_problem("docs/tasks/900-x/code-review.md", "respond", "900-x"))

    def test_inside_refuses_escapes_and_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "wt"
            root.mkdir()
            (root / "out").symlink_to(Path(d))
            self.assertEqual(deepseek.inside(root, "a/b.py"), "a/b.py")
            self.assertIsNone(deepseek.inside(root, "../x"))
            self.assertIsNone(deepseek.inside(root, "/etc/passwd"))
            self.assertIsNone(deepseek.inside(root, "out/secret"))

    def test_commands(self):
        root = Path("/repo")
        ok = ["git status", "git diff main...HEAD", "git log --oneline", "python3 -m unittest discover -s tests",
              "python3 tools/figures.py --all", "python3 -m ipo_agent.figures_check --all",
              "python3 -m ipo_agent.outcomes --no-fetch", "python3 -m ipo_agent.quiet AM --check", "npm test", "npm run lint", "npx --no-install tsc --noEmit"]
        for cmd in ok:
            self.assertIsNone(deepseek.command_problem(cmd.split(), "build", root, root), cmd)
        refused = ["git commit -m x", "git push", "git -c x=y status", "git diff --output=f",
                   "git diff --no-index /a /b", "python3 -c print(1)", "python3 ../../x.py",
                   "python3 -m ipo_agent.snapshot --print", "python3 -m ipo_agent.rhp ACME",
                   "python3 -m ipo_agent.outcomes", "python3 -m ipo_agent.quiet AM", "python3 -m json.tool",
                   "npm install left-pad", "npx tsc", "bash -c ls", "rm -rf x", "curl http://x"]
        for cmd in refused:
            self.assertTrue(deepseek.command_problem(cmd.split(), "build", root, root), cmd)
        self.assertTrue(deepseek.command_problem(["python3", "-m", "unittest"], "plan", root, root))
        self.assertIsNone(deepseek.command_problem(["git", "status"], "plan", root, root))

    def test_status_and_rounds(self):
        text = "---\ntask: 900-x\nstatus: planning\n---\n\n# 900: X\n\nstatus: not this one\n"
        self.assertEqual(deepseek.plan_status(text), "planning")
        changed = deepseek.set_status(text, "plan-review")
        self.assertEqual(deepseek.plan_status(changed), "plan-review")
        self.assertIn("status: not this one", changed)
        review = "# R\n\n## Round 1 (x)\n\n**Verdict:** Changes requested\n\n## Round 2 (y)\n\n**Verdict:** Approved\n"
        self.assertEqual(deepseek.latest_round(review), (2, "Approved"))
        self.assertEqual(deepseek.latest_round("# empty"), (0, ""))

    def test_responses_cut(self):
        text = "## Round 1\nA\n## Responses (DeepSeek)\nB\n## Round 2\nC\n## Responses (DeepSeek)\nD\n"
        self.assertEqual(text[deepseek.responses_cut(text):], "## Responses (DeepSeek)\nD\n")
        no_table = "## Round 1\nA\n## Responses (DeepSeek)\nB\n## Round 2\nC\n"
        self.assertEqual(deepseek.responses_cut(no_table), len(no_table))

    def test_roadmap_entry(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "docs/tasks").mkdir(parents=True)
            (Path(d) / "docs/tasks/ROADMAP.md").write_text(ROADMAP)
            title, slug, status, text = deepseek.roadmap_entry(Path(d), "900")
            self.assertEqual((title, slug), ("Test task", "900-test-task"))
            self.assertIn("Ready", status)
            self.assertIn("Add a helper.", text)
            self.assertNotIn("901", text)
            self.assertIsNone(deepseek.roadmap_entry(Path(d), "999"))


class StepTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.main = Path(self.tmp.name) / "repo"
        files = {
            "AGENTS.md": "# Agent rules\n",
            "docs/tasks/README.md": "# Tasks\n",
            "docs/tasks/ROADMAP.md": ROADMAP,
            ".gitignore": ".worktrees/\n.deepseek-logs/\n",
            "analysis/acme.md": "cached analysis\n",
        }
        for rel, text in files.items():
            (self.main / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.main / rel).write_text(text)
        (self.main / "docs/tasks/templates").mkdir()
        shutil.copy(ROOT / "docs/tasks/templates/plan.md", self.main / "docs/tasks/templates/plan.md")
        self.git(self.main, "init", "-q", "-b", "main")
        self.git(self.main, "config", "user.email", "t@example.com")
        self.git(self.main, "config", "user.name", "Test")
        self.git(self.main, "add", "-A")
        self.git(self.main, "commit", "-q", "-m", "init")
        self.wt = self.main / ".worktrees/900-test-task"
        self.plan = self.wt / "docs/tasks/900-test-task/plan.md"

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, cwd, *args):
        return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                              text=True).stdout

    def step(self, mode, script, **kw):
        s = deepseek.Step(self.main, "900", mode, MODEL, fake_model(script), out=lambda *a, **k: None)
        return s, s.run(kw.get("max_turns", 20), kw.get("max_cost", 1.0))

    def planned(self):
        """Run a plan step that fills in the plan, and return the plan's text."""
        filled = lambda: self.plan.write_text(self.plan.read_text().replace(
            "## Steps\n", "## Steps\n\nAdd `helper.py` with a test.\n"))
        self.step("plan", [[call("read_file", path="AGENTS.md")], filled, "Plan written."])
        return self.plan.read_text()

    def approve(self):
        self.plan.write_text(deepseek.set_status(self.plan.read_text(), "approved"))
        (self.plan.parent / "plan-review.md").write_text("# Plan review\n\n## Round 1 (d)\n\n**Verdict:** Approved\n")
        self.git(self.wt, "add", "-A")
        self.git(self.wt, "commit", "-q", "-m", "Plan review 900 round 1: Approved")

    def test_plan_makes_worktree_and_hands_off(self):
        text = self.planned()
        self.assertEqual(self.git(self.wt, "branch", "--show-current").strip(), "task/900-test-task")
        self.assertEqual(deepseek.plan_status(text), "plan-review")
        self.assertIn(f"planner: DeepSeek deepseek-test (OpenRouter)", text)
        self.assertIn("# 900: Test task", text)
        self.assertIn("> Add a helper.", text)
        log = self.git(self.wt, "log", "-1", "--format=%s%n%b")
        self.assertIn("Plan 900: Test task", log)
        self.assertIn(TRAILER, log)
        self.assertEqual(self.git(self.main, "branch", "--show-current").strip(), "main")

    def test_plan_tools_refuse_other_files(self):
        s, _ = self.step("plan", [
            [call("write_file", path="ipo_agent/x.py", content="x"),
             call("write_file", path="../../escape.txt", content="x"),
             call("read_file", path="../../.env.local"),
             call("run", command="python3 -m unittest")],
            lambda: self.plan.write_text(self.plan.read_text() + "\nfilled\n"),
            "done"])
        self.assertFalse((self.wt / "ipo_agent/x.py").exists())
        self.assertFalse((self.main.parent / "escape.txt").exists())

    def test_plan_needs_a_ready_task(self):
        s = deepseek.Step(self.main, "901", "plan", MODEL, fake_model([]), out=lambda *a, **k: None)
        with self.assertRaises(deepseek.Stop) as e:
            s.run(5, 1.0)
        self.assertEqual(e.exception.code, 1)

    def test_empty_plan_is_not_handed_off(self):
        with self.assertRaises(deepseek.Stop) as e:
            self.step("plan", ["nothing to do"])
        self.assertEqual(e.exception.code, 3)
        self.assertEqual(deepseek.plan_status(self.plan.read_text()), "planning")

    def test_turn_limit_stops_without_hand_off(self):
        with self.assertRaises(deepseek.Stop) as e:
            self.step("plan", [[call("list_dir")]] * 5, max_turns=3)
        self.assertEqual(e.exception.code, 2)

    def test_build_commits_with_trailer_and_hands_off(self):
        self.planned()
        with self.assertRaises(deepseek.Stop):  # not approved yet
            self.step("build", ["x"])
        self.approve()
        verified = lambda: self.plan.write_text(self.plan.read_text().replace(
            "Test commands run, with their output pasted.", "OK"))
        s, _ = self.step("build", [
            [call("write_file", path="helper.py", content="X = 1\n")],
            [call("commit", message="Task 900: helper", paths=["helper.py"])],
            [call("commit", message="sneaky", paths=["analysis/acme.md"])],
            verified, "Built."])
        self.assertEqual(deepseek.plan_status(self.plan.read_text()), "code-review")
        log = self.git(self.wt, "log", "--format=%s|%b", "main..HEAD")
        self.assertIn("Task 900: helper", log)
        self.assertIn("Task 900: ready for code review", log)
        self.assertNotIn("sneaky", log)
        self.assertEqual(log.count(TRAILER), 3)  # plan, helper, hand-off
        self.assertEqual(self.git(self.wt, "status", "--porcelain"), "")

    def test_build_that_touches_a_protected_path_is_not_handed_off(self):
        self.planned()
        self.approve()
        # What a script run through `run` could do: the file tools can't stop it, the check can.
        sneaky = lambda: (self.wt / "analysis/acme.md").write_text("changed\n")
        with self.assertRaises(deepseek.Stop) as e:
            self.step("build", [sneaky, "Built."])
        self.assertEqual(e.exception.code, 3)
        self.assertIn("analysis/acme.md", str(e.exception))
        self.assertEqual(deepseek.plan_status(self.plan.read_text()), "approved")

    def test_build_restores_frontmatter_and_keeps_the_approved_plan(self):
        self.planned()
        self.approve()
        tamper = lambda: self.plan.write_text(deepseek.set_status(self.plan.read_text(), "merge-ready"))
        s, _ = self.step("build", [tamper, "Built."])
        self.assertEqual(deepseek.plan_status(self.plan.read_text()), "code-review")
        self.assertTrue(s.warnings)

        self.plan.write_text(deepseek.set_status(self.plan.read_text(), "approved"))
        self.git(self.wt, "commit", "-qam", "back to approved")
        rewrite = lambda: self.plan.write_text(self.plan.read_text().replace("Add `helper.py`", "Add anything"))
        with self.assertRaises(deepseek.Stop) as e:
            self.step("build", [rewrite, "Built."])
        self.assertIn("approved plan", str(e.exception))

    def test_respond_may_change_only_its_responses(self):
        self.planned()
        self.approve()
        self.step("build", ["Built."])
        review = self.plan.parent / "code-review.md"
        review.write_text("# Code review\n\n## Round 1 (d)\n\n**Verdict:** Changes requested\n\n"
                          "| 1 | Major | `helper.py:1` | bad | fix |\n\n## Responses (DeepSeek)\n\n"
                          "| # | Response | Commit |\n| --- | --- | --- |\n| 1 | | |\n")
        self.plan.write_text(deepseek.set_status(self.plan.read_text(), "code-changes"))
        self.git(self.wt, "add", "-A")
        self.git(self.wt, "commit", "-q", "-m", "Code review 900 round 1")

        answer = lambda: review.write_text(review.read_text().replace("| 1 | | |", "| 1 | Fixed | abc |"))
        self.step("respond", [answer, "Responded."])
        self.assertEqual(deepseek.plan_status(self.plan.read_text()), "code-review")
        self.assertIn("respond to code review round 1", self.git(self.wt, "log", "-1", "--format=%s"))

        self.plan.write_text(deepseek.set_status(self.plan.read_text(), "code-changes"))
        self.git(self.wt, "commit", "-qam", "again")
        soften = lambda: review.write_text(review.read_text().replace("| Major |", "| Nit |"))
        with self.assertRaises(deepseek.Stop) as e:
            self.step("respond", [soften, "Responded."])
        self.assertIn("Responses", str(e.exception))

    def test_build_resumes_after_a_limit(self):
        self.planned()
        self.approve()
        with self.assertRaises(deepseek.Stop) as e:
            self.step("build", [[call("write_file", path="helper.py", content="X = 1\n")]], max_turns=1)
        self.assertEqual(e.exception.code, 2)
        self.step("build", ["Built."])  # uncommitted helper.py from the first run is allowed
        self.assertEqual(deepseek.plan_status(self.plan.read_text()), "code-review")
        self.assertIn("helper.py", self.git(self.wt, "ls-files"))

    def test_plan_resumes_after_a_limit(self):
        filled = lambda: self.plan.write_text(self.plan.read_text() + "\nfilled\n")
        with self.assertRaises(deepseek.Stop):
            self.step("plan", [filled, [call("list_dir")]], max_turns=1)
        self.step("plan", ["Plan written."])
        self.assertEqual(deepseek.plan_status(self.plan.read_text()), "plan-review")

    def test_key_is_redacted_and_never_handed_off(self):
        self.planned()
        self.approve()
        key = "sk-or-v1-" + "ab12" * 10
        (self.main / ".env.local").write_text(f"OPENROUTER_API_KEY={key}\n")
        (self.wt / "leak.py").write_text("print(open('../../.env.local').read())\n")
        copied = lambda: (self.wt / "fixture.txt").write_text(key)
        s = deepseek.Step(self.main, "900", "build", MODEL,
                          fake_model([[call("run", command="python3 leak.py")], copied, "Built."]),
                          out=lambda *a, **k: None, secrets=[key])
        with self.assertRaises(deepseek.Stop) as e:
            s.run(20, 1.0)
        self.assertEqual(e.exception.code, 3)
        self.assertIn("fixture.txt: holds an OpenRouter API key", str(e.exception))
        log = s.log_path.read_text()
        self.assertNotIn(key, log)
        self.assertIn("OPENROUTER_API_KEY=[REDACTED]", log)

    def test_run_gets_no_secrets(self):
        self.planned()
        self.approve()
        os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
        try:
            s = deepseek.Step(self.main, "900", "build", MODEL, None, out=lambda *a, **k: None)
            s.open_worktree()
            (self.wt / "env.py").write_text("import os; print(sorted(os.environ))")
            out = s.t_run("python3 env.py")
        finally:
            del os.environ["OPENROUTER_API_KEY"]
        self.assertTrue(out.startswith("exit 0"), out)
        self.assertNotIn("OPENROUTER", out)


if __name__ == "__main__":
    unittest.main()
