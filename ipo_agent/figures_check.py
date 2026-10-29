"""Figures check: every ₹ figure an analysis states must appear in its RHP text.

Reads one analysis (``analysis/<key>.md``), extracts its ₹ figures (units: crore,
lakh, million, billion, and composed ones such as "lakh Cr"), converts them all to
rupees, and reports which ones appear in that IPO's RHP extract
(``analysis/rhp/<key>.txt``), within half a unit of the figure's last written digit
in the figure's own unit. Approximate figures (``≈`` or ``~``) are counted separately
and skipped. Analyses whose card says ``"source": "web"``, or that have no RHP
extract, are skipped.

This is a **text-figure verifier, not a semantic auditor**: a "found" figure appeared
somewhere in the RHP text, possibly in a different context. It reports only and never
fails — the exit code never depends on how many figures were found, so the routine's
twice-daily pushes to ``main`` are never gated by it.

Usage:
    python3 -m ipo_agent.figures_check bls-polymers
    python3 -m ipo_agent.figures_check --all
    python3 -m ipo_agent.figures_check --all --root /path/to/repo
"""

import argparse
import json
import pathlib
import re
import sys
from dataclasses import dataclass, field

ROOT = pathlib.Path(__file__).resolve().parent.parent

# --- units --------------------------------------------------------------------
# token → rupees multiplier. Short tokens (L, l, cr, mn) match only as whole
# words, so "₹20 Listing gain" is ₹20 with no unit, not ₹20 lakh.
_MULT = {
    "lakh": 10 ** 5, "lakhs": 10 ** 5, "lac": 10 ** 5, "lacs": 10 ** 5,
    "L": 10 ** 5, "l": 10 ** 5,
    "crore": 10 ** 7, "crores": 10 ** 7, "cr": 10 ** 7,
    "million": 10 ** 6, "millions": 10 ** 6, "mn": 10 ** 6,
    "billion": 10 ** 9, "billions": 10 ** 9, "bn": 10 ** 9,
}

UNITS = r"\b(?:" + "|".join(sorted(_MULT, key=len, reverse=True)) + r")\b"

# --- number shapes (analysis side) ---------------------------------------------
_NUM = r"[\d][\d,]*(?:\.\d+)?"

_WORDS = ("zero one two three four five six seven eight nine ten eleven twelve "
          "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty "
          "thirty forty fifty sixty seventy eighty ninety hundred thousand").split()
_WORD_ALT = r"(?:" + "|".join(sorted(_WORDS, key=len, reverse=True)) + r")"
_NUMBER = rf"(?:{_NUM}|{_WORD_ALT}(?:\s+{_WORD_ALT})*)"

# A figure: optional ≈/~ marker, a ₹ or Rs. prefix, a number (digits or words),
# optionally a range (A–B, en dash or hyphen, unit after B applies to both), and an
# optional unit.
_FIGURE = re.compile(
    rf"(?P<approx>[≈~])?\s*(?:₹|Rs\.)\s*"
    rf"(?P<a>{_NUMBER})"
    rf"(?:\s*(?:–|-)\s*(?P<b>{_NUMBER}))?"
    rf"(?:\s+(?P<unit>{UNITS}(?:\s+{UNITS})*))?",
    re.IGNORECASE,
)

# --- number shapes (RHP side) ---------------------------------------------------
# Candidates: ₹/Rs.-prefixed numbers with an optional unit, or bare numbers carrying
# an explicit unit word ("28,300.00 million" still matches without a prefix). Bare
# table cells without a unit word (e.g. under a "(₹ in lakhs)" header) are not
# candidates, and neither is a bare number right after a Latin letter + space
# ("USD 1.00 million" is not rupees).
_CANDIDATE = re.compile(
    rf"(?:(?P<pre>₹|Rs\.)\s*)?"
    rf"(?P<num>{_NUM})"
    rf"(?:\s+(?P<unit>{UNITS}(?:\s+{UNITS})*))?",
    re.IGNORECASE,
)

