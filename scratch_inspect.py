"""Scratch: first rows of shareholding + announcements for 016 tests."""
import json

BASE = "tests/fixtures/nse_stock"


def load(name):
    return json.load(open(f"{BASE}/{name}", encoding="utf-8"))


def rows_of(data):
    if isinstance(data, list):
        return data
    for key in ("data", "resCmpData", "announcements"):
        if isinstance(data.get(key), list):
            return data[key]
    return []


data = load("shareholding.json")
rows = rows_of(data)
print("== shareholding first 3 (raw order)")
for r in rows[:3]:
    print("  ", r.get("date"), r.get("pr_and_prgrp"), r.get("submissionDate"))

data = load("announcements.json")
rows = rows_of(data)
print("== announcements first 2 (raw order)")
for r in rows[:2]:
    print("  ", r.get("an_dt"), r.get("seq_id"), r.get("attchmntText")[:60])

# dates ascending
sh = [r for r in rows_of(load("shareholding.json"))]
asc = sorted(sh, key=lambda r: r.get("date") or "")
print("== shareholding asc first 2 / last 2")
for r in asc[:2] + asc[-2:]:
    print("  ", r.get("date"), r.get("pr_and_prgrp"))