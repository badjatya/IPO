#!/usr/bin/env python3
"""Claude Code hooks for this repo (standard library only).

    guard.py pre-bash     PreToolUse on Bash: block force/mirror/delete pushes and
                          pushes to any remote other than `origin`.
    guard.py post-write   PostToolUse on Write/Edit: check IPO cards (analysis/<key>.json)
                          and verdict files (reports/<date>-<am|pm>.json) against their
                          schemas (ipo_agent/cards.py, ipo_agent/email_render.py).

Exit 2 means "blocked / fix this" and stderr goes to Claude. These hooks also run inside
the scheduled IPO routine, so any bug in the hook itself exits 0: a broken guard must
never stop a run.
"""

import json
import os
import re
import shlex
import sys
from pathlib import Path

VERDICTS = {"apply", "listing_gains", "avoid", "neutral", "pending"}
ANCHOR_GRADES = {"strong", "average", "weak", "pending"}
CARD_FIELDS = {"name", "source", "analysed", "verdict", "verdict_text", "summary", "financials",
               "quota", "positives", "red_flags", "anchor", "anchor_grade"}
CARD_REQUIRED = {"name", "source", "verdict", "verdict_text"}
ENTRY_FIELDS = (CARD_FIELDS - {"name", "source", "analysed"}) | {"best_category", "category_note"}
REPORT_FIELDS = {"date", "session", "headline", "ipos", "notes", "generated", "carried_from"}
# Cards are reused for days, so they hold facts only (ROUTINE.md step 2c).
LIVE_WORDS = re.compile(r"\bGMP\b|\btoday\b|\btomorrow\b|\b(?:over)?subscribed\b", re.I)

CARD_PATH = re.compile(r"^analysis/[^/]+\.json$")
REPORT_PATH = re.compile(r"^reports/(\d{4}-\d{2}-\d{2})-(am|pm)\.json$")


def push_problems(command):
    """Problems with any `git push` inside a shell command line."""
    problems = []
    for part in re.split(r"&&|\|\||;|\||\n", command):
        try:
            words = shlex.split(part)
        except ValueError:
            words = part.split()
        if "git" not in words:
            continue
        rest = words[words.index("git") + 1:]
        while rest and rest[0].startswith("-"):  # git -C dir push ...
            rest = rest[2:] if rest[0] in ("-C", "-c") else rest[1:]
        if not rest or rest[0] != "push":
            continue
        args = rest[1:]
        flags = [a for a in args if a.startswith("-")]
        if any(f in ("-f", "--force", "--mirror", "-d", "--delete") or f.startswith("--force")
               for f in flags):
            problems.append(f"force, mirror or delete push is not allowed: {part.strip()}")
        if any(a.startswith("+") for a in args if not a.startswith("-")):
            problems.append(f"forced refspec (+) is not allowed: {part.strip()}")
        remotes = [a for a in args if not a.startswith("-")]
        if remotes and remotes[0] != "origin":
            problems.append(f"push only to `origin`, not `{remotes[0]}`: {part.strip()}")
    return problems


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def card_problems(card):
    if not isinstance(card, dict):
        return ["a card must be a JSON object"]
    problems = []
    missing = CARD_REQUIRED - card.keys()
    if missing:
        problems.append(f"missing fields: {', '.join(sorted(missing))}")
    unknown = card.keys() - CARD_FIELDS
    if unknown:
        problems.append(f"unknown fields: {', '.join(sorted(unknown))}")
    if card.get("source") not in (None, "rhp", "web"):
        problems.append(f"source must be rhp or web, not {card.get('source')!r}")
    problems += _field_problems(card)
    for key, value in card.items():
        for text in _strings(value):
            hit = LIVE_WORDS.search(text)
            if hit:
                problems.append(f"`{key}` mentions {hit.group(0)!r}: cards hold facts only, "
                                "no GMP, subscription or today/tomorrow (ROUTINE.md step 2c)")
                break
    return problems


def _field_problems(obj, where=""):
    problems = []
    if "verdict" in obj and obj["verdict"] not in VERDICTS:
        problems.append(f"{where}verdict must be one of {sorted(VERDICTS)}, not {obj['verdict']!r}")
    if "anchor_grade" in obj and obj["anchor_grade"] not in ANCHOR_GRADES:
        problems.append(f"{where}anchor_grade must be one of {sorted(ANCHOR_GRADES)}, "
                        f"not {obj['anchor_grade']!r}")
    for key in ("positives", "red_flags"):
        if key in obj and not (isinstance(obj[key], list)
                               and all(isinstance(x, str) for x in obj[key])):
            problems.append(f"{where}{key} must be a list of strings")
    return problems


def report_problems(report, date, session):
    if not isinstance(report, dict):
        return ["a verdict file must be a JSON object"]
    problems = []
    for key in ("date", "session", "ipos"):
        if key not in report:
            problems.append(f"missing `{key}`")
    unknown = report.keys() - REPORT_FIELDS
    if unknown:
        problems.append(f"unknown top-level fields: {', '.join(sorted(unknown))}")
    if "date" in report and report["date"] != date:
        problems.append(f"date {report['date']!r} doesn't match the file name ({date})")
    if "session" in report and report["session"] != session.upper():
        problems.append(f"session {report['session']!r} doesn't match the file name "
                        f"({session.upper()})")
    ipos = report.get("ipos", {})
    if not isinstance(ipos, dict):
        return problems + ["`ipos` must be an object keyed by IPO key"]
    for key, entry in ipos.items():
        if not isinstance(entry, dict):
            problems.append(f"ipos.{key} must be an object")
            continue
        unknown = entry.keys() - ENTRY_FIELDS
        if unknown:
            problems.append(f"ipos.{key}: unknown fields {', '.join(sorted(unknown))}")
        problems += _field_problems(entry, f"ipos.{key}.")
    return problems


def file_problems(rel_path, text):
    """Problems for a repo-relative path, or None if the guard doesn't cover it."""
    rel_path = rel_path.replace(os.sep, "/")
    report = REPORT_PATH.match(rel_path)
    if not (CARD_PATH.match(rel_path) or report):
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return [f"not valid JSON: {e}"]
    if report:
        return report_problems(data, report.group(1), report.group(2))
    return card_problems(data)


def main(mode):
    event = json.load(sys.stdin)
    tool_input = event.get("tool_input") or {}
    if mode == "pre-bash":
        problems = push_problems(tool_input.get("command", ""))
        target = "this push"
    elif mode == "post-write":
        path = Path(tool_input.get("file_path", ""))
        root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".").resolve()
        try:
            rel = path.resolve().relative_to(root)
        except ValueError:
            return 0
        if not path.exists():
            return 0
        problems = file_problems(str(rel), path.read_text(encoding="utf-8"))
        target = str(rel)
    else:
        return 0
    if not problems:
        return 0
    print(f"guard: {target} needs fixing:", file=sys.stderr)
    for p in problems:
        print(f"  - {p}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
    except SystemExit:
        raise
    except Exception as e:  # a guard bug must never block the routine
        print(f"guard: internal error ignored: {e!r}", file=sys.stderr)
        sys.exit(0)