_ONES = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: v for w, v in zip(
    "twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20, 100, 10))}
_SCALES = {"hundred": 100, "thousand": 1000}


@dataclass
class Figure:
    """One ₹ figure as written in an analysis."""
    text: str                # as written: "₹30,213 Cr" or "₹313"
    rupees: float            # normalised to rupees, or None if the words don't parse
    decimals: int            # digits after the decimal point, as written
    unit_multiplier: float   # 1 when no unit; product for composed units ("lakh Cr")
    approximate: bool        # prefixed ≈ or ~: the writer marked it as computed


@dataclass
class Check:
    """The result of checking one analysis (or why it was skipped)."""
    key: str = ""
    found: int = 0
    total: int = 0
    missing: list = field(default_factory=list)   # figure texts not found in the RHP
    approximate: int = 0                          # ≈/~ figures, not checked
    skipped: bool = False
    reason: str = ""                              # why skipped, when skipped
    note: str = ""                                # e.g. "no card" or "card unreadable"

    @property
    def share(self):
        """Fraction of figures found, 0.0–1.0; None when there were none."""
        return self.found / self.total if self.total else None


def _unit_multiplier(unit):
    """'lakh Cr' → 10**12, '' → 1, or None for an unrecognised token."""
    if not unit:
        return 1
    total = 1
    for token in unit.split():
        value = _MULT.get(token) or _MULT.get(token.lower())
        if value is None:
            return None
        total *= value
    return total


def _words_to_number(words):
    """'two hundred' → 200; raise ValueError on an unknown word."""
    total = current = 0
    for word in words:
        word = word.lower()
        if word in _ONES:
            current += _ONES[word]
        elif word in _TENS:
            current += _TENS[word]
        elif word in _SCALES:
            current = (current or 1) * _SCALES[word]
        else:
            raise ValueError(word)
    return total + current


def _parse_number(text):
    """'30,213' → 30213.0; 'two hundred' → 200.0; unparseable → None."""
    if re.fullmatch(r"[\d][\d,]*(?:\.\d+)?", text):
        return float(text.replace(",", ""))
    try:
        return float(_words_to_number(text.split()))
    except ValueError:
        return None


def _decimals(num_text):
    m = re.search(r"\.(\d+)$", num_text)
    return len(m.group(1)) if m else 0


def extract_figures(text):
    """Every ₹ figure in an analysis: numbers, units, ranges, word numbers, ≈/~."""
    figures = []
    for m in _FIGURE.finditer(text):
        unit = m.group("unit") or ""
        multiplier = _unit_multiplier(unit) or 1
        for group in ("a", "b"):
            num = m.group(group)
            if num is None:
                continue
            num = num.rstrip(",")   # "₹693, P/E" — the comma is punctuation, not the number
            text_fig = "₹" + num + (f" {unit.strip()}" if unit else "")
            parsed = _parse_number(num)
            figures.append(Figure(
                text=text_fig,
                rupees=parsed * multiplier if parsed is not None else None,
                decimals=_decimals(num),
                unit_multiplier=multiplier,
                approximate=bool(m.group("approx")),
            ))
    return figures


def rhp_candidates(rhp_text):
    """Every matchable figure in an RHP extract, all normalised to rupees."""
    candidates = []
    for m in _CANDIDATE.finditer(rhp_text):
        pre, unit = m.group("pre"), m.group("unit") or ""
        if not pre and not unit:
            continue  # a bare table cell, e.g. under "(₹ in lakhs)"
        multiplier = _unit_multiplier(unit)
        if multiplier is None:
            continue
        if not pre and m.start() >= 2 and re.match(r"[A-Za-z]\s", rhp_text[m.start() - 2:m.start()]):
            continue  # "USD 1.00 million" is not rupees
        candidates.append(float(m.group("num").rstrip(",").replace(",", "")) * multiplier)
    return candidates


def check_one(analysis_text, rhp_text):
    """Check one analysis against one RHP extract. Never fails the caller."""
    candidates = rhp_candidates(rhp_text)
    found = 0
    missing = []
    approximate = 0
    for fig in extract_figures(analysis_text):
        if fig.approximate:
            approximate += 1
            continue
        if fig.rupees is None:  # unparseable word number: report as missing
            missing.append(fig.text)
            continue
        tolerance = 0.5 * (10 ** -fig.decimals) * fig.unit_multiplier
        if any(fig.rupees - tolerance <= c <= fig.rupees + tolerance for c in candidates):
            found += 1
        else:
            missing.append(fig.text)
    return Check(found=found, total=found + len(missing), missing=missing,
                 approximate=approximate)


def card_source(root, key):
    """The card's ``source`` (``"web"``/``"rhp"``/None) plus a note for the caller.

    A missing or unparseable card never skips an analysis — the caller checks it
    anyway; the note records why no source was read.
    """
    card = root / "analysis" / f"{key}.json"
    if not card.exists():
        return None, "no card"
    try:
        return json.loads(card.read_text(encoding="utf-8")).get("source"), ""
    except Exception as e:  # a broken card is data, not a blocker
        return None, f"card unreadable ({e.__class__.__name__})"


def check_key(root, key):
    """Check the saved analysis ``key`` inside ``root`` (a path or a path-like)."""
    root = pathlib.Path(root)
    analysis = root / "analysis" / f"{key}.md"
    if not analysis.exists():
        return Check(key=key, skipped=True, reason=f"no analysis/{key}.md")
    source, note = card_source(root, key)
    if source == "web":
        return Check(key=key, skipped=True, reason="source: web")
    rhp = root / "analysis" / "rhp" / f"{key}.txt"
    if not rhp.exists():
        return Check(key=key, skipped=True, reason=f"no analysis/rhp/{key}.txt")
    check = check_one(analysis.read_text(encoding="utf-8"),
                      rhp.read_text(encoding="utf-8"))
    check.key = key
    check.note = note
    return check


def line(check):
    """One output line for a check."""
    if check.skipped:
        return f"{check.key}: skipped ({check.reason})"
    pct = f" ({round(check.share * 100)}%)" if check.share is not None else ""
    approx = f", {check.approximate} approximate" if check.approximate else ""
    note = f" [{check.note}]" if check.note else ""
    return f"{check.key}: {check.found}/{check.total} ₹ figures found{pct}{approx}{note}"


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Check that every ₹ figure in an analysis appears in its RHP text.")
    ap.add_argument("keys", nargs="*", metavar="KEY",
                    help="IPO key(s), e.g. bls-polymers")
    ap.add_argument("--all", action="store_true",
                    help="check every analysis/<key>.md, and print a TOTAL line")
    ap.add_argument("--root", type=pathlib.Path, default=ROOT,
                    help="repo root (default: the check's own repo)")
    args = ap.parse_args(argv)

    root = args.root
    keys = sorted(p.stem for p in (root / "analysis").glob("*.md")) if args.all else args.keys
    if not keys:
        ap.error("give one or more IPO keys, or --all")

    checks = [check_key(root, key) for key in keys]
    checked = [c for c in checks if not c.skipped]
    for c in checks:
        print(line(c))
        if not c.skipped and c.missing:
            print(f"  not found: {', '.join(c.missing)}")

    if args.all:
        found = sum(c.found for c in checked)
        total = sum(c.total for c in checked)
        pct = f" ({round(100 * found / total)}%)" if total else ""
        print(f"TOTAL: {found}/{total} ₹ figures found{pct} "
              f"across {len(checks)} analyses ({len(checks) - len(checked)} skipped)")
    return 0  # report only: a missing or approximate figure never fails the run


if __name__ == "__main__":
    sys.exit(main())
