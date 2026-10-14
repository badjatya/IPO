"""Cached per-IPO "cards": the slow-changing part of the email (what the company does,
financials, quota, positives, red flags, anchor book, baseline verdict). Written once per IPO
at analysis time to analysis/<key>.json and reused every run, so a run only writes the parts
that move with the numbers (verdict override, best category, headline).

Card schema:
{
  "name": "HD Fire Protect Limited",
  "source": "rhp" | "web",        # "web" = stub written before the RHP was filed; replaced
                                  # by the full card once analysis/<key>.md exists
  "analysed": "2026-10-12",
  "verdict": "apply|listing_gains|avoid|neutral|pending", "verdict_text": "Apply",
  "summary": "...", "financials": "...", "quota": "...",
  "positives": ["..."], "red_flags": ["..."],   # facts only: no GMP, subscription or "today"
  "anchor": "...", "anchor_grade": "strong|average|weak|pending"
}
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIR = ROOT / "analysis"


def path(key):
    return DIR / f"{key}.json"


def load(key):
    p = path(key)
    return json.loads(p.read_text()) if p.exists() else None


def needs_card(key):
    """No card yet, or only a web stub while the full RHP analysis now exists."""
    card = load(key)
    return card is None or ((DIR / f"{key}.md").exists() and card.get("source") != "rhp")
